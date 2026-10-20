"""StarUML 5.0 project file (.uml, "XPD" XML) object model, reader and writer.

The .uml format is a serialized MOF object graph:

    <XPD:OBJ name="OwnedElements[0]" type="UMLClass" guid="...">   owned child
    <XPD:ATTR name="Name" type="string">Foo</XPD:ATTR>               attribute
    <XPD:REF name="Namespace">guid</XPD:REF>                         reference
    <XPD:ATTR name="#Views" type="integer">2</XPD:ATTR>              collection size
    <XPD:REF name="Views[0]">guid</XPD:REF>                          collection item

StarUML stores both directions of every association (e.g. a view's ``Model``
ref and the model's ``Views[]`` collection), so builders in this package
always keep both sides in sync.
"""
from __future__ import annotations

import base64
import os
import uuid
import xml.etree.ElementTree as ET
from typing import Iterator, Optional, Union

NS = "http://www.staruml.com"
_Q = "{%s}" % NS


def new_guid() -> str:
    """StarUML GUID: 16 random bytes + 2 zero bytes, base64 (24 chars, ends in 'AA')."""
    return base64.b64encode(uuid.uuid4().bytes + b"\0\0").decode("ascii")


def fmt_real(v: float) -> str:
    """Format like Delphi FloatToStr (15 significant digits, no trailing zeros)."""
    s = "%.15g" % v
    if "e" in s:
        s = repr(float(v))
    return s


class Attr:
    __slots__ = ("name", "type", "value")

    def __init__(self, name: str, type_: str, value: str):
        self.name, self.type, self.value = name, type_, value


class Ref:
    __slots__ = ("name", "target")

    def __init__(self, name: str, target: Union["Obj", str]):
        self.name, self.target = name, target

    @property
    def guid(self) -> str:
        return self.target.guid if isinstance(self.target, Obj) else self.target


class Child:
    __slots__ = ("name", "obj")

    def __init__(self, name: str, obj: "Obj"):
        self.name, self.obj = name, obj


class Coll:
    """Ordered collection (``#Name`` + ``Name[i]``) of owned objects or references."""
    __slots__ = ("name", "items")

    def __init__(self, name: str):
        self.name = name
        self.items: list = []  # Obj (owned) or Ref-target (Obj | guid str)


def _coerce(value, type_: Optional[str]):
    if isinstance(value, bool):
        return "True" if value else "False", type_ or "boolean"
    if isinstance(value, int):
        return str(value), type_ or "integer"
    if isinstance(value, float):
        return fmt_real(value), type_ or "real"
    return str(value), type_ or "string"


class Obj:
    """One XPD:OBJ node. ``items`` keeps file order (Attr | Ref | Child | Coll)."""

    def __init__(self, type_: str, guid: Optional[str] = None):
        self.type = type_
        self.guid = guid or new_guid()
        self.items: list = []
        self.owner: Optional[Obj] = None

    # ---- generic accessors -------------------------------------------------
    def _find(self, cls, name):
        for it in self.items:
            if isinstance(it, cls) and it.name == name:
                return it
        return None

    def set(self, name: str, value, type_: Optional[str] = None) -> "Obj":
        """Set (or replace) an attribute; ``None`` removes it."""
        it = self._find(Attr, name)
        if value is None:
            if it:
                self.items.remove(it)
            return self
        sval, stype = _coerce(value, type_)
        if it:
            it.value, it.type = sval, stype
        else:
            self.items.append(Attr(name, stype, sval))
        return self

    def get(self, name: str, default=None):
        it = self._find(Attr, name)
        return it.value if it else default

    def ref(self, name: str, target: Union["Obj", str, None]) -> "Obj":
        it = self._find(Ref, name)
        if target is None:
            if it:
                self.items.remove(it)
        elif it:
            it.target = target
        else:
            self.items.append(Ref(name, target))
        return self

    def get_ref(self, name: str) -> Optional[str]:
        """GUID of a reference, whether it was loaded from a file or built in memory."""
        it = self._find(Ref, name)
        return it.guid if it else None

    def child(self, name: str, obj: "Obj") -> "Obj":
        """Attach a single owned sub-object (e.g. NameLabel, DiagramView)."""
        it = self._find(Child, name)
        if it:
            it.obj = obj
        else:
            self.items.append(Child(name, obj))
        obj.owner = self
        return obj

    def get_child(self, name: str) -> Optional["Obj"]:
        it = self._find(Child, name)
        return it.obj if it else None

    def coll(self, name: str, create: bool = True) -> Optional[Coll]:
        c = self._find(Coll, name)
        if c is None and create:
            c = Coll(name)
            self.items.append(c)
        return c

    def add(self, name: str, obj: "Obj") -> "Obj":
        """Append an owned object to collection ``name``."""
        self.coll(name).items.append(obj)
        obj.owner = self
        return obj

    def add_ref(self, name: str, target: Union["Obj", str]) -> "Obj":
        self.coll(name).items.append(target)
        return self

    def items_of(self, name: str) -> list:
        c = self.coll(name, create=False)
        return list(c.items) if c else []

    @property
    def name(self) -> Optional[str]:
        return self.get("Name")

    # ---- traversal -----------------------------------------------------------
    def owned(self) -> Iterator["Obj"]:
        for it in self.items:
            if isinstance(it, Child):
                yield it.obj
            elif isinstance(it, Coll):
                for x in it.items:
                    if isinstance(x, Obj) and x.owner is self:
                        yield x

    def walk(self) -> Iterator["Obj"]:
        yield self
        for o in self.owned():
            yield from o.walk()

    def __repr__(self):
        return "<%s %r %s>" % (self.type, self.name, self.guid)


