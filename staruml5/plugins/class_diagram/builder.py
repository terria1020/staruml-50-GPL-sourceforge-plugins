"""ClassDiagram IR -> StarUML class diagram (model elements + views)."""
from __future__ import annotations

from ...core import views as V
from ...core.ir import ClassDiagram, ClassNode
from ...core.layout import grid_components
from ...core.xpd import Obj

VIS = {"+": None, "-": "vkPrivate", "#": "vkProtected", "~": "vkPackage"}


def _attr_text(a) -> str:
    s = "%s%s" % (a.visibility or "+", a.name)
    if a.type:
        s += ": " + a.type
    if a.default:
        s += " = " + a.default
    return s


def _op_text(o) -> str:
    ps = ", ".join(("%s: %s" % (p.name, p.type) if p.name and p.type else (p.name or p.type)) for p in o.params)
    s = "%s%s(%s)" % (o.visibility or "+", o.name, ps)
    if o.return_type:
        s += ": " + o.return_type
    return s


def class_size(c: ClassNode) -> tuple[int, int]:
    head_lines = [c.name]
    stereo = _stereo_text(c)
    if stereo:
        head_lines.append("<<%s>>" % stereo)
    rows = [_attr_text(a) for a in c.attributes] + [_op_text(o) for o in c.operations] + list(c.literals)
    w = max([int(V.text_width(t) * 1.1) for t in head_lines] + [V.text_width(t) for t in rows] + [60]) + 24
    if c.kind == "interface" and not (c.attributes or c.operations):
        return max(45, V.text_width(c.name)), 45
    h = len(head_lines) * V.LINE_H + 10
    if c.kind == "enumeration":
        h += max(1, len(c.literals)) * V.LINE_H + 8 + 8
    else:
        h += max(1, len(c.attributes)) * V.LINE_H + 6 if c.attributes else 8
        h += max(1, len(c.operations)) * V.LINE_H + 6 if c.operations else 8
    return w, h


def _stereo_text(c: ClassNode) -> str:
    if c.kind == "enumeration":
        return "enumeration"
    if c.kind == "interface" and (c.attributes or c.operations):
        return "interface"
    return c.stereotype


STANDARD_STEREOTYPES = {"boundary", "control", "entity"}


def _make_model(owner: Obj, c: ClassNode, packages: dict) -> Obj:
    ns = owner
    if c.package:
        ns = packages.get(c.package)
        if ns is None:
            ns = V.new_element(owner, "UMLPackage", c.package)
            packages[c.package] = ns
    t = {"class": "UMLClass", "interface": "UMLInterface", "enumeration": "UMLEnumeration"}[c.kind]
    m = V.new_element(ns, t, c.name)
    if c.stereotype and c.kind == "class":
        if c.stereotype in STANDARD_STEREOTYPES:
            m.set("StereotypeProfile", "UMLStandard")
        m.set("StereotypeName", c.stereotype)
    if c.abstract:
        m.set("IsAbstract", True)
    for o in c.operations:
        op = Obj("UMLOperation")
        op.set("Name", o.name)
        if VIS.get(o.visibility):
            op.set("Visibility", VIS[o.visibility], "UMLVisibilityKind")
        if o.static:
            op.set("OwnerScope", "skClassifier", "UMLScopeKind")
        if o.abstract:
            op.set("IsAbstract", True)
        op.ref("Owner", m)
        m.add("Operations", op)
        for p in o.params:
            po = Obj("UMLParameter")
            po.set("Name", p.name or "arg")
            if p.type:
                po.set("TypeExpression", p.type)
            po.ref("BehavioralFeature", op)
            op.add("Parameters", po)
        if o.return_type:
            po = Obj("UMLParameter")
            po.set("Name", "return")
            po.set("DirectionKind", "pdkReturn", "UMLParameterDirectionKind")
            po.set("TypeExpression", o.return_type)
            po.ref("BehavioralFeature", op)
            op.add("Parameters", po)
    for a in c.attributes:
        at = Obj("UMLAttribute")
        at.set("Name", a.name)
        if VIS.get(a.visibility):
            at.set("Visibility", VIS[a.visibility], "UMLVisibilityKind")
        if a.static:
            at.set("OwnerScope", "skClassifier", "UMLScopeKind")
        if a.type:
            at.set("TypeExpression", a.type)
        if a.default:
            at.set("InitialValue", a.default)
        at.ref("Owner", m)
        m.add("Attributes", at)
    for lit in c.literals:
        lo = Obj("UMLEnumerationLiteral")
        lo.set("Name", lit)
        lo.ref("Enumeration", m)
        m.add("Literals", lo)
    return m


