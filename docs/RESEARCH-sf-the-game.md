# 레퍼런스 조사 — SF: The Game (sf.thijs.gg) 및 유사 "도시 → 게임" 프로젝트

> 조사일: 2026-09-02
> 출처: GeekNews 글 https://news.hada.io/topic?id=32865 및 거기 연결된 링크들
> 목적: 앞선 [Isopolis 조사](RESEARCH-isopolis.md)와 대비되는 접근 — **실시간 3D 플레이형** 도시 재현 사례 정리

> ⚠️ **주의**: 이 프로젝트는 Isopolis와 달리 **공개된 개발 노트가 없다.**
> 아래 기술 내용은 사이트 UI 문자열, 제작자의 X 게시글, GeekNews 요약에서 끌어모은 것이며
> 파이프라인 세부(타일 변환 방법, 비용, 파이프라인 코드)는 **확인되지 않았다**. §5 참조.

---

## 1. 개요

- **이름**: San Francisco — The Game
- **URL**: https://sf.thijs.gg
- **제작자**: Thijs ([@cdngdev](https://x.com/cdngdev), 포트폴리오 https://thijs.gg)
- **무엇**: 샌프란시스코 실제 도시 전역을 브라우저에서 걸어다닐 수 있는 **1인칭/3인칭 3D 게임**.
  제작자 표현으로 "건물을 오르고, 차를 '훔치고', 아무 데나 탐험할 수 있다".
- **반응 규모**: HN 460점 / 댓글 140개 이상.
  제작자 집계로 인게임 누적 이동 15,000마일 이상, 누적 플레이 884시간.

### Isopolis와의 대비

| | Isopolis | SF: The Game |
|---|---|---|
| 형식 | 2D 아이소메트릭 픽셀 **지도** | 실시간 3D **게임** |
| 생성 방식 | 확산 모델 파인튜닝으로 타일 **선(先)생성** | 실제 3D 지오데이터를 **런타임 스트리밍** |
| 데이터 | Google Photorealistic 3D Tiles (학습 입력) | **Apple Maps 데이터** + OpenStreetMap |
| 산출물 | 정적 타일 피라미드 3,570개 / 287MB | 동적 로딩, 정적 산출물 없음 |
| 조작 | 팬·줌 | WASD 이동, 점프, 달리기, 탈것, 글라이더 |
| AI 개입 | 파이프라인의 핵심 | 확인된 바 없음 |

같은 도시를 두고 **"그림으로 굳힐 것인가, 공간으로 돌릴 것인가"** 라는 갈림길을 보여주는 한 쌍이다.

---

## 2. 확인된 기능

**조작**
- `WASD` 이동 / 마우스 시점 / `Space` 점프 / `Shift` 달리기
- `C` 카메라 전환 (3인칭 지원)
- `V` 차량 탑승
- `H` 글라이더
- 클릭 순간이동 (`CLICK TO TELEPORT`)

**월드**
- 주변 거리 타일을 **동적 로드**, 표시 범위 **470m**
- 줌 레벨 **Z15–Z20** 타일 스트리밍 (`TILE STREAM IDLE` 등 상태 표시)
- 거리별 LOD 조절 (Z20 근거리 → Z16 원거리)
- `NEIGHBORHOOD READY 100%` 로딩 진행률 표시

**부가**
- 좌표 표시 및 `COPY LINK` — 현재 위치 공유 링크 생성
- 방위 표시 (N·000°)
- 리셋, 월드 안전(safe) 모드
- 아바타 커스터마이징, 채팅
- 멀티플레이어 — **현재 비활성(DISABLED)**
- 자원(목재·돌·금속) 수집 UI가 존재하나 값은 0 — 미완성 또는 실험적 요소로 보임

**저작권 표기**: `© OpenStreetMap contributors`

---

## 3. 커뮤니티 반응 (GeekNews 댓글 + HN)

- **Apple 서비스약관 위반 우려** — 가장 반복적으로 제기된 쟁점.
  Apple Maps 3D 데이터를 게임 클라이언트로 스트리밍하는 것이 약관상 허용되는지 불명확.
  (Isopolis가 Google 3D Tiles TOS 레이트 제한에 걸렸던 것과 같은 계열의 문제)
- **메모리 누수 보고** — 장시간 플레이 시 브라우저 메모리 증가.
- **MMO/멀티플레이 확장 제안** — 멀티플레이가 비활성 상태라 요구가 많음.
- **고해상도 로컬 버전 다운로드 희망** — 스트리밍 의존을 벗어나고 싶다는 요구.
- **GIS 데이터 활용 가능성** 논의 — 공공 GIS를 얹어 도시 정보 시각화로 확장하자는 제안.
- 향수 관련 언급: 1989년 게임 *Vette!* (SF 배경 드라이빙 게임)와 비교.

---

## 4. 함께 언급된 유사 프로젝트

| 프로젝트 | URL | 내용 | 확인 상태 |
|---|---|---|---|
| Isopolis | https://sf.isopolis.city | SF 아이소메트릭 픽셀 지도 | [별도 문서](RESEARCH-isopolis.md) |
| Seattle 64 | https://seattle64.benjasmin.chatgpt.site | 시애틀 다운타운을 대축척으로 탐험. 드래그 또는 WASD 이동. 데이터: OpenStreetMap + **King County GIS 오픈데이터**. 사진 갤러리·여행 정보·공유 기능 포함 | 사이트 확인, 기술 스택 미상 |
| City Rider | https://cityrider.jpsmaps.com | 도시 주행 계열 프로젝트 | **HTTP 403 — 미확인** |
| Mooncraft 2000 | https://mooncraft2000.com | HTML5 Canvas 기반 무료 브라우저 게임 (레트로 계열) | 사이트 확인, 상세 미상 |
| Vette! (1989) | https://en.wikipedia.org/wiki/Vette | SF 배경 3D 드라이빙 게임. 본 프로젝트의 정신적 선조로 댓글에서 언급 | 참고 |

---

## 5. 확인 실패 / 미검증 항목

| 항목 | 상태 |
|---|---|
| HN 스레드 https://news.ycombinator.com/item?id=49422784 | **HTTP 429 (2회 시도) — 본문 미확인.** 제작자가 스레드에서 밝힌 기술 세부는 못 읽었다 |
| 제작자 X 원문 https://x.com/cdngdev/status/2091909073038082139 | 미러(xcancel) 서비스 중단, 원문 미확인. 인용문은 검색 스니펫 경유 **2차 정보** |
| https://cityrider.jpsmaps.com | HTTP 403 |
| 렌더링 엔진 (three.js? 자체?) | **미확인** |
| Apple Maps 데이터 취득·변환 방법 | **미확인** |
| 호스팅·대역폭 비용 | **미확인** |
| thijs.gg 포트폴리오 내 개발 노트 | **없음** (포트폴리오에 이 프로젝트 자체가 미등재) |

> 첫 조회 시 요약 도구가 "Apple이 개발한 프로젝트"라고 잘못 기술했으나,
> 실제로는 **개인 제작자 Thijs가 Apple Maps 데이터를 사용해 만든 것**이다. Apple과 무관하다.

---

## 6. `pixel_city`에 주는 시사점

1. **선생성(pre-render) vs 런타임 스트리밍은 근본적 분기점이다.**
   Isopolis는 한 번 만들고 정적 호스팅($25~35, 287MB)으로 끝난다.
   이쪽은 생성 비용이 없는 대신 **데이터 제공자 약관과 대역폭에 상시로 묶인다.**
   `pixel_city`가 픽셀아트 지향이면 전자가 압도적으로 유리하다.
2. **지도 데이터 제공자 약관이 두 프로젝트 모두의 최대 리스크다.**
   Google 3D Tiles(Isopolis)든 Apple Maps(이쪽)든 똑같이 걸린다.
   OSM + 공공 GIS(Seattle 64 방식)로 가면 이 리스크가 사라진다 — 대신 건물 형상 품질이 떨어진다.
3. **차용할 만한 UX 패턴**: 좌표 → 공유 링크(Isopolis의 URL 해시와 동일한 발상),
   로딩 진행률 명시, LOD 단계 노출. 셋 다 구현 비용이 낮고 체감이 크다.
4. **멀티플레이·자원 수집은 미완성 상태로 노출돼 있다.** 범위를 넓히면 이렇게 된다는 사례.
   `pixel_city`는 "보는 것"과 "노는 것" 중 하나를 먼저 완성하는 편이 낫다.
5. **메모리 누수는 무한 스트리밍 월드의 기본 함정이다.** 타일 캐시 상한을 처음부터 잡아야 한다.

---

## 7. 원본 링크

- GeekNews: https://news.hada.io/topic?id=32865
- 프로젝트: https://sf.thijs.gg
- 제작자 포트폴리오: https://thijs.gg
- 제작자 X 게시글: https://x.com/cdngdev/status/2091909073038082139
- HN 스레드: https://news.ycombinator.com/item?id=49422784
- Isopolis: https://sf.isopolis.city
- Seattle 64: https://seattle64.benjasmin.chatgpt.site
- City Rider: https://cityrider.jpsmaps.com
- Mooncraft 2000: https://mooncraft2000.com
- Vette! (1989): https://en.wikipedia.org/wiki/Vette
- Vette! 스크린샷: https://www.mobygames.com/game/799/vette/screenshots/dos/
