# pixel_city

서울 도심 관광축(경복궁·창덕궁·창경궁·종묘·북촌·인사동·종로·명동·남산, **7.86km²**)을
공공 공간데이터로 재현한 아이소메트릭 픽셀 지도.

**제8회 공간정보 활용·아이디어 경진대회** — GeoAI 혁신 아이디어 분야 출품 예정 · 비영리
**마감 2026-09-18**

---

## 두 갈래로 진행한다

| | 접근 | 상태 |
|---|---|---|
| **[prototype1](prototype1/)** | **공공데이터 벡터 렌더** — 건물 폴리곤·층수·용도·구조를 그대로 압출해 그린다. AI는 텍스처와 랜드마크에만 | 뷰어 동작 중 |
| **[prototype2](prototype2/)** | **확산 모델 기반** — 조건 이미지(edge·height·mask)로 이미지를 생성한다 | 별도 진행 |

prototype1은 기하가 정확하고 비용이 0인 대신 질감이 약하고,
prototype2는 질감이 좋은 대신 환각·검수 부담이 있다. 둘을 비교해 제출본을 정한다.

---

## prototype1 빠른 실행

```bash
export VWORLD_API_KEY=... VWORLD_API_DOMAIN=...
BB=126.970,37.551,126.996,37.582

cd prototype1
for L in bld road heri river park temple museum market tourinfo; do
  python poc/collect.py $L $BB
done
python poc/export.py .                  # -> web/data/*.json
cd web && python -m http.server 8765    # http://127.0.0.1:8765
```

뷰어에서 좌상단 **픽셀화** 체크박스로 픽셀 렌더 / 이전 렌더를 즉시 비교할 수 있다.

## 문서

- [prototype1/docs/CONCEPT.md](prototype1/docs/CONCEPT.md) — 기획서
- [prototype1/docs/PLAN.md](prototype1/docs/PLAN.md) — 일정·체크리스트
- [prototype1/docs/APPROACH.md](prototype1/docs/APPROACH.md) — 생성 방식 결정 기록
- [prototype1/docs/FLOW.md](prototype1/docs/FLOW.md) — 흐름도
- [prototype1/docs/WORKLOG.md](prototype1/docs/WORKLOG.md) — 작업 기록
- [prototype1/docs/AGENTS.md](prototype1/docs/AGENTS.md) — AI 에이전트 작업 지침
- 레퍼런스 조사: [Isopolis](prototype1/docs/RESEARCH-isopolis.md) ·
  [SF: The Game](prototype1/docs/RESEARCH-sf-the-game.md)

## 데이터 출처

V-World(건물·도로·국가유산·공원·POI) · 국토지리정보원(DEM) · 국가유산청 · 서울교통공사
