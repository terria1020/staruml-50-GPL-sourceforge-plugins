"""Minimal MCP (Model Context Protocol) server over stdio - standard library only.

Register with an MCP client, e.g. Claude Code:

    claude mcp add staruml5 -- python -m staruml5 mcp

Tools work on .uml files directly (no StarUML needed). The ``staruml_com_*``
tools additionally talk to a running StarUML 5 through COM (Windows, or Wine).
"""
from __future__ import annotations

import json
import os
import sys
import traceback

from . import __version__, api
from .core.xpd import Project, validate

PROTOCOL = "2024-11-05"

SYNTAX_HELP = {
    "class": """classDiagram
    direction TB
    class Animal {
        <<abstract>>
        +String name
        -int age
        +makeSound()* void
        +getAge() int
        +create(name: String)$ Animal
    }
    class IPet { <<interface>> +play() void }
    class Color { <<enumeration>> RED; GREEN }
    namespace domain { class Owner }
    Animal <|-- Dog            %% generalization (Dog extends Animal)
    Dog ..|> IPet              %% realization
    Owner "1" --> "0..*" IPet : owns   %% directed association + multiplicities
    Dog *-- Collar             %% composition (diamond at Dog)
    Owner o-- Address          %% aggregation
    Dog ..> Color : uses       %% dependency
    note for Dog "text\\nsecond line"
Class names with spaces/Korean: use backticks: class `주문 서비스`""",
    "sequence": """sequenceDiagram
    participant A as 표시 이름
    actor U
    U->>A: call(args)        %% synchronous call (activation box)
    A-->>U: result           %% return (dashed)
    A-)B: event              %% asynchronous send
    A-xB: close              %% destroy
    A->>A: self call         %% self message (nested activation)
    alt 조건1
        ...
    else 조건2
        ...
    end
    opt 조건 ... end   loop 매 30초 ... end   par A ... and B ... end
    critical ... option ... end   break ... end
    Note right of A: text
Message numbers ('1 : ') and '()' after call names are added by StarUML.""",
    "activity": """flowchart TD                 %% TD/TB/LR; flowcharts become UML activity diagrams
    start((시작)) --> A[action]   %% ((x)) without incoming edge = initial node
    A --> B{decision?}            %% {text} = decision (text shown next to the diamond)
    B -->|yes| C[[sub activity]]  %% [[x]] = subactivity
    B -->|no| D
    D --> M{ }                    %% MERGE node: decision with an EMPTY label { } (or @{ shape: f-circ })
    C --> M                       %%   do not use sm-circ/((x)) for merges: they become initial/final nodes
    M --> F@{ shape: fork }       %% fork / join bars
    F --> G & H
    G --> J@{ shape: join }
    H --> J
    J --> stop(((종료)))          %% (((x))), @{ shape: fr-circ } or ((x)) without outgoing edge = final node
                                  %% @{ shape: sm-circ } = initial node (never a merge)
    subgraph 사용자 ... end        %% subgraph = swimlane (vertical partitions)
    [*] --> A                     %% [*] also works as initial/final""",
}

TOOLS = [
    {
        "name": "mermaid_to_staruml",
        "description": "Convert Mermaid (classDiagram, sequenceDiagram, flowchart/graph) into a StarUML 5.0 .uml "
                       "project file. Adds to an existing project when into_path is given (a .bak copy is kept), "
                       "otherwise creates a new project. A diagram with the same name in the same package is "
                       "replaced unless replace=false. Use mermaid_syntax_help first if unsure about syntax.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mermaid": {"type": "string", "description": "Mermaid source"},
                "output_path": {"type": "string", "description": "Where to write the .uml (default: into_path)"},
                "into_path": {"type": "string", "description": "Existing .uml project to add the diagram to"},
                "package": {"type": "string", "description": "Model/package path, e.g. 'Design Model::Orders'",
                            "default": "Design Model"},
                "diagram_name": {"type": "string"},
                "diagram_type": {"type": "string", "enum": ["class", "sequence", "activity", "flowchart"],
                                 "description": "Override auto-detection from the Mermaid header"},
                "style": {"type": "string", "enum": sorted(api.STYLES), "default": "default"},
                "replace": {"type": "boolean", "default": True},
            },
            "required": ["mermaid"],
        },
    },
    {
        "name": "staruml_list_diagrams",
        "description": "List all diagrams (name, type, package) in a StarUML 5 .uml file.",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "staruml_to_mermaid",
        "description": "Read an existing StarUML 5 diagram and return it as Mermaid text (sequence, class, "
                       "activity). Edit the text and write it back with mermaid_to_staruml (same name => replace).",
        "inputSchema": {"type": "object", "properties": {
            "path": {"type": "string"}, "diagram_name": {"type": "string"},
            "package": {"type": "string"}}, "required": ["path", "diagram_name"]},
    },
    {
        "name": "staruml_remove_diagram",
        "description": "Delete a diagram from a .uml file (sequence/activity: also its interaction/activity graph).",
        "inputSchema": {"type": "object", "properties": {
            "path": {"type": "string"}, "diagram_name": {"type": "string"},
            "package": {"type": "string"}}, "required": ["path", "diagram_name"]},
    },
    {
        "name": "staruml_validate",
        "description": "Check a .uml file for dangling references and duplicate GUIDs.",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "mermaid_syntax_help",
        "description": "Supported Mermaid syntax (and how it maps to StarUML) for a diagram type.",
        "inputSchema": {"type": "object", "properties": {
            "diagram_type": {"type": "string", "enum": ["class", "sequence", "activity"]}},
            "required": ["diagram_type"]},
    },
    {
        "name": "staruml_com",
        "description": "Control a running StarUML 5 via COM (Windows, or Wine on Linux/macOS). Actions: "
                       "status, open <file> (args[0]), reload, save, list, show <diagram>, "
                       "layout <diagram> (StarUML auto-layout + save), export <diagram> <image.jpg|bmp|emf>, "
                       "import-fragment <file.mfj> [package]. Use 'open'/'reload' after writing a file so the "
                       "user sees the change. force=true discards unsaved changes in StarUML.",
        "inputSchema": {"type": "object", "properties": {
            "action": {"type": "string"},
            "args": {"type": "array", "items": {"type": "string"}},
            "force": {"type": "boolean", "default": False}}, "required": ["action"]},
    },
]


