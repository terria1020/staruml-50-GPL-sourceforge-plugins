# StarUML 5.0 on Wine (Linux / macOS)

StarUML 5.0은 2005년에 나온 32비트 Delphi 앱(ANSI)입니다. Wine에서 실행할 때 필요한 핵심은 세 가지입니다.

1. **32비트 실행 환경**: Linux에서는 `WINEARCH=win32` 프리픽스, macOS에서는 wow64를 씁니다.
2. **로케일**: `LANG=ko_KR.UTF-8`. StarUML은 시스템 ANSI 코드페이지로 문자열을 다룹니다. 한국어 Windows의 CP949와 같게 맞춰야 `.uml` 안의 한글이 깨지지 않습니다.
3. **한글 폰트 대체**: Tahoma, MS Sans Serif 등을 NanumGothic(macOS는 Apple SD Gothic Neo)으로 매핑합니다.

`install.sh`가 이것을 모두 처리합니다.

## Linux (검증됨: Ubuntu 24.04, wine 9.0)

```bash
sudo dpkg --add-architecture i386 && sudo apt update
sudo apt install wine wine32 wine64 innoextract fonts-nanum curl

./install.sh --download --addin      # 또는 ./install.sh /path/to/staruml-5.0-with-cm.exe --addin
./run-staruml.sh                      # 또는 ./run-staruml.sh some.uml
```

- 기본 프리픽스는 `~/.wine-staruml5`입니다. `WINEPREFIX=...`로 바꿀 수 있습니다.
- 설치파일은 GUI로 실행하지 않고 `innoextract`로 풉니다. Inno 설치기를 Wine에서 그대로 돌리면 `Pgmr101.ocx` 등록 오류(`PGMRC100.DLL` 없음)로 중단되기 때문입니다. 이 OCX가 없어도 StarUML은 정상 동작합니다.
- 처음 실행하면 *New Project* 대화상자가 뜹니다. 닫거나 Default Approach를 고르면 됩니다.

### 호스트에서 제어하기

```bash
export WINEPREFIX=~/.wine-staruml5 LANG=ko_KR.UTF-8
python3 -m staruml5 convert ../examples/sequence_basic.mmd -o /tmp/demo.uml
python3 -m staruml5 com open /tmp/demo.uml --force
python3 -m staruml5 com show sequence_basic
python3 -m staruml5 com import-fragment /tmp/x.mfj "Design Model"
```

브리지는 `wine cscript`로 `staruml5/bridge/staruml_bridge.js`를 실행합니다. Wine 콘솔은 긴 비ASCII 출력에서 크래시하는 문제가 있어서, 결과는 `\uXXXX`로 이스케이프한 ASCII JSON으로 주고받습니다.

## macOS (Apple Silicon: 잠정 불가, Intel: 미검증)

Apple Silicon에서는 설치(`install.sh`)는 끝나지만 StarUML이 시작하지 못합니다 ([#1](https://github.com/terria1020/staruml-50-GPL-sourceforge-plugins/issues/1)).

| Wine | 결과 |
|---|---|
| wine-stable 11.0 (Homebrew) | 스플래시 화면에서 멈춤 (CPU 100%) |
| wine-devel 11.18 ([Gcenx 빌드](https://github.com/Gcenx/macOS_Wine_builds)) | 시작 중 크래시 |

확인 환경: macOS 27.2, Apple M4, Rosetta 2, wow64 프리픽스.

따라서 macOS에서 **쓸 수 없는 것**은 실행 중인 StarUML이 필요한 기능뿐입니다.

- `python3 -m staruml5 com ...` (open, reload, layout, export, import-fragment 등)
- MCP 도구 `staruml_com`
- 메뉴 애드인 (Tools > Mermaid)

`convert`, `export`, `fragment`, `list`, `remove`, `validate`와 나머지 MCP 도구는 `.uml` 파일만 다루므로 macOS에서도 그대로 동작합니다. 만든 `.uml`은 Windows나 Linux(Wine)의 StarUML에서 열어 확인하면 됩니다.

시도해 보려면 다음 순서로 합니다. Intel Mac과 CrossOver는 아직 확인하지 않았습니다.

```bash
brew install --cask --no-quarantine wine-stable
brew install innoextract
# Apple Silicon: Rosetta 2 필요 (softwareupdate --install-rosetta)
./install.sh --download --addin
./run-staruml.sh
```

- 최신 macOS용 Wine은 32비트 프리픽스를 만들 수 없습니다. 그래서 64비트(wow64) 프리픽스의 `C:\Program Files (x86)`에 설치합니다.
- 한글 폰트는 `Apple SD Gothic Neo`로 매핑합니다.
- 다른 Wine 빌드는 `PATH`에 그 빌드의 `bin`을 앞에 두고 실행합니다. COM 브리지는 `STARUML5_WINE`으로 wine 실행 파일을 지정할 수 있습니다.

## 알려진 제약

| 항목 | 상태 |
|---|---|
| `com export` (JPEG/BMP/EMF) | Wine에서 `E_NOTIMPL` 오류. Windows에서는 동작할 것으로 예상합니다. |
| 메뉴 애드인 (Tools > Mermaid) | 메뉴 등록은 확인했습니다. 실행하려면 프리픽스 안에 Windows Python이 필요합니다. |
| 실행 중 크래시 후 무응답 | `wineserver -k` 후 `run-staruml.sh`로 다시 시작합니다. |
