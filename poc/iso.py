"""V-World WFS(건물 폴리곤+층수 / 도로 / 국가유산) -> 아이소메트릭 픽셀 렌더 PoC.

건물 형상·위치는 데이터 그대로. 스타일만 팔레트로 준다.
"""
import json, math
from PIL import Image, ImageDraw

ALPHA = math.radians(22.5)   # 방위각
PHI   = math.radians(30.0)   # 고도각
FLOOR_H = 3.0                # ponytail: 층고 3m 고정. GIS건물통합정보의 실측 높이 붙으면 교체
W, H, ZOOM, PAD = 520, 380, 3, 14

BG      = (26, 30, 38)
GROUND  = (54, 60, 68)
ROAD    = (86, 92,102)
HERI    = (74,104, 78)      # 국가유산 구역
HERI_ED = (96,132, 98)
PAL = {  # (지붕, 밝은 벽, 어두운 벽)
    "low":  ((198,178,146), (166,148,120), (126,112, 90)),
    "mid":  ((188,192,198), (154,158,166), (114,118,128)),
    "high": ((158,172,192), (126,140,160), ( 92,104,124)),
}
band = lambda fl: "low" if fl <= 2 else ("mid" if fl <= 5 else "high")


def _origin(paths):
    pts = [c for p in paths for c in p]
    lon0 = sum(p[0] for p in pts)/len(pts); lat0 = sum(p[1] for p in pts)/len(pts)
    return lon0, lat0, 111320*math.cos(math.radians(lat0)), 110540


def _rings(geom):
    t, c = geom["type"], geom["coordinates"]
    if t == "MultiPolygon":   return [poly[0] for poly in c]
    if t == "Polygon":        return [c[0]]
    if t == "MultiLineString": return list(c)
    if t == "LineString":     return [c]
    return []


BBOX = (126.9740, 37.5760, 126.9820, 37.5820)   # 요청한 화면 범위 (lon/lat)


def load(bld_f, road_f=None, heri_f=None):
    src = {"bld": json.load(open(bld_f, encoding="utf-8"))["features"]}
    src["road"] = json.load(open(road_f, encoding="utf-8"))["features"] if road_f else []
    src["heri"] = json.load(open(heri_f, encoding="utf-8"))["features"] if heri_f else []
    allr = [r for fs in src.values() for f in fs for r in _rings(f["geometry"])]
    lon0, lat0, mlon, mlat = _origin(allr)
    to = lambda r: [((c[0]-lon0)*mlon, (c[1]-lat0)*mlat) for c in r]

    blds = []
    for f in src["bld"]:
        fl = max(1, int(float(f["properties"].get("gro_flo_co") or 0)))   # 0층 -> 1층
        for r in _rings(f["geometry"]):
            blds.append((to(r), fl*FLOOR_H, fl, f["properties"].get("buld_nm")))
    roads = [to(r) for f in src["road"] for r in _rings(f["geometry"])]
    heris = [to(r) for f in src["heri"] for r in _rings(f["geometry"])]
    # 화면 범위를 로컬 미터로 (WFS는 bbox에 걸친 피처 전체를 주므로 프레임은 bbox로 고정한다)
    frame = [((lo-lon0)*mlon, (la-lat0)*mlat)
             for lo, la in [(BBOX[0],BBOX[1]),(BBOX[2],BBOX[1]),(BBOX[2],BBOX[3]),(BBOX[0],BBOX[3])]]
    return blds, roads, heris, frame


def proj(e, n, h, s):
    return ((e*math.cos(ALPHA) - n*math.sin(ALPHA))/s,
            -((e*math.sin(ALPHA) + n*math.cos(ALPHA))*math.sin(PHI) + h*math.cos(PHI))/s)


def depth(en):   # 클수록 멀다
    return sum(e*math.sin(ALPHA) + n*math.cos(ALPHA) for e, n in en)/len(en)


def fit(frame, headroom=60.0):
    """요청 bbox가 화면에 꽉 차도록 SCALE(m/px)과 중심을 구한다.

    headroom: 높은 건물이 위로 삐져나가는 만큼의 여유(m).
    """
    pts = [proj(e, n, h, 1.0) for (e, n) in frame for h in (0, headroom)]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    s = max((max(xs)-min(xs))/(W-2*PAD), (max(ys)-min(ys))/(H-2*PAD))
    cx = W/2 - (min(xs)+max(xs))/2/s
    cy = H/2 - (min(ys)+max(ys))/2/s
    return s, cx, cy


def render(blds, roads, heris, frame, out):
    s, cx, cy = fit(frame)
    img = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(img)
    S = lambda e, n, h: (proj(e, n, h, s)[0]+cx, proj(e, n, h, s)[1]+cy)

    ext = 3000
    dr.polygon([S(-ext,-ext,0), S(ext,-ext,0), S(ext,ext,0), S(-ext,ext,0)], fill=GROUND)
    for g in heris:
        dr.polygon([S(e, n, 0) for e, n in g], fill=HERI, outline=HERI_ED)
    for g in roads:
        dr.line([S(e, n, 0) for e, n in g], fill=ROAD, width=max(2, int(9/s)), joint="curve")

    for en, h, fl, _ in sorted(blds, key=lambda b: -depth(b[0])):
        roof, lit_c, dark_c = PAL[band(fl)]
        for i in range(len(en)-1):
            (e1, n1), (e2, n2) = en[i], en[i+1]
            nx, nz = (n2-n1), -(e2-e1)                      # 바깥 법선
            if nx*math.sin(ALPHA) + nz*math.cos(ALPHA) <= 0:   # 뒷면 제거
                continue
            lit = abs(nx)/(math.hypot(nx, nz) + 1e-9)
            dr.polygon([S(e1,n1,0), S(e2,n2,0), S(e2,n2,h), S(e1,n1,h)],
                       fill=lit_c if lit > 0.5 else dark_c)
        dr.polygon([S(e, n, h) for e, n in en], fill=roof, outline=dark_c)

    img.resize((W*ZOOM, H*ZOOM), Image.NEAREST).save(out)   # 픽셀 스냅
    return out, s


def selfcheck():
    assert proj(0, 0, 10, 1)[1] < proj(0, 0, 0, 1)[1]      # 높을수록 화면 위
    assert proj(0, 100, 0, 1)[1] < proj(0, 0, 0, 1)[1]     # 북쪽일수록 멀다(위)
    assert depth([(0, 100)]) > depth([(0, 0)])
    s, cx, cy = fit([(0,0),(100,0),(100,100),(0,100)]); assert s > 0
    print("selfcheck ok")


if __name__ == "__main__":
    selfcheck()
    b, r, hr, fr = load("gf_bld.json", "gf_lt_l_sprd.json", "gf_lt_c_uo301.json")
    print(f"건물 {len(b)}동 / 도로 {len(r)} / 국가유산 {len(hr)}")
    p, s = render(b, r, hr, fr, "poc_iso.png")
    print(f"saved {p}  scale={s:.3f} m/px  {W*ZOOM}x{H*ZOOM}")
