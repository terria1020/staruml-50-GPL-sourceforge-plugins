# StarUML 5.0 file format notes (.uml / .mfj)

Findings from extracting the StarUML 5.0.2.1570 installer, dumping the COM type
library embedded in `StarUML.exe` (see `com-api.txt`, produced by
`tools/tlbdump.py`) and saving reference diagrams by driving StarUML through COM.

## Container

```xml
<?xml version="1.0" encoding="UTF-8"?>
<XPD:PROJECT xmlns:XPD="http://www.staruml.com" version="1">     <!-- .mfj: XPD:MODELFRAGMENT -->
<XPD:HEADER><XPD:SUBUNITS></XPD:SUBUNITS><XPD:PROFILES><XPD:PROFILE>UMLStandard</XPD:PROFILE></XPD:PROFILES></XPD:HEADER>
<XPD:BODY>
<XPD:OBJ name="DocumentElement" type="UMLProject" guid="...">  ... </XPD:OBJ>
</XPD:BODY>
</XPD:PROJECT>
```

* UTF-8 and CRLF line ends. Multi-line text values also use CRLF. Older files use the
  namespace `http://www.plasticsoftware.com/products/plastic`.
* `XPD:OBJ name="Role" type="MetaClass" guid="..."` is an owned object. `XPD:ATTR name type` is an
  attribute (`string`, `integer`, `real`, `boolean`, enum type names such as
  `UMLVisibilityKind`, `Points`). `XPD:REF` is a reference by GUID.
* Collections are written as `<XPD:ATTR name="#Views" type="integer">n</XPD:ATTR>`
  followed by `Views[0]` ... `Views[n-1]`, each either an `OBJ` (owned) or a `REF`.
* GUID = base64 of 16 random bytes plus 2 zero bytes (24 chars ending in `AA`).
* **Both directions of every association are stored**: `View.Model` together with
  `Model.Views[]`, `Transition.Source` with `Vertex.Outgoings[]`, `Stimulus.Sender` with
  `Object.SendingStimuli[]`, `Generalization.Child` with `Child.Generalizations[]`, and so on.
  A dangling reference renders as an "M" (missing model) marker.
* Real numbers use Delphi `FloatToStr` (15 significant digits, e.g. `1.5707963267949`).
* StarUML is an ANSI application: text is converted to the system code page (CP949 on
  Korean Windows) when loaded.

## Ownership

| Diagram | Owner chain |
|---|---|
| Class | `UMLModel/UMLPackage.OwnedDiagrams[] -> UMLClassDiagram` |
| Sequence | `Package.OwnedCollaborationInstanceSets[] -> UMLCollaborationInstanceSet` (`RepresentedClassifier` = package) `.InteractionInstanceSets[] -> UMLInteractionInstanceSet .OwnedDiagrams[] -> UMLSequenceDiagram`. Objects live in `CollaborationInstanceSet.ParticipatingInstances[]`, stimuli in `InteractionInstanceSet.ParticipatingStimuli[]` (each owns an `Action`: `UMLCallAction` / `UMLReturnAction` / `UMLSendAction` / `UMLCreateAction` / `UMLDestroyAction`), combined fragments in `InteractionInstanceSet.Fragments[]` (`InteractionOperator` = `iokAlt`, `iokOpt`, `iokLoop`, `iokPar`, `iokRegion`, ...; `Operands[]` with `Guard`). |
| Activity | `Package.Behaviors[] -> UMLActivityGraph` (`Context` = package) with `Top: UMLCompositeState` (`Subvertices[]`: `UMLActionState`, `UMLSubactivityState`, `UMLPseudostate` [`pkInitial`, `pkDecision`, `pkSynchronization`, `pkJunction`, ...], `UMLFinalState`), `OwnedDiagrams[] -> UMLActivityDiagram`, `Transitions[]` (`GuardCondition`), `Partitions[]` (`Contents[]`, swimlanes). |

## Views

* Diagram: `Diagram.DiagramView` (`UMLClassDiagramView` etc.) `.OwnedViews[]`.
* Node views: `LineColor`, `FillColor`, `Left`, `Top`, `Width`, `Height`, `Model`, plus
  sub-views. `UMLNameCompartmentView` holds `NameLabel`, `StereotypeLabel`, `PropertyLabel`.
  Class views also hold `AttributeCompartment`, `OperationCompartment` and
  `TemplateParameterCompartment`; these compartments are bound to the model too
  (`Model.Views[]` lists them).
* Edge views: `Points` (`x,y;x,y;...`), `Head`, `Tail` (views), `LineStyle`
  (`lsRectilinear` ...), and `EdgeLabelView` children with `Alpha` (radians) and `Distance`.
  Association views carry head/tail role, multiplicity and property labels, plus
  qualifier compartments parked at (-1000, -1000).
* Sequence: `UMLSeqObjectView` (Height = lifeline length) owns `LifeLine: UMLLifeLineView`.
  Messages attach to lifeline views. Each `UMLSeqStimulusView` owns `Activation:
  UMLActivationView` (14 px wide; left = lifeline centre - 7, +7 per nesting level).
  A self message is drawn as `x,y; x+30,y; x+30,y+20; act.left+13,y+20`.
  `UMLCombinedFragmentView` owns `UMLInteractionOperandView`s in `ContainedViews[]`.
  Message numbers and the `()` after call names are computed by StarUML.
* StarUML recomputes label texts and node auto-size on display. Stored sizes only need to be close.

## Model fragments (.mfj)

Same body with `XPD:MODELFRAGMENT` and a `UMLPackage` as `DocumentElement` (no
`Namespace` ref). Import it with `IProjectManager.ImportModelFragment(package, file)` or *File > Import*.

## Add-ins

A folder in `<StarUML>\modules\` with `<Name>.aid` (XML: `NAME`, `ISACTIVE`, `MENUFILE` ...)
and `<Name>.mnu` (menus; a `MAINITEM` with `script="x.vbs|x.js"` runs a script that
gets the application via `CreateObject("StarUML.StarUMLApplication")`). No COM DLL is
needed for script-only add-ins.
