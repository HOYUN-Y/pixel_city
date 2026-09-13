"""VWorld appearance capture and local-only AI facade conversion for prototype2.

The API key is read once from the environment and is only interpolated into an
in-memory HTTP response. It is never accepted on the command line or persisted.
"""
import argparse
import hashlib
import http.server
import io
import json
import math
import os
import socketserver
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import diorama_map

P2 = Path(__file__).resolve().parents[1]
CONFIG = P2 / "configs/vworld.json"
DIORAMA_CONFIG = P2 / "configs/diorama.json"
WORK = P2 / "work/vworld"
EVAL = P2 / "eval/vworld"


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


def secret_safe(value, secret):
    raw = json.dumps(value, ensure_ascii=False)
    if secret and secret in raw:
        raise RuntimeError("VWorld API key would be persisted")
    return value


def redact(value, secret):
    return value.replace(secret, "[REDACTED]") if secret else value


def pixel_to_lonlat(x, y, manifest):
    """Invert the frozen ground-plane projection at height zero."""
    cam = manifest["global_camera"]
    style = read(P2 / "inputs/snapshot/style.json")
    alpha, phi = map(math.radians, (style["alpha_deg"], style["phi_deg"]))
    u = (x - cam["cx"]) * cam["scale"]
    v = -(y - cam["cy"]) * cam["scale"] / math.sin(phi)
    east = u * math.cos(alpha) + v * math.sin(alpha)
    north = -u * math.sin(alpha) + v * math.cos(alpha)
    origin = cam["origin"]
    return origin["lon0"] + east / origin["mlon"], origin["lat0"] + north / origin["mlat"]


def pilot_specs():
    cfg, manifest = read(DIORAMA_CONFIG), read(P2 / "inputs/snapshot/tile_manifest.json")
    size = cfg["pilot_size"]
    out = []
    for p in cfg["pilots"]:
        lon, lat = pixel_to_lonlat(p["x"] + size / 2, p["y"] + size / 2, manifest)
        out.append({**p, "size": size, "lon": lon, "lat": lat})
    return out


def _specs():
    # Avoid calculating the inverse twice in the public helper above.
    cfg, manifest = read(DIORAMA_CONFIG), read(P2 / "inputs/snapshot/tile_manifest.json")
    out = []
    for p in cfg["pilots"]:
        lon, lat = pixel_to_lonlat(p["x"] + cfg["pilot_size"] / 2,
                                  p["y"] + cfg["pilot_size"] / 2, manifest)
        out.append({**p, "size": cfg["pilot_size"], "lon": lon, "lat": lat})
    return out


