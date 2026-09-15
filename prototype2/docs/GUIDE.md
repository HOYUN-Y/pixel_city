# prototype2 상세 실행·실험 안내

서울의 건물·도로 배치를 유지하면서 외관을 선명한 픽셀 그래픽으로 재해석한다.
로컬 추론 이력과 명시적으로 승인된 OpenRouter 시험을 분리한다. 최신 시험은 이미지형 2×2 지도 위의
장소·경로·캐릭터·수작업 가림과 남산3×3 확장, 독립 랜드마크 합성이다. 기존 객체형 지도도 보존하며 지도 조작 중에는 AI 호출을 하지 않는다.

## 최신 생성 시험 — 광화문·종로타워 (2026-09-15)

후속 [종로타워 2칸 연결·노을 시험](http://127.0.0.1:8766/web/pilot/?view=landmark-link&run=20260915T130211965290Z)이 추가됐다.
배경2장·1792×1024px, 기존 타워/차량 재사용, 낮↔노을과 타워 지면 그림자 미리보기다.
생성2회/$0.161325에서 종료. 전체 지리 정합은 미통과이며 실제 일조/날씨 연동이 아니다.
[사용법·미달 사항](landmark-link-20260915.md) · [감사 기록](landmark-link-20260915.json)

[시험 화면](http://127.0.0.1:8766/web/pilot/?view=landmark-pilot&run=20260914T144245416491Z&scene=jongno-tower) · [상세 결과·사용법](landmark-pilot-20260915.md) · [감사 기록](landmark-pilot-20260915.json)

VWorld 고정 정사영 원본에서 배경과 투명 랜드마크를 별도로 생성했다. 두 장소는 아직 연결된 지도가 아니다.
총5회/$0.408161, 생성 종료. 장소 선택·원본/배경/합성 비교·45초 산책·실제 알파 가림을 시험한다.
종로타워 외곽 크기·앵커는 균일 배치 보정 후 기준을 통과했으나 내부 빈 공간 원본 정렬은 미달이다.
광화문 크기 비율은 미달이고 두 배경의 도로 정합은 미검증이다. 모두 비교 후보이며 사용자 미감은 미승인이다.
Python110개·Node7개 계약 시험과 실제 4화면×2장소 브라우저 검증 통과. 기본 지도·원격 저장소는 변경하지 않는다.

## 최신 생성 시험 — 남산 3×3 확장 (2026-09-14)

사용자가 원본 외관 누락 안내 후 AI 생성을 요청하여, 부족한 높이·외관을 **AI 추정**으로 구분해 생성했다.
지도5장·국소보정1장·양방향차량1장, 총7회/$0.566248. 남은 보정1회는 사용하지 않고 생성을 닫았다.

- [3×3 지도·차량 시험 열기](http://127.0.0.1:8766/web/pilot/?view=projection-expand&run=20260914T131603270823Z)
- [완성 후보 PNG](../eval/vworld/projection_expand/runs/20260914T131603270823Z/final.png)
- [원본·보정 전·최종 비교](../eval/vworld/projection_expand/runs/20260914T131603270823Z/index.html) · [상세 기록](namsan-expansion-20260914.md)

처음에는 전체 지도·정지 상태다. **지도 검수 → 도로 보기 → 차량 재생**으로 경계를 넘는4대를 본다.
타워 선택·기존 남산 산책도 유지한다. 원본 비교 중에는 상호작용이 정지하며 최대100%/검수200%다.
도로·차량 크기는 수작업 그림 좌표다. 실제 도로 정합, 모든5칸 축척/너비 오차 및 사용자 미감은 미승인이다.
이번 작업은 로컬 브랜치/커밋만 진행하며 병합·푸시·기존 기본 지도 변경은 하지 않는다.

## 최근 완성 시험 — 정사영 남산 산책·타워 선택 (2026-09-14)

- [산책 시험 열기](http://127.0.0.1:8766/web/pilot/?view=projection-walk&run=20260914T115537004661Z)
- [수작업 경로·가림 및 검증](../eval/vworld/projection_walk/runs/20260914T115537004661Z/index.html) · [Git 보존 기록](projection-walk-20260914.json)

현재 화풍을 **잠정 사용**한 상호작용 시험이다. 추가 AI 생성·외부 GPU·API 과금은 0회다.
부모 `20260914T093846326385Z`의 최종 배경을 바이트 그대로 복사하고 기존 캐릭터를 재사용했다.
기존 기본 지도 `20260914T084137369841Z`와 정사영 비교 화면은 유지한다.

흰색 N서울타워나 **지도 검수 → 장소 → N서울타워**를 선택하면 윤곽과 정보 패널을 표시한다.
주황색 철탑은 선택 대상이 아니다. 타워 숨김·이동·회전·조명과 차량은 제공하지 않는다.
**지도 검수 → 캐릭터 재생**으로 산책하며 재생/일시정지·처음으로·위치 슬라이더·따라가기·경로/캐릭터 표시를 조작한다.
기본은 정지, 전체 코스는 45초 단회 재생 후 멈춘다. 다시 재생하면 처음부터 시작한다.
모바일 첫 화면은 타워 중심이므로 서쪽 시작점의 캐릭터가 화면 밖일 수 있다. 따라가기를 켜고 재생하면 보인다.

산책로의 서쪽/동쪽은 실제 명소가 아닌 시험 지점이다. 가려진 기단 뒤 연결은 수작업 추정이며
실제 접근성·보행 시간·경사·충돌 판정·거리 정보가 아니다. 캐릭터 크기도 실측 축척이 아닌 가독성용 표현이다.
기단·수목·주황색 철탑 가림을 적용한다. 완전가림은 **타워 기단**에서 검증했고, 수목과 철탑에서는 부분가림을 검증했다.
계획의 수목 완전가림은 현재 캐릭터가 수관보다 커서 확보하지 못했다. 검증을 통과시키려고 수관 윤곽을 확대하지 않았다.

원본/보정 전에서는 상호작용이 비활성화되고, 최종으로 돌아와도 자동 재생하지 않는다.
확대 상한은 일반 100%, 디버그 200%다. 탭 비활성 시 진행을 멈추고 복귀 시 시간차로 건너뛰지 않는다.
추가 인터페이스는 `landmark.mode=highlight_only`, `route.playback=once`이며 기존 분리형 타워·반복 재생 기본값은 유지한다.

검증: Python 85개·Node 계약 5종, 기존 브라우저 4종 및 새 시험 4개 화면(DPR 1·2·3, reduced-motion).
배경 효과를 모두 끈 캔버스는 직접 그린 원본과 전체 픽셀이 같았다. 101개 위치 샘플에서 비가림·부분·완전가림을 확인했다.
핀치와 탭 비활성 검증은 브라우저에 합성 이벤트를 전달한 검사이며 실제 OS 조작과 구분한다.
타워/배경/철탑 선택, 드래그 오클릭, 재생 종료·정지·초기화, 원본 전환, 누락 파일·해시 오류와 외부 요청 0건을 검증했다.

```bash
# 모두 오프라인 — 새 실행 생성 또는 저장 결과 검증
prototype2/.venv/bin/python prototype2/scripts/projection_walk.py build
prototype2/.venv/bin/python prototype2/scripts/projection_walk.py verify --run 20260914T115537004661Z
prototype2/.venv/bin/python prototype2/tests/projection_walk_browser_check.py --run 20260914T115537004661Z
```

입력 좌표는 `configs/projection_walk.json`, 이미지·캡처·전체 검증은 `eval/vworld/projection_walk/runs/<run>/`에 보존한다.
초기 경로 점검 실행 2개도 로컬에 남기며 최신 전달 대상은 위 실행이다. 원본·에셋이 없는 checkout은 명시적 오류를 표시한다.
미감 승인과 전체 구조 검증은 여전히 미완료이며, 이 시험이 새 지역 확장이나 실제 길찾기 승인을 뜻하지 않는다.

## 보존한 시험 — 정사영 남산 2×2 픽셀 지도 (2026-09-14)

- [지도에서 보기: 이동·줌·원본/보정 전/최종 전환](http://127.0.0.1:8766/web/pilot/?view=projection-lab&run=20260914T093846326385Z)
- [완성 후보 PNG](../eval/vworld/orthographic_lab/runs/20260914T093846326385Z/mosaic.png) · [원본·후보·실제 프롬프트 비교](../eval/vworld/orthographic_lab/runs/20260914T093846326385Z/index.html)
- [Git 보존 생성·검증 기록](orthographic-lab-20260914.json)

사용자가 정사영 원본의 텍스처 한계를 감수한 실험용 AI 입력과 남산 2×2 생성을 승인했다.
실행 `20260914T093846326385Z`는 기본 4장 + 숲 수평 연결 보정 1회, **총 5회 / 282.694초 / $0.423610**다.
기존 OpenRouter `openai/gpt-image-2.5-sunburst` / OpenAI 제공업체 고정, high, 1:1, 원출력별 1024²를 사용했다.
최대 6회 중 타워 보정 1회는 불필요해 사용하지 않았고 실행을 닫았다. 추가 유료 호출·재시도는 하지 않는다.

### 원본과 결과의 축척

정사영 원본은 `20260914T091414062775Z/orthographic.png`다. 기존 768px 조각/192px 원본 겹침을 재사용하며,
1024px 생성물의 256px 겹침을 문맥으로 전달하고 이미 생성한 픽셀을 합성 단계에서 보존했다.
최종 1536²는 원본 중앙 `[192,256,1344,1408]`의 4/3 확대다. 원본 전체 1600m 폭을 담은 결과가 아니다.
원본의 100m 투영 길이는 해당 배율에서 128px다. AI 결과가 정확히 이 축척을 지킨다는 보증은 아니다.

타워·경사면과 큰 도시 구도는 대체로 유지되었다. 왼쪽 수평 연결부의 수관 연결 보정만 채택했다.
오른쪽 숲의 밀도 변화와 일부 건물 연결·주거지·도로 재해석은 남는다. 실제 외벽 복원이 아니다.
타워는 이번 결과에서 배경 그림의 일부이며, 기존 독립 타워·차량·보행 경로는 이 그림에 옮기지 않았다.

### 검증과 한계

- 기술 검증 통과: 원출력 SHA-256, 겹침 고정, 보정 영역 밖 불변, 최종 합성과 3종 줌 피라미드 재검증.
- 생성 전 수작업 기준점: 타워 2점·도로 8점·건물 선분 6개. 원본이 불명확하거나 재해석 뒤 대응이 어려운 도로 3점과 건물 2개는 null로 기록했다.
- 식별 가능한 7개 위치의 오차 중앙값 약 2.85px·최대 약 6.55px, 타워 길이 약 −3.4%다. 수작업 근사 표식에 따른 **부분 대리 지표**이며 정확한 실측이나 전체 구조 보존 판정이 아니다.
- 전체 구조는 **미검증**, 사용자 미감은 **미승인**이다. 누락 기준점을 제외하고 통과라고 보고하지 않는다.
- Python 82개·Node 계약 4종·기존 브라우저 4종 및 새 시험의 데스크톱/태블릿/모바일/DPR 2·3 검증. 브라우저 외부 요청·변경 요청·오류 0건.

지도 검수에서 원본·보정 전·최종을 같은 중심/배율로 전환할 수 있다. 일반 확대는 100% 상한,
200%는 디버그 전용이다. 표시되는 생성 연결선은 실제 고정 픽셀 경계인 x/y=896이며 명목 조각 중앙 768과 구분한다.
기존 원근 그림은 참고 링크로만 비교하며 같은 지리 범위의 정합 비교라고 표시하지 않는다.

```bash
# 과금 없는 로컬 재검증/비교 화면 갱신
prototype2/.venv/bin/python prototype2/scripts/orthographic_lab.py verify --run 20260914T093846326385Z
prototype2/.venv/bin/python prototype2/scripts/orthographic_lab.py publish --run 20260914T093846326385Z
prototype2/.venv/bin/python prototype2/tests/pilot_browser_check.py --projection --run 20260914T093846326385Z
```

원본·출력·전체 요청 기록·수작업 검수·캡처는 `eval/vworld/orthographic_lab/runs/<run>/`에 Git 제외 로컬 보존한다.
`approved_run.json`은 이번 한 번의 승인에 연결되며 재초기화로 예산을 새로 만들지 않는다.
기본 실행 `20260914T084137369841Z`, prototype1, README는 그대로다. 새 checkout에는 이미지가 없으므로
명확한 로컬 생성물 누락 오류를 표시한다. 공개 호스팅·재배포는 하지 않았다.

## 보존한 시험 — 남산 원근·정사영 원본 비교 (2026-09-14)

[비교 화면 열기](http://127.0.0.1:8766/eval/vworld/projection_probe/runs/20260914T091414062775Z/index.html) · [Git 보존 검증 기록](projection-probe-20260914.json)

이번 산출물은 **픽셀 AI 완성본이 아닌 VWorld 원본 비교**다. AI 호출은 0회다.
같은 카메라 위치·방향에서 원근과 정사영을 촬영했으며 중심 기준 폭은 1600m, 출력은 1536²/DPR 1이다.
중심 126.98808, 37.55112, heading 22.5°, pitch −30°, 거리 1800m, near/far 1/10000m.
현장에서 안정화한 지형 높이 251.33766693105997m에 80m를 더한 목표점을 양쪽에 공통 적용했다.

| 월드 100m 기준선의 투영 길이 | 앞 | 중간 | 뒤 |
| --- | ---: | ---: | ---: |
| 원근 | 123.43px | 96.00px | 78.55px |
| 정사영 | 96.00px | 96.00px | 96.00px |

카메라 깊이 −400/0/+400m에 둔 실제 월드 좌표 끝점을 SceneTransforms로 투영한 길이다.
고정 길이의 화면 장식이나 건물 픽셀 인식 측정이 아니다. 기준선 토글로 위치를 확인할 수 있다.
실제 frustum과 projection matrix, 초기/반복/최종 카메라를 함께 검사했다. 두 화면의 전체 지리 범위는 같지 않다.
맞춤/100%는 양쪽에 함께 적용된다. 정사영도 높이와 경사 표현은 남으며 모든 건물이 같은 크기가 된다는 뜻은 아니다.

**투영 검증은 통과, AI 입력 승인은 보류**다. 타워와 경사면은 보이지만 일부 외벽은 검거나 텍스처가 불완전하다.
원근은 제한 시간 내 globe.tilesLoaded가 true가 되지 않았고, 상단에 검은 영역이 있다.
정사영의 globe.tilesLoaded=true도 별도 건물 레이어가 완성되었다는 보증은 아니다. 사용자 미감 승인은 아직 없다.
원본을 AI로 옮겨도 축척 유지가 자동 보장되지는 않으므로 후속 생성에는 별도 구조 검증이 필요하다.

첫 진단 실행 `20260914T091028751265Z`는 SDK의 지연 카메라 이동으로 양쪽 카메라가 달라 실패했다.
초기 SDK/지형 안정화와 설정 직후 카메라 기준 검사를 보강한 뒤 위 실행에서 재검증했다. 실패 원본도 로컬 보존했다.
기본 지도는 기존 `20260914T084137369841Z`이며 타워·차량·prototype1·README는 변경하지 않았다.

```bash
# 저장 원본만 재검증/비교 페이지 갱신 — 외부 요청 없음
prototype2/.venv/bin/python prototype2/scripts/projection_probe.py verify --run 20260914T091414062775Z
prototype2/.venv/bin/python prototype2/scripts/projection_probe.py report --run 20260914T091414062775Z
# 새 VWorld 촬영만 실행 — 환경변수 VWORLD_API_KEY 필요, AI 요청 없음
prototype2/.venv/bin/python prototype2/scripts/projection_probe.py capture --allow-external
```

원본·비교 HTML·전체 샘플·브라우저 QA는 `eval/vworld/projection_probe/runs/<run>/`에 로컬 보존한다(Git 제외).
키 포함 SDK HTML은 메모리와 일시 로컬 서버에서만 사용한다. 지형 조회 실패 시 예전 높이로 대체하지 않는다.
새 촬영은 모드별 최대 90초의 대기 예산을 사용하며 첫 모드에는 SDK/지형 초기화가 포함된다.

## 기존 기본 결과 — 독립 남산타워·풍경용 차량 (2026-09-14)

- [차량 주행](http://127.0.0.1:8766/web/pilot/?view=seam-lab&scene=downtown&run=20260914T084137369841Z): 좌하단 지도 검수 → **도로 보기**. 양방향 각 2대, 총 4대가 이동한다.
- [남산타워 조작](http://127.0.0.1:8766/web/pilot/?view=seam-lab&scene=namsan&run=20260914T084137369841Z): 지도 검수 → **타워 보기**, 또는 타워 본체 클릭. 조명·숨김·복원을 시험한다.
- [표시/숨김 및 차량 원출력 비교](../eval/vworld/seam_lab/runs/20260914T084137369841Z/index.html)
- [Git 보존 생성·검증 기록](living-lab-20260914.json)

새 실행 `20260914T084137369841Z`는 이전 2×2 실행의 이미지를 그대로 이어받았다.
추가 OpenRouter 요청은 **2회 / 89.178초 / $0.135817**: 타워 뒤 배경 1회, 동일 차량의 양방향 이미지 1회.
기존 모델·OpenAI 제공업체 고정, high, 1:1, 출력별 1024²를 사용했다. 추가 호출·재시도는 하지 않았다.
입력은 기존 AI 남산 그림 crop과 제거 안내 마스크, 차량용 기존 AI 덕수궁 화풍 참고이며 새 VWorld 촬영은 없다.

### 무엇이 독립 객체인가

일반 건물·도로·숲은 여전히 배경 그림이다. 흰색 N서울타워만 원본 픽셀과 수작업 마스크로 분리했다.
옆의 주황색 철탑은 분리 대상이 아니다. 타워 표시·조명 꺼짐 상태의 바탕 합성은 기존 그림과 픽셀 단위로 같다.
안테나·기단 가장자리 잔상을 없애기 위해 제거 영역 주변 7px와 그림자를 복원 레이어에 포함했으며,
클릭 판정은 타워 실루엣만 사용한다. 조명은 전망대의 지정된 두 영역에만 켜진다.

타워를 숨기면 보행 캐릭터의 타워 기단 가림도 해제된다. 숨김 뒤 숲·돌담·공터는 **AI 추정**이며
실제 숨겨진 지형 복원이 아니다. 복원부는 주변보다 일부 부드럽고 나무 배치·돌담 연결의 재해석이 남는다.
타워를 이동·회전하거나 모든 면을 재구성하는 3D 객체는 아니다.

차량은 수작업으로 정한 그림 위 두 경로를 28 이미지 px/초로 이동한다. 실제 차선·속도·통행방향 정보가 아니다.
경로 끝은 약 12px 구간에서 사라졌다 나타나며, 신호·정체·교차로 판단은 없다. 같은 차선은 동일 속도·고정 간격이다.
원본 차량의 투명 알파와 광택 테두리는 보존했고 런타임만 최대 32²로 축소·이진 알파 처리했다.
그림의 도로가 노란 포장처럼 보이는 문제는 이번에 수정하지 않았다.

차량은 기본 재생하지만 reduced-motion 설정에서는 정지한다. 차량 일시정지·숨김·위치 슬라이더가 있고,
숨겨진 탭에서는 시간이 진행되지 않는다. 기존 보행 캐릭터는 계속 기본 정지다. 비교 모드에서는 상호작용을 끈다.
이미지·객체 데이터 해시 검증을 통과해야 표시하며 지도 조작 중에는 외부 API 요청이 없다.

### 보존 및 재검증

원본·생성물은 Git 제외 로컬 폴더 `prototype2/eval/vworld/seam_lab/runs/20260914T084137369841Z/`에 있다.
새 checkout에는 이 데이터가 없으므로 기존 객체 데모를 사용할 수 있다. 기존 실행·README·prototype1은 보존했다.
다음 명령은 추가 과금 없이 실행한다(Node 22 이상).

```bash
prototype2/.venv/bin/python prototype2/scripts/living_lab.py verify --run 20260914T084137369841Z
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests -p 'test_*.py'
node prototype2/tests/test_living_core.mjs
prototype2/.venv/bin/python prototype2/tests/living_browser_check.py --run 20260914T084137369841Z
```

`build`는 해당 실행에 고정된 시각 검수 설정으로 오프라인 합성한다. `activate`는 현재 manifest와 일치하는
브라우저 검증 기록이 있어야 기본 실행을 전환한다. 이번 2회 한도는 소진됐으며 새 생성은 별도 승인 대상이다.

## 보존한 결과 — 연결·남산·캐릭터 시험 (2026-09-14)

- [덕수궁 시험](http://127.0.0.1:8766/web/pilot/?view=seam-lab&scene=downtown)
- [남산·타워 시험](http://127.0.0.1:8766/web/pilot/?view=seam-lab&scene=namsan)
- [원본·기존·문맥 연결·보정 비교](../eval/vworld/seam_lab/runs/20260913T173009999136Z/index.html)
- [전체 프롬프트·입력 해시·비용](../eval/vworld/seam_lab/runs/20260913T173009999136Z/report.json)
- [Git에 보존한 프롬프트·해시·비용·검증 기록](seam-lab-20260914.json)
- [보존 영역 및 실제 연결선 검증](../eval/vworld/seam_lab/runs/20260913T173009999136Z/verification.json)

실행 `20260913T173009999136Z`: **12회 / 579.191초 / $0.976156**. 승인된 한도를 모두 사용했으며
추가 생성·재시도·모델 우회는 하지 않았다. 네이티브 1024² 지도 8장, 덕수궁 경계 보정 2장,
남산타워 보정 1장, 공유 투명 캐릭터 1장이다. 요청 시간은 합계이며 구현·검수 시간은 포함하지 않는다.

### 결과 해석

- 덕수궁: 이웃 문맥과 강제 픽셀 보존으로 연결하고 경계 두 곳을 보정했다. 보정 전보다 단절이 완화된
  후보지만 도로가 노란 보행로처럼 바뀌고 수목·외관이 재해석되는 문제는 남는다. 완벽한 연결이나 실측 정합 통과가 아니다.
- 남산: 새 VWorld 캡처의 정상·능선·사면과 타워의 기둥·전망대·안테나가 읽힌다. 보정에서 타워 상단의
  불필요한 가로 돌출을 줄였다. 암벽·숲·원거리 주택은 AI 해석이며 정확한 지형 복원으로 볼 수 없다.
- 촬영 중심의 지형 높이는 약 251m로 조회됐다. 0m 고정 카메라 대신 지형 높이를 반영했다.
  VWorld 전체 `tilesLoaded`는 false여서 전경을 시각 검수한 범위만 사용했다. 원거리 텍스처는 거칠다.
- 미감 승인은 사용자 검수 대기다. Isopolis 전용 LoRA를 학습한 결과가 아니며 전체 서울로 확장하지 않았다.

### 생성·합성 구조

25% 겹치는 동일 원본 crop을 좌상→우상→좌하→우하로 생성한다. 원본·화풍·기존 결과를 얹은 문맥·
흑백 문맥 안내 이미지를 입력하고 남산에는 같은 원본의 타워 세부 crop을 추가한다.
마스크 전용 API 파라미터가 아니라 **참고 이미지에 의한 편집 유도**다. 이미 확정한 픽셀은 로컬 합성으로
보존하며 원래 격자(768px)와 실제 새 영역 경계(896px)를 모두 기록한다.

보정 후보의 지정 영역만 교체하고 바깥 픽셀은 유지한다. RGB 경계 차이는 진단값이며 건물·지형 연결의
합격 점수가 아니다. 지도 최초 8개 출력은 디코딩한 RGB 픽셀을 PNG로 보존했고, 보정·캐릭터 4개는
응답 원본 바이트를 보존했다. 캐릭터 원본 알파는 유지하고 런타임만 축소·이진 알파 처리해 광택 테두리를 줄인다.

### 조작과 제약

1. 좌하단 **지도 검수**에서 장면·비교 결과를 선택한다. 기본 최대 100%, 검수용 200%다.
2. 지도 핀 또는 장소 목록을 선택하면 상세 창/모바일 시트가 열린다. ‘지도에서 보기’로 이동한다.
3. ‘시험 코스’ 또는 ‘다음 장소’로 장면별 3개 지점을 확인한다.
4. ‘캐릭터 재생’은 45초 순환 경로를 따라 움직인다. 따라가기·일시정지·위치 슬라이더로 가림을 확인한다.

덕수궁 건물 2곳, 남산 타워 기단과 수목 2곳의 가림 윤곽을 수기로 지정했다. 경로 구간의 앞/뒤 정보로
캐릭터와 겹친 부분만 가린다. **고도·깊이를 추론한 것이 아니며 실제 길찾기나 보행 가능성을 보증하지 않는다.**
캐릭터는 동일 스프라이트 이동·좌우 반전·작은 상하 움직임이며 방향별 보행 프레임은 없다.
기본 자동 재생은 꺼져 있고 숨겨진 탭에서는 애니메이션을 중단한다.

가림·장소 데이터는 최종 후보의 해시에 고정되며 브라우저도 이미지 SHA-256을 검증한다.
원본/다른 후보 비교에서는 상호작용을 비활성화한다. AI 대화·업로드·방문 인증은 계속 미연결이다.

### 실행·검증·재현

README의 서버 명령은 저장소 루트에서 실행한다. 새 지도는 Git 제외 로컬 생성물이 필요하고,
없으면 명확한 오류를 표시한다. 새 checkout에서도 바로 보는 화면은 기존 객체 데모다.
원본과 타워 참고는 `prototype2/work/vworld/seam_lab/20260913T172824302822Z/`,
생성·합성·검수 파일은 `prototype2/eval/vworld/seam_lab/runs/20260913T173009999136Z/`에 있다.

다음은 **추가 과금 없는** 명령이다.
JavaScript 검증은 Node 22 이상을 사용한다. Node 20.15 환경에서는 `.mjs` 검증 명령에
`--experimental-default-type=module`을 추가한다(Node 24에는 해당 옵션을 넣지 않는다).

```bash
prototype2/.venv/bin/python prototype2/scripts/seam_lab.py publish --run 20260913T173009999136Z
prototype2/.venv/bin/python prototype2/scripts/seam_lab.py verify --run 20260913T173009999136Z
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests -p 'test_*.py'
node prototype2/tests/test_lab_core.mjs
prototype2/.venv/bin/python prototype2/tests/lab_browser_check.py --run 20260913T173009999136Z
```

새 생성 절차는 `capture`→원본 시각 검수→설정 해시 확인→`init`→`scene --scene downtown|namsan`→
`repair --scene ... --number ...`→`character`→시각 검수/가림 설정→`publish`→`verify`다.
외부 단계에는 `--allow-external`과 해당 환경변수 키가 필요하다. **이번 12회는 소진됐으므로 새 유료 실행은
별도 승인 대상**이다. 진행 중/실패 요청이 남거나 같은 이름을 다시 호출하면 중단한다. 동시 생성은 파일 잠금으로 막는다.
검수 설정은 특정 실행에 고정되어 새 결과에 자동 적용되지 않는다. 원본·모델·키·화풍 참고는 Git에 올리지 않는다.

## 보존한 결과 — 객체형 지도와 AI 에셋 6종 (2026-09-14)

- [객체형 지도 열기](http://127.0.0.1:8766/web/pilot/?view=objects)
- [생성 외관·기본 도형·반복 타일 비교](../assets/object_pilot/index.html)
- [실제 프롬프트와 비용](../assets/object_pilot/generation.json) · [장면 매니페스트](../assets/object_pilot/manifest.json) · [시각 검수 기록](../assets/object_pilot/review.json)

덕수궁 북측 18개 건물의 위치·윤곽·높이를 고정 스냅샷에서 가져왔다. 외관은 실제 벽면 복원이 아니라
사용자 화풍 참고에 따른 AI 재해석이다. 건물 4628(목조)·4577(저층)·4485(현대식)와
아스팔트·보도블록·궁궐 돌바닥을 **총 6회**, 추가 호출 없이 생성했다.

실행 `20260913T163032352584Z`: 요청 시간 합계 **234.937초**, 실제 비용 **$0.385141**.
OpenRouter / `openai/gpt-image-2.5-sunburst`, OpenAI 제공업체 고정, high, 1:1, 요청별 1장.
건물에는 도형 렌더와 화풍 참고 두 장, 바닥에는 화풍 참고 한 장만 전송했다. VWorld 캡처·GUI는 전송하지 않았다.

**윤곽 검사 1/3 통과, 미감 미승인.** 원입력 전체 알파 IoU는 현대식 0.9914, 저층 0.9180,
목조 0.8307이다. 사전 기준 0.95에 못 미친 두 건물은 지도에서 기본 도형으로 표시하고,
AI 원형은 별도 비교 화면에 남겼다. 원출력의 주변 광택/반투명 영역도 원본에는 보존한다.
채택 후보만 고정 도형 마스크 안으로 제한하며, 생성물의 경계를 맞추기 위한 비선형 변형은 하지 않는다.
바닥은 64² 아트픽셀로 BOX 축소했으며 3×3 반복에서 보도·돌바닥의 주기성이 보여 후속 검수 대상으로 남긴다.

### 객체형 화면에서 확인할 것

- 건물 클릭 또는 지도 검수의 건물 선택 → ID·스냅샷 높이·AI 적용 여부 표시. 목록 선택 시 해당 건물로 이동.
- 건물 숨김·복원 → 아래 바닥과 뒤 건물이 남는다. 선택과 가림은 같은 픽셀 깊이 버퍼를 사용한다.
- **#4485 창문 켜기/끄기** → 실제 후보의 창문 위치에 수기로 지정한 마스크 4개만 점등한다.
  다른 건물의 점등은 미연결이며 지붕의 밝은 픽셀을 창문으로 추정하지 않는다.
- 검수용 보행자 이동·위치 슬라이더 → 건물 앞뒤 가림을 확인한다. 확대된 마커이며 실제 사람 크기·경로 안내가 아니다.
- 기본 도형/AI 후보 전환, 바닥 윤곽, 25/50/100% 및 검수 200%. 카메라 회전은 지원하지 않는다.

장면은 512² 아트픽셀을 3배 표시한다. 모든 건물은 개별 RGBA·카메라 깊이 이미지·ID·배치 기준점을 가진다.
배경에 건물이 그려진 완성 이미지를 잘라 붙이는 방식이 아니다. 캔버스의 정적 합성은 상태 변경 시만 다시 만들고,
보행 마커만 프레임별 갱신한다. 숨겨진 탭과 reduced-motion 환경에서는 자동 애니메이션을 제한한다.
GUI 가이드·피드·업로드·시간대·날씨 등 기존 서비스 시안은 계속 미연결이다.

### 실행과 재현

소형 데모는 저장소에 포함되어 새 checkout에서도 아래 서버만 실행하면 된다.

```bash
python3 -m http.server 8766 --bind 127.0.0.1 --directory prototype2
```

`scripts/object_pilot.py prepare`는 오프라인 도형 입력만 만든다.
아래 `generate`는 **새 유료 최대 6회**이므로 별도 승인 없이 반복하지 않는다. 실패·중단 시 자동 재시도나
다른 모델/로컬 추론 우회는 없다. 원출력·입력·상세 기록은 Git 제외 `eval/object_pilot/runs/`에 보존한다.

```bash
prototype2/.venv/bin/python prototype2/scripts/object_pilot.py generate --allow-external
prototype2/.venv/bin/python prototype2/scripts/object_pilot.py build --run prototype2/eval/object_pilot/runs/20260913T163032352584Z
```

`build`는 기존 원출력을 재사용하며 API를 부르지 않는다. `--run` 생략 또는 미완료 생성은 데모를 덮어쓰지 않는다.
점등 마스크는 위 실행에 고정되어 새 후보에 자동 적용되지 않는다. 색·창문 구성의 미감 승인과 실제 외관 정합은 별도다.

```bash
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests -p 'test_*.py'
node prototype2/tests/test_viewer.cjs
node prototype2/tests/test_objects_core.mjs
prototype2/.venv/bin/python prototype2/tests/object_browser_check.py
prototype2/.venv/bin/python prototype2/tests/pilot_browser_check.py
```

테스트는 유료 호출을 모의 응답으로 대체하며 사용자 화풍 파일 없이 실행할 수 있다.
브라우저 QA는 Chromium의 데스크톱·태블릿·모바일 에뮬레이션이고, 실제 iOS/Safari 검증은 아니다.
공개 배포·전체 지도 확장은 하지 않는다. `prototype1` 실행 코드와 데이터에는 변경이 없다.

## 이전 결과 — 2×2 시험 지도 + 반응형 GUI (2026-09-14)

`docs/design`의 데스크톱/모바일 시안을 별도 정적 웹 GUI로 재구현했다.
기존 `/web/` 전체 지도는 보존하고 **새 화면은 `/web/pilot/`**이다.

```bash
python3 -m http.server 8766 --bind 127.0.0.1 --directory prototype2
```

- [로컬 GUI](http://127.0.0.1:8766/web/pilot/?run=20260913T154045571223Z)
- [합성 이미지](../eval/vworld/openrouter/seam_zoom/runs/20260913T154045571223Z/mosaic.png)
- [생성·검수 기록과 실제 프롬프트](../eval/vworld/openrouter/seam_zoom/runs/20260913T154045571223Z/index.html)
- [데스크톱 화면](../eval/vworld/openrouter/seam_zoom/runs/20260913T154045571223Z/gui_desktop.png) ·
  [모바일 화면](../eval/vworld/openrouter/seam_zoom/runs/20260913T154045571223Z/gui_mobile.png)

4회 요청으로 1024² 이미지 4장 생성. 가장자리 128px를 제외한 768px core를 합쳐 1536²로 구성한다.
단일 VWorld 원근 캡처에서 인접 crop 4개를 사용했으므로 다른 카메라 간 정합이나 7.8㎢ 전체 적용을
검증한 것이 아니다. 실제 요청 합계 **208.365초, $0.275348**, 자동 재시도/모델 우회 없음.
출력과 입력 이미지, 프롬프트, 해시, 비용·시간은 실행 폴더에 보존하며 Git에서는 제외한다.

**GUI 구현·조작 검증 완료 / 지도 연결 품질 불합격.** 중앙 지붕·담장·수목과 동측 도로에
불일치가 남는다. 흐리게 합성하거나 실패 영역을 숨기지 않았으며 전체 96조각 확장은 보류한다.
개별 화풍은 선명하지만 사용자 미감 승인과 실제 좌표 정확성은 별도다.

### GUI 동작 범위

- 첫 화면은 지도만 중심에 표시. 900px 이상은 플로팅 창, 미만은 모바일 하단 시트.
- 지도 드래그·휠·핀치·줌 버튼, 미니맵 위치 표시. 기본 12.5~100%, 검수에서만 200%.
- 좌하단 `지도 검수`: 원본/AI 전환, 조각 경계·검수점, 배율 비교, 기록 링크, 시안 상태 미리보기.
- 가이드/피드/도감/명소/올리기/엽서 창과 탭 이동은 가능. 예시 콘텐츠이며 실제 전송·저장·
  좋아요·댓글·방문 인증·파일 선택·업로드·AI 응답은 없다. 레이어·시간대·날씨도 미연결이다.
- 기존 경복궁 시안의 핀·경로를 덕수궁에 붙이지 않는다. GUI가 API 키나 외부 AI 서비스를 호출하지 않는다.
- 폰트는 NeoDunggeunmo 1.601/Pretendard 1.3.9 로컬 파일로 제공. 라이선스/출처는 `web/pilot/fonts/`.
- 원출력/타일이 없는 새 checkout에서는 미생성 안내가 정상이며 다른 지도로 자동 대체하지 않는다.

### 재현과 검증

아래 생성 명령은 **새 유료 4회 시험**이다. 이전 결과를 재사용하는 명령이 아니므로 별도 승인 없이 반복하지 않는다.

```bash
prototype2/.venv/bin/python prototype2/scripts/openrouter_style.py --mode seam-zoom --allow-external
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests -p 'test_*.py'
node prototype2/tests/test_viewer.cjs
prototype2/.venv/bin/python prototype2/tests/pilot_browser_check.py --run 20260913T154045571223Z
```

브라우저 검사는 로컬 임시 서버·Chromium을 사용한다. `--run` 생략 시 합성 테스트 패턴으로 검증하며
어느 모드도 AI 호출을 하지 않는다. 1440×900·1024×768·390×844, DPR 1/2/3, 줌 중심/상하한,
창 이동, 시트 전환, CSP, 외부 요청·제출 없음, 잘못된 run/타일 누락 오류를 검사한다.
모바일 핀치는 터치 이벤트 시뮬레이션이며 실제 iOS/Safari 기기 검수는 하지 않았다.

아래 내용은 이전 단일 후보/로컬 생성 경로의 이력이다. 최신 GUI·4조각 시험 범위는 위 항목을 따른다.

### 선택적 OpenRouter 비교 — 첫 후보 생성 완료

기본 지도 파이프라인은 위 로컬 정책을 유지한다. 별도 `scripts/openrouter_style.py`는
사용자가 요청한 API 비교용이며 `--allow-external` 명시가 필요하다. 실제 호출 전 지도 구역과
화풍 참고 두 장을 OpenRouter/OpenAI로 전송하는 것 및 유료 생성에 대한 명시적 승인이 필요하다.
키는 `OPENROUTER_API_KEY` 환경변수로만 읽는다. 로그/보고서에 키나 요청의 base64 본문을 남기지 않는다.
Sunburst/OpenAI 경로, high, 1:1, 한 장으로 고정하고 자동 재시도·제공업체 우회를 금지한다.
지원 옵션에 정확한 크기가 없어 원해상도를 보존하며 필요 시 비교본만 1024px로 정규화한다.
산출물은 `eval/vworld/openrouter/runs/`에 분리한다. 초기 호출은 승인 부족으로 차단됐고,
사용자의 명시적 외부 전송·유료 생성 승인 후 한 번 실행했다. 기존 Qwen 결과는 보존한다.

- [OpenRouter / 로컬 Qwen 비교](../eval/vworld/openrouter/runs/20260913T142830815903Z/index.html)
- 1024×1024, high, 단일 요청 56.428초, API usage 보고 비용 $0.068837.
- 원출력은 참고 픽셀 화풍에 더 가깝지만 수목·포장·차선 등 AI가 보완한 세부가 있다.
  실제 지도 정확성/사용자 미감 승인은 별도다. 전체 지도·웹 타일은 교체하지 않았다.

## 보존한 이력: Qwen 로컬 화풍 시험

현재 시험은 `--variant q8`이다. 기존 BF16 장기 실행은 중단하고 결과/가중치를 보존했다.
Q8_0 transformer 21.76GB만 추가 다운로드하며 기존 인코더 등을 재사용한다.
활성 파일 세트는 약 38.62GB이고, **전체 캐시 크기나 실행 메모리의 상한이 아니다**.
512px·4단계 호환성 확인 후 1024px·40단계 **seed 20260913 한 장만** 생성한다.
Q8에서는 두 번째 seed와 반복 재현을 실행하지 않는다. 속도 개선은 보장하지 않는다.

```bash
prototype2/.venv/bin/python -m pip install --no-deps gguf==0.19.0
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py qwen-prepare --variant q8
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py qwen-pilot --variant q8
```

[Q8 비교 화면](../eval/vworld/qwen/q8/index.html). Q8 파일의 고정 리비전·크기·SHA256,
2511의 `zero_cond_t=true`, 전체 transformer 키 일치와 양자화 상태를 확인한다.
실패 시 BF16/CPU/외부 GPU로 우회하지 않는다. 단계별 monotonic/wall 경과 시간을 구분하며
이 수치를 순수 GPU 연산 시간으로 해석하지 않는다. 아래 variant 생략 명령은 보존한 BF16 경로다.

2026-09-13 실제 시험: 다운로드/해시 검증은 완료했지만 GGUF의 추가 빈 보조 텐서
`__index_timestep_zero__`가 전체 키 검사에서 차단되어 로딩 전에 중단됐다.
해당 실행에는 Q8 후보가 없다. 후속 수정에서는 표식이 ComfyUI의 2511 식별용임을 확인하고,
정확한 이름/F32/형태 `[0]`/원소 수 0일 때만 메모리 내 사전에서 제외한다.
일반 가중치 1,933개의 키와 형태는 모두 검사하고, Q8 가중치가 로딩 후에도 보존되는지 확인한다.
원본 GGUF는 변경하지 않는다. 실제 후속 실행 상태는 최신 비교 화면의 보고서를 확인한다.

루트 `docs/design`의 모바일 디자인은 당시 향후 UI 기준이었으며 모델 입력으로 사용하지 않는다.
디자인의 지도 배경은 기존 경복궁 렌더와 동일하다. 이번에는 기존 덕수궁 구역을 유지하고
390px 화면의 건물/길/수목 가독성을 추가 검수한다. 앱 UI·가이드·피드·도감은 이번 범위가 아니다.
실행 중 `smoke_progress.json`, `seed_*_progress.json`에 단계별 시간과 메모리 샘플을 저장한다.

기존 SDXL RPG 시안은 사용자 미감 목표를 충족하지 못했다. 현재 원근 시점은 유지하며,
VWorld의 실제 외관 특징과 사용자가 제공한 픽셀 그래픽 참고를 서로 다른 입력으로 전달한다.
Qwen-Image-Edit-2511은 Isopolis와 같은 기반 모델이지만, Isopolis의 별도 학습 가중치를
사용하는 것은 아니므로 동일 품질을 보장하지 않는다. LoRA 학습과 전체 지도 확장은 하지 않는다.

```bash
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py qwen-prepare
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py qwen-pilot --region downtown
# 호환성 확인만 실행할 때:
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py qwen-pilot --smoke-only
```

- 설정: `configs/qwen.json`. 공식 모델 리비전을 고정하고 약 57.7GB를 `work/models/`에 받는다.
  `qwen-prepare`만 다운로드하며 추론은 오프라인·MPS·BF16이다. CPU/외부 서비스 fallback은 없다.
- 입력: 기존 `work/vworld/downtown_source.png`와 사용자가 제공한 참고 파일을 복사한
  `work/references/pixel_style.png`. 두 입력의 SHA-256이 다르면 실행하지 않는다.
- 덕수궁과 주변 저층 건물의 `(320,512)–(1088,1280)` 구역만 종횡비 왜곡 없이 시험한다.
  기존 문서의 해당 `downtown` 시안에 붙인 “광화문” 표기는 정확한 장면 식별이 아니었다.
- 512px·4단계 smoke 뒤 1024px·40단계 두 seed와 첫 seed 반복을 실행한다.
  원출력과 512px→1024px 최근접 확대본을 별도로 보존한다. 색상 제한·경계 덧그리기·
  중간값 필터·장식 합성은 적용하지 않는다.
- 진입점: [최신 Qwen 비교](../eval/vworld/qwen/index.html). 실행마다 별도 `runs/` 폴더에
  비교표·중첩 검수 화면·원출력·프롬프트·실행시간·샘플링한 MPS 메모리 기록을 보존한다.
  실패나 smoke 통과를 화풍 성공으로 표시하지 않으며 실제 결과 상태는 각 `report.json`을 확인한다.
- 미감과 구조는 별도 육안 검수 대상이다. 사용자 승인 전 기존 전체 지도나 웹 타일을 교체하지 않는다.

## 보존한 이전 경로: 대표 3구역 및 SDXL 시험

- [인터랙티브 비교](../eval/diorama/index.html): 경복궁·광화문/도심·남산 주변을 슬라이더로 비교
- [세 구역 비교표](../eval/diorama/comparison.png): 기본 기하 / 이전 prototype2 / 새 디오라마
- [검증 기록](../eval/diorama/report.json): 색 변화율, 반복 재현, 구조 마스크, 이음새 검증
- 기존 전체 지도 `work/fullmap/mosaic.png`와 웹 타일은 그대로 보존했다.
- **새 디오라마는 1,536×1,536px 대표 이미지 3장이다. 전체 96타일 적용은 사용자 승인 후다.**

이전 전체 지도는 파이프라인 완성 산출물이지 미감 목표를 달성한 최종본이 아니다.
새 미감은 따뜻한 지면, 청회색 기와와 용마루, 목조·단청, 용도별 창문·벽면,
녹지 군집, 좌상단 하이라이트와 짧은 접지 그림자로 구성한다.

## 로컬 AI와 공간데이터

이번 시안은 기존 Mac MPS 실행에서 만든 SDXL 재질 9종을 해시 검증 후 `assets/diorama/`에
고정해 재사용했다. 이번 리디자인에서 새로운 모델 추론은 실행하지 않았다. 원 프롬프트·seed·
모델 리비전·실행시간은 에셋 매니페스트에 남긴다. 재생성 명령도 캐시만 사용한다.

`inputs/snapshot/`에 city/layers/meta/poi, 투영 상수와 타일 매니페스트를 고정했다.
실행 중 prototype1 코드를 import하거나 데이터를 다시 읽지 않는다. 초기 복사 이후에는
스냅샷 해시 검증만 수행하므로 다른 세션의 prototype1 변경이 출력에 영향을 주지 않는다.

## VWorld 실제 외관 + 로컬 AI 시험

공통 벽면 패턴을 줄이기 위해 VWorld WebGL 3D 화면을 동일한 세 대표 지역에서 캡처하고,
건물별 색·대비·패턴 서명을 `object_id`와 연결하는 시험 파이프라인을 추가했다. 브라우저
페이지는 메모리에서만 제공되므로 키가 파일이나 명령행에 남지 않는다. VWorld 캡처는
외부 공간데이터 조회지만 AI 연산은 로컬 MPS/CUDA에서만 실행한다.

```bash
export VWORLD_API_KEY='발급받은-키'
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py probe
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py generate
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py validate
```

`probe`는 직교 카메라, 3D 타일 로드, 외관 확보율과 기존 기하 정렬을 확인한다. 기준을
통과하지 않으면 AI를 실행하지 않는다. 통과 결과는 `eval/vworld/comparison.png`에 기본
기하, VWorld 원본, 로컬 AI 픽셀 변환의 3열 비교로 생성된다. 원본 캡처와 파생 파일은
Git에서 제외하고 모델도 `local_files_only=True`로만 읽는다.

기존 마스크 재투영 시안의 외관이 지나치게 평평해 VWorld 광화문 장면 전체를 직접
픽셀화하는 경로도 구현했다. 상단 지도 라벨과 하단 UI는 AI 입력에서 제거하고 출처 표기를
별도 footer로 다시 붙인다. 2px·64색, 동일 seed에서 강도 0.25/0.35/0.45를 비교한다.

```bash
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py direct-pilot --region downtown
```

결과는 `eval/vworld/direct/comparison.png`이다. 과거의 “구조 기준 통과”는 이미지 경계와
전역 이동량의 대리 지표였으며, 개별 건물의 위치·형태 보존을 입증하지 않는다.
이전 기본 추천 강도 0.35는 최종 채택이나 사용자 미감 승인을 뜻하지 않는다.

### 생활형 픽셀 RPG 시안

Direct 결과보다 사진 질감을 더 줄이고 게임 배경처럼 읽히도록 광화문 장면을 384×384
논리 해상도, 4px 격자, 48색으로 다시 해석한다. 특정 게임 에셋은 복제하지 않고 따뜻한
생활형 RPG의 일반적인 색·형태 문법만 사용한다. 소형 사람·차량·가로수는 투명 레이어로
분리하며 주요 건물 경계는 결정적 후처리로 보강한다.

```bash
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py rpg-pilot --region downtown
prototype2/.venv/bin/python prototype2/scripts/vworld_pipeline.py rpg-finalize --region downtown
```

결과는 `eval/vworld/rpg/comparison.png`이며 **미감 미승인·현재 후보에서 제외**다.
강도 0.60의 경계 재현율 72.1%는 원본 경계를 덧그린 뒤의 수치다. 전역 이동 추정 0px도
개별 건물 이동이 없다는 뜻이 아니다. 반복 생성 동일성만 별개의 실측 결과로 보존한다.
별도 장식 레이어가 있어도 AI 프롬프트가 장식물을 허용했으므로 원출력에 장식이 없다는 보장은 없다.

건물·도로의 기본 마스크와 높이는 유지한다. 아트픽셀은 화면 3px이며 처마·그림자의 허용
범위는 원래 건물에서 최대 4 아트픽셀이다. 창문·기와·녹지는 미술적 패턴이다.
문화유산/공원 폴리곤이 겹치는 곳은 열린 마당으로 표현한다. 개별 수목·마당 포장의 실측
데이터를 확보했다는 뜻은 아니며, 지형의 실제 고저차 재구축도 이번 범위에 포함하지 않는다.

## 재현과 검증

저장소 루트에서 실행한다. 현재 세션의 `prototype2/.venv`를 사용한다.

```bash
prototype2/.venv/bin/python prototype2/scripts/freeze_inputs.py
prototype2/.venv/bin/python prototype2/scripts/diorama_map.py pilot
prototype2/.venv/bin/python prototype2/scripts/diorama_map.py validate
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests -v
node prototype2/tests/test_viewer.cjs
```

비교 HTML은 파일로 직접 열 수 있다. 로컬 HTTP로 보려면 다음 명령 후
`http://127.0.0.1:8766/eval/diorama/`를 연다. 기존 전체 지도는 `/web/`이다.

```bash
python3 -m http.server 8766 --bind 127.0.0.1 --directory prototype2
```

`diorama_map.py assets`는 기존 로컬 생성 결과를 에셋 폴더로 고정하는 명령이다.
SDXL 재질을 새로 생성하려면 `local_style.py generate`를 사용한다. 모델이 캐시에 없으면
다운로드하지 않고 실패한다. 승인 후 전체 생성 절차는 [PLAN.md](../PLAN.md)에 있다.

모델·데이터 이용조건은 [LICENSES.md](../LICENSES.md), 변경 기록은 [CHANGELOG.md](../CHANGELOG.md).
