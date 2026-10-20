"""Constructors for StarUML 5 model elements and their diagram views.

Every helper mirrors the object structure StarUML itself writes (captured by
driving StarUML 5.0.2 through COM and saving), including the redundant
back-references (``Views[]``, ``Incomings[]`` ...) that StarUML expects.
"""
from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from typing import Optional

from .xpd import Obj

HALF_PI = math.pi / 2  # 1.5707963267949 in StarUML files
PI_6 = math.pi / 6
PI_4 = math.pi / 4


@dataclass
class Style:
    """Colors use Delphi notation: ``clMaroon``, ``clBlack`` or ``$00BBGGRR``."""
    line_color: Optional[str] = "clMaroon"
    fill_color: Optional[str] = "$00B9FFFF"
    font_face: Optional[str] = None
    font_size: Optional[int] = None
    font_color: Optional[str] = None


DEFAULT_STYLE = Style()


# ---------------------------------------------------------------------------
# text metrics (StarUML default font is Tahoma 8pt)
# ---------------------------------------------------------------------------
def char_width(ch: str) -> float:
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 12.0
    if ch in "iljI.,:;'|!":
        return 3.0
    if ch in "mwMW@":
        return 9.0
    if ch.isupper():
        return 7.0
    return 6.0


def text_width(s: str) -> int:
    return int(math.ceil(sum(char_width(c) for c in s)))


LINE_H = 13  # height of one text line


# ---------------------------------------------------------------------------
# generic view parts
# ---------------------------------------------------------------------------
def styled(view: Obj, style: Style) -> Obj:
    if style.line_color:
        view.set("LineColor", style.line_color)
    if style.fill_color:
        view.set("FillColor", style.fill_color)
    if style.font_face:
        view.set("FontFace", style.font_face)
    if style.font_color:
        view.set("FontColor", style.font_color)
    if style.font_size:
        view.set("FontSize", style.font_size)
    return view


def bind(model: Obj, view: Obj) -> Obj:
    """Link view <-> model in both directions."""
    view.ref("Model", model)
    model.add_ref("Views", view)
    return view


def label(text: Optional[str] = None, visible: bool = True, font_style: Optional[int] = None) -> Obj:
    lv = Obj("LabelView")
    if not visible:
        lv.set("Visible", False)
    if font_style is not None:
        lv.set("FontStyle", font_style)
    if text:
        lv.set("Text", text)
    return lv


def name_compartment(text: str, font_style: Optional[int] = 1, stereotype: Optional[str] = None) -> Obj:
    nc = Obj("UMLNameCompartmentView")
    nc.child("NameLabel", label(text, font_style=font_style))
    if stereotype:
        nc.child("StereotypeLabel", label("<<%s>>" % stereotype))
    else:
        nc.child("StereotypeLabel", label(visible=False))
    nc.child("PropertyLabel", label(visible=False))
    return nc


def edge_label(model: Optional[Obj], alpha: float, distance: float, text: Optional[str] = None,
               visible: bool = True, edge_position: Optional[str] = None, host: Optional[Obj] = None) -> Obj:
    lv = Obj("EdgeLabelView")
    if not visible:
        lv.set("Visible", False)
    lv.set("Alpha", float(alpha), "real")
    lv.set("Distance", float(distance), "real")
    if edge_position:
        lv.set("EdgePosition", edge_position, "EdgePositionKind")
    if text:
        lv.set("Text", text)
    if model is not None:
        bind(model, lv)
    if host is not None:
        lv.ref("HostEdge", host)
    return lv


def node_view(type_: str, model: Optional[Obj], x: int, y: int, w: int, h: int, style: Style) -> Obj:
    v = styled(Obj(type_), style)
    v.set("Left", int(x)).set("Top", int(y)).set("Width", int(w)).set("Height", int(h))
    if model is not None:
        bind(model, v)
    return v


def edge_view(type_: str, model: Optional[Obj], tail: Obj, head: Obj, points, style: Style,
              line_style: Optional[str] = None) -> Obj:
    v = styled(Obj(type_), style)
    if line_style:
        v.set("LineStyle", line_style, "LineStyleKind")
    v.set("Points", points_str(points), "Points")
    if model is not None:
        bind(model, v)
    v.ref("Head", head)
    v.ref("Tail", tail)
    return v


