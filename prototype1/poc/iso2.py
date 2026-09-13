"""용도별건물정보(dt_d198) 기반 아이소메트릭 픽셀 렌더.

건물 형상·층수·용도·구조가 전부 한 응답에 들어 있어 조인이 필요 없다.
목구조는 처마를 달아 한옥/전각으로 구분해 그린다.
"""
import math, os, re, sys, json
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain                       # zq/cells를 공유한다. rasterio는 grid()에서만 쓴다

STYLE = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "style.json"), encoding="utf-8"))
_C = STYLE["colors"]
_rgb = lambda v: tuple(v)

ALPHA, PHI = math.radians(STYLE["alpha_deg"]), math.radians(STYLE["phi_deg"])
FLOOR_H      = STYLE["floor_h"]          # floor_h_curve가 없을 때만 쓰는 폴백
WOOD_FLOOR_H = STYLE["wood_floor_h"]     # 한옥 (실측 중앙 4.00m)
PALACE_FLOOR_H = STYLE.get("palace_floor_h", 7.0)   # 전각은 1층이어도 높다
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


def bld_height(fl, hg, wood, palace, style=None):
    """건물 높이(m). 실측(buld_hg)이 타당하면 그 값, 아니면 층수 x 층고곡선.

    **app.js는 이 값을 city.json의 `h`에서 읽기만 하므로 거울 구현이 필요 없다.**

    이상치 처리가 비대칭인 게 핵심이다 (실측 2,545동을 훑어 정했다):
      - 층고가 **너무 작으면**(< hg_min_ratio) **높이 기록이 틀린 것**이다.
        안국빌딩 15층 12.5m(0.8m/층) 같은 6건. -> 곡선으로 폴백한다.
      - 층고가 **커 보이면** **층수 기록이 틀린 것**이다.
        창덕궁 인정전 1층 21.0m, D동 1층 47.4m 같은 12건. -> **실측이 옳다. 자르지 않는다.**
    """
    style = style or STYLE
    if hg and hg > 0 and fl > 0 and hg / fl >= style.get("hg_min_ratio", 2.0):
        return hg                                    # 실측 (36.4%)
    if wood:
        return fl * (PALACE_FLOOR_H if palace else WOOD_FLOOR_H)
    curve = style.get("floor_h_curve")
    if not curve:
        return fl * FLOOR_H                          # 곡선을 지우면 옛 상수로 돌아간다
    h = curve[0][1]
    for lo, v in curve:                              # 계단 표. 보간하지 않는다
        if fl >= lo:
            h = v
    return fl * h


def parse(path):
    x = open(path, encoding="utf-8", errors="replace").read()
    x = x.replace("</collection>", "")   # collect.py 캐시 래퍼 무해화
    out = []
    for f in re.findall(r"<sop:dt_d198[ >].*?</sop:dt_d198>", x, re.S):
        get = lambda t: (re.search(rf"<sop:{t}>(.*?)</sop:{t}>", f) or [None, ""])[1] \
              if re.search(rf"<sop:{t}>(.*?)</sop:{t}>", f) else ""
        use   = get("buld_prpos_cl_code_nm") or None
        prpos = get("main_prpos_code_nm") or None      # 주용도 세분류 (24종) — 지붕색
        strct = get("strct_code_nm") or ""             # 전체 문자열 — 벽 재질
        gid   = get("gis_idntfc_no") or ""             # dt_d196(연령) 조인 키
        nm    = (get("buld_nm") or "") + (" " + get("buld_dong_nm") if get("buld_dong_nm") else "")
        try: fl = max(1, int(get("ground_floor_co") or 1))
        except ValueError: fl = 1
        try: hg = float(get("buld_hg") or 0)         # 실측 높이. dt_d198에 들어 있다
        except ValueError: hg = 0.0
        wood = "목" in strct
        palace = wood and any(k in nm for k in ("궁", "종묘", "사직"))
        h = bld_height(fl, hg, wood, palace)
        meas = 1 if h == hg and hg > 0 else 0        # 실측을 썼는지 (정보 패널용)
        for c in re.findall(r"<gml:coordinates[^>]*>(.*?)</gml:coordinates>", f, re.S):
            ring = [tuple(map(float, p.split(",")[:2])) for p in c.split() if "," in p]
            if len(ring) >= 4:
                out.append({"ring": ring, "h": h, "use": use, "wood": wood,
                            "palace": palace, "nm": nm.strip(),
                            "prpos": prpos, "strct": strct, "gid": gid, "fl": fl,
                            "meas": meas})
    return out


