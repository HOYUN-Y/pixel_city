"""Local SDXL assets + deterministic Seoul diorama rendering.

Pilot output is deliberately separate from the approved full map. Full-map
commands require a review record matching the current pilot/config/assets.
"""
import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont

import conditions
from geometry import DATA
from freeze_inputs import freeze

P2 = Path(__file__).resolve().parents[1]
WORK = P2 / "work/diorama"
ASSETS = P2 / "assets/diorama"
EVAL = P2 / "eval/diorama"
CONFIG = P2 / "configs/diorama.json"


def read(p):
    return json.loads(Path(p).read_text())


def write(p, v):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n")


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def assets():
    """Freeze already-generated local SDXL outputs; never call a remote model."""
    source = P2 / "work/style_bank"
    manifest = read(source / "style_manifest.json")
    ASSETS.mkdir(parents=True, exist_ok=True)
    selected = {}
    for kind, filename in manifest["selected"].items():
        entry = next(i for i in manifest["items"] if i["texture"] == filename)
        src = source / filename
        if digest(src) != entry["sha256"]:
            raise RuntimeError(f"SDXL source asset hash mismatch: {kind}")
        dest = ASSETS / (kind + ".png")
        shutil.copyfile(src, dest)
        selected[kind] = {**entry, "file": dest.name, "sha256": digest(dest)}
    write(ASSETS / "manifest.json", {
        "model": manifest["model"], "revision": manifest["model_revision"],
        "generation": "Previously generated on local Mac MPS; no new inference",
        "selected": selected})
    print(f"Frozen {len(selected)} local SDXL assets")


def setup():
    freeze()
    cfg = read(CONFIG)
    if cfg["art_pixel"] != 3 or cfg["max_extension_art_pixels"] != 4:
        raise ValueError("This renderer uses the reviewed 3px grid / 4-art-pixel limit")
    ramps = {k: np.array([ImageColor.getrgb(c) for c in v], dtype=np.uint8)
             for k, v in cfg["ramps"].items()}
    if sum(len(v) for v in ramps.values()) != 48:
        raise ValueError("Expected 48 palette entries")
    manifest = read(ASSETS / "manifest.json")
    textures = {}
    for kind, v in manifest["selected"].items():
        p = ASSETS / v["file"]
        if digest(p) != v["sha256"]:
            raise RuntimeError(f"Changed frozen AI asset: {p}")
        # Pixel motifs, not full-screen high-frequency stripes. Fixed statistics
        # per asset (never per tile) are essential to overlap consistency.
        im = Image.open(p).convert("L").resize((32, 32), Image.Resampling.BOX)
        a = np.asarray(im, dtype=np.float32)
        textures[kind] = np.digitize(a, np.quantile(a, [.25, .5, .75]))
    return cfg, ramps, textures, read(DATA / "tile_manifest.json")


def shift(a, dx, dy):
    out = np.zeros_like(a)
    h, w = a.shape
    if abs(dx) >= w or abs(dy) >= h:
        return out
    out[max(dy, 0):min(h, h + dy), max(dx, 0):min(w, w + dx)] = \
        a[max(-dy, 0):min(h, h - dy), max(-dx, 0):min(w, w - dx)]
    return out


