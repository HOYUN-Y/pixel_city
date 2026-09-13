"""전체 지도 조건 타일 생성, 추론, 조립, 웹 타일 변환.

모든 타일은 bbox별 fit이 아니라 하나의 전역 투영 평면을 공유한다.

  python tile_pipeline.py prepare --manifest-only
  python tile_pipeline.py prepare
  python tile_pipeline.py generate --limit 4
  python tile_pipeline.py seams
  python tile_pipeline.py assemble
  python tile_pipeline.py pyramid
"""
import argparse
import hashlib
import json
import math
import os
import sys
import time

from PIL import Image

P2 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(P2)
sys.path.insert(0, os.path.join(P2, "scripts"))
import geometry as iso2  # noqa: E402
import conditions  # noqa: E402
from s1_edit import cached_revision, check_prompt_lengths  # noqa: E402

DEFAULT_CONFIG = os.path.join(P2, "configs", "pipeline.json")
DEFAULT_WORK = os.path.join(P2, "work", "fullmap")
DATA_FILES = [os.path.join(iso2.DATA, n) for n in
              ("city.json", "layers.json", "meta.json", "poi.json")]


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def global_camera(cfg, meta):
    bbox, scale = cfg["bbox"], cfg["scale"]
    o = meta["origin"]
    to_en = lambda lon, lat: ((lon - o["lon0"]) * o["mlon"],
                              (lat - o["lat0"]) * o["mlat"])
    frame = [to_en(*p) for p in ((bbox[0], bbox[1]), (bbox[2], bbox[1]),
                                  (bbox[2], bbox[3]), (bbox[0], bbox[3]))]
    pts = [iso2.proj(e, n, h, 1.0) for e, n in frame for h in (0.0, conditions.HMAX)]
    us, vs = [p[0] for p in pts], [p[1] for p in pts]
    pad = conditions.PAD
    width = math.ceil((max(us) - min(us)) / scale) + 2 * pad
    height = math.ceil((max(vs) - min(vs)) / scale) + 2 * pad
    return {"scale": scale, "width": width, "height": height,
            "cx": pad - min(us) / scale, "cy": pad - min(vs) / scale,
            "alpha_deg": iso2.STYLE["alpha_deg"], "phi_deg": iso2.STYLE["phi_deg"],
            "bbox": bbox, "origin": o, "hmax": conditions.HMAX, "frame_en": frame}


def build_manifest(cfg):
    _, _, meta = conditions.load()
    g = global_camera(cfg, meta)
    size, overlap = cfg["tile_size"], cfg["overlap"]
    core = size - overlap * 2
    if size % 8 or core <= 0:
        raise ValueError("tile_size는 8의 배수이고 overlap*2보다 커야 한다")
    cols, rows = math.ceil(g["width"] / core), math.ceil(g["height"] / core)
    tiles = []
    for row in range(rows):
        for col in range(cols):
            x0, y0 = col * core - overlap, row * core - overlap
            name = f"r{row:02d}_c{col:02d}"
            tiles.append({"id": name, "row": row, "col": col,
                          "x0": x0, "y0": y0,
                          "seed": cfg["base_seed"] + row * cols + col,
                          "condition_dir": f"conditions/{name}",
                          "output": f"generated/{name}.png", "status": "pending"})
    clean_g = {k: v for k, v in g.items() if k != "frame_en"}
    return {"version": 1, "config": cfg, "input_sha256": {os.path.basename(p): sha256(p) for p in DATA_FILES},
            "global_camera": clean_g, "grid": {"rows": rows, "cols": cols,
            "tile_size": size, "overlap": overlap, "core": core}, "tiles": tiles}


def verify_inputs(manifest):
    now = {os.path.basename(p): sha256(p) for p in DATA_FILES}
    if now != manifest["input_sha256"]:
        raise RuntimeError("prototype1 입력 데이터 해시가 바뀌었다. 새 manifest를 만든다")


