"""AI 재질을 구조 조건 안에서만 합성하는 완전 로컬 지도 렌더러."""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

P2 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(P2, "scripts"))
import conditions  # noqa: E402
import tile_pipeline  # noqa: E402
from overlay import metrics  # noqa: E402

WORK = os.path.join(P2, "work", "fullmap")
STYLE = os.path.join(P2, "work", "style_bank", "style_manifest.json")

ALPHA = {"roof": 0.16, "wall": 0.10, "road": 0.04, "ground": 0.02, "vegetation": 0.04}


def read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def texture_bank(style_path):
    manifest = read(style_path)
    root = os.path.dirname(style_path)
    missing = [k for k, v in manifest["selected"].items() if not v]
    if missing:
        raise RuntimeError("선택된 AI 재질이 없다: " + ", ".join(missing))
    return manifest, {k: np.asarray(Image.open(os.path.join(root, v)).convert("RGB"))
                      for k, v in manifest["selected"].items()}


def tiled(tex, width, height, x0, y0):
    ys = np.mod(np.arange(y0, y0 + height), tex.shape[0])
    xs = np.mod(np.arange(x0, x0 + width), tex.shape[1])
    return tex[ys[:, None], xs[None, :]]


def same(rgb, value):
    return np.all(rgb == np.asarray(value, dtype=np.uint8), axis=2)


def apply_material(out, tex, choose, alpha, x0, y0):
    if not choose.any():
        return
    layer = tiled(tex, out.shape[1], out.shape[0], x0, y0).astype(np.float32)
    # 재질의 색 자체가 아니라 평균에서 벗어난 질감만 섞어 원래 클래스 팔레트를 보존한다.
    high = np.clip(layer - layer.reshape(-1, 3).mean(axis=0), -80, 80)
    mixed = out.astype(np.float32) + high * alpha
    out[choose] = np.clip(mixed[choose], 0, 255).astype(np.uint8)


def build_palette(textures, base, colors):
    thumbs = [Image.fromarray(v).resize((64, 64), Image.Resampling.BOX) for v in textures.values()]
    thumbs.append(base.resize((64, 64), Image.Resampling.BOX))
    strip = Image.new("RGB", (64 * len(thumbs), 64))
    for i, im in enumerate(thumbs):
        strip.paste(im, (i * 64, 0))
    return strip.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)


def style_tile(condition_dir, textures, palette, x0, y0):
    src = os.path.join(condition_dir, "source", "base_rgb.png")
    cond = os.path.join(condition_dir, "conditions")
    base_im = Image.open(src).convert("RGB")
    out = np.asarray(base_im).copy()
    cls = np.asarray(Image.open(os.path.join(cond, "mask.png")).convert("RGB"))
    surface = np.asarray(Image.open(os.path.join(cond, "surface.png")).convert("L"))
    edge = np.asarray(Image.open(os.path.join(cond, "edge.png")).convert("L"))
    object_id = np.asarray(Image.open(os.path.join(cond, "object_id.png")).convert("RGB"))

    roof = surface == conditions.SURFACE["roof"]
    wall = ((surface == conditions.SURFACE["wall_lit"]) |
            (surface == conditions.SURFACE["wall_dark"]))
    class_roofs = (
        ("palace_roof", conditions.MASK["palace"]),
        ("hanok_roof", conditions.MASK["hanok"]),
        ("commercial_roof", conditions.MASK["상업용"]),
        ("residential_roof", conditions.MASK["주거용"]),
        ("civic_roof", conditions.MASK["문교사회용"]),
        ("civic_roof", conditions.MASK["공공용"]),
    )
    claimed = np.zeros(roof.shape, dtype=bool)
    for key, color in class_roofs:
        choose = roof & same(cls, color)
        apply_material(out, textures[key], choose, ALPHA["roof"], x0, y0)
        claimed |= choose
    apply_material(out, textures["commercial_roof"], roof & ~claimed, ALPHA["roof"], x0, y0)
    apply_material(out, textures["wall"], wall, ALPHA["wall"], x0, y0)
    apply_material(out, textures["road"], surface == conditions.SURFACE["road"], ALPHA["road"], x0, y0)
    apply_material(out, textures["ground"], surface == conditions.SURFACE["ground"], ALPHA["ground"], x0, y0)
    green = ((surface == conditions.SURFACE["park"]) | (surface == conditions.SURFACE["heri"]))
    apply_material(out, textures["vegetation"], green, ALPHA["vegetation"], x0, y0)

    # 생성 재질보다 구조선이 항상 우선한다.
    building = np.any(object_id != 0, axis=2)
    out[(edge >= 128) & building] = (38, 43, 52)
    styled = Image.fromarray(out).quantize(palette=palette, dither=Image.Dither.NONE).convert("RGB")
    return base_im, styled


