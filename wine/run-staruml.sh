#!/usr/bin/env bash
# Start StarUML 5.0 from the Wine prefix created by install.sh.
#   ./run-staruml.sh [file.uml]
# Works with macOS' stock bash 3.2 (no empty-array expansion under `set -u`).
set -euo pipefail
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine-staruml5}"
export WINEDEBUG="${WINEDEBUG:--all}"
export LANG="${SU_LANG:-ko_KR.UTF-8}"
WINE="${STARUML5_WINE:-wine}"

EXE="$WINEPREFIX/drive_c/Program Files/StarUML/StarUML.exe"
[[ -f "$EXE" ]] || EXE="$WINEPREFIX/drive_c/Program Files (x86)/StarUML/StarUML.exe"
if [[ ! -f "$EXE" ]]; then
  echo "StarUML.exe not found in $WINEPREFIX - run ./install.sh first (or set WINEPREFIX)"; exit 1
fi

if [[ $# -gt 0 ]]; then
  FILE="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
  exec "$WINE" "$EXE" "$(winepath -w "$FILE")"
fi
exec "$WINE" "$EXE"