def _make_view(dv: Obj, c: ClassNode, m: Obj, x, y, w, h, style) -> Obj:
    if c.kind == "interface":
        v = V.node_view("UMLInterfaceView", m, x, y, w, h, style)
        boxed = bool(c.attributes or c.operations)
        if not boxed:
            v.set("StereotypeDisplay", "sdkIcon", "UMLStereotypeDisplayKind")
        v.child("NameCompartment", V.name_compartment(c.name, 1, "interface" if boxed else None))
        ac = V.bind(m, Obj("UMLAttributeCompartmentView"))
        oc = V.bind(m, Obj("UMLOperationCompartmentView"))
        if not boxed or not c.attributes:
            ac.set("Visible", False)
        if not boxed:
            oc.set("Visible", False)
        v.child("AttributeCompartment", ac)
        v.child("OperationCompartment", oc)
    elif c.kind == "enumeration":
        v = V.node_view("UMLEnumerationView", m, x, y, w, h, style)
        v.child("NameCompartment", V.name_compartment(c.name, 1, "enumeration"))
        v.child("EnumerationLiteralCompartment", V.bind(m, Obj("UMLEnumerationLiteralCompartmentView")))
        oc = V.bind(m, Obj("UMLOperationCompartmentView"))
        if not c.operations:
            oc.set("Visible", False)
        v.child("OperationCompartment", oc)
    else:
        v = V.node_view("UMLClassView", m, x, y, w, h, style)
        v.child("NameCompartment", V.name_compartment(c.name, 3 if c.abstract else 1, c.stereotype or None))
        v.child("AttributeCompartment", V.bind(m, Obj("UMLAttributeCompartmentView")))
        v.child("OperationCompartment", V.bind(m, Obj("UMLOperationCompartmentView")))
        tp = V.bind(m, Obj("UMLTemplateParameterCompartmentView"))
        tp.set("Visible", False)
        v.child("TemplateParameterCompartment", tp)
    return V.add_to_diagram(dv, v)


def _association(owner, dv, r, ma, mb, va, vb, style, points):
    asc = V.new_element(owner, "UMLAssociation", r.label or None)
    ends = []
    for (m, mult, role, nav) in ((ma, r.source_mult, r.source_role, r.navigable in ("source", "both", "none")),
                                  (mb, r.target_mult, r.target_role, r.navigable in ("target", "both", "none"))):
        e = Obj("UMLAssociationEnd")
        if role:
            e.set("Name", role)
        if not nav:
            e.set("IsNavigable", False)
        if mult:
            e.set("Multiplicity", mult)
        e.ref("Association", asc)
        e.ref("Participant", m)
        asc.add("Connections", e)
        m.add_ref("Associations", e)
        ends.append(e)
    if r.kind == "aggregation":
        ends[0].set("Aggregation", "akAggregate", "UMLAggregationKind")
    elif r.kind == "composition":
        ends[0].set("Aggregation", "akComposite", "UMLAggregationKind")
    # keep attribute order like StarUML (Name, IsNavigable, Aggregation, Multiplicity)
    for e in ends:
        order = {"Name": 0, "IsNavigable": 1, "Aggregation": 2, "Multiplicity": 3}
        attrs = [it for it in e.items if getattr(it, "name", None) in order and it.__class__.__name__ == "Attr"]
        rest = [it for it in e.items if it not in attrs]
        e.items = sorted(attrs, key=lambda a: order[a.name]) + rest

    ev = V.edge_view("UMLAssociationView", asc, va, vb, points, style)
    V.std_edge_labels(ev, asc, r.label or None)
    e0, e1 = ends
    ev.child("HeadRoleNameLabel", V.edge_label(e1, -V.PI_6, 30, r.target_role or None, edge_position="epHead"))
    ev.child("TailRoleNameLabel", V.edge_label(e0, V.PI_6, 30, r.source_role or None, edge_position="epTail"))
    ev.child("HeadMultiplicityLabel", V.edge_label(e1, V.PI_6, 25, r.target_mult or None, edge_position="epHead"))
    ev.child("TailMultiplicityLabel", V.edge_label(e0, -V.PI_6, 25, r.source_mult or None, edge_position="epTail"))
    ev.child("HeadPropertyLabel", V.edge_label(e1, -V.PI_4, 40, visible=False, edge_position="epHead"))
    ev.child("TailPropertyLabel", V.edge_label(e0, V.PI_4, 40, visible=False, edge_position="epTail"))
    for nm, e in (("HeadQualifierCompartment", e1), ("TailQualifierCompartment", e0)):
        q = Obj("UMLQualifierCompartmentView")
        q.set("Left", -1000).set("Top", -1000).set("Width", 50).set("Height", 50)
        V.bind(e, q)
        ev.child(nm, q)
    return V.add_to_diagram(dv, ev)


