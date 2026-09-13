"""V-World 정사영상 -> 건물별 지붕색 `poc/cache_roof.json`.

**왜 이게 필요한가** — 지붕색이 주용도로만 갈리는데 주용도는 공간적으로 군집한다
(근생은 근생끼리 붙어 있다). 그래서 조합이 102종이어도 화면에서는 덩어리로 보인다.
실측: 최근접 이웃과 지붕색이 사실상 같은 건물이 **43.5%**. 영상에서 실제 색을 가져와
이걸 깬다. 근거와 대조 측정은 docs/WORKLOG.md 2026-09-13.

**AI를 쓰지 않는다.** 건물 외곽선이 이미 있으니 그 안의 화소 중앙값이면 된다.
생성 모델을 끼우면 팔레트 규율(5비트 버킷)·파이썬 패리티·재현성이 한꺼번에 깨진다.

**3D가 아니라 정사영상이다.** V-World 3D DATA API는 중단됐고 3차원 데이터는
국가공간정보 보안관리규정상 '공개제한'이라 복제·출력이 불가하다. 정사영상은 별개
데이터셋이고 WMTS로 공개돼 있다.

    export VWORLD_API_KEY=...
    uv run --with pillow python roofcolor.py --stats     # 2단계: 통계만, 파일 안 씀
    uv run --with pillow python roofcolor.py             # 전체 실행 -> cache_roof.json
"""
import json, math, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
WEB  = os.path.join(os.path.dirname(HERE), "web", "data")
ORTHO = os.path.join(HERE, "cache_ortho")

ZOOM   = 18        # 0.473 m/px. 하위 5% 건물도 139화소 (z19는 4배 비싸고 필요 없다)
LEAN   = 0.078     # 기울어짐 수평변위 / 높이. 을지로 타일에서 벽 폭을 재 추정한 값
MIN_PX = 20        # 침식 후 이 미만이면 폴백
K      = 12        # 군집 수 = 팔레트에 더할 색 수 (예산 160, 현재 137)
LIFT   = (1.25, 1.00, 0.04)   # (명도배율, 채도배율, 명도가산) — 아래 _lift 참조
SLEEP  = 0.25      # collect.py와 같은 고정 지연
LAYER  = "Satellite"


# ---------- 타일 좌표 ----------
# ⚠️ V-World WMTS 경로는 {z}/{y}/{x}다. x/y를 바꾸면 "서비스 제공영역이 아닙니다"가 온다.
#    영상 레이어는 Satellite뿐이다 (Base는 같은 좌표에서 404, Hybrid는 라벨 오버레이).

def _xy(lon, lat, z):
    n = 2 ** z
    return ((lon + 180) / 360 * n,
            (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)


def _lonlat(x, y, z):
    """_xy의 역변환 — 자체 검증용."""
    n = 2 ** z
    return (x / n * 360 - 180,
            math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n)))))


def mpp(lat, z):
    return 156543.03392 / 2 ** z * math.cos(math.radians(lat))


def tiles(bbox, z=ZOOM):
    """bbox를 덮는 (x, y) 목록. y는 위에서 아래로 증가한다."""
    x0, y1 = _xy(bbox[0], bbox[1], z)          # 남서 -> x 최소, y 최대
    x1, y0 = _xy(bbox[2], bbox[3], z)          # 북동 -> x 최대, y 최소
    return [(x, y)
            for y in range(int(y0), int(y1) + 1)
            for x in range(int(x0), int(x1) + 1)]


