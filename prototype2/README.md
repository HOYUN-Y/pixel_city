# prototype2 — 서울 관광 디오라마

로컬 SDXL 재질과 규칙 기반 렌더러로 서울의 건물·도로 구조를 유지하면서 색채와 입면을
새로 표현한다. 외부 GPU/API는 사용하지 않는다.

## 현재 상태: 대표 3구역 구현 완료, VWorld 외관 시험 경로 추가

- [인터랙티브 비교](eval/diorama/index.html): 경복궁·광화문/도심·남산 주변을 슬라이더로 비교
- [세 구역 비교표](eval/diorama/comparison.png): 기본 기하 / 이전 prototype2 / 새 디오라마
- [검증 기록](eval/diorama/report.json): 색 변화율, 반복 재현, 구조 마스크, 이음새 검증
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

결과는 `eval/vworld/direct/comparison.png`이며 세 후보 모두 2px 분석 격자의 구조 기준을
통과했다. 기본 추천값은 외관 보존과 표현 변화의 중간인 강도 0.35다.

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
다운로드하지 않고 실패한다. 승인 후 전체 생성 절차는 [PLAN.md](PLAN.md)에 있다.

모델·데이터 이용조건은 [LICENSES.md](LICENSES.md), 변경 기록은 [CHANGELOG.md](CHANGELOG.md).
