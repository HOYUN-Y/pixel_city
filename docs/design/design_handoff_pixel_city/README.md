# Handoff: Pixel City — 광화문 픽셀 지도 앱 (모바일)

## Overview
서울 광화문·경복궁 일대를 아이소메트릭 픽셀 지도로 보여주고, 그 위에 (1) LLM 관광 가이드 질의응답 → 추천 루트를 지도에 표시, (2) 사용자 명소/루트 업로드 + 사진, 좋아요/댓글 피드, (3) 방문 인증 → 픽셀 카드 도감, (4) 픽셀 엽서 공유를 얹은 모바일 앱의 인터랙티브 프로토타입.

지도 이미지는 저장소 `pixel_city/prototype2/eval/diorama/palace_diorama.png` (V-World 건물·도로 데이터 기반 룰 렌더)를 그대로 사용. UI는 지도 위 오버레이이며 지도는 항상 배경으로 남는다.

## About the Design Files
이 번들의 HTML 파일은 **HTML로 만든 디자인 레퍼런스(프로토타입)** 이다. 의도한 룩과 동작을 보여주는 용도이며 그대로 배포하는 코드가 아니다. 목표는 이 디자인을 **대상 코드베이스의 환경(React Native / Flutter / 웹 React 등)에서 그 환경의 패턴으로 재구현**하는 것. 아직 앱 프레임워크가 없다면 커스텀 Canvas 지도 뷰어(prototype1/2 `web/app.js`의 타일 뷰어)를 그대로 살릴 수 있는 웹 스택(React + Canvas)을 권장.

## Fidelity
**High-fidelity.** 색·타이포·간격·상태가 최종안 수준. 단, 아래는 플레이스홀더:
- 명소/피드 사진 → 그라디언트 박스 (실제 사용자 업로드 이미지로 대체)
- 도감 카드 아트 → 그라디언트 (명소별 픽셀 스프라이트로 대체)
- 지도 → 정지 이미지 1장 (실제는 타일 피라미드 `web/tiles/{z}/{x}/{y}.png`, manifest: 9134×5528, tile 256, max_zoom 6, bbox 126.97,37.551 – 126.996,37.582)
- LLM 응답 → 정규식 매칭 시나리오 3종 (실제 LLM API로 대체)

## Files
- `Pixel City 광화문 (standalone).html` — 오프라인 단일 파일. 브라우저로 열면 바로 동작.
- `screenshots/` — 주요 상태 12장.
- `source/Pixel City Prototype.dc.html` — 프로토타입 원본 (템플릿 + 로직 클래스). **데이터 모델·상태 전이는 이 파일의 `<script>` 로직을 기준으로 한다.**
- `source/Pixel City Options.dc.html` — 같은 프로토타입을 3가지 룩/시간대로 나열한 비교 페이지.
- `source/ios-frame.jsx`, `source/support.js` — 프리뷰 런타임(디바이스 프레임·템플릿 엔진). 재구현 대상 아님.
- `source/assets/` — 지도 렌더 이미지 3장 (저장소 prototype2 산출물).

## Screens / Views

