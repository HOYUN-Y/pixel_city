"""용도별건물정보(dt_d198) 기반 아이소메트릭 픽셀 렌더.

건물 형상·층수·용도·구조가 전부 한 응답에 들어 있어 조인이 필요 없다.
목구조는 처마를 달아 한옥/전각으로 구분해 그린다.
"""
import math, os, re, sys, json
from PIL import Image, ImageDraw

STYLE = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "style.json"), encoding="utf-8"))
_C = STYLE["colors"]
_rgb = lambda v: tuple(v)

ALPHA, PHI = math.radians(STYLE["alpha_deg"]), math.radians(STYLE["phi_deg"])
FLOOR_H      = STYLE["floor_h"]
WOOD_FLOOR_H = STYLE["wood_floor_h"]     # 전각은 1층이어도 높다
PALACE_SCALE = STYLE["palace_scale"]
EAVE         = STYLE["eave"]             # 처마 내밀기 배율

W, H, ZOOM, PAD = 520, 380, 3, 14
BBOX = (126.9740, 37.5760, 126.9820, 37.5820)

BG, GROUND, ROAD = _rgb(_C["bg"]), _rgb(_C["ground"]), _rgb(_C["road"])
HERI, HERI_ED    = _rgb(_C["heri"]), _rgb(_C["heri_edge"])
PARK, PARK_ED    = _rgb(_C["park"]), _rgb(_C["park_edge"])
RIVER            = _rgb(_C["river"])
# 용도 -> (지붕, 밝은벽, 어두운벽)
PAL = {k: tuple(map(_rgb, v)) for k, v in _C["use"].items()}
PAL[None] = tuple(map(_rgb, _C["default"]))
PALACE = tuple(map(_rgb, _C["palace"]))   # 청기와 / 단청 적색 기둥
HANOK  = tuple(map(_rgb, _C["hanok"]))    # 회기와 / 목재


def parse(path):
    x = open(path, encoding="utf-8", errors="replace").read()
    x = x.replace("</collection>", "")   # collect.py 캐시 래퍼 무해화
    out = []
    for f in re.findall(r"<sop:dt_d198[ >].*?</sop:dt_d198>", x, re.S):
        get = lambda t: (re.search(rf"<sop:{t}>(.*?)</sop:{t}>", f) or [None, ""])[1] \
              if re.search(rf"<sop:{t}>(.*?)</sop:{t}>", f) else ""
        use   = get("buld_prpos_cl_code_nm") or None
        strct = get("strct_code_nm") or ""
        nm    = (get("buld_nm") or "") + (" " + get("buld_dong_nm") if get("buld_dong_nm") else "")
        try: fl = max(1, int(get("ground_floor_co") or 1))
        except ValueError: fl = 1
        wood = "목" in strct
        palace = wood and any(k in nm for k in ("궁", "종묘", "사직"))
        h = fl * (WOOD_FLOOR_H * (PALACE_SCALE if palace else 1.0) if wood else FLOOR_H)
        for c in re.findall(r"<gml:coordinates[^>]*>(.*?)</gml:coordinates>", f, re.S):
            ring = [tuple(map(float, p.split(",")[:2])) for p in c.split() if "," in p]
            if len(ring) >= 4:
                out.append({"ring": ring, "h": h, "use": use, "wood": wood,
                            "palace": palace, "nm": nm.strip()})
    return out


def to_local(blds):
    pts = [p for b in blds for p in b["ring"]]
    lon0 = sum(p[0] for p in pts)/len(pts); lat0 = sum(p[1] for p in pts)/len(pts)
    mlon, mlat = 111320*math.cos(math.radians(lat0)), 110540
    for b in blds:
        b["en"] = [((c[0]-lon0)*mlon, (c[1]-lat0)*mlat) for c in b["ring"]]
    frame = [((lo-lon0)*mlon, (la-lat0)*mlat) for lo, la in
             [(BBOX[0],BBOX[1]),(BBOX[2],BBOX[1]),(BBOX[2],BBOX[3]),(BBOX[0],BBOX[3])]]
    return frame


proj = lambda e, n, h, s: ((e*math.cos(ALPHA) - n*math.sin(ALPHA))/s,
                           -((e*math.sin(ALPHA)+n*math.cos(ALPHA))*math.sin(PHI) + h*math.cos(PHI))/s)
depth = lambda en: sum(e*math.sin(ALPHA)+n*math.cos(ALPHA) for e, n in en)/len(en)


def expand(en, k):
    """중심 기준 확대 — 처마 근사."""
    cx = sum(e for e, _ in en)/len(en); cy = sum(n for _, n in en)/len(en)
    return [(cx + (e-cx)*k, cy + (n-cy)*k) for e, n in en]


def fit(frame, headroom=60.0):
    pts = [proj(e, n, h, 1.0) for (e, n) in frame for h in (0, headroom)]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    s = max((max(xs)-min(xs))/(W-2*PAD), (max(ys)-min(ys))/(H-2*PAD))
    return s, W/2-(min(xs)+max(xs))/2/s, H/2-(min(ys)+max(ys))/2/s


