"""High-level API used by the CLI, the MCP server and the StarUML add-in."""
from __future__ import annotations

import os
import shutil
from typing import Optional

from . import plugins
from .core import views as V
from .core.xpd import Obj, Project, validate

STYLES = {
    # StarUML 5 defaults (maroon lines, light-yellow fill) - what the GUI writes
    "default": V.Style(),
    # black & white, good for documents
    "mono": V.Style(line_color="clBlack", fill_color="clWhite"),
    # no explicit colours: follow the viewer's StarUML options
    "none": V.Style(line_color=None, fill_color=None),
}


def get_style(style=None, line_color=None, fill_color=None, font_face=None, font_size=None) -> V.Style:
    if isinstance(style, V.Style):
        base = style
    else:
        base = STYLES.get(style or "default")
        if base is None:
            raise ValueError("unknown style %r (known: %s)" % (style, ", ".join(STYLES)))
    return V.Style(line_color=line_color or base.line_color, fill_color=fill_color or base.fill_color,
                   font_face=font_face or base.font_face, font_size=font_size or base.font_size)


# --------------------------------------------------------------------------- lookup helpers
def owner_package(diagram: Obj) -> Optional[Obj]:
    """The model/package a diagram logically belongs to."""
    o = diagram.owner
    while o is not None and o.type not in ("UMLModel", "UMLPackage", "UMLSubsystem", "UMLProject"):
        o = o.owner
    return o


def package_path(o: Optional[Obj]) -> str:
    names = []
    while o is not None and o.type != "UMLProject":
        names.append(o.name or "")
        o = o.owner
    return "::".join(reversed(names))


def list_diagrams(prj: Project) -> list:
    out = []
    for d in prj.diagrams():
        dv = d.get_child("DiagramView")
        out.append({
            "name": d.name,
            "type": d.type,
            "package": package_path(owner_package(d)),
            "views": len(dv.items_of("OwnedViews")) if dv else 0,
            "guid": d.guid,
        })
    return out


def find_diagram(prj: Project, name: str, package: Optional[str] = None) -> Optional[Obj]:
    hits = [d for d in prj.diagrams() if d.name == name and
            (package is None or package_path(owner_package(d)) == package)]
    if len(hits) > 1:
        raise ValueError("diagram name %r is ambiguous (%d matches); pass package=" % (name, len(hits)))
    return hits[0] if hits else None


def remove_diagram(prj: Project, diagram: Obj) -> int:
    """Delete a diagram. For sequence/activity diagrams the interaction / activity
    graph that only exists for this diagram is deleted too."""
    target = diagram
    o = diagram.owner
    if diagram.type == "UMLSequenceDiagram" and o is not None and o.type == "UMLInteractionInstanceSet":
        cis = o.owner
        if len(o.items_of("OwnedDiagrams")) == 1 and cis is not None and len(cis.items_of("InteractionInstanceSets")) == 1:
            target = cis
    elif diagram.type == "UMLActivityDiagram" and o is not None and o.type == "UMLActivityGraph":
        if len(o.items_of("OwnedDiagrams")) == 1:
            target = o
    return prj.remove([target])


# --------------------------------------------------------------------------- conversion
def build(prj: Project, mermaid: str, package: str = "Design Model", name: Optional[str] = None,
          style=None, replace: bool = True, kind: Optional[str] = None) -> dict:
    """Parse Mermaid and add the resulting diagram to an in-memory project."""
    text, fm_title = plugins.strip_front_matter(mermaid)
    plugin = plugins.get(kind) if kind else plugins.detect(text)
    ir = plugin.parse(text)
    dname = name or fm_title or getattr(ir, "title", "") or plugin.title
    owner = prj.ensure_package(package) if package else prj.root
    replaced = False
    if replace:
        old = find_diagram(prj, dname, package_path(owner) if owner is not prj.root else None)
        if old is not None and owner_package(old) is owner:
            remove_diagram(prj, old)
            replaced = True
    d = plugin.build(owner, ir, dname, get_style(style))
    return {"diagram": dname, "type": d.type, "plugin": plugin.name, "package": package_path(owner),
            "replaced": replaced, "guid": d.guid}


def convert(mermaid_sources, output: Optional[str] = None, into: Optional[str] = None,
            package: str = "Design Model", names=None, style=None, replace: bool = True,
            backup: bool = True, title: str = "Untitled", kind: Optional[str] = None) -> dict:
    """Convert one or more Mermaid sources into a StarUML 5 project file.

    * ``into``  - existing .uml to add the diagrams to (default: new project)
    * ``output`` - where to write (default: ``into``; a ``.bak`` copy is kept)
    """
    if isinstance(mermaid_sources, str):
        mermaid_sources = [mermaid_sources]
    names = list(names or [])
    if into:
        prj = Project.load(into)
    else:
        prj = Project.new(title, model_name=None)
    results = []
    for i, src in enumerate(mermaid_sources):
        results.append(build(prj, src, package=package, name=names[i] if i < len(names) else None,
                             style=style, replace=replace, kind=kind))
    out = output or into
    if not out:
        raise ValueError("output path required")
    if backup and os.path.exists(out):
        shutil.copyfile(out, out + ".bak")
    prj.save(out)
    return {"output": os.path.abspath(out), "diagrams": results, "problems": validate(prj)}


def make_fragment(mermaid_sources, output: str, package_name: Optional[str] = None, names=None,
                  style=None, kind: Optional[str] = None) -> dict:
    """Write a model fragment (.mfj) - a package StarUML can import into any open project."""
    if isinstance(mermaid_sources, str):
        mermaid_sources = [mermaid_sources]
    names = list(names or [])
    prj = Project.new_fragment(package_name or "Mermaid")
    results = []
    for i, src in enumerate(mermaid_sources):
        results.append(build(prj, src, package="", name=names[i] if i < len(names) else None,
                             style=style, replace=False, kind=kind))
    if package_name is None and len(results) == 1:
        prj.root.set("Name", results[0]["diagram"])
    prj.save(output)
    return {"output": os.path.abspath(output), "package": prj.root.name, "diagrams": results,
            "problems": validate(prj)}


def to_mermaid(prj: Project, diagram_name: str, package: Optional[str] = None) -> str:
    """Reverse conversion: describe an existing StarUML diagram as Mermaid text."""
    from .export import export_diagram
    d = find_diagram(prj, diagram_name, package)
    if d is None:
        raise KeyError("diagram %r not found" % diagram_name)
    return export_diagram(prj, d)