def prepare(cfg, work, manifest_only=False):
    manifest = build_manifest(cfg)
    manifest_path = os.path.join(work, "tile_manifest.json")
    if os.path.exists(manifest_path):
        old = read_json(manifest_path)
        if old.get("config") == cfg and old.get("input_sha256") == manifest["input_sha256"]:
            previous = {t["id"]: t for t in old.get("tiles", [])}
            for tile in manifest["tiles"]:
                if tile["id"] in previous:
                    tile.update({k: v for k, v in previous[tile["id"]].items()
                                 if k not in ("row", "col", "x0", "y0", "seed",
                                              "condition_dir", "output")})
    write_json(manifest_path, manifest)
    if manifest_only:
        return manifest
    city, layers, meta = conditions.load()
    base = global_camera(cfg, meta)
    for i, tile in enumerate(manifest["tiles"], 1):
        cam = {**base, "size": cfg["tile_size"],
               "cx": base["cx"] - tile["x0"], "cy": base["cy"] - tile["y0"]}
        out = os.path.join(work, tile["condition_dir"])
        paths = conditions.render(city, layers, cam).save(out)
        cam_out = {k: v for k, v in cam.items() if k != "frame_en"}
        write_json(os.path.join(out, "source", "camera.json"), cam_out)
        sizes = {Image.open(p).size for p in paths.values()}
        if sizes != {(cfg["tile_size"], cfg["tile_size"])}:
            raise RuntimeError(f"{tile['id']} 조건 크기 불일치: {sizes}")
        print(f"[{i}/{len(manifest['tiles'])}] {tile['id']}")
    return manifest


def generate(manifest_path, limit, allow_cpu=False, selected=()):
    import torch
    from diffusers import StableDiffusionXLControlNetPipeline, ControlNetModel

    manifest = read_json(manifest_path)
    verify_inputs(manifest)
    known = {t["id"] for t in manifest["tiles"]}
    unknown = set(selected) - known
    if unknown:
        raise ValueError(f"manifest에 없는 타일: {', '.join(sorted(unknown))}")
    cfg, work = manifest["config"], os.path.dirname(manifest_path)
    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    if device == "cpu" and not allow_cpu:
        raise RuntimeError("GPU/MPS를 찾지 못했다. 확인용이면 --allow-cpu를 명시한다")
    dtype = torch.float16 if device in ("mps", "cuda") else torch.float32
    cn = ControlNetModel.from_pretrained(cfg["controlnet"], torch_dtype=dtype)
    pipe = StableDiffusionXLControlNetPipeline.from_pretrained(
        cfg["model"], controlnet=cn, torch_dtype=dtype, variant="fp16" if dtype == torch.float16 else None).to(device)
    pipe.set_progress_bar_config(disable=True)
    check_prompt_lengths(pipe, cfg)
    done = 0
    for tile in manifest["tiles"]:
        if selected and tile["id"] not in selected:
            continue
        out = os.path.join(work, tile["output"])
        if tile["status"] == "complete" and os.path.exists(out):
            continue
        if done >= limit:
            break
        edge = Image.open(os.path.join(work, tile["condition_dir"], "conditions", "edge.png")).convert("RGB")
        started = time.time()
        image = pipe(prompt=cfg["prompt"], negative_prompt=cfg["negative"], image=edge,
                     controlnet_conditioning_scale=cfg["control_scale"],
                     num_inference_steps=cfg["steps"], guidance_scale=cfg["guidance"],
                     generator=torch.Generator(device).manual_seed(tile["seed"])).images[0]
        os.makedirs(os.path.dirname(out), exist_ok=True)
        image.save(out)
        tile.update(status="complete", seconds=round(time.time() - started, 1), device=device,
                    model_revision=cached_revision(cfg["model"]),
                    controlnet_revision=cached_revision(cfg["controlnet"]))
        write_json(manifest_path, manifest)
        done += 1
        print(f"[{done}/{limit}] {tile['id']} {tile['seconds']}s")