def fetch(bbox, z=ZOOM, cache=ORTHO, key=None, log=True):
    """타일을 내려받아 cache/{z}_{x}_{y}.jpg 로 남긴다. 이미 있으면 건너뛴다."""
    key = key or os.environ["VWORLD_API_KEY"]
    os.makedirs(cache, exist_ok=True)
    want = tiles(bbox, z)
    got = miss = 0
    for i, (x, y) in enumerate(want):
        p = os.path.join(cache, f"{z}_{x}_{y}.jpg")
        if os.path.exists(p) and os.path.getsize(p) > 0:
            got += 1
            continue
        url = f"https://api.vworld.kr/req/wmts/1.0.0/{key}/{LAYER}/{z}/{y}/{x}.jpeg"
        time.sleep(SLEEP)
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                body = r.read()
        except Exception as e:                              # noqa: BLE001
            print(f"  ! {z}/{y}/{x} {e}", file=sys.stderr); miss += 1; continue
        # 영역 밖이면 200인데 본문이 XML 예외다. 크기로 먼저 거른다
        if body[:1] != b"\xff":
            miss += 1
            if miss <= 3:
                print(f"  ! {z}/{y}/{x} 영상 아님: {body[:120]!r}", file=sys.stderr)
            continue
        open(p, "wb").write(body)
        got += 1
        if log and (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(want)}", file=sys.stderr)
    return {"want": len(want), "got": got, "miss": miss}


# ---------- 표본 ----------

def _ring_px(ring, z):
    """[(lon,lat)...] -> 전역 화소 좌표 [(px,py)...] (타일*256 기준)."""
    return [(_xy(lo, la, z)[0] * 256, _xy(lo, la, z)[1] * 256) for lo, la in ring]


def _bbox_px(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _inside(px, py, ring):
    """짝수-홀수 판정. terrain._in_poly와 같은 규칙."""
    c = False
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]; x2, y2 = ring[i + 1]
        if (y1 > py) != (y2 > py) and px < (x2 - x1) * (py - y1) / (y2 - y1 + 1e-12) + x1:
            c = not c
    return c


def _erode_ok(px, py, ring, r):
    """(px,py)가 외곽선 안이고 **모든 변에서 r 이상** 떨어졌는가.

    다각형 침식을 제대로 하는 대신 변까지의 거리로 근사한다 — 볼록/오목 상관없이
    맞고, 건물 외곽선은 변이 10개 안팎이라 비용도 무시할 만하다.
    """
    if not _inside(px, py, ring):
        return False
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]; x2, y2 = ring[i + 1]
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
        if math.hypot(px - (x1 + t * dx), py - (y1 + t * dy)) < r:
            return False
    return True