class ArtSheet(conditions.Sheet):
    """Keep visible face IDs to orient windows and roof ridges, without
    altering any of the six baseline geometry/semantic channels."""

    def __init__(self, cam):
        super().__init__(cam)
        self.face_ids = Image.new("I", (cam["size"], cam["size"]))
        self.face_draw = ImageDraw.Draw(self.face_ids)
        self.face_data = [(0., 0., 0., 0., 0.)]
        self.heritage = Image.new("L", (cam["size"], cam["size"]))

    def face(self, pts, rgb, cls, h, surface="ground", object_id=0):
        super().face(pts, rgb, cls, h, surface, object_id)
        if surface == "heri":
            ImageDraw.Draw(self.heritage).polygon(pts, fill=255)
        if surface.startswith("wall"):
            p, q = pts[0], pts[1]
            slope = (q[1] - p[1]) / (q[0] - p[0]) if abs(q[0] - p[0]) > 1 else 0.
            self.face_data.append((slope, pts[2][1] - slope * pts[2][0], p[0], 0., 0.))
        else:
            # A ridge follows the longest footprint edge and stays inside roof.
            ring = pts[:-1] if pts[0] == pts[-1] else pts
            pairs = list(zip(ring, ring[1:] + ring[:1]))
            p, q = max(pairs, key=lambda pq: (pq[0][0]-pq[1][0])**2 + (pq[0][1]-pq[1][1])**2)
            dx, dy = q[0]-p[0], q[1]-p[1]
            length = max(math.hypot(dx, dy), 1.)
            cx = sum(p[0] for p in ring) / len(ring)
            cy = sum(p[1] for p in ring) / len(ring)
            self.face_data.append((dy / length, dx / length, cx, cy, length))
        self.face_draw.polygon(pts, fill=len(self.face_data)-1)

    def line(self, pts, rgb, cls, w):
        super().line(pts, rgb, cls, w)
        self.face_draw.line(pts, fill=0, width=w, joint="curve")


