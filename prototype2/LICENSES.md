# 모델·데이터·출력 이용조건

지도·모델 조건 최초 확인일: 2026-09-12. API 시험/폰트 기록 갱신: 2026-09-14.
실제 배포 전 링크의 최신 원문을 다시 확인한다.

## 2×2 시험 GUI 추가 사항 (2026-09-14)

- 사용자 승인으로 덕수궁 VWorld 캡처의 인접 crop 4개와 기존 화풍 참고를 OpenRouter/OpenAI에
  전송해 4회 생성했다. 이전 단일 후보 승인과 별도로 승인된 시험이며 자동 추가 생성은 금지한다.
- GUI는 로컬 정적 파일만 읽고 키/입력 폼/사진을 외부로 보내지 않는다. 지도 출처와 AI 재해석,
  실측 정합 미검증 표기를 유지한다. 생성물·참고 이미지의 공개 배포 권한을 판정한 것은 아니다.
- 시안용 사진/카드 영역은 표시된 그라디언트 예시다. 실제 사용자 게시물이나 관광 정보로 제공하지 않는다.
- NeoDunggeunmo 1.601, Pretendard 1.3.9는 공식 원본 폰트를 수정 없이 로컬 제공한다.
  저작권·SIL OFL 1.1 전문, 고정 출처와 SHA-256은 `web/pilot/fonts/LICENSE.txt`와 README에 포함한다.

## 현재 로컬 판정 경로

- Q8 시험은 `unsloth/Qwen-Image-Edit-2511-GGUF`의 Q8_0 배포본을 사용한다.
  원본 Qwen의 부속 모델은 기존 캐시를 재사용하며 모델 파일을 저장소에 포함하지 않는다.
  배포 출처: https://huggingface.co/unsloth/Qwen-Image-Edit-2511-GGUF

- `Qwen/Qwen-Image-Edit-2511`: 모델 카드 표기 Apache-2.0.
  공식 리비전 `6f3ccc0b56e431dc6a0c2b2039706d7d26f22cb9`를 로컬 시험에 사용한다.
  - 모델: https://huggingface.co/Qwen/Qwen-Image-Edit-2511
  - Isopolis의 별도 학습 LoRA나 지도 이미지는 다운로드·재사용하지 않는다.
- `stabilityai/stable-diffusion-xl-base-1.0`: CreativeML Open RAIL++-M.
  모델 제공자는 생성 출력에 대한 권리를 주장하지 않지만, 출력 사용자는 라이선스의
  사용 제한을 준수하고 결과 사용에 책임을 진다.
  - 모델: https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0
  - 라이선스: https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/LICENSE.md
- `diffusers/controlnet-canny-sdxl-1.0`: 모델 카드 표기 Open RAIL++.
  - 모델: https://huggingface.co/diffusers/controlnet-canny-sdxl-1.0

모델 ID와 실제 Hugging Face 캐시 리비전은 각 결과의 JSON 메타데이터에 기록한다.
판정용 결과와 최종 채택 결과를 구분한다.

## 실행 정책

기본 경로는 완전 로컬 추론 전용이다. 사용자의 모델 교체 요청에 따라 Qwen 단일 구역
편집 시험을 허용한다. 공식 가중치 다운로드와 외부 지도 조회는 외부 AI 추론과 구분한다.
SDXL의 이전 경로와 산출물은 보존한다. 예외로 2026-09-13 사용자 명시적 승인하에
덕수궁 지도 crop과 사용자 화풍 참고 두 장을 OpenRouter/OpenAI에 전송하여
`openai/gpt-image-2.5-sunburst` 후보 한 장을 생성했다. 별도 API 경로만 외부 추론을 사용한다.
API 결과는 공개 가중치 라이선스의 적용 대상으로 간주하지 않으며, 공개 배포 전 서비스 약관과
지도/참고 이미지 권리를 별도 확인한다. 이번 산출물은 로컬 검수용이며 공개 배포하지 않았다.

## 입력 데이터

초기 입력은 `prototype1/web/data/*.json`에서 `prototype2/inputs/snapshot/`으로 복사해 고정했다.
원본을 수정하지 않으며 후속 렌더는 스냅샷만 읽는다. `snapshot.json`과 `tile_manifest.json`에
입력 파일 SHA-256을 저장한다. 입력 해시가 달라지면 기존 생성
결과와 직접 비교하거나 이어서 생성하지 않는다. 공공데이터별 출처 표시와 원 약관은 최종 배포 전에
별도 데이터 출처표로 확정한다.

### VWorld WebGL 3D 시험 입력

- 공식 WebGL 3D API 3.0과 `facility_build` 레이어를 사용한다.
- 화면에 VWorld 로고를 유지하고 메타데이터에 서비스명·API 버전·캡처일을 기록한다.
- API 키와 캡처 원본은 저장소에 커밋하지 않는다. 공개 배포 전 최신 이용조건과 출처표시
  요구사항을 다시 확인한다: https://www.data.go.kr/data/3073144/openapi.do
- 카카오·네이버 로드뷰 이미지는 이번 생성 입력에 사용하지 않는다.

## 출력물 정책

- AI 배경은 공간데이터의 시각적 해석이며 실측 지도라고 표시하지 않는다.
- POI·지하철 좌표 레이어는 AI 이미지와 분리한다.
- 후보, 실패 사례, 프롬프트, seed, 모델 리비전과 실행시간을 보존한다.
- 디오라마에서 재사용한 로컬 SDXL 에셋 출처는 `assets/diorama/manifest.json`에 기록한다.
- 사용자 제공 게임 스크린샷은 로컬 화풍 검수·조건 입력으로만 사용한다. 농장 배치·캐릭터·
  건물 스프라이트를 추출해 지도 에셋으로 옮기지 않으며 원본을 Git이나 공개 사이트에 배포하지 않는다.
  이번 로컬 시험은 참고 이미지나 파생 출력의 공개 배포 권한을 판정한 것이 아니다.
