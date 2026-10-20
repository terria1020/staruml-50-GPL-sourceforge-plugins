"""Activity diagram / flowchart plugin: Mermaid ``flowchart``/``graph`` -> StarUML 5
activity diagram (actions, decisions, fork/join, swimlanes from subgraphs)."""
from .builder import build_activity_diagram
from .parser import parse_flowchart
from .exporter import export_activity
from .. import DiagramPlugin

PLUGIN = DiagramPlugin(
    name="activity",
    title="Activity Diagram / Flowchart",
    mermaid_headers=("flowchart", "graph"),
    parse=parse_flowchart,
    build=build_activity_diagram,
    aliases=("flowchart",),
    export=export_activity,
    diagram_types=("UMLActivityDiagram",),
)