def styled(sheet, ramps, tex, x0, y0, cfg):
    surface = np.asarray(sheet.im["surface"])[..., 0]
    cls = np.asarray(sheet.im["mask"])
    oid_rgb = np.asarray(sheet.im["object_id"]).astype(np.int32)
    oid = oid_rgb[..., 0] * 65536 + oid_rgb[..., 1] * 256 + oid_rgb[..., 2]
    h, w = surface.shape
    y, x = np.indices((h, w))
    local_x, local_y = x, y
    x, y = x + x0, y + y0
    ax, ay = np.floor_divide(x, 3), np.floor_divide(y, 3)
    # Inverse isometric axes: roof and paving patterns follow the map plane.
    u = np.floor((.924 * x - .765 * y) / 3).astype(np.int32)
    v = np.floor((-.383 * x - 1.848 * y) / 3).astype(np.int32)
    variation = (oid * 1103515245 + cfg["seed"]) % 2147483647
    face = np.asarray(sheet.face_ids)
    data = np.asarray(sheet.face_data)
    out = np.empty((h, w, 3), dtype=np.uint8)
    out[:] = ramps["stone"][2]

    def material(kind, xx=u, yy=v):
        a = tex[kind]
        return a[np.mod(yy, a.shape[0]), np.mod(xx, a.shape[1])]

    def paint(mask, ramp, level):
        colors = ramps[ramp][np.clip(level, 0, 3)]
        out[mask] = colors[mask] if colors.ndim == 3 else colors

    def isclass(name):
        return np.all(cls == conditions.MASK[name], axis=2)

    s = conditions.SURFACE
    ground = surface == s["ground"]
    heri = surface == s["heri"]
    park = surface == s["park"]
    # Heritage and park polygons overlap in the source. Preserve the source
    # masks, but use open courtyard materials where a heritage polygon exists.
    courtyard = (np.asarray(sheet.heritage) > 0) & (park | heri)
    park = park & ~courtyard
    heri = heri | courtyard
    road = surface == s["road"]
    water = surface == s["water"]
    roof = surface == s["roof"]
    wall = (surface == s["wall_lit"]) | (surface == s["wall_dark"])
    building = oid != 0
    palace, hanok = isclass("palace"), isclass("hanok")
    wood = palace | hanok
    # Warm urban ground and heritage courtyards. Heritage polygons are not
    # tree observations: keep them open, with paving instead of invented trees.
    ground_level = 2 + ((material("ground") == 3) & ((u + v) % 7 == 0))
    paint(ground | heri, "stone", ground_level)
    joints = heri & ((u % 18 == 0) | ((v + (u // 18 % 2) * 8) % 16 == 0))
    paint(joints, "stone", 1)
    # Canopy-like flat clusters wholly confined to observed park polygons.
    wu = u + np.floor(5 * np.sin(v / 13) + 3 * np.sin(u / 29)).astype(int)
    wv = v + np.floor(5 * np.sin(u / 17) + 2 * np.sin(v / 23)).astype(int)
    cellx, celly = np.floor_divide(wu, 16), np.floor_divide(wv, 16)
    noise = ((cellx * 73856093) ^ (celly * 19349663) ^ cfg["seed"]) % 11
    radial = ((wu % 16 - 5 - noise % 5) ** 2 + (wv % 16 - 5 - noise % 4) ** 2)
    leaves = material("vegetation", ax // 2 + cellx, ay // 2 + celly)
    green_level = np.where(radial < 40 + noise * 2, 1 + (leaves >= 2), 1)
    green_level = np.where((radial > 80) & (noise < 3), 0, green_level)
    green_level += ((wu % 16 < 6) & (wv % 16 < 5) & (radial < 22) & (leaves == 3))
    paint(park, "green", green_level)
    paint(water, "water", 1 + ((v % 11 < 2) & (material("ground") >= 2)))
    paint(road, "road", 1)
    # No guessed road markings. A light curb follows the existing road mask.
    road_inner = road & ~shift(road, 0, 3)
    paint(road_inner, "road", 2)
    # Short contact shadows, never new objects. L-infinity limit = 12px.
    shadow = shift(building, 9, 9) & ~building
    shadow &= ground | heri | park | road
    paint(shadow & (ground | heri), "stone", 0)
    paint(shadow & road, "road", 0)
    paint(shadow & park, "green", 0)
    roof_map = [(palace, "palace", "palace_roof"),
                (hanok, "hanok", "hanok_roof"),
                (isclass("주거용"), "brick", "residential_roof"),
                (isclass("공공용") | isclass("문교사회용"), "cream", "civic_roof")]
    paint(roof, "glass", 2 + (material("commercial_roof") == 3))
    for mask, ramp, key in roof_map:
        a = material(key)
        levels = 1 + (a >= 2)
        if ramp in ("palace", "hanok"):
            levels = np.where(u % 4 == 0, 3, levels)
            levels = np.where(v % 12 == 0, 0, levels)
        paint(roof & mask, ramp, levels)
    ridge_distance = ((local_y - data[face, 3]) * data[face, 1]
                      - (local_x - data[face, 2]) * data[face, 0])
    for mask, ramp in ((palace, "palace"), (hanok, "hanok")):
        paint(roof & mask & (ridge_distance > 3), ramp, 1 + (u % 4 == 0))
        paint(roof & mask & (np.abs(ridge_distance) <= 2) & (data[face, 4] > 18), ramp, 3)
    lit = surface == s["wall_lit"]
    paint(wall, "cream", np.where(lit, 2, 1))
    paint(wall & isclass("주거용") & (variation % 3 == 0), "brick", np.where(lit, 2, 1))
    # Floor stripes follow each visible wall orientation. Object seed shifts
    # window spacing but never changes the footprint or building height.
    floor = np.floor((local_y - data[face, 0] * local_x - data[face, 1]) / 3 + 1e-7).astype(int)
    columns = np.floor((local_x - data[face, 2]) / 3 + 1e-7).astype(int) + variation % 5
    windows = wall & ~wood & (columns % 5 < 3) & (floor % 6 >= 1) & (floor % 6 < 4)
    paint(windows, "glass", np.where(lit, 2, 0) + (material("wall", columns, floor) == 3))
    paint(windows & (floor % 6 == 1), "glass", np.where(lit, 3, 1))
    paint(wall & ~wood & (floor % 6 == 5), "cream", np.where(lit, 3, 0))
    paint(wall & wood, "timber", np.where(lit, 2, 0))
    paint(wall & wood & (columns % 6 < 4), "cream", np.where(lit, 2, 1))
    paint(wall & palace & (floor % 6 < 2), "dancheong", 1 + (columns % 4 == 0))
    # Eave-only extension, at most one art pixel, underneath other buildings.
    traditional = roof & wood
    spread = np.asarray(Image.fromarray(traditional).filter(ImageFilter.MaxFilter(7)))
    eave = spread & ~building & (ground | heri | park)
    paint(eave, "palace", 0)
    # Original structure is readable but not every texture receives black ink.
    boundary = building & ((oid != shift(oid, 1, 0)) | (oid != shift(oid, 0, 1)))
    paint(boundary, "ink", 1)
    roof_light = roof & ~shift(roof, 0, 1)
    paint(roof_light & ~wood, "cream", 3)
    effect = np.zeros((h, w), np.uint8)
    effect[shadow] = 1
    effect[eave] = 2
    return Image.fromarray(out), Image.fromarray(effect)


def region_camera(manifest, x, y, size, margin=15):
    cam = {**manifest["global_camera"], "size": size + margin * 2,
           "cx": manifest["global_camera"]["cx"] - x + margin,
           "cy": manifest["global_camera"]["cy"] - y + margin}
    o = cam["origin"]
    b = cam["bbox"]
    cam["frame_en"] = [((lon - o["lon0"]) * o["mlon"], (lat - o["lat0"]) * o["mlat"])
                       for lon, lat in ((b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]))]
    return cam


def render_region(cfg, ramps, tex, manifest, x, y, size):
    # Context margin makes decoration independent of crop/tile boundaries.
    margin = 15
    cam = region_camera(manifest, x, y, size, margin)
    city, layers, _ = conditions.load()
    sh = conditions.render(city, layers, cam, sheet_type=ArtSheet)
    result, effect = styled(sh, ramps, tex, x - margin, y - margin, cfg)
    box = (margin, margin, margin + size, margin + size)
    channels = {k: im.crop(box) for k, im in sh.im.items()}
    return result.crop(box), effect.crop(box), channels


def signature():
    return {"config": digest(CONFIG), "renderer": digest(__file__),
            "conditions": digest(P2 / "scripts/conditions.py"),
            "geometry": digest(P2 / "scripts/geometry.py"),
            "snapshot": digest(DATA / "snapshot.json"),
            "assets": digest(ASSETS / "manifest.json")}


def change_score(a, b, valid):
    delta = np.abs(np.asarray(a).astype(int) - np.asarray(b).astype(int)).max(axis=2)
    return float((delta[valid] >= 18).mean()) if valid.any() else 0.


def pilot():
    cfg, ramps, tex, manifest = setup()
    EVAL.mkdir(parents=True, exist_ok=True)
    original = Image.open(P2 / "work/fullmap/mosaic.png").convert("RGB")
    report = {"signature": signature(), "status": "awaiting_user_visual_review", "pilots": []}
    overview = Image.new("RGB", (1536, 3 * 560 + 70), "#eee5d4")
    dr = ImageDraw.Draw(overview)
    dr.text((20, 20), "SEOUL DIORAMA / THREE DISTRICTS / SAME CAMERA", fill="#343e48", font=font(25))
    for i, p in enumerate(cfg["pilots"]):
        size, x, y = cfg["pilot_size"], p["x"], p["y"]
        im, effect, ch = render_region(cfg, ramps, tex, manifest, x, y, size)
        locked = original.crop((x, y, x + size, y + size))
        valid = np.asarray(ch["surface"])[..., 0] != 0
        ratio = change_score(locked, im, valid)
        stem = EVAL / p["id"]
        im.save(str(stem) + "_diorama.png")
        locked.save(str(stem) + "_locked.png")
        ch["rgb"].save(str(stem) + "_base.png")
        effect.save(str(stem) + "_effects.png")
        for key in ("object_id", "surface", "mask"):
            ch[key].save(str(stem) + "_" + key + ".png")
        for col, (source, label) in enumerate(((ch["rgb"], "BASE GEOMETRY"),
                                              (locked, "PREVIOUS LOCKED"), (im, "SEOUL DIORAMA"))):
            top = 70 + i * 560
            dr.text((col * 512 + 12, top), p["label"] + " / " + label, fill="#343e48", font=font(14))
            overview.paste(source.resize((512, 512), Image.Resampling.BOX), (col * 512, top + 32))
        # Determinism is verified on the actual renderer, not inferred from seeds.
        again, _, _ = render_region(cfg, ramps, tex, manifest, x, y, size)
        if im.tobytes() != again.tobytes():
            raise RuntimeError("Non-deterministic pilot: " + p["id"])
        entry = {"id": p["id"], "changed_fraction": ratio, "sha256": digest(str(stem) + "_diorama.png"),
                 "repeat_identical": True}
        report["pilots"].append(entry)
        print(p["id"], f"changed {ratio:.1%}", flush=True)
    overview.save(EVAL / "comparison.png")
    write(EVAL / "report.json", report)
    print(EVAL / "comparison.png")


def font(size):
    for p in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def approved():
    p = EVAL / "approval.json"
    if not p.exists():
        raise RuntimeError("Full map waits for user review of eval/diorama/comparison.png")
    approval = read(p)
    if approval.get("approved_by") != "user" or approval.get("signature") != signature():
        raise RuntimeError("Approval must match the current reviewed renderer and assets")
    report = read(EVAL / "report.json")
    if approval.get("report_sha256") != digest(EVAL / "report.json"):
        raise RuntimeError("Pilot report changed after approval")
    if not report.get("validation_passed"):
        raise RuntimeError("Pilot validation required")


def build():
    cfg, ramps, tex, manifest = setup()
    approved()
    dest = WORK / "tiles"
    dest.mkdir(parents=True, exist_ok=True)
    for t in manifest["tiles"]:
        im, _, _ = render_region(cfg, ramps, tex, manifest, t["x0"], t["y0"], manifest["grid"]["tile_size"])
        im.save(dest / (t["id"] + ".png"))
        print(t["id"], flush=True)
    write(WORK / "build.json", {"signature": signature()})


def assemble():
    approved()
    validate_full()
    m = read(DATA / "tile_manifest.json")
    if read(WORK / "build.json")["signature"] != signature():
        raise RuntimeError("Stale full-map build")
    g, grid = m["global_camera"], m["grid"]
    out = Image.new("RGB", (g["width"], g["height"]))
    ov, core = grid["overlap"], grid["core"]
    for t in m["tiles"]:
        im = Image.open(WORK / "tiles" / (t["id"] + ".png"))
        out.paste(im.crop((ov, ov, ov + core, ov + core)), (t["col"] * core, t["row"] * core))
    out.save(WORK / "mosaic.png")
    write(WORK / "assembled.json", {"signature": signature(), "sha256": digest(WORK / "mosaic.png")})
    out.thumbnail((2048, 2048), Image.Resampling.BOX)
    out.save(EVAL / "diorama_full_overview.png")


def pyramid():
    approved()
    completed = read(WORK / "assembled.json")
    if completed["signature"] != signature() or completed["sha256"] != digest(WORK / "mosaic.png"):
        raise RuntimeError("Stale or changed assembled map")
    public = read(P2 / "web/tiles/manifest.json")
    im = Image.open(WORK / "mosaic.png")
    if list(im.size) != [public["width"], public["height"]]:
        raise RuntimeError("Baseline/diorama map dimensions differ")
    root = P2 / "web/tiles/diorama"
    ts = public["tile_size"]
    for z in range(public["max_zoom"] + 1):
        f = 2 ** (public["max_zoom"] - z)
        size = tuple(math.ceil(n / f) for n in im.size)
        level = im.resize(size, Image.Resampling.BOX) if f > 1 else im
        for y in range(math.ceil(size[1] / ts)):
            for x in range(math.ceil(size[0] / ts)):
                p = root / str(z) / str(x) / f"{y}.png"
                p.parent.mkdir(parents=True, exist_ok=True)
                level.crop((x * ts, y * ts, min((x + 1) * ts, size[0]), min((y + 1) * ts, size[1]))).save(p)
    public.update(styles={"baseline": "tiles", "diorama": "tiles/diorama"}, default_style="diorama")
    write(P2 / "web/tiles/manifest.json", public)


def validate_full():
    if read(WORK / "build.json")["signature"] != signature():
        raise RuntimeError("Stale full-map build")
    m = read(DATA / "tile_manifest.json")
    tiles = {(t["row"], t["col"]): t for t in m["tiles"]}
    worst = 0.
    for (r, c), t in tiles.items():
        a = np.asarray(Image.open(WORK / "tiles" / (t["id"] + ".png")))
        for dr, dc in ((0, 1), (1, 0)):
            if (r + dr, c + dc) not in tiles:
                continue
            other = tiles[r + dr, c + dc]
            b = np.asarray(Image.open(WORK / "tiles" / (other["id"] + ".png")))
            aa, bb = (a[:, 768:], b[:, :256]) if dc else (a[768:], b[:256])
            worst = max(worst, float(np.any(aa != bb, axis=2).mean()))
    if worst > .005:
        raise RuntimeError(f"Full-map seam exceeds 0.5%: {worst:.4%}")
    print(f"{len(tiles)} full-map tiles verified; worst seam {worst:.4%}")


def validate():
    cfg, ramps, tex, m = setup()
    report = read(EVAL / "report.json")
    if report["signature"] != signature():
        raise RuntimeError("Stale pilot: regenerate after renderer/config changes")
    palette = np.concatenate(list(ramps.values()))
    for p, entry in zip(cfg["pilots"], report["pilots"]):
        stem = EVAL / p["id"]
        if digest(str(stem) + "_diorama.png") != entry["sha256"]:
            raise RuntimeError("Pilot image changed")
        if entry["changed_fraction"] < .6:
            raise RuntimeError("Insufficient visual change: " + p["id"])
        im = np.asarray(Image.open(str(stem) + "_diorama.png"))
        colors = np.unique(im.reshape(-1, 3), axis=0)
        assert all(np.any(np.all(palette == c, axis=1)) for c in colors)
        # Plain baseline Sheet never invokes any diorama drawing logic.
        city, layers, _ = conditions.load()
        plain = conditions.render(city, layers, region_camera(m, p["x"], p["y"], cfg["pilot_size"]))
        size = cfg["pilot_size"]
        ch = {k: im.crop((15, 15, size + 15, size + 15)) for k, im in plain.im.items()}
        for key in ("object_id", "surface", "mask"):
            assert Image.open(str(stem) + "_" + key + ".png").tobytes() == ch[key].tobytes()
        b = np.any(np.asarray(ch["object_id"]) != 0, axis=2)
        allowed = np.asarray(Image.fromarray(b).filter(ImageFilter.MaxFilter(25)))
        effect = np.asarray(Image.open(str(stem) + "_effects.png")) != 0
        # Objects just outside the crop may cast shadows into a 12px border.
        assert not np.any((effect & ~allowed)[12:-12, 12:-12])
    # Adjacent 1024px renders overlap by 256px, independently rendered context.
    worst = 0.
    for p in cfg["pilots"]:
        a, _, _ = render_region(cfg, ramps, tex, m, p["x"], p["y"], 1024)
        for dx, dy in ((768, 0), (0, 768)):
            b, _, _ = render_region(cfg, ramps, tex, m, p["x"] + dx, p["y"] + dy, 1024)
            aa, bb = np.asarray(a), np.asarray(b)
            left, right = (aa[:, 768:], bb[:, :256]) if dx else (aa[768:], bb[:256])
            worst = max(worst, float(np.any(left != right, axis=2).mean()))
    if worst > .005:
        raise RuntimeError(f"Overlap exceeds 0.5%: {worst:.4%}")
    report.update(validation_passed=True, worst_seam=worst, core_masks_unchanged=True,
                  extension_screen_px_max=12, palette_colors=48)
    write(EVAL / "report.json", report)
    print(f"Pilot validation passed, worst overlap {worst:.4%}; user visual review still pending")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("assets", "pilot", "validate", "build", "assemble", "pyramid"))
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if args.command == "build" and not args.all:
        parser.error("build requires --all; use pilot for initial review")
    if args.command == "validate" and args.all:
        approved()
        validate_full()
    else:
        globals()[args.command]()
