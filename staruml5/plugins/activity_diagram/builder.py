"""ActivityDiagram IR -> StarUML activity diagram (ActivityGraph + views)."""
from __future__ import annotations

from ...core import views as V
from ...core.ir import ActivityDiagram, FlowNode
from ...core.layout import layered
from ...core.xpd import Obj

PSEUDO = {"initial": "pkInitial", "decision": "pkDecision", "merge": "pkDecision",
          "fork": "pkSynchronization", "join": "pkSynchronization", "junction": "pkJunction"}


def node_size(n: FlowNode, horizontal: bool):
    k = n.kind
    if k == "initial":
        return 20, 20
    if k in ("final", "flowfinal"):
        return 26, 26
    if k in ("decision", "merge"):
        return 50, 30
    if k in ("fork", "join"):
        return (6, 70) if horizontal else (70, 6)
    lines = n.name.split("\n")
    w = max(V.text_width(l) for l in lines) + 30
    h = V.LINE_H * len(lines) + 22
    if k == "subactivity":
        w += 20
        h += 8
    return max(90, w), max(40, h)


def _row_extent(v: Obj, all_views):
    """Top/bottom of the band of views vertically overlapping ``v``."""
    x, y, w, h = V.rect(v)
    top, bot = y, y + h
    for o in all_views:
        ox, oy, ow, oh = V.rect(o)
        if oy < y + h and oy + oh > y:
            top, bot = min(top, oy), max(bot, oy + oh)
    return top, bot


def _orth_points(sv: Obj, tv: Obj, direction: str, back: bool, right_x: int, all_views=()):
    sx, sy, sw, sh = V.rect(sv)
    tx, ty, tw, th = V.rect(tv)
    scx, scy = sx + sw / 2, sy + sh / 2
    tcx, tcy = tx + tw / 2, ty + th / 2
    if direction in ("LR", "RL"):
        if back:
            y = max(sy + sh, ty + th) + 30
            return [(scx, sy + sh), (scx, y), (tcx, y), (tcx, ty + th)]
        x0 = sx + sw if tcx >= scx else sx
        x1 = tx if tcx >= scx else tx + tw
        if abs(scy - tcy) < 2:
            return [(x0, scy), (x1, scy)]
        mx = (x0 + x1) / 2
        return [(x0, scy), (mx, scy), (mx, tcy), (x1, tcy)]
    if back:
        # leave below the source's row, run up the right margin, enter the target from above
        yb = _row_extent(sv, all_views)[1] + 14
        ya = _row_extent(tv, all_views)[0] - 14
        return [(scx, sy + sh), (scx, yb), (right_x, yb), (right_x, ya), (tcx, ya), (tcx, ty)]
    y0 = sy + sh if tcy >= scy else sy
    y1 = ty if tcy >= scy else ty + th
    if abs(scx - tcx) < 2:
        return [(scx, y0), (scx, y1)]
    if sv.type == "UMLPseudostateView" and sw == 50:      # decision: leave from the side corner
        x0 = sx + sw if tcx > scx else sx
        return [(x0, scy), (tcx, scy), (tcx, y1)]
    my = (y0 + y1) / 2
    return [(scx, y0), (scx, my), (tcx, my), (tcx, y1)]


