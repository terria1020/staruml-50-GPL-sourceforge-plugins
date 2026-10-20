"""Reverse conversion entry point: StarUML diagram -> Mermaid text."""
from __future__ import annotations

from . import plugins
from .core.xpd import Obj, Project


def export_diagram(prj: Project, diagram: Obj) -> str:
    return plugins.for_diagram_type(diagram.type).export(prj, diagram)
