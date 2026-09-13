# prototype2 상세 실행·실험 안내

서울의 건물·도로 배치를 유지하면서 외관을 선명한 픽셀 그래픽으로 재해석한다.
로컬 추론 이력과 명시적으로 승인된 OpenRouter 시험을 분리한다. 최신 시험은 이미지형 2×2 지도 위의
장소·경로·캐릭터·수작업 가림이다. 기존 객체형 지도도 보존하며 지도 조작 중에는 AI 호출을 하지 않는다.

## 최신 결과 — 연결·남산·캐릭터 시험 (2026-09-14)

- [덕수궁 시험](http://127.0.0.1:8766/web/pilot/?view=seam-lab&scene=downtown)
- [남산·타워 시험](http://127.0.0.1:8766/web/pilot/?view=seam-lab&scene=namsan)
- [원본·기존·문맥 연결·보정 비교](../eval/vworld/seam_lab/runs/20260913T173009999136Z/index.html)
- [전체 프롬프트·입력 해시·비용](../eval/vworld/seam_lab/runs/20260913T173009999136Z/report.json)
- [Git에 보존한 프롬프트·해시·비용·검증 기록](seam-lab-20260914.json)
- [보존 영역 및 실제 연결선 검증](../eval/vworld/seam_lab/runs/20260913T173009999136Z/verification.json)

실행 `20260913T173009999136Z`: **12회 / 579.191초 / $0.976156**. 승인된 한도를 모두 사용했으며
추가 생성·재시도·모델 우회는 하지 않았다. 네이티브 1024² 지도 8장, 덕수궁 경계 보정 2장,
남산타워 보정 1장, 공유 투명 캐릭터 1장이다. 요청 시간은 합계이며 구현·검수 시간은 포함하지 않는다.

### 결과 해석

- 덕수궁: 이웃 문맥과 강제 픽셀 보존으로 연결하고 경계 두 곳을 보정했다. 보정 전보다 단절이 완화된
  후보지만 도로가 노란 보행로처럼 바뀌고 수목·외관이 재해석되는 문제는 남는다. 완벽한 연결이나 실측 정합 통과가 아니다.
- 남산: 새 VWorld 캡처의 정상·능선·사면과 타워의 기둥·전망대·안테나가 읽힌다. 보정에서 타워 상단의
  불필요한 가로 돌출을 줄였다. 암벽·숲·원거리 주택은 AI 해석이며 정확한 지형 복원으로 볼 수 없다.
- 촬영 중심의 지형 높이는 약 251m로 조회됐다. 0m 고정 카메라 대신 지형 높이를 반영했다.
  VWorld 전체 `tilesLoaded`는 false여서 전경을 시각 검수한 범위만 사용했다. 원거리 텍스처는 거칠다.
- 미감 승인은 사용자 검수 대기다. Isopolis 전용 LoRA를 학습한 결과가 아니며 전체 서울로 확장하지 않았다.

### 생성·합성 구조

25% 겹치는 동일 원본 crop을 좌상→우상→좌하→우하로 생성한다. 원본·화풍·기존 결과를 얹은 문맥·
흑백 문맥 안내 이미지를 입력하고 남산에는 같은 원본의 타워 세부 crop을 추가한다.
마스크 전용 API 파라미터가 아니라 **참고 이미지에 의한 편집 유도**다. 이미 확정한 픽셀은 로컬 합성으로
보존하며 원래 격자(768px)와 실제 새 영역 경계(896px)를 모두 기록한다.

보정 후보의 지정 영역만 교체하고 바깥 픽셀은 유지한다. RGB 경계 차이는 진단값이며 건물·지형 연결의
합격 점수가 아니다. 지도 최초 8개 출력은 디코딩한 RGB 픽셀을 PNG로 보존했고, 보정·캐릭터 4개는
응답 원본 바이트를 보존했다. 캐릭터 원본 알파는 유지하고 런타임만 축소·이진 알파 처리해 광택 테두리를 줄인다.

### 조작과 제약

1. 좌하단 **지도 검수**에서 장면·비교 결과를 선택한다. 기본 최대 100%, 검수용 200%다.
2. 지도 핀 또는 장소 목록을 선택하면 상세 창/모바일 시트가 열린다. ‘지도에서 보기’로 이동한다.
3. ‘시험 코스’ 또는 ‘다음 장소’로 장면별 3개 지점을 확인한다.
4. ‘캐릭터 재생’은 45초 순환 경로를 따라 움직인다. 따라가기·일시정지·위치 슬라이더로 가림을 확인한다.

덕수궁 건물 2곳, 남산 타워 기단과 수목 2곳의 가림 윤곽을 수기로 지정했다. 경로 구간의 앞/뒤 정보로
캐릭터와 겹친 부분만 가린다. **고도·깊이를 추론한 것이 아니며 실제 길찾기나 보행 가능성을 보증하지 않는다.**
캐릭터는 동일 스프라이트 이동·좌우 반전·작은 상하 움직임이며 방향별 보행 프레임은 없다.
기본 자동 재생은 꺼져 있고 숨겨진 탭에서는 애니메이션을 중단한다.

가림·장소 데이터는 최종 후보의 해시에 고정되며 브라우저도 이미지 SHA-256을 검증한다.
원본/다른 후보 비교에서는 상호작용을 비활성화한다. AI 대화·업로드·방문 인증은 계속 미연결이다.

### 실행·검증·재현

README의 서버 명령은 저장소 루트에서 실행한다. 새 지도는 Git 제외 로컬 생성물이 필요하고,
없으면 명확한 오류를 표시한다. 새 checkout에서도 바로 보는 화면은 기존 객체 데모다.
원본과 타워 참고는 `prototype2/work/vworld/seam_lab/20260913T172824302822Z/`,
생성·합성·검수 파일은 `prototype2/eval/vworld/seam_lab/runs/20260913T173009999136Z/`에 있다.

다음은 **추가 과금 없는** 명령이다.
JavaScript 검증은 Node 22 이상을 사용한다. Node 20.15 환경에서는 `.mjs` 검증 명령에
`--experimental-default-type=module`을 추가한다(Node 24에는 해당 옵션을 넣지 않는다).

```bash
prototype2/.venv/bin/python prototype2/scripts/seam_lab.py publish --run 20260913T173009999136Z
prototype2/.venv/bin/python prototype2/scripts/seam_lab.py verify --run 20260913T173009999136Z
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests -p 'test_*.py'
node prototype2/tests/test_lab_core.mjs
prototype2/.venv/bin/python prototype2/tests/lab_browser_check.py --run 20260913T173009999136Z
```

새 생성 절차는 `capture`→원본 시각 검수→설정 해시 확인→`init`→`scene --scene downtown|namsan`→
`repair --scene ... --number ...`→`character`→시각 검수/가림 설정→`publish`→`verify`다.
외부 단계에는 `--allow-external`과 해당 환경변수 키가 필요하다. **이번 12회는 소진됐으므로 새 유료 실행은
별도 승인 대상**이다. 진행 중/실패 요청이 남거나 같은 이름을 다시 호출하면 중단한다. 동시 생성은 파일 잠금으로 막는다.
검수 설정은 특정 실행에 고정되어 새 결과에 자동 적용되지 않는다. 원본·모델·키·화풍 참고는 Git에 올리지 않는다.

## 보존한 결과 — 객체형 지도와 AI 에셋 6종 (2026-09-14)

- [객체형 지도 열기](http://127.0.0.1:8766/web/pilot/?view=objects)
- [생성 외관·기본 도형·반복 타일 비교](../assets/object_pilot/index.html)
- [실제 프롬프트와 비용](../assets/object_pilot/generation.json) · [장면 매니페스트](../assets/object_pilot/manifest.json) · [시각 검수 기록](../assets/object_pilot/review.json)

덕수궁 북측 18개 건물의 위치·윤곽·높이를 고정 스냅샷에서 가져왔다. 외관은 실제 벽면 복원이 아니라
사용자 화풍 참고에 따른 AI 재해석이다. 건물 4628(목조)·4577(저층)·4485(현대식)와
아스팔트·보도블록·궁궐 돌바닥을 **총 6회**, 추가 호출 없이 생성했다.

실행 `20260913T163032352584Z`: 요청 시간 합계 **234.937초**, 실제 비용 **$0.385141**.
OpenRouter / `openai/gpt-image-2.5-sunburst`, OpenAI 제공업체 고정, high, 1:1, 요청별 1장.
건물에는 도형 렌더와 화풍 참고 두 장, 바닥에는 화풍 참고 한 장만 전송했다. VWorld 캡처·GUI는 전송하지 않았다.

**윤곽 검사 1/3 통과, 미감 미승인.** 원입력 전체 알파 IoU는 현대식 0.9914, 저층 0.9180,
목조 0.8307이다. 사전 기준 0.95에 못 미친 두 건물은 지도에서 기본 도형으로 표시하고,
AI 원형은 별도 비교 화면에 남겼다. 원출력의 주변 광택/반투명 영역도 원본에는 보존한다.
채택 후보만 고정 도형 마스크 안으로 제한하며, 생성물의 경계를 맞추기 위한 비선형 변형은 하지 않는다.
바닥은 64² 아트픽셀로 BOX 축소했으며 3×3 반복에서 보도·돌바닥의 주기성이 보여 후속 검수 대상으로 남긴다.

### 객체형 화면에서 확인할 것

- 건물 클릭 또는 지도 검수의 건물 선택 → ID·스냅샷 높이·AI 적용 여부 표시. 목록 선택 시 해당 건물로 이동.
- 건물 숨김·복원 → 아래 바닥과 뒤 건물이 남는다. 선택과 가림은 같은 픽셀 깊이 버퍼를 사용한다.
- **#4485 창문 켜기/끄기** → 실제 후보의 창문 위치에 수기로 지정한 마스크 4개만 점등한다.
  다른 건물의 점등은 미연결이며 지붕의 밝은 픽셀을 창문으로 추정하지 않는다.
- 검수용 보행자 이동·위치 슬라이더 → 건물 앞뒤 가림을 확인한다. 확대된 마커이며 실제 사람 크기·경로 안내가 아니다.
- 기본 도형/AI 후보 전환, 바닥 윤곽, 25/50/100% 및 검수 200%. 카메라 회전은 지원하지 않는다.

장면은 512² 아트픽셀을 3배 표시한다. 모든 건물은 개별 RGBA·카메라 깊이 이미지·ID·배치 기준점을 가진다.
배경에 건물이 그려진 완성 이미지를 잘라 붙이는 방식이 아니다. 캔버스의 정적 합성은 상태 변경 시만 다시 만들고,
보행 마커만 프레임별 갱신한다. 숨겨진 탭과 reduced-motion 환경에서는 자동 애니메이션을 제한한다.
GUI 가이드·피드·업로드·시간대·날씨 등 기존 서비스 시안은 계속 미연결이다.

### 실행과 재현

소형 데모는 저장소에 포함되어 새 checkout에서도 아래 서버만 실행하면 된다.

```bash
python3 -m http.server 8766 --bind 127.0.0.1 --directory prototype2
```

`scripts/object_pilot.py prepare`는 오프라인 도형 입력만 만든다.
아래 `generate`는 **새 유료 최대 6회**이므로 별도 승인 없이 반복하지 않는다. 실패·중단 시 자동 재시도나
다른 모델/로컬 추론 우회는 없다. 원출력·입력·상세 기록은 Git 제외 `eval/object_pilot/runs/`에 보존한다.

```bash
prototype2/.venv/bin/python prototype2/scripts/object_pilot.py generate --allow-external
prototype2/.venv/bin/python prototype2/scripts/object_pilot.py build --run prototype2/eval/object_pilot/runs/20260913T163032352584Z
```

`build`는 기존 원출력을 재사용하며 API를 부르지 않는다. `--run` 생략 또는 미완료 생성은 데모를 덮어쓰지 않는다.
점등 마스크는 위 실행에 고정되어 새 후보에 자동 적용되지 않는다. 색·창문 구성의 미감 승인과 실제 외관 정합은 별도다.

```bash
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests -p 'test_*.py'
node prototype2/tests/test_viewer.cjs
node prototype2/tests/test_objects_core.mjs
prototype2/.venv/bin/python prototype2/tests/object_browser_check.py
prototype2/.venv/bin/python prototype2/tests/pilot_browser_check.py
```

테스트는 유료 호출을 모의 응답으로 대체하며 사용자 화풍 파일 없이 실행할 수 있다.
브라우저 QA는 Chromium의 데스크톱·태블릿·모바일 에뮬레이션이고, 실제 iOS/Safari 검증은 아니다.
공개 배포·전체 지도 확장은 하지 않는다. `prototype1` 실행 코드와 데이터에는 변경이 없다.

## 이전 결과 — 2×2 시험 지도 + 반응형 GUI (2026-09-14)

`docs/design`의 데스크톱/모바일 시안을 별도 정적 웹 GUI로 재구현했다.
기존 `/web/` 전체 지도는 보존하고 **새 화면은 `/web/pilot/`**이다.

```bash
python3 -m http.server 8766 --bind 127.0.0.1 --directory prototype2
```

- [로컬 GUI](http://127.0.0.1:8766/web/pilot/?run=20260913T154045571223Z)
- [합성 이미지](../eval/vworld/openrouter/seam_zoom/runs/20260913T154045571223Z/mosaic.png)
- [생성·검수 기록과 실제 프롬프트](../eval/vworld/openrouter/seam_zoom/runs/20260913T154045571223Z/index.html)
- [데스크톱 화면](../eval/vworld/openrouter/seam_zoom/runs/20260913T154045571223Z/gui_desktop.png) ·
  [모바일 화면](../eval/vworld/openrouter/seam_zoom/runs/20260913T154045571223Z/gui_mobile.png)

4회 요청으로 1024² 이미지 4장 생성. 가장자리 128px를 제외한 768px core를 합쳐 1536²로 구성한다.
단일 VWorld 원근 캡처에서 인접 crop 4개를 사용했으므로 다른 카메라 간 정합이나 7.8㎢ 전체 적용을
검증한 것이 아니다. 실제 요청 합계 **208.365초, $0.275348**, 자동 재시도/모델 우회 없음.
출력과 입력 이미지, 프롬프트, 해시, 비용·시간은 실행 폴더에 보존하며 Git에서는 제외한다.

**GUI 구현·조작 검증 완료 / 지도 연결 품질 불합격.** 중앙 지붕·담장·수목과 동측 도로에
불일치가 남는다. 흐리게 합성하거나 실패 영역을 숨기지 않았으며 전체 96조각 확장은 보류한다.
개별 화풍은 선명하지만 사용자 미감 승인과 실제 좌표 정확성은 별도다.

### GUI 동작 범위

- 첫 화면은 지도만 중심에 표시. 900px 이상은 플로팅 창, 미만은 모바일 하단 시트.
- 지도 드래그·휠·핀치·줌 버튼, 미니맵 위치 표시. 기본 12.5~100%, 검수에서만 200%.
- 좌하단 `지도 검수`: 원본/AI 전환, 조각 경계·검수점, 배율 비교, 기록 링크, 시안 상태 미리보기.
- 가이드/피드/도감/명소/올리기/엽서 창과 탭 이동은 가능. 예시 콘텐츠이며 실제 전송·저장·
  좋아요·댓글·방문 인증·파일 선택·업로드·AI 응답은 없다. 레이어·시간대·날씨도 미연결이다.
- 기존 경복궁 시안의 핀·경로를 덕수궁에 붙이지 않는다. GUI가 API 키나 외부 AI 서비스를 호출하지 않는다.
- 폰트는 NeoDunggeunmo 1.601/Pretendard 1.3.9 로컬 파일로 제공. 라이선스/출처는 `web/pilot/fonts/`.
- 원출력/타일이 없는 새 checkout에서는 미생성 안내가 정상이며 다른 지도로 자동 대체하지 않는다.

### 재현과 검증

아래 생성 명령은 **새 유료 4회 시험**이다. 이전 결과를 재사용하는 명령이 아니므로 별도 승인 없이 반복하지 않는다.

```bash
prototype2/.venv/bin/python prototype2/scripts/openrouter_style.py --mode seam-zoom --allow-external
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests -p 'test_*.py'
node prototype2/tests/test_viewer.cjs
prototype2/.venv/bin/python prototype2/tests/pilot_browser_check.py --run 20260913T154045571223Z
```

브라우저 검사는 로컬 임시 서버·Chromium을 사용한다. `--run` 생략 시 합성 테스트 패턴으로 검증하며
어느 모드도 AI 호출을 하지 않는다. 1440×900·1024×768·390×844, DPR 1/2/3, 줌 중심/상하한,
창 이동, 시트 전환, CSP, 외부 요청·제출 없음, 잘못된 run/타일 누락 오류를 검사한다.
모바일 핀치는 터치 이벤트 시뮬레이션이며 실제 iOS/Safari 기기 검수는 하지 않았다.

아래 내용은 이전 단일 후보/로컬 생성 경로의 이력이다. 최신 GUI·4조각 시험 범위는 위 항목을 따른다.

### 선택적 OpenRouter 비교 — 첫 후보 생성 완료

기본 지도 파이프라인은 위 로컬 정책을 유지한다. 별도 `scripts/openrouter_style.py`는
사용자가 요청한 API 비교용이며 `--allow-external` 명시가 필요하다. 실제 호출 전 지도 구역과
화풍 참고 두 장을 OpenRouter/OpenAI로 전송하는 것 및 유료 생성에 대한 명시적 승인이 필요하다.
키는 `OPENROUTER_API_KEY` 환경변수로만 읽는다. 로그/보고서에 키나 요청의 base64 본문을 남기지 않는다.
Sunburst/OpenAI 경로, high, 1:1, 한 장으로 고정하고 자동 재시도·제공업체 우회를 금지한다.
지원 옵션에 정확한 크기가 없어 원해상도를 보존하며 필요 시 비교본만 1024px로 정규화한다.
산출물은 `eval/vworld/openrouter/runs/`에 분리한다. 초기 호출은 승인 부족으로 차단됐고,
사용자의 명시적 외부 전송·유료 생성 승인 후 한 번 실행했다. 기존 Qwen 결과는 보존한다.

- [OpenRouter / 로컬 Qwen 비교](../eval/vworld/openrouter/runs/20260913T142830815903Z/index.html)
- 1024×1024, high, 단일 요청 56.428초, API usage 보고 비용 $0.068837.
- 원출력은 참고 픽셀 화풍에 더 가깝지만 수목·포장·차선 등 AI가 보완한 세부가 있다.
  실제 지도 정확성/사용자 미감 승인은 별도다. 전체 지도·웹 타일은 교체하지 않았다.

## 보존한 이력: Qwen 로컬 화풍 시험

현재 시험은 `--variant q8`이다. 기존 BF16 장기 실행은 중단하고 결과/가중치를 보존했다.
Q8_0 transformer 21.76GB만 추가 다운로드하며 기존 인코더 등을 재사용한다.
활성 파일 세트는 약 38.62GB이고, **전체 캐시 크기나 실행 메모리의 상한이 아니다**.
512px·4단계 호환성 확인 후 1024px·40단계 **seed 20260913 한 장만** 생성한다.
Q8에서는 두 번째 seed와 반복 재현을 실행하지 않는다. 속도 개선은 보장하지 않는다.

```bash
prototype2/.venv/bin/python -m pip install --no-deps gguf==0.19.0
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py qwen-prepare --variant q8
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py qwen-pilot --variant q8
```

[Q8 비교 화면](../eval/vworld/qwen/q8/index.html). Q8 파일의 고정 리비전·크기·SHA256,
2511의 `zero_cond_t=true`, 전체 transformer 키 일치와 양자화 상태를 확인한다.
실패 시 BF16/CPU/외부 GPU로 우회하지 않는다. 단계별 monotonic/wall 경과 시간을 구분하며
이 수치를 순수 GPU 연산 시간으로 해석하지 않는다. 아래 variant 생략 명령은 보존한 BF16 경로다.

2026-09-13 실제 시험: 다운로드/해시 검증은 완료했지만 GGUF의 추가 빈 보조 텐서
`__index_timestep_zero__`가 전체 키 검사에서 차단되어 로딩 전에 중단됐다.
해당 실행에는 Q8 후보가 없다. 후속 수정에서는 표식이 ComfyUI의 2511 식별용임을 확인하고,
정확한 이름/F32/형태 `[0]`/원소 수 0일 때만 메모리 내 사전에서 제외한다.
일반 가중치 1,933개의 키와 형태는 모두 검사하고, Q8 가중치가 로딩 후에도 보존되는지 확인한다.
원본 GGUF는 변경하지 않는다. 실제 후속 실행 상태는 최신 비교 화면의 보고서를 확인한다.

루트 `docs/design`의 모바일 디자인은 당시 향후 UI 기준이었으며 모델 입력으로 사용하지 않는다.
디자인의 지도 배경은 기존 경복궁 렌더와 동일하다. 이번에는 기존 덕수궁 구역을 유지하고
390px 화면의 건물/길/수목 가독성을 추가 검수한다. 앱 UI·가이드·피드·도감은 이번 범위가 아니다.
실행 중 `smoke_progress.json`, `seed_*_progress.json`에 단계별 시간과 메모리 샘플을 저장한다.

기존 SDXL RPG 시안은 사용자 미감 목표를 충족하지 못했다. 현재 원근 시점은 유지하며,
VWorld의 실제 외관 특징과 사용자가 제공한 픽셀 그래픽 참고를 서로 다른 입력으로 전달한다.
Qwen-Image-Edit-2511은 Isopolis와 같은 기반 모델이지만, Isopolis의 별도 학습 가중치를
사용하는 것은 아니므로 동일 품질을 보장하지 않는다. LoRA 학습과 전체 지도 확장은 하지 않는다.

```bash
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py qwen-prepare
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py qwen-pilot --region downtown
# 호환성 확인만 실행할 때:
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py qwen-pilot --smoke-only
```

- 설정: `configs/qwen.json`. 공식 모델 리비전을 고정하고 약 57.7GB를 `work/models/`에 받는다.
  `qwen-prepare`만 다운로드하며 추론은 오프라인·MPS·BF16이다. CPU/외부 서비스 fallback은 없다.
- 입력: 기존 `work/vworld/downtown_source.png`와 사용자가 제공한 참고 파일을 복사한
  `work/references/pixel_style.png`. 두 입력의 SHA-256이 다르면 실행하지 않는다.
- 덕수궁과 주변 저층 건물의 `(320,512)–(1088,1280)` 구역만 종횡비 왜곡 없이 시험한다.
  기존 문서의 해당 `downtown` 시안에 붙인 “광화문” 표기는 정확한 장면 식별이 아니었다.
- 512px·4단계 smoke 뒤 1024px·40단계 두 seed와 첫 seed 반복을 실행한다.
  원출력과 512px→1024px 최근접 확대본을 별도로 보존한다. 색상 제한·경계 덧그리기·
  중간값 필터·장식 합성은 적용하지 않는다.
- 진입점: [최신 Qwen 비교](../eval/vworld/qwen/index.html). 실행마다 별도 `runs/` 폴더에
  비교표·중첩 검수 화면·원출력·프롬프트·실행시간·샘플링한 MPS 메모리 기록을 보존한다.
  실패나 smoke 통과를 화풍 성공으로 표시하지 않으며 실제 결과 상태는 각 `report.json`을 확인한다.
- 미감과 구조는 별도 육안 검수 대상이다. 사용자 승인 전 기존 전체 지도나 웹 타일을 교체하지 않는다.

## 보존한 이전 경로: 대표 3구역 및 SDXL 시험

- [인터랙티브 비교](../eval/diorama/index.html): 경복궁·광화문/도심·남산 주변을 슬라이더로 비교
- [세 구역 비교표](../eval/diorama/comparison.png): 기본 기하 / 이전 prototype2 / 새 디오라마
- [검증 기록](../eval/diorama/report.json): 색 변화율, 반복 재현, 구조 마스크, 이음새 검증
- 기존 전체 지도 `work/fullmap/mosaic.png`와 웹 타일은 그대로 보존했다.
- **새 디오라마는 1,536×1,536px 대표 이미지 3장이다. 전체 96타일 적용은 사용자 승인 후다.**

이전 전체 지도는 파이프라인 완성 산출물이지 미감 목표를 달성한 최종본이 아니다.
새 미감은 따뜻한 지면, 청회색 기와와 용마루, 목조·단청, 용도별 창문·벽면,
녹지 군집, 좌상단 하이라이트와 짧은 접지 그림자로 구성한다.

## 로컬 AI와 공간데이터

이번 시안은 기존 Mac MPS 실행에서 만든 SDXL 재질 9종을 해시 검증 후 `assets/diorama/`에
고정해 재사용했다. 이번 리디자인에서 새로운 모델 추론은 실행하지 않았다. 원 프롬프트·seed·
모델 리비전·실행시간은 에셋 매니페스트에 남긴다. 재생성 명령도 캐시만 사용한다.

`inputs/snapshot/`에 city/layers/meta/poi, 투영 상수와 타일 매니페스트를 고정했다.
실행 중 prototype1 코드를 import하거나 데이터를 다시 읽지 않는다. 초기 복사 이후에는
스냅샷 해시 검증만 수행하므로 다른 세션의 prototype1 변경이 출력에 영향을 주지 않는다.

## VWorld 실제 외관 + 로컬 AI 시험

공통 벽면 패턴을 줄이기 위해 VWorld WebGL 3D 화면을 동일한 세 대표 지역에서 캡처하고,
건물별 색·대비·패턴 서명을 `object_id`와 연결하는 시험 파이프라인을 추가했다. 브라우저
페이지는 메모리에서만 제공되므로 키가 파일이나 명령행에 남지 않는다. VWorld 캡처는
외부 공간데이터 조회지만 AI 연산은 로컬 MPS/CUDA에서만 실행한다.

```bash
export VWORLD_API_KEY='발급받은-키'
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py probe
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py generate
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py validate
```

`probe`는 직교 카메라, 3D 타일 로드, 외관 확보율과 기존 기하 정렬을 확인한다. 기준을
통과하지 않으면 AI를 실행하지 않는다. 통과 결과는 `eval/vworld/comparison.png`에 기본
기하, VWorld 원본, 로컬 AI 픽셀 변환의 3열 비교로 생성된다. 원본 캡처와 파생 파일은
Git에서 제외하고 모델도 `local_files_only=True`로만 읽는다.

기존 마스크 재투영 시안의 외관이 지나치게 평평해 VWorld 광화문 장면 전체를 직접
픽셀화하는 경로도 구현했다. 상단 지도 라벨과 하단 UI는 AI 입력에서 제거하고 출처 표기를
별도 footer로 다시 붙인다. 2px·64색, 동일 seed에서 강도 0.25/0.35/0.45를 비교한다.

```bash
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py direct-pilot --region downtown
```

결과는 `eval/vworld/direct/comparison.png`이다. 과거의 “구조 기준 통과”는 이미지 경계와
전역 이동량의 대리 지표였으며, 개별 건물의 위치·형태 보존을 입증하지 않는다.
이전 기본 추천 강도 0.35는 최종 채택이나 사용자 미감 승인을 뜻하지 않는다.

### 생활형 픽셀 RPG 시안

Direct 결과보다 사진 질감을 더 줄이고 게임 배경처럼 읽히도록 광화문 장면을 384×384
논리 해상도, 4px 격자, 48색으로 다시 해석한다. 특정 게임 에셋은 복제하지 않고 따뜻한
생활형 RPG의 일반적인 색·형태 문법만 사용한다. 소형 사람·차량·가로수는 투명 레이어로
분리하며 주요 건물 경계는 결정적 후처리로 보강한다.

```bash
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py rpg-pilot --region downtown
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py rpg-finalize --region downtown
```

결과는 `eval/vworld/rpg/comparison.png`이며 **미감 미승인·현재 후보에서 제외**다.
강도 0.60의 경계 재현율 72.1%는 원본 경계를 덧그린 뒤의 수치다. 전역 이동 추정 0px도
개별 건물 이동이 없다는 뜻이 아니다. 반복 생성 동일성만 별개의 실측 결과로 보존한다.
별도 장식 레이어가 있어도 AI 프롬프트가 장식물을 허용했으므로 원출력에 장식이 없다는 보장은 없다.

건물·도로의 기본 마스크와 높이는 유지한다. 아트픽셀은 화면 3px이며 처마·그림자의 허용
범위는 원래 건물에서 최대 4 아트픽셀이다. 창문·기와·녹지는 미술적 패턴이다.
문화유산/공원 폴리곤이 겹치는 곳은 열린 마당으로 표현한다. 개별 수목·마당 포장의 실측
데이터를 확보했다는 뜻은 아니며, 지형의 실제 고저차 재구축도 이번 범위에 포함하지 않는다.

## 재현과 검증

저장소 루트에서 실행한다. 현재 세션의 `prototype2/.venv`를 사용한다.

```bash
prototype2/.venv/bin/python prototype2/scripts/freeze_inputs.py
prototype2/.venv/bin/python prototype2/scripts/diorama_map.py pilot
prototype2/.venv/bin/python prototype2/scripts/diorama_map.py validate
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests -v
node prototype2/tests/test_viewer.cjs
```

비교 HTML은 파일로 직접 열 수 있다. 로컬 HTTP로 보려면 다음 명령 후
`http://127.0.0.1:8766/eval/diorama/`를 연다. 기존 전체 지도는 `/web/`이다.

```bash
python3 -m http.server 8766 --bind 127.0.0.1 --directory prototype2
```

`diorama_map.py assets`는 기존 로컬 생성 결과를 에셋 폴더로 고정하는 명령이다.
SDXL 재질을 새로 생성하려면 `local_style.py generate`를 사용한다. 모델이 캐시에 없으면
다운로드하지 않고 실패한다. 승인 후 전체 생성 절차는 [PLAN.md](../PLAN.md)에 있다.

모델·데이터 이용조건은 [LICENSES.md](../LICENSES.md), 변경 기록은 [CHANGELOG.md](../CHANGELOG.md).
