# 도심 고밀도 확장 — 2026-09-16

상태: 렌더러 구현·원본 수집 완료. **2026-09-17 외부 전송 승인 완료, OpenRouter 가격 확인 HTTP503으로 생성 전 중단**. AI 생성·최종 통합·신규 배포는 미완료다. 현재 공개 배포는 기존 종로 2칸 버전을 유지한다.

## 승인한 범위

- 경복궁–광화문–종각 약1.65㎢: `[126.971,37.568,126.984,37.581]`.
- 정사영 방위22.5°·내려다보기30°, 100m당256px. 기존 그림을 확대하는 작업이 아니다.
- 건물 실루엣과 경계 여백을 포함한4608×3072px, 생성 코어768px의6×4구역.
- 생성 요청1024², 코어 둘레128px 문맥, 인접 요청256px 겹침.
- 독립 객체3곳: 종로타워·보신각 원출력 재사용 우선, 광화문 새 후보. 다른5곳 독립 제작은 다음 차수.
- 이번 이미지 예산 총$5, 호출 최대32회. 배경24·광화문1·보신각 재구성 배경1·조건부 기존 객체 대체2·국소 보정4.
- 과금 미확정/가격 확인 실패/예산 부족 시 중단. 자동 재시도·모델 변경·예산 증액 없음.
- 기존 AI 가이드의$1 영구 원장과 별개다. 이번 UI 시험은 가이드 유료 호출을 하지 않는다.

## 표시·통합 구현

- `city-dense-pilot` 별도 형식. 기존 공개본과 과거 장면은 변환 없이 기존 렌더러로 읽는다.
- 배경512px 표시 타일, 해상도1/0.5/0.25. 1152×768 저해상도 전체 배경을 먼저 로딩한다.
- 현재 화면을 우선하고 주변 한 줄은 남은 캐시 범위에서 읽는다. 동시 요청4, 디코딩 캐시 최대48개.
- 실패한 표시 타일을 반복 요청하지 않으며 저해상도 배경을 유지한다. 새로고침 시 다시 시도할 수 있다.
- 객체·히트·보신각 패치는 영역별 PNG와 전역 위치로 저장한다. 전체 크기 마스크를 객체마다 만들지 않는다.
- 광화문 중심50%, 최대100%, 전체 보기·미니맵·세 명소 바로가기.
- 도감 ID·36곳 관광자료·비 효과·가이드 서버는 유지한다. 실제 길찾기나 실측 복원으로 표시하지 않는다.

## 생성·배포 관문

1. 전체 원본의3D 로딩·범위·동일 투영을 확인한다. 깊이별100m=256±1px, 조각 공통점≤1px.
2. 첫 인접2장을 생성하기 전에 구조2점과 크기1개를 고정한다. 밀도·화풍·좌표·연결 검증 후 나머지를 생성한다.
3. 출력 구조 오차≤16px·너비변화±15%, 주요 도로 경계≤4px, 잘린 지붕·중복 객체·빈 영역 없음.
4. 보신각 고도·높이의 추정 상태는 별도로 유지한다. 기술 검증을 측량 정확도나 사용자 미감 승인으로 바꾸지 않는다.
5. `delivery.json`의 검수 기록이 충족되어야 `dense_snapshot.py`가 표시 타일을 내보낸다.
6. `city_release.py --snapshot <새 스냅샷>`은 매니페스트에 명시된 PNG와 정제 JSON만 복사한다.
   새 지도는 매니페스트 SHA를 `snapshotSha256`으로 사용자 지시 배포 기록에 연결한다. 권리 확인 완료는 아니다.
7. 검증용 합성 데이터에는 `testFixture=true`를 기록하고 배포를 거부한다. 실패·부분 결과로 현재 공개본을 교체하지 않는다.

## 현재 검증

- Python124개, Node17개 통과.
- 고밀도 렌더러: 데스크톱1440×1000·모바일390×844 진입, 이동, 세 명소 선택, 보신각 전환/복원, 타일 장애 후 배경 유지.
- 진단 데이터 시험에서 캐시 최대48개, 오류0, 유료 호출0.
- 기존 종로 배포용 UI의 도감·검색·날씨·차량·보신각·모의 가이드 회귀 통과.
- 위 UI 시험은 실제 AI 생성 결과의 품질 검증이 아니다.
- 진단 기록: `prototype2/work/dense-renderer-qa-20260916/`.
- 추가 진단: `prototype2/work/dense-renderer-qa-20260916-v2/`. 차량 시간 진행·명소별 화면·전체 보기 포함. 데스크톱 캐시48/모바일40개, JS 오류0. 의도적으로503을 반환한 타일은 저해상도 배경으로 대체했다.
- 기존 지도 회귀: `prototype2/work/dense-legacy-qa-20260916/`.

