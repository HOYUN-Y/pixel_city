# 18동 기하 고정형 AI 외관 시험

덕수궁 북측의 기존 18동을 대상으로, 건물 전체를 이미지 모델에 그리게 하지 않고
AI가 만든 벽면·지붕 재료를 데이터 기반 건물 면에 적용한다. 전체 지도 전환이나 실제 외관 복원이 아니다.

상태(2026-09-19): **6종 생성·18동 적용 완료**, 요청 시간 합계233.091초, 실제 비용 **$0.360595**.
18동의 알파·깊이·기본 도형·배치와 바닥 보존 검사는 모두 통과했다. **미감은 미승인**이다.
현대식 재료도 노란 벽돌 같은 색감이 강하고, 현재 해상도에서 창문 반복과 세부 노이즈가 촘촘하다.
기존 단독4485 AI 후보보다 미감이 좋아졌다고 보기는 어렵다. 구조적 가능성과 미술 품질은 분리해 판단한다.
상세 관찰은 결과 폴더의 `review.json`에 기록했다. 추가 호출·지도 확장·공개본 교체는 하지 않았다.

## 결과 확인

- 새 화면: `http://127.0.0.1:8766/web/pilot/?view=objects-materials`
- 비교 인덱스: `prototype2/assets/object_material_pilot/index.html`
- 전체 비교 PNG: 같은 폴더 `comparison.png` — 기본 도형 / 이전 후보 / 새 외관.
- 대표 3동: `representative_4628`, `representative_4577`, `representative_4485`의 PNG와 `_3x.png`.
- 기존 화면은 `?view=objects`로 그대로 유지한다. 이전 AI 외관이 실제 채택된 건물은 18동 중 1동이다.

로컬 서버:

```sh
python3 -m http.server 8766 --bind 127.0.0.1 --directory prototype2
```

## 비교 조건과 구현

- `prototype2/inputs/snapshot`의 고정 스냅샷 사용. prototype1 런타임 의존·수정 없음.
- 기존 18동 목록, footprint, 높이, 목조 처마 도형, 카메라·배치·깊이 버퍼 유지.
- 512×512 아트픽셀을 3배 표시. 세 모드 모두 기존 AI 바닥을 동일하게 사용해 외관만 비교한다.
- 목조는 기존 kind 분류, 나머지는 높이 30m 이상 현대식 / 미만 조적. 실제 건축 양식을 판정하는 분류가 아니다.
- 각 유형의 벽면 모듈·지붕 재료 2종씩 총 6종. 원본을 32×32 재료로 축소해 면 내부 좌표로 샘플링한다.
- 벽면 반복 간격은 3m, 목조는 2.5m. 완전한 모듈만 배치하고 남는 양끝·상단은 재료 경계의 중간색으로 채운다.
  층수·창문 개수는 실측값이 아니다. 지붕 재료는 ENU 평면의 4m 반복을 사용한다.
- 벽 방향별 명암은 렌더러가 부여한다. AI가 만든 윤곽·알파·깊이는 사용하지 않는다.
- 기본 도형 렌더의 동일한 raster 함수에 RGB 콜백만 추가한다. 덮는 픽셀과 깊이 결정은 기존 코드 경로를 공유한다.
- 각 객체의 `previous` PNG와 `appearance_mode: face_materials`를 추가하고 기존 매니페스트 버전을 유지한다.
  새 화면에서 `source` / `previous` / `ai` 세 모드를 이동·확대 상태를 유지하며 전환한다.
- 기존 수기 창문 마스크는 새 외관에서 무효화한다. 새 화면은 점등·보행 마커를 사용하지 않는다.

## 생성과 재현

이번 실험은 기존 dense 예산과 분리한 **최대 6회 / $2** 한도다.
기존 OpenRouter → OpenAI `openai/gpt-image-2.5-sunburst`, high, 1:1, opaque, 요청당 1장 경로를 유지한다.
이미지 생성 스킬에 따라 참고 이미지는 화풍 참고로만 명시하고, 게임의 구도·건물·캐릭터 복사를 지시하지 않는다.
기존 API 경로 유지라는 사용자 선택을 따른 것으로 다른 모델이나 내장 이미지 생성으로 대체하지 않는다.

- 전송 자료: 기존 `work/references/pixel_style.png` 화풍 참고 1장과 재료별 프롬프트.
- 지도 원본·건물 도형·GUI·관광 자료는 전송하지 않는다. 키는 인증 헤더에만 사용하고 기록하지 않는다.
- 호출 전 현재 기능·단가 확인. 요청마다 $0.75 보수적 예약을 확보하며 실패·과금 불명확·예산 부족 시 중단.
- 로컬 잠금과 단일 원장으로 중복 실행을 거부한다. 자동 재시도·추가 배치·모델 대체 없음.
- 생성 원본·원장: `prototype2/work/object-material-pilot/`.
- 완성 비교 화면에는 프롬프트·단가·실제 비용 기록과 입력/출력 해시를 남긴다. 원본 화풍 참고는 배포 폴더에 복사하지 않는다.

```sh
# 유료·외부 전송 단계. 이미 시작한 실험은 다시 실행할 수 없다.
prototype2/.venv/bin/python prototype2/scripts/object_materials.py generate --allow-external
# 오프라인 단계. 기존 결과 폴더를 덮어쓰지 않는다.
prototype2/.venv/bin/python prototype2/scripts/object_materials.py build
```

## 검증과 제한

`geometry_checks.json`에서 18동 모두 기본 도형과 새 외관의 알파·깊이·배치 일치, 바닥 원본 해시 일치를 검사한다.
이것은 내부 렌더링 일관성이지 현실·VWorld와의 측량 정확도 검증이 아니다.

```sh
prototype2/.venv/bin/python -m unittest discover -s prototype2/tests -p 'test_object*.py'
node --test prototype2/tests/test_objects_core.mjs
prototype2/.venv/bin/python prototype2/tests/object_material_browser_check.py
prototype2/.venv/bin/python prototype2/tests/object_browser_check.py
```

PC·모바일에서 세 모드의 실제 픽셀 차이, 동일 뷰포트, 건물 숨김/복원, 이동·확대와 검수 이미지 로딩을 확인한다.
브라우저 시험은 로컬 GET/HEAD만 허용하며 유료 API 호출은 하지 않는다.

실행 결과: Python 전체154개, Node 오프라인18개 통과. 새 화면 PC1440×900·모바일390×844의
세 모드·동일 뷰포트·숨김/복원·확대·이동·18동 비교 이미지 로딩 통과, JS 오류0·외부 요청0이다.
기존 객체형 화면도 PC·태블릿·모바일 점등·보행 가림 회귀 통과.
새 화면 캡처와 결과는 `prototype2/work/object-material-pilot/browser_qa/`에 있다.
별도 외부 Redis 연결 점검은 환경변수 누락으로 실행되지 않았으며 이번 외관 시험의 통과 범위에 포함하지 않는다.

미감 승인은 별도다. 새 방식은 건물 실루엣·복잡한 지붕·실제 출입구를 개선하지 않으며,
평면 지형, 낮은 화면 해상도, 반복되는 바닥과 창문 표현의 한계가 남는다.
결과가 단조로워도 기하 기준을 완화하거나 추가 생성으로 자동 확대하지 않는다.
차량·랜드마크·그림자·조경·새 지형은 범위 밖이며, 공개 배포·커밋·병합·푸시는 하지 않는다.
