"""Small Sugiyama-style layered layout (no external dependencies).

``layered(sizes, edges)`` returns top-left coordinates for every node.
Optionally nodes can be pinned to swimlane columns.
"""
from __future__ import annotations

from collections import defaultdict


def _break_cycles(nodes, edges):
    adj = defaultdict(list)
    for u, v in edges:
        adj[u].append(v)
    state, back = {}, set()

    def dfs(u):
        stack = [(u, iter(adj[u]))]
        state[u] = 1
        while stack:
            n, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                state[n] = 2
                stack.pop()
                continue
            s = state.get(nxt, 0)
            if s == 1:
                back.add((n, nxt))
            elif s == 0:
                state[nxt] = 1
                stack.append((nxt, iter(adj[nxt])))

    for n in nodes:
        if state.get(n, 0) == 0:
            dfs(n)
    return [(v, u) if (u, v) in back else (u, v) for u, v in edges if u != v]


def _layers(nodes, edges):
    preds = defaultdict(list)
    succs = defaultdict(list)
    for u, v in edges:
        preds[v].append(u)
        succs[u].append(v)
    layer = {}
    indeg = {n: len(preds[n]) for n in nodes}
    queue = [n for n in nodes if indeg[n] == 0]
    for n in queue:
        layer[n] = 0
    i = 0
    while i < len(queue):
        u = queue[i]
        i += 1
        for v in succs[u]:
            layer[v] = max(layer.get(v, 0), layer[u] + 1)
            indeg[v] -= 1
            if indeg[v] == 0:
                queue.append(v)
    for n in nodes:  # anything left (should not happen after cycle breaking)
        layer.setdefault(n, 0)
    return layer, preds, succs