## 원본 확보와 생성 중단 기록

- 2026-09-17 사용자가 명시한 외부 전송 범위와$5 한도를 승인하여 재개했다. 첫 생성 전 최신 모델·가격 조회(`GET /images/models/openai/gpt-image-2.5-sunburst/endpoints`)가 HTTP503으로 실패했다. 이전 가격으로 우회하거나 자동 재시도하지 않고 중단했다. 유료 POST·예약 intent 생성 전 실패하여 누적0회/$0이다.
- 재개 기록: `prototype2/work/dense-city-20260916-source/resume-20260917.json`. 외부 전송 승인 자체는 해결됐으며, 현재 대기는 제공자 메타데이터 조회 실패다. 다음 재개 시 최신 가격·기능 확인부터 수행한다.
- 24개1024² 원본과4608×3072 합성 원본을 확보했다. 경복궁·광화문·종로타워의3D 자료를 시각 확인했다.
- 원본100m=256px, 공통점의 수학적 정렬 오차 최대`4.25e-9px`. 렌더링 LOD 차이 때문에 실제 겹침의 RGB 평균 차이는`0.024~5.133/255`이며, 생성 결과 연결 통과를 뜻하지 않는다.
- 첫 인접 후보는`background_2_2`와`background_2_3`. 각각 구조2점과 지붕 너비102.59px/145.77px를 생성 전에 고정했다.
- 2026-09-16 첫 유료 요청이 실행 전 자동 승인 검토에서 차단됐다. 로컬 지도·스타일 참조 이미지를 외부 OpenRouter로 전송하는 범위의 명시적 승인이 필요하다는 사유다. 우회하거나 재시도하지 않았다.
- **이번 이미지 요청0회, 비용$0.** 요청 intent·AI 결과 없음. 가이드 실호출도0회.
- 예정 전송처: OpenRouter API → OpenAI 제공자, `openai/gpt-image-2.5-sunburst`. 첫 요청 자료: `source_2_2.png`, 사용자 게임 스타일 참조`style.png`, 광화문 제거 마스크`gwang_remove_2_2.png`, 기존 지도 색상 참조`palette.png`, 고정 좌표가 포함된 프롬프트. API 키는 인증에만 사용하며 이미지·프롬프트에 포함하지 않는다.
- 전체 이미지 예산$5/최대32회는 유지하며, 첫2장 검수 전 후속22장 생성 금지도 유지한다. 승인 대기는 자료의 이용권이 확인됐다는 뜻이 아니다.
- 원본·프롬프트·검증점·스크립트 보관: `prototype2/work/dense-city-20260916-source/`(Git/공개 배포 제외). `source_full_preview.png`는 **AI 완성본이 아닌 원본 수집 미리보기**다.
- 첫2장 품질, 전체 경계, 독립 객체3곳, 실제 도로 차량 구간, 실제 결과 브라우저 검수·배포가 남아 있다. 이 관문을 통과한`delivery.json`은 아직 만들지 않았다.

## 재현

```sh
node --test prototype2/tests/test_dense_map.mjs
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests -p 'test_dense_snapshot.py'
prototype2/.venv/bin/python prototype2/tests/dense_browser_check.py --dest prototype2/work/dense-renderer-qa-NEW
# 실제 검수 완료 스냅샷이 준비된 뒤에만:
prototype2/.venv/bin/python prototype2/tests/dense_browser_check.py --snapshot prototype2/assets/city_dense --dest prototype2/work/dense-real-qa-NEW
prototype2/.venv/bin/python prototype2/scripts/dense_snapshot.py --source <검수완료자료> --dest prototype2/assets/city_dense
prototype2/.venv/bin/python prototype2/scripts/city_release.py --snapshot prototype2/assets/city_dense --dest prototype2/work/city-release-NEW --deployment-decision <지시기록JSON>
```

로컬 고밀도 진입점은 개발 서버의 `/?dense=1`이며, 실제 스냅샷이 준비되기 전에는 사용하지 않는다.
기본 `/`와 기존 공개 사이트는 기존 지도다. 원격 푸시·main 병합은 이번 범위에 없다.