def _median(vals):
    v = sorted(vals)
    return v[len(v) // 2]


def sample(blds, z=ZOOM, cache=ORTHO, lean=LEAN, min_px=MIN_PX, log=True):
    """건물 dict 목록 -> {gid: (r,g,b)}. 실패한 건물은 키가 없다.

    **타일 단위로 1장씩** 연다. 모자이크를 메모리에 만들지 않는다 (z19면 148M화소).
    건물 하나가 여러 타일에 걸치면 타일마다 화소를 모아 마지막에 중앙값을 낸다.
    """
    from PIL import Image                      # noqa: PLC0415  (선택 의존성)

    # 건물 -> 화소 외곽선 · 침식 반경. 한 번만 계산한다
    prep = []
    for b in blds:
        gid = b.get("gid")
        if not gid:
            continue
        ring = _ring_px(b["ring"], z)
        if len(ring) < 4:
            continue
        lat = b["ring"][0][1]
        r = max(1.0, lean * b.get("h", 0) / mpp(lat, z))   # 최소 1화소는 늘 깎는다
        prep.append((gid, ring, r, _bbox_px(ring)))

    # 타일 -> 그 타일에 걸친 건물 인덱스
    by_tile = {}
    for i, (_, _, _, (x0, y0, x1, y1)) in enumerate(prep):
        for ty in range(int(y0) // 256, int(y1) // 256 + 1):
            for tx in range(int(x0) // 256, int(x1) // 256 + 1):
                by_tile.setdefault((tx, ty), []).append(i)

    acc = {}                                   # gid -> [[r...],[g...],[b...]]
    done = 0
    for (tx, ty), idxs in sorted(by_tile.items()):
        p = os.path.join(cache, f"{z}_{tx}_{ty}.jpg")
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert("RGB")
        px = im.load()
        ox, oy = tx * 256, ty * 256
        for i in idxs:
            gid, ring, r, (bx0, by0, bx1, by1) = prep[i]
            a = acc.setdefault(gid, ([], [], []))
            for yy in range(max(0, int(by0) - oy), min(256, int(by1) - oy + 1)):
                for xx in range(max(0, int(bx0) - ox), min(256, int(bx1) - ox + 1)):
                    if _erode_ok(ox + xx + 0.5, oy + yy + 0.5, ring, r):
                        c = px[xx, yy]
                        a[0].append(c[0]); a[1].append(c[1]); a[2].append(c[2])
        done += 1
        if log and done % 100 == 0:
            print(f"  타일 {done}/{len(by_tile)}", file=sys.stderr)

    return {g: (_median(a[0]), _median(a[1]), _median(a[2]))
            for g, a in acc.items() if len(a[0]) >= min_px}


# ---------- 군집 ----------
#
# **왜 k-means인가, 그리고 왜 시드가 없는가** — 팔레트에 넣을 수 있는 색은 한 줌인데
# (예산 160, 현재 137) 표본은 수천 개다. 줄여야 한다. 다만 재현성이 생명이라
# 난수를 안 쓴다: 초기 중심을 **명도 순 등간 분위수**로 잡으면 같은 입력에 같은 답이 나온다.
#
# 중심은 `cache_roof.json`에 박아두므로 재현성의 최종 보증은 그 파일이다.
# k-means는 그 파일을 한 번 만드는 도구일 뿐이다.

def _d2(a, b):
    return (a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2


def cluster(colors, k=12, iters=40):
    """RGB 목록 -> (중심 k개, 각 색의 중심 인덱스).

    ⚠️ **기존 팔레트를 피하는 재배치는 넣었다가 뺐다.** 중심이 기존 색과 가까우면
    표본에서 가장 먼 색으로 다시 심게 했는데, 그게 **극단값에 중심을 박아버렸다**:
    7~14동짜리 형광 주황·하늘색 중심이 3개 생기고 최대 셀이 14.8% -> 23.6%로 나빠졌다.

    애초에 필요가 없었다. 재배치 없이 군집한 12색과 기존 137색의 **최소거리가 12.2**라
    뷰어 selfcheck의 기준(14)을 이미 만족한다. 빈 버킷도 32,640개다.
    충돌 검증은 뷰어가 기하로 하고(`pixelCitySelfCheck`), 여기서는 진단만 낸다.
    """
    if len(colors) <= k:
        return list(colors), list(range(len(colors)))
    # 결정론적 초기화 — 난수 없음
    order = sorted(colors, key=lambda c: (c[0]+c[1]+c[2], c))
    cent = [list(order[min(len(order)-1, (2*i+1) * len(order) // (2*k))]) for i in range(k)]

    assign = [0] * len(colors)
    for _ in range(iters):
        moved = False
        for i, c in enumerate(colors):
            best, bd = 0, 1e18
            for j, m in enumerate(cent):
                d = _d2(c, m)
                if d < bd:
                    bd = d; best = j
            if assign[i] != best:
                assign[i] = best; moved = True
        sums = [[0, 0, 0, 0] for _ in range(k)]
        for i, c in enumerate(colors):
            a = sums[assign[i]]
            a[0] += c[0]; a[1] += c[1]; a[2] += c[2]; a[3] += 1
        for j, a in enumerate(sums):
            if a[3]:
                cent[j] = [int(a[0]/a[3] + .5), int(a[1]/a[3] + .5), int(a[2]/a[3] + .5)]
        if not moved:
            break

    return [tuple(c) for c in cent], assign


def nearest_gap(cent, avoid):
    """각 중심이 기존 팔레트 색과 얼마나 떨어졌나 — 진단용. 14 미만이면 거의 같은 색이다."""
    return [round(min(math.sqrt(_d2(c, a)) for a in avoid), 1) for c in cent]


# ---------- 색 보정 ----------
#
# **왜 명도만 올리는가** — 정사영상의 지붕은 어둡다(명도 중앙 94, 현재 규칙색은 171).
# 좁은 골목의 건물은 지붕 상당 부분이 그림자에 들어가 표본이 실제보다 어둡게 나온다.
# 명도를 올리는 건 그 보정이기도 하다.
#
# ⚠️ **채도는 올리지 않는다.** 실측으로 반증됐다 — 채도를 1.45배 하면 이웃 동일색이
#   15.9% -> **17.7%로 나빠진다.** 색상이 비슷한 것끼리 채도를 올리면 서로 더 가까워진다.
#   화면으로도 형광 연두가 튄다. 그래서 기본 채도배율이 1.00이다.
#
# 보정은 `cache_roof.json`을 만들 때 **한 번** 적용되고 중심에 이미 반영된다.
# 런타임 스위치가 아니다 — 값을 바꾸면 이 스크립트를 다시 돌려야 한다.

def _lift(c, lift=LIFT):
    import colorsys
    vs, ss, vb = lift
    h, s, v = colorsys.rgb_to_hsv(c[0] / 255, c[1] / 255, c[2] / 255)
    r, g, b = colorsys.hsv_to_rgb(h, min(1.0, s * ss), min(1.0, v * vs + vb))
    return (round(r * 255), round(g * 255), round(b * 255))


def palette_colors(style):
    """style.json의 colors에서 RGB 삼중항을 전부 긁는다 — 군집이 피해야 할 색.

    파생색(처마 x0.72 등)과 지형 램프까지 훑진 않는다. 주요 색만 피하면 충분하고,
    정확한 판정은 뷰어의 `pixelCitySelfCheck()`가 기하로 한다.
    """
    out = []
    def walk(v):
        if isinstance(v, list):
            if len(v) == 3 and all(isinstance(x, (int, float)) for x in v):
                out.append(tuple(int(x) for x in v))
            else:
                for x in v: walk(x)
        elif isinstance(v, dict):
            for x in v.values(): walk(x)
    walk(style.get("colors", {}))
    return out


# ---------- 자체 검증 ----------

def _selfcheck():
    z = ZOOM
    # 타일 좌표 왕복
    for lon, lat in [(126.9840, 37.5665), (126.970, 37.551), (126.996, 37.582)]:
        x, y = _xy(lon, lat, z)
        lo, la = _lonlat(x, y, z)
        assert abs(lo - lon) < 1e-9 and abs(la - lat) < 1e-9, "타일 좌표 왕복 실패"
    # bbox를 정말 덮는가 — 네 모서리가 타일 목록 안에 있어야 한다
    bbox = (126.970, 37.551, 126.996, 37.582)
    ts = set(tiles(bbox, z))
    for lon, lat in [(bbox[0], bbox[1]), (bbox[2], bbox[1]),
                     (bbox[0], bbox[3]), (bbox[2], bbox[3])]:
        x, y = _xy(lon, lat, z)
        assert (int(x), int(y)) in ts, f"모서리 {lon},{lat}가 타일 목록 밖"
    assert len(ts) == 600, f"z18 타일 수가 600이 아니다: {len(ts)}"
    # 침식이 화소를 줄이는가 — 10x10 정사각에서 r=0은 안쪽 전부, r=2는 더 적어야
    sq = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
    n0 = sum(_erode_ok(x + .5, y + .5, sq, 0.01) for x in range(11) for y in range(11))
    n2 = sum(_erode_ok(x + .5, y + .5, sq, 2.0) for x in range(11) for y in range(11))
    assert n0 == 100 and n2 == 36, f"침식이 이상하다 {n0} {n2}"
    # 중앙값은 정렬 기준이어야 한다
    assert _median([3, 1, 2]) == 2 and _median([4, 1, 2, 3]) == 3
    # 군집은 결정론이어야 한다 — 같은 입력에 같은 중심
    toy = [(10, 10, 10), (12, 11, 9), (200, 30, 30), (205, 28, 33),
           (30, 200, 40), (28, 198, 44)]
    c1, a1 = cluster(toy, k=3)
    c2, a2 = cluster(list(toy), k=3)
    assert c1 == c2 and a1 == a2, "군집이 결정론이 아니다"
    assert len(set(a1)) == 3, f"세 덩어리가 안 갈린다: {a1}"
    # 진단 함수 — 같은 색이면 거리 0
    assert nearest_gap([c1[0]], [c1[0]]) == [0.0], "nearest_gap"
    print("roofcolor selfcheck OK")


def _stats(sampled, blds):
    """2단계 체크포인트 — 쓰기 전에 표본이 쓸 만한지 본다."""
    import colorsys
    n = len(blds)
    ok = len(sampled)
    print(f"건물 {n} / 표본 성공 {ok} ({ok/n*100:.1f}%) / 폴백 {n-ok} ({(n-ok)/n*100:.1f}%)")
    if not ok:
        return
    hs = [0] * 12
    sat = 0.0
    for r, g, b in sampled.values():
        mx, mn = max(r, g, b), min(r, g, b)
        sv = 0 if mx == mn else (mx - mn) / (255 - abs(mx + mn - 255))
        sat += sv
        if sv > 0.08:
            hs[int(colorsys.rgb_to_hsv(r/255, g/255, b/255)[0] * 360 // 30) % 12] += 1
    print(f"평균 채도 {sat/ok:.3f}   (화면 기준선 0.129 / Isopolis 0.227)")
    print("색상환 30도: " + "  ".join(f"{i*30}~{i*30+30}° {v/ok*100:.1f}%"
                                      for i, v in enumerate(hs) if v))
    lum = sorted((max(c) + min(c)) / 2 for c in sampled.values())
    print(f"명도 p10/p50/p90  {lum[ok//10]:.0f} / {lum[ok//2]:.0f} / {lum[int(ok*.9)]:.0f}")
    # 높이별 성공률 — 고층이 실패하는 게 설계 의도다. 정말 그런지 확인한다
    band = {}
    for b in blds:
        h = b.get("h", 0)
        k = "0~10m" if h < 10 else "10~20m" if h < 20 else "20~50m" if h < 50 else "50m+"
        t, s = band.get(k, (0, 0))
        band[k] = (t + 1, s + (1 if b.get("gid") in sampled else 0))
    print("높이별 성공률: " + "  ".join(f"{k} {s}/{t} ({s/t*100:.0f}%)"
                                       for k, (t, s) in sorted(band.items())))


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        _selfcheck(); raise SystemExit
    import iso2
    st = iso2.STYLE
    z = int(st.get("ortho_zoom", ZOOM))
    k = int(st.get("ortho_k", K))
    lift = tuple(st.get("ortho_lift", LIFT))
    min_px = int(st.get("ortho_min_px", MIN_PX))
    bbox = (126.970, 37.551, 126.996, 37.582)

    blds = iso2.parse(os.path.join(HERE, "cache_bld.xml"))
    print(f"타일 수집 z{z} …", file=sys.stderr)
    print(fetch(bbox, z), file=sys.stderr)
    print("표본 추출 …", file=sys.stderr)
    t0 = time.time()
    raw = sample(blds, z=z, min_px=min_px)
    print(f"  ({time.time()-t0:.0f}s)", file=sys.stderr)

    _selfcheck()
    _stats(raw, blds)
    if "--stats" in sys.argv:
        print("\n--stats 모드 — cache_roof.json을 쓰지 않았다.")
        raise SystemExit

    gids = list(raw.keys())
    cols = [_lift(raw[g], lift) for g in gids]
    cent, asg = cluster(cols, k=k)
    gaps = nearest_gap(cent, palette_colors(st))
    out = {"zoom": z, "k": k, "lift": list(lift), "min_px": min_px,
           "mpp": round(mpp((bbox[1] + bbox[3]) / 2, z), 4),
           "centers": [list(c) for c in cent],
           "by_gid": {g: asg[i] for i, g in enumerate(gids)},
           "stats": {"buildings": len(blds), "sampled": len(gids),
                     "fallback": len(blds) - len(gids), "tiles": len(tiles(bbox, z))}}
    p = os.path.join(HERE, "cache_roof.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    import collections
    cnt = collections.Counter(asg)
    print(f"\n중심 {k}색 -> {p}")
    for j, c in enumerate(cent):
        print(f"  {j:2d} rgb({c[0]:3d},{c[1]:3d},{c[2]:3d})  {cnt[j]/len(gids)*100:5.1f}%"
              f"   기존 팔레트와 최소거리 {gaps[j]:5.1f}")
