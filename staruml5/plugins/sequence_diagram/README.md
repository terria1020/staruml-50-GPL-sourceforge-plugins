# sequence_diagram plugin

Mermaid `sequenceDiagram` -> StarUML 5 Sequence Diagram (instance level: `UMLObject`, `UMLStimulus`).

| Mermaid | StarUML |
|---|---|
| `participant A as Label`, `actor A` | `UMLObject` + `UMLSeqObjectView` (underlined name) |
| `A->>B: msg`, `A->B` | `UMLCallAction` stimulus, activation box on B |
| `A-->>B: ret`, `A-->B` | `UMLReturnAction` (dashed); closes A's activation |
| `A-)B: evt` | `UMLSendAction` (asynchronous) |
| `A-xB: bye` | `UMLDestroyAction`; B's lifeline ends with an X |
| `create participant B` + first message | `UMLCreateAction`; B's box starts at that message |
| `A->>A: self` | self message (30 px loop); nested activation |
| `msg(args)` | `Name` + `Arguments` |
| `alt c1 / else c2 / end` | `UMLCombinedFragment iokAlt`, one operand per branch (guards shown) |
| `opt c`, `loop c`, `break c` | single operand; the condition becomes the frame title (StarUML style) |
| `par / and`, `critical / option` | `iokPar`, `iokRegion` |
| `Note right of A: text` | `UMLNoteView` |
| `rect`, `box`, `autonumber` | ignored (StarUML always numbers messages) |

Activations follow call/return semantics, like PlantUML's auto-activation: a call opens
an activation on the receiver, a return or a later message from an outer caller closes it.
Each operand of `alt`/`par` starts from the activation state at the fragment start.
