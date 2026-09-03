# prototype2 CHANGELOG

> prototype2 안에서 일어난 일만 기록한다. 최신이 위.
> 프로젝트 전체 기록은 [`docs/WORKLOG.md`](../prototype1/docs/WORKLOG.md)에 있고, 여기와 섞지 않는다.
> 무엇을 검증할지는 [README.md](README.md), 어떤 순서로 태울지는 [PLAN.md](PLAN.md).

---

## 2026-09-04 — S1 1차 결과: 미완결로 중단. 원인은 축척, 다음은 txt2img

**생성 15장** (`outputs/candidates/`), 대조 시트 2장 + 오버레이 9장 (`eval/`).
장당 30~90초 / Mac MPS. **판정 미완 — 시간 때문에 중단했다.**

### 무엇이 나왔나

| 구간 | 축척 | 강도 | 결과 |
|---|---|---|---|
| 광역 (700×670m) | 0.899 m/px | 0.35 | 구조 완벽, 변화 거의 없음 |
| 광역 | 0.899 m/px | 0.55 | 수목 생김. 건물은 그대로 |
| 광역 | 0.899 m/px | 0.75 | 수목 더 생기고 색이 틀어짐(자주빛). 북촌 밀집이 나무 덩어리로 뭉갬 |
| 근정전 확대 (220×222m) | **0.376 m/px** | 0.55 / 0.75 | **거의 무변화. 상자가 상자로 남음** |

retention(원본 라인 유지율)은 **0.74~0.84**로 강도와 무관하게 높았다.
**구조 보존은 문제가 아니었다. 미감이 안 올라온다.**

### 두 가지를 배웠다

1. **광역에서는 축척이 물리적 한계다.** 0.9 m/px면 한옥 한 채가 17px이다.
   17픽셀에 창문을 그릴 수 있는 모델은 없다. 늘어난 디테일이 전부 수목이었던 이유다.
2. **확대해도 안 됐다는 게 더 중요한 발견이다.** 근정전이 150px인데도 기와지붕이 안 생겼다.
   → 축척은 필요조건이었지 충분조건이 아니다. **진짜 원인은 img2img 구성**으로 보인다.
   초기 latent가 그 평평한 렌더라 모델이 원본 색·면을 못 벗어나고,
   ControlNet 0.75가 그 위에서 한 번 더 묶는다.

### 다음 한 수 (착수했으나 미완)

**txt2img + ControlNet** — 라인아트로 구조만 잡고 색·질감은 처음부터 그리게 한다.
`s1_edit.py --mode txt2img`로 구현해 뒀고, 0장에서 중단했다.

```bash
prototype2/.venv/bin/python prototype2/scripts/s1_edit.py \
  --inputs prototype2/inputs_zoom --tag _t2i --mode txt2img --strengths 0.5,0.8
```

**이게 PLAN §3에 정해 둔 "조정 2회" 중 두 번째다.** 여기서도 기와지붕이 안 나오면
PLAN §5대로 S1을 중단하고 prototype1 트랙에 시간을 넣는다. 판정은 사람이 한다.

### 코드 변경

- `s1_edit.py`에 `--inputs` / `--tag` / `--strengths` / `--mode` 추가.
  구간·모드를 바꿔 돌려도 결과가 안 섞인다.
- contact sheet가 `--limit`로 줄여 돌리면 IndexError 나던 버그 수정.
- `inputs_zoom/` 추가 — 근정전 확대 구간 조건 이미지
  (`--bbox 126.9755,37.5772,126.9787,37.5800`, 0.376 m/px).

## 2026-09-04 — 저장소 재편 대응 (`poc`/`web`/`docs` → `prototype1/`)

- 다른 세션이 저장소를 `prototype1/` + `prototype2/`로 갈랐다. `conditions.py`의 경로가 깨졌다.
- **한 일**: `conditions.py`에 `P1 = ROOT/prototype1` 한 줄을 넣어 `poc`·`web/data`를 다시 찾게 했다.
  `PLAN.md`·`CHANGELOG.md`의 상대 링크도 `../prototype1/docs/...`로 고쳤다. 재실행해서 동일 산출 확인.
- prototype1 뷰어에 픽셀화 토글이 붙고 `style.json`에 `pixel_size: 3`이 생겼다(2-A 완료).
  조건 이미지는 아직 이 격자를 쓰지 않는다 — **S1에서 픽셀 격자는 모델이 만들어야 할 것**이라
  입력을 미리 픽셀화하면 판정이 흐려진다. 채택 후 필요하면 그때 반영한다.

## 2026-09-04 — 격리 venv 사용 (`prototype2/.venv`)

- **문제**: anaconda base가 이미 깨져 있다. `scipy 1.13.1`은 numpy 1.x 빌드인데
  `numpy 2.2.6`이 설치돼 있어 `numpy.core.multiarray failed to import`가 난다.
  diffusers가 스케줄러에서 scipy를 타고 들어가 곧바로 걸린다.
