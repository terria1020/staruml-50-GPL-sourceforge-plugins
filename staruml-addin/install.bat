@echo off
rem Installs the Mermaid AddIn into StarUML 5.0 and writes its config.
rem Run from an *Administrator* command prompt (StarUML lives under Program Files).
setlocal
set "HERE=%~dp0"
for %%I in ("%HERE%..") do set "REPO=%%~fI"

set "SU=%ProgramFiles%\StarUML"
if not exist "%SU%\StarUML.exe" set "SU=%ProgramFiles(x86)%\StarUML"
if not "%~1"=="" set "SU=%~1"
if not exist "%SU%\StarUML.exe" (
  echo StarUML.exe not found. Usage: install.bat "C:\path\to\StarUML"
  exit /b 1
)

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY (
  echo Python 3 not found in PATH. Install Python 3.8+ and run again.
  exit /b 1
)

xcopy /E /I /Y "%HERE%MermaidAddIn" "%SU%\modules\staruml-mermaid" >nul || exit /b 1
if not exist "%APPDATA%\staruml5-mermaid" mkdir "%APPDATA%\staruml5-mermaid"
> "%APPDATA%\staruml5-mermaid\config.ini" (
  echo python=%PY%
  echo repo=%REPO%
)
echo Installed to "%SU%\modules\staruml-mermaid"
echo Config: "%APPDATA%\staruml5-mermaid\config.ini"
echo Restart StarUML: Tools ^> Mermaid
endlocal
