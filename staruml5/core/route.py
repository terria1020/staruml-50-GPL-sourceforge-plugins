"""Orthogonal edge routing that avoids boxes, plus a checker used by the tests.

The router tries a small set of right-angle path shapes for each edge (straight,
Z-shape through a row gap, side exit from a decision, detour through a free
vertical channel) and keeps the cheapest one. A path that runs through a node
box costs far more than any detour, so detours are taken only when needed.
Segments already used by other edges are penalised, so parallel edges get
their own lane instead of being drawn on top of each other.
"""
from __future__ import annotations

Rect = tuple  # (x, y, w, h)

MARGIN = 4          # clearance around boxes
GAP = 14            # distance of a detour channel from the box it avoids
STEP = 10           # spacing between parallel edges sharing a gap or channel


# --------------------------------------------------------------------------- geometry
def seg_hits_rect(p, q, r: Rect, m: float = MARGIN) -> bool:
    """True if the axis-parallel segment p-q passes through rect r (inflated by m)."""
    (x1, y1), (x2, y2) = p, q
    rx, ry, rw, rh = r
    lx, hx = min(x1, x2), max(x1, x2)
    ly, hy = min(y1, y2), max(y1, y2)
    return lx < rx + rw + m and hx > rx - m and ly < ry + rh + m and hy > ry - m


def simplify(points):
    pts = []
    for p in points:
        p = (round(p[0]), round(p[1]))
        if pts and pts[-1] == p:
            continue
        pts.append(p)
    out = []
    for p in pts:
        if len(out) >= 2:
            a, b = out[-2], out[-1]
            if (a[0] == b[0] == p[0]) or (a[1] == b[1] == p[1]):
                out[-1] = p
                continue
        out.append(p)
    return out


def segments(points):
    return list(zip(points, points[1:]))


def collinear_overlap(s1, s2, tol: float = 3) -> float:
    """Length two axis-parallel segments share when drawn on (nearly) the same line."""
    (a1, a2), (b1, b2) = s1, s2
    if a1[0] == a2[0] and b1[0] == b2[0] and abs(a1[0] - b1[0]) <= tol:
        lo = max(min(a1[1], a2[1]), min(b1[1], b2[1]))
        hi = min(max(a1[1], a2[1]), max(b1[1], b2[1]))
        return max(0, hi - lo)
    if a1[1] == a2[1] and b1[1] == b2[1] and abs(a1[1] - b1[1]) <= tol:
        lo = max(min(a1[0], a2[0]), min(b1[0], b2[0]))
        hi = min(max(a1[0], a2[0]), max(b1[0], b2[0]))
        return max(0, hi - lo)
    return 0


def _bands(rects, axis):
    """Merge rect extents along ``axis`` (1 = y rows, 0 = x columns) into bands."""
    iv = sorted((r[axis], r[axis] + r[axis + 2]) for r in rects)
    out = []
    for lo, hi in iv:
        if out and lo <= out[-1][1]:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return out


def _gap_lines(rects, lo, hi):
    """y values in the empty horizontal gaps strictly between lo and hi."""
    bands = _bands(rects, 1)
    ys = []
    for (b0, b1), (c0, _c1) in zip(bands, bands[1:]):
        if c0 - b1 >= 2 * MARGIN + 2:
            mid = (b1 + c0) / 2
            for k in (0, -1, 1, -2, 2):
                y = mid + k * STEP
                if b1 + MARGIN < y < c0 - MARGIN and lo < y < hi:
                    ys.append(y)
    return ys


