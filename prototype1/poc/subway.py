"""대상 구역(경복궁~남산) 내 지하철역.

ponytail: 프로토타입용 상수. 서울 열린데이터광장 인증키가 나오면 API 조회로 교체한다.
좌표는 역 중심 대략값이며 출입구 단위가 아니다. 노선 연결도 실제 지하 선형이 아니라
역을 잇는 단순 폴리라인으로 그린다 (docs/CONCEPT.md에서 허용한 단순화).
"""

STATIONS = [
    {"name": "경복궁",     "lon": 126.97300, "lat": 37.57583, "lines": ["3"]},
    {"name": "안국",       "lon": 126.98549, "lat": 37.57649, "lines": ["3"]},
    {"name": "종로3가",    "lon": 126.99189, "lat": 37.57146, "lines": ["1", "3", "5"]},
    {"name": "종각",       "lon": 126.98317, "lat": 37.57015, "lines": ["1"]},
    {"name": "시청",       "lon": 126.97723, "lat": 37.56542, "lines": ["1", "2"]},
    {"name": "을지로입구", "lon": 126.98254, "lat": 37.56604, "lines": ["2"]},
    {"name": "명동",       "lon": 126.98603, "lat": 37.56083, "lines": ["4"]},
    {"name": "회현",       "lon": 126.98125, "lat": 37.55849, "lines": ["4"]},
    {"name": "서울역",     "lon": 126.97243, "lat": 37.55598, "lines": ["1", "4"]},
]

# 노선별 역 순서 (연결선 그리기용). 구역 밖 구간은 담지 않는다.
LINE_ORDER = {
    "1": ["서울역", "시청", "종각", "종로3가"],
    "2": ["시청", "을지로입구"],
    "3": ["경복궁", "안국", "종로3가"],
    "4": ["서울역", "회현", "명동"],
    "5": ["종로3가"],
}


def stations_in(bbox):
    x0, y0, x1, y1 = bbox
    return [s for s in STATIONS if x0 <= s["lon"] <= x1 and y0 <= s["lat"] <= y1]


def _selfcheck():
    by = {s["name"] for s in STATIONS}
    for line, names in LINE_ORDER.items():
        for n in names:
            assert n in by, f"{line}호선의 {n} 역이 STATIONS에 없다"
        for n in names:
            assert line in dict((s["name"], s["lines"]) for s in STATIONS)[n], \
                f"{n} 역에 {line}호선이 없다"
    assert len(stations_in((126.970, 37.551, 126.996, 37.582))) == len(STATIONS)
    assert stations_in((0, 0, 1, 1)) == []
    print("subway selfcheck ok —", len(STATIONS), "역")


if __name__ == "__main__":
    _selfcheck()
