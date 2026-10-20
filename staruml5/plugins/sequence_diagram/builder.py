"""SequenceDiagram IR -> StarUML sequence diagram (instance level, like the
"Sequence Diagram" StarUML creates by default).

Geometry follows what StarUML 5 itself writes, measured from real files:
lifeline centre = Left + Width/2, activation boxes are 14px wide and start
at centre-7 (+7 per nesting level), self messages go 30px right and 20px
down, every stimulus is ``lsRectilinear``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ...core import views as V
from ...core.ir import Activation, Fragment, Message, SeqNote, SequenceDiagram
from ...core.xpd import Obj

ACTION_TYPE = {
    "call": "UMLCallAction",
    "send": "UMLSendAction",
    "return": "UMLReturnAction",
    "create": "UMLCreateAction",
    "destroy": "UMLDestroyAction",
}
OPERATOR = {
    "seq": "iokSeq", "alt": "iokAlt", "opt": "iokOpt", "break": "iokBreak", "par": "iokPar",
    "strict": "iokStrict", "loop": "iokLoop", "critical": "iokRegion", "region": "iokRegion",
    "neg": "iokNeg", "assert": "iokAssert", "ignore": "iokIgnore", "consider": "iokConsider",
}
OPERATOR_LABEL = {"critical": "critical", "region": "critical"}

TOP = 40
HEAD_H = 40
MSG_DY = 34
SELF_DY = 52
ACT_W = 14
LEAF_H = 29


@dataclass
class _Act:
    part: str
    left: int
    top: int
    view: Obj                      # UMLActivationView
    level: int
    last_y: int = 0
    base: bool = False


@dataclass
class _State:
    y: int
    acts: dict = field(default_factory=dict)       # part -> [ _Act ]
    stack: list = field(default_factory=list)      # call stack of _Act
    msg_no: int = 0


def split_call(text: str):
    """'login(id, pw)' -> ('login', 'id, pw'); plain text -> (text, None)."""
    t = text.strip()
    if t.endswith(")") and "(" in t:
        i = t.index("(")
        return t[:i].strip(), t[i + 1:-1].strip()
    return t, None


def _label_text(no: int, kind: str, name: str, args: Optional[str], ret: str = "") -> str:
    if kind in ("call", "create"):
        s = "%s(%s)" % (name, args or "")
    else:
        s = name if args is None else "%s(%s)" % (name, args)
    return "%d : %s" % (no, s)


def build_sequence_diagram(owner: Obj, diag: SequenceDiagram, name: str, style: V.Style = V.DEFAULT_STYLE,
                           show_numbers: bool = True):
    # ---------------------------------------------------------------- model containers
    cis = V.new_element(owner, "UMLCollaborationInstanceSet", name, coll="OwnedCollaborationInstanceSets",
                        owner_ref="RepresentedClassifier")
    # RepresentedClassifier is a plain ref (not ownership): fix the owner link
    cis.owner = owner
    iis = Obj("UMLInteractionInstanceSet")
    iis.set("Name", name)
    iis.ref("Context", cis)
    cis.add("InteractionInstanceSets", iis)
    d, dv = V.new_diagram(iis, "UMLSequenceDiagram", name)

    parts = list(diag.participants.values())
    pids = [p.id for p in parts]
    idx = {pid: i for i, pid in enumerate(pids)}

    # ---------------------------------------------------------------- horizontal layout
    widths = {p.id: max(70, V.text_width(p.name) + 24) for p in parts}
    need = {}            # (i, j) adjacent-or-not -> min centre distance
    self_need = {}       # i -> room needed right of lifeline i for self-message labels

    def visit(items):
        for it in items:
            if isinstance(it, Message):
                lw = V.text_width(_label_text(99, it.kind, *split_call(it.text))) + 30
                a, b = idx[it.source], idx[it.target]
                if a == b:
                    self_need[a] = max(self_need.get(a, 0), lw + 40)
                else:
                    k = (min(a, b), max(a, b))
                    need[k] = max(need.get(k, 0), lw)
            elif isinstance(it, Fragment):
                for o in it.operands:
                    visit(o.items)
            elif isinstance(it, SeqNote):
                for x in it.participants:
                    i = idx[x]
                    self_need[i] = max(self_need.get(i, 0), V.text_width(max(it.text.split("\n"), key=len)) + 60)

    visit(diag.items)
    centers = []
    for i, pid in enumerate(pids):
        if i == 0:
            c = 40 + widths[pid] / 2 + 40
        else:
            prev = pids[i - 1]
            c = centers[i - 1] + max(160, (widths[prev] + widths[pid]) / 2 + 40, self_need.get(i - 1, 0))
            for (a, b), w in need.items():
                if b == i:
                    c = max(c, centers[a] + w)
        centers.append(int(c))

    # ---------------------------------------------------------------- objects
    objs, oviews, lifelines = {}, {}, {}
    for i, p in enumerate(parts):
        o = Obj("UMLObject")
        o.set("Name", p.name)
        o.ref("CollaborationInstanceSet", cis)
        cis.add("ParticipatingInstances", o)
        objs[p.id] = o
        w = widths[p.id]
        left = centers[i] - w // 2
        ov = V.node_view("UMLSeqObjectView", o, left, TOP, w, 300, style)
        ov.child("NameCompartment", V.name_compartment(p.name, 4))
        ll = V.bind(o, Obj("UMLLifeLineView"))
        ov.child("LifeLine", ll)
        V.add_to_diagram(dv, ov)
        oviews[p.id] = ov
        lifelines[p.id] = ll

    def center_of(pid):
        ov = oviews[pid]
        return int(ov.get("Left")) + int(ov.get("Width")) // 2

    st = _State(y=TOP + HEAD_H + 30)

    # ---------------------------------------------------------------- activations helpers
    def top_act(pid) -> Optional[_Act]:
        lst = st.acts.get(pid) or []
        return lst[-1] if lst else None

    def close_act(a: _Act, y: int):
        h = max(LEAF_H, y - a.top, getattr(a, "closed_h", 0))
        a.closed_h = h
        a.view.set("Height", int(h))
        lst = st.acts.get(a.part, [])
        if a in lst:
            lst.remove(a)
        if a in st.stack:
            st.stack.remove(a)

    def open_act(pid, y, view: Obj, base=False) -> _Act:
        cur = top_act(pid)
        left = (cur.left + 7) if cur else center_of(pid) - 7
        level = (cur.level + 1) if cur else 0
        view.set("Left", int(left))
        view.set("Top", int(y))
        view.set("Width", ACT_W)
        view.set("Height", LEAF_H)
        a = _Act(pid, left, y, view, level, y, base)
        st.acts.setdefault(pid, []).append(a)
        return a

    def unwind_to(pid, y):
        """A message sent by ``pid``: everything called after pid's activation has returned."""
        for k in range(len(st.stack) - 1, -1, -1):
            if st.stack[k].part == pid:
                for a in st.stack[k + 1:][::-1]:
                    close_act(a, max(a.last_y + 15, a.top + LEAF_H))
                return

    def touch(pid, y):
        for a in st.acts.get(pid, []):
            a.last_y = max(a.last_y, y)

    # ---------------------------------------------------------------- items
    def place_message(m: Message):
        st.msg_no += 1
        y = st.y
        name, args = split_call(m.text)
        s = Obj("UMLStimulus")
        s.set("Name", name)
        if args:
            s.set("Arguments", args)
        s.ref("Sender", objs[m.source])
        s.ref("Receiver", objs[m.target])
        act = Obj(ACTION_TYPE[m.kind])
        act.ref("Stimulus", s)
        s.child("Action", act)
        s.ref("InteractionInstanceSet", iis)
        iis.add("ParticipatingStimuli", s)
        objs[m.source].add_ref("SendingStimuli", s)
        objs[m.target].add_ref("ReceivingStimuli", s)

        if m.kind != "return" and not (m.kind == "call" and m.source == m.target):
            unwind_to(m.source, y)
        sender_act = top_act(m.source)

        ev = V.styled(Obj("UMLSeqStimulusView"), style)
        ev.set("LineStyle", "lsRectilinear", "LineStyleKind")
        V.bind(s, ev)
        ev.ref("Head", lifelines[m.target])
        ev.ref("Tail", lifelines[m.source])
        text = _label_text(st.msg_no, m.kind, name, args) if show_numbers else (
            "%s(%s)" % (name, args or "") if m.kind in ("call", "create") else m.text)
        V.std_edge_labels(ev, s, text, dist=10, host=True)
        ev.get_child("StereotypeLabel").set("Distance", 25.0, "real")
        av = Obj("UMLActivationView")
        ev.child("Activation", av)

        if m.source == m.target:
            x0 = (sender_act.left + ACT_W - 1) if sender_act else center_of(m.source)
            base = sender_act is None
            a = open_act(m.target, y + 20, av, base=base)
            pts = [(x0, y), (x0 + 30, y), (x0 + 30, y + 20), (a.left + ACT_W - 1, y + 20)]
            if not base:
                close_act(a, y + 20 + LEAF_H)          # nested self call: leaf activation
            else:
                st.stack.append(a)
            touch(m.source, y + 20 + LEAF_H)
            st.y = y + SELF_DY
        else:
            going_right = idx[m.target] > idx[m.source]
            if sender_act:
                x0 = sender_act.left + (ACT_W - 1 if going_right else 0)
            else:
                x0 = center_of(m.source)
            if m.kind == "return":
                # return closes the sender's activation; head lands on receiver's active box
                if sender_act:
                    close_act(sender_act, y)
                    unwind_to(m.target, y)
                ra = top_act(m.target)
                if ra:
                    x1 = ra.left + (0 if going_right else ACT_W - 1)
                else:
                    x1 = center_of(m.target)
                av.set("Visible", False)
                av.set("Left", int(x1)).set("Top", int(y)).set("Width", ACT_W).set("Height", 25)
            elif m.kind in ("send", "destroy"):
                x1 = center_of(m.target) - (7 if going_right else -6)
                av.set("Visible", False)
                av.set("Left", int(center_of(m.target) - 7)).set("Top", int(y)).set("Width", ACT_W).set("Height", 25)
                if m.kind == "destroy":
                    for a in list(st.acts.get(m.target, [])):
                        close_act(a, y)
                    ov = oviews[m.target]
                    ov.set("Height", int(y - int(ov.get("Top")) + 12))
                    oviews[m.target].destroyed = True
            else:  # call / create
                a = open_act(m.target, y, av)
                st.stack.append(a)
                x1 = a.left + (0 if going_right else ACT_W - 1)
                if m.kind == "create":
                    ov = oviews[m.target]
                    ov.set("Top", int(y - HEAD_H // 2))
            pts = [(x0, y), (x1, y)]
            touch(m.source, y)
            touch(m.target, y)
            st.y = y + MSG_DY
        ev.set("Points", V.points_str(pts), "Points")
        V.add_to_diagram(dv, ev)
        return ev

    frag_views = []   # (fragment view, [operand views], nesting depth, involved participant idxs)

    def place_items(items, depth, involved):
        for it in items:
            if isinstance(it, Message):
                place_message(it)
                involved.update({idx[it.source], idx[it.target]})
                if it.source == it.target:
                    involved.add(("self", idx[it.source], V.text_width(_label_text(99, it.kind, *split_call(it.text)))))
            elif isinstance(it, Activation):
                if not it.on:
                    a = top_act(it.participant)
                    if a:
                        close_act(a, st.y - 10)
            elif isinstance(it, SeqNote):
                place_note(it)
                involved.update(idx[p] for p in it.participants)
            elif isinstance(it, Fragment):
                place_fragment(it, depth, involved)

    def place_note(n: SeqNote):
        c = center_of(n.participants[0])
        if n.position == "left":
            x = c - 30 - (V.text_width(max(n.text.split("\n"), key=len)) + 20)
        elif n.position == "over":
            x = c - 30
        else:
            x = c + 30
        nv = V.note_view(dv, n.text, max(0, x), st.y - 8, style)
        st.y += int(nv.get("Height")) + 12

    def place_fragment(fr: Fragment, depth, outer_involved):
        cf = Obj("UMLCombinedFragment")
        first_guard = fr.operands[0].guard if fr.operands else ""
        single = len(fr.operands) == 1
        if single and first_guard:
            cf.set("Name", first_guard)
        cf.set("InteractionOperator", OPERATOR.get(fr.operator, "iokSeq"), "UMLInteractionOperatorKind")
        cf.ref("EnclosingInteractionInstanceSet", iis)
        iis.add("Fragments", cf)

        top = st.y - 14
        st.y = top + 20 + 22
        involved = set()
        opviews = []
        # every operand starts from the activation state at the fragment start
        snap_stack = list(st.stack)
        snap_acts = {p: list(l) for p, l in st.acts.items()}
        for k, opnd in enumerate(fr.operands):
            if k > 0:
                st.stack[:] = snap_stack
                st.acts.clear()
                st.acts.update({p: list(l) for p, l in snap_acts.items()})
            op = Obj("UMLInteractionOperand")
            op.set("Name", opnd.guard or "InteractionOperand%d" % (k + 1))
            if opnd.guard and not single:
                op.set("Guard", opnd.guard)
            op.ref("CombinedFragment", cf)
            cf.add("Operands", op)
            otop = top + 20 if k == 0 else st.y - 12
            if k > 0:
                st.y += 16
            place_items(opnd.items, depth + 1, involved)
            ov = V.styled(Obj("UMLInteractionOperandView"), style)
            V.bind(op, ov)
            gl = V.label("[%s]" % opnd.guard if opnd.guard and not single else None,
                         visible=bool(opnd.guard and not single))
            ov.child("GuardLabel", gl)
            opviews.append((ov, otop))
            st.y += 4
        bottom = st.y
        st.y = bottom + 24
        outer_involved.update(involved)

        fv = V.styled(Obj("UMLCombinedFragmentView"), style)
        V.bind(cf, fv)
        V.add_to_diagram(dv, fv)
        fv.child("NameLabel", V.label(cf.get("Name") or None))
        fv.child("FrameTypeLabel", V.label(OPERATOR_LABEL.get(fr.operator, fr.operator), font_style=1))
        fv.set("Top", int(top)).set("Height", int(bottom - top))
        for i, (ov, otop) in enumerate(opviews):
            obot = opviews[i + 1][1] if i + 1 < len(opviews) else bottom
            ov.set("Top", int(otop)).set("Height", int(obot - otop))
            ov.ref("ContainerView", fv)
            fv.add("ContainedViews", ov)
        frag_views.append((fv, [o for o, _ in opviews], depth, involved,
                           V.text_width("%s %s" % (fr.operator, cf.get("Name") or "")) + 50))

    place_items(diag.items, 0, set())

    # close everything still open
    end_y = st.y + 10
    for pid in list(st.acts):
        for a in list(st.acts[pid])[::-1]:
            close_act(a, max(a.last_y + 15, a.top + LEAF_H))

    # ---------------------------------------------------------------- fragment widths (inner first)
    frag_views.sort(key=lambda t: -t[2])
    extents = []
    for fv, ops, depth, involved, min_w in frag_views:
        idxs = [x for x in involved if isinstance(x, int)]
        selfs = [x for x in involved if isinstance(x, tuple)]
        if not idxs:
            idxs = [0]
        margin = 90 - 15 * min(depth, 4)
        lft = min(centers[i] for i in idxs) - margin
        rgt = max(centers[i] for i in idxs) + margin
        for _, i, lw in selfs:
            rgt = max(rgt, centers[i] + 40 + lw + 10)
        # enclose inner fragments already sized
        top, h = int(fv.get("Top")), int(fv.get("Height"))
        for (l2, r2, t2, b2, d2) in extents:
            if d2 > depth and t2 >= top and b2 <= top + h:
                lft = min(lft, l2 - 12)
                rgt = max(rgt, r2 + 12)
        rgt = max(rgt, lft + min_w)
        fv.set("Left", int(lft), "integer")
        fv.set("Width", int(rgt - lft), "integer")
        for ov in ops:
            ov.set("Left", int(lft)).set("Width", int(rgt - lft))
        extents.append((lft, rgt, top, top + h, depth))
        # StarUML attribute order: LineColor FillColor Left Top Width Height
        _reorder(fv)
        for ov in ops:
            _reorder(ov)
    # fragments are drawn first (behind lifelines), like StarUML does
    coll = dv.coll("OwnedViews")
    fvs = [t[0] for t in frag_views]
    coll.items = [v for v in coll.items if v in fvs] + [v for v in coll.items if v not in fvs]

    # lifeline length
    for pid, ov in oviews.items():
        if getattr(ov, "destroyed", False):
            continue
        ov.set("Height", int(end_y + 20 - int(ov.get("Top"))))
    return d


_ORDER = {"LineColor": 0, "FillColor": 1, "Left": 2, "Top": 3, "Width": 4, "Height": 5}


def _reorder(v: Obj):
    from ...core.xpd import Attr
    head = [it for it in v.items if isinstance(it, Attr) and it.name in _ORDER]
    rest = [it for it in v.items if it not in head]
    v.items = sorted(head, key=lambda a: _ORDER[a.name]) + rest
