# 명소 자유 탐색 — 2026-09-20

## 최신: 8곳 연결·탐색 안정화 — 2026-09-22

[최신 로컬 지도](http://127.0.0.1:8766/work/landmark-discovery-20260922/) · [격리 패키지 화면](http://127.0.0.1:8766/work/landmark-discovery-20260922/release-candidate/public/)

- 지도 연결 **8/8곳**. 독립 에셋 3곳, 배경 윤곽 선택 3곳, 위치 안내 2곳이다. **동상 2곳의 새 그림을 완성했다는 뜻은 아니다.**
- 세종문화회관은 고정 스냅샷 인덱스 3385의 본관과 VWorld `source_2_2.png`를 대조해 기존 그림의 본관 윤곽을 연결했다. 주변 예술동과 고층 건물은 제외한다.
- 세종대왕·이순신 동상은 각각 TourAPI 콘텐츠 1364932·1364975의 수집 좌표를 저장된 촬영 좌표계에 투영했다. 근처 지형 표본 높이를 사용한 근사 위치는 `[2350,1987]`, `[2556,2238]`이다. 원본 캡처의 광장/동상 배치와 대조했으나 현재 AI 외형은 미확인이다. `selectionMode: "location-only"`로 윤곽 강조 없이 위치 마커·주변 지도 썸네일을 표시한다. 위치 정밀도 승인이나 동상 복원이 아니다.
- 8개 도감 ID·저장 키 유지, 전체/수집함 필터와 빈 상태 추가. 미연결 카드/주변 장소 상세가 지도 선택 해제와 함께 비워지던 문제를 수정했다. 이전 5곳 검수본에서도 미연결 카드 3개는 설명을 읽을 수 있다.
- PC 상세창을 도감 메뉴 오른쪽으로 옮겨 메뉴를 가리지 않게 했다. 수집 버튼의 키보드 포커스, 패널 닫기 후 포커스 복귀, 모바일 40dvh/확장 시트를 검증한다. 낮은 확대율에서 겹치는 보조 마커는 숨기되 명소 목록에서는 모두 접근 가능하다. 선택된 마커를 우선한다.
- 배경·기존 타일·기존 독립 에셋은 그대로다. 동적 차량은 꺼져 있으며 배경 안의 차량 그림은 남는다. 유료 API/이미지 생성 0회, 배포·커밋·푸시·prototype1 변경 없음.

새 산출물 루트: `prototype2/work/landmark-discovery-20260922/`. `new-landmarks-evidence.png`는 본관 윤곽과 두 동상 안내 위치, `report.json`은 원본 SHA와 위치 근거다. 최종 로컬 패키지는 `release-candidate/`이며 앞선 `package*`/`release-local`은 검증 과정의 중간 후보다. 최종 패키지 테스트는 `candidate-browser/`, 기존 5곳 회귀는 `five-spot-regression/`, 키보드·저장소 실패는 `accessibility/`, 기존 보신각/차량은 `legacy-regression/`에 남긴다.

```sh
prototype2/.venv/bin/python prototype2/scripts/discovery_extension.py --dest prototype2/work/discovery-next
prototype2/.venv/bin/python prototype2/scripts/city_release.py --snapshot prototype2/work/discovery-next/snapshot --dest prototype2/work/discovery-next/release --local-review
prototype2/.venv/bin/python prototype2/tests/discovery_browser_check.py --public-root prototype2/work/discovery-next/release/public --dest prototype2/work/discovery-next/browser
```

`--local-review`는 로컬 실행용 파일 구성만 허용한다. 빌드 가드는 권리 승인 기록과 무관하게 공개 배포를 거부한다. 일반 배포 경로의 `reviewOnly` 거부/기존 acceptance 검사는 유지한다. 새 `experience: "discovery"` 매니페스트 값은 패키지에서도 명소 탐색 모드를 선택한다. JS import 누락을 검사하고 썸네일/JSON 해시를 확인한다.

검증: Python 158개·Node 21개 통과. PC 1440×1000/모바일 390×844에서 원본·분리 패키지·기존 5곳 회귀, 썸네일/타일 503, 수집함·저장 복원·저장소 차단, 키보드·드래그·핀치 및 보신각 픽셀 복원을 확인한다. 기능 검증과 시각/지리 정합 승인은 별개이며 `reviewOnly=true`, `geometryPassed=false`, `userVisualApproval=false`를 유지한다.

다음 공개 배포 전 남은 일: 사용자 시각 검수, 기존 도로/경계 품질 관문 해소 또는 별도로 합의된 시험 공개 정책, 해당 후보 SHA에 연결된 배포 결정. 이번 로컬 패키지는 이러한 결정을 대신하지 않는다.

아래는 2026-09-20의 5곳 구현 이력이다.

## 확인 화면

[로컬 지도 열기](http://127.0.0.1:8766/work/landmark-discovery-20260920/)

서버가 꺼져 있다면 저장소 루트에서 실행:

```sh
python3 -m http.server 8766 --bind 127.0.0.1 --directory prototype2
```

상단 **명소 5곳** → 광화문·근정전·경회루·보신각·종로타워 중 선택한다. 순서가 정해진 투어나 자동 방문 처리는 없다. 도감은 기존 8개 ID와 `pixel-city.collection.v1` 저장소를 유지한다. 선택과 수집은 별개이고 수집은 직접 버튼을 눌러야 한다.

## 구현 범위

- `dense-polish-20260919`의 배경·75개 타일·3개 독립 랜드마크·가림 자료를 그대로 복사했다. 미채택 차량 제거 후보는 사용하지 않았다.
- 근정전·경회루는 새 스프라이트가 아니라 기존 그림에 `spots[].hitPolygon`을 추가했다. 지붕·몸체만 선택하고 궁궐 전체·연못을 선택 영역으로 삼지 않는다. 3개 기존 독립 랜드마크의 알파 선택이 우선한다.
- 명소 목록·지도 클릭·도감에서 같은 상세 정보를 연다. 목록 이동은 상세창이 차지하는 공간을 제외하여 건물을 배치하고 확대는 100% 이하로 제한한다. 지도 직접 클릭은 카메라를 옮기지 않는다.
- 모바일 상세는 40dvh, 상단 손잡이로 확대/축소한다. 패널만 닫으면 선택 유지, 빈 지도나 Escape는 선택과 보신각 가림 해제를 함께 해제한다.
- 연결된 5개 카드에는 기존 그림에서 만든 160×100 썸네일을 제공한다. 종횡비는 유지한다. 보신각은 기존 전경 45% 합성을 사용하며 `AI 재구성·추정 배치`를 표시한다. 나머지 3개 카드는 `지도 연결 준비 중`이다.
- 근정전·경회루는 경복궁 TourAPI 상위 자료만 연결한다. 개별 장소 정보·운영시간·역사를 새로 검증한 것으로 표시하지 않는다.
- 새 화면에서만 동적 차량·보행 시험과 관련 버튼을 비활성화했다. 그림 안에 이미 그려진 차량은 유지된다. 기존 시험 화면의 차량은 바뀌지 않았다.
- 날씨 미리보기와 명시적으로 전송하는 AI 질문 기능은 유지한다. 선택 시 AI 질문을 자동 호출하지 않는다. 이번 작업의 생성/API 유료 호출은 0회다.

## 위치 근거와 한계

`prototype2/inputs/snapshot/city.json`의 이름 인덱스 1370(경복궁 근정전), 1126(경복궁 경회루), 기존 VWorld 캡처의 궁궐 배치를 대조했다. 현재 배경의 근정전은 타일 `1/3_2.png`, 경회루는 `1/2_2.png`에 있다. 실제 선택 윤곽은 현재 AI 그림 위에서 추적한 **이미지 좌표**이며 원본 지리 좌표와 정합됐다는 뜻이 아니다.

`prototype2/work/landmark-discovery-20260920/`:

- `index.html`, `snapshot/`: 독립 로컬 검수본 및 썸네일/해시.
- `palace-selection-evidence.png`: 두 건물 선택 윤곽 확인용 그림.
- `report.json`: 원본 SHA, 보존 에셋, 위치 근거, 비용과 미검증 상태.
- `browser/`: PC·모바일 명소/도감/실패 대체 화면과 테스트 결과.
- `legacy-regression/`: 기존 3개 명소/보신각/차량 회귀 결과.

`reviewOnly=true`, `geometryPassed=false`, `userVisualApproval=false`를 유지한다. 기존 경계·도로 정합 경고는 해결된 것으로 바꾸지 않았다. 배포·커밋·푸시와 prototype1 변경은 없다.

## 재현과 검증

```sh
# 기존 출력은 덮어쓰지 않는다. 새 폴더를 지정해야 재생성할 수 있다.
prototype2/.venv/bin/python prototype2/scripts/landmark_discovery.py --dest prototype2/work/landmark-discovery-review-new
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests -p 'test_*.py'
node --test prototype2/tests/test_*.mjs
prototype2/.venv/bin/python prototype2/tests/discovery_browser_check.py
```

브라우저 검증은 1440×1000 및 390×844에서 명소 5개, 가시영역 이동, 도감 저장 복원, 정적 건물 직접 선택, 드래그·모바일 핀치, 빈 영역 해제, 썸네일/타일 503 대체 표시, 캐시 48개 이하를 검사한다. AI 엔드포인트는 테스트에서 모의 처리하며 POST가 없음을 확인한다. 기존 보신각의 픽셀 복원 및 마스크 밖 변경 없음도 별도 회귀 테스트한다.

검증 결과: 기존 Python 155개 + 신규 스냅샷 계약 1개, Node 21개 통과. 새 PC·모바일 브라우저 검증 및 기존 polish 회귀 검증 통과. 기능 검증과 사용자 시각 승인은 별개다.