- **한 일**: base를 고치지 않았다. **사용자의 다른 작업을 깨뜨릴 수 있어서다.**
  대신 `prototype2/.venv`(homebrew python 3.13)를 만들고 torch·diffusers를 여기에만 깐다.
  `.gitignore`에 이미 들어 있다.
- **실행 명령이 바뀐다**: `prototype2/.venv/bin/python prototype2/scripts/s1_edit.py`
  단, `conditions.py`는 PIL만 쓰므로 anaconda로도 돈다.

## 2026-09-04 — S1 실행 환경: 로컬 SDXL + ControlNet 선택

- **결정**: GPU 대여 전에 **Mac(MPS) 로컬 SDXL + ControlNet으로 먼저 판정**한다.
  PLAN.md §1은 Qwen-Image-Edit(20B)을 위해 GPU 대여를 선행 조건으로 봤는데,
  S1이 답해야 할 질문("도로가 살아 있으면서 디테일이 느는가")은 **더 싼 모델로도 답이 나온다.**
  여기서 실패하면 대여 자체가 불필요하고, 통과하면 그때 Qwen으로 화질을 올린다.
- **환경**: Mac15,8 / RAM 128GB / torch 2.13 MPS 사용 가능. `diffusers`·`accelerate` 추가 설치.
- **감수하는 것**: SDXL 화질이 Qwen-Image-Edit보다 낮다. 라이선스도 Apache 2.0이 아니라
  CreativeML Open RAIL++-M이다 — **LoRA 학습을 하지 않으므로 출력물 이용에는 문제가 없지만,
  최종 채택 시에는 Qwen으로 재생성해 [CONCEPT §8-B](../prototype1/docs/CONCEPT.md)의 "전 과정 Apache 2.0"
  서사를 유지한다.** 이 판정용 출력물은 제출 문서의 근거 자료로만 쓴다.

## 2026-09-04 — P2-0 / P2-1 완료 · 실행 계획 분리

- **한 일**: 조건 이미지 생성기 [`scripts/conditions.py`](scripts/conditions.py) 작성.
  경복궁 대표 구간 하나에서 `base_rgb` / `edge` / `height` / `mask` 네 장을 같은 카메라로
  뽑고, 재투영용 `camera.json`을 같이 쓴다. 실행 계획은 [PLAN.md](PLAN.md)로 분리했다.

  ```bash
  /opt/anaconda3/bin/python prototype2/scripts/conditions.py          # 경복궁 1024²
  /opt/anaconda3/bin/python prototype2/scripts/conditions.py --check  # 골든값 대조만
  ```

- **핵심**: **`prototype1/web/data/*.json`만 읽는다.** V-World 키도, 삭제된 원본 WFS 캐시도 필요 없다.
  `prototype1/poc/export.py`가 이미 델타 인코딩·페인터 정렬을 해뒀기 때문에 그대로 되읽으면 된다.
- **렌더러 삼중화를 피했다**: 투영은 `prototype1/poc/iso2.py`를 import 한다. 매 실행마다
  `prototype1/web/data/meta.json`의 골든값 5건과 대조하는 자체 검사가 돌아 포팅 드리프트를 잡는다.
- **네 장의 은면 처리가 일치한다**: 같은 폴리곤을 같은 순서로 네 캔버스에 칠한다.
  덕분에 `edge.png`가 **은선 없는 깨끗한 라인아트**로 나온다 (ControlNet lineart 바로 입력 가능).
- **검증**: 결과가 `prototype1/poc/gyeongbok.png`와 전각 배치·한옥 밀도까지 일치. 네 장 크기 동일 자동 검사.
- **height 보정**: 대부분 건물이 3~15m라 선형 정규화(HMAX=60m)면 전부 검게 뭉쳐 sqrt 곡선을 썼다.
- **카메라**: `126.9740,37.5760,126.9820,37.5820` (경복궁~삼청동 약 700×670m) /
  방위 22.5° · 고도 30° / 1024² / **0.899 m/px**. 상수는 `prototype1/poc/style.json`에서 읽는다.
- **계획에서 잘라낸 것** (근거는 [PLAN.md](PLAN.md) §0):
  - **P2-5 인접 2×2 타일 — 뺀다.** Isopolis 원저자도 못 푼 문제고 D-14에 걸릴 자리가 아니다
  - **P2-6 LoRA — 하지 않는다.** 09-09 판정이 아니라 지금 못박는다
  - **P2-2 모델 2~3종 비교 — 1종으로 시작.** A가 통과했을 때만 B를 본다
  - 목표 산출물을 "전역 지도 교체"에서 **"제출 문서에 실을 대표 장면 1장 + 흐름도"**로 바꿨다.
    제출물이 문서이므로 README §8의 착지점 2·3이 처음부터 현실적이다.
- **건드린 파일**: `scripts/conditions.py`(신규), `PLAN.md`(신규), `CHANGELOG.md`(신규),
  `.gitignore`(신규), `inputs/**`(생성물), `README.md`.
  **prototype2 밖은 건드리지 않는다.**
- **다음 일**: S1 단일 컷 판정 — 강도 3단계 × seed 3개 = 9장.
