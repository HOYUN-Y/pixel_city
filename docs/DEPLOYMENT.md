# Prototype2 배포 환경

## 로컬 패키지 준비 업데이트 — 2026-09-22

명소 8곳 검수본의 독립 로컬 패키지를 `prototype2/work/landmark-discovery-20260922/release-candidate/`에 구성했다. **새 배포는 하지 않았다.** 아래 공개 URL·ID는 기존 배포 기록이며 이번 작업에서 재배포하거나 현재 온라인 상태를 재확인하지 않았다.

`city_release.py --local-review`는 검수본을 로컬 실행용으로 구성하되 `check-release.mjs`에서 항상 배포 빌드를 거부한다. 이 옵션과 권리 승인/배포 결정 파일은 함께 사용할 수 없다. 일반 경로의 검수본 거부 및 정합·품질 승인 조건은 유지된다. 명소 모듈 누락을 수정했고, 상대 JS import가 패키지 안에서 모두 해석되는지 검사한다. 매니페스트 `experience: "discovery"`에 따라 새 명소 UI를 연결하며, 기존 지도 패키지와 호환된다. 자세한 화면·검증은 [명소 탐색 문서](LANDMARK_DISCOVERY.md)를 참고한다.

이하 구성과 실제 공개 배포 기록은 2026-09-16 기준이다.

기록 기준: 2026-09-16. 현재 코드와 실제 연결 기록을 기준으로 작성했다.
**공개 배포 완료:** https://pixel-city-beta-six.vercel.app · 지도와 실제 AI 가이드 활성화.
첫 배포가 Vercel에 의해 자동으로 production에 배정됐다. 로그인 없는 HTTP 200 및 가이드 GET 활성 상태를 확인했다.
배포 ID: `dpl_89UxqmtNLCoyFZGGT7jy6Z9Fi4Dc`.

경복궁–광화문–종각 고밀도 확장은 [DENSE_CITY.md](DENSE_CITY.md)에 별도로 기록한다.
2026-09-17 승인된 실패 구역1회 재생성까지 성공해 배경24/24조각과 랜드마크 합성 후보를 확보했다.4608×3072 전체 빈 영역0픽셀. 총28회 시도/27회 성공, 확정$2.316011·기존 미확정 예약$0.75 포함$3.066011. 구조/경계/랜드마크 검수와 실제 지도 통합 시험이 남아 새 지도 배포는 하지 않았다. 최신 시안은 로컬 `prototype2/work/dense-city-20260916-source/dense_full_24_preview.png`다.
새 지도는 배포하지 않았으며 위 공개 URL의 기존 종로2칸 지도는 교체하지 않았다.

## 구성

| 역할 | 구성 | 실행 위치 |
|---|---|---|
| 지도·도감·검색·차량·비 효과 | 기존 HTML / JavaScript / Canvas | 브라우저 |
| 정적 파일 | 지도 PNG, 정제 관광 JSON, JS/CSS, 폰트 | Vercel 정적 호스팅 |
| AI 가이드 | Node.js 24.x, `api/guide.mjs` | Vercel Function |
| 영구 예산·요청 제한 | Upstash Redis, REST + 원자적 Lua | 별도 관리형 Redis |
| 언어 모델 | OpenRouter → OpenAI, `openai/gpt-5.6-luna` | 외부 API |
| 도감 저장 | `localStorage` | 사용자의 현재 브라우저 |
| AI 지도 이미지 생성 | 기존 오프라인 생성 파이프라인 | 배포 서버 밖 |

Next.js 전환, GPU 서버, 계정/방문 인증, 실시간 날씨, 실제 길찾기는 포함하지 않는다.
이미지 생성 작업은 방문자의 요청으로 실행되지 않는다. 가이드가 꺼져도 지도·도감은 동작한다.

## 계정 및 리소스

