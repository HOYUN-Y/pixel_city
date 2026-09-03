"""P2-1 — 공간데이터 렌더를 이미지 모델용 조건(condition) 이미지 4종으로 내보낸다.

`web/data/{city,layers,meta}.json`만 읽는다. V-World 키도, 원본 WFS 캐시도 필요 없다.
네 장 모두 같은 카메라·같은 크기로 그리므로 픽셀 좌표가 서로 정확히 대응한다.

    inputs/source/base_rgb.png      현재 팔레트 렌더 (기준선 / img2img 입력)
    inputs/source/camera.json       재투영용 카메라 (P2-7에서 POI를 다시 얹을 때 쓴다)
    inputs/conditions/edge.png      면 경계 흰 선 (painter 순서라 은면 제거됨)
    inputs/conditions/height.png    높이 명암
    inputs/conditions/mask.png      클래스별 단색 ID

투영은 `poc/iso2.py`의 것을 그대로 import 한다. 렌더러를 세 번째로 복제하지 않는다.

    python prototype2/scripts/conditions.py
    python prototype2/scripts/conditions.py --check
"""
import argparse, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "poc"))
import iso2                                  # noqa: E402  proj / depth / expand / STYLE
from export import dec_ring                  # noqa: E402  델타 인코딩 역변환
from PIL import Image, ImageDraw             # noqa: E402

DATA = os.path.join(ROOT, "web", "data")
BBOX = (126.9740, 37.5760, 126.9820, 37.5820)   # 경복궁~삼청동. poc/gyeongbok.png와 동일
PAD = 8

# 의미 마스크 색상 ID. 서로 충분히 떨어뜨려 후처리에서 정확히 되찾을 수 있게 한다.
MASK = {
    "bg":     (0, 0, 0),        "ground":  (64, 64, 64),
    "road":   (128, 128, 128),  "park":    (0, 160, 0),
    "water":  (0, 0, 255),      "heri":    (0, 96, 64),
    "palace": (255, 0, 0),      "hanok":   (255, 128, 0),
    "상업용": (0, 255, 255),    "주거용":  (255, 255, 0),
    "문교사회용": (255, 0, 255), "공업용": (160, 80, 0),
    "공공용": (0, 128, 255),    "bld":     (192, 192, 192),
}
GROUND_GRAY = 16        # 지면. bg(0)와 구분되어야 프레임 밖을 잘라낼 수 있다
HMAX = 60.0             # height.png 정규화 상한(m). 구역 최고층 건물 기준


def load():
    j = lambda n: json.load(open(os.path.join(DATA, f"{n}.json"), encoding="utf-8"))
    return j("city"), j("layers"), j("meta")


