"""StarUML 5 activity diagram -> Mermaid ``flowchart`` (reverse conversion)."""
from __future__ import annotations

from ...core.xpd import Obj, Project


def _esc(t: str) -> str:
    t = (t or "").strip().replace("\r\n", "<br/>").replace("\n", "<br/>")
    return '"%s"' % t.replace('"', "'") if any(c in t for c in '()[]{}|<>"') else t


def export_activity(prj: Project, diagram: Obj) -> str:
    idx = prj.index()
    dv = diagram.get_child("DiagramView")
    views = dv.items_of("OwnedViews")
    lanes = sorted([v for v in views if v.type == "UMLSwimlaneView"], key=lambda v: int(v.get("Left", 0)))
    nid, decl, lane_nodes = {}, {}, {}
    n = 0
    for v in views:
        m = idx.get(v.get_ref("Model"))
        if m is None:
            continue
        t = v.type
        if t not in ("UMLActionStateView", "UMLSubactivityStateView", "UMLPseudostateView", "UMLFinalStateView"):
            continue
        n += 1
        i = "n%d" % n
        nid[v.guid] = i
        name = m.name or ""
        if t == "UMLActionStateView":
            decl[i] = "%s[%s]" % (i, _esc(name))
        elif t == "UMLSubactivityStateView":
            decl[i] = "%s[[%s]]" % (i, _esc(name))
        elif t == "UMLFinalStateView":
            decl[i] = "%s@{ shape: fr-circ }" % i
        else:
            k = m.get("PseudostateKind")
            if k == "pkInitial":
                decl[i] = "%s@{ shape: sm-circ }" % i
            elif k == "pkSynchronization":
                decl[i] = "%s@{ shape: fork }" % i
            elif k in ("pkDecision", "pkChoice", "pkJunction"):
                label = name if name and not name.startswith(("Decision", "Merge", "Junction")) else ""
                decl[i] = "%s{%s}" % (i, _esc(label)) if label else "%s{ }" % i
            else:
                decl[i] = "%s((%s))" % (i, _esc(name or "o"))
        cx = int(v.get("Left", 0)) + int(v.get("Width", 0)) // 2
        for lv in lanes:
            if int(lv.get("Left", 0)) <= cx < int(lv.get("Left", 0)) + int(lv.get("Width", 0)):
                lm = idx.get(lv.get_ref("Model"))
                lane_nodes.setdefault(lm.name if lm is not None else "Lane", []).append(i)
                break

    lines = ["flowchart TD"]
    in_lane = set()
    for lv in lanes:
        lm = idx.get(lv.get_ref("Model"))
        ln = lm.name if lm is not None else "Lane"
        ids = lane_nodes.get(ln, [])
        lines.append("    subgraph %s" % _esc(ln))
        for i in ids:
            lines.append("        " + decl[i])
            in_lane.add(i)
        lines.append("    end")
    for i, dcl in decl.items():
        if i not in in_lane:
            lines.append("    " + dcl)
    for v in views:
        if v.type != "UMLTransitionView":
            continue
        t = idx.get(v.get_ref("Model"))
        a, b = nid.get(v.get_ref("Tail")), nid.get(v.get_ref("Head"))
        if not a or not b:
            continue
        g = t.get("GuardCondition") if t is not None else None
        lines.append("    %s -->%s %s" % (a, "|%s|" % g if g else "", b))
    return "\n".join(lines) + "\n"
