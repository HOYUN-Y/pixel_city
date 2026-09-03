# Phase 0 PoC — V-World WFS 압출 렌더

V-World WFS에서 받은 **건물 폴리곤 + 지상층수**만으로 아이소메트릭 픽셀 렌더가
가능한지 검증한 코드. **AI 없음, 비용 0.**

## 실행

```bash
export VWORLD_API_KEY=...        # vworld.kr 오픈API 인증키
export VWORLD_API_DOMAIN=...     # 인증키에 등록한 도메인

# 데이터 받기 (경복궁~삼청동 일대)
BBOX="126.9740,37.5760,126.9820,37.5820"
for L in lt_c_spbd lt_l_sprd lt_c_uo301; do
  curl -s -o "gf_${L}.json" \
    "https://api.vworld.kr/req/wfs?SERVICE=WFS&REQUEST=GetFeature&VERSION=2.0.0&TYPENAME=${L}&BBOX=${BBOX}&SRSNAME=EPSG:4326&OUTPUT=application/json&MAXFEATURES=1000&KEY=${VWORLD_API_KEY}&DOMAIN=${VWORLD_API_DOMAIN}"
done
mv gf_lt_c_spbd.json gf_bld.json

pip install Pillow
python iso.py                    # -> poc_iso.png
```

## 사용 레이어

| 레이어 | 내용 | 쓰는 필드 |
|---|---|---|
| `lt_c_spbd` | 도로명주소건물 | `gro_flo_co` 지상층수, `buld_nm` 건물명, 폴리곤 |
| `lt_l_sprd` | 도로명주소도로 | 라인, `road_bt` 도로폭 |
| `lt_c_uo301` | 국가유산 지정/보호구역 | 폴리곤 (경복궁 등) |

## 결과

`poc_iso.png` — 292동, 최고 6층, scale 1.84 m/px.

## 알려진 한계

- **실측 높이 없음.** `gro_flo_co`(층수) × 3m로 추정 (`FLOOR_H`)
- **용도 구분 불가.** `buld_se_cd` 전부 `'0'`, `poi_chk` 전부 `null`
  → 용도별 스타일링하려면 국토부 GIS건물통합정보 필요
- **지붕 형태 없음.** 궁궐 전각·한옥이 납작한 상자로 나옴 → 스프라이트로 보강해야 함
- WFS는 bbox에 걸친 피처 **전체**를 반환한다. 프레임은 bbox로 고정한다 (`BBOX` 상수)

---

# v2 — 용도별건물정보(dt_d198) 단독 렌더  ← **이쪽이 본선**

`iso2.py` / `poc_iso2.png`.

V-World **디지털트윈국토(dtna) API**는 기존 오픈API(`/req/wfs`)와 **다른 카탈로그**다.
여기 `용도별건물정보`가 있고, **폴리곤 + 층수 + 용도 + 구조가 한 응답에** 들어 있어
`lt_c_spbd`와 조인할 필요가 없다.

## 엔드포인트

```bash
# 대량 조회 (bbox) — 이걸 쓴다
https://api.vworld.kr/ned/wfs/getBuildingUseWFS?typename=dt_d198&bbox=<minx,miny,maxx,maxy>&srsname=EPSG:4326&maxFeatures=1000&key=<KEY>&domain=<DOMAIN>

# 건물연령 (동일 방식, typename 다름)
https://api.vworld.kr/ned/wfs/getBuildingAgeWFS?typename=dt_d196&...

# 단건 조회 (PNU) — buldHg(실측 높이)는 여기에만 있다
https://api.vworld.kr/ned/data/getBuildingUse?pnu=<19자리>&format=json&key=<KEY>&domain=<DOMAIN>
```

> ⚠️ **필드명 표기가 다르다.** WFS는 snake_case(`buld_prpos_cl_code_nm`),
> 데이터API는 camelCase(`buldPrposClCodeNm`).

## 쓰는 필드 (WFS `dt_d198`)

| 필드 | 내용 | 용도 |
|---|---|---|
| `ag_geom` | MultiPolygon | 건물 형상 |
| `ground_floor_co` | 지상층수 | 높이 추정 |
| `buld_prpos_cl_code_nm` | 용도 대분류 | 팔레트 매핑 (주거용/상업용/문교사회용) |
| `main_prpos_code_nm` | 주용도 | 세부 분류 |
| `strct_code_nm` | 구조 | **`"목"` 포함 → 한옥·전각 판별** |
| `buld_nm` + `buld_dong_nm` | 건물명·동명 | 라벨 (예: 경복궁 경회루) |

