"""Mermaid ``sequenceDiagram`` parser -> SequenceDiagram IR."""
from __future__ import annotations

import re

from ...core.ir import Activation, Fragment, Message, Operand, SeqNote, SequenceDiagram

# longest arrows first
_ARROWS = ["-->>", "->>", "-->", "->", "--x", "-x", "--)", "-)"]
_ARROW_KIND = {
    "->>": "call", "->": "call",
    "-->>": "return", "-->": "return",
    "-x": "destroy", "--x": "destroy",
    "-)": "send", "--)": "send",
}
_MSG = re.compile(r"^(.+?)\s*(" + "|".join(re.escape(a) for a in _ARROWS) + r")\s*([+-]?)\s*(.+?)\s*:\s*(.*)$")
_MSG_NOTEXT = re.compile(r"^(.+?)\s*(" + "|".join(re.escape(a) for a in _ARROWS) + r")\s*([+-]?)\s*(.+?)\s*$")

_FRAG_OPEN = {"loop": "loop", "alt": "alt", "opt": "opt", "par": "par", "critical": "critical",
              "break": "break", "neg": "neg", "strict": "strict", "seq": "seq", "assert": "assert",
              "ignore": "ignore", "consider": "consider", "region": "critical"}
_FRAG_NEXT = {"else": "alt", "and": "par", "option": "critical"}


def _text(s: str) -> str:
    return s.replace("<br/>", "\n").replace("<br>", "\n").replace("\\n", "\n").strip()


def parse_sequence_diagram(src: str) -> SequenceDiagram:
    d = SequenceDiagram(autonumber=False)
    stack = [Operand()]          # current operand receiving items
    blocks = []                  # open blocks: Fragment, or None for rect/box
    pending_create = False

    def emit(item):
        stack[-1].items.append(item)

    for raw in src.splitlines():
        line = raw.strip()
        if not line or line.startswith("%%"):
            continue
        low = line.lower()
        first = low.split()[0] if low.split() else ""
        if first == "sequencediagram":
            continue
        if first == "title":
            d.title = line[5:].strip(" :")
            continue
        if first == "autonumber":
            d.autonumber = True
            continue
        if first in ("rect", "box"):
            blocks.append(None)
            continue
        if first == "end":
            if blocks and blocks.pop() is not None:
                stack.pop()
            continue
        if first == "create":
            pending_create = True
            line = line[6:].strip()
            low = line.lower()
            first = low.split()[0]
        if first in ("participant", "actor"):
            rest = line[len(first):].strip()
            m = re.match(r"^(.+?)\s+as\s+(.+)$", rest)
            pid, label = (m.group(1).strip(), _text(m.group(2))) if m else (rest, "")
            p = d.part(pid)
            p.kind = first
            if label:
                p.label = label
            if pending_create:
                p.created = True
                pending_create = False
            continue
        if first in ("destroy",):
            continue  # mermaid 'destroy X' line; the -x message carries the semantics
        if first in ("activate", "deactivate"):
            pid = line.split(None, 1)[1].strip()
            d.part(pid)
            emit(Activation(pid, first == "activate"))
            continue
        if first == "note":
            m = re.match(r"^note\s+(left of|right of|over)\s+(.+?)\s*:\s*(.*)$", line, re.I)
            if m:
                pos = {"left of": "left", "right of": "right", "over": "over"}[m.group(1).lower()]
                parts = [x.strip() for x in m.group(2).split(",")]
                for x in parts:
                    d.part(x)
                emit(SeqNote(_text(m.group(3)), parts, pos))
                continue
        if first in _FRAG_OPEN and not _looks_like_message(line):
            op = _FRAG_OPEN[first]
            guard = line[len(first):].strip()
            fr = Fragment(op, [Operand(guard)])
            emit(fr)
            blocks.append(fr)
            stack.append(fr.operands[0])
            continue
        open_frags = [b for b in blocks if b is not None]
        if first in _FRAG_NEXT and open_frags and not _looks_like_message(line):
            guard = line[len(first):].strip()
            opnd = Operand(guard)
            open_frags[-1].operands.append(opnd)
            stack[-1] = opnd
            continue
        m = _MSG.match(line) or _MSG_NOTEXT.match(line)
        if m:
            g = m.groups()
            src_id, arrow, mod, dst_id = g[0].strip(), g[1], g[2], g[3].strip()
            text = _text(g[4]) if len(g) > 4 else ""
            for x in (src_id, dst_id):
                d.part(x)
            kind = _ARROW_KIND[arrow]
            if d.participants[dst_id].created and not any(
                    isinstance(i, Message) and i.target == dst_id for i in _all_messages(stack[0])):
                kind = "create"
            emit(Message(src_id, dst_id, text, kind, activate=(mod == "+"), deactivate=(mod == "-")))
            continue
        if first in ("links", "link", "properties", "details"):
            continue
        raise ValueError("sequenceDiagram: cannot parse line: %r" % line)
    d.items = stack[0].items
    return d


def _looks_like_message(line: str) -> bool:
    """True if a line starting with a keyword ('loop', 'else' ...) is really a message."""
    head = line.split(":", 1)[0]
    return any(a in head for a in _ARROWS)


def _all_messages(opnd):
    for it in opnd.items:
        if isinstance(it, Message):
            yield it
        elif isinstance(it, Fragment):
            for o in it.operands:
                yield from _all_messages(o)
