# Prototype2 피드백 베타 — 2026-09-16

## 확인하기

```sh
prototype2/.venv/bin/python prototype2/scripts/city_snapshot.py
node prototype2/server/dev.mjs
```

<http://127.0.0.1:8768/>

공개용 UI의 로컬 미리보기다. 기존 시안 창 동작을 유지한 개발 진입점은
`/web/pilot/index.html?view=city-pilot`이며, 두 화면은 동일 데이터/지도/가이드를 사용한다.

- 지도: 기존 종로 연결 결과 1792×1024, 최대 확대 100%. 이번에 배경을 새로 생성하지 않았다.
- 종로타워 선택, 차량 재생/정지/구간 이동, 보행 시험.
- 8개 도감 카드, 명시적 브라우저 저장, 주변 36개 장소 검색과 상세.
- 비 미리보기 끄기/약하게/강하게. 실시간 날씨가 아니며 reduced-motion에서는 정적 색조만 적용한다.
- 그림자는 보류. 기존 노을 실험 실행은 변경하지 않았다.
- 도감에 있는 장소 모두가 지도 객체인 것은 아니다. 검증된 종로타워 외에는 지도 이동을 제공하지 않는다.
- 데이터 원본 경로·관계 구분은 [TOURAPI_DATA.md](TOURAPI_DATA.md).

최종 합성 이미지: `prototype2/assets/city_pilot/final.png`.
최종 스크린샷: `prototype2/work/city-final-qa-20260916/{desktop,mobile}_{map,place,rain}.png`.
정합 보고서와 16개 증거 이미지: `prototype2/work/city-alignment-20260916/`.
이 파일들은 원본 재배포 여부가 미확정이므로 Git 및 공개 패키지 외부 업로드에서 제외한다.

## 완료와 보류

| 항목 | 상태 |
|---|---|
| 지도/도감/검색/날씨/차량 UI | 로컬 동작 및 데스크톱·모바일 검증 |
| 복수 랜드마크 형식 | `landmarks[]` 지원, 기존 `landmark` 호환 |
| 보신각 독립 에셋 | 원본에서 앞 건물에 가려 크기·윤곽 검증 불가, 생성 보류 |
| 도로 정합 | 12곳 중 10곳 측정 가능, 명목 오차 0–7px, 수기 불확실성 ±4px; 2곳 판정 불가 |
| 건물 폭 | 같은 지붕 4곳 비율 0.9904/1/1/1, 끝점 불확실성 ±3px |
| 정합 전체 합격 | **아님**. 명목 오차와 불확실성을 포함한 엄격 판정을 구분해야 함 |
| 추가 이미지 비용 | 0회 / $0. 기존 유료 실행은 닫힌 상태 유지 |
| 실제 LLM 연결 | 서버 구현 및 mock 검증. Redis 연결 완료, 영구 원장 초기화·가이드 활성 설정·실호출은 아직 보류. 실호출 0회 / $0 |
| Vercel | 전용 `pixel-city-beta` 프로젝트 및 무료 Redis 연결 완료. 아래 권한 확인 전 업로드 보류 |

## 공개 전 필요한 확인

### 1. VWorld 파생 지도 공개 허용