def seam_report(manifest_path):
    import numpy as np
    manifest = read_json(manifest_path)
    work, grid = os.path.dirname(manifest_path), manifest["grid"]
    by_rc = {(t["row"], t["col"]): t for t in manifest["tiles"]}
    size, core = grid["tile_size"], grid["core"]
    rows = []
    for (r, c), a in by_rc.items():
        pa = os.path.join(work, a["output"])
        if not os.path.exists(pa):
            continue
        ia = np.asarray(Image.open(pa).convert("RGB"), dtype=np.float32)
        for dr, dc, axis in ((0, 1, "vertical"), (1, 0, "horizontal")):
            b = by_rc.get((r + dr, c + dc))
            if not b:
                continue
            pb = os.path.join(work, b["output"])
            if not os.path.exists(pb):
                continue
            ib = np.asarray(Image.open(pb).convert("RGB"), dtype=np.float32)
            if axis == "vertical":
                x = size - core
                aa, bb = ia[:, core:], ib[:, :x]
            else:
                y = size - core
                aa, bb = ia[core:, :], ib[:y, :]
            rows.append({"a": a["id"], "b": b["id"], "axis": axis,
                         "mean_abs_rgb": round(float(np.abs(aa - bb).mean()), 3)})
    report = {"pairs": rows, "mean": round(sum(x["mean_abs_rgb"] for x in rows) / len(rows), 3) if rows else None}
    write_json(os.path.join(work, "seams.json"), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def validate_conditions(manifest_path):
    """인접 조건 타일의 같은 전역 영역이 래스터 반올림 허용범위 안에서 일치하는지 본다."""
    import numpy as np
    manifest = read_json(manifest_path)
    verify_inputs(manifest)
    work, grid = os.path.dirname(manifest_path), manifest["grid"]
    by_rc = {(t["row"], t["col"]): t for t in manifest["tiles"]}
    size, core = grid["tile_size"], grid["core"]
    shared = size - core
    worst = 0.0
    for (r, c), a in by_rc.items():
        for dr, dc, axis in ((0, 1, "vertical"), (1, 0, "horizontal")):
            b = by_rc.get((r + dr, c + dc))
            if not b:
                continue
            for name in ("edge.png", "height.png", "mask.png", "surface.png", "object_id.png"):
                pa = os.path.join(work, a["condition_dir"], "conditions", name)
                pb = os.path.join(work, b["condition_dir"], "conditions", name)
                if not os.path.exists(pa) or not os.path.exists(pb):
                    raise RuntimeError("조건 타일이 없다. prepare를 먼저 실행한다")
                ia, ib = np.asarray(Image.open(pa)), np.asarray(Image.open(pb))
                aa, bb = ((ia[:, core:], ib[:, :shared]) if axis == "vertical"
                          else (ia[core:, :], ib[:shared, :]))
                ratio = float(np.any(aa != bb, axis=2).mean())
                worst = max(worst, ratio)
                # PIL의 폴리곤/선 raster rounding 때문에 정수 이동이어도 경계 1px 일부가 다를 수 있다.
                if ratio > 0.005:
                    raise RuntimeError(f"조건 overlap 불일치 {a['id']} {b['id']} {name}: {ratio:.4%}")
    print(f"condition overlap ok — worst mismatch {worst:.4%}")


def assemble(manifest_path):
    manifest = read_json(manifest_path)
    work, g, grid = os.path.dirname(manifest_path), manifest["global_camera"], manifest["grid"]
    canvas = Image.new("RGB", (g["width"], g["height"]), (26, 30, 38))
    ov, core = grid["overlap"], grid["core"]
    for tile in manifest["tiles"]:
        p = os.path.join(work, tile["output"])
        if not os.path.exists(p):
            raise RuntimeError(f"생성 타일 누락: {tile['id']}")
        im = Image.open(p).convert("RGB").crop((ov, ov, ov + core, ov + core))
        canvas.paste(im, (tile["col"] * core, tile["row"] * core))
    colors = manifest["config"]["palette_colors"]
    canvas = canvas.quantize(colors=colors, method=Image.Quantize.MEDIANCUT).convert("RGB")
    out = os.path.join(work, "mosaic.png")
    canvas.save(out)
    print(out)
    return out


def export_web_data(manifest, dest):
    poi = read_json(os.path.join(iso2.DATA, "poi.json"))
    g, q = manifest["global_camera"], 10.0
    alpha, phi = math.radians(g["alpha_deg"]), math.radians(g["phi_deg"])
    def xy(e10, n10):
        e, n = e10 / q, n10 / q
        u = e * math.cos(alpha) - n * math.sin(alpha)
        v = -((e * math.sin(alpha) + n * math.cos(alpha)) * math.sin(phi))
        return [round(u / g["scale"] + g["cx"], 2), round(v / g["scale"] + g["cy"], 2)]
    out = {k: [{**p, "xy": xy(p["x"], p["y"])} for p in poi.get(k, [])]
           for k in ("museum", "market", "tourinfo")}
    out["subway"] = {"stations": [{**p, "xy": xy(p["x"], p["y"])} for p in poi["subway"]["stations"]],
                     "lines": {k: [xy(*p) for p in pts] for k, pts in poi["subway"]["lines"].items()}}
    write_json(os.path.join(dest, "data", "generated", "poi.json"), out)


def pyramid(manifest_path):
    manifest = read_json(manifest_path)
    work, cfg = os.path.dirname(manifest_path), manifest["config"]
    src = Image.open(os.path.join(work, "mosaic.png")).convert("RGB")
    tile_size = cfg["web_tile_size"]
    max_zoom = math.ceil(math.log2(max(src.size) / tile_size))
    dest = os.path.join(P2, "web", "tiles")
    for z in range(max_zoom + 1):
        factor = 2 ** (max_zoom - z)
        size = (math.ceil(src.width / factor), math.ceil(src.height / factor))
        level = src if factor == 1 else src.resize(size, Image.Resampling.BOX)
        for y in range(math.ceil(level.height / tile_size)):
            for x in range(math.ceil(level.width / tile_size)):
                p = os.path.join(dest, str(z), str(x), f"{y}.png")
                os.makedirs(os.path.dirname(p), exist_ok=True)
                level.crop((x * tile_size, y * tile_size,
                            min((x + 1) * tile_size, level.width),
                            min((y + 1) * tile_size, level.height))).save(p)
    public = {"width": src.width, "height": src.height, "tile_size": tile_size,
              "max_zoom": max_zoom, "bbox": cfg["bbox"]}
    write_json(os.path.join(dest, "manifest.json"), public)
    export_web_data(manifest, os.path.join(P2, "web"))
    print(f"web pyramid z0..{max_zoom}: {dest}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("prepare", "validate", "generate", "seams", "assemble", "pyramid"))
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--work", default=DEFAULT_WORK)
    ap.add_argument("--manifest-only", action="store_true")
    ap.add_argument("--limit", type=int, default=10**9)
    ap.add_argument("--tiles", help="쉼표로 지정. 생략하면 모든 pending 타일")
    ap.add_argument("--allow-cpu", action="store_true")
    a = ap.parse_args()
    cfg, manifest = read_json(a.config), os.path.join(a.work, "tile_manifest.json")
    if a.command == "prepare": prepare(cfg, a.work, a.manifest_only)
    elif a.command == "validate": validate_conditions(manifest)
    elif a.command == "generate":
        selected = tuple(x for x in (a.tiles or "").split(",") if x)
        generate(manifest, a.limit, a.allow_cpu, selected)
    elif a.command == "seams": seam_report(manifest)
    elif a.command == "assemble": assemble(manifest)
    else: pyramid(manifest)


if __name__ == "__main__":
    main()