| 항목 | 값 |
|---|---|
| Vercel 로그인 계정 | `hoyun-y` |
| Vercel scope | `hoyun-ryu-s-projects` |
| 전용 프로젝트 | `pixel-city-beta` |
| 프로젝트 ID | `prj_ODMjqiTaCUDNvriJX5jqTOD7Uh3p` |
| Redis 이름 | `pixel-city-guide-budget` |
| Redis 리소스 ID | `store_rHTOrWyB1cCjyvoN` |
| Redis 플랜 / 확인 상태 | `Free` / `available` |
| Redis 연결 환경 | production, preview, development |
| 공개 URL / 커스텀 도메인 | `https://pixel-city-beta-six.vercel.app` / 설정하지 않음 |

[Vercel 프로젝트](https://vercel.com/hoyun-ryu-s-projects/pixel-city-beta) ·
[Redis 관리 화면](https://vercel.com/hoyun-ryu-s-projects/~/stores/integration/store_rHTOrWyB1cCjyvoN)

Redis 생성 요청에는 `primaryRegion=hnd1`, `autoUpgrade=false`, `eviction=false`,
`prodPack=false`를 명시했다. CLI inspect로 확인한 항목은 Free 플랜·available 상태·프로젝트 연결이다.
세부 옵션은 관리 화면에서도 확인한 뒤 운영한다. Vercel Function 리전은 현재 생성 설정에서 별도로 지정하지 않았다.
Redis의 Free 플랜과 Vercel 계정의 요금제는 별개다. Vercel 요금제는 이 문서에서 확정하지 않는다.
다른 프로젝트의 환경변수·도메인·배포 보호 설정은 변경하지 않는다.

## 코드와 배포 산출물

- [관광 데이터·지도 스냅샷 생성](../prototype2/scripts/city_snapshot.py)
- [공개 패키지 생성](../prototype2/scripts/city_release.py)
- [가이드 API 진입점](../prototype2/api/guide.mjs)
- [가이드 처리](../prototype2/server/guide.mjs) / [Redis 예산 제어](../prototype2/server/budget.mjs)
- [로컬 서버](../prototype2/server/dev.mjs)

실제 배포 패키지: `prototype2/work/city-release-20260916-v5`.
초기 빌드의 Function 리전은 `iad1`로 표시됐다.
후속 코드 변경을 반영하려면 기존 후보를 덮어쓰지 말고 새 후보를 만든다.
**저장소 루트나 prototype2 전체를 Vercel에 업로드하지 않는다.**

패키지 생성기가 만드는 설정:

| 설정 | 값 |
|---|---|
| Framework | 지정하지 않음 (`null`) |
| Node.js | `24.x` |
| Build command | `npm run build` |
| Output directory | `public` |
| Function | `api/guide.mjs`, 최대 실행 설정 35초 |
| Function 포함 데이터 | `assets/city_pilot/places.json` |
| 빌드 보호 장치 | 이용권 승인 또는 별도 사용자 지시 시험 배포 기록이 없으면 실패 |

공개 파일은 명시적 목록으로만 복사한다. 기존 PNG 7개와 보신각 PNG 4개, 정제 JSON, 필요한 JS/CSS,
폰트와 라이선스를 포함한다. 원본 캡처, 게임 참고 이미지, 프롬프트, 생성 로그,
API 키, Drive 경로, 로컬 검수 UI는 제외한다. 문서 자체도 이 웹 패키지에 포함하지 않는다.

## 서버 환경변수

| 변수 | 용도 / 현재 처리 |
|---|---|
| `GUIDE_ENABLED` | 문자열 `true`일 때만 가이드 활성 가능. 미설정은 비활성 |
| `OPENROUTER_API_KEY` | 서버 전용 추론 키. production / preview에 Secret 등록 완료 |
| `KV_REST_API_URL` | Vercel Redis 연동이 주입하는 REST 주소 |
| `KV_REST_API_TOKEN` | 쓰기 가능한 REST 토큰. 예산 예약/정산에 필요 |
| `UPSTASH_REDIS_REST_URL` | 위 URL의 대체 변수. 둘 다 있으면 이 값 우선 |
| `UPSTASH_REDIS_REST_TOKEN` | 위 토큰의 대체 변수. 둘 다 있으면 이 값 우선 |
| `GUIDE_IP_HASH_SALT` | 24자 이상 난수. IP HMAC용으로 환경 간 동일하게 유지 |

주입된 `KV_REST_API_READ_ONLY_TOKEN`은 예산 쓰기에 사용할 수 없다.
`REDIS_URL`, `KV_URL`, `VERCEL_OIDC_TOKEN`은 현재 가이드 구현에서 사용하지 않는다.
실제 토큰·비밀번호는 문서, Git, 클라이언트 JS, 로그에 기록하지 않는다.

로컬에서 받은 접속 정보는 Git 제외 경로
`prototype2/work/city-release-20260916-v3/.env.redis.local`에 있다.
`.env.local`과 `.vercel/`도 배포 업로드 대상에서 제외한다.
로컬 셸의 export만으로 Vercel 서버 환경이 설정되지는 않는다. 대상 환경별 등록·적용을 확인한다.
`GUIDE_ENABLED=true`와 동일한 `GUIDE_IP_HASH_SALT`도 production / preview에 등록했다.
로컬 활성 설정은 Git 제외 `prototype2/work/guide-live/guide.env`에 보관한다.

## 가이드 제한과 영구 원장

현재 코드의 설정값이며 가격표의 최신 시세를 의미하지 않는다.

- 모델 고정, reasoning `low`, 출력 최대 900토큰. 자동 재시도·모델 fallback 없음.
- 요청 가격 상한: 입력 $0.20 / 100만 토큰, 출력 $1.20 / 100만 토큰. 요청 전 메타데이터도 검사.
- 가이드 전체 예산 **$1**. 요청당 $0.01를 먼저 예약하고 `usage.cost`로 실제 비용 정산.
- 전체 동시 요청 2개, IP별 분당 3회·일 20회. 시간 구간은 epoch 기반 고정 구간이며 일 경계는 UTC다.
- production / preview / development와 로컬 실호출은 **같은 영구 원장·총예산**을 사용한다.
- IP 원문 대신 HMAC을 저장한다. 대화는 브라우저에서 최근 일부만 전달하며 앱 서버는 원문을 기록하지 않는다.

영구 해시 키: `pixel-city:guide:lifetime:v1`.
`used`는 달러×1,000,000 정수로, 실제 정산 비용과 미정산 예약액을 합친 금액이다.
`blocked`는 차단 여부, `completed`는 정산 완료 횟수다.
진행 중 예약은 같은 키 이름 뒤에 `:active`가 붙은 해시에 저장한다.

영구 원장은 **최초 1회 초기화 완료**했다. 기존 키를 덮어쓰거나 배포할 때마다
0으로 초기화하지 않는다. 원장 유실은 새 예산이 아니라 복구가 필요한 장애다.
`server/guide-ops.mjs status`로 비밀값 없이 누적액·차단·활성 예약을 확인한다.
운영자 검수 호출도 같은 원장에 정산하며, `smokeAttempts`는 최대 5회를 영구 제한한다.

저장소 실패, 예산 부족, 과금 미확정, 시간 초과는 가이드만 차단한다.
미정산 예약은 자동 환불·만료하지 않는다. 서버가 종료돼 활성 예약이 남으면
실제 과금 상태를 확인한 후 수동 복구하며, 확인 전 `blocked`나 예약을 지우지 않는다.

## 배포 전 조건과 절차

### 이용조건 미확정과 사용자 결정

사용자가 이용조건 미확정 상태에서도 시험 배포를 진행하도록 명시적으로 지시했다.
비영리라는 이유만으로 이용 허용이 확정되지는 않는다. [기존 검토](CITY_BETA.md#1-vworld-파생-지도-공개-허용)는 미해결 상태로 유지한다.
`publicRightsApproved=false`, `rightsVerified=false`, `userDirectedPilot=true`로 구분했다.
승인 기록을 형식상 true로 바꾸지 않았다. 지시 기록은 Git 제외
`prototype2/work/deployment-decision-20260916.json`이며 대상 기본 이미지 해시와 사용자 지시를 포함한다.
이 기록은 권리자의 허가나 법적 적합성 확인을 대체하지 않는다.

### 로컬 확인

다음 명령은 저장소 루트에서 실행한다.

```sh
prototype2/.venv/bin/python prototype2/scripts/city_snapshot.py
prototype2/.venv/bin/python prototype2/scripts/city_reveal.py --source prototype2/work/bosingak-reveal-20260916
node prototype2/server/dev.mjs
```

<http://127.0.0.1:8768/>에서 지도와 기능을 확인한다. 키와 원장이 없으면 가이드가 비활성인 것이 정상이다.

### 새 후보 구성

```sh
prototype2/.venv/bin/python prototype2/scripts/city_release.py --dest prototype2/work/city-release-NEW
```

위 명령은 승인되지 않은 로컬 후보만 만든다. 공개 허용 근거가 준비되면
`--rights-approval`로 승인 기록 JSON 경로를 추가한다. 필요한 필드는
`approved`, `finalSha256`, `evidence`이며 정확한 검사는 패키지 생성기를 따른다.
이번 시험은 대신 `--deployment-decision prototype2/work/deployment-decision-20260916.json`을 사용했다.
단순 재배포를 위해 새로운 허가를 추정하거나 권리 확인 값을 변경하지 않는다.

허용 근거 또는 명시적 시험 배포 지시가 기록된 새 후보만 전용 프로젝트에 연결한다 (`NEW`는 새 폴더명으로 바꾼다).

```sh
vercel link --project pixel-city-beta --scope hoyun-ryu-s-projects --yes --cwd prototype2/work/city-release-NEW
```

그 후 후보 폴더에서 빌드 가드·파일 목록·비밀정보 제외를 확인하고 Vercel 검증 배포를 진행한다.
로그아웃 상태의 공개 접근, 모바일 정적 이미지/폰트 로딩, 가이드 활성·비활성 양쪽을 검증한 뒤
production으로 승격한다. 첫 배포 후에는 이 문서에 실제 URL·배포 ID·검증일을 추가한다.
커스텀 도메인이나 다른 프로젝트 설정을 변경할 필요는 없다.

## 검증과 장애 대응

```sh
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests -p 'test_*.py'
node --test prototype2/tests/test_*.mjs
prototype2/.venv/bin/python prototype2/tests/city_browser_check.py
node --env-file=prototype2/work/city-release-20260916-v3/.env.redis.local prototype2/tests/city_redis_check.mjs
```

기록상 Python 122개, Node 14개 및 데스크톱/모바일 모의 가이드 시험을 통과했다.
실 Redis에서는 동시 10요청 중 2개 허용, 분당/일 제한, $1 상한, 과금 미확정 차단을 확인했다.
실제 AI 가이드는 로컬 3회에서 소개·현시점 정보 미확인·자료 없는 경로 요청 거절을 확인했다.
공개 배포 주소에서도 보신각 질문 1회 성공(3.854초), 총 4회 $0.002426 정산·미정산0을 확인했다.
공개 주소 데스크톱/모바일 UI 회귀도 통과했다. 상세 비용과 최종 검증은 [베타 기록](CITY_BETA.md)에 남긴다.
Redis 제한 시험 자체는 유료 모델을 호출하지 않는다.

| 증상 | 확인 / 대응 |
|---|---|
| 지도는 나오는데 가이드 비활성 | `/api/guide` GET 상태, 활성 변수, 쓰기 토큰, salt, 영구 원장 확인 |
| 가이드 503 | 예산·요청 제한·원장 상태·제공자 가격/응답을 확인. 무작정 재시도하지 않음 |
| 배포 빌드의 권한 검사 실패 | 공개 허용 근거와 대상 이미지 해시 확인. 가드를 제거하지 않음 |
| 지도/폰트 404 | `public` 출력 경로, 명시적 파일 목록, 배포 후보를 확인 |
| 과금 미확정 또는 활성 예약 잔류 | 가이드를 끄고 실제 사용 내역 확인. 임의 환불·원장 삭제 금지 |

가이드 중단은 `GUIDE_ENABLED`를 끄고 대상 배포에 반영하는 방식으로 한다.
문제가 생긴 배포는 검증된 이전 배포가 있을 때만 되돌린다. 롤백해도 Redis 누적 예산은 유지한다.
무료 리소스를 유료 플랜으로 바꾸거나 자동 업그레이드를 켜려면 별도 승인을 받는다.

관련 문서: [베타 구현·검수 기록](CITY_BETA.md), [TourAPI 원본 위치와 활용](TOURAPI_DATA.md).
