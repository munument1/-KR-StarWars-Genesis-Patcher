# 제네시스 모드 플러그인 괄호 병기 전수 검수

기준: Genesis 8.8.32 / 2026-10-08.

## 범위

- **검수:** 모드 플러그인 140개에서 사용하는 번역 레시피 37,235개 위치.
- **제외:** 본편 및 공식 DLC 기반 Strings 13개, 본편·DLC 보충 Strings 26개. 이들은 검수·변경 대상이 아닙니다.
- **제외:** 폰트, HUD, BAT, 비번역 바이너리.

## 결과

독립적으로 폭넓게 수집한 괄호 내 한글·영문 혼용 후보 **185곳**의 원문·번역·필드 위치를 비교해 판정했습니다.

| 판정 | 개수 | 근거 |
|---|---:|---|
| 영문 중복 병기 제거 | **14곳** | 같은 명칭·동작을 한글과 영어로 중복 표기 |
| 그대로 유지 | **171곳** | 약어, 식별자, 코드, 게임 변수, 함선 종류·등급, 설명·요약·버그 신고 안내, 영문 참조 절 제목 |

### 수정 제안의 예

- `저장(SAVE)` → `저장`
- `재시작(RESTART)` → `재시작`
- `함선 상인 프레임워크(Ship Vendor Framework)` → `함선 상인 프레임워크`
- `림(Rim)` → `림`
- `록(The Rock)` → `록`
- `exertion(노력)` → `노력`
- `꺼짐(OFF)` → `꺼짐`

### 유지 예

- `STAP(1인용 정찰 플랫폼)`, `BARC(바이크 정찰 코만도)`: 스타워즈 공식 차량·조직 약어와 풀이.
- `X-윙 (S) 원자로 (C)`, `Blurrg-1120 (개조형)`: 함선·장비 등급과 개조형 정보.
- `CAPS(완전 자동 조종 시스템)`: 약어의 의미 설명.
- `최소(Min)`: 타 설정에서 참조하는 실제 옵션 이름.
- `데이터 손상 대처 방법(Dealing with Corruption)`: 영문 README에서 찾을 섹션 이름.
- `실험 1B (이 문구를 보았다면 신고하세요)`: 개발자의 버그 신고 안내.
- `<Global=...>`, `<Alias=...>`, UI/게임 변수, `ISB`·`CIS` 등의 고유 약어.

## 자료

- [`decisions.json`](decisions.json): 185곳 전체의 위치·기존 문맥·수정 또는 유지 판정·이유.
- [`scripts/audit_genesis_parentheses.py`](../../scripts/audit_genesis_parentheses.py): 고확률 병기 후보 추출. 본편/DLC Strings 검사에서 제외.
- [`scripts/audit_genesis_parentheses_broad.py`](../../scripts/audit_genesis_parentheses_broad.py): 약어·코드까지 포함하는 넓은 후보 추출.
- [`scripts/validate_parentheses_review.py`](../../scripts/validate_parentheses_review.py): 전수 후보 185곳과 판정 내역 일치 검증, 원문/플레이스홀더/줄바꿈 검사 후 **적용하지 않는** 번역 변경안 JSON 생성.

```powershell
python scripts/audit_genesis_parentheses.py --self-test
python scripts/audit_genesis_parentheses.py --repo . --out candidates.csv --summary-json summary.json
python scripts/audit_genesis_parentheses_broad.py --repo . --out all-candidates.csv
python scripts/validate_parentheses_review.py --repo . --overlay reviewed-overlay.json
```

## 배포 주의

**현재 브랜치의 변경은 검수 판정 및 변경 제안이며, 실행 패처 번역·설치 데이터에 실제 반영된 상태가 아닙니다.** 레시피를 무작정 바꾸면 SHA-256 결과 검증과 구버전 갱신 절차가 깨질 수 있습니다. 실제 적용을 위해서는 제네시스 원본 플러그인으로 전체 결과를 재생성하고 입출력 해시, 이전 버전 업그레이드, 설치·복원 검증, 새 EXE 빌드가 필요합니다.

사람이 직접 플레이 검증한 것으로 표시하지 않습니다.