def build_class_diagram(owner: Obj, diag: ClassDiagram, name: str, style: V.Style = V.DEFAULT_STYLE,
                        reuse_elements: bool = True):
    """Create model elements under ``owner`` (a UMLModel/UMLPackage) and a class diagram."""
    d, dv = V.new_diagram(owner, "UMLClassDiagram", name)

    # reuse existing classes with the same name in the owner (so several diagrams can share them)
    existing = {}
    if reuse_elements:
        for e in owner.items_of("OwnedElements"):
            if isinstance(e, Obj) and e.type in ("UMLClass", "UMLInterface", "UMLEnumeration"):
                existing.setdefault(e.name, e)

    sizes = {cid: class_size(c) for cid, c in diag.classes.items()}
    # hierarchy edges point parent -> child so parents end up on top
    edges = []
    for r in diag.relations:
        if r.kind in ("generalization", "realization"):
            edges.append((r.target, r.source))
        else:
            edges.append((r.source, r.target))
    pos = grid_components(sizes, edges, direction=diag.direction if diag.direction in ("TB", "LR", "BT", "RL") else "TB",
                          hgap=70, vgap=80)

    packages = {}
    models, cviews = {}, {}
    for cid, c in diag.classes.items():
        m = existing.get(c.name) if not c.package else None
        if m is None or m.type != {"class": "UMLClass", "interface": "UMLInterface",
                                   "enumeration": "UMLEnumeration"}[c.kind]:
            m = _make_model(owner, c, packages)
        models[cid] = m
        x, y = pos[cid]
        w, h = sizes[cid]
        cviews[cid] = _make_view(dv, c, m, x, y, w, h, style)

    for r in diag.relations:
        if r.source not in models or r.target not in models:
            continue
        ma, mb = models[r.source], models[r.target]
        va, vb = cviews[r.source], cviews[r.target]
        pts = V.straight_points(va, vb)
        if r.kind == "generalization":
            g = V.new_element(owner, "UMLGeneralization", r.label or None)
            g.ref("Child", ma).ref("Parent", mb)
            mb.add_ref("Specializations", g)
            ma.add_ref("Generalizations", g)
            ev = V.edge_view("UMLGeneralizationView", g, va, vb, pts, style)
            V.std_edge_labels(ev, g, r.label or None)
            V.add_to_diagram(dv, ev)
        elif r.kind in ("realization", "dependency"):
            t = "UMLRealization" if r.kind == "realization" else "UMLDependency"
            dep = V.new_element(owner, t, r.label or None)
            dep.ref("Client", ma).ref("Supplier", mb)
            ma.add_ref("ClientDependencies", dep)
            mb.add_ref("SupplierDependencies", dep)
            ev = V.edge_view(t + "View", dep, va, vb, pts, style)
            V.std_edge_labels(ev, dep, r.label or None)
            V.add_to_diagram(dv, ev)
        else:
            _association(owner, dv, r, ma, mb, va, vb, style, pts)

    # notes
    maxx = max([int(v.get("Left")) + int(v.get("Width")) for v in cviews.values()] + [40])
    ny = 40
    for n in diag.notes:
        if n.target and n.target in cviews:
            tv = cviews[n.target]
            nv = V.note_view(dv, n.text, int(tv.get("Left")) + int(tv.get("Width")) + 40,
                             max(0, int(tv.get("Top")) - 50), style)
            V.note_link_view(dv, nv, tv, style)
        else:
            nv = V.note_view(dv, n.text, maxx + 60, ny, style)
            ny += int(nv.get("Height")) + 20
    return d