def building_metrics(condition_dir, styled):
    """지면 질감은 제외하고 object ID가 있는 건물 구조 안에서만 경계를 평가한다."""
    cond = os.path.join(condition_dir, "conditions")
    oid = np.asarray(Image.open(os.path.join(cond, "object_id.png")).convert("RGB"))
    mask = Image.fromarray((np.any(oid != 0, axis=2) * 255).astype(np.uint8))
    black = Image.new("RGB", styled.size, (0, 0, 0))
    result = Image.composite(styled.convert("RGB"), black, mask)
    source = Image.composite(Image.open(os.path.join(cond, "edge.png")).convert("RGB"), black, mask)
    return metrics(source, result)


def build(work, style_path, selected, build_all=False):
    manifest = read(os.path.join(work, "tile_manifest.json"))
    tile_pipeline.verify_inputs(manifest)
    _, textures = texture_bank(style_path)
    first = manifest["tiles"][0]
    base0 = Image.open(os.path.join(work, first["condition_dir"], "source", "base_rgb.png")).convert("RGB")
    palette = build_palette(textures, base0, manifest["config"]["palette_colors"])
    palette_path = os.path.join(work, "locked", "palette.png")
    os.makedirs(os.path.dirname(palette_path), exist_ok=True)
    palette.save(palette_path)
    ids = {t["id"] for t in manifest["tiles"]} if build_all else set(selected or manifest["config"]["pilot_tiles"])
    for tile in manifest["tiles"]:
        if tile["id"] not in ids:
            continue
        base, styled = style_tile(os.path.join(work, tile["condition_dir"]), textures, palette,
                                  tile["x0"], tile["y0"])
        out = os.path.join(work, "locked", "tiles", tile["id"] + ".png")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        styled.save(out)
        score = building_metrics(os.path.join(work, tile["condition_dir"]), styled)
        print(tile["id"], "F1", f"{score['f1']:.3f}", "density", f"{score['edge_density_ratio']:.2f}")


def preview(work):
    manifest = read(os.path.join(work, "tile_manifest.json"))
    ids = manifest["config"]["pilot_tiles"]
    by_id = {t["id"]: t for t in manifest["tiles"]}
    ov, core = manifest["grid"]["overlap"], manifest["grid"]["core"]
    coords = [by_id[i] for i in ids]
    r0, c0 = min(t["row"] for t in coords), min(t["col"] for t in coords)
    out = Image.new("RGB", (core * 2, core * 2), (26, 30, 38))
    for tile in coords:
        p = os.path.join(work, "locked", "tiles", tile["id"] + ".png")
        if not os.path.exists(p):
            raise RuntimeError("pilot 타일이 없다. build를 먼저 실행한다")
        im = Image.open(p).crop((ov, ov, ov + core, ov + core))
        out.paste(im, ((tile["col"] - c0) * core, (tile["row"] - r0) * core))
    path = os.path.join(work, "locked", "preview_2x2.png")
    out.save(path)
    evidence = os.path.join(P2, "eval", "locked_preview_2x2.png")
    os.makedirs(os.path.dirname(evidence), exist_ok=True)
    out.save(evidence)
    print(path)
    print(evidence)


