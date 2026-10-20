# activity_diagram plugin

Mermaid `flowchart` / `graph` -> StarUML 5 Activity Diagram. StarUML 5 has no flowchart
type, so flowcharts are drawn as activity diagrams.

| Mermaid | StarUML |
|---|---|
| `A[text]`, `A(text)`, `A{{text}}`, `A[/text/]` ... | `UMLActionState` |
| `A{question}` | decision `UMLPseudostate pkDecision` + question as `UMLTextView` |
| `A{ }` with one outgoing edge | merge (decision diamond without text) |
| `A[[text]]` | `UMLSubactivityState` |
| `A((x))` without incoming edges, `A@{shape: sm-circ}`, `[*] -->` | initial state |
| `A((x))` without outgoing edges, `A(((x)))`, `A@{shape: fr-circ}`, `--> [*]` | final state |
| `A([시작])` / `A([종료])` (start/end words) | initial / final |
| `A@{ shape: fork }`, `A@{ shape: join }` | `pkSynchronization` bar |
| `A -->\|guard\| B`, `A -- guard --> B` | `UMLTransition.GuardCondition` (`[ guard ]`) |
| `A --> B & C`, chains `A --> B --> C` | expanded into single transitions |
| `subgraph Lane ... end`, `subgraph L1["Lane"] ... end` | `UMLPartition` + vertical `UMLSwimlaneView` (lanes are keyed by id, so two lanes may share a name) |
| `TD`, `LR` | layout direction (lanes are always vertical) |

Edges are drawn orthogonally (`lsRectilinear`). Loops go back up along the right margin.
