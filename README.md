# pixel_city

서울 공간데이터를 바탕으로 만드는 픽셀 지도 실험입니다.

- [prototype1](prototype1/poc/README.md): 규칙 기반 지도
- [prototype2](prototype2/README.md): AI 이미지 지도·상호작용 시험
- [개발·검증 안내](docs/DEVELOPMENT.md)
- [최신 명소 8곳·검수 결과](docs/LANDMARK_DISCOVERY.md) · [배포 환경](docs/DEPLOYMENT.md)
- [광화문 일대 기획·조사](docs/planning/seoul-pilot.md): 지역·랜드마크 8개·실제 시간과 날씨 표현
- [TourAPI 수집·검토](docs/planning/tourapi-collection.md): 로컬 데이터 수집 방법과 조사 결과

```bash
python3 -m http.server 8766 --bind 127.0.0.1 --directory prototype2
```
