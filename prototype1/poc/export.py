"""수집 캐시 -> 브라우저 뷰어용 JSON.

좌표는 bbox 중심을 원점으로 한 로컬 ENU 미터로 바꾸고 0.1m 정수로 양자화한다.
링은 첫 점만 절대값이고 나머지는 델타다.

**페인터 정렬을 여기서 미리 해둔다.** 브라우저는 저장된 순서대로 그리기만 하면 된다.
"""
import json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import iso2
import subway

Q = 10.0                      # 0.1m 단위 양자화
BBOX = (126.970, 37.551, 126.996, 37.582)


def origin(bbox):
    """bbox 중심을 원점으로. 점 평균이 아니라 bbox라서 재현 가능하다."""
    lon0, lat0 = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    return lon0, lat0, 111320 * math.cos(math.radians(lat0)), 110540


def enc_ring(ring, to_en):
    """[(lon,lat)...] -> [x0,y0,dx,dy,...] (0.1m 정수, 첫 점만 절대)"""
    pts = [(round(e * Q), round(n * Q)) for e, n in map(to_en, ring)]
    out = [pts[0][0], pts[0][1]]
    for (px, py), (x, y) in zip(pts, pts[1:]):
        out += [x - px, y - py]
    return out


def dec_ring(a):
    """enc_ring 역변환 — 자체 검증용."""
    x, y = a[0], a[1]
    out = [(x / Q, y / Q)]
    for i in range(2, len(a), 2):
        x += a[i]; y += a[i + 1]
        out.append((x / Q, y / Q))
    return out


def _roof_table(cache_dir):
    """cache_roof.json -> (중심색 목록, {gid: 인덱스}). 파일이 없으면 ([], {}).

    되돌리기 1층: 이 파일을 지우면 `roofc`가 안 나가고 뷰어는 오늘 색을 쓴다.
    되돌리기 2층: style.json의 `roof_ortho: false`.
    """
    if not iso2.STYLE.get("roof_ortho", True):
        return [], {}
    p = os.path.join(cache_dir, "cache_roof.json")
    if not os.path.exists(p):
        return [], {}
    d = json.load(open(p, encoding="utf-8"))
    return [list(c) for c in d["centers"]], d["by_gid"]


def build_city(cache_dir, to_en):
    blds = iso2.parse(os.path.join(cache_dir, "cache_bld.xml"))
    age = iso2.parse_age(os.path.join(cache_dir, "cache_age.xml"))
    roof_rgb, roof_by_gid = _roof_table(cache_dir)
    for b in blds:
        b["en"] = [to_en(c) for c in b["ring"]]
    blds.sort(key=lambda b: -iso2.depth(b["en"]))      # 먼 것부터 = 그리는 순서

    # 인덱스 테이블 — uses/uidx와 같은 관례. 등장 순서대로 번호를 준다
    tables = {"uses": ([], {}), "prp": ([], {}), "str": ([], {})}
    def idx(key, v):
        lst, m = tables[key]
        if v is None or v == "":
            return -1
        if v not in m:
            m[v] = len(lst); lst.append(v)
        return m[v]

    # ⚠️ 정렬 **후** 한 루프 안에서 전부 채운다. 따로 돌면 names 인덱스가 어긋난다
    kind, use, hh, rings, names = [], [], [], [], []
    prpos, strct, yr, fl, meas, roofc = [], [], [], [], [], []
    for i, b in enumerate(blds):
        use.append(idx("uses", b["use"]))
        prpos.append(idx("prp", b.get("prpos")))
        strct.append(idx("str", b.get("strct")))
        yr.append(age.get(b.get("gid"), 0))            # 0 = 결측 -> 중립 밴드
        fl.append(b.get("fl", 1))
        meas.append(b.get("meas", 0))                  # 1 = 실측 높이 사용
        roofc.append(roof_by_gid.get(b.get("gid"), -1))  # -1 = 표본 실패 -> 규칙색 폴백
        kind.append(2 if b["palace"] else (1 if b["wood"] else 0))
        hh.append(round(b["h"] * Q))
        rings.append(enc_ring(b["ring"], to_en))
        if b["nm"]:
            names.append([i, b["nm"]])
    return {"n": len(blds), "uses": tables["uses"][0], "kind": kind, "use": use,
            "h": hh, "rings": rings, "names": names,
            "prp": tables["prp"][0], "prpos": prpos,
            "str": tables["str"][0], "strct": strct, "yr": yr, "fl": fl,
            "meas": meas,
            # 지붕색 실측 — 없으면 두 키 모두 빠지고 뷰어가 규칙색으로 돌아간다
            **({"roof_rgb": roof_rgb, "roofc": roofc} if roof_rgb else {})}


def build_layers(cache_dir, to_en):
    def enc(kind, wkey=None):
        p = os.path.join(cache_dir, f"cache_{kind}.json")
        gs = iso2._geoms(p, wkey=wkey)
        if wkey is None:
            return [enc_ring(g, to_en) for g in gs if len(g) >= 2]
        return [[round(w * Q), enc_ring(g, to_en)] for g, w in gs if len(g) >= 2]

    return {"road": enc("road", wkey="road_bt"), "heri": enc("heri"),
            "park": enc("park"), "river": enc("river"), "temple": enc("temple")}


POI_FIELDS = {
    "museum":   ("mus_nam", ["mus_typ", "opr_tel", "opr_url", "new_adr"]),
    "market":   ("name",    ["category", "items", "adr_road", "homepage"]),
    "tourinfo": ("tur_nam", ["des_inf", "add_inf", "sws_tme", "swe_tme"]),
}


