"""Mermaid ``classDiagram`` parser -> ClassDiagram IR."""
from __future__ import annotations

import re

from ...core.ir import Attribute, ClassDiagram, Note, Operation, Param, Relation

# relation arrows: left-end, line, right-end
_ARROW = r"(<\|--|<\|\.\.|\*--|o--|<--|<\.\.|--\|>|\.\.\|>|--\*|--o|-->|\.\.>|--|\.\.)"
_ID = r"([\w\u0080-￿.$-]+|`[^`]+`)"
_REL = re.compile(
    r"^" + _ID + r"(?:\s*\"([^\"]*)\")?\s*" + _ARROW + r"\s*(?:\"([^\"]*)\"\s*)?" + _ID + r"(?:\s*:\s*(.*))?$")

_KIND = {
    # arrow: (kind, swap)  swap=True means mermaid right side is the "source"
    "<|--": ("generalization", True), "--|>": ("generalization", False),
    "<|..": ("realization", True), "..|>": ("realization", False),
    "*--": ("composition", False), "--*": ("composition", True),
    "o--": ("aggregation", False), "--o": ("aggregation", True),
    "-->": ("association", False), "<--": ("association", True),
    "--": ("association", False),
    "..>": ("dependency", False), "<..": ("dependency", True),
    "..": ("dependency", False),
}


def _unq(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] == "`":
        return s[1:-1]
    return s


def _generic(s: str) -> str:
    """Mermaid generics ``List~int~`` -> ``List<int>``."""
    out, opened = [], False
    for ch in s:
        if ch == "~":
            out.append(">" if opened else "<")
            opened = not opened
        else:
            out.append(ch)
    return "".join(out)


def parse_member(text: str):
    """Returns Attribute or Operation, or ('stereotype', name)."""
    t = text.strip()
    if not t:
        return None
    m = re.match(r"^<<\s*(.+?)\s*>>$", t)
    if m:
        return ("stereotype", m.group(1))
    static = abstract = False
    if t.endswith("$"):
        static, t = True, t[:-1].rstrip()
    elif t.endswith("*") and ")" in t:
        abstract, t = True, t[:-1].rstrip()
    vis = "+"
    if t[0] in "+-#~":
        vis, t = t[0], t[1:].strip()
    if "(" in t and ")" in t:
        name = t[: t.index("(")].strip()
        args = t[t.index("(") + 1: t.rindex(")")]
        rest = t[t.rindex(")") + 1:].strip()
        if rest.startswith("*"):
            abstract, rest = True, rest[1:].strip()
        elif rest.startswith("$"):
            static, rest = True, rest[1:].strip()
        if rest.endswith("$"):
            static, rest = True, rest[:-1].strip()
        elif rest.endswith("*"):
            abstract, rest = True, rest[:-1].strip()
        if rest.startswith(":"):
            rest = rest[1:].strip()
        params = []
        for a in _split_args(args):
            a = a.strip()
            if not a:
                continue
            if ":" in a:
                pn, pt = a.split(":", 1)
                params.append(Param(pn.strip(), _generic(pt.strip())))
            else:
                parts = a.split()
                if len(parts) >= 2:   # "int count" (type first, mermaid style)
                    params.append(Param(parts[-1], _generic(" ".join(parts[:-1]))))
                else:
                    params.append(Param(parts[0], ""))
        return Operation(name, params, _generic(rest), vis, static, abstract)
    default = ""
    if "=" in t:
        t, default = t.split("=", 1)
        t, default = t.strip(), default.strip()
    if ":" in t:
        n, ty = t.split(":", 1)
        return Attribute(n.strip(), _generic(ty.strip()), vis, static, default)
    parts = t.split()
    if len(parts) >= 2:
        return Attribute(parts[-1], _generic(" ".join(parts[:-1])), vis, static, default)
    return Attribute(t, "", vis, static, default)


def _split_args(s: str):
    depth, cur, out = 0, [], []
    for ch in s:
        if ch in "<~([" and ch != "~":
            depth += 1
        elif ch in ">)]":
            depth -= 1
        if ch == "," and depth <= 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return out


def _apply_member(d: ClassDiagram, cid: str, text: str):
    c = d.cls(cid)
    mem = parse_member(text)
    if mem is None:
        return
    if isinstance(mem, tuple):
        _apply_stereotype(c, mem[1])
    elif c.kind == "enumeration" and isinstance(mem, Attribute) and not mem.type:
        c.literals.append(mem.name)
    elif isinstance(mem, Operation):
        c.operations.append(mem)
    else:
        c.attributes.append(mem)