def points_str(points) -> str:
    return ";".join("%d,%d" % (int(round(x)), int(round(y))) for x, y in points)


def std_edge_labels(edge: Obj, model: Obj, name: Optional[str] = None, name_visible: bool = True,
                    dist: float = 15, host: bool = False) -> None:
    """NameLabel / StereotypeLabel / PropertyLabel trio every UML edge view carries."""
    h = edge if host else None
    edge.child("NameLabel", edge_label(model, HALF_PI, dist, name, visible=name_visible, host=h))
    edge.child("StereotypeLabel", edge_label(model, HALF_PI, dist * 2, visible=False, host=h))
    edge.child("PropertyLabel", edge_label(model, -HALF_PI, dist, visible=False, host=h))


def add_to_diagram(diagram_view: Obj, view: Obj) -> Obj:
    diagram_view.add("OwnedViews", view)
    return view


# ---------------------------------------------------------------------------
# diagrams
# ---------------------------------------------------------------------------
_DIAGRAM_VIEW = {
    "UMLClassDiagram": "UMLClassDiagramView",
    "UMLActivityDiagram": "UMLActivityDiagramView",
    "UMLSequenceDiagram": "UMLSequenceDiagramView",
    "UMLStatechartDiagram": "UMLStatechartDiagramView",
}


def new_diagram(owner: Obj, type_: str, name: str) -> tuple[Obj, Obj]:
    d = Obj(type_)
    d.set("Name", name)
    d.ref("DiagramOwner", owner)
    dv = d.child("DiagramView", Obj(_DIAGRAM_VIEW[type_]))
    dv.ref("Diagram", d)
    owner.add("OwnedDiagrams", d)
    return d, dv


def new_element(owner: Obj, type_: str, name: Optional[str] = None, coll: str = "OwnedElements",
                owner_ref: str = "Namespace") -> Obj:
    e = Obj(type_)
    if name is not None:
        e.set("Name", name)
    e.ref(owner_ref, owner)
    owner.add(coll, e)
    return e


def note_view(dv: Obj, text: str, x: int, y: int, style: Style) -> Obj:
    lines = text.split("\n")
    w = max(text_width(l) for l in lines) + 20
    h = LINE_H * len(lines) + 12
    v = node_view("UMLNoteView", None, x, y, max(w, 40), max(h, 30), style)
    v.set("Text", text.replace("\n", "\r\n") + "\r\n")
    return add_to_diagram(dv, v)


def note_link_view(dv: Obj, note: Obj, target: Obj, style: Style) -> Obj:
    p1 = center(note)
    p2 = center(target)
    v = styled(Obj("UMLNoteLinkView"), style)
    v.set("Points", points_str([p1, p2]), "Points")
    v.ref("Head", target)
    v.ref("Tail", note)
    return add_to_diagram(dv, v)


def center(v: Obj):
    return (int(v.get("Left", 0)) + int(v.get("Width", 0)) / 2,
            int(v.get("Top", 0)) + int(v.get("Height", 0)) / 2)


def rect(v: Obj):
    x, y = int(v.get("Left", 0)), int(v.get("Top", 0))
    return x, y, int(v.get("Width", 0)), int(v.get("Height", 0))


def clip_to_rect(cx, cy, tx, ty, r):
    """Point where the segment from rect centre (cx,cy) towards (tx,ty) leaves rect r."""
    x, y, w, h = r
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    sx = (w / 2) / abs(dx) if dx else float("inf")
    sy = (h / 2) / abs(dy) if dy else float("inf")
    s = min(sx, sy)
    return cx + dx * s, cy + dy * s


def straight_points(tail: Obj, head: Obj):
    t, h = center(tail), center(head)
    return [clip_to_rect(t[0], t[1], h[0], h[1], rect(tail)),
            clip_to_rect(h[0], h[1], t[0], t[1], rect(head))]
