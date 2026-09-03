# pixel_city

서울 도심 관광축을 AI 생성 아이소메트릭 픽셀아트 지도로 재현하고,
관광·지하철 등 공공 공간데이터를 레이어로 얹는 프로토타입.

**제8회 공간정보 활용·아이디어 경진대회** (GeoAI 혁신 아이디어 분야) 출품 예정 · 비영리
**마감 2026-09-18** · 현재 **기획 단계** (코드 없음)

## 문서

- [docs/CONCEPT.md](docs/CONCEPT.md) — **기획서** (컨셉·범위·데이터·리스크·공모전 대응)
- [docs/FLOW.md](docs/FLOW.md) — **전체 흐름도** (mermaid)
- [docs/APPROACH.md](docs/APPROACH.md) — 지도 생성 방식 3안 비교 (미결정)
- [docs/PLAN.md](docs/PLAN.md) — 일정과 진행 체크리스트
- [docs/WORKLOG.md](docs/WORKLOG.md) — 작업 기록
- [docs/AGENTS.md](docs/AGENTS.md) — AI 에이전트 작업 지침

## 레퍼런스 조사

- [docs/RESEARCH-isopolis.md](docs/RESEARCH-isopolis.md) — Isopolis(SF) / isometric.nyc.
  **채택한 파이프라인의 원형**
- [docs/RESEARCH-sf-the-game.md](docs/RESEARCH-sf-the-game.md) — SF: The Game 외 실시간 3D형.
  비교 대상, 이번엔 **미채택**

## 데이터 출처 (예정)

V-World(3D 건물·항공영상·DEM) · 한국관광공사 TourAPI · 국가유산청 ·
카카오 로컬 API · Tmap API · 서울 열린데이터광장