### 1. 메인 지도 (기본 화면) — `01-map-default.png`
- **레이아웃**: 전체 화면 지도(드래그 팬) 위에 3층 오버레이. 상단 바(top 62px, 좌우 14px) / 하단 시트 / 우하단 FAB.
- **지도**: 1536×1536 이미지, `transform: translate(pan) scale(0.62)`, `image-rendering: pixelated`. 초기 pan (-110, -180).
- **시간대 틴트**: 지도 위 전체 레이어 `mix-blend-mode: multiply`, 낮 `transparent` / 노을 `rgba(255,170,110,.45)` / 밤 `rgba(60,70,140,.6)`, transition .6s.
- **비 효과**: `repeating-linear-gradient(115deg, transparent 0 14px, #DCEBF5 14px 16px, transparent 16px 40px)`, opacity .35, `background-position` 0→400px 0.5s 무한 애니메이션.
- **핀** (명소마다, 지도 좌표 기준 `translate(-50%,-100%)`):
  - 라벨 박스: padding 6px 12px, 카테고리 색 배경, `border: 3px solid #3A2A1E`, radius 6px, 흰 글자 700 20px(지도 스케일 0.62 → 실제 ~12.4px), `box-shadow: 4px 4px 0 rgba(58,42,30,.5)`. 좌측 12px 흰 정사각 아이콘.
  - 하단 삼각 꼬리: border 10px transparent + `border-top: 14px solid #3A2A1E`.
  - 루트 활성 시 번호 배지(#3A2A1E 배경 / #F2C14E 글자 14px). 현재 경유지는 `bob` 1s 상하 애니메이션.
  - 탭 → 명소 상세 시트.
- **상단 바**
  - AI 검색 필드(높이 52, 유리질: `rgba(251,243,228,.92)` + `backdrop-filter: blur(10px)`, radius 16, `border 1.5px rgba(58,42,30,.12)`, shadow `0 6px 20px rgba(58,42,30,.18)`). 좌측 22px "AI" 배지(#E8735A, 2px #3A2A1E 테두리, 픽셀 폰트 13px). 플레이스홀더 "광화문에서 반나절, 뭐부터 볼까요?" + 블링크 커서. 탭 → 시트 확장(AI 가이드 탭).
  - 시간대 버튼 52×52 (같은 유리질). 14px 색 견본(낮 #F2C14E / 노을 #E8735A / 밤 #3A3F7A) + 라벨 11px. 탭 → 낮→노을→밤 순환.
  - 레이어 칩 행(가로 스크롤): 명소 / 사용자 스팟 / 지하철 / 문화재 구역. padding 7px 12px, pill, 12.5px 600. 켜짐 `#3A2A1E`/`#FBF3E4`, 꺼짐 `rgba(251,243,228,.92)`/`#3A2A1E`. 지하철·문화재는 토스트 "데이터 레이어 연결 예정".
- **FAB**: 56×56, radius 18, #E8735A, `border 3px #3A2A1E`, 흰 "+" 30px, shadow `0 8px 20px rgba(232,115,90,.45)`. 위치 `bottom = sheetH + 16`, 시트 완전 확장 시 화면 밖(-80)으로 숨김. transition .35s `cubic-bezier(.2,.8,.2,1)`.
- **하단 시트**: 배경 #FBF3E4, radius 24 24 0 0, shadow `0 -10px 30px rgba(58,42,30,.18)`. 높이 3단계: collapsed 64 / peek 118 / full 600 (transition .35s). 상단 26px 핸들 영역(44×5 #C9B58E 바), 탭 행(AI 가이드 / 피드 / 도감; 활성 `#3A2A1E` 배경 흰 글자 radius 12, 13.5px 700), 내용 스크롤 영역 padding 0 16px 40px, gap 12.

### 2. AI 가이드 탭 — `02-ai-guide-chat.png`, `03-route-on-map.png`
- 말풍선: 사용자 `#3A2A1E`/`#FBF3E4`, radius `16 16 4 16`, 우측 정렬. 가이드 `#fff`/`#3A2A1E`, `border 1.5px rgba(58,42,30,.12)`, radius `16 16 16 4`. 14.5px / line-height 1.5, max-width 86%.
- 입력 중 표시: "가이드가 코스를 짜고 있어요…" (1.1s 후 응답).
- **추천 코스 카드** (가이드 응답에 첨부): `border 2px #3A2A1E`, radius 14, `box-shadow 4px 4px 0 #3A2A1E`. 90px 지도 썸네일 + "AI 추천 코스" 픽셀 배지 / 제목 16px 800 / 메타 12.5px #6B5541 / 경유지 칩(#F1E3C6, "1. 북촌한옥마을" 형식) / 버튼 "지도에 표시"(#6FA657 흰글자, flex 1) + "저장"(#F1E3C6).
- 빠른 질문 칩: 반나절 고궁 코스 / 저녁에 먹거리 위주로 / 비 오는 날 실내 (pill, `border 1.5px #3A2A1E`, #fff).
- 입력 바(시트 하단 고정): input 높이 46, radius 14, `border 2px #3A2A1E`; 전송 버튼 46×46 #3A2A1E / ↑ #F2C14E.
- **루트 표시 시**: 지도에 SVG polyline 2겹 — 아래 #3A2A1E 14px opacity .35, 위 #F2C14E 8px `dasharray 18 22` + `dashoffset` 1.2s 무한(걷는 느낌). 시트는 peek로 내려가고 첫 경유지로 카메라 이동(`pan = (201 - mx*scale, 380 - my*scale)`).
- **루트 바** (top 172, 좌우 14): #3A2A1E 배경 #FBF3E4 글자, radius 14, padding 10 12. 제목 14px 700 / 메타 "1/4 · 북촌한옥마을 → 국립현대미술관" 12px 75%. "다음 →" 버튼(#F2C14E, 13px 700) → 다음 경유지로 카메라 이동, 마지막이면 토스트. ✕(28×28 `rgba(255,255,255,.12)`) → 루트 해제.

### 3. 명소 상세 시트 — `04-spot-detail.png`, `05-spot-visited.png`
- 딤 `rgba(58,42,30,.45)` 위에 하단 시트(max-height 82%, radius 24 24 0 0, `popin` .3s). 바깥 탭으로 닫힘.
- 히어로 190px (사진; 현재 그라디언트). 중앙 "사진 N장 · 사용자 업로드" 배지. 우상단 ✕ 32×32 #3A2A1E. 좌하단 -16px 겹치는 카테고리 태그(카테고리 색 배경, `border 3px #3A2A1E`, radius 8, 15px 800, shadow 3px 3px 0).
- 본문 padding 28 18 34, gap 14: 이름 24px 900 / 부제 13px #8A7358 / 버튼 행[♥ 좋아요(흰 배경, 눌리면 #E8735A 흰글자, flex 1) · 방문 인증(#6FA657, flex 2, shadow 3px 3px 0 #3A2A1E)] / 설명 14.5px lh 1.6 #4A3A2C / 태그 `#고궁` (#F1E3C6, nowrap) / 댓글 목록(28px 아바타 + 13.5px) / 댓글 입력 42px.
- 방문 완료 후 버튼: #8A7358 "✓ 방문 완료 · 카드 보유"; 재탭 시 토스트 "이미 받은 카드예요".

### 4. 카드 획득 모달
- 딤 `rgba(58,42,30,.7)`, 중앙 "NEW CARD!" 픽셀 폰트 14px #F2C14E letter-spacing 1px.
- 카드 190px 폭 3:4, `border 3px #3A2A1E`, radius 14, `box-shadow 6px 6px 0 #3A2A1E, 0 0 60px rgba(242,193,78,.6)`, `popin` .45s `cubic-bezier(.2,.9,.3,1.3)`(오버슈트). 우상단 등급 배지(COMMON/RARE/EPIC), 하단 이름 픽셀 폰트 15px.
- 하단 "도감 N/7 · 탭하여 닫기".

### 5. 도감 탭 — `06-collection.png`
- 헤더 카드 #3A2A1E: "광화문 도감" 픽셀 15px / 설명 12.5px / 우측 "1/7" 픽셀 22px #F2C14E + 90×8 진행바.
- 3열 그리드 gap 10, 카드 3:4, `border 2px #3A2A1E`, radius 12, shadow 3px 3px 0. 미획득: opacity .55 + `grayscale(1)`. 탭 → 해당 명소 상세.
- 하단 "✉ 오늘의 픽셀 엽서 만들기" (#8CC5D8, 2px 테두리, 14px 800).

### 6. 피드 탭 — `07-feed.png`
- 카드: `border 2px #3A2A1E`, radius 14, #fff, shadow 4px 3px 0. 헤더(32px 아바타 · 닉네임 13.5px 700 · "2시간 전 · 명소" 11.5px #8A7358 · 우측 SPOT(#B85C3A)/ROUTE(#6FA657) 픽셀 배지) / 120px 사진 영역(dashed) / 제목 15.5px 800 / 설명 13px / 액션 행 "♥ 88 · 💬 12 · ▶ 따라가기(#6FA657, 우측)". 좋아요 토글은 카드 탭(상세 열기)과 분리(stopPropagation).

### 7. 업로드 — `08-upload.png`
- 전체 화면 #FBF3E4, 헤더 padding 64 18 12 (← 36×36 흰 버튼 + "내 장소 올리기" 20px 900).
- 세그먼트 [📍 명소 | 〰 루트] (#F1E3C6 트랙, 활성 #fff).
- 3칸 정사각: 사진 추가(dashed, "AI가 픽셀로 변환") / 픽셀 변환 미리보기(`map_rpg_downtown.png`) / 위치 찍기(지도 썸네일 위 #E8735A 버튼).
- 필드: 이름(48px, `border 2px #3A2A1E`, radius 12), 한 줄 소개(textarea 3줄), 태그 칩 7개 토글(한옥·카페·야경·먹거리·사진·아이랑·비오는날).
- 루트 선택 시 추가 카드: 경유지 목록(22px #F2C14E 번호 배지) + "+ 경유지 추가 · 예상 도보 1시간 40분".
- 안내문 12px #8A7358(공공누리 표기 안내). 제출 버튼 "지도에 올리기" #6FA657, `border 3px`, radius 14, 16px 900, shadow 4px 4px 0 → 닫히고 피드 탭 + 토스트 "업로드 완료! 검수 후 지도에 표시돼요".

### 8. 픽셀 엽서 — `12-postcard.png`
- 전체 화면 #FBF3E4. 엽서 3:2, `border 4px #3A2A1E`, `box-shadow 8px 8px 0 #2E1C10`, `rotate(-1.5deg)`. 배경 = 현재 지도 pan 기준 크롭(`background-size 180%`) + 시간대 틴트. 좌하단 "광화문 · 경복궁"(픽셀 20px, `text-shadow 2px 2px 0 #3A2A1E`) + "SEOUL PIXEL CITY · 날짜" 12px. 우상단 54×64 우표(dashed, 최근 카드 아트) + 원형 소인.
- 메시지 textarea, 버튼 [이미지 저장 #F2C14E | 친구에게 보내기 #8CC5D8] (`border 3px`, shadow 3px 3px 0 #2E1C10).

### 9. UI 톤 변형 "스타듀" — `10-stardew-dusk.png`
프로토타입 우측 컨트롤(또는 `uiStyle` prop) = `pixel`일 때 다음 오버라이드:
- 패널(`.pnl`): radius 0, `border 3px #5A3921`, `box-shadow inset 0 0 0 3px #F3DFAE, 4px 4px 0 #5A3921`, 배경 #F7E9C6, blur 없음.
- 어두운 패널(`.pnl-dark`): `border 3px #5A3921`, inset 3px #A6754A, 배경 #8B5A2B.
- 버튼(`.btn`): radius 0, `inset -3px -3px 0 rgba(0,0,0,.25), 3px 3px 0 #5A3921`, `border 2px #5A3921`.
- 칩: radius 0 + 2px 테두리. 제목(`.hd`): 픽셀 폰트 NeoDunggeunmo.

## Interactions & Behavior
- 지도 팬: pointerdown 시작점 저장 → pointermove로 pan 갱신 → pointerup 종료. (핀치 줌 미구현; 실제 구현에서는 타일 줌 레벨 0–6 연동.)
- 시트: 핸들 탭 → peek ↔ full. 탭 선택 시 full. 검색 필드 탭 → full + AI 가이드 탭.
- 채팅: Enter 또는 ↑ 전송. 1.1s "입력 중" 후 응답. 응답 매칭 규칙(프로토타입): `/반나절|고궁|궁|처음|3시간|추천/` → 고궁 코스, `/먹|음식|저녁|시장|맛/` → 서촌 먹거리, `/비|우산|실내|추워|더워/` → 실내 코스, 기타 → 기본 응답. 실제 구현: LLM에 (사용자 질문 + 현재 시간대/날씨 + 반경 내 공공 POI + 사용자 업로드 스팟)을 컨텍스트로 전달, 응답을 `{title, meta, stops[], ids[]}` 구조로 받아 카드 렌더.
- 토스트: top 150 중앙, #3A2A1E, 1.8s 후 소멸, `popin` .25s.
- 애니메이션 정의: `dash`(stroke-dashoffset → -40, 1.2s linear ∞), `bob`(translateY -100%↔-112%, 1s ∞), `rain`(0.5s ∞), `popin`(scale .6→1 + opacity), `blink`(1s step-end ∞).

## State Management
```
pan {x,y}, scale(0.62), drag
sheet: 'collapsed'|'peek'|'full'   tab: 'chat'|'feed'|'book'
msgs[{me, text, routeKey?}], typing, draft
route: routeKey|null, step (현재 경유지 index)
spot: spotId|null (상세), liked{spotId}, visited{spotId}, showCard: spotId|null
upload, upKind: 'spot'|'route', upTags{}
postcard, toast
layers{spots, users, subway, heritage}
feedLikes{}, feedLiked{}
time: 'day'|'dusk'|'night', ui: 'modern'|'pixel', weather: 'clear'|'rain'
```
데이터: `SPOTS[]` {id, name, cat, mx, my(지도 px), bg(카테고리 색), sub, desc, tags, likes, photos, rarity, comments[]}, `ROUTES{}` {title, meta, stops[], ids[]}. 실제 구현에서는 mx/my 대신 위경도 → 아이소메트릭 투영(prototype1 ENU 프레임) 변환.

## Design Tokens
**색**
- 잉크 `#3A2A1E` · 진갈 `#5A3921` · 그림자갈 `#2E1C10` · 나무 `#8B5A2B` · 보조 텍스트 `#6B5541` / `#8A7358` / `#4A3A2C`
- 크림(시트) `#FBF3E4` · 파치먼트 `#F1E3C6` / `#F7E9C6` · 지면 `#EFE4CC` / `#D9CBA5` / `#E3D3AE` · 핸들 `#C9B58E`
- 코랄(주 액션·FAB) `#E8735A` · 해(루트·강조) `#F2C14E` · 잎(확정·루트 태그) `#6FA657` · 하늘 `#8CC5D8` · 기와 `#2F6F6F` · 벽돌 `#B85C3A` · 밤 `#3A3F7A`
- 유리질 패널 `rgba(251,243,228,.92)` + blur 10px

**타이포**: 본문 Pretendard (fallback -apple-system, Apple SD Gothic Neo). 픽셀 라벨 NeoDunggeunmo(https://github.com/neodgm/neodgm) — 배지·도감 제목·등급·"NEW CARD!"에만. 크기: 24/20/16/15.5/14.5/13.5/12.5/11.5/11.

**간격·형태**: 화면 여백 14–18px, 카드 내부 12–14px, gap 8–14px. radius 6(핀)/8/10/12/14(카드)/16(유리질)/18(FAB)/24(시트). 테두리 2–3px 잉크. "하드 섀도" `Npx Npx 0 #3A2A1E` (N=3–8)가 이 UI의 시그니처.

## Assets
- `assets/map_palace.png` (1536², 경복궁 구역) — 메인 지도. `assets/map_downtown.png` — 코스 카드·피드 썸네일. `assets/map_rpg_downtown.png` — 업로드 화면 "픽셀 변환 미리보기" 예시. 모두 저장소 prototype2 산출물(V-World 데이터, 출처 표기 필요).
- 아이콘은 텍스트 글리프(✕ ← ↑ ♥ ▶ ✉ 📍 💬)로 대체됨 → 구현 시 픽셀 아이콘 세트로 교체 권장.
