# TODO

## Wine porting (paused)

- [ ] `com export` fails under Wine with `E_NOTIMPL` (0x80004001) for JPEG/BMP/EMF.
      Candidates: GDI+/OLE picture APIs missing in Wine; try `winetricks gdiplus`
      or native `oleaut32`, or fall back to a window screenshot (xdotool + import).
- [ ] macOS Apple Silicon: StarUML hangs/crashes on start under wine-stable 11.0 and
      wine-devel 11.18, so COM bridge and add-in are unavailable (#1).
      Not tried yet: CrossOver, wine-staging, Windows 11 ARM VM.
- [ ] Verify macOS Intel with `wine/install.sh`.
- [ ] Menu add-in inside Wine: document or script installing a Windows Python
      (embeddable zip) in the prefix and writing `config.ini`.
- [ ] Auto-dismiss the *New Project* dialog on start (registry option for the default approach).

## Features

- [ ] Verify `com export` / `com layout` on real Windows.
- [ ] Verify `mcp --http` end to end from macOS against a Windows 11 ARM VM (VMware Fusion):
      StarUML (x86) under emulation, ARM64 `cscript` -> x86 COM server activation.
- [ ] Sequence: `create participant` positioning polish, `activate/deactivate` mapped
      to explicit activation lengths, notes over several lifelines.
- [ ] Class: generic parameters, association class, qualifiers, package views for `namespace`.
- [ ] Activity: object flow, signal send/accept states, flow final, horizontal swimlanes.
- [ ] Optional: state diagram plugin (`stateDiagram-v2` -> UMLStatechartDiagram),
      use case diagram plugin.
