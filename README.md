# pixel_city

서울 도심의 실제 건물·도로·지형 공간데이터를 바탕으로 만드는 아이소메트릭 픽셀 지도입니다.

공간데이터로 도시의 위치와 구조를 정확하게 구성하고, 이미지 모델로 지붕·창문·수목·거리의
픽셀아트 표현을 보강합니다. 완성된 지도 위에는 관광지, 문화재, 지하철과 보행 경로 같은
정보를 실제 좌표에 맞춰 표시합니다.

## 프로토타입

| 구분 | 목적 | 현재 상태 |
|---|---|---|
| [prototype1](prototype1/poc/README.md) | V-World 건물·도로·지형을 규칙 기반 픽셀 지도로 렌더 | 서울 도심 6,991동, DEM 지형, POI·지하철 레이어 뷰어 구현 |
| [prototype2](prototype2/README.md) | 공간 구조를 잠그고 로컬 SDXL 재질과 디오라마 표현을 결합 | 대표 3구역 시안·비교 뷰어 완료, 전체 96타일 적용은 승인 대기 |

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

## 검증

```bash
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests -v
node prototype2/tests/test_viewer.cjs
prototype2/.venv/bin/python prototype2/scripts/freeze_inputs.py
prototype2/.venv/bin/python prototype2/scripts/diorama_map.py validate
```

V-World API 키는 환경변수로만 주입하며 저장소에 포함하지 않습니다. 데이터·모델·이미지
이용조건은 [prototype2/LICENSES.md](prototype2/LICENSES.md)에 정리했습니다.