# --------------------------------------------------------------------------- router
class Router:
    def __init__(self, nodes: dict, soft=(), walls=()):
        """nodes: id -> rect (hard obstacles). soft: rects to avoid if possible
        (labels, notes). walls: x positions of thick vertical lines (swimlane borders)."""
        self.nodes = dict(nodes)
        self.soft = list(soft)
        self.walls = list(walls)
        self.used = []                  # segments of already routed edges
        allr = list(self.nodes.values())
        self.xs_base = sorted({x for r in allr for x in (r[0] - GAP, r[0] + r[2] + GAP)})
        self.right_x = max((r[0] + r[2] for r in allr), default=0) + 30

    def cost(self, pts, src, dst, limit=None):
        c = 12 * (len(pts) - 2)
        segs = segments(pts)
        for i, (p, q) in enumerate(segs):
            if limit is not None and c >= limit:
                return c                # already worse than the best candidate
            for nid, r in self.nodes.items():
                if nid in (src, dst):
                    continue
                if seg_hits_rect(p, q, r):
                    c += 1000
            for r in self.soft:
                if seg_hits_rect(p, q, r, 1):
                    c += 60
            if p[0] == q[0]:
                for wx in self.walls:
                    if abs(p[0] - wx) < 6 and abs(p[1] - q[1]) > 2:
                        c += 300
            for u in self.used:
                c += 2.0 * collinear_overlap((p, q), u)                    # drawn on top of another edge
                c += 0.3 * collinear_overlap((p, q), u, tol=STEP - 1)      # hugging it (looks doubled)
            c += abs(p[0] - q[0]) * 0.02 + abs(p[1] - q[1]) * 0.02
        # the segments must not run back through the source / into the target from inside
        for nid in (src, dst):
            r = self.nodes.get(nid)
            if r is None:
                continue
            inner = segs[1:] if nid == src else segs[:-1]
            for p, q in inner:
                if seg_hits_rect(p, q, r, -1):
                    c += 1000
        return c

    def candidates(self, s: Rect, t: Rect, decision: bool):
        sx, sy, sw, sh = s
        tx, ty, tw, th = t
        scx, tcx = sx + sw / 2, tx + tw / 2
        scy = sy + sh / 2
        rects = list(self.nodes.values())
        forward = ty >= sy + sh
        xs = sorted(set(self.xs_base + [scx, tcx]))
        xs = [x + k * STEP for x in xs for k in (0, 1, -1)] + [self.right_x + k * STEP for k in range(4)]
        if forward:
            y0, y1 = sy + sh, ty
            if abs(scx - tcx) < 2:
                yield [(scx, y0), (tcx, y1)]
            mids = _gap_lines(rects, y0, y1) or [(y0 + y1) / 2]
            for my in mids:
                yield [(scx, y0), (scx, my), (tcx, my), (tcx, y1)]
            if decision and abs(scx - tcx) >= 2:
                side = sx + sw if tcx > scx else sx
                yield [(side, scy), (tcx, scy), (tcx, y1)]
            yas = [y for y in mids if y < y0 + 80] or mids[:1]
            ybs = [y for y in mids if y > y1 - 80] or mids[-1:]
            for cx in xs:
                for ya in yas[:3]:
                    for yb in ybs[-3:]:
                        if ya <= yb:
                            yield [(scx, y0), (scx, ya), (cx, ya), (cx, yb), (tcx, yb), (tcx, y1)]
                if decision:
                    side = sx + sw if cx > scx else sx
                    for yb in ybs[-3:]:
                        yield [(side, scy), (cx, scy), (cx, yb), (tcx, yb), (tcx, y1)]
        else:
            # back edge (loop) or same-row edge: leave below, come back above the target
            top_all = min(r[1] for r in rects)
            bot_all = max(r[1] + r[3] for r in rects)
            yas = _gap_lines(rects, sy + sh, bot_all + 40)[:3] or [sy + sh + 14]
            ybs = _gap_lines(rects, top_all - 40, ty)[-3:] or [ty - 14]
            if abs(sy - ty) < 2 and (tx > sx + sw or tx + tw < sx):   # same row: straight across
                x0 = sx + sw if tx > sx else sx
                x1 = tx if tx > sx else tx + tw
                yield [(x0, scy), (x1, scy)]
            for cx in xs:
                for ya in yas:
                    for yb in ybs:
                        yield [(scx, sy + sh), (scx, ya), (cx, ya), (cx, yb), (tcx, yb), (tcx, ty)]

    def route(self, src: str, dst: str, decision: bool = False):
        s, t = self.nodes[src], self.nodes[dst]
        best, best_c = None, None
        for pts in self.candidates(s, t, decision):
            pts = simplify(pts)
            if len(pts) < 2:
                continue
            c = self.cost(pts, src, dst, best_c)
            if best_c is None or c < best_c:
                best, best_c = pts, c
        self.used.extend(segments(best))
        return best


# --------------------------------------------------------------------------- checker
def check_edges(edges, nodes: dict):
    """edges: [(src_id, dst_id, points)]. Returns (box_crossings, overlap_length).

    box_crossings lists (src, dst, node) for every segment that runs through a
    node other than its own ends; overlap_length is the total length drawn on
    top of another edge's segment (excluding the shared last stretch into a
    common target)."""
    hits = []
    for src, dst, pts in edges:
        for p, q in segments(pts):
            for nid, r in nodes.items():
                if nid in (src, dst):
                    continue
                if seg_hits_rect(p, q, r, 0):
                    hits.append((src, dst, nid))
    overlap = 0.0
    for i, (s1, d1, p1) in enumerate(edges):
        for s2, d2, p2 in edges[i + 1:]:
            if d1 == d2 or s1 == s2:
                continue          # converging into / diverging from the same node is expected
            for a in segments(p1):
                for b in segments(p2):
                    overlap += collinear_overlap(a, b)
    return hits, overlap
