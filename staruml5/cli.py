"""Command line interface:  ``python -m staruml5 <command> ...``"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import api, plugins
from .core.xpd import Project, validate


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


def _print(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_convert(a):
    srcs = [_read(p) for p in a.inputs]
    names = a.name or [None if p == "-" else None for p in a.inputs]
    if not a.name:
        # default diagram name: front-matter title, else the file name
        names = []
        for p, src in zip(a.inputs, srcs):
            _, title = plugins.strip_front_matter(src)
            names.append(title or (None if p == "-" else os.path.splitext(os.path.basename(p))[0]))
    res = api.convert(srcs, output=a.output, into=a.into, package=a.package, names=names, style=a.style,
                      replace=not a.no_replace, backup=not a.no_backup, title=a.title, kind=a.type)
    _print(res)
    return 1 if res["problems"] else 0


def cmd_fragment(a):
    srcs = [_read(p) for p in a.inputs]
    names = a.name or [os.path.splitext(os.path.basename(p))[0] if p != "-" else None for p in a.inputs]
    _print(api.make_fragment(srcs, a.output, package_name=a.package, names=names, style=a.style, kind=a.type))
    return 0


def cmd_list(a):
    _print(api.list_diagrams(Project.load(a.file)))
    return 0


def cmd_export(a):
    text = api.to_mermaid(Project.load(a.file), a.diagram, a.package)
    if a.output:
        with open(a.output, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    return 0


def cmd_remove(a):
    prj = Project.load(a.file)
    d = api.find_diagram(prj, a.diagram, a.package)
    if d is None:
        print("diagram not found: %s" % a.diagram, file=sys.stderr)
        return 1
    n = api.remove_diagram(prj, d)
    prj.save(a.output or a.file)
    _print({"removed": a.diagram, "objects": n})
    return 0


def cmd_validate(a):
    problems = validate(Project.load(a.file))
    _print({"file": a.file, "problems": problems})
    return 1 if problems else 0


def cmd_com(a):
    from . import bridge
    try:
        if a.action == "open":
            r = bridge.open_project(a.args[0], force=a.force)
        elif a.action == "export":
            r = bridge.export_image(a.args[0], a.args[1], *(a.args[2:3]))
        elif a.action == "import-fragment":
            r = bridge.import_fragment(a.args[0], *(a.args[1:2]))
        elif a.action in ("reload",):
            r = bridge.reload(force=a.force)
        else:
            r = bridge.run(a.action, *a.args, *(["--force"] if a.force else []))
    except bridge.BridgeError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    _print(r)
    return 0


def cmd_mcp(a):
    if a.http:
        from .mcp_http import serve_http
        serve_http(a.http, root=a.root, token=a.token)
        return 0
    from .mcp_server import serve
    serve()
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="staruml5", description="Mermaid <-> StarUML 5.0 (.uml) tools")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("convert", help="Mermaid file(s) -> .uml project (new or existing)")
    p.add_argument("inputs", nargs="+", help=".mmd files ('-' = stdin)")
    p.add_argument("-o", "--output", help="output .uml (default: --into file)")
    p.add_argument("--into", help="existing .uml project to add the diagrams to")
    p.add_argument("--package", default="Design Model", help="target model/package path, e.g. 'Design Model::Orders'")
    p.add_argument("--name", action="append", help="diagram name (repeat per input)")
    p.add_argument("--type", help="force diagram type: class | sequence | activity | flowchart")
    p.add_argument("--style", default="default", choices=sorted(api.STYLES))
    p.add_argument("--title", default="Untitled", help="project title for new projects")
    p.add_argument("--no-replace", action="store_true", help="keep an existing diagram with the same name")
    p.add_argument("--no-backup", action="store_true", help="do not write <output>.bak")
    p.set_defaults(func=cmd_convert)

    p = sub.add_parser("fragment", help="Mermaid file(s) -> model fragment (.mfj) for File > Import")
    p.add_argument("inputs", nargs="+")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--package", help="name of the package the fragment creates")
    p.add_argument("--name", action="append")
    p.add_argument("--type")
    p.add_argument("--style", default="default", choices=sorted(api.STYLES))
    p.set_defaults(func=cmd_fragment)

    p = sub.add_parser("list", help="list diagrams in a .uml file")
    p.add_argument("file")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("export", help="StarUML diagram -> Mermaid text")
    p.add_argument("file")
    p.add_argument("diagram")
    p.add_argument("--package")
    p.add_argument("-o", "--output")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("remove", help="delete a diagram (and its interaction/activity graph)")
    p.add_argument("file")
    p.add_argument("diagram")
    p.add_argument("--package")
    p.add_argument("-o", "--output")
    p.set_defaults(func=cmd_remove)

    p = sub.add_parser("validate", help="check references/GUIDs of a .uml file")
    p.add_argument("file")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("com", help="drive a running StarUML (status|open|reload|save|list|show|layout|export|import-fragment)")
    p.add_argument("action")
    p.add_argument("args", nargs="*")
    p.add_argument("--force", action="store_true", help="discard unsaved changes in StarUML")
    p.set_defaults(func=cmd_com)

    p = sub.add_parser("mcp", help="run the MCP server on stdio, or on HTTP with --http (for AI agents)")
    p.add_argument("--http", metavar="[HOST:]PORT", help="serve MCP over HTTP instead of stdio, e.g. 0.0.0.0:8765")
    p.add_argument("--root", help="HTTP: workspace directory that tool paths and /files are confined to (default: cwd)")
    p.add_argument("--token", help="HTTP: bearer token clients must send (default: $STARUML5_TOKEN; "
                                   "required unless listening on localhost)")
    p.set_defaults(func=cmd_mcp)

    a = ap.parse_args(argv)
    try:
        return a.func(a)
    except (ValueError, KeyError, OSError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
