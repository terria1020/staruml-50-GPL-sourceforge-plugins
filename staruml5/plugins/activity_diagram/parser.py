"""Mermaid ``flowchart`` / ``graph`` parser -> ActivityDiagram IR.

StarUML 5 has no dedicated flowchart diagram, so flowcharts become UML
activity diagrams. Shape mapping:

    A[text] A(text) A([text]) A{{text}} A[/text/] ...   action state
    A{text}                                             decision (merge if no text)
    A{ }   A@{ shape: f-circ }                          merge
    A[[text]]                                           subactivity state
    A((text))                                           initial (no incoming) / final (no outgoing)
    A(((text)))                                         final state
    A@{ shape: fork }   A@{ shape: join }               synchronization bar
    [*]                                                 initial (as source) / final (as target)
    subgraph Lane ... end                               swimlane (partition)
"""
from __future__ import annotations

import re

from ...core.ir import ActivityDiagram, FlowEdge, Note

_ID_RE = re.compile(r"[A-Za-z0-9_\u0080-￿][A-Za-z0-9_.\-\u0080-￿]*|\[\*\]")

# (open, close, shape) - longest first
_SHAPES = [
    ("(((", ")))", "dblcircle"),
    ("([", "])", "stadium"),
    ("[[", "]]", "subroutine"),
    ("[(", ")]", "cylinder"),
    ("((", "))", "circle"),
    ("{{", "}}", "hexagon"),
    ("[/", "/]", "lean"), ("[/", "\\]", "trap"),
    ("[\\", "\\]", "lean"), ("[\\", "/]", "trap"),
    (">", "]", "asym"),
    ("[", "]", "rect"),
    ("(", ")", "round"),
    ("{", "}", "rhombus"),
]

_NEW_SHAPE = {
    "fork": "fork", "join": "join", "hourglass": "fork",
    "circle": "circle", "circ": "circle", "sm-circ": "initial", "small-circle": "initial", "start": "initial",
    "stop": "final", "fr-circ": "final", "framed-circle": "final", "dbl-circ": "final", "double-circle": "final",
    # Mermaid's "Junction" (filled circle) is a merge/branch point, not a fork/join bar
    "f-circ": "rhombus", "filled-circle": "rhombus", "junction": "rhombus",
    "diam": "rhombus", "diamond": "rhombus", "decision": "rhombus", "question": "rhombus",
    "subproc": "subroutine", "subprocess": "subroutine", "fr-rect": "subroutine", "subroutine": "subroutine",
    "cross-circ": "flowfinal", "summary": "flowfinal",
    "text": "text",
}

_EDGE_TEXT = re.compile(
    r"^\s*(<)?(--|==|-\.)\s*(?!>)(.+?)\s*(-{2,}>|={2,}>|\.-+>|-{3,}|={3,}|\.-+|-{2,}[ox]|={2,}[ox])\s*")
_EDGE = re.compile(r"^\s*(<|o|x)?(-{2,}|={2,}|-\.+-|~{3,})(>|o|x)?\s*(?:\|([^|]*)\|)?\s*")


def _clean(t: str) -> str:
    t = t.strip()
    if len(t) >= 2 and t[0] == t[-1] == '"':
        t = t[1:-1]
    if t.startswith("`") and t.endswith("`"):
        t = t[1:-1]
    t = re.sub(r"<br\s*/?>", "\n", t)
    t = t.replace("\\n", "\n")
    t = re.sub(r"</?(b|i|em|strong|u)>", "", t)
    return t.strip()


class _Parser:
    def __init__(self, d: ActivityDiagram):
        self.d = d
        self.shape = {}

    def node(self, s: str, i: int, lane: str):
        m = _ID_RE.match(s, i)
        if not m:
            raise ValueError("flowchart: expected node at: %r" % s[i:])
        nid = m.group(0)
        i = m.end()
        label, shape = None, None
        if s.startswith("@{", i):
            j = s.index("}", i)
            body = s[i + 2:j]
            i = j + 1
            sm = re.search(r"shape\s*:\s*([\w-]+)", body)
            lm = re.search(r'label\s*:\s*"([^"]*)"', body)
            shape = _NEW_SHAPE.get(sm.group(1).lower(), "rect") if sm else "rect"
            label = _clean(lm.group(1)) if lm else None
        else:
            for op, cl, sh in _SHAPES:
                if s.startswith(op, i):
                    j = self._find_close(s, i + len(op), cl)
                    if j < 0:
                        continue
                    label = _clean(s[i + len(op):j])
                    shape = sh
                    i = j + len(cl)
                    break
        if nid == "[*]":
            return nid, i
        n = self.d.node(nid)
        if label is not None:
            n.label = label
        if shape:
            self.shape[nid] = shape
        if lane and not n.lane:
            n.lane = lane
        if s.startswith(":::", i):
            m2 = re.match(r":::[\w-]+", s[i:])
            i += m2.end()
        return nid, i

    @staticmethod
    def _find_close(s, i, cl):
        in_q = False
        while i < len(s):
            if s[i] == '"':
                in_q = not in_q
            elif not in_q and s.startswith(cl, i):
                return i
            i += 1
        return -1

    def node_group(self, s, i, lane):
        ids = []
        while True:
            while i < len(s) and s[i] == " ":
                i += 1
            nid, i = self.node(s, i, lane)
            ids.append(nid)
            m = re.match(r"\s*&\s*", s[i:])
            if m:
                i += m.end()
                continue
            return ids, i

    def statement(self, s: str, lane: str):
        i = 0
        left, i = self.node_group(s, i, lane)
        while i < len(s):
            rest = s[i:]
            if not rest.strip() or rest.strip() == ";":
                break
            m = _EDGE_TEXT.match(rest)
            label = ""
            if m and m.group(2) and m.group(3) and not m.group(3).startswith(("-", ">", "|")):
                label = _clean(m.group(3))
                i += m.end()
            else:
                m = _EDGE.match(rest)
                if not m:
                    raise ValueError("flowchart: cannot parse edge in: %r" % s)
                label = _clean(m.group(4) or "")
                i += m.end()
            right, i = self.node_group(s, i, lane)
            for a in left:
                for b in right:
                    self.d.edges.append(FlowEdge(a, b, label))
            left = right


