"""Drive a running StarUML 5 through its COM automation API.

Runs ``bridge/staruml_bridge.js`` with Windows Script Host (``cscript``). On
Linux/macOS the same script runs under Wine (``wine cscript``), so the bridge
works wherever StarUML itself runs. No pywin32 needed.

Environment variables:
    STARUML5_WINE         wine executable to use on non-Windows hosts (default: ``wine``)
    WINEPREFIX            prefix that has StarUML installed (see wine/ in the repo)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "staruml_bridge.js")
IS_WINDOWS = os.name == "nt"


class BridgeError(RuntimeError):
    pass


def _wine() -> str:
    w = os.environ.get("STARUML5_WINE", "wine")
    if not shutil.which(w):
        raise BridgeError("StarUML runs on Windows only; on this OS install Wine and StarUML into a prefix "
                          "(see wine/README in the repository) or set STARUML5_WINE")
    return w


def to_windows_path(path: str) -> str:
    """Translate a host path into the path StarUML sees."""
    if IS_WINDOWS or not path:
        return os.path.abspath(path) if path else path
    p = os.path.abspath(path)
    try:
        out = subprocess.run(["winepath", "-w", p],
                             capture_output=True, text=True, timeout=60)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip().splitlines()[-1]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "Z:" + p.replace("/", "\\")


def _esc_arg(a: str) -> str:
    """ASCII-only argument: non-ASCII and backslash become \\uXXXX (decoded by the script)."""
    return "".join(c if 32 <= ord(c) < 127 and c != "\\" else "\\u%04x" % ord(c) for c in a)


def run(*args: str, timeout: int = 180) -> dict:
    """Run one bridge command, return its JSON result (raises BridgeError on failure)."""
    script = SCRIPT
    args = tuple(_esc_arg(a) for a in args)
    if IS_WINDOWS:
        cmd = ["cscript", "//nologo", "//U", script] + list(args)
    else:
        # Wine's cscript prints nothing with //U; it writes the console code page instead
        cmd = [_wine(), "cscript", "//nologo", to_windows_path(script)] + list(args)
    env = dict(os.environ)
    env.setdefault("WINEDEBUG", "-all")
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env)
    except FileNotFoundError as e:
        raise BridgeError("cannot run %s: %s" % (cmd[0], e))
    except subprocess.TimeoutExpired:
        raise BridgeError("StarUML did not answer within %ds (a modal dialog may be open)" % timeout)
    raw = p.stdout
    text = None
    encs = ("utf-16-le", "mbcs") if IS_WINDOWS else ("utf-8", "cp949", "latin-1")
    for enc in encs:
        try:
            text = raw.decode(enc)
            if "{" in text:
                break
        except (UnicodeDecodeError, LookupError):
            continue
    text = (text or "").replace("﻿", "")
    line = next((l for l in text.splitlines() if l.strip().startswith("{")), None)
    if line is None:
        raise BridgeError("bridge produced no result (exit %s): %s %s" % (
            p.returncode, text.strip()[:500], p.stderr.decode("utf-8", "replace")[:500]))
    res = json.loads(line)
    if not res.get("ok"):
        raise BridgeError(res.get("error", "unknown error"))
    return res


# convenience wrappers ---------------------------------------------------------------
def status():
    return run("status")


def open_project(path: str, force: bool = False):
    return run("open", to_windows_path(path), *(["--force"] if force else []))


def reload(force: bool = False):
    return run("reload", *(["--force"] if force else []))


def save():
    return run("save")


def list_diagrams():
    return run("list")


def show(diagram: str, package: str = ""):
    return run("show", diagram, *([package] if package else []))


def layout(diagram: str, package: str = ""):
    return run("layout", diagram, *([package] if package else []))


def export_image(diagram: str, out: str, package: str = ""):
    return run("export", diagram, to_windows_path(out), *([package] if package else []))


def import_fragment(path: str, package: str = ""):
    return run("import-fragment", to_windows_path(path), *([package] if package else []))


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(run(*sys.argv[1:]), ensure_ascii=False, indent=2))
