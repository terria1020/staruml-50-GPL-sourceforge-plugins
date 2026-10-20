"""Class diagram plugin: Mermaid ``classDiagram`` -> StarUML 5 class diagram."""
from .builder import build_class_diagram
from .parser import parse_class_diagram
from .exporter import export_class
from .. import DiagramPlugin

PLUGIN = DiagramPlugin(
    name="class",
    title="Class Diagram",
    mermaid_headers=("classdiagram", "classdiagram-v2"),
    parse=parse_class_diagram,
    build=build_class_diagram,
    export=export_class,
    diagram_types=("UMLClassDiagram",),
)
