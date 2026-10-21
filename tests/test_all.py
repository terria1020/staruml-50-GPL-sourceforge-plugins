"""Run with:  python -m unittest discover -s tests"""
import glob
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from staruml5 import api, plugins  # noqa: E402
from staruml5.core.xpd import Project, validate  # noqa: E402
from staruml5.mcp_server import serve  # noqa: E402

EXAMPLES = sorted(glob.glob(os.path.join(ROOT, "examples", "*.mmd")))


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


class ConvertTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_examples_convert_and_validate(self):
        self.assertTrue(EXAMPLES)
        for ex in EXAMPLES:
            with self.subTest(ex=os.path.basename(ex)):
                out = os.path.join(self.tmp, "x.uml")
                res = api.convert(read(ex), out, names=["D"])
                self.assertEqual(res["problems"], [])
                prj = Project.load(out)
                self.assertEqual(validate(prj), [])
                # the file round-trips byte for byte through the reader/writer
                with open(out, "rb") as f:
                    self.assertEqual(prj.to_xml().encode("utf-8"), f.read())

    def test_reverse_export_reparses_to_same_shape(self):
        for ex in EXAMPLES:
            with self.subTest(ex=os.path.basename(ex)):
                src = read(ex)
                plugin = plugins.detect(src)
                ir1 = plugin.parse(src)
                out = os.path.join(self.tmp, "r.uml")
                api.convert(src, out, names=["D"])
                text = api.to_mermaid(Project.load(out), "D")
                ir2 = plugins.detect(text).parse(text)
                if plugin.name == "sequence":
                    self.assertEqual(len(ir1.participants), len(ir2.participants))
                    self.assertEqual(_count_msgs(ir1.items), _count_msgs(ir2.items))
                elif plugin.name == "class":
                    self.assertEqual(len(ir1.classes), len(ir2.classes))
                    self.assertEqual(len(ir1.relations), len(ir2.relations))
                else:
                    self.assertEqual(len(ir1.edges), len(ir2.edges))
                    self.assertEqual(sorted(ir1.lane_title(k) for k in ir1.lanes),
                                     sorted(ir2.lane_title(k) for k in ir2.lanes))

    def test_into_existing_and_replace(self):
        out = os.path.join(self.tmp, "p.uml")
        src = read(os.path.join(ROOT, "examples", "sequence_basic.mmd"))
        api.convert(src, out, names=["S"])
        api.convert(src, into=out, names=["S"])          # replace
        api.convert(src, into=out, names=["S2"], package="Design Model::Sub")
        prj = Project.load(out)
        names = sorted(d["name"] for d in api.list_diagrams(prj))
        self.assertEqual(names, ["S", "S2"])
        self.assertEqual(validate(prj), [])
        self.assertTrue(os.path.exists(out + ".bak"))

    def test_remove_diagram(self):
        out = os.path.join(self.tmp, "rm.uml")
        api.convert([read(e) for e in EXAMPLES], out, names=["d%d" % i for i in range(len(EXAMPLES))])
        prj = Project.load(out)
        for d in list(api.list_diagrams(prj)):
            api.remove_diagram(prj, api.find_diagram(prj, d["name"]))
        self.assertEqual(api.list_diagrams(prj), [])
        self.assertEqual(validate(prj), [])

    def test_fragment(self):
        out = os.path.join(self.tmp, "f.mfj")
        res = api.make_fragment(read(EXAMPLES[0]), out)
        self.assertEqual(res["problems"], [])
        prj = Project.load(out)
        self.assertEqual(prj.kind, "MODELFRAGMENT")
        self.assertEqual(prj.root.type, "UMLPackage")