def parse_age(path):
    """cache_age.xml(dt_d196) -> {gis_idntfc_no: 사용승인연도}.

    ⚠️ `buld_age` 필드는 쓰지 않는다 — 실측하니 p75·p90·최대가 전부 2028로
    나이가 아니라 연도가 섞여 있다. `use_confm_de`(사용승인일)만 신뢰한다
    (6,949건 중 64.3% 존재, 1930~2020년대에 고르게 분포).
    """
    if not os.path.exists(path):
        return {}
    x = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for f in re.findall(r"<sop:dt_d196[ >].*?</sop:dt_d196>", x, re.S):
        gm = re.search(r"<sop:gis_idntfc_no>(.*?)</sop:gis_idntfc_no>", f)
        dm = re.search(r"<sop:use_confm_de>(\d{4})", f)
        if gm and dm:
            out[gm.group(1)] = int(dm.group(1))
    return out


"""건물 색 변주 — 지붕은 용도, 벽은 재질×연령.

지붕색과 벽색을 분리하면 팔레트는 **덧셈**으로 늘고 외형은 **곱셈**으로 는다.
묶어두면 같은 변주에 630색이 필요한데 분리하면 65색이면 된다.

실측(6,985동)으로 축을 골랐다:
  - 주용도 세분류 24종 — 상위 10종이 97.9% 커버. 대분류 6종보다 훨씬 고르다
  - 구조 3분류 콘크리트 2,953 / 조적 1,399 / 기타 187 (목조는 kind가 이미 처리)
  - 사용승인연도 63.7% 존재. 경계 1966/1989가 가장 균형 잡힌다
  - 한옥은 재질 축이 없으므로 **주용도(주거/근생/기타)로 벽을 가른다** —
    상점으로 쓰이는 한옥은 실제로 파사드가 다르다. 안 가르면 한옥 2,351동이
    한 덩어리로 남아 최대 셀이 25.7%가 된다 (가르면 13.4%)

결측은 전부 중립으로 떨어져 **오늘과 같은 색**이 된다. 이게 되돌리기 동치다.
"""
MAT_CONCRETE = ("철근콘크리트", "철골철근", "철골콘크리트")
MAT_MASONRY  = ("벽돌", "조적", "블록", "석")


def wall_mat(strct):
    """구조 문자열 -> 벽 재질 3분류. 목조는 None (kind가 처리)."""
    if "목" in strct:
        return None
    if any(k in strct for k in MAT_CONCRETE):
        return "콘크리트"
    if any(k in strct for k in MAT_MASONRY):
        return "조적"
    return "기타"


def wood_use(prpos):
    """한옥·궁궐의 벽 구분 — 주거 / 근생 / 기타."""
    p = prpos or ""
    return "주거" if "주택" in p else ("근생" if "근린생활" in p else "기타")


def age_band(year, breaks):
    """연령 밴드. 결측은 중립(1) = 배율 1.0 = 오늘과 같은 색."""
    if not year:
        return 1
    return 0 if year < breaks[0] else (2 if year >= breaks[1] else 1)


def variant(b, style, year=None):
    """(지붕 그룹 키, 벽 그룹 키, 연령 밴드). **app.js variant()의 파이썬 거울.**"""
    ab = age_band(year, style.get("age_break", [1966, 1989]))
    if b["wood"]:
        return ("궁궐" if b["palace"] else "한옥", wood_use(b.get("prpos")), ab)
    roof_g = style.get("colors", {}).get("roof_g", {})
    rg = b.get("prpos") if b.get("prpos") in roof_g else None
    return (rg, wall_mat(b.get("strct", "")), ab)


def _sc(c, k):
    return tuple(max(0, min(255, round(v * k))) for v in c)


def bld_colors(b, style=None, year=None):
    """(지붕, 밝은벽, 어두운벽). **app.js palette()의 파이썬 거울.**

    결측이면 전부 기존 색으로 떨어진다 — 이게 되돌리기 동치다.
    """
    style = style or STYLE
    col = style["colors"]
    rg, wm, ab = variant(b, style, year if year is not None else b.get("yr"))
    k = col.get("age_k", [1, 1, 1])[ab]
    if b["wood"]:
        kn = "궁궐" if b["palace"] else "한옥"
        base = PALACE if b["palace"] else HANOK
        w = col.get("wood_wall", {}).get(kn, {}).get(wm)
        return (base[0], _sc(w[0], k), _sc(w[1], k)) if w else base
    roof = col.get("roof_g", {}).get(rg)
    fb = PAL.get(b["use"], PAL[None])
    m = col.get("wall_m", {}).get(wm)
    return (tuple(roof) if roof else fb[0],
            _sc(m[0], k) if m else fb[1],
            _sc(m[1], k) if m else fb[2])


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


