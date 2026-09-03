# prototype2 CHANGELOG

> prototype2 안에서 일어난 일만 기록한다. 최신이 위.
> 프로젝트 전체 기록은 [`docs/WORKLOG.md`](../docs/WORKLOG.md)에 있고, 여기와 섞지 않는다.
> 무엇을 검증할지는 [README.md](README.md), 어떤 순서로 태울지는 [PLAN.md](PLAN.md).

---

## 2026-09-04 — S1 실행 환경: 로컬 SDXL + ControlNet 선택

- **결정**: GPU 대여 전에 **Mac(MPS) 로컬 SDXL + ControlNet으로 먼저 판정**한다.
  PLAN.md §1은 Qwen-Image-Edit(20B)을 위해 GPU 대여를 선행 조건으로 봤는데,
  S1이 답해야 할 질문("도로가 살아 있으면서 디테일이 느는가")은 **더 싼 모델로도 답이 나온다.**
  여기서 실패하면 대여 자체가 불필요하고, 통과하면 그때 Qwen으로 화질을 올린다.
- **환경**: Mac15,8 / RAM 128GB / torch 2.13 MPS 사용 가능. `diffusers`·`accelerate` 추가 설치.
- **감수하는 것**: SDXL 화질이 Qwen-Image-Edit보다 낮다. 라이선스도 Apache 2.0이 아니라
  CreativeML Open RAIL++-M이다 — **LoRA 학습을 하지 않으므로 출력물 이용에는 문제가 없지만,
  최종 채택 시에는 Qwen으로 재생성해 [CONCEPT §8-B](../docs/CONCEPT.md)의 "전 과정 Apache 2.0"
  서사를 유지한다.** 이 판정용 출력물은 제출 문서의 근거 자료로만 쓴다.

## 2026-09-04 — P2-0 / P2-1 완료 · 실행 계획 분리

- **한 일**: 조건 이미지 생성기 [`scripts/conditions.py`](scripts/conditions.py) 작성.
  경복궁 대표 구간 하나에서 `base_rgb` / `edge` / `height` / `mask` 네 장을 같은 카메라로
  뽑고, 재투영용 `camera.json`을 같이 쓴다. 실행 계획은 [PLAN.md](PLAN.md)로 분리했다.

  ```bash
  /opt/anaconda3/bin/python prototype2/scripts/conditions.py          # 경복궁 1024²
  /opt/anaconda3/bin/python prototype2/scripts/conditions.py --check  # 골든값 대조만
  ```

- **핵심**: **`web/data/*.json`만 읽는다.** V-World 키도, 삭제된 원본 WFS 캐시도 필요 없다.
  `poc/export.py`가 이미 델타 인코딩·페인터 정렬을 해뒀기 때문에 그대로 되읽으면 된다.
- **렌더러 삼중화를 피했다**: 투영은 `poc/iso2.py`를 import 한다. 매 실행마다
  `web/data/meta.json`의 골든값 5건과 대조하는 자체 검사가 돌아 포팅 드리프트를 잡는다.
- **네 장의 은면 처리가 일치한다**: 같은 폴리곤을 같은 순서로 네 캔버스에 칠한다.
  덕분에 `edge.png`가 **은선 없는 깨끗한 라인아트**로 나온다 (ControlNet lineart 바로 입력 가능).
- **검증**: 결과가 `poc/gyeongbok.png`와 전각 배치·한옥 밀도까지 일치. 네 장 크기 동일 자동 검사.
- **height 보정**: 대부분 건물이 3~15m라 선형 정규화(HMAX=60m)면 전부 검게 뭉쳐 sqrt 곡선을 썼다.
- **카메라**: `126.9740,37.5760,126.9820,37.5820` (경복궁~삼청동 약 700×670m) /
  방위 22.5° · 고도 30° / 1024² / **0.899 m/px**. 상수는 `poc/style.json`에서 읽는다.
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

## 2026-09-04 — 격리 venv 사용 (`prototype2/.venv`)

- **문제**: anaconda base가 이미 깨져 있다. `scipy 1.13.1`은 numpy 1.x 빌드인데
  `numpy 2.2.6`이 설치돼 있어 `numpy.core.multiarray failed to import`가 난다.
  diffusers가 스케줄러에서 scipy를 타고 들어가 곧바로 걸린다.
- **한 일**: base를 고치지 않았다. **사용자의 다른 작업을 깨뜨릴 수 있어서다.**
  대신 `prototype2/.venv`(homebrew python 3.13)를 만들고 torch·diffusers를 여기에만 깐다.
  `.gitignore`에 이미 들어 있다.
- **실행 명령이 바뀐다**: `prototype2/.venv/bin/python prototype2/scripts/s1_edit.py`
  단, `conditions.py`는 PIL만 쓰므로 anaconda로도 돈다.