class ExportMermaidValidityTests(unittest.TestCase):
    """Issue #2: exported Mermaid must stay within what the Mermaid parser accepts."""

    def _project(self):
        from staruml5.core import views as V
        from staruml5.core.ir import ActivityDiagram, Fragment, Message, Operand, SequenceDiagram
        prj = Project.new("T")
        m = prj.find_package("Design Model")
        d = SequenceDiagram()
        d.part("A")
        d.part("B")
        d.items = [
            Fragment("opt", [Operand("", [Message("A", "A", "one")]), Operand("", [Message("A", "B", "two")])]),
            Fragment("neg", [Operand("never", [Message("B", "A", "bad")])]),
            Fragment("alt", [Operand("ok", [Message("A", "B", "x")]), Operand("", [Message("B", "A", "y")])]),
        ]
        plugins.get("sequence").build(m, d, "S", api.get_style())
        for o in prj.root.walk():  # StarUML GUI style: name on the fragment, no guard
            if o.type == "UMLCombinedFragment" and o.get("InteractionOperator") == "iokOpt":
                o.set("Name", "X case")
        V.new_diagram(m, "UMLClassDiagram", "EmptyClass")
        plugins.get("activity").build(m, ActivityDiagram(), "EmptyActivity", api.get_style())
        return prj

    def test_opt_with_two_operands_has_no_else(self):
        text = api.to_mermaid(self._project(), "S")
        lines = [l.strip() for l in text.splitlines()]
        alt_at = lines.index("alt ok")
        self.assertNotIn("else", lines[:alt_at])            # no `else` inside opt
        # one block per operand; the Name labels only the first (it is not the 2nd's condition)
        self.assertEqual(lines.count("opt X case"), 1)
        self.assertEqual(lines.index("opt X case") + 3, lines.index("opt"))
        self.assertIn("else", lines[alt_at:])                 # alt keeps its else

    def test_unsupported_operator_round_trips_via_directive(self):
        text = api.to_mermaid(self._project(), "S")
        self.assertNotIn("\n    neg", text)
        self.assertIn("%% staruml:operator neg", text)
        ir = plugins.detect(text).parse(text)
        self.assertEqual([i.operator for i in ir.items if hasattr(i, "operands")], ["opt", "opt", "neg", "alt"])

    def test_empty_diagrams_are_not_bare_headers(self):
        prj = self._project()
        self.assertEqual(api.to_mermaid(prj, "EmptyClass").split(), ["classDiagram", "direction", "TB"])
        for name in ("EmptyClass", "EmptyActivity"):
            text = api.to_mermaid(prj, name)
            plugins.detect(text).parse(text)    # our own parser accepts it too

    def test_lanes_with_the_same_name_stay_separate(self):
        src = """flowchart TD
            subgraph A["Worker"]
                a1[one] --> a2[two]
            end
            subgraph B["Worker"]
                b1[three]
            end
            a2 --> b1"""
        out = os.path.join(tempfile.mkdtemp(), "l.uml")
        api.convert(src, out, names=["L"])
        prj = Project.load(out)
        lanes = [o for o in prj.root.walk() if o.type == "UMLPartition"]
        self.assertEqual([l.name for l in lanes], ["Worker", "Worker"])
        text = api.to_mermaid(prj, "L")
        self.assertEqual(text.count('subgraph'), 2)
        for n in ("[one]", "[two]", "[three]"):
            self.assertEqual(text.count(n), 1, text)     # every node declared exactly once
        ir = plugins.detect(text).parse(text)
        self.assertEqual(len(ir.lanes), 2)
        self.assertEqual([ir.lane_title(k) for k in ir.lanes], ["Worker", "Worker"])

    def test_export_from_memory_matches_export_from_file(self):
        prj = self._project()
        out = os.path.join(tempfile.mkdtemp(), "m.uml")
        prj.save(out)
        self.assertEqual(api.to_mermaid(prj, "S"), api.to_mermaid(Project.load(out), "S"))