def camera(meta, bbox, size):
    """bbox 프레임이 size 안에 들어가는 배율·오프셋. iso2.fit과 같은 계산이다."""
    o = meta["origin"]
    to_en = lambda c: ((c[0] - o["lon0"]) * o["mlon"], (c[1] - o["lat0"]) * o["mlat"])
    frame = [to_en(c) for c in ((bbox[0], bbox[1]), (bbox[2], bbox[1]),
                                (bbox[2], bbox[3]), (bbox[0], bbox[3]))]
    pts = [iso2.proj(e, n, h, 1.0) for e, n in frame for h in (0.0, HMAX)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    s = max((max(xs) - min(xs)) / (size - 2 * PAD), (max(ys) - min(ys)) / (size - 2 * PAD))
    return {"scale": s, "size": size,
            "cx": size / 2 - (min(xs) + max(xs)) / 2 / s,
            "cy": size / 2 - (min(ys) + max(ys)) / 2 / s,
            "alpha_deg": iso2.STYLE["alpha_deg"], "phi_deg": iso2.STYLE["phi_deg"],
            "bbox": list(bbox), "origin": o, "hmax": HMAX, "frame_en": frame}


class Sheet:
    """네 장을 한 번에 그린다. 같은 폴리곤을 같은 순서로 칠하므로 은면 처리가 일치한다."""

    def __init__(self, cam):
        n = cam["size"]
        self.cam = cam
        self.im = {k: Image.new("RGB", (n, n), c) for k, c in
                   (("rgb", tuple(iso2.STYLE["colors"]["bg"])), ("edge", (0, 0, 0)),
                    ("height", (0, 0, 0)), ("mask", MASK["bg"]))}
        self.dr = {k: ImageDraw.Draw(v) for k, v in self.im.items()}

    def S(self, e, n, h):
        u, v = iso2.proj(e, n, h, self.cam["scale"])
        return (u + self.cam["cx"], v + self.cam["cy"])

    def face(self, pts, rgb, cls, h):
        """한 면. 네 장 전부 채워야 painter 순서로 뒤가 가려진다."""
        # 대부분의 건물이 3~15m라 선형이면 전부 어둡게 뭉친다. sqrt로 저층부를 벌린다.
        g = round(GROUND_GRAY + (255 - GROUND_GRAY) * min(h / HMAX, 1.0) ** 0.5)
        self.dr["rgb"].polygon(pts, fill=rgb)
        self.dr["height"].polygon(pts, fill=(g, g, g))
        self.dr["mask"].polygon(pts, fill=MASK.get(cls, MASK["bld"]))
        self.dr["edge"].polygon(pts, fill=(0, 0, 0), outline=(255, 255, 255))

    def line(self, pts, rgb, cls, w):
        self.dr["rgb"].line(pts, fill=rgb, width=w, joint="curve")
        self.dr["height"].line(pts, fill=(GROUND_GRAY,) * 3, width=w, joint="curve")
        self.dr["mask"].line(pts, fill=MASK[cls], width=w, joint="curve")
        self.dr["edge"].line(pts, fill=(255, 255, 255), width=1, joint="curve")

    def save(self, out):
        d = {"rgb": os.path.join(out, "source", "base_rgb.png")}
        for k in ("edge", "height", "mask"):
            d[k] = os.path.join(out, "conditions", f"{k}.png")
        for k, p in d.items():
            os.makedirs(os.path.dirname(p), exist_ok=True)
            self.im[k].save(p)
        return d


def render(city, layers, cam):
    sh, C = Sheet(cam), iso2.STYLE["colors"]
    q = 10.0
    en = lambda ring: dec_ring(ring)
    # 크롭 밖 지오메트리는 버린다. 프레임 여백까지 남기려고 20% 넉넉히 잡는다.
    fe = cam["frame_en"]
    lo = (min(p[0] for p in fe), min(p[1] for p in fe))
    hi = (max(p[0] for p in fe), max(p[1] for p in fe))
    m = (0.2 * (hi[0] - lo[0]), 0.2 * (hi[1] - lo[1]))
    inside = lambda pts: any(lo[0] - m[0] <= e <= hi[0] + m[0] and
                             lo[1] - m[1] <= n <= hi[1] + m[1] for e, n in pts)

    ext = 4000
    sh.face([sh.S(-ext, -ext, 0), sh.S(ext, -ext, 0),
             sh.S(ext, ext, 0), sh.S(-ext, ext, 0)], tuple(C["ground"]), "ground", 0)

    for key, cls, col in (("heri", "heri", C["heri"]), ("park", "park", C["park"]),
                          ("temple", "heri", C["heri"]), ("river", "water", C["river"])):
        for r in layers.get(key, []):
            pts = en(r)
            if len(pts) >= 3 and inside(pts):
                sh.face([sh.S(e, n, 0) for e, n in pts], tuple(col), cls, 0)
    for w10, r in sorted(layers.get("road", []), key=lambda x: x[0]):
        pts = en(r)
        if inside(pts):
            sh.line([sh.S(e, n, 0) for e, n in pts], tuple(C["road"]), "road",
                    max(1, round(w10 / q / cam["scale"])))

    pal = {k: tuple(map(tuple, v)) for k, v in C["use"].items()}
    for i in range(city["n"]):                     # export.py가 먼 것부터 정렬해 두었다
        pts = en(city["rings"][i])
        if not inside(pts):
            continue
        h, k = city["h"][i] / q, city["kind"][i]
        ui = city["use"][i]
        use = city["uses"][ui] if ui >= 0 else None
        if k:                                      # 목구조 — 낮은 기둥부 + 내민 처마
            cls = "palace" if k == 2 else "hanok"
            roof, lit, dark = map(tuple, C["palace"] if k == 2 else C["hanok"])
            body = h * 0.5
            walls(sh, pts, 0, body, lit, dark, cls, body)
            eave = iso2.expand(pts, iso2.STYLE["eave"])
            shade = tuple(int(c * 0.72) for c in roof)
            walls(sh, eave, body, h, roof, shade, cls, h)
            sh.face([sh.S(e, n, h) for e, n in eave], roof, cls, h)
        else:
            cls = use if use in MASK else "bld"
            roof, lit, dark = pal.get(use, tuple(map(tuple, C["default"])))
            walls(sh, pts, 0, h, lit, dark, cls, h)
            sh.face([sh.S(e, n, h) for e, n in pts], roof, cls, h)
    return sh


def walls(sh, pts, h0, h1, lit, dark, cls, h):
    import math
    a = math.radians(iso2.STYLE["alpha_deg"])
    for (e1, n1), (e2, n2) in zip(pts, pts[1:]):
        nx, nz = (n2 - n1), -(e2 - e1)
        if nx * math.sin(a) + nz * math.cos(a) <= 0:       # 뒷면
            continue
        c = lit if abs(nx) / (math.hypot(nx, nz) + 1e-9) > 0.5 else dark
        sh.face([sh.S(e1, n1, h0), sh.S(e2, n2, h0),
                 sh.S(e2, n2, h1), sh.S(e1, n1, h1)], c, cls, h)


def selfcheck():
    _, _, meta = load()
    for g in meta["golden"]:                       # 투영이 뷰어·파이썬과 같은지
        u, v = iso2.proj(g["e"], g["n"], g["h"], 1.0)
        assert abs(u - g["u"]) < 1e-6 and abs(v - g["v"]) < 1e-6, g
    cam = camera(meta, BBOX, 256)
    assert cam["scale"] > 0
    p0, p1 = Sheet(cam).S(0, 0, 0), Sheet(cam).S(0, 0, 20)
    assert p1[1] < p0[1], "높이가 화면 위쪽이어야 한다"
    assert len(set(MASK.values())) == len(MASK), "마스크 색 ID가 겹친다"
    print("selfcheck ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", default=",".join(map(str, BBOX)))
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--out", default=os.path.join(ROOT, "prototype2", "inputs"))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    selfcheck()
    if a.check:
        sys.exit(0)

    city, layers, meta = load()
    cam = camera(meta, tuple(map(float, a.bbox.split(","))), a.size)
    sh = render(city, layers, cam)
    paths = sh.save(a.out)
    cam.pop("frame_en")
    cp = os.path.join(a.out, "source", "camera.json")
    json.dump(cam, open(cp, "w"), indent=1)
    sizes = {Image.open(p).size for p in paths.values()}
    assert len(sizes) == 1, sizes                  # 네 장 정합 자동 검사
    for k, p in sorted(paths.items()):
        print(f"  {k:7s} {os.path.relpath(p, ROOT)}")
    print(f"  camera  {os.path.relpath(cp, ROOT)}  scale {cam['scale']:.3f} m/px  {sizes.pop()}")
