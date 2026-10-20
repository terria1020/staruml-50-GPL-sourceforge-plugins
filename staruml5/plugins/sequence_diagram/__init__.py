"""Sequence diagram plugin: Mermaid ``sequenceDiagram`` -> StarUML 5 sequence diagram
(objects, stimuli, activations, combined fragments alt/opt/loop/par/...)."""
from .builder import build_sequence_diagram
from .parser import parse_sequence_diagram
from .exporter import export_sequence
from .. import DiagramPlugin

PLUGIN = DiagramPlugin(
    name="sequence",
    title="Sequence Diagram",
    mermaid_headers=("sequencediagram",),
    parse=parse_sequence_diagram,
    build=build_sequence_diagram,
    export=export_sequence,
    diagram_types=("UMLSequenceDiagram",),
)