class ParserTests(unittest.TestCase):
    def test_sequence_fragments(self):
        ir = plugins.get("sequence").parse("""sequenceDiagram
            A->>B: hi
            alt x
              B-->>A: ok
            else y
              B-)A: async
            end
            loop forever
              A->>A: self
            end""")
        frags = [i for i in ir.items if hasattr(i, "operands")]
        self.assertEqual([f.operator for f in frags], ["alt", "loop"])
        self.assertEqual([o.guard for o in frags[0].operands], ["x", "y"])
        self.assertEqual(frags[0].operands[1].items[0].kind, "send")

    def test_class_members(self):
        ir = plugins.get("class").parse("""classDiagram
            class A {
              +int x
              -name : String = "a"
              +run(a: int, b: str) bool
              +make()$ A
              +area()* double
            }
            A <|-- B
            C "1" --> "*" A : has""")
        a = ir.classes["A"]
        self.assertEqual([(x.name, x.type, x.visibility) for x in a.attributes],
                         [("x", "int", "+"), ("name", "String", "-")])
        self.assertEqual(a.operations[0].return_type, "bool")
        self.assertTrue(a.operations[1].static)
        self.assertTrue(a.operations[2].abstract)
        self.assertEqual(a.operations[2].return_type, "double")
        g = ir.relations[0]
        self.assertEqual((g.kind, g.source, g.target), ("generalization", "B", "A"))
        self.assertEqual((ir.relations[1].source_mult, ir.relations[1].target_mult), ("1", "*"))

    def test_flowchart_shapes(self):
        ir = plugins.get("activity").parse("""flowchart LR
            s((start)) --> a[Act] --> d{ok?}
            d -->|yes| f@{ shape: fork }
            f --> b & c
            b --> j@{ shape: join }
            c --> j
            j --> e(((end)))
            d -- no --> sub[[Sub]]""")
        kinds = {k: n.kind for k, n in ir.nodes.items()}
        self.assertEqual(kinds, {"s": "initial", "a": "action", "d": "decision", "f": "fork", "b": "action",
                                 "c": "action", "j": "join", "e": "final", "sub": "subactivity"})
        self.assertIn(("d", "sub", "no"), [(e.source, e.target, e.label) for e in ir.edges])

    def test_flowchart_merge_nodes(self):
        ir = plugins.get("activity").parse("""flowchart TD
            s@{ shape: sm-circ } --> d{ok?}
            d -->|y| a[A]
            d -->|n| b[B]
            a --> m{ }
            b --> m
            m --> c[C] --> j@{ shape: f-circ }
            a --> j
            j --> e@{ shape: fr-circ }""")
        kinds = {k: n.kind for k, n in ir.nodes.items()}
        self.assertEqual((kinds["s"], kinds["m"], kinds["j"], kinds["e"]), ("initial", "merge", "merge", "final"))

    def test_syntax_help_documents_merge(self):
        from staruml5.mcp_server import SYNTAX_HELP
        help_text = SYNTAX_HELP["activity"]
        self.assertIn("{ }", help_text)
        self.assertIn("MERGE", help_text)
        # the documented example itself must parse, merge included
        example = "\n".join(l.split("%%")[0].rstrip() for l in help_text.splitlines()
                            if "subgraph" not in l and l.split("%%")[0].strip())
        kinds = {k: n.kind for k, n in plugins.get("activity").parse(example).nodes.items()}
        self.assertEqual(kinds["M"], "merge")


def _activity_routes(path, diagram):
    """(edges, nodes) of an activity diagram in a .uml file, for core.route.check_edges."""
    prj = Project.load(path)
    dv = api.find_diagram(prj, diagram).get_child("DiagramView")
    node_types = ("UMLActionStateView", "UMLSubactivityStateView", "UMLPseudostateView", "UMLFinalStateView")
    nodes, edges = {}, []
    for v in dv.items_of("OwnedViews"):
        if v.type in node_types:
            nodes[v.guid] = tuple(int(v.get(k)) for k in ("Left", "Top", "Width", "Height"))
        elif v.type == "UMLTransitionView":
            pts = [tuple(int(c) for c in xy.split(",")) for xy in v.get("Points").split(";")]
            edges.append((v.get_ref("Tail"), v.get_ref("Head"), pts))
    return edges, nodes


class RoutingTests(unittest.TestCase):
    """Activity edges are right-angle routes that never run through another box."""

    def test_two_phase_commit_has_no_box_crossings(self):
        from staruml5.core.route import check_edges
        out = os.path.join(tempfile.mkdtemp(), "2pc.uml")
        api.convert(read(os.path.join(ROOT, "tests", "fixtures", "two_phase_commit.mmd")), out)
        edges, nodes = _activity_routes(out, "이중 쓰기 2PC 적재")
        self.assertEqual(len(edges), 31)
        hits, overlap = check_edges(edges, nodes)
        self.assertEqual(hits, [])            # was 25 before obstacle-aware routing
        self.assertEqual(overlap, 0)          # was 1631 px of edges drawn on top of each other
        for _s, _t, pts in edges:             # every segment is horizontal or vertical
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                self.assertTrue(x1 == x2 or y1 == y2, pts)

    def test_examples_have_no_box_crossings(self):
        from staruml5.core.route import check_edges
        for name in ("activity_swimlane", "flowchart_basic"):
            out = os.path.join(tempfile.mkdtemp(), name + ".uml")
            api.convert(read(os.path.join(ROOT, "examples", name + ".mmd")), out, names=[name])
            hits, overlap = check_edges(*_activity_routes(out, name))
            self.assertEqual((hits, overlap), ([], 0), name)

    def test_checker_detects_a_crossing(self):
        from staruml5.core.route import check_edges
        nodes = {"a": (0, 0, 40, 20), "b": (0, 100, 40, 20), "c": (0, 200, 40, 20)}
        hits, _ = check_edges([("a", "c", [(20, 20), (20, 200)])], nodes)
        self.assertEqual(hits, [("a", "c", "b")])