class Project:
    """A whole .uml file: header (sub-units, profiles) + root UMLProject."""

    def __init__(self, root: Obj, profiles=("UMLStandard",), subunits=(), kind: str = "PROJECT"):
        self.root = root
        self.kind = kind          # PROJECT (.uml) or MODELFRAGMENT (.mfj)
        self.profiles = list(profiles)
        self.subunits = list(subunits)

    # ---- construction --------------------------------------------------------
    @classmethod
    def new(cls, title: str = "Untitled", model_name: Optional[str] = "Design Model") -> "Project":
        root = Obj("UMLProject")
        root.set("Title", title)
        prj = cls(root)
        if model_name:
            prj.add_model(model_name)
        return prj

    @classmethod
    def new_fragment(cls, package_name: str) -> "Project":
        """A model fragment (.mfj): a single UMLPackage StarUML can import with
        File > Import > Model Fragment or ``ProjectManager.ImportModelFragment``."""
        root = Obj("UMLPackage")
        root.set("Name", package_name)
        return cls(root, kind="MODELFRAGMENT")

    def add_model(self, name: str, stereotype: Optional[str] = None) -> Obj:
        m = Obj("UMLModel")
        m.set("Name", name)
        if stereotype:
            m.set("StereotypeProfile", "UMLStandard").set("StereotypeName", stereotype)
        m.ref("Namespace", self.root)
        self.root.add("OwnedElements", m)
        return m

    # ---- lookup ----------------------------------------------------------------
    def index(self) -> dict:
        return {o.guid: o for o in self.root.walk()}

    def find_package(self, path: str) -> Optional[Obj]:
        """Find a model/package by ``::``- or ``/``-separated name path."""
        parts = [p for p in path.replace("/", "::").split("::") if p]
        cur = self.root
        if self.kind == "MODELFRAGMENT" and parts and parts[0] == self.root.name:
            parts = parts[1:]
        for p in parts:
            nxt = None
            for o in cur.items_of("OwnedElements"):
                if isinstance(o, Obj) and o.type in ("UMLModel", "UMLPackage", "UMLSubsystem") and o.name == p:
                    nxt = o
                    break
            if nxt is None:
                return None
            cur = nxt
        return cur

    def ensure_package(self, path: str) -> Obj:
        parts = [p for p in path.replace("/", "::").split("::") if p]
        cur = self.root
        if self.kind == "MODELFRAGMENT" and parts and parts[0] == self.root.name:
            parts = parts[1:]
        for i, p in enumerate(parts):
            nxt = None
            for o in cur.items_of("OwnedElements"):
                if isinstance(o, Obj) and o.type in ("UMLModel", "UMLPackage", "UMLSubsystem") and o.name == p:
                    nxt = o
                    break
            if nxt is None:
                nxt = Obj("UMLModel" if (cur is self.root and self.kind == "PROJECT") else "UMLPackage")
                nxt.set("Name", p)
                nxt.ref("Namespace", cur)
                cur.add("OwnedElements", nxt)
            cur = nxt
        return cur

    def diagrams(self) -> list:
        out = []
        for o in self.root.walk():
            if o.type.endswith("Diagram") and o.type.startswith("UML"):
                out.append(o)
        return out

    def remove(self, objs) -> int:
        """Delete owned objects (with their subtrees) and purge every reference to them."""
        dead = set()
        for o in objs:
            dead.update(x.guid for x in o.walk())
            parent = o.owner
            if parent is None:
                continue
            for it in list(parent.items):
                if isinstance(it, Child) and it.obj is o:
                    parent.items.remove(it)
                elif isinstance(it, Coll) and o in it.items:
                    it.items.remove(o)
        for o in self.root.walk():
            for it in list(o.items):
                if isinstance(it, Ref) and it.guid in dead:
                    o.items.remove(it)
                elif isinstance(it, Coll):
                    it.items = [x for x in it.items
                                if (x.guid if isinstance(x, Obj) else x) not in dead]
        return len(dead)

    # ---- I/O ---------------------------------------------------------------------
    @classmethod
    def load(cls, path: str) -> "Project":
        tree = ET.parse(path)
        top = tree.getroot()
        global _Q
        _Q = top.tag[: top.tag.index("}") + 1] if top.tag.startswith("{") else ""
        header = top.find(_Q + "HEADER")
        profiles, subunits = [], []
        if header is not None:
            pe = header.find(_Q + "PROFILES")
            if pe is not None:
                profiles = [(p.text or "") for p in pe]
            se = header.find(_Q + "SUBUNITS")
            if se is not None:
                subunits = [ET.tostring(s, encoding="unicode") for s in se]
        body = top.find(_Q + "BODY")
        root_el = body.find(_Q + "OBJ")
        root = _parse_obj(root_el)
        kind = top.tag.replace(_Q, "")
        prj = cls(root, profiles, subunits, kind=kind)
        prj.namespace = _Q[1:-1] or NS
        return prj

    namespace = NS

    def to_xml(self) -> str:
        out = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<XPD:%s xmlns:XPD="%s" version="1">' % (self.kind, self.namespace),
               "<XPD:HEADER>"]
        if self.kind == "MODELFRAGMENT":
            out += ["</XPD:HEADER>", "<XPD:BODY>"]
            _emit(self.root, "DocumentElement", out)
            out += ["</XPD:BODY>", "</XPD:MODELFRAGMENT>"]
            return "\r\n".join(out) + "\r\n"
        out.append("<XPD:SUBUNITS>")
        for s in self.subunits:
            out.append(s.replace(' xmlns:ns0="%s"' % self.namespace, "").replace("ns0:", "XPD:"))
        out += ["</XPD:SUBUNITS>", "<XPD:PROFILES>"]
        for p in self.profiles:
            out.append("<XPD:PROFILE>%s</XPD:PROFILE>" % _esc(p))
        out += ["</XPD:PROFILES>", "</XPD:HEADER>", "<XPD:BODY>"]
        _emit(self.root, "DocumentElement", out)
        out += ["</XPD:BODY>", "</XPD:%s>" % self.kind]
        return "\r\n".join(out) + "\r\n"

    def save(self, path: str) -> None:
        data = self.to_xml().encode("utf-8")
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)


