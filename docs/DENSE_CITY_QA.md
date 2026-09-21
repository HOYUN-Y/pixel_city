# 실제 24조각 지도 검증 — 2026-09-17

## 세종대로 배경 차량 제거 시험 — 후속

결과: **비교 시험 완료, 후보 미채택**. 기존 지도와 공개 배포는 유지한다. [3모드 비교 화면](http://127.0.0.1:8766/work/sejong-clean-road-20260919/)에서①기존 배경+이동 차량,②정리 배경만,③정리 배경+이동 차량을50%/100%로 비교할 수 있다. 종로 차량은 이 비교에 표시하지 않으며 기존 통합 지도에는 그대로 있다.

- 작업 범위: 최신 polish 배경에서 전역 `(1920,1408)`의1024×1024 crop, 세종대로 기존 시험 두 차선 주변. 차량·그림자29개 사각형 영역(차량 대수와 일치하지 않음), 합집합11,869픽셀을 생성 전에 고정했다. 주차장·보도는 제거 대상으로 삼지 않았다.
- 생성: 기존 OpenRouter/OpenAI `sejong_clean_road_20260919`1회,40.747초/$0.070209. 참조는 현재 그림과 제거 마스크2장. 이미지 생성 스킬의 원본 보존·참조 역할 명시·결과 육안 확인 절차를 사용했고, 실제 요청은 승인된 기존 API 원장을 재사용했다. 최종 프롬프트는 결과 폴더의 `authorization.json`, 기존 생성 폴더의 동명 `_intent.json`에 보존했다.
- 원출력은 마스크 밖 차량과 주변 표현까지 바꿨으므로 통째로 사용하지 않았다. 고정 마스크 내부만 합성하여 **마스크 밖 변경0픽셀**을 확보했다. 그러나 일부 수동 사각형이 차체·그림자 전체를 덮지 못했고, 생성된 노면/차선이 기존 픽셀과 경계에서 달라 잔상·패치 자국이 남았다. 이는 마스크의 한계와 모델의 주변 재해석이 함께 작용한 결과다. 보존 검사 통과를 시각 품질 통과로 간주하지 않았다.
- 생성 후 결과에 맞춰 마스크를 넓히거나, 넓은 도로 영역을 덮어쓰거나, 추가 유료 재시도를 하지 않았다. `candidateAccepted=false`, `userVisualApproval=false`, `reviewOnly=true` 유지. ②③은 미채택 후보의 문제 확인용이며 기본 화면은①이다.
- 검증: Python155/Node19 통과. PC1440×1000/모바일390×844에서3모드·50/100%·세종대로2대·속도32px/s·재생/정지 확인. 기존 배율별 타일75개가 새 배경의 해당 좌표/축소 결과와 정확히 일치했다. 차량 전체 주기 및9프레임 시트를 추가했다. 이 검사는 지도 전체 도로 정합이나 후보 미관의 통과가 아니다.
- 최신 비용: 누계31회, 확정$2.543542 + 과거 실패 미확정 예약$0.75 = 보수적$3.293542. 총$5/32회 한도 유지. repair3회 소진, replacement1회 잔여. 슬롯 전용·예산 증액은 하지 않았다.

산출물은 `prototype2/work/sejong-clean-road-20260919/`에 있다: `before.png`, `after.png`, `comparison.png`, `mask_review.png`, `frozen_mask.json`, `visual_review.json`, `report.json`, `snapshot/`, `qa/report.json`, `qa/1440_cycle.png`. 구현은 `sejong_clean_road.py`, 로컬 전용 `road-review.js`, 회귀는 `clean_road_browser_check.py`다. 원본 스냅샷이나 공개 API 형식은 변경하지 않았다.

### 향후 배경 생성 지침

움직이는 차량을 표시할 **주행 차도에는 원본에 차량이 있어도 차량과 차량 그림자를 제거하고 빈 노면을 생성**하도록 명시한다. “차량을 추가하지 말라”만으로는 원본 차량 보존을 막지 못한다. 주차장·주차 차량은 별도 구분하고, 차선·횡단보도·연석은 보존한다. 이 지침을 문서에만 추가했으며 완료된 기존 생성 작업의 프롬프트/출력은 소급 변경하지 않았다.

다음 보정은 차체·그림자 마스크 누락을 먼저 줄이고, 차선 보호/복원 방법을 정한 뒤 별도 승인 범위로 다룬다. 이번 미채택 결과를 전체 지도에 확장하지 않는다.

## 기존 그림 고도화 검수 — 2026-09-19

범위: 기존 그림 유지, 광화문 외관 비율, 보신각 선택/전경 투명도, 종로·세종대로 차량 통합. `prototype2/work/dense-polish-20260919/`의 `source/`와 `snapshot/`은 별도 출력이며 기존 검수본을 덮어쓰지 않았다. prototype1·공개 배포·커밋·푸시는 변경하지 않았다.

### 적용 결과

- **광화문**: 이미지 생성 스킬의 참조 역할 분리·원본 보존·결과 확인 절차를 적용하되 승인된 기존 OpenRouter/OpenAI 파이프라인을 재사용했다. 구조 원본/실루엣/스타일3장을 참조한 `gwanghwamun_polish_20260919`1회,64.654초/$0.078611. 넓고 낮은 이층 지붕·석축·3개 홍예, 고정 평행투영, 투명 배경을 명시했다. 최종 프롬프트는 `generation_authorization.json` 및 기존 생성 폴더의 동명 `_intent.json`에 있다. 원출력 보존 후 알파128 기준·균등 축소만 적용했다. 크기는102×85 →109×80px, 기준113×77 대비 너비−3.54%/높이+3.90%로 개선됐다. 내부 구조·실측 형상의 일치를 인증하지 않는다. 지면 하단1617px 유지, 광화문 신구 영역 밖 변경0픽셀.
- **보신각**: 기존 허용 마스크와 실제 앞 건물 윤곽을 분리했다. 가리지 않은 스프라이트는 선명하게, 앞 건물과 겹치는 영역만 반투명 합성한다. 선택 시200ms/45%, reduced-motion 즉시. 같은 명소를 다시 선택해도 수동 복원 상태를 덮어쓰지 않는다. 다른 명소/빈 지도/Escape는 복원, 모바일 패널 닫기는 유지. 작은 지도 마커는 숨겨진 건물을 찾기 위한 명시적 버튼이며 투명 영역을 클릭 대상으로 확장하지 않았다. 기존 추정 underlay·sprite 재사용, 보신각 추가 AI0회.
- **차량**: `jongno-*`/`sejong-*`4개 차선, 각1대. 종로 Y+26 최종 경로와 세종 기존 경로 유지. 차량별 버퍼(`lane:index`)로 동일 sprite를 사용하는 지역 간 덮어쓰기를 방지했다. `points` 꺾은선 거리 기반 이동을 지원하되 이번 경로는 직선이며 기존 start/end도 유지한다. 기존3개 전경 마스크는 종로 차선에만 적용. 독립 명소와 보신각 전경/스프라이트 가림을 추가하고 반투명 전경의 차량 가림 농도를 동일하게 연결했다.
- **배경 경계**: 배경 SHA `d48119ae3ace36efa645ed272808d6892675350a84ebfca9e562ebb776dc17a4` 유지. 기존24조각/38경계/15교차부 근거와 atlas를 재사용하고 보류4곳(`0_4–0_5`, `1_1–1_2`, `1_2–1_3`, `1_2–2_2`)을 재확인했다. 지붕·포장·식재의 원본 차이는 남지만 확정된 새 차도 단절이나 안전한 추가 생성 표적은 없었다. 기존 DP 소유권·광화문 바닥·숲 보정은 유지하고 새 워핑/블러/유료 배경 생성은 하지 않았다. **4곳 해결 완료라는 의미가 아니다.**

### 검사와 한계

- Python155개, Node19개 통과. PC1440×1000/모바일390×844 기본 및 고도화 전용 브라우저 검사 오류0. 비·도감·검색·모의 가이드(각2회, 실제 유료0회), 줌100% 상한, 타일503 대체 표시, 캐시48개 이하 확인. 통합본 캐시는PC45/모바일39개였다.
- 자동/수동 선택, 지도 마커, 패널 닫기 유지, 빈 지도 복원 확인. 보신각 합성은 허용 마스크 밖 변경0, 내부 변경15,620픽셀, 해제 시 원본 바이트 완전 복원. 200ms 전환과 반투명 차량 알파도 확인했다.
- 4대 전체 이동 주기·끝점 페이드·경계 횡단 확인. 최장 주기18.017705초, 표본 간 이동≤0.999249px. **차량의 보이는 알파 픽셀**을 기존에 독립적으로 고정한 종로 차도 윤곽과 대조했다. 한 viewport당 픽셀-시간 표본: 차도 안133,839 / 확정 밖0 / ±2px 경계 불확실8,961 / 검수 범위 밖426,020. 서로 다른 고유 픽셀 수가 아니다. 윤곽 바깥 지역과 윤곽 직사각형 끝은 미검수로 분류했다. 세종 및 종로 서쪽은 시각 주기 시트만 제공하며 수치 차도 통과로 세지 않았다. `roadPassed=false` 유지.
- 보신각의 가려진 바닥은 AI 추정이며 실제 가림 관계·높이는 미검증이다. 반투명 보기 자체의 미관은 사용자 확인 전이다. `visualAcceptance`는 과거 `acceptance`와 별개이고 `geometryPassed=false`, `userVisualApproval=false`, `reviewOnly=true`를 유지한다. 기존 배포 게이트를 낮추지 않았다.

### 결과 파일과 재검증

- `index.html`: 통합 로컬 지도. 주소 <http://127.0.0.1:8766/work/dense-polish-20260919/>.
- `before.png`, `after.png`:4608×3072 전체 비교. `gwanghwamun_before.png`, `gwanghwamun_after.png`:3배 확대 비교.
- `polish-qa-final/1440_reveal.png`: 보신각 합성 원본. `390_auto_bosingak.png`: 모바일 상호작용 화면. `1440_jongno_cycle.png`, `1440_sejong_cycle.png`: 지역별9프레임 주기 시트.
- `report.json`: 입력 SHA·광화문 비율·원장 비용·보류 목록. `browser/browser_qa.json`, `browser/city-regression/`, `polish-qa-final/polish_qa.json`: 기능/픽셀 검사.
- `generation_authorization.json`: 이번 승인 범위와 최종 프롬프트. 원장은 `dense-city-20260916-source/report.json`을 그대로 사용했다. 누계30회/확정$2.473333/과거 미확정 예약$0.75. 새 실패 없음. 남은2회(대체1, 보정1)는 사용하지 않았다.

```sh
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests -p 'test_*.py'
node --test prototype2/tests/test_*.mjs
prototype2/.venv/bin/python prototype2/tests/dense_browser_check.py --snapshot prototype2/work/dense-polish-20260919/snapshot --dest prototype2/work/dense-polish-20260919/browser-recheck --full-regression
# 기존 prototype2 로컬 서버8766이 실행 중일 때
prototype2/.venv/bin/python prototype2/tests/polish_browser_check.py --url http://127.0.0.1:8766/work/dense-polish-20260919/ --dest prototype2/work/dense-polish-20260919/polish-recheck
```

`dense_polish.py`는 이미 존재하는 source/snapshot 재출력을 거부한다. 생성 준비 옵션을 재실행하거나 새 유료 호출을 자동 재시도하지 않는다. 아래 절은 이전 단계 기록이다.

## 최신: 도로 의미 검수와 종로 차량 경로 수정

결과 폴더: `prototype2/work/dense-roads-20260917/`.
**종로타워 앞 보도·광장을 지나는 차량 경로를 수정했다. 배경 변경0픽셀, 추가 AI 호출0회, 공개 배포 변경 없음.**

### 확인한 문제와 수정

- 24조각 개요와 원본/결과의 38개 접합부·15개 교차부를 직접 대조했다. 53개 영역 중 차도 노출29, 일반 차도 없음7, 가림/대응 불명확17로 기록했다. 영역 수는 독립 도로 수가 아니다.
- 이번 검사에서 새로 보정해야 할 **명확한 배경 도로 단절은 확인하지 못했다.** 이는 모든 도로의 위치·폭이 정확하다는 뜻이 아니다.
- 실제로 확인된 문제는 종로 역방향 차량의 직선 경로가 종로타워 앞 보도·광장과 북쪽 도로 가장자리를 지나던 점이다. 양쪽 차선·연결 보행 시험 경로를 화면 Y축으로26px 옮겼다. 차량 간격·속도32px/s·직선 경로 형식은 유지했다. 지리 좌표나 지도 자체를 이동한 것이 아니다.
- 먼저20px 이동한 검수본에서는 차도 밖 표본은 없어졌지만 경계 근접61개가 남았다. **보정 전에 고정한 도로 윤곽을 바꾸지 않고** 경로만6px 더 안쪽으로 조정했다. 중간 후보도 보존했다.
- 현재 그림의 보이는 차도를 직접 따라 만든 윤곽과 ±2px 판독 여유를 기준으로, PC/모바일 각각455개 차량 중심 표본이 모두 차도 안에 있었다. 같은 시각의 이전 경로는 차도 안66·밖285·경계 불확실104였다. 나머지707개는 해당 윤곽 검수 범위 밖이므로 통과로 세지 않았다.
- 이 검사는 **현재 그림의 선택 차도 구간과 차량 중심점**의 관계다. 차량 전체 부피 충돌, 서쪽 건물 뒤 실제 도로, 지도 전체 지리 정확도 인증이 아니다. 기존 전경 건물3개 가림 마스크는 유지했다. 세종대로 경로는 변경하지 않았다.

### 원본 정합의 남은 한계

- `dense_roads.py`는 그림 전체 유사도 대신 명시한 도로 가장자리의 법선 방향 거리와 교차로 모서리 거리를 계산한다. 판독 여유를 포함해4px 이내일 때만 통과하며, 기준을 걸치거나 대응점이 보이지 않으면 보류한다.
- 기존8개 패치 검사와 실패 이력은 보존했다. 추가10개 도로 관찰점은5개 근사 대응·5개 대응 불가이며 **모두4px 승인 보류**다. 근사 판독에 둔 ±6px는 통계적 신뢰구간이 아닌 보수적 수동 판독 여유다. 세 구간의 도로폭도 양쪽 경계를 확정하지 못해 숫자를 억지로 만들지 않았다.
- 원본의 흐릿함·차량·식재·건물 가림 때문에 남은 불확실성을 AI 재생성으로 해결할 근거는 없다. 따라서 이번에는 유료 생성하지 않고 남은 보정 슬롯1회를 유지했다.
- `geometryPassed=false`, `all_roads_passed=false`, `reviewOnly=true`를 유지한다. 전체4px 정합 승인과 광화문 등 다른 미해결 조건을 우회하지 않았다. 사용자가 픽셀 검사를 대신 해야 한다는 의미도 아니다.

### 결과 보기

- [차량 경로 수정 전후](../prototype2/work/dense-roads-20260917/vehicle_center_before_after.png): 빨강=차도 밖, 초록=안, 노랑=경계 불확실. 최신26px 후보다.
- [검수 위치도](../prototype2/work/dense-roads-20260917/road_review_overview.png): 노랑=차도 노출, 초록=차도 없음, 분홍=가림/불명확. 색은 정합 합격 여부가 아니다.
- [최신 전체 미리보기](../prototype2/work/dense-roads-20260917/preview.png): 배경·랜드마크 그림은 이전 최종본과 동일하다. 차량 경로 수정은 정지 지도 그림에 포함되지 않는다.
- `jongno-v2-browser/1440_traffic_cycle.png`, `sejong-final-browser/1440_traffic_cycle.png`: 실제 렌더러와 해시 검증 타일로 생성한 한 주기9장 비교. 별도 실제 UI 스크린샷도 같은 폴더에 있다.
- **최종 검수 스냅샷:** `jongno-v2-snapshot/`, `sejong-snapshot/`. `jongno-snapshot/`은20px 중간 후보이므로 최신본으로 사용하지 않는다.
- `inputs.json`, `source_controls_frozen.json`, `annotations.json`, `road_review.json`, `road_corridor_frozen.json`, `1440_center_checks.json`, `report.json`에 입력 SHA·관찰 근거·범위·판정·잔여 제한을 보관한다.

### 테스트와 재현

- Python146개 / Node18개 통과. 새 도로 테스트8개는 법선/모서리 거리, 판독 불확실성, 가려진 대응점,53개 영역 목록, 입력 고정, 승인 보존, 차량 중심과 경계 구분을 다룬다.
- 종로 약18.018초·세종대로 약15.130초의 **한 주기 전체를 이동 간격1px 이하**로 검사하고, 순간 이동이 발생하는 반복 경계의 투명도도 확인했다.
- PC/모바일 각각 종로1,162개 차량 상태: 완전 가림438·부분138·노출586. 세종대로978개 상태는 모두 노출됐다. 차량 수가 아니라 시간별 검사 표본 수다.
- 양쪽 PC1440×1000·모바일390×844 통과, JS 오류0. 종로 도감·수집·검색·비·모의 가이드 전체 회귀 통과, 유료 가이드 호출0. 최대100% 확대, 코어 경계 통과,48개 캐시 한도, 타일503 대체 동작 확인.

```sh
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests -p test_dense_roads.py
prototype2/.venv/bin/python prototype2/scripts/dense_roads.py review --dest prototype2/work/dense-roads-20260917 --annotations prototype2/work/dense-roads-20260917/annotations.json
prototype2/.venv/bin/python prototype2/tests/dense_browser_check.py --snapshot prototype2/work/dense-roads-20260917/jongno-v2-snapshot --dest prototype2/work/dense-roads-NEW-browser --full-regression
```

## 이전: 차량 가림·보신각 윤곽·도로 보조 검수

결과 폴더: `prototype2/work/dense-occlusion-20260917/`.
**종로 시험 경로의 차량 가림 구현 및 PC/모바일 회귀 통과. 추가 AI 호출0회, 배포 변경 없음.**

### 차량 가림

- 현재 배경의 전경 건물3개 구역을 윤곽 마스크로 기록했다. 적용 차선을 명시해 다른 경로에 무조건 적용하지 않는다.
- `traffic.occluders`는 선택적 배열이며 각 항목은 `id`, 전역 `rect`, 크기가 일치하는 그레이스케일 `mask`, 적용 `lanes`를 가진다. 내보내기가 마스크를 복사하고 매니페스트 SHA에 포함한다. 잘못된 크기·범위·차선·파일을 거부한다. 필드가 없는 기존 스냅샷도 동작한다.
- 차량 크기의 오프스크린 캔버스에만 `destination-out`을 적용한다. 지도 자체·다른 차량·랜드마크를 지우지 않는다. 마스크를 벗어나면 원래 차량 픽셀이 복원된다.
- 실제 종로 경로를0~18초/0.25초 간격으로 검사했다. 각 화면에서 차량146개 상태 중 완전 가림55·부분 가림18·노출73을 확인했다. 이는 순간별 차량 픽셀 검사 횟수이며 차량 대수가 아니다.
- 세종대로의 동일 검사146개 상태는 모두 노출됐다. 종로 마스크가 다른 구역 차량을 잘못 가리지 않았다.
- `traffic_before_after.png`: 이전 벽면 위 차량 / 건물 뒤 가림 / 도로로 다시 등장 비교. 현재는 지정한 종로 시험 구역만 보정한 것이며 지도 전체 건물의 자동 깊이 처리는 아니다.

### 보신각

- 예전 지도에서 옮긴 마스크 대신 현재 이미지의 가리는 건물 윤곽을 직접 지정했다. 보신각 스프라이트 알파를 합쳐 목표 객체가 마스크 밖에서 잘리지 않게 했다.
- 기존 생성 지면을 재사용해 새 마스크 안에만 합성했고, 마스크 밖 배경 변경0을 확인했다. 반투명 비율과 선택/복원 동작은 유지한다.
- `bosingak_outline_comparison.png`에 현재 배경·이전 마스크·새 윤곽 후보를 나란히 저장했다. 수동 윤곽과 추정된 보신각 위치에 대한 시각 승인은 별도이며, 실측 형상 승인을 의미하지 않는다.

### 남은 경계4곳과 도로

- 경계4곳을 넓은 문맥으로 재확인한 추정 이동은 모두0px였다. 지붕 반복 패턴1곳, 궁궐 지면/식재3곳으로 분류했다. 그중 `[2304,1504]`는 보조 상관도0.498로 낮아 불확실성을 유지한다. 원래 실패 표본/기준을 덮어쓰지 않았다.
- 세종대로5곳·종로의 보이는 도로3곳을 선택해 원본/이전/최종을 비교했다. **이전 합성본 대 개선본은8곳 모두 이동0px, NCC≥0.759**로 확인했다.
- 하지만 **VWorld 원본 대 생성 최종본**의 NCC≥0.6·이동≤4px 기준은2/8곳만 충족했다. 식재·차선·차량 재해석으로 대응 신뢰도가 낮은 곳이 있으며, 이것을 모두 위치 오차로 단정하지도 통과로 처리하지도 않는다. 전체 도로의4px 정합은 계속 미승인이다.
- `geometry_review.json`, `road_controls_frozen.json`, `road_controls_comparison.png`에 검사 범위와 결과를 보관한다. 이번 단계에서 지도 배경·좌표는 수정하지 않았다.

### 테스트와 확인 경로

- Python138개 / Node18개 통과. 크기·차선·경로·해시 계약과 실제 Canvas의 부분 알파/복원 테스트를 추가했다.
- 종로·세종대로 모두1440×1000 / 390×844에서 이동·줌·차량 코어 경계 통과·타일 장애 대응 통과. 종로는 도감/수집/검색/비/모의 가이드 전체 회귀도 통과했다. JS 오류0, 실제 가이드 호출0.
- `jongno-browser/1440_traffic_start.png`, `jongno-browser/1440_traffic.png`, `jongno-browser/390_bosingak.png`: 실제 UI 증거.
- `jongno-snapshot/`, `sejong-snapshot/`: 별도 검수본. 원래 배경·기존 배포본은 보존했고, `reviewOnly=true` 및 실패한 배포 관문은 유지한다.

```sh
prototype2/.venv/bin/python prototype2/tests/dense_browser_check.py --snapshot prototype2/work/dense-occlusion-20260917/jongno-snapshot --dest prototype2/work/dense-occlusion-NEW-jongno --full-regression
prototype2/.venv/bin/python prototype2/tests/dense_browser_check.py --snapshot prototype2/work/dense-occlusion-20260917/sejong-snapshot --dest prototype2/work/dense-occlusion-NEW-sejong
```

아래는 이번 차량/보신각 보정 전의 경계 개선 이력이다.

## 최신: 경계 재조합 + 국소 AI 보정

광화문 시험 후 전체 **38개 경계·15개 교차점**의 비교 후보를 만들었다.
최신 결과는 `prototype2/work/dense-seams-20260917-final/` 아래이며 공개본은 교체하지 않았다.

- `preview.png` / `candidate.png`: 개선 전체 지도, 각각1536×1024 / 4608×3072.
- `gwanghwamun_comparison.png`: 기존/개선 비교. 광화문을 숨긴 배경에서도 제거 전 문루 잔상이 없도록 해당 구역을2_2 조각으로 고정했다. 문루 자체 비율은 이전 후보 그대로다.
- `forest_comparison.png`: 기존/재조합/허용 영역만 AI 합성/AI 원출력 비교. 마지막 원출력 전체는 채택하지 않았다.
- `report.json`: 입력 SHA, 마스크·문맥·프롬프트 위치, 비용, 표시 타일 재구성 검사.
- `browser/`: 개선본 실제 데스크톱·모바일 기능 회귀와 스크린샷. 검수본 `snapshot/`은 `reviewOnly=true`이고 기존 실패 승인 값을 유지한다.

### 방법 및 보존 검사

`dense_seams.py`는256px 겹침 안에서 RGB·윤곽 차이와 고대비 경계 비용으로 동적 계획법 접합선을 선택한다.
행·열 순서로 픽셀 소유권을 결정하고, 네 조각 교차부도 단일 소유권으로 합성한다.
원본 픽셀 좌표·색상 보정값은 고정하고 기하 변형을 하지 않는다. 기본 접합에는 혼합을 쓰지 않는다.
명시적으로 지정한 보호 구역은 한쪽 조각을 유지한다. **윤곽 비용은 건물 전체의 의미론적 보호를 보장하지 않는다.**

- 재조합: 변경1,410,848픽셀, 겹침 밖 변경0, 빈 영역0, 광화문 보호 소유권 일치.
- AI 보정: 숲의6,397픽셀 마스크만 허용, 안쪽4px 혼합. 실제 변경6,392픽셀, 마스크 밖 변경0.
- AI 원출력은 마스크 밖1,041,293픽셀도 변경했다. `imagegen` 지침의 보존 조건을 프롬프트에 명시했으나 준수되지 않아, 프로그램에서 영역 밖 픽셀을 제외했다.
- 1 / 0.5 / 0.25 해상도 표시 타일을 다시 이어 붙여 전체 이미지 축소본과 바이트 단위 일치를 검사했다.
- Python136개 / Node17개 통과. 신규 경계 테스트8개에는 결정성·차단된 경로·단일 소유권·교차점·후속 조각의 보호 영역 보존·보정 영역 밖 보존이 포함된다.
- 브라우저1440×1000 / 390×844 통과. JS 오류0, 캐시48/45, 타일503 주입8/4개 후 대체 배경 유지, 차량32px/s·코어 경계 통과, 최대100% 확대 제한 확인. 도감·수집·검색·비·모의 가이드 회귀도 통과했다.

### 시각 검수와 남은 제한

`dense-seams-20260917-full/`의38개 확대 비교와15개 교차점 비교를 검토했다.
광화문 주변의 넓게 섞인 잔상과 포장/식재 이음새가 줄었고, 숲 경계는 작은 보정 영역에서 연결 표현을 다듬었다.
다만 전체 지도에서 식재 표현·세부 색감 차이가 모두 사라졌다는 판정은 아니다.

- 기존 고정190패치를 **이전 최종 배경 대 새 재조합 배경**으로 비교하면34/38경계가 NCC≥0.6·이동≤4px였다. 이전 원시 조각끼리의32/38과 다른 검사이므로 직접적인 품질 상승 수치로 비교하면 안 된다.
- 보류4곳: `0_4–0_5`, `1_1–1_2`, `1_2–1_3`, `1_2–2_2`. 앞의 평평한 지붕 패치는 작은 문맥에서6.40px, 넓은 보조 문맥에서는0px/NCC0.957이었다. 원래 경고는 유지하며 사후 통과로 바꾸지 않았다. 나머지3곳은 지면/식재 표현 차이로 상관이 낮았다.
- 원래 구조 고정점을 최종 배경에 재검사하면17/24조각이 자동 후보 기준을 만족했다. 3조각은 고정점 문맥이 최종 지도 밖의 여백에 걸려 판정 불가, 4조각은 상관 신뢰도 미달이다. 이전 원시 조각의19/24 기록을 변경하지 않았다.
- **주요 도로 횡단 지점 전체의4px 측정은 미완료**다. 부분 패치 검사·육안 연결 확인을 전체 지리 정합 승인으로 취급하지 않는다.
- 차량 전경 건물 가림, 보신각 마스크, 광화문 비율 문제는 이번 작업 범위 밖이며 여전히 남아 있다. 새 공개 승인·배포·push/main 병합은 하지 않았다.

### 유료 호출

사용자가 선택한 기존 OpenRouter→OpenAI 경로로 `forest_seam_repair_1` **1회/$0.078711** 사용했다.
초기 샌드박스 시도는 읽기 전용 모델 메타데이터 조회에서 막혔고 유료 POST/intent 전에 종료됐다.
네트워크 권한 승인 후 실제 생성1회가 완료됐다. 자동 유료 재시도는 없었다.
총29회 시도, 확정 비용$2.394722, 과거 실패 예약$0.75 포함 보수적 합계$3.144722.
총$5/32회 한도 유지, 보정 슬롯은1회 남았다. 추가 생성 없이 비교본을 보관한다.
정확한 프롬프트와 입력은 기존 생성 폴더의 `generation_tasks.json` 및 `forest_seam_repair_1_intent.json`에 있다.

### 재현

```sh
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests -p test_dense_seams.py
prototype2/.venv/bin/python prototype2/scripts/dense_seams.py pilot --source prototype2/work/dense-city-20260916-source --dest prototype2/work/dense-seams-NEW-pilot
# pilot 비교를 직접 검수하고 report SHA를 연결한 review.json이 있을 때만:
prototype2/.venv/bin/python prototype2/scripts/dense_seams.py full --source prototype2/work/dense-city-20260916-source --dest prototype2/work/dense-seams-NEW-full --pilot prototype2/work/dense-seams-NEW-pilot
prototype2/.venv/bin/python prototype2/tests/dense_browser_check.py --snapshot prototype2/work/dense-seams-20260917-final/snapshot --dest prototype2/work/dense-seams-NEW-browser --full-regression
```

아래는 경계 개선 전 실제 지도 테스트 이력이다.

결론: **기능 테스트 통과, 시각 품질 관문 미통과. 신규 배포하지 않음.**
실제 AI 생성 지도와 독립 랜드마크 후보로 시험했다. 합성 진단 블록을 실제 결과로 대체해 보고한 것이 아니다.
이번 테스트의 유료 이미지/가이드 호출은0회이며 생성 비용 원장은 변경하지 않았다.

## 기능 결과

| 항목 | 결과 |
| --- | --- |
| Python 단위/통합 |128개 통과 |
| Node 전체 테스트 |17개 통과 |
| 실제 지도 데스크톱/모바일 |1440×1000,390×844 통과,JS 오류0 |
| 진입/이동/명소3곳/전체 보기 |통과 |
| 줌 |초기50%, 최대100%, 상한 확대 버튼 비활성화, 축소/전체 보기 통과 |
| 차량 |2대·32px/s·768px 생성 코어 경계 통과·정지/재생 통과 |
| 타일 장애 |일부 타일에503 주입, 저해상도 지도 유지·반복 요청 없음 |
| 캐시 |48개 제한, 세종대로 최종 데스크톱48/모바일44; 종로45/39 |
| 보신각 |표시/복원·명소 전환 시 해제 통과; 마스크 모양의 품질은 별도 |
| 도감/수집/검색 |명소8곳, 수집 후 새로고침 유지, 보신각터 검색 통과 |
| 날씨 |데스크톱·모바일 비 효과 접근/표시 통과 |
| AI 가이드 |모의 응답·HTML 삽입 방지·503 후 지도 유지 통과; 실제 유료 호출 없음 |
| 검수본 배포 방지 |`reviewOnly` 스냅샷 배포 거부 테스트 통과 |

줌 테스트 첫 강화 실행은100%에서 이미 비활성화된 버튼을 누르려다 타임아웃됐다.
앱 오류가 아니라 테스트 절차 문제였고, 버튼 비활성화를 확인하도록 바꾼 뒤 통과했다.
자동 UI 통과는 배경 건물 가림·경계 미감까지 통과했다는 뜻이 아니다.

## 확인된 시각 문제

1. **종로 차량 가림 실패 — 우선 보정 필요.**
   종로타워 앞 도로를 따라 두 생성 코어에 걸친 경로를 시험했다.
   도로 일부가 전경 건물에 가려지는데 차량은 건물 벽면 위에 그려진다.
   `dense-map.js`의 `drawTraffic`에는 배경 건물 가림 마스크 처리가 없고 배경/객체 뒤가 아닌 위에 그린다.
   이동 수학/속도/경계 통과는 통과하지만 종로 차량의 시각적 배치는 미통과다.
   원본 도로 위에 경로를 겹친 자료와 실제 브라우저 시작 화면을 보관했다.
   경로는 시험용이며 실제 차선이나 통행 방향을 검증한 것이 아니다.
2. **보신각 마스크 경계.**
   버튼 동작과 복원은 정상이나 추정 마스크가 건물 일부를 잘라 반투명 경계가 부자연스럽다.
   원본 기반 전경 건물 윤곽으로 다시 정해야 한다. 현재 공개 품질 승인 대상이 아니다.
3. **광화문 비율/겹침.**
   생성 문루가 원본보다 길쭉한 비율이다. 균등 축소 후보는 너비−9.73%/높이+10.39%이며 정확한 형상 승인은 아니다.
   `1_2–2_2`의 원시 겹침에는 광화문 제거 전/후 차이도 있어, 독립 객체를 숨겨 잔상이 없는지까지 보정 후 재확인해야 한다.
4. **배경 경계6곳.**
   경계38곳×고정5패치 비교에서32곳은 모든 패치가NCC≥0.6·이동≤4px였다.
   나머지6곳은 `1_1–1_2`, `1_2–1_3`, `1_2–2_2`, `2_2–2_3`, `2_3–3_3`, `3_0–3_1`이다.
   비교 이미지를 직접 검토했으며 식재 밀도/색·일부 도로 세부·광화문 제거 전후가 다르다.
   패치가 모두 도로는 아니며, 낮은 상관 자체가 실제 위치 오류의 증거는 아니다. 전체 도로4px 기준을 승인하지 않았다.
5. **구조5조각 확인 유보.**
   원래 고정점 검사19/24통과는 그대로 유지했다.
   저신뢰5조각에 더 넓은63×63 패치를 보조 비교하면 추정 이동은0~1.42px였다.
   하지만 `0_0`, `3_5`에는 여전히 낮은 상관이 남고, 다른 곳도 세부 식재/형상 검수를 대신하지 못한다.
   원래39×39 패치의 기준이나 고정점을 바꿔 사후 통과시키지 않았다.

세종대로의 실제 차량 경계 통과 지점은 별도 확인했다. 두 원시 겹침의 추정 이동0px/NCC0.7594로 해당 도로 패치 시험은 통과했다.

## 증거 파일

모두 `prototype2/work/dense-real-qa-20260917/` 아래 로컬 전용이다.

- `browser-v3/browser_qa.json`: 세종대로 차량·줌·타일 장애 시험.
- `browser-v3/city-regression/browser_qa.json`: 도감/수집/검색/비/모의 가이드.
- `browser-v3/1440_traffic.png`, `browser-v3/390_bosingak.png`: 실제 UI 화면.
- `jongno-browser/browser_qa.json`: 종로 차량 이동 기능 시험.
- `jongno-browser/1440_traffic_start.png`: 건물 위에 차량이 그려지는 시각 문제.
- `jongno_traffic_source_full.png`: VWorld 원본에 표시한 종로 시험 경로.
- `geometry_qa.json`: 경계190패치·저신뢰 구조점 보조 비교·선택 도로 패치.
- `snapshot/`, `jongno-snapshot/`: 실제 생성물을 쓰는 `reviewOnly=true`, `testFixture=false` 스냅샷.

## 재현과 안전장치

```sh
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests
node --test prototype2/tests/test_*.mjs
prototype2/.venv/bin/python prototype2/tests/dense_browser_check.py --snapshot prototype2/work/dense-real-qa-20260917/snapshot --dest prototype2/work/dense-real-qa-NEW --full-regression
prototype2/.venv/bin/python prototype2/tests/dense_browser_check.py --snapshot prototype2/work/dense-real-qa-20260917/jongno-snapshot --dest prototype2/work/dense-jongno-qa-NEW
```

`dense_snapshot.export(..., review_only=True)`는 `prototype2/work/` 아래에만 검수본을 만든다.
기존 `acceptance` 실패 값을 보존하고 매니페스트/빌드에 `reviewOnly`를 기록한다.
`city_release.py`는 검수본을 거부한다. 정식 내보내기의 품질 관문은 그대로다.
배포·푸시·실제 가이드 호출은 수행하지 않았다.

다음 변경 순서: 차량 배경 가림 → 보신각 윤곽 → 광화문 비율/잔상 → 경계6곳과 구조5조각 → 같은 실제 지도 회귀 재실행.