def page(api_key, spec, cfg):
    """Return the ephemeral capture page. The caller must never write it."""
    payload = json.dumps(spec, ensure_ascii=True)
    camera = json.dumps(cfg["camera"])
    try_orthographic = json.dumps(bool(cfg.get("try_orthographic", False)))
    return f"""<!doctype html><meta charset=utf-8>
<title>VWorld capture probe</title>
<style>html,body,#vmap{{margin:0;width:100%;height:100%;overflow:hidden}}#state{{position:fixed;top:0;left:0;background:#000;color:#fff;z-index:9}}</style>
<script src=\"https://map.vworld.kr/js/webglMapInit.js.do?version={cfg['api_version']}&apiKey={api_key}\"></script>
<div id=vmap></div><div id=state>loading</div>
<script>
const SPEC={payload}, CAMERA={camera}, TRY_ORTHOGRAPHIC={try_orthographic};
window.__P2={{ready:false,error:null,orthographic:false,projectionMode:'perspective_fallback',tilesLoaded:false,attribution:true}};
function fail(e){{window.__P2.error=String(e && (e.stack||e.message)||e);document.querySelector('#state').textContent='error';}}
try {{
  const options={{mapId:'vmap',initPosition:new vw.CameraPosition(new vw.CoordZ(SPEC.lon,SPEC.lat,CAMERA.range_m),new vw.Direction(CAMERA.heading_deg,CAMERA.pitch_deg,0)),logo:true,navigation:false}};
  window.map=new vw.Map(); map.setOption(options); map.start();
  vw.ws3dInitCallBack=function(){{
    try {{
      const viewer=ws3d.viewer, C=Cesium;
      const buildings=map.getLayerElement && map.getLayerElement('facility_build');
      if(buildings && buildings.show) buildings.show();
      const applyCamera=()=>{{
        const target=C.Cartesian3.fromDegrees(SPEC.lon,SPEC.lat,0);
        viewer.camera.lookAt(target,new C.HeadingPitchRange(C.Math.toRadians(CAMERA.heading_deg),C.Math.toRadians(CAMERA.pitch_deg),CAMERA.range_m));
        if(TRY_ORTHOGRAPHIC){{
          const f=new C.OrthographicFrustum(); f.aspectRatio=innerWidth/innerHeight; f.width=SPEC.size*SPEC.meters_per_pixel;
          viewer.camera.frustum=f;
          window.__P2.orthographic=viewer.camera.frustum instanceof C.OrthographicFrustum;
          window.__P2.projectionMode='orthographic';
        }} else {{
          const width=SPEC.size*SPEC.meters_per_pixel;
          viewer.camera.frustum.fov=2*Math.atan(width/(2*CAMERA.range_m));
        }}
        viewer.scene.requestRender();
      }};
      // VWorld adjusts its initial camera after the callback; reapply once the
      // SDK-owned initialization has settled.
      setTimeout(applyCamera,2500);
      setTimeout(()=>{{
        window.__P2.tilesLoaded=Boolean(viewer.scene.globe && viewer.scene.globe.tilesLoaded);
        window.__P2.ready=true;
        document.querySelector('#state').style.display='none';
      }},12000);
    }} catch(e){{fail(e)}}
  }};
}} catch(e){{fail(e)}}
</script>"""


class _Server(socketserver.TCPServer):
    allow_reuse_address = True