def build_poi(cache_dir, to_en, bbox):
    out = {}
    for kind, (namek, extras) in POI_FIELDS.items():
        p = os.path.join(cache_dir, f"cache_{kind}.json")
        items = []
        if os.path.exists(p):
            for f in json.load(open(p, encoding="utf-8"))["features"]:
                g = f["geometry"]
                if g["type"] != "Point":
                    continue
                e, n = to_en(g["coordinates"])
                pr = f["properties"]
                it = {"x": round(e * Q), "y": round(n * Q),
                      "name": (pr.get(namek) or "").strip()}
                for k in extras:
                    v = pr.get(k)
                    if v not in (None, "", "null"):
                        it[k] = str(v).strip()
                items.append(it)
        out[kind] = items

    st = subway.stations_in(bbox)
    pos = {}
    for s in st:
        e, n = to_en((s["lon"], s["lat"]))
        pos[s["name"]] = [round(e * Q), round(n * Q)]
    out["subway"] = {
        "stations": [{"x": pos[s["name"]][0], "y": pos[s["name"]][1],
                      "name": s["name"], "lines": s["lines"]} for s in st],
        "lines": {ln: [pos[n] for n in names if n in pos]
                  for ln, names in subway.LINE_ORDER.items()},
    }
    return out


def main(cache_dir=".", out_dir=None):
    out_dir = out_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "data")
    os.makedirs(out_dir, exist_ok=True)
    lon0, lat0, mlon, mlat = origin(BBOX)
    to_en = lambda c: ((c[0] - lon0) * mlon, (c[1] - lat0) * mlat)

    city   = build_city(cache_dir, to_en)
    layers = build_layers(cache_dir, to_en)
    poi    = build_poi(cache_dir, to_en, BBOX)

    frame = [[round(e * Q), round(n * Q)] for e, n in
             (to_en((BBOX[0], BBOX[1])), to_en((BBOX[2], BBOX[1])),
              to_en((BBOX[2], BBOX[3])), to_en((BBOX[0], BBOX[3])))]
    # 투영 이식 검증용 골든 값 — JS가 로드 시 대조한다
    golden = [{"e": e, "n": n, "h": h,
               "u": iso2.proj(e, n, h, 1.0)[0], "v": iso2.proj(e, n, h, 1.0)[1]}
              for e, n, h in [(0, 0, 0), (100, 0, 0), (0, 100, 0),
                              (0, 0, 50), (-250, 730, 12.5)]]
    meta = {"bbox": list(BBOX), "q": Q,
            "origin": {"lon0": lon0, "lat0": lat0, "mlon": mlon, "mlat": mlat},
            "frame": frame, "style": iso2.STYLE, "golden": golden}

    for nm, obj in (("city", city), ("layers", layers), ("poi", poi), ("meta", meta)):
        p = os.path.join(out_dir, f"{nm}.json")
        json.dump(obj, open(p, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        print(f"  {nm}.json  {os.path.getsize(p)/1024:>8.1f} KB")
    print(f"건물 {city['n']} (이름 {len(city['names'])}) / 도로 {len(layers['road'])} / "
          f"공원 {len(layers['park'])} / 문화재 {len(layers['heri'])} / "
          f"POI {sum(len(poi[k]) for k in POI_FIELDS)} / 지하철 {len(poi['subway']['stations'])}역")


def _selfcheck():
    to_en = lambda c: (c[0] * 1000, c[1] * 1000)
    ring = [(0, 0), (0.01, 0), (0.01, 0.02), (0, 0)]
    enc = enc_ring(ring, to_en)
    assert enc[:2] == [0, 0]
    back = dec_ring(enc)
    assert len(back) == len(ring)
    for (a, b), c in zip([to_en(p) for p in ring], back):
        assert abs(a - c[0]) < 0.05 and abs(b - c[1]) < 0.05, (a, b, c)
    # 인덱스 테이블 관례 — 결측은 -1, 등장 순서대로 번호
    import iso2 as _i
    st = {"age_break": [1966, 1989], "prpos_group": {"단독주택": "house"}}
    assert _i.age_band(None, [1966, 1989]) == 1, "결측은 중립 밴드여야 한다"
    assert _i.age_band(1950, [1966, 1989]) == 0 and _i.age_band(2010, [1966, 1989]) == 2
    assert _i.wall_mat("철근콘크리트구조") == "콘크리트"
    assert _i.wall_mat("벽돌구조") == "조적" and _i.wall_mat("블록구조") == "조적"
    assert _i.wall_mat("일반철골구조") == "기타"
    assert _i.wall_mat("일반목구조") is None, "목조는 kind가 처리한다"
    assert _i.wood_use("단독주택") == "주거" and _i.wood_use("제2종근린생활시설") == "근생"
    assert _i.wood_use(None) == "기타"
    # 전 결측 -> 중립 = 오늘과 같은 색 (되돌리기 동치)
    assert _i.variant({"wood": False, "palace": False}, st) == (None, "기타", 1)
    # 높이 — 실측 우선 + 비대칭 가드
    assert _i.bld_height(1, 21.0, True, True) == 21.0
    assert _i.bld_height(15, 12.5, False, False) > 40
    assert abs(_i.bld_height(1, 0, True, False) - 4.00) < .01
    lon0, lat0, mlon, mlat = origin((126.0, 37.0, 127.0, 38.0))
    assert abs(lon0 - 126.5) < 1e-9 and abs(lat0 - 37.5) < 1e-9
    assert mlon > 0 and mlat > 0
    print("export selfcheck ok")


if __name__ == "__main__":
    if "--check" in sys.argv:
        _selfcheck()
    else:
        _selfcheck()
        main(sys.argv[1] if len(sys.argv) > 1 else ".")
