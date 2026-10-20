"""Diagram intermediate representation shared by the Mermaid parsers and the
.uml builders. AI agents can also build these directly (see ``api.py``)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# --------------------------------------------------------------------- class
@dataclass
class Param:
    name: str = ""
    type: str = ""


@dataclass
class Attribute:
    name: str
    type: str = ""
    visibility: str = "+"          # + - # ~
    static: bool = False
    default: str = ""


@dataclass
class Operation:
    name: str
    params: list = field(default_factory=list)   # [Param]
    return_type: str = ""
    visibility: str = "+"
    static: bool = False
    abstract: bool = False


@dataclass
class ClassNode:
    id: str
    label: str = ""
    kind: str = "class"           # class | interface | enumeration
    stereotype: str = ""
    abstract: bool = False
    attributes: list = field(default_factory=list)
    operations: list = field(default_factory=list)
    literals: list = field(default_factory=list)
    package: str = ""             # mermaid namespace

    @property
    def name(self):
        return self.label or self.id


@dataclass
class Relation:
    kind: str                     # association generalization realization dependency aggregation composition
    source: str                   # for generalization/realization: child / implementer
    target: str                   # for generalization/realization: parent / interface
    label: str = ""
    source_mult: str = ""
    target_mult: str = ""
    source_role: str = ""
    target_role: str = ""
    navigable: str = "none"       # none | target | source | both


@dataclass
class Note:
    text: str
    target: Optional[str] = None


@dataclass
class ClassDiagram:
    title: str = ""
    direction: str = "TB"
    classes: dict = field(default_factory=dict)   # id -> ClassNode
    relations: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def cls(self, cid: str) -> ClassNode:
        if cid not in self.classes:
            self.classes[cid] = ClassNode(cid)
        return self.classes[cid]


# --------------------------------------------------------------- sequence
@dataclass
class Participant:
    id: str
    label: str = ""
    kind: str = "participant"     # participant | actor
    created: bool = False         # created by a message mid-diagram

    @property
    def name(self):
        return self.label or self.id


@dataclass
class Message:
    source: str
    target: str
    text: str = ""
    kind: str = "call"            # call | return | send (async) | create | destroy
    activate: bool = False        # '+' suffix  -> activate target
    deactivate: bool = False      # '-' suffix  -> deactivate source


@dataclass
class Fragment:
    operator: str                 # alt opt loop par break critical neg ...
    operands: list = field(default_factory=list)  # [Operand]


@dataclass
class Operand:
    guard: str = ""
    items: list = field(default_factory=list)     # Message | Fragment | SeqNote | Activation


@dataclass
class Activation:
    participant: str
    on: bool = True


@dataclass
class SeqNote:
    text: str
    participants: list = field(default_factory=list)
    position: str = "right"       # left | right | over


@dataclass
class SequenceDiagram:
    title: str = ""
    participants: dict = field(default_factory=dict)   # id -> Participant (ordered)
    items: list = field(default_factory=list)          # Message | Fragment | SeqNote | Activation
    autonumber: bool = True

    def part(self, pid: str) -> Participant:
        if pid not in self.participants:
            self.participants[pid] = Participant(pid)
        return self.participants[pid]


# --------------------------------------------------------------- activity
@dataclass
class FlowNode:
    id: str
    label: str = ""
    kind: str = "action"          # action initial final flowfinal decision merge fork join subactivity object signal_send signal_accept note
    lane: str = ""

    @property
    def name(self):
        return self.label if self.label else self.id


@dataclass
class FlowEdge:
    source: str
    target: str
    label: str = ""


@dataclass
class ActivityDiagram:
    title: str = ""
    direction: str = "TB"
    nodes: dict = field(default_factory=dict)     # id -> FlowNode
    edges: list = field(default_factory=list)
    lanes: list = field(default_factory=list)     # ordered lane names
    notes: list = field(default_factory=list)     # Note(text, target)

    def node(self, nid: str) -> FlowNode:
        if nid not in self.nodes:
            self.nodes[nid] = FlowNode(nid)
        return self.nodes[nid]
