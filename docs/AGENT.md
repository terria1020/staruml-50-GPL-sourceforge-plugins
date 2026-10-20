# Guide for AI agents

You can draw StarUML 5.0 diagrams by writing **Mermaid** and calling the
`staruml5` MCP tools or CLI. StarUML itself is only needed to look at the result.

## Workflow

1. Call `mermaid_syntax_help(diagram_type)` once per diagram type you will write.
2. New diagram: `mermaid_to_staruml(mermaid, into_path=<project.uml>, package="Design Model::...", diagram_name=...)`.
   - Without `into_path`, pass `output_path` to create a new project.
   - A diagram with the same name in the same package is **replaced**; a `.bak` copy is kept.
3. Edit an existing diagram: `staruml_to_mermaid(path, diagram_name)`, then change the text,
   then `mermaid_to_staruml(..., into_path=path, diagram_name=same name)`.
4. Check the result with `staruml_validate(path)`; the problems list should be `[]`.
5. If StarUML is running, `staruml_com(action="reload")` (or `open`) shows the change.
   Ask the user before using `force=true`, because it discards unsaved edits in StarUML.

## Conventions that match how people draw in StarUML 5

- Sequence: write plain message text such as `Server->>DB: 데이터 저장`. StarUML adds the
  number and the `()` itself. Use `opt <condition>` for a single-operand fragment
  (the condition becomes the frame title) and `alt c1 ... else c2 ... end` for alternatives.
- Participant labels may contain spaces or Korean: `participant DB as 주문 데이터베이스`.
- Class names with spaces: wrap them in backticks, for example `` class `주문 서비스` ``.
- Activity: one `subgraph` per swimlane, `{question}` for decisions, edge labels `-->|guard|`.

## CLI equivalents

```
python -m staruml5 convert in.mmd --into project.uml --package "Design Model" --name "X"
python -m staruml5 export project.uml "X"
python -m staruml5 list project.uml
python -m staruml5 validate project.uml
python -m staruml5 com reload
```
