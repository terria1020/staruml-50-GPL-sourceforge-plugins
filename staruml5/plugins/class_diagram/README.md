# class_diagram plugin

Mermaid `classDiagram` -> StarUML 5 Class Diagram (`parser.py` -> `builder.py`), and back (`exporter.py`).

| Mermaid | StarUML |
|---|---|
| `class A { ... }`, `A : +x int` | `UMLClass` + `UMLClassView` |
| `<<interface>>` | `UMLInterface` (lollipop icon if it has no members, box otherwise) |
| `<<enumeration>>` + literal lines | `UMLEnumeration` + `UMLEnumerationLiteral` |
| `<<abstract>>`, `method()*` | `IsAbstract` (italic) |
| `<<entity>>`, `<<boundary>>`, `<<control>>`, `<<anything>>` | stereotype (UMLStandard profile for the first three) |
| `+ - # ~` | `vkPublic`, `vkPrivate`, `vkProtected`, `vkPackage` |
| `attr$`, `method()$` | `OwnerScope = skClassifier` (underlined) |
| `name: Type = init`, `Type name` | `TypeExpression`, `InitialValue` |
| `op(a: int, b: str) ReturnType` | `UMLParameter`s + return parameter (`pdkReturn`) |
| `A <\|-- B` | `UMLGeneralization` (B is the child) |
| `A <\|.. B` / `B ..\|> A` | `UMLRealization` |
| `A --> B`, `A -- B` | `UMLAssociation` (navigability from the arrow) |
| `A *-- B`, `A o-- B` | composition / aggregation (diamond at A) |
| `A ..> B` | `UMLDependency` |
| `A "1" --> "0..*" B : label` | multiplicities + association name |
| `note for A "text"` | `UMLNoteView` + `UMLNoteLinkView` |
| `namespace X { ... }` | `UMLPackage X` holding the classes |

Existing classes with the same name in the target package are reused, so several
diagrams can show the same model elements.
