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

## macOS (실험적, 미검증)

```bash
brew install --cask --no-quarantine wine-stable     # 또는 gcenx/wine 의 wine-crossover
brew install innoextract
# Apple Silicon: Rosetta 2 필요 (softwareupdate --install-rosetta)
./install.sh --download --addin
./run-staruml.sh
```

- 최신 macOS용 Wine은 32비트 프리픽스를 만들 수 없습니다. 그래서 64비트(wow64) 프리픽스의 `C:\Program Files (x86)`에 설치합니다.
- 한글 폰트는 `Apple SD Gothic Neo`로 매핑합니다.
- 잘 안 되면 CrossOver(상용)에서 "Windows XP 32-bit" bottle을 만들고, 같은 순서(파일 복사, 레지스트리, `StarUML.exe /regserver`)로 설치하는 방법이 가장 확실합니다.

## 알려진 제약

| 항목 | 상태 |
|---|---|
| `com export` (JPEG/BMP/EMF) | Wine에서 `E_NOTIMPL` 오류. Windows에서는 동작할 것으로 예상합니다. |
| 메뉴 애드인 (Tools > Mermaid) | 메뉴 등록은 확인했습니다. 실행하려면 프리픽스 안에 Windows Python이 필요합니다. |
| 실행 중 크래시 후 무응답 | `wineserver -k` 후 `run-staruml.sh`로 다시 시작합니다. |
