# Star Wars Genesis 한국어 패처

**Star Wars Genesis 8.8.32용 Windows 한국어 패처 v0.1.0**입니다.
기존 8.8.1 SST 번역과 추가 번역 검토 결과를 반영하며, 사용자의 플러그인에서
번역된 파일을 생성한 다음 백업하고 적용합니다. Python, Java, xTranslator,
Gemini API 키를 별도로 설치하거나 입력할 필요가 없습니다.

## 다운로드와 설치

1. [Releases](https://github.com/munument1/-KR-StarWars-Genesis-Patcher/releases/latest)에서
   `GenesisKRPatcher-v0.1.0.zip`을 내려받고 압축을 풉니다.
2. 실행 중인 Starfield를 완전히 종료합니다.
3. `GenesisKRPatcher.exe`를 실행해 제네시스의 **Game 폴더**를 선택합니다.
   `mods`, `profiles`, `ModOrganizer.ini`가 들어 있는 폴더입니다.
   Steam의 Starfield 설치 폴더를 선택하지 마세요.
4. **검사하고 패치 생성**을 누릅니다. 이 단계는 게임 파일을 변경하지 않습니다.
5. 준비가 끝나면 **백업 후 적용**을 누릅니다.
6. MO2에서 `Star Wars Genesis Compiler` 프로필로 SFSE를 실행합니다.
   Starfield 언어는 영어를 사용합니다. 처음 실행 시 화면이 뜨기까지 시간이 걸릴 수 있습니다.

기존 시험판 적용자는 동일한 절차를 사용하면 됩니다. 이미 적용된 파일은 건너뜁니다.
설치 버전이나 모드 우선순위, 원본 파일이 지원 대상과 다르면 적용을 중단합니다.
없는 선택 DLC의 추가 Strings는 건너뜁니다.

## 적용 범위

- 140개 플러그인과 13개 Genesis Strings 파일, 총 248,199개 텍스트 변경 위치.
- 추가 초안 및 보류 항목 6,371건의 AI·Codex 검토 반영.
- HUD UI 사전의 문구 키 3,051개 유지, 3,013개 값 변경.
  제네시스가 따로 바꾼 문구 65개는 스타워즈 설정과 안내를 유지해서 번역했습니다.
- UI 및 대화창에 Pretendard 한글 글리프 추가. 기존 영문 및 컨트롤러 글리프 유지.
- 원형 HUD 행성 이름의 한글 잘림 보정: 글자 칸 18픽셀, 간격 13도, 크기 11.
- Genesis에서 제공하지 않는 기존 사용자 한패 Strings 26개.
- `GENESIS_DOCUMENTS.bat` 한국어 안내. 최고 그래픽은 정확히 `MAX`를 입력해야 선택됩니다.

패처의 적용 대상은 **제네시스 `mods` 폴더와 Game 폴더의 BAT**입니다.
Steam 본편 `Starfield/Data`는 버전 확인을 위해 읽기만 하며 수정하지 않습니다.
제네시스가 스타워즈식으로 변경한 영어를 번역 원문으로 사용합니다.

## 백업과 복원

백업은 선택한 Game 폴더의 `.genesis-kr-backups/작업번호`에 저장됩니다.
패처의 **백업 복원**에서 해당 폴더의 `journal.json`을 선택하면 되돌릴 수 있습니다.
여러 차례 나누어 적용한 경우, 모두 되돌리려면 **최근 백업부터 역순으로** 복원하세요.
설치 후 다른 도구로 파일을 바꾸었다면 덮어쓰지 않고 복원을 중단합니다.

## 확인한 범위

사용자가 실제 게임에서 메뉴 번역, 한글 폰트 출력, 원형 HUD의 행성 이름 표시를
확인했습니다. 패치 엔진 및 설치/복원 단위 테스트 14개를 통과했고, 플러그인 및
Strings 파일 153개를 독립 파서로 검증했습니다. EXE의 내장 파일 검사와 패치 생성도
검증했습니다.

전체 퀘스트와 대사를 플레이 검증한 릴리즈는 아닙니다. 기존 SST 전체의 사람 교열,
xTranslator와의 완전한 출력 대조, 모든 PEX 및 SWF 내부 문구 검토는 완료되지 않았습니다.
게임 내 오역이나 잘림은 [Issues](https://github.com/munument1/-KR-StarWars-Genesis-Patcher/issues)에
스크린샷과 해당 위치를 알려주세요.

## 소스 실행 및 빌드

Python 3.14에서 확인했습니다. 소스 실행에는 표준 라이브러리만 사용합니다.

```powershell
python patcher_app.py
python -m unittest test_patch_engine test_installer_backend
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm --onefile --windowed --name GenesisKRPatcher --add-data "installer-data;installer-data" patcher_app.py
```

`installer-data`는 배포용 번역/글리프/HUD 수정 자료입니다. 전체 게임 플러그인이나
API 키, 개인 설정, 작업 로그는 저장소에 포함하지 않습니다.

## 출처

- 원본 모드팩: [Star Wars Genesis](https://genesismodlist.com/)
- 번역 도구 및 SST 형식 참고: [xTranslator](https://github.com/MGuffin/xTranslator)
- 한글 글리프: [Pretendard](https://github.com/orioncactus/pretendard), SIL Open Font License 1.1.
  [라이선스 전문](docs/Pretendard-LICENSE.txt)

Star Wars Genesis 및 원본 게임/모드의 공식 배포물이 아닌 한국어 패치 프로젝트입니다.