def build_activity_diagram(owner: Obj, diag: ActivityDiagram, name: str, style: V.Style = V.DEFAULT_STYLE,
                           rectilinear: bool = True):
    ag = Obj("UMLActivityGraph")
    ag.set("Name", name)
    ag.ref("Context", owner)
    owner.add("Behaviors", ag)
    top = ag.child("Top", Obj("UMLCompositeState"))
    top.set("Name", "TOP")
    top.ref("StateMachine", ag)
    d, dv = V.new_diagram(ag, "UMLActivityDiagram", name)

    horizontal = diag.direction in ("LR", "RL")
    nodes = {k: n for k, n in diag.nodes.items() if n.kind != "note"}
    sizes = {k: node_size(n, horizontal) for k, n in nodes.items()}

    lanes = list(diag.lanes)
    lane_of = None
    if lanes:
        lane_of = {}
        for k, n in nodes.items():
            lane_of[k] = n.lane
        # nodes outside any subgraph follow a neighbour, else the first lane
        for _ in range(3):
            for e in diag.edges:
                if e.source in lane_of and e.target in lane_of:
                    if not lane_of[e.source] and lane_of[e.target]:
                        lane_of[e.source] = lane_of[e.target]
                    if not lane_of[e.target] and lane_of[e.source]:
                        lane_of[e.target] = lane_of[e.source]
        for k in lane_of:
            if not lane_of[k]:
                lane_of[k] = lanes[0]
    edges = [(e.source, e.target) for e in diag.edges if e.source in nodes and e.target in nodes]
    lane_top = 40
    origin = (40, lane_top + (40 if lanes else 0))
    pos, lane_rects = layered(sizes, edges, direction=("TB" if lanes else diag.direction), hgap=60, vgap=50,
                              lane_of=lane_of, lanes=lanes or None, origin=origin)

    # ---- partitions / swimlanes (drawn first so they stay behind)
    parts = {}
    if lanes:
        bottom = max(pos[k][1] + sizes[k][1] for k in nodes) + 40 if nodes else 300
        for lname, lx, lw in lane_rects:
            p = Obj("UMLPartition")
            p.set("Name", lname)
            p.ref("ActivityGraph", ag)
            ag.add("Partitions", p)
            parts[lname] = p
            sv = V.node_view("UMLSwimlaneView", p, lx, lane_top, lw, bottom - lane_top, style)
            sv.child("NameLabel", V.label(lname))
            V.add_to_diagram(dv, sv)

    # ---- vertices
    models, nviews = {}, {}
    counters = {}
    decision_labels = []
    for k, n in nodes.items():
        kind = n.kind
        if kind in PSEUDO:
            m = Obj("UMLPseudostate")
            base = {"initial": "InitialState", "decision": "Decision", "merge": "Merge",
                    "fork": "Fork", "join": "Join", "junction": "Junction"}[kind]
            counters[base] = counters.get(base, 0) + 1
            m.set("Name", n.label if (n.label and kind == "decision") else "%s%d" % (base, counters[base]))
            m.set("PseudostateKind", PSEUDO[kind], "UMLPseudostateKind")
            vt = "UMLPseudostateView"
        elif kind in ("final", "flowfinal"):
            m = Obj("UMLFinalState")
            counters["Final"] = counters.get("Final", 0) + 1
            m.set("Name", "FinalState%d" % counters["Final"])
            vt = "UMLFinalStateView"
        elif kind == "subactivity":
            m = Obj("UMLSubactivityState")
            m.set("Name", n.name)
            vt = "UMLSubactivityStateView"
        else:
            m = Obj("UMLActionState")
            m.set("Name", n.name)
            vt = "UMLActionStateView"
        m.ref("ContainerState", top)
        top.add("Subvertices", m)
        models[k] = m
        x, y = pos[k]
        w, h = sizes[k]
        v = V.node_view(vt, m, x, y, w, h, style)
        if vt in ("UMLActionStateView", "UMLSubactivityStateView"):
            v.child("NameCompartment", V.name_compartment(n.name, None))
            if vt == "UMLSubactivityStateView":
                v.child("IncludeLabel", V.label(visible=False))
        nviews[k] = V.add_to_diagram(dv, v)
        if lanes:
            p = parts[lane_of[k]]
            p.add_ref("Contents", m)
            m.add_ref("OwnerPartitions", p)
        # decision question text: StarUML does not draw pseudostate names, add a free text view
        if kind == "decision" and n.label:
            decision_labels.append((k, n.label))

    # decision question text: StarUML does not draw pseudostate names, add a free text view
    # on whichever upper corner is free
    for k, text in decision_labels:
        x, y, w, h = V.rect(nviews[k])
        tw = V.text_width(text) + 10
        others = [V.rect(v) for kk, v in nviews.items() if kk != k]

        def free(rx):
            return not any(rx < ox + ow and rx + tw > ox and y - 16 < oy + oh and y > oy for ox, oy, ow, oh in others)
        tx = x + w - 6 if free(x + w - 6) else (x - tw + 6 if free(x - tw + 6) else x + w - 6)
        tv = V.node_view("UMLTextView", None, tx, y - 16, tw, 16, style)
        tv.set("Text", text)
        V.add_to_diagram(dv, tv)

    # ---- transitions
    right_x = max([pos[k][0] + sizes[k][0] for k in nodes] + [0]) + 30
    order = {k: i for i, k in enumerate(nodes)}
    for e in diag.edges:
        if e.source not in models or e.target not in models:
            continue
        t = Obj("UMLTransition")
        if e.label:
            t.set("GuardCondition", e.label)
        t.ref("StateMachine", ag)
        t.ref("Source", models[e.source])
        t.ref("Target", models[e.target])
        ag.add("Transitions", t)
        models[e.source].add_ref("Outgoings", t)
        models[e.target].add_ref("Incomings", t)
        sv, tv = nviews[e.source], nviews[e.target]
        if rectilinear:
            sy, ty = pos[e.source][1], pos[e.target][1]
            sx, tx = pos[e.source][0], pos[e.target][0]
            back = (ty < sy) if not horizontal else (tx < sx)
            pts = _orth_points(sv, tv, "TB" if lanes else diag.direction, back, right_x, list(nviews.values()))
            right_x += 8 if back else 0
        else:
            pts = V.straight_points(sv, tv)
        ev = V.edge_view("UMLTransitionView", t, sv, tv, pts, style,
                         line_style="lsRectilinear" if rectilinear else None)
        V.std_edge_labels(ev, t, "[ %s ] " % e.label if e.label else None, name_visible=bool(e.label))
        V.add_to_diagram(dv, ev)

    # ---- notes
    for nt in diag.notes:
        if nt.target and nt.target in nviews:
            tv = nviews[nt.target]
            nv = V.note_view(dv, nt.text, int(tv.get("Left")) + int(tv.get("Width")) + 40, int(tv.get("Top")), style)
            V.note_link_view(dv, nv, tv, style)
        else:
            V.note_view(dv, nt.text, right_x + 40, 40, style)
    return d