def _apply_stereotype(c, st: str):
    s = st.strip()
    low = s.lower()
    if low == "interface":
        c.kind = "interface"
    elif low in ("enumeration", "enum"):
        c.kind = "enumeration"
        # attributes declared before the stereotype become literals
        for a in c.attributes:
            c.literals.append(a.name)
        c.attributes = []
    elif low == "abstract":
        c.abstract = True
    else:
        c.stereotype = s


def parse_class_diagram(src: str) -> ClassDiagram:
    d = ClassDiagram()
    lines = _logical_lines(src)
    i = 0
    ns_stack = []
    cur_class = None
    while i < len(lines):
        line = lines[i]
        i += 1
        if cur_class is not None:
            if line == "}":
                cur_class = None
            else:
                _apply_member(d, cur_class, line)
            continue
        low = line.lower()
        if low.startswith("classdiagram"):
            continue
        if low.startswith("direction "):
            d.direction = line.split()[1].upper()
            continue
        if low.startswith("title"):
            d.title = line[5:].strip(" :")
            continue
        if low.startswith("namespace "):
            ns_stack.append(line[10:].strip().rstrip("{").strip())
            continue
        if line == "}":
            if ns_stack:
                ns_stack.pop()
            continue
        if low.startswith(("style ", "classdef ", "cssclass ", "click ", "link ", "callback ")):
            continue
        m = re.match(r'^note\s+for\s+' + _ID + r'\s+"(.*)"$', line, re.I)
        if m:
            d.notes.append(Note(m.group(2).replace("\\n", "\n").replace("<br>", "\n"), _unq(m.group(1))))
            continue
        m = re.match(r'^note\s+"(.*)"$', line, re.I)
        if m:
            d.notes.append(Note(m.group(1).replace("\\n", "\n").replace("<br>", "\n")))
            continue
        m = re.match(r"^<<\s*(.+?)\s*>>\s*" + _ID + r"$", line)
        if m:
            _apply_stereotype(d.cls(_unq(m.group(2))), m.group(1))
            continue
        m = re.match(r"^class\s+" + _ID + r"(~[^~]*~)?(?:\s*\[\s*\"(.*)\"\s*\])?\s*(:::\s*\w+)?\s*(<<.+?>>)?\s*(\{)?\s*(\})?$", line)
        if m:
            cid = _unq(m.group(1))
            c = d.cls(cid)
            if m.group(2):
                c.label = cid + _generic(m.group(2))
            if m.group(3):
                c.label = m.group(3)
            if m.group(5):
                _apply_stereotype(c, m.group(5)[2:-2])
            if ns_stack:
                c.package = "::".join(ns_stack)
            if m.group(6) and not m.group(7):
                cur_class = cid
            continue
        m = _REL.match(line)
        if m:
            a, amult, arrow, bmult, b, lbl = m.groups()
            a, b = _unq(a), _unq(b)
            kind, swap = _KIND[arrow]
            r = Relation(kind, a, b, (lbl or "").strip(), amult or "", bmult or "")
            if kind == "association":
                r.navigable = {"-->": "target", "<--": "source"}.get(arrow, "none")
                if arrow == "<--":
                    r.navigable = "source"
            if swap and kind != "association":
                r.source, r.target = b, a
                r.source_mult, r.target_mult = bmult or "", amult or ""
            d.cls(r.source)
            d.cls(r.target)
            if ns_stack:
                for x in (r.source, r.target):
                    if not d.classes[x].package:
                        d.classes[x].package = "::".join(ns_stack)
            d.relations.append(r)
            continue
        m = re.match(r"^" + _ID + r"\s*:\s*(.+)$", line)
        if m:
            _apply_member(d, _unq(m.group(1)), m.group(2))
            continue
        m = re.match(r"^" + _ID + r"$", line)
        if m:
            d.cls(_unq(m.group(1)))
            continue
        raise ValueError("classDiagram: cannot parse line: %r" % line)
    # mermaid "Animal <|-- Duck : label" style relation labels sometimes hold roles "a | b"
    return d


def _logical_lines(src: str):
    out = []
    for raw in src.splitlines():
        s = raw.strip()
        if not s or s.startswith("%%"):
            continue
        # "class A {  +x int }" on one line -> split braces
        if s.startswith("class ") and "{" in s and s.endswith("}") and not s.rstrip("}").rstrip().endswith("{"):
            head, body = s.split("{", 1)
            out.append(head.strip() + " {")
            for part in body[:-1].split(";"):
                if part.strip():
                    out.append(part.strip())
            out.append("}")
            continue
        out.append(s)
    return out
