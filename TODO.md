# TODO

## Wine porting (paused)

- [ ] `com export` fails under Wine with `E_NOTIMPL` (0x80004001) for JPEG/BMP/EMF.
      Candidates: GDI+/OLE picture APIs missing in Wine; try `winetricks gdiplus`
      or native `oleaut32`, or fall back to a window screenshot (xdotool + import).
- [ ] Verify macOS (Intel and Apple Silicon) with `wine/install.sh`: wow64 prefix, `/reg:32`
      registry view, `Program Files (x86)` path, Apple SD Gothic Neo font mapping.
- [ ] Menu add-in inside Wine: document or script installing a Windows Python
      (embeddable zip) in the prefix and writing `config.ini`.
- [ ] Auto-dismiss the *New Project* dialog on start (registry option for the default approach).

## Features

- [ ] Verify `com export` / `com layout` on real Windows.
- [ ] Sequence: `create participant` positioning polish, `activate/deactivate` mapped
      to explicit activation lengths, notes over several lifelines.
- [ ] Class: generic parameters, association class, qualifiers, package views for `namespace`.
- [ ] Activity: object flow, signal send/accept states, flow final, horizontal swimlanes.
- [ ] Optional: state diagram plugin (`stateDiagram-v2` -> UMLStatechartDiagram),
      use case diagram plugin.