def _esc(s: str) -> str:
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # XML parsers normalise CRLF -> LF; StarUML writes CRLF inside text.
    s = s.replace("\r\n", "\n").replace("\n", "\r\n")
    return s


def _emit(o: Obj, name: str, out: list) -> None:
    out.append('<XPD:OBJ name="%s" type="%s" guid="%s">' % (name, o.type, o.guid))
    for it in o.items:
        if isinstance(it, Attr):
            out.append('<XPD:ATTR name="%s" type="%s">%s</XPD:ATTR>' % (it.name, it.type, _esc(it.value)))
        elif isinstance(it, Ref):
            out.append('<XPD:REF name="%s">%s</XPD:REF>' % (it.name, it.guid))
        elif isinstance(it, Child):
            _emit(it.obj, it.name, out)
        elif isinstance(it, Coll):
            if not it.items:
                continue
            out.append('<XPD:ATTR name="#%s" type="integer">%d</XPD:ATTR>' % (it.name, len(it.items)))
            for i, x in enumerate(it.items):
                nm = "%s[%d]" % (it.name, i)
                if isinstance(x, Obj) and x.owner is o:
                    _emit(x, nm, out)
                else:
                    g = x.guid if isinstance(x, Obj) else x
                    out.append('<XPD:REF name="%s">%s</XPD:REF>' % (nm, g))
    out.append("</XPD:OBJ>")


def _split_index(name: str):
    if name.endswith("]") and "[" in name:
        base, idx = name[:-1].split("[", 1)
        return base, int(idx)
    return name, None


def _parse_obj(el) -> Obj:
    o = Obj(el.get("type"), el.get("guid"))
    colls = {}
    for c in el:
        tag = c.tag.replace(_Q, "")
        name = c.get("name")
        if tag == "ATTR" and name.startswith("#"):
            colls[name[1:]] = o.coll(name[1:])
            continue
        base, idx = _split_index(name)
        if idx is not None and base in colls:
            coll = colls[base]
            if tag == "OBJ":
                sub = _parse_obj(c)
                sub.owner = o
                coll.items.append(sub)
            else:
                coll.items.append((c.text or "").strip())
            continue
        if tag == "ATTR":
            o.items.append(Attr(name, c.get("type"), c.text or ""))
        elif tag == "REF":
            o.items.append(Ref(name, (c.text or "").strip()))
        elif tag == "OBJ":
            sub = _parse_obj(c)
            sub.owner = o
            o.items.append(Child(name, sub))
    return o


def resolve(prj: Project, target) -> Optional[Obj]:
    if isinstance(target, Obj):
        return target
    return prj.index().get(target)


def validate(prj: Project) -> list:
    """Return a list of problems (dangling references, duplicate GUIDs, bad counts)."""
    problems = []
    seen = {}
    for o in prj.root.walk():
        if o.guid in seen:
            problems.append("duplicate guid %s (%s / %s)" % (o.guid, seen[o.guid].type, o.type))
        seen[o.guid] = o
    for o in prj.root.walk():
        for it in o.items:
            if isinstance(it, Ref):
                if it.guid not in seen:
                    problems.append("%s %r: dangling ref %s -> %s" % (o.type, o.name, it.name, it.guid))
            elif isinstance(it, Coll):
                for x in it.items:
                    g = x.guid if isinstance(x, Obj) else x
                    if g not in seen:
                        problems.append("%s %r: dangling ref %s[] -> %s" % (o.type, o.name, it.name, g))
    return problems

