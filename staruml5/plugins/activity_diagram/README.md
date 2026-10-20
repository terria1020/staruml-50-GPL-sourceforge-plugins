# activity_diagram plugin

Mermaid `flowchart` / `graph` -> StarUML 5 Activity Diagram. StarUML 5 has no flowchart
type, so flowcharts are drawn as activity diagrams.

| Mermaid | StarUML |
|---|---|
| `A[text]`, `A(text)`, `A{{text}}`, `A[/text/]` ... | `UMLActionState` |
| `A{question}` | decision `UMLPseudostate pkDecision` + question as `UMLTextView` |
| `A{ }` (empty label), `A@{ shape: f-circ }` | **merge** (decision diamond without text). Do not use `sm-circ`/`((x))` for a merge: those become initial/final nodes |
| `A[[text]]` | `UMLSubactivityState` |
| `A((x))` without incoming edges, `A@{shape: sm-circ}`, `[*] -->` | initial state |
| `A((x))` without outgoing edges, `A(((x)))`, `A@{shape: fr-circ}`, `--> [*]` | final state |
| `A([시작])` / `A([종료])` (start/end words) | initial / final |
| `A@{ shape: fork }`, `A@{ shape: join }` | `pkSynchronization` bar |
| `A -->\|guard\| B`, `A -- guard --> B` | `UMLTransition.GuardCondition` (`[ guard ]`) |
| `A --> B & C`, chains `A --> B --> C` | expanded into single transitions |
| `subgraph Lane ... end`, `subgraph L1["Lane"] ... end` | `UMLPartition` + vertical `UMLSwimlaneView` (lanes are keyed by id, so two lanes may share a name) |
| `TD`, `LR` | layout direction (lanes are always vertical) |

Edges are drawn orthogonally (`lsRectilinear`) by `core/route.py`: each edge tries a few
right-angle shapes (straight, Z through a row gap, side exit from a decision, detour through
a free vertical channel next to the boxes in the way) and keeps the cheapest. Running through
a node box costs far more than any detour, edges already drawn are avoided so parallel edges
get their own track, and swimlane borders are not used as tracks. Loops go back up through a
free channel. `tests/fixtures/two_phase_commit.mmd` is the regression case (0 box crossings).

Known limits: node positions come from `core/layout.py` and are not changed to make room
for long edges (no Sugiyama dummy nodes), edges may still cross each other, and guard labels
are placed by StarUML relative to the edge, so a label can still touch a box.
