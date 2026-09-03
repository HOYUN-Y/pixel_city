# pixel_city

서울 도심 관광축을 AI 생성 아이소메트릭 픽셀아트 지도로 재현하고,
관광·지하철 등 공공 공간데이터를 레이어로 얹는 프로토타입.

**제8회 공간정보 활용·아이디어 경진대회** (GeoAI 혁신 아이디어 분야) 출품 예정 · 비영리
**마감 2026-09-18** · 현재 **프로토타입 동작** (뷰어 + 관광·지하철 레이어)

## 문서

- [docs/CONCEPT.md](docs/CONCEPT.md) — **기획서** (컨셉·범위·데이터·리스크·공모전 대응)
- [docs/FLOW.md](docs/FLOW.md) — 전체 흐름도 (mermaid)
- [docs/APPROACH.md](docs/APPROACH.md) — 지도 생성 방식 3안 비교 (미결정)
- [docs/PLAN.md](docs/PLAN.md) — 일정과 진행 체크리스트
- [docs/WORKLOG.md](docs/WORKLOG.md) — 작업 기록
- [docs/AGENTS.md](docs/AGENTS.md) — AI 에이전트 작업 지침
- [prototype2/README.md](prototype2/README.md) — 구조 제어형 AI 픽셀 지도 실험 계획

## 레퍼런스 조사

- [docs/RESEARCH-isopolis.md](docs/RESEARCH-isopolis.md) — Isopolis(SF) / isometric.nyc.
  **채택한 파이프라인의 원형**
- [docs/RESEARCH-sf-the-game.md](docs/RESEARCH-sf-the-game.md) — SF: The Game 외 실시간 3D형.
  비교 대상, 이번엔 **미채택**

## 데이터 출처 (예정)

V-World(3D 건물·항공영상·DEM) · 한국관광공사 TourAPI · 국가유산청 ·
카카오 로컬 API · Tmap API · 서울 열린데이터광장

## 실행

```bash
export VWORLD_API_KEY=... VWORLD_API_DOMAIN=...
BB=126.970,37.551,126.996,37.582

# 1. 공간데이터 수집 (bbox 재귀 분할로 maxFeatures 1000 상한 우회)
for L in bld road heri river park temple museum market tourinfo; do
  python poc/collect.py $L $BB
done

# 2. 브라우저용 JSON 내보내기
python poc/export.py .          # -> web/data/{city,layers,poi,meta}.json

# 3. 뷰어 실행
cd web && python -m http.server 8765   # http://127.0.0.1:8765
```

정적 PNG가 필요하면 `python poc/iso2.py cache_bld.xml $BB 900 680 2 out.png`.