def layered(sizes: dict, edges: list, direction: str = "TB", hgap: int = 50, vgap: int = 60,
            lane_of: dict | None = None, lanes: list | None = None, origin=(40, 40)):
    """sizes: id -> (w, h). edges: [(u, v)]. Returns (pos: id -> (x, y), lane_rects)."""
    nodes = list(sizes)
    if not nodes:
        return {}, []
    edges = [(u, v) for u, v in edges if u in sizes and v in sizes]
    dag = _break_cycles(nodes, edges)
    layer, preds, succs = _layers(nodes, dag)

    nlayers = max(layer.values()) + 1
    rows = [[] for _ in range(nlayers)]
    for n in nodes:  # keep declaration order as initial order
        rows[layer[n]].append(n)

    horizontal = direction in ("LR", "RL")
    # ---- crossing reduction: barycenter sweeps
    order = {}

    def renumber():
        for r in rows:
            for i, n in enumerate(r):
                order[n] = i

    renumber()
    lane_idx = {l: i for i, l in enumerate(lanes or [])}
    for sweep in range(8):
        rng = range(1, nlayers) if sweep % 2 == 0 else range(nlayers - 2, -1, -1)
        for li in rng:
            nb = preds if sweep % 2 == 0 else succs

            def key(n):
                ns = [order[m] for m in nb[n] if m in order]
                bc = sum(ns) / len(ns) if ns else order[n]
                if lane_of:
                    return (lane_idx.get(lane_of.get(n, ""), 0), bc)
                return (0, bc)

            rows[li].sort(key=key)
            renumber()
    if lane_of:
        for r in rows:
            r.sort(key=lambda n: (lane_idx.get(lane_of.get(n, ""), 0), order[n]))
        renumber()

    # ---- coordinates
    # "main" axis = layer axis, "cross" axis = within-layer axis
    def main_sz(n):
        w, h = sizes[n]
        return w if horizontal else h

    def cross_sz(n):
        w, h = sizes[n]
        return h if horizontal else w

    layer_extent = [max(main_sz(n) for n in r) if r else 0 for r in rows]
    main_pos = []
    acc = 0
    for li in range(nlayers):
        main_pos.append(acc)
        acc += layer_extent[li] + vgap

    cross = {}
    lane_rects = []
    if lane_of and lanes:
        # each lane is a column; nodes of a layer within a lane are placed side by side
        lane_width = {}
        for l in lanes:
            best = 0
            for r in rows:
                ns = [n for n in r if lane_of.get(n, "") == l]
                if ns:
                    best = max(best, sum(cross_sz(n) for n in ns) + hgap * (len(ns) - 1))
            lane_width[l] = max(best + 2 * hgap, 160)
        lane_x = {}
        x = 0
        for l in lanes:
            lane_x[l] = x
            x += lane_width[l]
        for r in rows:
            for l in lanes:
                ns = [n for n in r if lane_of.get(n, "") == l]
                if not ns:
                    continue
                tot = sum(cross_sz(n) for n in ns) + hgap * (len(ns) - 1)
                c = lane_x[l] + (lane_width[l] - tot) / 2
                for n in ns:
                    cross[n] = c
                    c += cross_sz(n) + hgap
        lane_rects = [(l, lane_x[l], lane_width[l]) for l in lanes]
    else:
        # place each layer centred, then pull nodes towards their parents' centre
        widths = [sum(cross_sz(n) for n in r) + hgap * (len(r) - 1) for r in rows]
        maxw = max(widths) if widths else 0
        for li, r in enumerate(rows):
            c = (maxw - widths[li]) / 2
            for n in r:
                cross[n] = c
                c += cross_sz(n) + hgap
        for _ in range(4):
            for li in range(1, nlayers):
                r = rows[li]
                desired = {}
                for n in r:
                    ps = [p for p in preds[n] if p in cross]
                    if ps:
                        mid = sum(cross[p] + cross_sz(p) / 2 for p in ps) / len(ps)
                        desired[n] = mid - cross_sz(n) / 2
                    else:
                        desired[n] = cross[n]
                # resolve overlaps keeping order
                prev_end = None
                for n in r:
                    x = desired[n]
                    if prev_end is not None and x < prev_end + hgap:
                        x = prev_end + hgap
                    cross[n] = x
                    prev_end = x + cross_sz(n)
                # shift back left if the row drifted right of its desired centre
                if r:
                    shift = (sum(desired[n] for n in r) - sum(cross[n] for n in r)) / len(r)
                    if shift < 0:
                        min_x = min(cross[n] for n in r)
                        shift = max(shift, -min_x)
                        for n in r:
                            cross[n] += shift
        mn = min(cross.values())
        for n in cross:
            cross[n] -= mn

    pos = {}
    ox, oy = origin
    for n in nodes:
        m = main_pos[layer[n]] + (layer_extent[layer[n]] - main_sz(n)) / 2
        if horizontal:
            pos[n] = (int(ox + m), int(oy + cross[n]))
        else:
            pos[n] = (int(ox + cross[n]), int(oy + m))
    if direction in ("BT", "RL"):
        if horizontal:
            mx = max(pos[n][0] + sizes[n][0] for n in nodes)
            pos = {n: (ox + mx - (x + sizes[n][0]) , y) for n, (x, y) in pos.items()}
        else:
            my = max(pos[n][1] + sizes[n][1] for n in nodes)
            pos = {n: (x, oy + my - (y + sizes[n][1])) for n, (x, y) in pos.items()}
    lane_rects = [(l, ox + x - 0, w) for l, x, w in lane_rects]
    return pos, lane_rects


def grid_components(sizes: dict, edges: list, **kw):
    """Lay out each connected component separately and place them left to right."""
    parent = {n: n for n in sizes}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for u, v in edges:
        if u in parent and v in parent:
            parent[find(u)] = find(v)
    comps = defaultdict(list)
    for n in sizes:
        comps[find(n)].append(n)
    groups = sorted(comps.values(), key=lambda g: -len(g))
    singles = [g[0] for g in groups if len(g) == 1]
    multi = [g for g in groups if len(g) > 1]

    pos = {}
    ox, oy = kw.pop("origin", (40, 40))
    x = ox
    bottom = oy
    for g in multi:
        sub = {n: sizes[n] for n in g}
        se = [(u, v) for u, v in edges if u in sub and v in sub]
        p, _ = layered(sub, se, origin=(x, oy), **kw)
        pos.update(p)
        x = max(p[n][0] + sizes[n][0] for n in g) + kw.get("hgap", 50) * 2
        bottom = max(bottom, max(p[n][1] + sizes[n][1] for n in g))
    if singles:
        # isolated nodes: grid under (or next to) the connected parts
        y0 = bottom + kw.get("vgap", 60) if multi else oy
        cols = max(1, int(len(singles) ** 0.5 + 0.999))
        colw = max(sizes[n][0] for n in singles) + kw.get("hgap", 50)
        rowh = max(sizes[n][1] for n in singles) + kw.get("vgap", 60)
        for i, n in enumerate(singles):
            pos[n] = (ox + (i % cols) * colw, y0 + (i // cols) * rowh)
    return pos