2026-09-16 확인한 [공식 이용약관](https://www.vworld.kr/v4po_prcint_a001.do)의
제14조에는 3차원 공간정보의 무단 복제·유출 제한, 제19조에는 사전 승낙 없는
복제·변경·타인 제공 및 저장 제한이 있다.
[저작권 정책](https://www.vworld.kr/v4po_prcint_a006.do)은 공공누리 표시와
제3자 권리 확인을 요구한다. [공공데이터 API 안내](https://www.data.go.kr/data/3073144/openapi.do)의
이용제한 없음 표시만으로 특정 3D 외관을 변환한 공개 이미지의 허용까지 확정하지 않았다.
이는 위법 판정이 아니라 공개 권한에 관한 미확정 사항이다.

운영기관에 아래 사용 범위를 확인하거나 해당 허용 근거를 확보한 뒤 배포한다:
‘VWorld 3D 정사영 캡처를 AI로 픽셀화한 2D 지도를 Vercel에 비영리 공개,
원본 3D 데이터·텍스처·캡처는 배포하지 않고 VWorld 출처 표기.’
사용자 게임 참고 이미지도 공개 패키지에 포함하지 않는다. 기존 생성 캐릭터/차량만 재사용한다.
웹 폰트는 기존 배포본의 라이선스 파일을 함께 포함한다.

### 2. Upstash 계정 약관 동의

기존 Vercel 계정 `hoyun-y` / scope `hoyun-ryu-s-projects`에서 사용자가 동의를 완료했다.
이후 무료 플랜, 자동 업그레이드 끄기, eviction 끄기 설정으로 리소스를 생성했다.
CLI inspect에서 `Free` / `available` 및 전용 프로젝트만 연결됨을 재확인했다.

- 프로젝트: `pixel-city-beta` (`prj_ODMjqiTaCUDNvriJX5jqTOD7Uh3p`)
- Redis: `pixel-city-guide-budget` (`store_rHTOrWyB1cCjyvoN`)
- 연결 환경: production / preview / development
- 아직 배포하지 않았고, 다른 프로젝트는 변경하지 않았다.
- Vercel이 주입하는 `KV_REST_API_URL` / `KV_REST_API_TOKEN`도 서버에서 지원한다.
- 로컬 접속 정보는 Git 제외 `prototype2/work/city-release-20260916-v3/.env.redis.local`에만 저장했다. 값을 출력하지 않는다.

[Upstash 연결 약관 확인](https://vercel.com/hoyun-ryu-s-projects/~/integrations/accept-terms/upstash?source=cli)

실행한 생성 명령 (이미 생성 완료, 중복 실행하지 않음):

```sh
vercel integration add upstash/upstash-kv --plan free --name pixel-city-guide-budget --no-connect --no-env-pull -m primaryRegion=hnd1 -m eviction=false -m prodPack=false -m autoUpgrade=false --non-interactive
```

생성 시 `autoUpgrade=false`, `eviction=false`, `prodPack=false`를 명시했다. inspect 출력은 Free 플랜과 연결 상태만 제공했다.
기존 다른 프로젝트의 환경변수·도메인·배포 보호 설정은 변경하지 않는다.

## 가이드 서버와 예산

환경변수: `GUIDE_ENABLED=true`, `OPENROUTER_API_KEY`, `UPSTASH_REDIS_REST_URL`,
`UPSTASH_REDIS_REST_TOKEN`, `GUIDE_IP_HASH_SALT`(24자 이상 난수).
키는 브라우저에 넣지 않는다. `/api/guide` GET은 활성 상태만, POST는 명시적 질문 제출만 처리한다.

모델 `openai/gpt-5.6-luna`, reasoning low, 출력 최대 900토큰, OpenAI 제공자만,
자동 재시도·모델 fallback 없음. 문맥은 선택 장소 및 이름/소개 단어 검색 상위 4개다.
OpenRouter 메타데이터 가격을 매번 확인하고 요청에도 입력 $0.20/M·출력 $1.20/M 상한을 지정한다.
근거: [OpenRouter 가격 제한](https://openrouter.ai/docs/guides/routing/provider-selection#max-price).

예산은 **모든 실행 합산 $1**, 요청당 $0.01 보수 예약 후 실제 usage.cost로 정산한다.
Redis 영구 키 `pixel-city:guide:lifetime:v1`은 배포/요청 시 자동 생성·초기화·만료하지 않는다.
초기화는 최초 1회 운영자가 누적 실호출 비용(이번 실행은 0)을 확인한 뒤 원자적으로 수행한다.
값은 해시 필드 `used`(달러×1,000,000 정수), `blocked=0`, `completed=0`이다.
기존 키가 있으면 덮어쓰지 않는다. 누락/유실 시 새로 0으로 만들지 말고 원장을 복구한다.

Redis Lua에서 예약·전체 동시 처리 2개·IP 분당3회/일20회를 함께 검사한다.
IP 원문 대신 HMAC만 저장하며 대화 원문은 서버가 기록하지 않는다.
과금 미확정/시간 초과/저장소 장애 시 LLM은 보수적으로 차단하고 예약은 돌려주지 않는다.
진행 중 요청에 만료가 없어 서버 강제 종료 뒤 2개가 남으면 운영자가 확인할 때까지 차단된다.
정산 후 잘못된 응답이라도 이미 발생한 비용은 차감한다.
실 Redis의 격리된 시험 키로 동시 10요청 중 2개 허용, 분당3회/일20회 제한,
$1 상한 및 과금 미확정 차단을 검증했다. 시험 키는 종료 후 삭제했으며 영구 원장은 건드리지 않았다.
네트워크 장애는 mock 검증, 실제 답변 품질과 영구 원장 초기화는 아직 남아 있다.

```sh
node --env-file=prototype2/work/city-release-20260916-v3/.env.redis.local prototype2/tests/city_redis_check.mjs
```

유료 AI 호출은 0회다. CLI가 자동 설치한 Upstash 에이전트 스킬은 앱 기능과 별개이며 구현 커밋에 포함하지 않는다.

## 공개 패키지와 재개 순서

```sh
prototype2/.venv/bin/python prototype2/scripts/city_release.py --dest prototype2/work/city-release-NEW
```

화이트리스트는 지도7개 PNG·정제 JSON·필요 JS/CSS·폰트·가이드 서버뿐이다.
원본 캡처/프롬프트/게임 참고/로그/키/Drive 경로/로컬 검수 UI는 제외한다.
최신 후보 `prototype2/work/city-release-20260916-v3`는 `publicRightsApproved=false`이며
빌드 가드가 배포를 거부한다. 이 후보를 업로드하지 않는다.
권한 근거가 확보되면 `{approved:true,finalSha256:"...",evidence:"..."}` 검토 기록을
`--rights-approval`로 전달해 새 후보를 만든다. 근거 없는 true 변경으로 우회하지 않는다.

재개: 누적 원장 최초 초기화/서버 환경 설정 → 최대5회 실 LLM 시험($1 합산 내)
→ 공개 권한 확인 → 최신 코드로 새 공개 후보 구성 → Vercel 검증 배포 → 로그아웃 공개 접근 및 모바일 확인 → production 승격.
공개 URL, 실호출 품질, 실제 Vercel Function 번들 동작은 아직 검증하지 않았다.

## 검증 명령

```sh
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests -p 'test_*.py'
node --test prototype2/tests/test_*.mjs
prototype2/.venv/bin/python prototype2/tests/city_browser_check.py
```

Python 기존 118개와 신규 스냅샷/공개 패키지 3개, Node 14개(기존 7개 스위트 + 신규 가이드/복수 객체 7개 테스트) 통과.
브라우저는 1440×1000 / 390×844, 도감 저장 후 새로고침, 검색, 비, reduced-motion,
차량 재생 및 최대 줌을 확인했고 유료 POST는 발생하지 않았다.
최종 브라우저 검증에는 각 화면에서 가이드 성공/실패 응답 각1회 모의시험,
HTML 응답의 텍스트 표시 및 복수 객체 알파 선택·독립 가림 시험도 포함했다.
기존 종로 연결 뷰어의 로딩도 오류 없이 확인했고 닫힌 실행의 manifest 해시는 작업 전과 동일하다.
API 실제 호출·공개 접속은 미검증으로 남긴다. Redis 실 동시성/제한은 후속 검증 완료했다.
다른 세션의 README/루트 scripts/docs/planning 및 prototype1은 수정하지 않는다.
