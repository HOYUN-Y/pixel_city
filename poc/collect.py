"""V-World dtna WFS 수집기 — bbox 재귀 분할로 maxFeatures 1000 상한을 우회한다.

응답이 정확히 MAXF면 잘린 것으로 보고 4분할해 다시 받는다.
"""
import os, re, sys, time, json, urllib.parse, urllib.request

KEY    = os.environ["VWORLD_API_KEY"]
DOMAIN = os.environ["VWORLD_API_DOMAIN"]
MAXF   = 1000                     # 서버 상한. 초과 요청은 INVALID_RANGE
SLEEP  = 0.25                     # ponytail: 고정 지연. 429 나면 늘린다
# dtna WFS (GML2, sop: 네임스페이스) — 재귀 분할 대상
ENDPOINTS = {
    "bld": ("https://api.vworld.kr/ned/wfs/getBuildingUseWFS", "dt_d198"),
    "age": ("https://api.vworld.kr/ned/wfs/getBuildingAgeWFS", "dt_d196"),
}
# 기존 오픈API WFS (GeoJSON) — 피처 수가 적어 분할 없이 받는다
GEOJSON_LAYERS = {"road": "lt_l_sprd", "heri": "lt_c_uo301", "river": "lt_c_wkmstrm"}


def _fetch(url, typename, bbox):
    q = urllib.parse.urlencode({
        "key": KEY, "domain": DOMAIN, "typename": typename,
        "bbox": ",".join(f"{v:.6f}" for v in bbox),
        "srsname": "EPSG:4326", "maxFeatures": MAXF, "output": "GML2",
    })
    with urllib.request.urlopen(f"{url}?{q}", timeout=120) as r:
        return r.read().decode("utf-8", "replace")


def _split(b):
    x0, y0, x1, y1 = b
    mx, my = (x0+x1)/2, (y0+y1)/2
    return [(x0,y0,mx,my), (mx,y0,x1,my), (x0,my,mx,y1), (mx,my,x1,y1)]


def collect(kind, bbox, depth=0, stats=None):
    """bbox 안의 피처 XML 조각을 모두 모아 반환. 잘리면 4분할 재귀."""
    url, typename = ENDPOINTS[kind]
    stats = stats if stats is not None else {"req": 0, "split": 0}
    stats["req"] += 1
    time.sleep(SLEEP)
    x = _fetch(url, typename, bbox)
    if "ServiceException" in x:
        msg = re.search(r"<ServiceException[^>]*>(.*?)</ServiceException>", x, re.S)
        raise RuntimeError(f"WFS 오류 depth={depth}: {(msg.group(1) if msg else x)[:160]}")
    feats = re.findall(rf"<sop:{typename}[ >].*?</sop:{typename}>", x, re.S)
    if len(feats) >= MAXF:
        if depth >= 6:
            print(f"  ! depth 한계에서 여전히 포화: {bbox}", file=sys.stderr)
            return feats
        stats["split"] += 1
        print(f"  {'  '*depth}포화({len(feats)}) → 4분할", file=sys.stderr)
        out = []
        for sub in _split(bbox):
            out += collect(kind, sub, depth+1, stats)
        return out
    return feats


def fetch_geojson(kind, bbox):
    """기존 오픈API WFS에서 GeoJSON으로 받는다. 1000 포화 시 4분할."""
    layer = GEOJSON_LAYERS[kind]
    def one(b, depth=0):
        q = urllib.parse.urlencode({
            "SERVICE": "WFS", "REQUEST": "GetFeature", "VERSION": "2.0.0",
            "TYPENAME": layer, "BBOX": ",".join(f"{v:.6f}" for v in b),
            "SRSNAME": "EPSG:4326", "OUTPUT": "application/json",
            "MAXFEATURES": MAXF, "KEY": KEY, "DOMAIN": DOMAIN,
        })
        time.sleep(SLEEP)
        with urllib.request.urlopen(
                f"https://api.vworld.kr/req/wfs?{q}", timeout=120) as r:
            body = r.read().decode("utf-8", "replace")
        if not body.lstrip().startswith("{"):
            return []                              # 피처 없으면 XML 예외가 온다
        fs = json.loads(body).get("features", [])
        if len(fs) >= MAXF and depth < 5:
            out = []
            for sub in _split(b):
                out += one(sub, depth+1)
            return out
        return fs
    fs = one(bbox)
    seen, out = set(), []
    for f in fs:
        k = f.get("id") or json.dumps(f["geometry"])[:120]
        if k not in seen:
            seen.add(k); out.append(f)
    return out


ID = re.compile(r"<sop:gis_idntfc_no>(.*?)</sop:gis_idntfc_no>")

def dedup(feats):
    seen, out = set(), []
    for i, f in enumerate(feats):
        m = ID.search(f)
        k = m.group(1) if m else f"__{i}"
        if k not in seen:
            seen.add(k); out.append(f)
    return out


if __name__ == "__main__":
    kind = sys.argv[1] if len(sys.argv) > 1 else "bld"
    if kind in GEOJSON_LAYERS:
        bbox = tuple(map(float, sys.argv[2].split(",")))
        fs = fetch_geojson(kind, bbox)
        json.dump({"type": "FeatureCollection", "features": fs},
                  open(f"cache_{kind}.json", "w", encoding="utf-8"))
        print(f"{kind}: {len(fs)} features → cache_{kind}.json")
        raise SystemExit
    bbox = tuple(map(float, sys.argv[2].split(","))) if len(sys.argv) > 2 else \
           (126.9740, 37.5760, 126.9820, 37.5820)
    stats = {"req": 0, "split": 0}
    t0 = time.time()
    feats = collect(kind, bbox, stats=stats)
    uniq = dedup(feats)
    out = f"cache_{kind}.xml"
    open(out, "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<collection>\n' + "\n".join(uniq) + "\n</collection>\n")
    print(f"{kind}: 요청 {stats['req']}회 / 분할 {stats['split']}회 / "
          f"수집 {len(feats)} → 중복제거 {len(uniq)} / {time.time()-t0:.1f}s → {out}")


def _selfcheck():
    b = (0, 0, 10, 10)
    q = _split(b)
    assert len(q) == 4 and q[0] == (0, 0, 5, 5) and q[3] == (5, 5, 10, 10)
    a = "<sop:x><sop:gis_idntfc_no>A</sop:gis_idntfc_no></sop:x>"
    assert len(dedup([a, a, a])) == 1
    assert len(dedup(["<sop:x/>", "<sop:y/>"])) == 2   # id 없으면 각각 유지
    print("selfcheck ok")
