# 내장 자료 출처·배포 조건 확인

확인일: 2026-10-08. 권한이 없다고 단정한 목록이 아니라, 확보한 공개 조건과 추가 확인이 필요한 범위를 구분한 기록입니다. 크레딧은 허가 증빙을 대신하지 않습니다. [Nexus 제출 규정](https://help.nexusmods.com/article/28-file-submission-guidelines)

## 내장 내용

manifest의 185개 작업을 확인했습니다. 텍스트 레시피 153개(플러그인 140, Strings 13), 한글 글리프 레시피 3개, 전체 교체 파일 2개(UI 사전·BAT), 전체 보충 Strings 26개, HUD 배치 레시피 1개입니다. 보충 Strings 중 10개는 항목이 없는 빈 파일입니다. 모드 폴더 출처는 91개입니다.

플러그인 바이너리 전체를 배포하지 않는 구조이지만 레시피에는 원문과 기존 한국어 번역이 들어 있습니다. UI 사전·BAT는 완성된 교체 파일이며 보충 Strings는 전체 파일입니다. EXE 포장만으로 원문·번역·수정 권한 문제가 해결된 것으로 볼 수 없습니다. 사용자의 설치 원본을 요구하는 구조와 원문 포함 여부를 함께 설명해야 합니다.

## 핵심 확인 결과

| 자료 | 확인된 출처·조건 | 남은 확인 |
|---|---|---|
| Genesis 자체 자료(11114) | DeityVengy의 [원본 페이지](https://www.nexusmods.com/starfield/mods/11114)는 Strings만 번역하고 Genesis 업데이트 때 번역을 숨기는 조건을 명시합니다. 그 외 본인 자료는 개방되어 있다고도 설명하며 소유 구분은 연락을 권합니다. | 현재 ESM·UI·BAT·HUD 패처가 조건에 부합하는지 확인. 다른 제작자의 모드까지 일괄 허용된 것으로 해석하지 않음. |
| 이름/Strings 교체(9421) | DeityVengy의 [String Replacement Overhaul](https://www.nexusmods.com/starfield/mods/9421)은 원본 텍스트의 활용을 폭넓게 허용하는 작성자 지침이 있습니다. | 팀왈도 한국어 번역 재배포 조건은 별도. 본편 및 DLC별 번역 출처 대조. |
| 기존 한국어 번역 | 사용자가 팀왈도라고 확인했습니다. 레시피에 재사용한 한국어와 보충 Strings 26개를 포함합니다. | 공식 배포 안내의 정확한 버전·재사용·수정·재배포 조건 미확인. DLC/Creation 파일까지 모두 팀왈도인지 파일별 확인 필요. |
| Nasalization 기본 폰트 | IMVCIT의 [원본](https://www.nexusmods.com/starfield/mods/2163)은 수정과 자산 사용에 사전 허가를 요구합니다. | 원본을 포함하지 않고 사용자 파일에 한글 글리프만 추가하는 방식의 허용 여부 확인. Donation Points 제한도 명시되어 있으므로 활성화하지 않는 설정으로 준비. |
| Enhanced Dialogue Interface | Seb263의 [원본](https://www.nexusmods.com/starfield/mods/871)도 수정·자산 사용에 사전 허가를 요구합니다. | Enhanced Fonts.swf 글리프 추가 방식의 허용 여부 확인. 원본 파일은 배포하지 않음. |
| Pretendard 한글 글리프 | [Pretendard](https://github.com/orioncactus/pretendard) · Copyright Kil Hyung-jin · SIL OFL 1.1. [전문](../Pretendard-LICENSE.txt)을 ZIP에 포함했습니다. | 임베딩·수정 시 저작권 고지와 예약 이름 조건을 최종 대조. Pretendard 완성 폰트를 새 라이선스로 선언하지 않음. |
| xTranslator | [공개 저장소](https://github.com/MGuffin/xTranslator) · MPL-2.0. 도구 및 SST 형식 참고로 크레딧. 배포 EXE에 xTranslator 실행 파일·Pascal 소스는 포함되어 있지 않습니다. | 참고·포팅 범위를 개발 이력과 대조. 형식 참고만으로 전체 패처가 xTranslator 공식 배포물이라고 표기하지 않음. |
| 나머지 모드 | 설치 meta.ini에서 원본 링크를 추출했습니다. | [출처 목록](mod-sources.md)의 개별 수정·번역·재배포 조건은 아직 미확인. |

팀왈도 배포 공지 후보: [네이버 게시글](https://blog.naver.com/dhrgusdlrns4/223532045871). [배포 소식을 소개한 기사](https://quasarzone.com/bbs/qn_game/views/374257?commid=267044&cpage=1)의 원출처 링크로 찾았으며, 네이버 본문은 접근 제한으로 읽지 못했습니다. 후보 링크 발견을 재배포 허가 확인으로 처리하지 않았습니다.

## 배포 방식별 선택지

현재 묶음 그대로 배포하려면 위 공개 조건과 별도 허용 범위를 확인합니다. 제작자가 허용하지 않는 자료는 범위를 줄이거나, 사용자가 별도로 받은 원본·한국어 번역에서 로컬로 필요한 자료를 읽는 방식으로 바꿀 수 있습니다. 이 방식에서도 원 제작자의 패치·수정 조건은 확인해야 하며, 자동으로 허가가 해결된다고 단정하지 않습니다.

Genesis 업데이트가 확인되면 구버전 Nexus 파일/페이지를 숨기는 절차를 운영하고, 대응 버전 검사 후 공개합니다. 새 버전이 나왔다는 것을 Nexus 저장소 파일 버전만 보고 단정하지 않으며 공식 모드리스트 릴리즈와 대조합니다. 원 제작자 조건은 GitHub 공개 자료에도 적용 여부를 확인합니다.
