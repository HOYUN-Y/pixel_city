# 개발 안내

서울 도심의 실제 건물·도로·지형 공간데이터를 바탕으로 만드는 아이소메트릭 픽셀 지도입니다.

프로젝트의 목표는 공간데이터로 도시의 위치와 구조를 구성하고, 이미지 모델로 지붕·창문·수목·거리의
픽셀아트 표현을 보강합니다. 완성된 지도 위에는 관광지, 문화재, 지하철과 보행 경로 같은
정보를 실제 좌표에 맞춰 표시하는 것입니다. prototype2의 현재 그림 지도는 실측 정합 미검증 상태입니다.

> 최신 기준: 2026-09-22. [명소 탐색](LANDMARK_DISCOVERY.md), [고밀도 지도](DENSE_CITY.md), [배포 환경](DEPLOYMENT.md)을 구분해서 확인하세요. 소스 메인 통합은 웹 재배포나 지도 품질 승인을 뜻하지 않습니다.

## 프로토타입

| 구분 | 목적 | 현재 상태 |
|---|---|---|
| [prototype1](../prototype1/poc/README.md) | V-World 건물·도로·지형을 규칙 기반 픽셀 지도로 렌더 | 서울 도심 6,991동, DEM 지형, POI·지하철 레이어 뷰어 구현 |
| [prototype2](../prototype2/README.md) | AI 그림 지도에 명소 탐색·도감을 결합 | 고밀도 배경 24조각, 명소 8곳 연결(건물 6·위치 안내 2). 로컬 검증 완료, 지리 정합·신규 배포는 미승인 |

`prototype1`은 공간데이터와 규칙 기반 표현의 기준선이고, `prototype2`는 고정된 입력
스냅샷을 사용하는 독립 실험입니다. 최신 결과와 제한은 [prototype2 상세 안내](../prototype2/docs/GUIDE.md)와
[진행 상태](../prototype2/PLAN.md)에 기록합니다. README는 진입 링크와 최소 실행법만 유지합니다.

## 로컬에서 보기

```bash
# prototype1 뷰어: http://127.0.0.1:8765/
cd prototype1/web
python3 serve.py

# prototype2 비교 뷰어: http://127.0.0.1:8766/eval/diorama/
cd ../..
python3 -m http.server 8766 --bind 127.0.0.1 --directory prototype2
```

기존 [객체형 지도](http://127.0.0.1:8766/web/pilot/?view=objects)는 저장소에 포함된 소형 데모 에셋으로
바로 열린다. API 키나 로컬 AI 모델이 필요 없다. 건물 클릭 후 좌하단 **지도 검수**에서 숨김·복원·
창문 점등과 보행 마커를 조작한다. [AI 에셋 6종 비교](http://127.0.0.1:8766/assets/object_pilot/)에서
미채택 후보도 확인할 수 있다. 기존 2×2 이미지 시험은 `/web/pilot/`에 보존했으며 로컬 생성물이 필요하다.

## 검증

Python 환경은 `prototype2/requirements.lock.txt`를 사용하며, Node 검증은 **Node.js 24.x**를 기준으로 한다. 로그인 셸이 다른 Node 버전을 선택한다면 먼저 `node --version`을 확인한다.

새로 받은 저장소에는 `prototype2/work/`, 원본 캡처·관광 수집본·배포 환경 파일이 없다.
최신 실지도는 [명소 문서](LANDMARK_DISCOVERY.md)의 로컬 산출물이 있는 환경에서만 열린다.
코드 계약 검사는 저장소 파일과 합성 데이터로 실행하며, 실제 로컬 자료가 필요한 통합 검사는 자료가 없으면 사유를 표시하고 건너뛴다. 자동으로 AI 생성·수집·배포를 실행하지 않는다.

```bash
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests -p 'test_*.py'
prototype2/.venv/bin/python -m unittest discover -s scripts -p 'test_*.py'
node --test prototype2/tests/test_*.mjs
node prototype2/tests/test_viewer.cjs
prototype2/.venv/bin/python prototype2/scripts/freeze_inputs.py
prototype2/.venv/bin/python prototype2/scripts/diorama_map.py validate
```

V-World API 키는 환경변수로만 주입하며 저장소에 포함하지 않습니다. 데이터·모델·이미지
이용조건은 [prototype2/LICENSES.md](../prototype2/LICENSES.md)에 정리했습니다.

`.agents/`와 `skills-lock.json`은 로컬 설치 도구로 보존하되 추적하지 않는다. 관광 수집 스크립트는 `scripts/`, 기획은 `docs/planning/`에 두며 수집 원본 위치는 [TourAPI 문서](planning/tourapi-collection.md)를 참고한다.

2026-09-22 통합 전 검증: 스테이징한 파일만 별도 임시 폴더에 내보내 Python 158개(로컬 자료 필요 6개 skip), Node 21개, 관광 수집 모의 테스트 9개를 확인했다. 유료 호출·웹 재배포 없이 수행했으며 로컬 캡처/생성물 없이도 일반 계약 검사가 통과한다.
