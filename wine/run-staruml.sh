#!/usr/bin/env bash
# Start StarUML 5.0 from the Wine prefix created by install.sh.
#   ./run-staruml.sh [file.uml]
set -euo pipefail
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine-staruml5}"
export WINEDEBUG="${WINEDEBUG:--all}"
export LANG="${SU_LANG:-ko_KR.UTF-8}"
EXE="$WINEPREFIX/drive_c/Program Files/StarUML/StarUML.exe"
[[ -f "$EXE" ]] || EXE="$WINEPREFIX/drive_c/Program Files (x86)/StarUML/StarUML.exe"
ARG=()
if [[ $# -gt 0 ]]; then ARG=("$(winepath -w "$(cd "$(dirname "$1")" && pwd)/$(basename "$1")")"); fi
exec wine "$EXE" "${ARG[@]}"
