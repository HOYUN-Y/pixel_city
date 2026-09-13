"""공개DEM(.img) -> 뷰어용 표고 격자 `web/data/terrain.json`.

좌표계 골칫거리를 여기서 끝낸다. 브라우저는 축정렬 직사각 배열에 이중선형만 하면 된다.

핵심: ENU는 lon/lat의 선형 사상이다 (e=(lon-lon0)*mlon, n=(lat-lat0)*mlat).
따라서 ENU 정규격자는 EPSG:4326의 축정렬 격자와 같고, reproject 한 번으로 끝난다.

프레임(origin/bbox)은 `web/data/meta.json`에서 읽는다. `export.py`를 import하면
export -> iso2 -> PIL 연쇄로 죽고(Pillow 없음), origin()을 복붙하면 프레임이 분기한다.
meta.json은 커밋된 city.json과 같은 프레임을 이미 데이터로 갖고 있다.

    uv run --with rasterio python terrain.py <37608.img> --check
    uv run --with rasterio python terrain.py <37608.img>
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
WEB  = os.path.join(os.path.dirname(HERE), "web", "data")
Q    = 10.0                      # 0.1m 정수 양자화 (저장소 공통 관례)
STEP = 90.0                      # 원본 해상도와 같게. 더 잘게 해도 정보가 늘지 않는다
ALPHA_DEG = 22.5                 # 페인터 순서 검산용. style.json alpha_deg와 같아야 한다
PAD  = 900.0                     # 10셀. 프레임 밖으로 격자 끝을 밀어낸다 (아래 참조)

# 실측 대조표 — docs/WORKLOG.md 2026-09-04 "DEM 2차 검증: 도엽 37608"
ORACLE = [(126.9882, 37.5512, 266.0, "남산"),
          (126.9770, 37.5796,  38.4, "경복궁"),
          (126.9780, 37.5665,  30.8, "시청")]


def frame(meta_path=None):
    """meta.json -> (origin, bbox). ENU <-> lon/lat 환산 상수."""
    m = json.load(open(meta_path or os.path.join(WEB, "meta.json"), encoding="utf-8"))
    o = m["origin"]
    return (o["lon0"], o["lat0"], o["mlon"], o["mlat"]), tuple(m["bbox"])


def _fill_nodata(a, nodata):
    """가장 가까운 유효값으로 메운다 (행 방향 -> 열 방향).

    패드 동쪽 일부가 도엽 밖으로 나갈 수 있다. 패드는 '프레임 끝에서 지형이
    절벽으로 끊기지 않게' 두는 것이므로, 바깥으로 평평히 잇는 것이 의도에 맞다.
    ponytail: 2.5k셀짜리 파이썬 루프. 격자가 커지면 scipy 쓰면 된다.
    """
    ny, nx = a.shape
    bad = 0
    for j in range(ny):                                  # 행 방향
        row = a[j]
        valid = [i for i in range(nx) if row[i] != nodata]
        if not valid:
            continue
        for i in range(nx):
            if row[i] == nodata:
                row[i] = row[min(valid, key=lambda v: abs(v - i))]
                bad += 1
    for i in range(nx):                                  # 남은 것은 열 방향
        col = a[:, i]
        valid = [j for j in range(ny) if col[j] != nodata]
        if not valid:
            continue
        for j in range(ny):
            if col[j] == nodata:
                col[j] = col[min(valid, key=lambda v: abs(v - j))]
                bad += 1
    return bad


def grid(img, origin, bbox, step=STEP, pad=PAD, style=None):
    """DEM -> ENU 축정렬 표고 격자 dict.

    음영 상수(exag/light/gain/shade)도 함께 실어 보낸다. 두 렌더러가 같은 숫자를
    읽게 하려는 것이다 — style.json은 export.py가 meta.json에 복사해야 뷰어에
    닿는데 수집 캐시가 없어 지금 돌릴 수 없다.
    """
    style = style or {}
    import numpy as np, rasterio
    from rasterio.transform import Affine
    from rasterio.warp import reproject, Resampling

    lon0, lat0, mlon, mlat = origin
    halfE = (bbox[2] - bbox[0]) / 2 * mlon
    halfN = (bbox[3] - bbox[1]) / 2 * mlat
    e0, n0 = -(halfE + pad), -(halfN + pad)
    nx = int(math.ceil((2 * (halfE + pad)) / step)) + 1
    ny = int(math.ceil((2 * (halfN + pad)) / step)) + 1

    # 목적 래스터: EPSG:4326, 픽셀 '중심'이 격자점에 오도록 반 픽셀 밀어 놓는다
    dx, dy = step / mlon, step / mlat
    lon_w = lon0 + e0 / mlon
    lat_n = lat0 + (n0 + (ny - 1) * step) / mlat         # 행 0 = 최북단 (rasterio 관례)
    dst_t = Affine.translation(lon_w - dx / 2, lat_n + dy / 2) * Affine.scale(dx, -dy)

    dst = np.full((ny, nx), -9999.0, dtype="float32")
    with rasterio.open(img) as src:
        reproject(source=rasterio.band(src, 1), destination=dst,
                  src_transform=src.transform, src_crs=src.crs, src_nodata=src.nodata,
                  dst_transform=dst_t, dst_crs="EPSG:4326", dst_nodata=-9999.0,
                  resampling=Resampling.bilinear)
    filled = _fill_nodata(dst, -9999.0)
    dst = np.flipud(dst)                                 # 행 0 = 최남단 (n 증가 방향)

    # datum = ENU 원점(=bbox 중심, 평지 도심)의 표고. 재현 가능하고 프레이밍이 유지된다
    oi, oj = (0.0 - e0) / step, (0.0 - n0) / step
    z0 = float(_bilin(dst, nx, ny, oi, oj))
    rel = dst - z0
    g = {"nx": nx, "ny": ny, "step": step,
         "e0": round(e0, 1), "n0": round(n0, 1),
         "z0": round(z0, 1),
         "exag": style.get("terrain_exag", 1.0),
         "light": style.get("terrain_light", [1.0, 0.35]),
         "gain": style.get("terrain_gain", 3),
         "zband": style.get("terrain_zband", 50.0),
         "neutral": style.get("terrain_neutral", 2),
         # 채널별 배율. 위로 갈수록 R>G>B -> 밝아지며 난색으로 이동한다
         "shade": style.get("terrain_shade", [[1.0, 1.0, 1.0]] * 3),
         "zmin": round(float(rel.min()), 1), "zmax": round(float(rel.max()), 1),
         "src": os.path.basename(img), "pad": pad, "filled": filled,
         "z": [int(round(v * Q)) for v in rel.ravel().tolist()]}
    g["golden"] = [{"e": round(e, 1), "n": round(n, 1), "z": round(zq(g, e, n), 3)}
                   for e, n in [(459.0, -1691.0), (-529.0, 1448.0), (0.0, 0.0)]]
    return g


def _bilin(a, nx, ny, fi, fj):
    """2D 배열 이중선형. fi/fj는 격자 인덱스 좌표."""
    i, j = int(math.floor(fi)), int(math.floor(fj))
    if i < 0 or j < 0 or i > nx - 1 or j > ny - 1:
        return 0.0
    i, j = min(i, nx - 2), min(j, ny - 2)                # 마지막 행·열 클램프
    u, v = fi - i, fj - j
    return ((a[j][i] * (1 - u) + a[j][i + 1] * u) * (1 - v)
            + (a[j + 1][i] * (1 - u) + a[j + 1][i + 1] * u) * v)


def zq(g, e, n):
    """격자 표고(datum 상대 미터). 격자 밖은 0. **app.js zAt()의 파이썬 거울.**

    ⚠️ 과장(exag)은 **적용하지 않는다.** 순수 DEM 값이라 golden도 이 기준이다.
    쓰는 쪽에서 곱한다 (app.js zAt은 TEXAG를 곱하므로 golden 대조 시 나눈다,
    iso2.py는 Z()에서 곱한다).
    """
    fi, fj = (e - g["e0"]) / g["step"], (n - g["n0"]) / g["step"]
    nx, ny = g["nx"], g["ny"]
    if fi < 0 or fj < 0 or fi > nx - 1 or fj > ny - 1:
        return 0.0
    i, j = min(int(math.floor(fi)), nx - 2), min(int(math.floor(fj)), ny - 2)
    u, v = fi - i, fj - j
    z, at = g["z"], lambda ii, jj: z[jj * nx + ii] / Q
    return ((at(i, j) * (1 - u) + at(i + 1, j) * u) * (1 - v)
            + (at(i, j + 1) * (1 - u) + at(i + 1, j + 1) * u) * v)


def _rnd(x):
    """JS Math.round와 **동일한** 반올림. 파이썬 round()는 0.5에서 짝수로 가고
    JS는 위로 간다 (round(2.5): 파이썬 2, JS 3). 이식 함정이라 맞춰 둔다."""
    return math.floor(x + 0.5)


def _in_poly(px, py, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def cells(g, zones=()):
    """음영 셀 목록 [(i, j, 단계, 지표)]. **app.js buildTerrainCells()의 파이썬 거울.**

    단계 = neutral + round(표고/zband) - round(경사*gain), 램프 범위로 clamp.

    - **표고 밴드가 주 신호다.** 경사만 쓰면 균일 사면이 균일 톤이 되어 산이 평지와
      같은 색으로 칠해진다 (실측: 남산 종단면 232m->31m 구간에서 단계가 2·3 두 개만
      쓰이고, 단계 2의 휘도는 평지 공원과 완전히 동일했다). 지도가 산을 보여주는
      방식은 표고별 색조다. 경사는 국지적 형태(능선·골)를 얹는 보조 신호로만 쓴다.
    - 기울기는 3x3 중앙차분으로 평활한다. 단일 셀 차분은 90m DEM의 셀 잡음을 그대로
      증폭해 언덕이 패치워크로 읽힌다 (남산 220셀 실측: 인접 단계차 0.39 vs 0.20).
    - neutral 단계(배율 1.0 = 평지)는 제외한다 — 기존 폴리곤 렌더의 크리스프한 경계를
      덮지 않고 기복이 있는 곳만 덮는다. zband(60m)가 도심 대역폭(41.5m)보다 커서
      평지 도심은 대부분 여기 남는다.
    - zones = [(지표번호, ring)]. 그리는 순서대로 주고 마지막 일치를 쓴다.
    """
    nx, ny, step, z = g["nx"], g["ny"], g["step"], g["z"]
    k = g.get("exag", 1.0) / Q
    le, ln = g.get("light", [1.0, 0.35])
    gain = g.get("gain", 3)
    zband = g.get("zband", 50.0)
    neutral = g.get("neutral", 2)
    top = len(g.get("shade", [0] * 8)) - 1
    zc = lambda i, j: z[min(ny - 1, max(0, j)) * nx + min(nx - 1, max(0, i))] * k
    boxes = []
    for cover, ring in zones:
        xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
        boxes.append((cover, min(xs), min(ys), max(xs), max(ys), ring))
    out = []
    for j in range(ny - 2, -1, -1):                  # 먼 것부터 (t 내림차순)
        for i in range(nx - 2, -1, -1):
            grad = ((zc(i+2, j) + zc(i+2, j+1) - zc(i-1, j) - zc(i-1, j+1)) / 2 * le
                  + (zc(i, j+2) + zc(i+1, j+2) - zc(i, j-1) - zc(i+1, j-1)) / 2 * ln) \
                  / (3 * step)
            zmid = (zc(i, j) + zc(i+1, j) + zc(i, j+1) + zc(i+1, j+1)) / 4
            lv = max(0, min(top, neutral + _rnd(zmid / zband) - _rnd(grad * gain)))
            if lv == neutral:
                continue
            ce, cn = g["e0"] + (i + 0.5) * step, g["n0"] + (j + 0.5) * step
            cover = 0
            for cv, x0, y0, x1, y1, ring in boxes:
                if x0 <= ce <= x1 and y0 <= cn <= y1 and _in_poly(ce, cn, ring):
                    cover = cv
            out.append((i, j, lv, cover))
    return out


def _selfcheck(g, img, origin):
    import rasterio
    from rasterio.warp import transform
    lon0, lat0, mlon, mlat = origin
    to_en = lambda lo, la: ((lo - lon0) * mlon, (la - lat0) * mlat)

    assert len(g["z"]) == g["nx"] * g["ny"], (len(g["z"]), g["nx"], g["ny"])
    assert all(v > -5000 for v in g["z"]), "nodata(-9999)가 격자에 남았다"

    # (1) 원본 직접 표본 — 좌표계/도엽이 바뀌면 여기서 깨진다
    with rasterio.open(img) as d:
        xs, ys = transform("EPSG:4326", d.crs,
                           [o[0] for o in ORACLE], [o[1] for o in ORACLE])
        raw = [list(d.sample([(x, y)]))[0][0] for x, y in zip(xs, ys)]
    for (lo, la, want, nm), got in zip(ORACLE, raw):
        assert abs(got - want) < 20, f"원본 {nm}: {got:.1f} != {want}"

    # (2) 격자 경유 — 행/열 전치·부호 오류를 잡는 핵심 assert
    for lo, la, want, nm in ORACLE:
        got = zq(g, *to_en(lo, la)) + g["z0"]
        assert abs(got - want) < 25, f"격자 {nm}: {got:.1f} != {want}"

    # (3) 방향성·기준면·경계
    assert zq(g, 459.0, -1691.0) - zq(g, -529.0, 1448.0) > 150, "남산이 경복궁보다 높지 않다"
    assert abs(zq(g, 0.0, 0.0)) < 0.05, "원점은 datum이라 0이어야 한다"
    assert zq(g, 1e9, 1e9) == 0.0, "격자 밖은 0"
    assert g["zmax"] - g["zmin"] > 150, "남산 기복이 살아 있지 않다"
    # 격자점에서 이중선형은 원값과 일치해야 한다 (메시 꼭짓점이 이걸 전제한다)
    assert abs(zq(g, g["e0"], g["n0"]) - g["z"][0] / Q) < 1e-9
    last = (g["ny"] - 1) * g["nx"] + g["nx"] - 1
    assert abs(zq(g, g["e0"] + (g["nx"] - 1) * g["step"],
                    g["n0"] + (g["ny"] - 1) * g["step"]) - g["z"][last] / Q) < 1e-9, \
        "마지막 격자점 클램프가 안 걸렸다"

    # (4) 음영 셀 — 평지는 빠지고, 남산에 경사 셀이 몰려야 한다
    cs = cells(g)
    assert cs, "음영 셀이 하나도 없다"
    assert all(lv != 2 for _, _, lv, _ in cs), "평지(단계 2)가 섞여 있다"
    tot = (g["nx"] - 1) * (g["ny"] - 1)
    assert 0.1 < len(cs) / tot < 0.6, f"경사 셀 비율이 이상하다: {len(cs)/tot:.2f}"
    ns = [g["n0"] + (j + 0.5) * g["step"] for _, j, _, _ in cs]
    south = sum(1 for v in ns if v < -1000) / len(ns)
    assert south > 0.25, f"경사 셀이 남산(남단)에 몰리지 않는다: {south:.2f}"
    # 페인터 순서 — 중첩 루프 불변식: 행(j)이 내림차순, 행 안에서 i가 내림차순.
    # 전역 t 내림차순은 성립하지 않는다 (한 행의 동쪽 끝이 다음 행 서쪽 끝보다 t가 작다).
    # 그래도 무해한 이유를 아래에서 실제로 검산한다.
    assert all((cs[k][1], -cs[k][0]) <= (cs[k + 1][1], -cs[k + 1][0]) or
               cs[k][1] > cs[k + 1][1] for k in range(len(cs) - 1)), "루프 순서가 깨졌다"
    rows = [j for _, j, _, _ in cs]
    assert rows == sorted(rows, reverse=True), "행이 내림차순이 아니다"

    # 순서가 뒤집힌 쌍은 화면 u 구간이 겹치지 않아야 한다 (겹치면 실제로 잘못 덮인다).
    # t = e·sinα + n·cosα, u = e·cosα - n·sinα. 표본으로 본다 — 전수는 O(n^2)다.
    import math as _m
    al, st = _m.radians(ALPHA_DEG), g["step"]
    def tu(i, j):
        e, n = g["e0"] + i * st, g["n0"] + j * st
        t = min((e + de) * _m.sin(al) + (n + dn) * _m.cos(al)
                for de in (0, st) for dn in (0, st))
        us = [(e + de) * _m.cos(al) - (n + dn) * _m.sin(al)
              for de in (0, st) for dn in (0, st)]
        return t, min(us), max(us)
    smp = [tu(i, j) for i, j, _, _ in cs[::max(1, len(cs) // 200)]]
    bad = [(a, b) for x, a in enumerate(smp) for b in smp[x + 1:]
           if b[0] > a[0] and b[1] < a[2] and a[1] < b[2]]
    assert not bad, f"나중에 그리는 먼 셀이 화면에서 겹친다: {bad[:2]}"
    print("terrain selfcheck ok")


def main(img, out=None, check_only=False):
    origin, bbox = frame()
    style = json.load(open(os.path.join(HERE, "style.json"), encoding="utf-8"))
    g = grid(img, origin, bbox, style=style)
    _selfcheck(g, img, origin)
    print(f"격자 {g['nx']}x{g['ny']} = {g['nx']*g['ny']}점 / step {g['step']:.0f}m "
          f"/ pad {g['pad']:.0f}m / nodata 보간 {g['filled']}칸")
    print(f"datum z0 {g['z0']:.1f}m / 상대고도 {g['zmin']:.1f} ~ {g['zmax']:.1f}m "
          f"/ exag {g['exag']} / light {g['light']} / gain {g['gain']}")
    print(f"음영 셀 {len(cells(g))}개 (격자 {(g['nx']-1)*(g['ny']-1)}칸 중 경사 있는 것만)")
    if check_only:
        return g
    out = out or os.path.join(WEB, "terrain.json")
    json.dump(g, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"  terrain.json  {os.path.getsize(out)/1024:.1f} KB")
    return g


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if not a:
        print(__doc__); raise SystemExit(1)
    main(a[0], a[1] if len(a) > 1 else None, "--check" in sys.argv)
