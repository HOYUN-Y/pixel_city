# 모델·데이터·출력 이용조건

확인일: 2026-09-12. 실제 배포 전 링크의 최신 원문을 다시 확인한다.

## 현재 로컬 판정 경로

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

현재 활성 경로는 완전 로컬 전용이다. 외부 GPU·유료 이미지 API·Qwen 계열 모델은 사용하지
않는다. SDXL은 전체 지도를 다시 그리지 않고 반복 재질 뱅크를 생성하는 데만 사용한다.

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
- 제3자 스타일을 직접 복제하도록 지시한 이미지나 권리가 불명확한 참조 이미지는 사용하지 않는다.