# Set by the HTTP server (mcp_http): tool paths are then relative to ROOT and may not leave it.
ROOT = None
INSTRUCTIONS = None


def resolve(path):
    """Map a tool path into ROOT (identity when no ROOT is set)."""
    if ROOT is None or not path:
        return path
    full = os.path.realpath(os.path.join(ROOT, path))
    try:
        inside = os.path.normcase(os.path.commonpath([full, ROOT])) == os.path.normcase(ROOT)
    except ValueError:   # different drives on Windows
        inside = False
    if not inside:
        raise ValueError("path is outside the server root %s: %s" % (ROOT, path))
    return full


def _call(name: str, a: dict):
    if name == "mermaid_to_staruml":
        out = resolve(a.get("output_path") or a.get("into_path"))
        if not out:
            raise ValueError("output_path or into_path is required")
        into = resolve(a.get("into_path"))
        if into and not os.path.exists(into):
            raise ValueError("into_path does not exist: %s" % into)
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        return api.convert(a["mermaid"], output=out, into=into, package=a.get("package", "Design Model"),
                           names=[a["diagram_name"]] if a.get("diagram_name") else None,
                           style=a.get("style"), replace=a.get("replace", True), kind=a.get("diagram_type"))
    if name == "staruml_list_diagrams":
        return api.list_diagrams(Project.load(resolve(a["path"])))
    if name == "staruml_to_mermaid":
        return api.to_mermaid(Project.load(resolve(a["path"])), a["diagram_name"], a.get("package"))
    if name == "staruml_remove_diagram":
        path = resolve(a["path"])
        prj = Project.load(path)
        d = api.find_diagram(prj, a["diagram_name"], a.get("package"))
        if d is None:
            raise ValueError("diagram not found: %s" % a["diagram_name"])
        n = api.remove_diagram(prj, d)
        prj.save(path)
        return {"removed": a["diagram_name"], "objects": n}
    if name == "staruml_validate":
        return {"problems": validate(Project.load(resolve(a["path"])))}
    if name == "mermaid_syntax_help":
        return SYNTAX_HELP[{"flowchart": "activity"}.get(a["diagram_type"], a["diagram_type"])]
    if name == "staruml_com":
        from . import bridge
        args = list(a.get("args") or [])
        act = a["action"]
        if act == "open":
            return bridge.open_project(resolve(args[0]), force=a.get("force", False))
        if act == "export":
            return bridge.export_image(args[0], resolve(args[1]), *args[2:3])
        if act == "import-fragment":
            return bridge.import_fragment(resolve(args[0]), *args[1:2])
        return bridge.run(act, *args, *(["--force"] if a.get("force") else []))
    raise ValueError("unknown tool %s" % name)


def _handle(msg: dict):
    mid = msg.get("id")
    method = msg.get("method")
    if method == "initialize":
        res = {"protocolVersion": msg.get("params", {}).get("protocolVersion", PROTOCOL),
               "capabilities": {"tools": {}},
               "serverInfo": {"name": "staruml5", "version": __version__}}
        if INSTRUCTIONS:
            res["instructions"] = INSTRUCTIONS
        return res
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        p = msg.get("params", {})
        try:
            res = _call(p.get("name"), p.get("arguments") or {})
            text = res if isinstance(res, str) else json.dumps(res, ensure_ascii=False, indent=2)
            return {"content": [{"type": "text", "text": text}], "isError": False}
        except Exception as e:  # report tool errors to the model, not as protocol errors
            return {"content": [{"type": "text", "text": "%s: %s" % (type(e).__name__, e)}], "isError": True}
    if method == "ping":
        return {}
    if mid is None:
        return None   # notification
    raise KeyError(method)


def dispatch(msg: dict):
    """Handle one JSON-RPC message; returns the response object, or None for notifications."""
    mid = msg.get("id")
    try:
        result = _handle(msg)
        if mid is None:
            return None
        return {"jsonrpc": "2.0", "id": mid, "result": result}
    except KeyError as e:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "method not found: %s" % e}}
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)}}


def serve(stdin=None, stdout=None):
    for stream in (sys.stdin, sys.stdout):
        try:
            stream.reconfigure(encoding="utf-8")   # Windows consoles default to the ANSI code page
        except (AttributeError, ValueError):
            pass
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        out = dispatch(msg)
        if out is None:
            continue
        stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        stdout.flush()


if __name__ == "__main__":
    serve()