def assemble(work):
    manifest = read(os.path.join(work, "tile_manifest.json"))
    g, grid = manifest["global_camera"], manifest["grid"]
    out = Image.new("RGB", (g["width"], g["height"]), (26, 30, 38))
    ov, core = grid["overlap"], grid["core"]
    for tile in manifest["tiles"]:
        p = os.path.join(work, "locked", "tiles", tile["id"] + ".png")
        if not os.path.exists(p):
            raise RuntimeError("locked 타일 누락: " + tile["id"])
        im = Image.open(p).crop((ov, ov, ov + core, ov + core))
        out.paste(im, (tile["col"] * core, tile["row"] * core))
    path = os.path.join(work, "mosaic.png")
    out.save(path)
    overview = out.copy()
    overview.thumbnail((2048, 2048), Image.Resampling.BOX)
    evidence = os.path.join(P2, "eval", "locked_full_overview.png")
    overview.save(evidence)
    print(path)
    print(evidence)


def validate(work, require_all=False):
    manifest = read(os.path.join(work, "tile_manifest.json"))
    ids = {t["id"] for t in manifest["tiles"]} if require_all else set(manifest["config"]["pilot_tiles"])
    missing, worst_f1 = [], 1.0
    source_edges = result_edges = 0
    for tile in manifest["tiles"]:
        if tile["id"] not in ids:
            continue
        out = os.path.join(work, "locked", "tiles", tile["id"] + ".png")
        if not os.path.exists(out):
            missing.append(tile["id"]); continue
        score = building_metrics(os.path.join(work, tile["condition_dir"]), Image.open(out))
        source_edges += score["source_edge_pixels"]
        result_edges += score["result_edge_pixels"]
        if score["source_edge_pixels"] >= 1000:
            worst_f1 = min(worst_f1, score["f1"])
    if missing:
        raise RuntimeError("styled 타일 누락: " + ", ".join(missing))
    density = result_edges / source_edges if source_edges else 0.0
    if density > 5.0:
        raise RuntimeError(f"전체 edge density 초과: {density:.2f}")
    # 같은 전역 overlap은 재질까지 동일해야 한다. 래스터 경계 반올림만 0.5% 허용한다.
    by_rc = {(t["row"], t["col"]): t for t in manifest["tiles"] if t["id"] in ids}
    size, core = manifest["grid"]["tile_size"], manifest["grid"]["core"]
    shared, worst_seam = size - core, 0.0
    for (r, c), a in by_rc.items():
        for dr, dc, axis in ((0, 1, "vertical"), (1, 0, "horizontal")):
            b = by_rc.get((r + dr, c + dc))
            if not b:
                continue
            ia = np.asarray(Image.open(os.path.join(work, "locked", "tiles", a["id"] + ".png")))
            ib = np.asarray(Image.open(os.path.join(work, "locked", "tiles", b["id"] + ".png")))
            aa, bb = ((ia[:, core:], ib[:, :shared]) if axis == "vertical"
                      else (ia[core:, :], ib[:shared, :]))
            mismatch = float(np.any(aa != bb, axis=2).mean())
            worst_seam = max(worst_seam, mismatch)
    if worst_seam > 0.005:
        raise RuntimeError(f"locked overlap 불일치 초과: {worst_seam:.4%}")
    print(f"locked validation ok — min F1 {worst_f1:.3f}, total density {density:.2f}, "
          f"worst seam {worst_seam:.4%}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("build", "preview", "validate", "assemble", "pyramid"))
    ap.add_argument("--work", default=WORK)
    ap.add_argument("--style", default=STYLE)
    ap.add_argument("--tiles", help="쉼표로 지정")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    chosen = tuple(x for x in (a.tiles or "").split(",") if x)
    if a.command == "build": build(a.work, a.style, chosen, a.all)
    elif a.command == "preview": preview(a.work)
    elif a.command == "validate": validate(a.work, a.all)
    elif a.command == "assemble": assemble(a.work)
    else: tile_pipeline.pyramid(os.path.join(a.work, "tile_manifest.json"))
