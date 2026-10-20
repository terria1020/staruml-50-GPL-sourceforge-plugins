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
