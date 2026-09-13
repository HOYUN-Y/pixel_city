# Gate 1 — SDXL txt2img + ControlNet 판정

판정일: 2026-09-12
판정: **실패 — 전체 타일 생성 금지**

## 실행

- 모델: `stabilityai/stable-diffusion-xl-base-1.0`
- 모델 리비전: `462165984030d82259a11f4367a4eed129e94a7b`
- ControlNet: `diffusers/controlnet-canny-sdxl-1.0`
- ControlNet 리비전: `eb115a19a10d14909256db740ed109532ab1483c`
- 구간: `inputs_zoom`, 1024×1024, 약 0.376m/px
- 조건 강도: 0.5, 0.8
- seed: 1, 2, 3
- 생성시간: 80~262초/장, Mac MPS
- RGB SHA-256: `4a03c63792b839e91b9fc08c29457191ffabe0169d4519a10e8692a8498ce9c6`
- edge SHA-256: `d2ea6e4c9f1e50b6cf9717b40967a5f6730c0432bdd19110575d16be1acfb130`

## 결과

| 결과 | recall | precision | F1 | edge density |
|---|---:|---:|---:|---:|
| st080 seed3 | 0.937 | 0.107 | 0.192 | 14.79× |
| st080 seed2 | 0.972 | 0.105 | 0.189 | 14.79× |
| st050 seed3 | 0.999 | 0.091 | 0.168 | 23.84× |
| st080 seed1 | 0.979 | 0.089 | 0.164 | 15.94× |
| st050 seed2 | 0.987 | 0.088 | 0.161 | 22.25× |
| st050 seed1 | 0.999 | 0.084 | 0.155 | 24.19× |

미감과 픽셀아트 밀도는 기존 입력보다 명확히 좋아졌다. 그러나 전각 수·형태·배치와 빈 마당이
대량으로 바뀌었고, 없는 탑·정원·군중이 생성됐다. 같은 장소라고 설명할 수 없으며 주요 객체
추가·삭제 0건 기준을 충족하지 못한다.

기존 retention(recall) 단독 지표는 과도하게 많은 생성 경계도 정답 경계 근처에 걸리는 결함이
있었다. 이후 판정은 precision, F1, 원본 대비 edge density와 육안 구조 검사를 함께 사용한다.

## 다음 조치

SDXL txt2img 추가 튜닝은 하지 않는다. 외부 CUDA GPU에서 Qwen-Image-Edit-2511에 base RGB와
edge를 함께 제공해 seed 3개를 평가한다. 해당 게이트가 통과하기 전에는 96개 전체 생성을 실행하지 않는다.