class McpTests(unittest.TestCase):
    def test_handshake_and_call(self):
        tmp = tempfile.mkdtemp()
        out = os.path.join(tmp, "m.uml")
        reqs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
                "name": "mermaid_to_staruml",
                "arguments": {"mermaid": "sequenceDiagram\n A->>B: hi", "output_path": out,
                              "diagram_name": "T"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {
                "name": "staruml_to_mermaid", "arguments": {"path": out, "diagram_name": "T"}}},
        ]
        sin = io.StringIO("\n".join(json.dumps(r) for r in reqs) + "\n")
        sout = io.StringIO()
        serve(sin, sout)
        res = [json.loads(l) for l in sout.getvalue().splitlines()]
        self.assertEqual([r["id"] for r in res], [1, 2, 3, 4])
        self.assertIn("tools", res[1]["result"])
        self.assertFalse(res[2]["result"]["isError"], res[2])
        self.assertIn("A->>B: hi", res[3]["result"]["content"][0]["text"])


class McpHttpTests(unittest.TestCase):
    def setUp(self):
        import threading
        from staruml5 import mcp_http
        self.root = tempfile.mkdtemp()
        self.httpd = mcp_http.make_server("127.0.0.1:0", root=self.root, token="t0ken")
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        from staruml5 import mcp_server
        self.httpd.shutdown()
        self.httpd.server_close()
        mcp_server.ROOT = mcp_server.INSTRUCTIONS = None

    def req(self, method, path, body=None, token="t0ken", headers=None):
        import urllib.error
        import urllib.request
        data = body if isinstance(body, bytes) or body is None else json.dumps(body).encode("utf-8")
        r = urllib.request.Request(self.base + path, data=data, method=method, headers=dict(headers or {}))
        if token:
            r.add_header("Authorization", "Bearer " + token)
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def call(self, rid, name, args):
        code, body = self.req("POST", "/mcp", {"jsonrpc": "2.0", "id": rid, "method": "tools/call",
                                               "params": {"name": name, "arguments": args}})
        self.assertEqual(code, 200)
        return json.loads(body)["result"]

    def test_auth_and_origin(self):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
        self.assertEqual(self.req("POST", "/mcp", msg, token=None)[0], 401)
        self.assertEqual(self.req("POST", "/mcp", msg, token="wrong")[0], 401)
        self.assertEqual(self.req("POST", "/mcp", msg, headers={"Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.req("POST", "/mcp", msg)[0], 200)
        self.assertEqual(self.req("POST", "/mcp", {"jsonrpc": "2.0", "method": "notifications/initialized"})[0], 202)
        self.assertEqual(self.req("GET", "/mcp")[0], 405)

    def test_convert_and_files_stay_in_root(self):
        res = self.call(1, "mermaid_to_staruml", {"mermaid": "sequenceDiagram\n A->>B: 안녕",
                                                  "output_path": "sub/m.uml", "diagram_name": "T"})
        self.assertFalse(res["isError"], res)
        code, data = self.req("GET", "/files/sub/m.uml")
        self.assertEqual(code, 200)
        self.assertEqual(data, open(os.path.join(self.root, "sub", "m.uml"), "rb").read())
        self.assertEqual(self.req("PUT", "/files/up/c.uml", data)[0], 201)
        res = self.call(2, "staruml_to_mermaid", {"path": "up/c.uml", "diagram_name": "T"})
        self.assertIn("A->>B: 안녕", res["content"][0]["text"])
        self.assertTrue(self.call(3, "staruml_validate", {"path": "../outside.uml"})["isError"])
        self.assertTrue(self.call(4, "staruml_validate", {"path": os.path.abspath(__file__)})["isError"])
        self.assertEqual(self.req("GET", "/files/%2e%2e/x")[0], 403)
        names = [i["name"] for i in json.loads(self.req("GET", "/files/")[1])]
        self.assertEqual(names, ["sub", "up"])


def _count_msgs(items):
    n = 0
    for it in items:
        if hasattr(it, "operands"):
            for o in it.operands:
                n += _count_msgs(o.items)
        elif hasattr(it, "kind") and hasattr(it, "source"):
            n += 1
    return n


if __name__ == "__main__":
    unittest.main()
