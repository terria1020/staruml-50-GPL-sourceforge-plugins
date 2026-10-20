"""StarUML 5 class diagram -> Mermaid ``classDiagram`` (reverse conversion)."""
from __future__ import annotations

import re

from ...core.xpd import Obj, Project

VIS = {"vkPrivate": "-", "vkProtected": "#", "vkPackage": "~"}
NODE_VIEWS = ("UMLClassView", "UMLInterfaceView", "UMLEnumerationView", "UMLSignalView", "UMLExceptionView")


def _cid(name: str) -> str:
    if re.fullmatch(r"[A-Za-z_][\w]*", name or ""):
        return name
    return "`%s`" % name


def export_class(prj: Project, diagram: Obj) -> str:
    idx = prj.index()
    dv = diagram.get_child("DiagramView")
    views = dv.items_of("OwnedViews")
    model_of_view = {}
    lines = ["classDiagram"]
    for v in views:
        if v.type not in NODE_VIEWS:
            continue
        m = idx.get(v.get_ref("Model"))
        if m is None:
            continue
        model_of_view[v.guid] = m
        cid = _cid(m.name or "Unnamed")
        body = []
        if m.type == "UMLInterface":
            body.append("<<interface>>")
        elif m.type == "UMLEnumeration":
            body.append("<<enumeration>>")
        elif m.get("StereotypeName"):
            body.append("<<%s>>" % m.get("StereotypeName"))
        if m.get("IsAbstract") == "True" and m.type == "UMLClass":
            body.append("<<abstract>>")
        for a in m.items_of("Attributes"):
            if not isinstance(a, Obj):
                continue
            s = VIS.get(a.get("Visibility"), "+") + (a.name or "")
            if a.get("TypeExpression"):
                s += " : " + a.get("TypeExpression")
            if a.get("InitialValue"):
                s += " = " + a.get("InitialValue")
            if a.get("OwnerScope") == "skClassifier":
                s += "$"
            body.append(s)
        for lit in m.items_of("Literals"):
            if isinstance(lit, Obj):
                body.append(lit.name or "")
        for o in m.items_of("Operations"):
            if not isinstance(o, Obj):
                continue
            ps, ret = [], ""
            for p in o.items_of("Parameters"):
                if not isinstance(p, Obj):
                    continue
                if p.get("DirectionKind") == "pdkReturn":
                    ret = p.get("TypeExpression") or ""
                else:
                    ps.append("%s: %s" % (p.name, p.get("TypeExpression")) if p.get("TypeExpression") else (p.name or ""))
            s = "%s%s(%s)" % (VIS.get(o.get("Visibility"), "+"), o.name, ", ".join(ps))
            if o.get("IsAbstract") == "True":
                s += "*"
            elif o.get("OwnerScope") == "skClassifier":
                s += "$"
            if ret:
                s += " " + ret
            body.append(s)
        if body:
            lines.append("    class %s {" % cid)
            lines += ["        " + b for b in body]
            lines.append("    }")
        else:
            lines.append("    class %s" % cid)

    def name_of(view_guid):
        m = model_of_view.get(view_guid)
        return _cid(m.name) if m is not None else None

    for v in views:
        t = v.type
        m = idx.get(v.get_ref("Model"))
        a, b = name_of(v.get_ref("Tail")), name_of(v.get_ref("Head"))
        if m is None or a is None or b is None:
            continue
        label = (" : " + m.name) if m.name else ""
        if t == "UMLGeneralizationView":
            lines.append("    %s <|-- %s%s" % (b, a, label))
        elif t == "UMLRealizationView":
            lines.append("    %s <|.. %s%s" % (b, a, label))
        elif t == "UMLDependencyView":
            lines.append("    %s ..> %s%s" % (a, b, label))
        elif t == "UMLAssociationView":
            ends = [e for e in m.items_of("Connections") if isinstance(e, Obj)]
            if len(ends) != 2:
                continue
            e0, e1 = ends
            # make sure e0 is the tail end
            tail_model = model_of_view.get(v.get_ref("Tail"))
            if tail_model is not None and e0.get_ref("Participant") != tail_model.guid:
                e0, e1 = e1, e0
            agg = e0.get("Aggregation")
            nav0 = e0.get("IsNavigable") != "False"
            nav1 = e1.get("IsNavigable") != "False"
            if agg == "akComposite":
                arrow = "*--"
            elif agg == "akAggregate":
                arrow = "o--"
            elif nav1 and not nav0:
                arrow = "-->"
            elif nav0 and not nav1:
                arrow = "<--"
            else:
                arrow = "--"
            m0 = ' "%s"' % e0.get("Multiplicity") if e0.get("Multiplicity") else ""
            m1 = '"%s" ' % e1.get("Multiplicity") if e1.get("Multiplicity") else ""
            lines.append("    %s%s %s %s%s%s" % (a, m0, arrow, m1, b, label))
        elif t == "UMLNoteLinkView":
            pass
    for v in views:
        if v.type == "UMLNoteView":
            txt = (v.get("Text") or "").strip().replace("\r\n", "\\n").replace("\n", "\\n").replace('"', "'")
            target = None
            for lv in views:
                if lv.type == "UMLNoteLinkView" and lv.get_ref("Tail") == v.guid:
                    target = name_of(lv.get_ref("Head"))
            lines.append('    note for %s "%s"' % (target, txt) if target else '    note "%s"' % txt)
    if len(lines) == 1:
        # Mermaid rejects a bare `classDiagram`; a direction statement keeps an empty diagram valid
        lines.append("    direction TB")
    return "\n".join(lines) + "\n"