## 검증 결과 (경복궁 일대 bbox)

- 213동 중 **일반목구조 113동** — 전부 경복궁 전각. 동 이름까지 정확
  (함원전·흠경각·경회루·사정전·교태전·강녕전 …)
- 용도 대분류: 상업용 92 / 주거용 71 / 문교사회용 46
- **층수 결측 0건**

## 알려진 한계

- **WFS 응답에 `buldHg`(실측 높이)가 없다.** 층수 × 층고로 추정
  (`FLOOR_H=3.0`, 목구조는 `WOOD_FLOOR_H=5.0`). 실측이 필요하면 PNU 단건 조회로 보강
- 처마는 폴리곤을 중심 기준 확대(`EAVE=1.35`)한 근사. 진짜 오프셋 아님
- 용마루·지붕 곡률 없음 — 스프라이트 단계에서 보강

---

# Phase 1 — 구역 전체 수집·렌더

`collect.py` (수집) / `iso2.py` (렌더) / `seoul_core.png` (결과).

## 대상 구역

```
bbox  126.970, 37.551  ~  126.996, 37.582
가로 2.29 km · 세로 3.43 km · 면적 7.86 km²
경복궁·창덕궁·창경궁·종묘 · 북촌 · 인사동 · 종로 · 명동 · 남산
```

## 실행

```bash
export VWORLD_API_KEY=... VWORLD_API_DOMAIN=...
BB=126.970,37.551,126.996,37.582

python collect.py bld   $BB     # -> cache_bld.xml   (재귀 분할)
python collect.py road  $BB     # -> cache_road.json
python collect.py heri  $BB     # -> cache_heri.json
python collect.py river $BB     # -> cache_river.json

python iso2.py cache_bld.xml $BB 900 680 2 seoul_core.png
```

## maxFeatures 상한 우회

**서버 상한은 1000이다** (`MAXFEATURES=5000` → `INVALID_RANGE`).
1.8×2.2km bbox에서 정확히 1000개가 와서 잘린 것을 확인했다.

`collect.py`는 **응답이 정확히 1000이면 잘린 것으로 보고 bbox를 4분할해 재귀 수집**한다.
`gis_idntfc_no`로 중복을 제거한다 (분할 경계에 걸친 건물이 양쪽에서 온다).

구역 전체 실측: **요청 25회 / 분할 6회 / 수집 7,196 → 중복제거 6,985동 / 12.1초**

## 수집 결과

| 항목 | 수 |
|---|---|
| 건물 | **6,985** |
| 도로 | 1,408 |
| 국가유산 구역 | 177 |
| 하천 | 1 |

### 건물 분포

| 구조 | 동수 | | 용도 | 동수 |
|---|---|---|---|---|
| 철근콘크리트 | 2,817 | | 상업용 | 4,308 |
| **일반목구조** | **2,446** | | 주거용 | 2,142 |
| 벽돌 | 1,282 | | 문교사회용 | 371 |
| 기타 | 440 | | 기타 | 164 |

목구조 2,446동은 **1층 1,786 / 2층 630**으로 전형적 한옥·저층 목조다.
건물명에 **창덕궁 36 · 경복궁 33 · 종묘 17 · 창경궁 9**가 잡힌다.

## 남은 과제

- **DEM 미반영** — 남산·북악산이 평평하다. 지형 기복이 없다
- 목구조를 전부 같은 스타일로 그린다 → 궁궐 전각과 일반 한옥을 구분해야 함 (Phase 2)
- 도로가 얇고 흐리다 — `road_bt`(도로폭)를 반영하지 않았다
- 타일 분할 미구현 (Phase 4)

## 도로폭·궁궐 구분 반영

- **도로폭**: `road_bt`(1,408개 전부 보유, 1~20m)를 선 굵기로. 굵은 도로를 나중에 그려
  간선(세종대로·종로)이 위로 오게 한다
- **궁궐 vs 한옥**: 목구조를 `buld_nm`에 `궁/종묘/사직` 포함 여부로 나눈다
  - 궁궐 98동 → 청기와 + 단청 기둥, 층고 ×1.4
  - 일반 한옥 2,352동 → 회기와 + 목재

확대 렌더: `gyeongbok.png` (경복궁~북촌, 1.69 m/px)