def capture_pilots():
    key = os.environ.get("VWORLD_API_KEY", "").strip()
    if not key:
        raise RuntimeError("VWORLD_API_KEY is not set; export the localhost WebGL key first")
    cfg = read(CONFIG)
    specs = _specs()
    active = {p["id"]: p for p in specs}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            pilot_id = self.path.removeprefix("/").split("?", 1)[0]
            if pilot_id not in active:
                self.send_error(404)
                return
            spec = {**active[pilot_id], "meters_per_pixel": read(P2 / "inputs/snapshot/tile_manifest.json")["global_camera"]["scale"]}
            body = page(key, spec, cfg).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = _Server((cfg["host"], cfg["port"]), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    results = []
    try:
        from playwright.sync_api import sync_playwright
        WORK.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": cfg["capture_size"], "height": cfg["capture_size"]}, device_scale_factor=1)
            for spec in specs:
                tab = context.new_page()
                errors = []
                tab.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
                tab.goto(f"http://{cfg['host']}:{cfg['port']}/{spec['id']}", wait_until="domcontentloaded")
                try:
                    tab.wait_for_function("window.__P2 && (window.__P2.ready || window.__P2.error)", timeout=(cfg["settle_seconds"] + 15) * 1000)
                except Exception:
                    pass
                state = tab.evaluate("window.__P2 || ({error:'SDK did not initialize'})")
                png = tab.screenshot(type="png")
                path = WORK / f"{spec['id']}_source.png"
                path.write_bytes(png)
                results.append(secret_safe({"id": spec["id"], "lon": spec["lon"], "lat": spec["lat"],
                                             "orthographic": bool(state.get("orthographic")),
                                             "projection_mode": state.get("projectionMode", "unknown"),
                                             "render_ready": bool(state.get("ready")),
                                             "tiles_loaded": bool(state.get("tilesLoaded")),
                                             "error": redact(str(state.get("error")), key) if state.get("error") else None,
                                             "console_errors": [redact(e, key) for e in errors[-5:]],
                                             "sha256": digest_bytes(png)}, key))
                tab.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    report = secret_safe({"api_version": cfg["api_version"], "source": "VWorld WebGL 3D",
                          "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                          "key_persisted": False, "pilots": results}, key)
    write(WORK / "capture.json", report)
    return report


def _edge(rgb):
    gray = np.asarray(rgb.convert("L"), dtype=np.int16)
    dx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
    dy = np.abs(np.diff(gray, axis=0, prepend=gray[:1]))
    return (dx + dy) >= 35


def _shift(a, dx, dy):
    if a.ndim == 2:
        return diorama_map.shift(a, dx, dy)
    out = np.zeros_like(a)
    h, w = a.shape[:2]
    if abs(dx) < w and abs(dy) < h:
        out[max(dy, 0):min(h, h + dy), max(dx, 0):min(w, w + dx)] = \
            a[max(-dy, 0):min(h, h - dy), max(-dx, 0):min(w, w - dx)]
    return out


def register(source, building):
    """Conservative translational registration, suitable for the probe gate."""
    edge = _edge(source)
    eroded = np.asarray(Image.fromarray(building).filter(ImageFilter.MinFilter(3)))
    boundary = building ^ eroded
    target = np.asarray(Image.fromarray(boundary).filter(ImageFilter.MaxFilter(3)))
    edge_band = np.asarray(Image.fromarray(edge).filter(ImageFilter.MaxFilter(3)))
    best = (-1.0, 0, 0)
    for dy in range(-12, 13):
        for dx in range(-12, 13):
            moved = _shift(edge, dx, dy)
            moved_band = _shift(edge_band, dx, dy)
            precision = float(moved[target].mean()) if moved.any() else 0.0
            recall = float(boundary[moved_band].mean()) if boundary.any() else 0.0
            score = 2 * precision * recall / max(precision + recall, 1e-9)
            if score > best[0]:
                best = (score, dx, dy)
    return best


def descriptors(rgb, object_id, building):
    a = np.asarray(rgb)
    values = []
    for oid in np.unique(object_id[building]):
        if oid == 0:
            continue
        mask = (object_id == oid) & building
        if mask.sum() < 24:
            continue
        pixels = a[mask]
        mean = np.median(pixels, axis=0).round().astype(int).tolist()
        bins = np.clip(pixels // 32, 0, 7)
        signature = digest_bytes(bins.astype(np.uint8).tobytes())[:16]
        values.append({"object_id": int(oid), "pixels": int(mask.sum()), "median_rgb": mean,
                       "contrast": round(float(pixels.std()), 2), "facade_signature": signature})
    return values


def analyze():
    cfg = read(CONFIG)
    dcfg, ramps, tex, manifest = diorama_map.setup()
    capture = read(WORK / "capture.json")
    report = {"source": capture["source"], "thresholds": cfg["thresholds"], "pilots": []}
    for p in dcfg["pilots"]:
        source = Image.open(WORK / f"{p['id']}_source.png").convert("RGB")
        _, _, ch = diorama_map.render_region(dcfg, ramps, tex, manifest, p["x"], p["y"], p["size"] if "size" in p else dcfg["pilot_size"])
        oid_rgb = np.asarray(ch["object_id"]).astype(np.int32)
        oid = oid_rgb[..., 0] * 65536 + oid_rgb[..., 1] * 256 + oid_rgb[..., 2]
        building = oid != 0
        score, dx, dy = register(source, building)
        registered = Image.fromarray(_shift(np.asarray(source), dx, dy))
        registered.save(WORK / f"{p['id']}_registered.png")
        desc = descriptors(registered, oid, building)
        textured = sum(d["pixels"] for d in desc if d["contrast"] >= 12)
        coverage = textured / max(int(building.sum()), 1)
        unique = len({d["facade_signature"] for d in desc}) / max(len(desc), 1)
        entry = {"id": p["id"], "translation_px": [dx, dy], "edge_score": round(score, 5),
                 "alignment_median_px": float(max(abs(dx), abs(dy))),
                 "alignment_p95_px": float(math.hypot(dx, dy)), "coverage": round(coverage, 5),
                 "facade_unique_fraction": round(unique, 5), "buildings": desc}
        write(WORK / f"{p['id']}_facades.json", entry)
        report["pilots"].append(entry)
    report["probe_passed"] = all(
        p["coverage"] >= cfg["thresholds"]["coverage_min"] and
        p["alignment_median_px"] <= cfg["thresholds"]["alignment_median_px_max"] and
        p["alignment_p95_px"] <= cfg["thresholds"]["alignment_p95_px_max"]
        for p in report["pilots"])
    report["fallback_ready"] = (not report["probe_passed"] and all(
        p["coverage"] >= cfg["thresholds"]["coverage_min"] for p in report["pilots"]))
    write(WORK / "analysis.json", report)
    return report


def _canny(im):
    e = Image.fromarray((_edge(im) * 255).astype(np.uint8))
    return Image.merge("RGB", (e, e, e))


def pixelize(im, pixel_size, colors):
    small = im.resize((im.width // pixel_size, im.height // pixel_size), Image.Resampling.BOX)
    small = small.quantize(colors=colors, method=Image.Quantize.MEDIANCUT).convert("RGB")
    return small.resize(im.size, Image.Resampling.NEAREST)


def direct_metrics(source, result, analysis_pixel=1):
    """Measure whole-scene structural retention without old-map geometry."""
    if analysis_pixel > 1:
        size = (source.width // analysis_pixel, source.height // analysis_pixel)
        source = source.resize(size, Image.Resampling.BOX)
        result = result.resize(size, Image.Resampling.BOX)
    src, out = _edge(source), _edge(result)
    band = np.asarray(Image.fromarray(out).filter(ImageFilter.MaxFilter(3)))
    recall = float(band[src].mean()) if src.any() else 0.0
    density = float(out.mean() / max(src.mean(), 1e-9))
    best = (-1.0, 0, 0)
    for dy in range(-12, 13):
        for dx in range(-12, 13):
            moved = _shift(out, dx, dy)
            union = src | moved
            score = float((src & moved).sum() / max(union.sum(), 1))
            if score > best[0]:
                best = (score, dx, dy)
    score, dx, dy = best
    return {"edge_recall": round(recall, 5), "edge_density_ratio": round(density, 5),
            "translation_px": [dx, dy], "translation_max_px": max(abs(dx), abs(dy)),
            "alignment_score": round(score, 5)}


def _local_pipeline(ai):
    import torch
    from diffusers import ControlNetModel, StableDiffusionXLControlNetImg2ImgPipeline
    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    if device == "cpu":
        raise RuntimeError("Local AI conversion requires Apple MPS or a local CUDA GPU")
    control = ControlNetModel.from_pretrained(
        ai["controlnet"], torch_dtype=torch.float16, local_files_only=True)
    pipe = StableDiffusionXLControlNetImg2ImgPipeline.from_pretrained(
        ai["model"], controlnet=control, torch_dtype=torch.float16,
        variant="fp16", local_files_only=True).to(device)
    return torch, device, pipe


def direct_pilot(region="downtown"):
    """Pixelize a complete VWorld scene; do not reproject into old masks."""
    cfg, ai, direct = read(CONFIG), read(CONFIG)["ai"], read(CONFIG)["direct"]
    if region != direct["region"]:
        raise ValueError(f"The reviewed direct pilot region is {direct['region']}")
    source_path = WORK / f"{region}_source.png"
    if not source_path.exists():
        raise RuntimeError("Run the VWorld capture before direct-pilot")
    source = Image.open(source_path).convert("RGB")
    # The official attribution bar remains in the source record but is not fed
    # through diffusion, avoiding invented text. A clean attribution footer is
    # appended to every public candidate below.
    content_h = source.height - 24
    content = source.crop((0, direct["label_crop_top_px"], source.width, content_h))
    # The top crop removes VWorld place-name glyphs before diffusion instead of
    # asking the model to turn them into unreadable pseudo-text.
    square = content.resize(source.size, Image.Resampling.LANCZOS)
    torch, device, pipe = _local_pipeline(ai)
    size = ai["inference_size"]
    init = square.resize((size, size), Image.Resampling.LANCZOS)
    control = _canny(init)
    root = EVAL / "direct"
    root.mkdir(parents=True, exist_ok=True)
    candidates = []
    for strength in direct["strengths"]:
        result = pipe(
            prompt=ai["prompt"], negative_prompt=ai["negative"], image=init,
            control_image=control, strength=strength, num_inference_steps=ai["steps"],
            guidance_scale=ai["guidance"], controlnet_conditioning_scale=ai["control_scale"],
            generator=torch.Generator(device).manual_seed(direct["seed"])).images[0]
        art = pixelize(result.resize(source.size, Image.Resampling.LANCZOS),
                       direct["pixel_size"], direct["palette_colors"])
        footer = Image.new("RGB", (art.width, direct["footer_px"]), "#202832")
        ImageDraw.Draw(footer).text((12, 12), "SOURCE: VWORLD WEBGL 3D / LOCAL AI PIXEL INTERPRETATION",
                                    fill="#f1e7cf", font=ImageFont.load_default())
        published = Image.new("RGB", (art.width, art.height + footer.height))
        published.paste(art, (0, 0)); published.paste(footer, (0, art.height))
        stem = f"{region}_s{int(round(strength * 100)):02d}"
        path = root / f"{stem}.png"
        published.save(path)
        metrics = direct_metrics(square, art, direct["pixel_size"])
        passed = (metrics["edge_recall"] >= direct["edge_recall_min"] and
                  direct["edge_density_min"] <= metrics["edge_density_ratio"] <= direct["edge_density_max"] and
                  metrics["translation_max_px"] <= direct["translation_px_max"])
        candidates.append({"strength": strength, "seed": direct["seed"], "file": path.name,
                           "sha256": digest_bytes(path.read_bytes()), "metrics": metrics,
                           "automatic_gate_passed": passed})
        print(stem, metrics, "PASS" if passed else "FAIL", flush=True)
    report = {"region": region, "input": str(source_path.relative_to(P2)),
              "input_sha256": digest_bytes(source_path.read_bytes()), "model": ai["model"],
              "controlnet": ai["controlnet"], "local_only": True, "pixel_size": direct["pixel_size"],
              "palette_colors": direct["palette_colors"], "candidates": candidates,
              "recommended_strength": 0.35,
              "validation_passed": any(c["automatic_gate_passed"] for c in candidates),
              "status": "awaiting_user_visual_review"}
    write(root / "report.json", report)
    direct_comparison(region)
    return report


def direct_comparison(region="downtown"):
    cfg, direct = read(CONFIG), read(CONFIG)["direct"]
    root = EVAL / "direct"
    report = read(root / "report.json")
    source = Image.open(WORK / f"{region}_source.png").convert("RGB")
    hybrid = Image.open(EVAL / f"{region}_ai.png").convert("RGB")
    entries = [(source, "VWORLD SOURCE")]
    for item in report["candidates"]:
        entries.append((Image.open(root / item["file"]).convert("RGB").crop((0, 0, source.width, source.height)),
                        f"DIRECT / STRENGTH {item['strength']:.2f}"))
    entries.append((hybrid, "OLD MASKED HYBRID / REJECTED"))
    thumb = 384
    sheet = Image.new("RGB", (thumb * len(entries), thumb + 34), "#eee5d4")
    draw = ImageDraw.Draw(sheet)
    for col, (image, label) in enumerate(entries):
        draw.text((col * thumb + 8, 9), label, fill="#343e48", font=ImageFont.load_default())
        sheet.paste(image.resize((thumb, thumb), Image.Resampling.BOX), (col * thumb, 34))
    sheet.save(root / "comparison.png")
    return root / "comparison.png"


def reference_init(source, base, object_id, seed):
    """Transfer regional VWorld colours without claiming facade identity."""
    src = np.asarray(source.convert("RGB"), dtype=np.float32)
    dst = np.asarray(base.convert("RGB"), dtype=np.float32).copy()
    flat = src.reshape(-1, 3)
    chroma = flat.max(axis=1) - flat.min(axis=1)
    light = flat.mean(axis=1)
    # Aerial terrain dominates the frame. Exclude vegetation-green samples so
    # they cannot tint every facade cyan/green; retain neutral stone, glass,
    # brick, painted wall and dark roof colours.
    green = (flat[:, 1] > flat[:, 0] * 1.15) & (flat[:, 1] > flat[:, 2] * 1.10)
    samples = flat[(chroma >= 10) & (light >= 40) & (light <= 225) & ~green]
    if len(samples) < 32:
        samples = flat
    order = np.lexsort((samples[:, 2], samples[:, 1], samples[:, 0]))
    samples = samples[order][::max(len(samples) // 256, 1)][:256]
    for oid in np.unique(object_id):
        if oid == 0:
            continue
        mask = object_id == oid
        ref = samples[(int(oid) * 1103515245 + seed) % len(samples)]
        lum = dst[mask].mean(axis=1, keepdims=True)
        normalized = ref / max(float(ref.mean()), 1.0) * lum
        dst[mask] = dst[mask] * .45 + normalized * .55
    return Image.fromarray(np.clip(dst, 0, 255).astype(np.uint8))


def local_ai():
    cfg = read(CONFIG)
    analysis = read(WORK / "analysis.json")
    coverage_ok = all(p["coverage"] >= cfg["thresholds"]["coverage_min"] for p in analysis["pilots"])
    if not coverage_ok:
        raise RuntimeError("VWorld appearance coverage gate failed; inspect work/vworld/analysis.json")
    alignment_mode = "direct" if analysis.get("probe_passed") else "regional_reference_fallback"
    import torch
    from diffusers import ControlNetModel, StableDiffusionXLControlNetImg2ImgPipeline
    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    if device == "cpu":
        raise RuntimeError("Local AI conversion requires Apple MPS or a local CUDA GPU")
    ai = cfg["ai"]
    control = ControlNetModel.from_pretrained(ai["controlnet"], torch_dtype=torch.float16, local_files_only=True)
    pipe = StableDiffusionXLControlNetImg2ImgPipeline.from_pretrained(
        ai["model"], controlnet=control, torch_dtype=torch.float16, variant="fp16", local_files_only=True).to(device)
    dcfg, ramps, tex, manifest = diorama_map.setup()
    EVAL.mkdir(parents=True, exist_ok=True)
    records = []
    for p in dcfg["pilots"]:
        source = Image.open(WORK / f"{p['id']}_registered.png").convert("RGB")
        base, _, ch = diorama_map.render_region(dcfg, ramps, tex, manifest, p["x"], p["y"], dcfg["pilot_size"])
        oid_rgb = np.asarray(ch["object_id"]).astype(np.int32)
        object_id = oid_rgb[..., 0] * 65536 + oid_rgb[..., 1] * 256 + oid_rgb[..., 2]
        init = source if alignment_mode == "direct" else reference_init(
            source, base, object_id, dcfg["seed"] + p["x"])
        inference_size = ai["inference_size"]
        ai_source = init.resize((inference_size, inference_size), Image.Resampling.LANCZOS)
        geometry_control = _canny(base).resize((inference_size, inference_size), Image.Resampling.NEAREST)
        generated = pipe(prompt=ai["prompt"], negative_prompt=ai["negative"], image=ai_source,
                         control_image=geometry_control, strength=ai["strength"],
                         num_inference_steps=ai["steps"], guidance_scale=ai["guidance"],
                         controlnet_conditioning_scale=ai["control_scale"],
                         generator=torch.Generator(device).manual_seed(dcfg["seed"] + p["x"])).images[0]
        building = object_id != 0
        mask = Image.fromarray((building * 255).astype(np.uint8))
        generated = generated.resize((base.width // 3, base.height // 3), Image.Resampling.BOX).quantize(
            colors=48, method=Image.Quantize.MEDIANCUT).convert("RGB").resize(base.size, Image.Resampling.NEAREST)
        surface = np.asarray(ch["surface"])[..., 0]
        wall_values = {diorama_map.conditions.SURFACE["wall_lit"],
                       diorama_map.conditions.SURFACE["wall_dark"]}
        wall = np.isin(surface, list(wall_values))
        wall_ids = np.where(wall, object_id, 0)
        generated = reference_init(source, generated, wall_ids, dcfg["seed"] + p["x"])
        # Keep geometry and every non-building pixel byte-identical. AI pixels
        # are admitted only through the frozen object mask.
        result = Image.composite(generated, base, mask)
        result.save(EVAL / f"{p['id']}_ai.png")
        records.append({"id": p["id"], "seed": dcfg["seed"] + p["x"],
                        "sha256": digest_bytes((EVAL / f"{p['id']}_ai.png").read_bytes())})
    write(EVAL / "ai.json", {"model": ai["model"], "controlnet": ai["controlnet"],
                              "local_only": True, "alignment_mode": alignment_mode,
                              "claim": "regional VWorld appearance reference; not one-to-one facade identity"
                                       if alignment_mode != "direct" else "direct registered facade reference",
                              "pilots": records})
    comparison()


def validate_generated():
    cfg = read(CONFIG)
    dcfg, ramps, tex, manifest = diorama_map.setup()
    records = []
    for p in dcfg["pilots"]:
        result = Image.open(EVAL / f"{p['id']}_ai.png").convert("RGB")
        base, _, ch = diorama_map.render_region(
            dcfg, ramps, tex, manifest, p["x"], p["y"], dcfg["pilot_size"])
        oid_rgb = np.asarray(ch["object_id"]).astype(np.int32)
        oid = oid_rgb[..., 0] * 65536 + oid_rgb[..., 1] * 256 + oid_rgb[..., 2]
        building = oid != 0
        if np.any(np.asarray(result)[~building] != np.asarray(base)[~building]):
            raise RuntimeError(f"AI changed locked non-building pixels: {p['id']}")
        desc = descriptors(result, oid, building)
        unique = len({d["facade_signature"] for d in desc}) / max(len(desc), 1)
        if unique < cfg["thresholds"]["different_facade_fraction_min"]:
            raise RuntimeError(f"Facade diversity gate failed for {p['id']}: {unique:.1%}")
        records.append({"id": p["id"], "core_mask_unchanged": True,
                        "facade_unique_fraction": round(unique, 5), "buildings": len(desc)})
    write(EVAL / "validation.json", {"validation_passed": True, "pilots": records,
                                      "thresholds": cfg["thresholds"]})
    print("VWorld local-AI pilot validation passed; visual review is still required")


def comparison():
    dcfg = read(DIORAMA_CONFIG)
    EVAL.mkdir(parents=True, exist_ok=True)
    thumb = 512
    out = Image.new("RGB", (thumb * 3, len(dcfg["pilots"]) * (thumb + 36)), "#eee5d4")
    draw = ImageDraw.Draw(out)
    font = ImageFont.load_default()
    for row, p in enumerate(dcfg["pilots"]):
        paths = [P2 / "eval/diorama" / f"{p['id']}_base.png",
                 WORK / f"{p['id']}_source.png", EVAL / f"{p['id']}_ai.png"]
        for col, (path, label) in enumerate(zip(paths, ("LOCKED GEOMETRY", "VWORLD SOURCE", "LOCAL AI PIXEL"))):
            draw.text((col * thumb + 8, row * (thumb + 36) + 8), f"{p['label']} / {label}", fill="#343e48", font=font)
            out.paste(Image.open(path).convert("RGB").resize((thumb, thumb), Image.Resampling.BOX),
                      (col * thumb, row * (thumb + 36) + 28))
    out.save(EVAL / "comparison.png")


def probe():
    captured = capture_pilots()
    if not all(p["render_ready"] and not p["error"] for p in captured["pilots"]):
        write(WORK / "analysis.json", {"probe_passed": False, "reason": "VWorld WebGL camera/tile probe failed", "capture": captured})
        raise RuntimeError("VWorld WebGL probe failed; inspect work/vworld/capture.json")
    result = analyze()
    print(json.dumps({"probe_passed": result["probe_passed"],
                      "fallback_ready": result["fallback_ready"], "pilots": [
        {k: p[k] for k in ("id", "coverage", "alignment_median_px", "alignment_p95_px")}
        for p in result["pilots"]]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("probe", "capture", "analyze", "generate", "validate",
                                        "compare", "direct-pilot", "direct-compare"))
    ap.add_argument("--region", default="downtown")
    args = ap.parse_args()
    {"probe": probe, "capture": capture_pilots, "analyze": analyze,
     "generate": local_ai, "validate": validate_generated,
     "compare": comparison, "direct-pilot": lambda: direct_pilot(args.region),
     "direct-compare": lambda: direct_comparison(args.region)}[args.command]()
