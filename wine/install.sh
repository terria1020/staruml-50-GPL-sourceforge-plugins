#!/usr/bin/env bash
# Install StarUML 5.0 into a Wine prefix (Linux; macOS experimental).
#
#   ./install.sh [installer.exe | --download] [--addin]
#
#   --download  fetch the official installer from SourceForge
#               (https://sourceforge.net/projects/staruml/files/staruml/5.0/)
#
# Environment:
#   WINEPREFIX   prefix to create/use (default: ~/.wine-staruml5)
#   SU_LANG      locale for StarUML text (default: ko_KR.UTF-8 -> CP949, needed for Korean)
#
# What it does (verified on Ubuntu 24.04 / wine 9.0):
#   1. extracts the Inno Setup installer with innoextract (no GUI, avoids the
#      Pgmr101.ocx registration error some installers raise under Wine)
#   2. copies the files to C:\Program Files\StarUML and writes the registry key
#   3. registers WinGraphviz.dll / OptMgr.dll, registers the COM server
#   4. maps Windows UI fonts to a Korean-capable font
#   5. optionally installs the Mermaid add-in (Tools > Mermaid)
set -euo pipefail

INSTALLER="${1:-}"
ADDIN="${2:-}"
URL="https://sourceforge.net/projects/staruml/files/staruml/5.0/staruml-5.0-with-cm.exe/download"
if [[ "$INSTALLER" == "--download" || -z "$INSTALLER" ]]; then
  CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/staruml5"
  mkdir -p "$CACHE"
  INSTALLER="$CACHE/staruml-5.0-with-cm.exe"
  if [[ ! -s "$INSTALLER" ]]; then
    echo "== downloading official installer from SourceForge"
    curl -fL --retry 3 -o "$INSTALLER" "$URL"
  fi
fi
if [[ ! -f "$INSTALLER" ]]; then
  echo "usage: $0 [installer.exe | --download] [--addin]"; exit 1
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
OS="$(uname -s)"
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine-staruml5}"
export WINEDEBUG="${WINEDEBUG:--all}"
export LANG="${SU_LANG:-ko_KR.UTF-8}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing: $1 -> $2"; exit 1; }; }
if [[ "$OS" == "Darwin" ]]; then
  need wine "brew install --cask --no-quarantine wine-stable   (or gcenx/wine/wine-crossover)"
  need innoextract "brew install innoextract"
  KFONT="Apple SD Gothic Neo"
  PF='C:\Program Files (x86)'
  REGVIEW="/reg:32"
else
  need wine "Debian/Ubuntu: sudo dpkg --add-architecture i386 && sudo apt update && sudo apt install wine wine32 wine64 innoextract fonts-nanum"
  need innoextract "sudo apt install innoextract"
  KFONT="NanumGothic"
  PF='C:\Program Files'
  REGVIEW=""
  # a pure 32-bit prefix is the most compatible choice for this 2005 Delphi app
  if [[ ! -d "$WINEPREFIX" ]]; then export WINEARCH=win32; fi
fi

echo "== prefix: $WINEPREFIX"
wineboot -i >/dev/null 2>&1 || true
[[ "$OS" == "Darwin" && -d "$WINEPREFIX/drive_c/Program Files (x86)" ]] || PF='C:\Program Files'

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
echo "== extracting installer"
innoextract -s -d "$TMP" "$INSTALLER"
[[ -f "$TMP/app/StarUML.exe" ]] || { echo "unexpected installer layout (no app/StarUML.exe)"; exit 1; }

DEST="$(winepath -u "$PF\\StarUML")"
mkdir -p "$DEST"
cp -r "$TMP/app/." "$DEST/"
echo "== installed files to $DEST"

wine reg add 'HKLM\Software\StarUML' /v InstallDir /t REG_SZ /d "$PF\\StarUML" /f $REGVIEW >/dev/null
for dll in WinGraphviz.dll OptMgr.dll; do
  wine regsvr32 /s "$PF\\StarUML\\$dll" >/dev/null 2>&1 || echo "   (warning: could not register $dll)"
done
# Delphi automation servers register themselves with /regserver
wine "$PF\\StarUML\\StarUML.exe" /regserver >/dev/null 2>&1 || true

for f in Tahoma "MS Sans Serif" "MS Shell Dlg" "MS Shell Dlg 2" Arial "Microsoft Sans Serif" Gulim "Segoe UI"; do
  wine reg add 'HKCU\Software\Wine\Fonts\Replacements' /v "$f" /t REG_SZ /d "$KFONT" /f >/dev/null
done
echo "== fonts mapped to $KFONT"

if [[ "$ADDIN" == "--addin" ]]; then
  cp -r "$REPO/staruml-addin/MermaidAddIn" "$DEST/modules/staruml-mermaid"
  echo "== Mermaid add-in copied (it needs a Windows Python inside the prefix to run; see wine/README.md)"
fi

cat <<MSG

Done. Start StarUML with:
  $HERE/run-staruml.sh
Drive it from the host with:
  WINEPREFIX="$WINEPREFIX" LANG=$LANG python3 -m staruml5 com status
MSG