def render(blds, frame, roads, out, heris=(), terr=None, zones=()):
    s, cx, cy = fit(frame)
    img = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(img)
    S = lambda e, n, h: (proj(e, n, h, s)[0]+cx, proj(e, n, h, s)[1]+cy)
    # 지면 밀착 — 도로·국가유산 구역이 지형을 탄다. zq는 과장 미적용이라 여기서 곱한다
    EXAG = (terr or {}).get("exag", 1.0)
    Z  = (lambda e, n: terrain.zq(terr, e, n) * EXAG) if terr else (lambda e, n: 0.0)
    SG = lambda e, n: S(e, n, Z(e, n))
    ext = 3000
    dr.polygon([S(-ext,-ext,0), S(ext,-ext,0), S(ext,ext,0), S(-ext,ext,0)], fill=GROUND)
    for g in heris:
        dr.polygon([SG(e, n) for e, n in g], fill=HERI, outline=HERI_ED)
    if terr:                       # 지형 음영 — app.js drawTerrain()과 같은 셀 목록을 쓴다
        sh, st_, base = terr["shade"], terr["step"], (GROUND, PARK, HERI)
        for i, j, lv, cover in terrain.cells(terr, zones):
            e, n = terr["e0"] + i*st_, terr["n0"] + j*st_
            e1, n1 = e + st_, n + st_
            f = sh[lv] if isinstance(sh[lv], (list, tuple)) else (sh[lv],)*3
            dr.polygon([SG(e,n), SG(e1,n), SG(e1,n1), SG(e,n1)],
                       fill=tuple(max(0, min(255, round(v*k)))
                                  for v, k in zip(base[cover], f)))
    for g, bt in sorted(roads, key=lambda r: r[1]):
        dr.line([SG(e, n) for e, n in g], fill=ROAD,
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
        # 건물은 중심 표고에 **평면으로** 앉는다. 정점별 표고를 주면 바닥이 비평면이 되어
        # 지붕이 기운다 (90m 격자 최대 경사에서 수 픽셀). app.js drawBuilding과 같은 규칙.
        z = Z(sum(e for e, _ in en)/len(en), sum(n for _, n in en)/len(en))
        roof, lit, dark = bld_colors(b)
        if b["wood"]:
            body = h*0.5
            walls(en, z, z+body, lit, dark)                  # 낮은 기둥부
            eave = expand(en, EAVE)                          # 크게 내민 처마 지붕
            walls(eave, z+body, z+h, roof, tuple(int(c*0.72) for c in roof))
            dr.polygon([S(e,n,z+h) for e,n in eave], fill=roof,
                       outline=tuple(int(c*0.62) for c in roof))
        else:
            walls(en, z, z+h, lit, dark)
            dr.polygon([S(e,n,z+h) for e,n in en], fill=roof, outline=dark)

    img.resize((W*ZOOM, H*ZOOM), Image.NEAREST).save(out)
    return s


def selfcheck():
    assert proj(0,0,10,1)[1] < proj(0,0,0,1)[1]
    sq=[(0,0),(10,0),(10,10),(0,10)]
    ex=expand(sq,2.0); assert abs(ex[0][0]-(-5))<1e-9 and abs(ex[2][0]-15)<1e-9
    assert fit([(0,0),(100,0),(100,100),(0,100)])[0] > 0
    # 높이 — 실측 우선, 이상치 가드는 비대칭
    S = STYLE
    assert bld_height(1, 21.0, True, True, S) == 21.0, "창덕궁 인정전 실측을 버렸다"
    assert bld_height(24, 97.2, False, False, S) == 97.2, "광화문 교보생명 실측을 버렸다"
    assert bld_height(1, 47.4, False, False, S) == 47.4, "층수 오류인데 실측을 버렸다"
    assert bld_height(15, 12.5, False, False, S) > 40, "안국빌딩: 높이 오류인데 실측을 썼다"
    assert abs(bld_height(1, 0, False, False, S) - 4.60) < .01
    assert abs(bld_height(5, 0, False, False, S) - 5*3.30) < .01
    assert abs(bld_height(20, 0, False, False, S) - 20*4.00) < .01
    assert abs(bld_height(1, 0, True, False, S) - 4.00) < .01, "한옥 폴백"
    assert abs(bld_height(1, 0, True, True,  S) - 8.25) < .01, "궁궐 폴백"
    # 곡선을 지우면 옛 상수로 돌아간다 (되돌리기 동치)
    import copy
    plain = copy.deepcopy(S); plain.pop("floor_h_curve", None)
    assert abs(bld_height(5, 0, False, False, plain) - 5*S["floor_h"]) < .01

    # ★ 되돌리기 동치 — style.json에서 색 블록을 지우면 오늘 색으로 돌아가야 한다
    import copy
    plain = copy.deepcopy(STYLE)
    for k in ("roof_g", "wall_m", "wood_wall"):
        plain["colors"].pop(k, None)
    b0 = {"wood": False, "palace": False, "use": "상업용",
          "prpos": "업무시설", "strct": "철근콘크리트구조"}
    assert bld_colors(b0, plain) == PAL["상업용"], "색 블록을 지워도 오늘 색이 아니다"
    hb = {"wood": True, "palace": False, "use": None, "prpos": "단독주택"}
    assert bld_colors(hb, plain) == HANOK, "한옥도 되돌아가야 한다"
    assert bld_colors(hb)[0] == HANOK[0], "한옥 지붕은 기와 고정 (용도로 안 변한다)"
    assert bld_colors(hb)[1] != HANOK[1], "한옥 벽은 주용도로 갈려야 한다"
    # 재질/용도/연령 분류가 app.js와 같은 규칙인지
    assert wall_mat("철근콘크리트구조") == "콘크리트" and wall_mat("벽돌구조") == "조적"
    assert wall_mat("일반철골구조") == "기타" and wall_mat("일반목구조") is None
    assert wood_use("단독주택") == "주거" and wood_use(None) == "기타"
    assert age_band(None, [1966, 1989]) == 1 and age_band(1950, [1966, 1989]) == 0
    # 연령이 벽만 바꾸고 지붕은 안 바꾼다
    c1 = {"wood": False, "palace": False, "use": "상업용",
          "prpos": "업무시설", "strct": "철근콘크리트구조"}
    a, b_ = bld_colors(c1, year=1950), bld_colors(c1, year=2010)
    assert a[0] == b_[0], "연령이 지붕색을 바꾸면 안 된다"
    assert a[1] != b_[1], "연령이 벽색을 바꿔야 한다"
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
    ages = parse_age("cache_age.xml")            # 없으면 {} -> 전부 중립 밴드
    for b in blds:
        b["yr"] = ages.get(b.get("gid"))
    # ENU 원점은 **bbox 중심**이다. 건물 정점 평균이었는데 그건 export.py/terrain.py의
    # 프레임과 달라서 terrain.json의 표고가 엉뚱한 곳에 얹힌다. fit()이 프레임 기준으로
    # 중심을 잡으므로 원점을 바꿔도 기존 출력 구도는 그대로다 (건물과 프레임이 같이 이동).
    lon0, lat0 = (BBOX[0]+BBOX[2])/2, (BBOX[1]+BBOX[3])/2
    mlon, mlat = 111320*math.cos(math.radians(lat0)), 110540
    for b in blds:
        b["en"] = [((c[0]-lon0)*mlon, (c[1]-lat0)*mlat) for c in b["ring"]]
    frame = [((lo-lon0)*mlon, (la-lat0)*mlat) for lo, la in
             [(BBOX[0],BBOX[1]),(BBOX[2],BBOX[1]),(BBOX[2],BBOX[3]),(BBOX[0],BBOX[3])]]
    L = lambda g: [((c[0]-lon0)*mlon, (c[1]-lat0)*mlat) for c in g]
    roads = [(L(g), w) for g, w in _geoms("cache_road.json", wkey="road_bt")]
    heris = [L(g) for g in _geoms("cache_heri.json")]
    rivers= [L(g) for g in _geoms("cache_river.json")]
    # 지형 — terrain.json이 없으면 평지로 그린다 (되돌리기 안전망)
    tp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "web", "data", "terrain.json")
    terr = json.load(open(tp, encoding="utf-8")) if os.path.exists(tp) else None
    # 음영 셀의 지표 판정용. app.js buildTerrainCells()와 같은 순서(heri -> park -> temple)
    zones = ([(2, g) for g in heris]
             + [(1, L(g)) for g in _geoms("cache_park.json")]
             + [(2, L(g)) for g in _geoms("cache_temple.json")]) if terr else ()
    print(f"건물 {len(blds)}동 (한옥 {sum(1 for x in blds if x['wood'] and not x['palace'])}"
          f" / 궁궐 {sum(1 for x in blds if x['palace'])}) / "
          f"도로 {len(roads)} / 국가유산 {len(heris)} / 하천 {len(rivers)} / "
          f"지형 {'격자 %dx%d' % (terr['nx'], terr['ny']) if terr else '없음(평지)'}")
    print("scale %.3f m/px -> %s"
          % (render(blds, frame, roads, out_f, heris+rivers, terr, zones), out_f))
