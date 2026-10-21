"""MCP over HTTP (Streamable HTTP transport, JSON responses only) - standard library only.

Serves the same tools as the stdio server from the machine that runs StarUML (e.g. a
Windows VM), so an agent on another machine can drive it:

    python -m staruml5 mcp --http 0.0.0.0:8765 --root C:\\uml --token <secret>

    claude mcp add --transport http staruml5-vm http://<vm-ip>:8765/mcp \\
        --header "Authorization: Bearer <secret>"

Tool paths are relative to --root and may not leave it. Files move with plain HTTP:

    POST   /mcp            JSON-RPC request (or batch) -> JSON response
    GET    /files/<path>   download a file under --root (a directory -> JSON listing)
    PUT    /files/<path>   upload a file under --root (parent directories are created)

Every request needs ``Authorization: Bearer <token>`` when a token is set. Requests
carrying an ``Origin`` header (browsers) are refused, against DNS rebinding.
"""
from __future__ import annotations

import hmac
import json
import os
import queue
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

from . import mcp_server

MAX_BODY = 64 * 1024 * 1024
LOOPBACK = ("127.0.0.1", "localhost", "::1")

_lock = threading.Lock()   # one tool call / file write at a time: StarUML and .uml files are not shared-safe

# Log lines go through a queue: a write to a Windows console blocks while text is being
# selected in it, and that must not hold up responses.
_log = queue.Queue()


def _log_writer():
    while True:
        line = _log.get()
        try:
            sys.stderr.write(line)
            sys.stderr.flush()
        except (OSError, ValueError):
            pass


threading.Thread(target=_log_writer, daemon=True).start()


def _disable_quick_edit():
    """Turn off QuickEdit for this Windows console, so a stray click does not start a selection."""
    if os.name != "nt":
        return
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-10)   # STD_INPUT_HANDLE
        mode = ctypes.c_uint32()
        if k.GetConsoleMode(h, ctypes.byref(mode)):
            k.SetConsoleMode(h, (mode.value & ~0x0040) | 0x0080)   # -ENABLE_QUICK_EDIT_MODE, +ENABLE_EXTENDED_FLAGS
    except (AttributeError, OSError):
        pass


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            return   # the client gave up (e.g. its timeout); nothing to report
        _log.put("error while handling a request from %s:\n%s" % (client_address[0], traceback.format_exc()))


class Handler(BaseHTTPRequestHandler):
    server_version = "staruml5"
    token = None

    def log_message(self, fmt, *args):
        _log.put("%s %s\n" % (self.address_string(), fmt % args))

    def _send(self, code, body=b"", ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        if body:
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _allowed(self) -> bool:
        if self.headers.get("Origin"):
            self._send(403, {"error": "browser (Origin) requests are not allowed"})
            return False
        if self.token:
            got = self.headers.get("Authorization", "").encode("utf-8")
            if not hmac.compare_digest(got, ("Bearer " + self.token).encode("utf-8")):
                self._send(401, {"error": "missing or wrong bearer token"})
                return False
        return True

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("body larger than %d bytes" % MAX_BODY)
        return self.rfile.read(n)

    def _file_path(self):
        rel = unquote(urlsplit(self.path).path[len("/files/"):])
        return rel, mcp_server.resolve(rel or ".")

    def _route(self):
        path = urlsplit(self.path).path
        if path == "/mcp":
            return "mcp"
        if path == "/files" or path.startswith("/files/"):
            return "files"
        return None

    def do_POST(self):
        if not self._allowed():
            return
        if self._route() != "mcp":
            return self._send(404, {"error": "not found"})
        try:
            msg = json.loads(self._body().decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            return self._send(400, {"jsonrpc": "2.0", "id": None,
                                    "error": {"code": -32700, "message": "parse error: %s" % e}})
        batch = isinstance(msg, list)
        with _lock:
            out = [r for r in map(mcp_server.dispatch, msg if batch else [msg]) if r is not None]
        if not out:
            return self._send(202)   # notifications / responses only
        self._send(200, out if batch else out[0])

    def do_GET(self):
        if not self._allowed():
            return
        route = self._route()
        if route == "mcp":
            return self._send(405, {"error": "no server-initiated stream; use POST"})
        if route != "files":
            return self._send(404, {"error": "not found"})
        try:
            rel, full = self._file_path()
        except ValueError as e:
            return self._send(403, {"error": str(e)})
        if os.path.isdir(full):
            items = [{"name": n, "dir": os.path.isdir(os.path.join(full, n)),
                      "size": os.path.getsize(os.path.join(full, n))} for n in sorted(os.listdir(full))]
            return self._send(200, items)
        if not os.path.isfile(full):
            return self._send(404, {"error": "no such file: %s" % rel})
        with open(full, "rb") as f:
            self._send(200, f.read(), "application/octet-stream")

    def do_PUT(self):
        if not self._allowed():
            return
        if self._route() != "files":
            return self._send(404, {"error": "not found"})
        try:
            rel, full = self._file_path()
            data = self._body()
        except ValueError as e:
            return self._send(403, {"error": str(e)})
        if not rel or os.path.isdir(full):
            return self._send(400, {"error": "PUT needs a file path"})
        with _lock:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            tmp = full + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, full)
        self._send(201, {"path": rel, "size": len(data)})

    def do_DELETE(self):
        if self._allowed():
            self._send(405, {"error": "sessions are not used"})


def parse_address(addr: str):
    host, sep, port = addr.rpartition(":")
    return (host.strip("[]") if sep else "127.0.0.1"), int(port)


def make_server(addr: str, root: str = None, token: str = None) -> Server:
    host, port = parse_address(addr)
    token = token or os.environ.get("STARUML5_TOKEN") or None
    if not token and host not in LOOPBACK:
        raise ValueError("refusing to listen on %s without a token: pass --token or set STARUML5_TOKEN" % host)
    mcp_server.ROOT = os.path.realpath(root or os.getcwd())
    os.makedirs(mcp_server.ROOT, exist_ok=True)
    mcp_server.INSTRUCTIONS = (
        "This server runs on a remote machine. Every path argument is relative to its workspace "
        "(%s); absolute paths outside it are rejected. Move files with HTTP on the same host and token: "
        "GET /files/<path> downloads (a directory gives a JSON listing), PUT /files/<path> uploads."
        % mcp_server.ROOT)
    Handler.token = token
    return Server((host, port), Handler)


def serve_http(addr: str, root: str = None, token: str = None):
    httpd = make_server(addr, root, token)
    _disable_quick_edit()
    host, port = httpd.server_address[:2]
    sys.stderr.write("staruml5 MCP on http://%s:%d/mcp  root=%s  token=%s\n"
                     % (host, port, mcp_server.ROOT, "on" if Handler.token else "off"))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
