"""StarUML 5 sequence diagram -> Mermaid ``sequenceDiagram`` (reverse conversion)."""
from __future__ import annotations

import re

from ...core.xpd import Obj, Project

ARROW = {"UMLCallAction": "->>", "UMLReturnAction": "-->>", "UMLSendAction": "-)",
         "UMLCreateAction": "->>", "UMLDestroyAction": "-x"}
OPERATOR = {"iokSeq": "seq", "iokAlt": "alt", "iokOpt": "opt", "iokBreak": "break", "iokPar": "par",
            "iokStrict": "strict", "iokLoop": "loop", "iokRegion": "critical", "iokNeg": "neg",
            "iokAssert": "assert", "iokIgnore": "ignore", "iokConsider": "consider"}
NEXT_KW = {"alt": "else", "par": "and", "critical": "option"}
# Block keywords Mermaid accepts. Other UML operators (neg, strict, ...) are written as
# `opt` preceded by a `%% staruml:operator <op>` comment, which our parser reads back.
MERMAID_BLOCKS = {"alt", "opt", "loop", "par", "critical", "break"}
OPERATOR_DIRECTIVE = "%% staruml:operator "


def _first_y(points: str) -> int:
    try:
        return int(points.split(";")[0].split(",")[1])
    except (IndexError, ValueError):
        return 0


def _safe_id(name: str, used: set) -> str:
    base = re.sub(r"[^\w]", "_", name, flags=re.UNICODE).strip("_") or "P"
    if base[0].isdigit():
        base = "P_" + base
    pid, k = base, 2
    while pid in used:
        pid = "%s%d" % (base, k)
        k += 1
    used.add(pid)
    return pid


def export_sequence(prj: Project, diagram: Obj) -> str:
    idx = prj.index()
    dv = diagram.get_child("DiagramView")
    views = dv.items_of("OwnedViews")

    objviews = sorted([v for v in views if v.type in ("UMLSeqObjectView", "UMLSeqClassifierRoleView")],
                      key=lambda v: int(v.get("Left", 0)))
    lifeline_owner = {}
    pid_of, used = {}, set()
    lines = ["sequenceDiagram"]
    for v in objviews:
        m = idx.get(v.get_ref("Model"))
        name = (m.name if m is not None else None) or "Object"
        pid = _safe_id(name, used)
        pid_of[v.guid] = pid
        ll = v.get_child("LifeLine")
        if ll is not None:
            lifeline_owner[ll.guid] = v.guid
        lifeline_owner[v.guid] = v.guid
        lines.append("    participant %s as %s" % (pid, name) if pid != name else "    participant %s" % pid)

    events = []   # (y, order, kind, payload)
    for v in views:
        if v.type in ("UMLSeqStimulusView", "UMLSeqMessageView"):
            s = idx.get(v.get_ref("Model"))
            if s is None:
                continue
            tail = pid_of.get(lifeline_owner.get(v.get_ref("Tail")))
            head = pid_of.get(lifeline_owner.get(v.get_ref("Head")))
            if not tail or not head:
                continue
            act = s.get_child("Action")
            arrow = ARROW.get(act.type if act is not None else "UMLCallAction", "->>")
            text = s.name or ""
            if s.get("Arguments"):
                text += "(%s)" % s.get("Arguments")
            events.append((_first_y(v.get("Points", "0,0")), 1, "msg", "%s%s%s: %s" % (tail, arrow, head, text)))
        elif v.type == "UMLNoteView":
            y = int(v.get("Top", 0))
            x = int(v.get("Left", 0))
            near = min(objviews, key=lambda o: abs(int(o.get("Left", 0)) + int(o.get("Width", 0)) // 2 - x),
                       default=None)
            if near is not None:
                txt = (v.get("Text") or "").strip().replace("\r\n", "<br/>").replace("\n", "<br/>")
                events.append((y, 1, "note", "Note right of %s: %s" % (pid_of[near.guid], txt)))

    frags = []
    for v in views:
        if v.type != "UMLCombinedFragmentView":
            continue
        cf = idx.get(v.get_ref("Model"))
        op = OPERATOR.get(cf.get("InteractionOperator", "iokSeq") if cf is not None else "iokSeq", "opt")
        top, h = int(v.get("Top", 0)), int(v.get("Height", 0))
        operands = []
        for ov in v.items_of("ContainedViews"):
            if not isinstance(ov, Obj):
                continue
            om = idx.get(ov.get_ref("Model"))
            operands.append((int(ov.get("Top", top)), (om.get("Guard") if om is not None else "") or ""))
        operands.sort()
        if not operands:
            operands = [(top, "")]
        name = (cf.name or "") if cf is not None else ""
        frags.append({"top": top, "bottom": top + h, "op": op, "operands": operands, "name": name})

    def emit(lo, hi, indent, out, depth=0):
        inner = sorted([f for f in frags if lo <= f["top"] and f["bottom"] <= hi and f.get("_lvl") is None],
                       key=lambda f: f["top"])
        mine = []
        for f in inner:
            if not any(g is not f and g["top"] <= f["top"] and f["bottom"] <= g["bottom"] for g in inner):
                mine.append(f)
        items = [(y, o, k, p) for (y, o, k, p) in events if lo <= y < hi and
                 not any(f["top"] <= y < f["bottom"] for f in mine)]
        items += [(f["top"], 0, "frag", f) for f in mine]
        for y, _, k, p in sorted(items, key=lambda t: (t[0], t[1])):
            if k != "frag":
                out.append(" " * indent + p)
                continue
            f = p
            f["_lvl"] = depth
            op = f["op"]
            pad = " " * indent
            if op not in MERMAID_BLOCKS:
                out.append(pad + OPERATOR_DIRECTIVE + op)
                op = "opt"
            ops = f["operands"]
            nxt = NEXT_KW.get(op)
            for i, (otop, guard) in enumerate(ops):
                obot = ops[i + 1][0] if i + 1 < len(ops) else f["bottom"]
                # the fragment's Name labels the whole fragment, so it goes on the first block
                # only; later operands carry just their own guard (never a borrowed condition)
                label = guard or (f["name"] if i == 0 else "")
                if i == 0:
                    kw = op
                elif nxt:
                    kw = nxt
                else:
                    # Mermaid has no `else` for opt/loop/break: continue as another block
                    out.append(pad + "end")
                    if f["op"] != op:
                        out.append(pad + OPERATOR_DIRECTIVE + f["op"])
                    kw = op
                out.append(pad + ("%s %s" % (kw, label)).rstrip())
                emit(otop if i else f["top"], obot, indent + 4, out, depth + 1)
            out.append(pad + "end")

    body = []
    emit(-10 ** 9, 10 ** 9, 4, body)
    return "\n".join(lines + body) + "\n"