def parse_flowchart(src: str) -> ActivityDiagram:
    d = ActivityDiagram()
    p = _Parser(d)
    lane_stack = []
    stmts = []
    for raw in src.splitlines():
        line = raw.strip()
        if not line or line.startswith("%%"):
            continue
        for part in _split_semicolons(line):
            stmts.append(part)
    for line in stmts:
        low = line.lower()
        first = low.split()[0]
        if first in ("flowchart", "graph"):
            parts = line.split()
            if len(parts) > 1:
                d.direction = {"TD": "TB"}.get(parts[1].upper(), parts[1].upper())
            continue
        if first == "title":
            d.title = line[5:].strip(" :")
            continue
        if first == "subgraph":
            rest = line[8:].strip()
            m = re.match(r'^([\w\u0080-￿.-]+)\s*\[(.*)\]\s*$', rest)
            # `subgraph id [title]`: lanes are keyed by id, so several lanes may share a title
            key, title = (m.group(1), _clean(m.group(2))) if m else (_clean(rest), _clean(rest))
            lane_stack.append(key)
            if len(lane_stack) == 1 and key not in d.lanes:
                d.lanes.append(key)
                if title != key:
                    d.lane_titles[key] = title
            continue
        if first == "end" and lane_stack and low == "end":
            lane_stack.pop()
            continue
        if first in ("direction", "classdef", "class", "style", "linkstyle", "click", "accTitle".lower(),
                     "accdescr"):
            continue
        m = re.match(r'^note\s*(?:for\s+([\w\u0080-￿.-]+))?\s*"(.*)"$', line, re.I)
        if m:
            d.notes.append(Note(_clean(m.group(2)), m.group(1)))
            continue
        p.statement(line, lane_stack[0] if lane_stack else "")

    _resolve_kinds(d, p.shape)
    return d


def _split_semicolons(line):
    out, cur, q, depth = [], [], False, 0
    for ch in line:
        if ch == '"':
            q = not q
        if not q:
            if ch in "[({":
                depth += 1
            elif ch in "])}":
                depth -= 1
        if ch == ";" and not q and depth <= 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        out.append("".join(cur).strip())
    return [x for x in out if x]


_START_WORDS = {"start", "begin", "시작"}
_END_WORDS = {"end", "stop", "finish", "종료", "끝"}


def _resolve_kinds(d: ActivityDiagram, shape: dict):
    # [*] pseudo nodes -> separate initial / final nodes
    new_edges = []
    star_i = star_f = 0
    for e in d.edges:
        s, t = e.source, e.target
        if s == "[*]":
            star_i += 1
            s = "__initial%d" % star_i
            d.node(s).kind = "initial"
        if t == "[*]":
            star_f += 1
            t = "__final%d" % star_f
            d.node(t).kind = "final"
        new_edges.append(FlowEdge(s, t, e.label))
    d.edges = new_edges
    # lanes of [*] nodes follow their neighbour
    for e in d.edges:
        if e.source.startswith("__initial") and not d.nodes[e.source].lane:
            d.nodes[e.source].lane = d.nodes[e.target].lane
        if e.target.startswith("__final") and not d.nodes[e.target].lane:
            d.nodes[e.target].lane = d.nodes[e.source].lane

    incoming = {n: 0 for n in d.nodes}
    outgoing = {n: 0 for n in d.nodes}
    for e in d.edges:
        outgoing[e.source] += 1
        incoming[e.target] += 1
    for nid, n in d.nodes.items():
        if nid.startswith("__"):
            continue
        sh = shape.get(nid, "rect")
        word = (n.label or nid).strip().lower()
        if sh == "rhombus":
            n.kind = "decision" if (n.label or outgoing[nid] > 1) else "merge"
        elif sh in ("fork", "join"):
            n.kind = "fork" if outgoing[nid] > 1 or sh == "fork" else "join"
            if sh == "join" or (incoming[nid] > 1 and outgoing[nid] <= 1):
                n.kind = "join"
        elif sh == "subroutine":
            n.kind = "subactivity"
        elif sh == "initial":
            n.kind = "initial"
        elif sh in ("final", "dblcircle"):
            n.kind = "final"
        elif sh == "flowfinal":
            n.kind = "flowfinal"
        elif sh == "circle":
            if incoming[nid] == 0:
                n.kind = "initial"
            elif outgoing[nid] == 0:
                n.kind = "final"
            else:
                n.kind = "action"
        elif sh == "stadium" and word in _START_WORDS and incoming[nid] == 0:
            n.kind = "initial"
        elif sh == "stadium" and word in _END_WORDS and outgoing[nid] == 0:
            n.kind = "final"
        elif sh == "text":
            n.kind = "note"
        else:
            n.kind = "action"
