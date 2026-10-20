"""Diagram plugins. Each sub-package exposes ``PLUGIN`` (a :class:`DiagramPlugin`)
with a Mermaid parser (text -> IR) and a builder (IR -> StarUML model + views).

To add a diagram type, create ``plugins/<name>/`` with ``parser.py``,
``builder.py`` and an ``__init__.py`` defining ``PLUGIN``, then list it in
``_PLUGIN_MODULES`` below.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Callable

_PLUGIN_MODULES = ("class_diagram", "sequence_diagram", "activity_diagram")


@dataclass
class DiagramPlugin:
    name: str
    title: str
    mermaid_headers: tuple
    parse: Callable          # (mermaid_text) -> IR
    build: Callable          # (owner_obj, ir, diagram_name, style) -> diagram Obj
    aliases: tuple = field(default_factory=tuple)
    export: Callable = None  # (project, diagram_obj) -> mermaid text
    diagram_types: tuple = field(default_factory=tuple)   # StarUML diagram types it can export


def all_plugins() -> list:
    return [importlib.import_module("%s.%s" % (__name__, m)).PLUGIN for m in _PLUGIN_MODULES]


def get(name: str) -> DiagramPlugin:
    for p in all_plugins():
        if name == p.name or name in p.aliases:
            return p
    raise KeyError("unknown diagram type %r (known: %s)" % (name, ", ".join(p.name for p in all_plugins())))


def for_diagram_type(diagram_type: str) -> DiagramPlugin:
    for p in all_plugins():
        if diagram_type in p.diagram_types:
            return p
    raise KeyError("no exporter for %s" % diagram_type)


def strip_front_matter(src: str):
    """Remove a Mermaid ``---`` front-matter block; returns (text, title)."""
    lines = src.splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    title = None
    if i < len(lines) and lines[i].strip() == "---":
        j = i + 1
        while j < len(lines) and lines[j].strip() != "---":
            s = lines[j].strip()
            if s.lower().startswith("title:"):
                title = s[6:].strip().strip('"\'')
            j += 1
        lines = lines[j + 1:]
    return "\n".join(lines), title


def detect(src: str) -> DiagramPlugin:
    text, _ = strip_front_matter(src)
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("%%"):
            continue
        head = s.split()[0].lower()
        for p in all_plugins():
            if head in p.mermaid_headers:
                return p
        raise ValueError("unsupported Mermaid diagram header: %r (supported: classDiagram, sequenceDiagram, "
                         "flowchart/graph)" % s.split()[0])
    raise ValueError("empty Mermaid source")
