# pixel_city

서울 도심의 실제 건물·도로·지형 공간데이터를 바탕으로 만드는 아이소메트릭 픽셀 지도입니다.

공간데이터로 도시의 위치와 구조를 정확하게 구성하고, 이미지 모델로 지붕·창문·수목·거리의
픽셀아트 표현을 보강합니다. 완성된 지도 위에는 관광지, 문화재, 지하철과 보행 경로 같은
정보를 실제 좌표에 맞춰 표시합니다.

## 프로토타입

| 구분 | 목적 | 현재 상태 |
|---|---|---|
| [prototype1](prototype1/poc/README.md) | V-World 건물·도로·지형을 규칙 기반 픽셀 지도로 렌더 | 서울 도심 6,991동, DEM 지형, POI·지하철 레이어 뷰어 구현 |
| [prototype2](prototype2/README.md) | 고정 도형과 API 생성 픽셀 에셋을 결합한 객체형 지도 시험 | 18개 객체·AI 6종 생성, 건물 윤곽 1/3 통과. 미감 검수 및 전체 확장은 보류 |

`prototype1`은 공간데이터와 규칙 기반 표현의 기준선이고, `prototype2`는 고정된 입력
스냅샷을 사용하는 독립 실험입니다. 두 경로의 현재 결과와 제한은 각 README에
기록돼 있습니다.

## 로컬에서 보기

```bash
# prototype1 뷰어: http://127.0.0.1:8765/
cd prototype1/web
python3 serve.py

# prototype2 비교 뷰어: http://127.0.0.1:8766/eval/diorama/
cd ../..
python3 -m http.server 8766 --bind 127.0.0.1 --directory prototype2
```

최신 [객체형 지도](http://127.0.0.1:8766/web/pilot/?view=objects)는 저장소에 포함된 소형 데모 에셋으로
바로 열린다. API 키나 로컬 AI 모델이 필요 없다. 건물 클릭 후 좌하단 **지도 검수**에서 숨김·복원·
창문 점등과 보행 마커를 조작한다. [AI 에셋 6종 비교](http://127.0.0.1:8766/assets/object_pilot/)에서
미채택 후보도 확인할 수 있다. 기존 2×2 이미지 시험은 `/web/pilot/`에 보존했으며 로컬 생성물이 필요하다.

## 검증

```bash
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests -v
node prototype2/tests/test_viewer.cjs
prototype2/.venv/bin/python prototype2/scripts/freeze_inputs.py
prototype2/.venv/bin/python prototype2/scripts/diorama_map.py validate
```

V-World API 키는 환경변수로만 주입하며 저장소에 포함하지 않습니다. 데이터·모델·이미지
이용조건은 [prototype2/LICENSES.md](prototype2/LICENSES.md)에 정리했습니다.