def render(blds, frame, roads, out, heris=()):
    s, cx, cy = fit(frame)
    img = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(img)
    S = lambda e, n, h: (proj(e, n, h, s)[0]+cx, proj(e, n, h, s)[1]+cy)
    ext = 3000
    dr.polygon([S(-ext,-ext,0), S(ext,-ext,0), S(ext,ext,0), S(-ext,ext,0)], fill=GROUND)
    for g in heris:
        dr.polygon([S(e, n, 0) for e, n in g], fill=HERI, outline=HERI_ED)
    for g, bt in sorted(roads, key=lambda r: r[1]):
        dr.line([S(e, n, 0) for e, n in g], fill=ROAD,
                width=max(1, round(bt/s)), joint="curve")

    def walls(en, h0, h1, lit_c, dark_c):
        for i in range(len(en)-1):
            (e1,n1),(e2,n2) = en[i], en[i+1]
            nx, nz = (n2-n1), -(e2-e1)
            if nx*math.sin(ALPHA) + nz*math.cos(ALPHA) <= 0: continue
            c = lit_c if abs(nx)/(math.hypot(nx,nz)+1e-9) > 0.5 else dark_c
            dr.polygon([S(e1,n1,h0), S(e2,n2,h0), S(e2,n2,h1), S(e1,n1,h1)], fill=c)

    for b in sorted(blds, key=lambda b: -depth(b["en"])):
        en, h = b["en"], b["h"]
        if b["wood"]:
            roof, lit, dark = PALACE if b["palace"] else HANOK
            body = h*0.5
            walls(en, 0, body, lit, dark)                    # 낮은 기둥부
            eave = expand(en, EAVE)                          # 크게 내민 처마 지붕
            walls(eave, body, h, roof, tuple(int(c*0.72) for c in roof))
            dr.polygon([S(e,n,h) for e,n in eave], fill=roof,
                       outline=tuple(int(c*0.62) for c in roof))
        else:
            roof, lit, dark = PAL.get(b["use"], PAL[None])
            walls(en, 0, h, lit, dark)
            dr.polygon([S(e,n,h) for e,n in en], fill=roof, outline=dark)

    img.resize((W*ZOOM, H*ZOOM), Image.NEAREST).save(out)
    return s


def selfcheck():
    assert proj(0,0,10,1)[1] < proj(0,0,0,1)[1]
    sq=[(0,0),(10,0),(10,10),(0,10)]
    ex=expand(sq,2.0); assert abs(ex[0][0]-(-5))<1e-9 and abs(ex[2][0]-15)<1e-9
    assert fit([(0,0),(100,0),(100,100),(0,100)])[0] > 0
    print("selfcheck ok")


def _geoms(path, wkey=None):
    """cache_*.json -> 좌표 리스트. wkey를 주면 (좌표, 속성값) 튜플로 반환."""
    if not os.path.exists(path):
        return []
    out = []
    for f in json.load(open(path, encoding="utf-8"))["features"]:
        g = f["geometry"]; t, c = g["type"], g["coordinates"]
        if t == "MultiPolygon":      gs = [poly[0] for poly in c]
        elif t == "Polygon":         gs = [c[0]]
        elif t == "MultiLineString": gs = list(c)
        elif t == "LineString":      gs = [c]
        else:                        gs = []
        if wkey is None:
            out += gs
        else:
            try: w = float(f["properties"].get(wkey) or 3)
            except (TypeError, ValueError): w = 3.0
            out += [(g_, w) for g_ in gs]
    return out


if __name__ == "__main__":
    selfcheck()
    a = sys.argv[1:]
    bld_f = a[0] if a else "bu_wfs.xml"
    if len(a) > 1:
        BBOX = tuple(map(float, a[1].split(",")))
    if len(a) > 3:
        W, H = int(a[2]), int(a[3])
    if len(a) > 4:
        ZOOM = int(a[4])
    out_f = a[5] if len(a) > 5 else "render.png"

    blds = parse(bld_f)
    pts = [p for b in blds for p in b["ring"]]
    lon0 = sum(p[0] for p in pts)/len(pts); lat0 = sum(p[1] for p in pts)/len(pts)
    mlon, mlat = 111320*math.cos(math.radians(lat0)), 110540
    for b in blds:
        b["en"] = [((c[0]-lon0)*mlon, (c[1]-lat0)*mlat) for c in b["ring"]]
    frame = [((lo-lon0)*mlon, (la-lat0)*mlat) for lo, la in
             [(BBOX[0],BBOX[1]),(BBOX[2],BBOX[1]),(BBOX[2],BBOX[3]),(BBOX[0],BBOX[3])]]
    L = lambda g: [((c[0]-lon0)*mlon, (c[1]-lat0)*mlat) for c in g]
    roads = [(L(g), w) for g, w in _geoms("cache_road.json", wkey="road_bt")]
    heris = [L(g) for g in _geoms("cache_heri.json")]
    rivers= [L(g) for g in _geoms("cache_river.json")]
    print(f"건물 {len(blds)}동 (한옥 {sum(1 for x in blds if x['wood'] and not x['palace'])}"
          f" / 궁궐 {sum(1 for x in blds if x['palace'])}) / "
          f"도로 {len(roads)} / 국가유산 {len(heris)} / 하천 {len(rivers)}")
    print("scale %.3f m/px -> %s" % (render(blds, frame, roads, out_f, heris+rivers), out_f))
