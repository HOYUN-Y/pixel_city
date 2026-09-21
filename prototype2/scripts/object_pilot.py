"""Bounded OpenRouter asset experiment + fixed-camera, per-object depth export.

Only `generate --allow-external` makes paid calls. prepare/build are offline.
Original images remain outside Git; the small reviewable demo is self-contained.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import html
import io
import json
import math
import os
from pathlib import Path
import shutil
import time

import numpy as np
from PIL import Image, ImageDraw

import geometry as geo
import openrouter_style as api

P2 = Path(__file__).resolve().parents[1]
CONFIG = P2 / "configs/object_pilot.json"
PREPARED = P2 / "work/object_pilot/prepared"
RUNS = P2 / "eval/object_pilot/runs"
PUBLIC = P2 / "assets/object_pilot"
DEPTH_OFFSET, DEPTH_SCALE = 10000, 100


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inputs():
    cfg = read(CONFIG)
    snapshot = read(geo.DATA / "snapshot.json")
    for name, digest in snapshot["files"].items():
        if sha(geo.DATA / name) != digest:
            raise ValueError("Frozen snapshot changed: " + name)
    return cfg, read(geo.DATA / "city.json"), read(geo.DATA / "layers.json"), read(geo.DATA / "meta.json")


def faces(city, building_id):
    i = building_id - 1
    ring = geo.dec_ring(city["rings"][i])
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    height = city["h"][i] / 10
    wood = bool(city["kind"][i])
    palette = ((87, 106, 131), (164, 111, 80), (111, 75, 58)) if wood else (
        (151, 167, 177), (203, 187, 153), (141, 137, 128))
    result = []

    def walls(points, low, high, roof_wall=False):
        for p, q in zip(points, points[1:]):
            if p == q:
                continue
            nx, ny = q[1] - p[1], p[0] - q[0]
            lit = abs(nx) / max(math.hypot(nx, ny), 1e-9) > .5
            color = palette[0] if roof_wall else palette[1 if lit else 2]
            result.append({"points": [(*p, low), (*q, low), (*q, high), (*p, high)],
                           "color": color, "surface": 1 if roof_wall else (2 if lit else 3)})

    roof = ring
    if wood:
        walls(ring, 0, height * .5)
        roof = geo.expand(ring, geo.STYLE["eave"])
        walls(roof, height * .5, height, True)
    else:
        walls(ring, 0, height)
    result.append({"points": [(*p, height) for p in roof], "color": palette[0], "surface": 1})
    return result


def fit(all_faces, size, pad):
    points = [geo.proj(*p, 1) for f in all_faces for p in f["points"]]
    a = np.asarray(points)
    lo, hi = a.min(0), a.max(0)
    scale = float(max(hi - lo) / (size - pad * 2))
    return {"size": size, "scale": scale, "cx": float(size / 2 - (hi[0] + lo[0]) / 2 / scale),
            "cy": float(size / 2 - (hi[1] + lo[1]) / 2 / scale),
            "alpha_deg": geo.STYLE["alpha_deg"], "phi_deg": geo.STYLE["phi_deg"]}


def project(p, cam):
    u, v = geo.proj(*p, cam["scale"])
    return u + cam["cx"], v + cam["cy"]


def depth(p):
    e, n, h = p
    return -(e * math.sin(geo.ALPHA) + n * math.cos(geo.ALPHA)) * math.cos(geo.PHI) + h * math.sin(geo.PHI)


def raster(all_faces, cam, paint=None):
    """Screen-space plane interpolation; nearer depth wins, including concave roofs.

    This is camera depth in meters, NOT normalized roof height or centroid Y.
    Polygon coverage is rasterized by Pillow; each planar face has affine depth.
    """
    size = cam["size"]
    color = np.zeros((size, size, 4), dtype=np.uint8)
    zbuffer = np.full((size, size), -np.inf, dtype=np.float32)
    surface = np.zeros((size, size), dtype=np.uint8)
    for face in all_faces:
        points = np.asarray([project(p, cam) for p in face["points"]])
        matrix = np.column_stack((points, np.ones(len(points))))
        coef, _, rank, _ = np.linalg.lstsq(matrix, [depth(p) for p in face["points"]], rcond=None)
        if rank < 3:
            continue
        lo = np.maximum(0, np.floor(points.min(0)).astype(int))
        hi = np.minimum(size, np.ceil(points.max(0)).astype(int) + 1)
        x0, y0 = lo
        x1, y1 = hi
        if x1 <= x0 or y1 <= y0:
            continue
        mask = Image.new("L", (x1 - x0, y1 - y0))
        ImageDraw.Draw(mask).polygon([tuple(p - lo) for p in points], fill=255)
        yy, xx = np.indices((y1 - y0, x1 - x0))
        values = coef[0] * (xx + x0 + .5) + coef[1] * (yy + y0 + .5) + coef[2]
        target = zbuffer[y0:y1, x0:x1]
        take = (np.asarray(mask) > 0) & (values > target)
        target[take] = values[take]
        if paint is None:
            color[y0:y1, x0:x1][take] = (*face["color"], 255)
        else:
            # Appearance only: coverage, face ordering and depth stay authoritative.
            rgb = paint(face, cam, xx + x0 + .5, yy + y0 + .5)
            color[y0:y1, x0:x1, :3][take] = rgb[take]
            color[y0:y1, x0:x1, 3][take] = 255
        surface[y0:y1, x0:x1][take] = face["surface"]
    return Image.fromarray(color), zbuffer, surface


def encode_depth(values):
    codes = np.where(np.isfinite(values), np.rint((values + DEPTH_OFFSET) * DEPTH_SCALE), 0).astype(np.uint32)
    return Image.fromarray(np.stack(((codes >> 16) & 255, (codes >> 8) & 255, codes & 255), -1).astype(np.uint8))


def prepare():
    cfg, city, _, _ = inputs()
    PREPARED.mkdir(parents=True, exist_ok=True)
    records = []
    for oid in cfg["ai_building_ids"]:
        shape = faces(city, oid)
        cam = fit(shape, 1024, 128)
        picture, _, _ = raster(shape, cam)
        picture.save(PREPARED / f"building_{oid}_input.png")
        records.append({"id": oid, "camera": cam, "input": f"building_{oid}_input.png",
                        "sha256": sha(PREPARED / f"building_{oid}_input.png")})
    result = {"config_sha256": sha(CONFIG), "snapshot_sha256": sha(geo.DATA / "snapshot.json"), "buildings": records}
    write(PREPARED / "manifest.json", result)
    return result


ART = ("Hand-crafted pixel-art city game asset, crisp deliberate pixel clusters, rich but controlled natural colors, "
       "warm sunlit highlights, cool shadows, readable small-scale details. Use the reference only for art style; "
       "never copy its buildings, characters, farm layout or objects. No text, logos, labels, collage or extra objects. ")


def prompt(kind, oid=None):
    if kind == "building":
        subject = {4628: "a low Korean timber building with blue-gray tiled roofing and warm wooden window frames",
                   4577: "a compact mid-rise city building with warm masonry, clearly organized window bays and an entrance",
                   4485: "a tall contemporary city building with cool glass window clusters and differentiated facade bays"}[oid]
        return ("Use case: style-transfer. Asset type: isolated fixed-camera building sprite. "
                "Image 1 is the EDIT TARGET and exact geometry/placement reference. Image 2 is ONLY the art-style reference. "
                "Restyle the building as " + subject + ". " + ART +
                "Keep the exact silhouette, footprint, roof-wall boundaries, height proportions, screen position, camera, "
                "scale and padding from Image 1. Paint only inside the existing building. Do not recenter, rotate, straighten "
                "or simplify its outline. No ground plane, cast shadow, vegetation or surrounding scene. "
                "Use a genuinely transparent background. Keep doors and windows distinguishable for later lighting effects.")
    subject = {"asphalt": "dark muted blue-gray city asphalt, fine sparse aggregate, no lane markings",
               "sidewalk": "warm cream and ochre sidewalk paving blocks with clearly arranged small joints",
               "courtyard": "warm golden stone courtyard paving with gently irregular rectangular blocks"}[kind]
    return ("Use case: stylized-concept. Asset type: seamless tileable pixel game ground texture. "
            "Image 1 is ONLY an art-style reference. Generate " + subject + ". " + ART +
            "Flat top-down orthographic material swatch filling the entire square edge to edge. "
            "Match opposite edges for seamless repetition. Consistent texel scale and even lighting. "
            "No perspective, borders, gradients, dominant focal objects, plants, shadows, cracks crossing the whole tile or road layout.")


def decode_asset(result, transparent):
    entries = result.get("data", [])
    if len(entries) != 1:
        raise ValueError("Expected exactly one image")
    blob = base64.b64decode(entries[0]["b64_json"], validate=True)
    im = Image.open(io.BytesIO(blob))
    if im.width != im.height or not 512 <= im.width <= 4096:
        raise ValueError("Unsupported image dimensions")
    im.load()
    rgba = im.convert("RGBA")
    alpha = np.asarray(rgba)[..., 3]
    if transparent and not (np.any(alpha == 0) and np.any(alpha > 127)):
        raise ValueError("True transparent building output required")
    if np.asarray(rgba)[..., :3].std() < 1:
        raise ValueError("Uniform output")
    return rgba


def generate(allow_external=False):
    if not allow_external:
        raise ValueError("Paid generation requires --allow-external")
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise ValueError("OPENROUTER_API_KEY is not set")
    cfg, _, _, _ = inputs()
    style = P2 / cfg["style_reference"]
    if sha(style) != cfg["style_sha256"]:
        raise ValueError("Style reference changed")
    if cfg["max_requests"] != 6 or cfg["ai_building_ids"] != [4628, 4577, 4485] or cfg["materials"] != ["asphalt", "sidewalk", "courtyard"]:
        raise ValueError("Approved six-asset request scope changed")
    capability = api.validate_capabilities(api.request_json(f"/images/models/{api.MODEL}/endpoints", key))
    if not {"transparent", "opaque"} <= set(capability["supported_parameters"].get("background", {}).get("values", [])):
        raise ValueError("Required backgrounds unsupported; no fallback")
    prepared = prepare()
    folder = RUNS / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder.mkdir(parents=True, exist_ok=False)
    shutil.copytree(PREPARED, folder / "inputs")
    shutil.copyfile(style, folder / "style_input.png")
    jobs = [("building", oid) for oid in cfg["ai_building_ids"]] + [(name, None) for name in cfg["materials"]]
    report = {"run_id": folder.name, "status": "requesting", "model": api.MODEL, "capability": capability,
              "prepared": prepared, "style_sha256": sha(style), "requests_started": 0, "assets": [],
              "total_cost_usd": 0, "visual_review": "not_reviewed", "geometry_review": "not_reviewed"}
    write(folder / "report.json", report)
    print("OUTPUT=" + str(folder), flush=True)
    try:
        for kind, oid in jobs:
            name = f"building_{oid}" if oid else kind
            references = [api.reference(Image.open(style))]
            if oid:
                references.insert(0, api.reference(Image.open(folder / "inputs" / f"{name}_input.png")))
            payload = {"model": api.MODEL, "prompt": prompt(kind, oid), "n": 1, "quality": "high", "aspect_ratio": "1:1",
                       "background": "transparent" if oid else "opaque",
                       "provider": {"only": ["openai"], "allow_fallbacks": False}, "input_references": references}
            item = {"name": name, "building_id": oid, "prompt": payload["prompt"], "status": "requesting",
                    "options": {k: v for k, v in payload.items() if k not in ("prompt", "input_references")}}
            report["assets"].append(item)
            report["requests_started"] += 1
            write(folder / "report.json", report)
            started = time.monotonic()
            response = api.request_json("/images", key, payload)
            item["seconds"] = round(time.monotonic() - started, 3)
            item["usage"] = response.get("usage")
            costs = [a.get("usage", {}).get("cost") if isinstance(a.get("usage"), dict) else None for a in report["assets"]]
            report["total_cost_usd"] = sum(costs) if all(isinstance(c, (int, float)) for c in costs) else None
            write(folder / "report.json", report)
            # Preserve returned bytes even when dimensions/alpha fail validation.
            if len(response.get("data", [])) == 1:
                (folder / f"{name}_raw.png").write_bytes(base64.b64decode(response["data"][0]["b64_json"], validate=True))
            im = decode_asset(response, bool(oid))
            item.update(status="generated", size=list(im.size), raw=f"{name}_raw.png", sha256=sha(folder / f"{name}_raw.png"))
            write(folder / "report.json", report)
            print(json.dumps({"asset": name, "completed": len(report["assets"]), "seconds": item["seconds"], "usage": item["usage"]}), flush=True)
        report["status"] = "awaiting_user_review"
        write(folder / "report.json", report)
        write(RUNS.parent / "current.json", {"run_id": folder.name})
        return folder
    except (Exception, KeyboardInterrupt) as exc:
        report["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        report["error"] = {"type": type(exc).__name__, "message": "Request or image validation failed; no retry. Inspect retained output and billing."}
        write(folder / "report.json", report)
        raise RuntimeError(report["error"]["message"]) from None


def ground(cam, cfg, layers, textures):
    size = cam["size"]
    yy, xx = np.indices((size, size))
    u = (xx + .5 - cam["cx"]) * cam["scale"]
    q = -(yy + .5 - cam["cy"]) * cam["scale"] / math.sin(geo.PHI)
    e, n = u * math.cos(geo.ALPHA) + q * math.sin(geo.ALPHA), -u * math.sin(geo.ALPHA) + q * math.cos(geo.ALPHA)
    tx = np.floor(e / cfg["material_meters_per_pixel"]).astype(int) % 64
    ty = np.floor(n / cfg["material_meters_per_pixel"]).astype(int) % 64
    material_ids = Image.new("L", (size, size), 1)
    draw = ImageDraw.Draw(material_ids)
    for key, index in (("park", 4), ("heri", 3), ("temple", 3), ("river", 5)):
        for ring in layers.get(key, []):
            draw.polygon([project((*p, 0), cam) for p in geo.dec_ring(ring)], fill=index)
    for width, ring in sorted(layers["road"], key=lambda x: x[0]):
        points = [project((*p, 0), cam) for p in geo.dec_ring(ring)]
        pixels = max(1, round(width / 10 / cam["scale"]))
        draw.line(points, fill=2, width=pixels + max(2, round(2 / cam["scale"])), joint="curve")
        draw.line(points, fill=0, width=pixels, joint="curve")
    ids = np.asarray(material_ids)
    result = np.full((size, size, 3), (208, 192, 142), dtype=np.uint8)
    for index, name in ((0, "asphalt"), (2, "sidewalk"), (3, "courtyard")):
        tile = textures.get(name)
        if tile is not None:
            result[ids == index] = np.asarray(tile)[ty, tx][ids == index]
        else:
            result[ids == index] = {0: (93, 108, 109), 2: (219, 195, 141), 3: (199, 177, 117)}[index]
    green = np.stack((76 + (tx % 9 == 0) * 9, 121 + (ty % 7 == 0) * 12, np.full_like(tx, 66)), -1)
    result[ids == 4] = green[ids == 4]
    result[ids == 5] = (80, 149, 171)
    return Image.fromarray(result), -q * math.cos(geo.PHI)


def build(run=None, destination=None):
    cfg, city, layers, meta = inputs()
    dest = Path(destination) if destination else PUBLIC
    dest.mkdir(parents=True, exist_ok=True)
    report = read(Path(run) / "report.json") if run else None
    if report and report['status'] != 'awaiting_user_review':
        raise ValueError('Incomplete generation cannot replace the demo')
    prepared = read(Path(run) / "inputs/manifest.json") if run else prepare()
    if prepared["snapshot_sha256"] != sha(geo.DATA / "snapshot.json"):
        raise ValueError("Run snapshot differs")
    if report:
        for b in prepared["buildings"]:
            if sha(Path(run) / 'inputs' / b['input']) != b['sha256']:
                raise ValueError('Geometry reference changed')
    shapes = {oid: faces(city, oid) for oid in cfg["building_ids"]}
    cam = fit([f for group in shapes.values() for f in group], cfg["width"] // cfg["art_pixel"], 28)
    textures, review_assets = {}, []
    if report:
        for a in report["assets"]:
            if a["status"] != "generated":
                continue
            path = Path(run) / a["raw"]
            if sha(path) != a["sha256"]:
                raise ValueError("Raw image changed")
            if a["building_id"] is None:
                tile = Image.open(path).convert("RGB").resize((64, 64), Image.Resampling.BOX)
                tile.save(dest / f"{a['name']}.png")
                textures[a["name"]] = tile
                repeat = Image.new("RGB", (192, 192))
                for y in range(3):
                    for x in range(3):
                        repeat.paste(tile, (x * 64, y * 64))
                repeat.save(dest / f"{a['name']}_repeat.png")
                arr = np.asarray(tile).astype(float)
                review_assets.append({"name": a["name"], "kind": "material", "image": f"{a['name']}.png",
                                      "repeat": f"{a['name']}_repeat.png", "edge_mae": float((np.abs(arr[0] - arr[-1]).mean() + np.abs(arr[:, 0] - arr[:, -1]).mean()) / 2),
                                      "status": "candidate_unreviewed"})
    base_ground, ground_depth = ground(cam, cfg, layers, {})
    art_ground, _ = ground(cam, cfg, layers, textures)
    base_ground.save(dest / "ground_base.png")
    art_ground.save(dest / "ground.png")
    encode_depth(ground_depth).save(dest / "ground_depth.png")
    composite = np.asarray(art_ground.convert("RGBA")).copy()
    zbuffer = ground_depth.copy()
    objects = []
    for oid, shape in shapes.items():
        image, values, surface = raster(shape, cam)
        box = image.getbbox()
        if box is None:
            raise ValueError("Empty building: " + str(oid))
        x0, y0, x1, y1 = box
        base = image.crop(box)
        sprite = base
        record = {"id": oid, "source_index": oid - 1, "footprint": geo.dec_ring(city["rings"][oid - 1]),
                  "height": city["h"][oid - 1] / 10, "kind": city["kind"][oid - 1], "xy": [x0, y0],
                  "size": list(base.size), "base": f"building_{oid}_base.png", "sprite": f"building_{oid}.png",
                  "depth": f"building_{oid}_depth.png", "light": f"building_{oid}_light.png", "status": "baseline", "has_light": False}
        if report and oid in cfg["ai_building_ids"]:
            item = next((a for a in report["assets"] if a.get("building_id") == oid and a["status"] == "generated"), None)
            if item:
                source = next(a for a in prepared["buildings"] if a["id"] == oid)
                canonical = source["camera"]
                raw_path = Path(run) / item["raw"]
                if sha(raw_path) != item['sha256']:
                    raise ValueError('Raw building image changed')
                raw = Image.open(raw_path).convert("RGBA").resize((1024, 1024), Image.Resampling.NEAREST)
                ratio = canonical["scale"] / cam["scale"]
                # Inverse of the immutable source-to-scene transform; never fit to generated alpha bounds.
                matrix = (1 / ratio, 0, (x0 - cam["cx"]) / ratio + canonical["cx"],
                          0, 1 / ratio, (y0 - cam["cy"]) / ratio + canonical["cy"])
                candidate = raw.transform(base.size, Image.Transform.AFFINE, matrix, Image.Resampling.NEAREST)
                candidate.save(dest / f"building_{oid}_candidate.png")
                raw.resize((512, 512), Image.Resampling.NEAREST).save(dest / f"building_{oid}_review.png")
                Image.open(Path(run) / "inputs" / source["input"]).resize((512, 512), Image.Resampling.NEAREST).save(dest / f"building_{oid}_geometry.png")
                expected, actual = np.asarray(base)[..., 3] > 127, np.asarray(candidate)[..., 3] > 127
                iou = float((expected & actual).sum() / max(1, (expected | actual).sum()))
                # Report full-input alpha IoU as well: crop-local IoU cannot detect invented geometry outside the crop.
                target_alpha = np.asarray(Image.open(Path(run) / "inputs" / source["input"]).convert("RGBA"))[..., 3] > 127
                raw_alpha = np.asarray(raw)[..., 3] > 127
                full_iou = float((target_alpha & raw_alpha).sum() / max(1, (target_alpha | raw_alpha).sum()))
                accepted = min(iou, full_iou) >= cfg["alpha_iou_min"]
                record.update(status="candidate_unreviewed" if accepted else "geometry_rejected", alpha_iou=iou, full_alpha_iou=full_iou)
                if accepted:
                    a = np.asarray(candidate).copy()
                    a[..., 3] = np.where(expected & actual, 255, 0)
                    sprite = Image.fromarray(a)
                review_assets.append({"name": f"building_{oid}", "kind": "building", "status": record["status"],
                                      "image": f"building_{oid}_review.png", "geometry": f"building_{oid}_geometry.png",
                                      "alpha_iou": iou, "full_alpha_iou": full_iou})
        base.save(dest / record["base"])
        sprite.save(dest / record["sprite"])
        encode_depth(values[y0:y1, x0:x1]).save(dest / record["depth"])
        light = Image.new("RGBA", base.size)
        windows = cfg["light_windows"].get(str(oid), []) if report and cfg.get("light_reference_run") == report["run_id"] and record["status"] == "candidate_unreviewed" else []
        for polygon in windows:
            ImageDraw.Draw(light).polygon([tuple(p) for p in polygon], fill=(255, 210, 99, 220))
        light_array = np.asarray(light).copy()
        wall = surface[y0:y1, x0:x1] >= 2
        light_array[..., 3] = np.where(wall & (np.asarray(sprite)[..., 3] > 127), light_array[..., 3], 0)
        record["has_light"] = bool(light_array[..., 3].any())
        Image.fromarray(light_array).save(dest / record["light"])
        visible = (np.asarray(sprite)[..., 3] > 127) & (values[y0:y1, x0:x1] > zbuffer[y0:y1, x0:x1])
        composite[y0:y1, x0:x1][visible] = np.asarray(sprite)[visible]
        zbuffer[y0:y1, x0:x1][visible] = values[y0:y1, x0:x1][visible]
        objects.append(record)
    Image.fromarray(composite).save(dest / "preview.png")
    passed = sum(o["status"] == "candidate_unreviewed" for o in objects)
    rejected = sum(o["status"] == "geometry_rejected" for o in objects)
    manifest = {"version": 1, "kind": "object_pilot", "status": "awaiting_user_review", "run_id": report["run_id"] if report else "offline-baseline",
                "width": cfg["width"], "height": cfg["width"], "art_pixel": cfg["art_pixel"], "camera": cam,
                "origin": meta["origin"], "snapshot_sha256": sha(geo.DATA / "snapshot.json"),
                "depth_encoding": {"offset": DEPTH_OFFSET, "scale": DEPTH_SCALE, "near": "maximum", "background": 0},
                "ground": "ground.png", "ground_base": "ground_base.png", "ground_depth": "ground_depth.png", "objects": objects,
                "materials": review_assets, "ai_building_ids": cfg["ai_building_ids"], "preview": "preview.png",
                "review_summary": f"18개 객체 · AI 외관 {passed}/3채 윤곽 통과 · {rejected}채 미채택 · 실물 외관 복원 아님 · 미감 미승인",
                "attribution": "국토교통부 / VWorld 공간데이터 · AI 외관 재해석 · 보도/보행 경로는 시험용 · 로컬 검수"}
    if report:
        manifest["generation"] = {k: report[k] for k in ("model", "requests_started", "total_cost_usd")}
        write(dest / "generation.json", {k: report[k] for k in ("run_id", "status", "model", "assets", "total_cost_usd", "requests_started", "style_sha256")})
    manifest["asset_sha256"] = {p.name: sha(p) for p in sorted(dest.glob('*.png'))}
    write(dest / "manifest.json", manifest)
    cards = []
    for a in review_assets:
        second = a.get("geometry", a.get("repeat"))
        cards.append(f'<article><h2>{html.escape(a["name"])}</h2><p>{html.escape(a["status"])}</p><img src="{a["image"]}"><img src="{second}"><pre>{html.escape(json.dumps(a, ensure_ascii=False, indent=2))}</pre></article>')
    (dest / "index.html").write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>객체 에셋 검수</title><style>body{background:#fbf3e4;color:#3a2a1e;font:16px system-ui;margin:24px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px}article{border:1px solid #cab48d;padding:12px;overflow:hidden}img{max-width:100%;image-rendering:pixelated;background:repeating-conic-gradient(#ddd 0 25%,#fff 0 50%) 0/16px 16px}pre{white-space:pre-wrap}</style><h1>객체형 픽셀 지도 — 에셋 검수</h1><p>원형/AI 후보 및 반복 이음새 비교. 미감 미승인. 도형 불합격 후보는 지도에서 기본 도형으로 표시합니다.</p><a href="../../web/pilot/?view=objects">객체 지도 열기</a> · <a href="generation.json">프롬프트·비용 기록</a><main>' + ''.join(cards) + '</main></html>')
    print(json.dumps({"output": str(dest), "objects": len(objects), "reviews": [{"name": a["name"], "status": a["status"]} for a in review_assets]}), flush=True)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "generate", "build"))
    parser.add_argument("--allow-external", action="store_true")
    parser.add_argument("--run", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "generate":
        generate(args.allow_external)
    else:
        if args.run is None:
            parser.error('build requires --run; the committed demo needs no generation or rebuild')
        build(args.run)
