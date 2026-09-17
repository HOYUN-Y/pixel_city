"""Explicit opt-in, single-image OpenRouter comparison. No retries or fallbacks."""
import argparse
import base64
import html
import io
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

import numpy as np
from PIL import Image
import qwen_style as qs

MODEL = "openai/gpt-image-2.5-sunburst"
API = "https://openrouter.ai/api/v1"
ROOT = qs.P2 / "eval/vworld/openrouter"
BASELINE = qs.P2 / "eval/vworld/qwen/q8/runs/20260913T113310465855Z"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward authorization or images to another URL.


def safe_generation_id(value):
    """Keep only provider generation identifiers, never arbitrary response text."""
    return value if isinstance(value, str) and re.fullmatch(r'gen-[A-Za-z0-9_-]{1,160}', value) else None


class RequestFailure(RuntimeError):
    def __init__(self, message, *, http_status=None, generation_id=None):
        super().__init__(message)
        self.http_status = http_status
        self.generation_id = safe_generation_id(generation_id)


def request_json(path, key, payload=None):
    req = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {key}",
                                 "Content-Type": "application/json"},
                                 data=json.dumps(payload).encode() if payload is not None else None)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=600) as response:
            data = response.read(64 * 1024 * 1024 + 1)
        if len(data) > 64 * 1024 * 1024:
            raise ValueError("Response exceeds 64 MiB")
        return json.loads(data)
    except urllib.error.HTTPError as exc:
        raise RequestFailure(f"OpenRouter HTTP {exc.code}; no automatic retry",
                             http_status=exc.code,
                             generation_id=exc.headers.get('x-generation-id') if exc.headers else None) from None
    except urllib.error.URLError:
        raise RequestFailure("OpenRouter network error; billing status may be unknown; no retry") from None


def validate_capabilities(data):
    endpoint = next((e for e in data.get("endpoints", []) if e.get("provider_tag") == "openai"), None)
    if endpoint is None:
        raise ValueError("Required OpenAI provider unavailable")
    params = endpoint["supported_parameters"]
    if "high" not in params.get("quality", {}).get("values", []):
        raise ValueError("High quality unsupported")
    if "1:1" not in params.get("aspect_ratio", {}).get("values", []):
        raise ValueError("Square output unsupported")
    if params.get("input_references", {}).get("max", 0) < 2:
        raise ValueError("Two reference images unsupported")
    if not params.get("n", {}).get("min", 0) <= 1 <= params.get("n", {}).get("max", 0):
        raise ValueError("Single image unsupported")
    return endpoint


def reference(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return {"type": "image_url", "image_url": {
        "url": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()}}


def decode(result):
    entries = result.get("data", [])
    if len(entries) != 1:
        raise ValueError("Expected exactly one generated image")
    blob = base64.b64decode(entries[0]["b64_json"], validate=True)
    image = Image.open(io.BytesIO(blob))
    image.load()
    image = image.convert("RGB")
    if image.width != image.height or not 512 <= image.width <= 4096:
        raise ValueError("Unexpected output dimensions")
    if np.asarray(image).std() < 1:
        raise ValueError("Near-uniform image")
    return image


def page(folder, report):
    entries = [("source.png", "VWorld / source"), ("qwen.png", "Local Qwen Q8 / 40 steps"),
               ("api_raw.png", "OpenRouter / Sunburst / raw"), ("api_grid.png", "Sunburst / 2px grid")]
    cards = "".join(f'<figure><figcaption>{label}</figcaption><a href="{file}"><img src="{file}"></a></figure>'
                    for file, label in entries if (folder / file).exists())
    overlay = ''
    if (folder / "api_raw.png").exists():
        overlay = '''<h2>원본 중첩</h2><label>AI 불투명도 <input id="opacity" type="range" min="0" max="100" value="50"></label>
<div class="overlay"><img src="source.png"><img id="ai" src="api_raw.png"></div>
<script>document.querySelector('#opacity').oninput=e=>document.querySelector('#ai').style.opacity=e.target.value/100;</script>'''
    (folder / "index.html").write_text(f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenRouter vs local Qwen</title><style>body{{margin:20px;background:#FBF3E4;color:#3A2A1E;font:16px system-ui}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:16px}}figure{{margin:0}}img{{max-width:100%;image-rendering:pixelated}}
.overlay{{position:relative;max-width:1024px}}.overlay img{{display:block;width:100%}}#ai{{position:absolute;inset:0;opacity:.5}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}</style>
<h1>같은 지도 — 로컬 Qwen / OpenRouter 비교</h1><p>상태: {html.escape(report['status'])} · 전체 지도 아님 · 사용자 미감 미승인</p>
<p>출처: 국토교통부 / VWorld · AI 재해석 · 로컬 검수용, 공개 배포하지 않음</p>
<p>지도와 화풍 참고만 OpenRouter/OpenAI로 전송. Qwen 출력과 앱 시안은 전송하지 않음.</p>
<div class="cards">{cards}</div>{overlay}<p><a href="report.json">시간·비용·설정·검수 기록</a></p>
<h2>실제 프롬프트</h2><pre>{html.escape(report['prompt'])}</pre></html>''')


def pilot(allow_external=False):
    if not allow_external:
        raise ValueError("External upload requires --allow-external")
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise ValueError("OPENROUTER_API_KEY is not set")
    cfg = qs.configuration("q8")
    source, crop, style = qs.inputs(cfg)
    baseline = qs.read(BASELINE / "report.json")
    candidate = baseline["candidates"][0]
    baseline_image = BASELINE / candidate["raw"]
    if qs.sha(baseline_image) != candidate["raw_sha256"]:
        raise ValueError("Baseline changed")
    if any(baseline["config"][k] != cfg[k] for k in ("source_sha256", "style_sha256", "crop", "prompt")):
        raise ValueError("Baseline input/config mismatch")
    capability = validate_capabilities(request_json(f"/images/models/{MODEL}/endpoints", key))
    folder = ROOT / "runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder.mkdir(parents=True, exist_ok=False)
    crop.save(folder / "scene_input.png")
    style.save(folder / "style_input.png")
    crop.resize((1024, 1024), Image.Resampling.LANCZOS).save(folder / "source.png")
    shutil.copyfile(baseline_image, folder / "qwen.png")
    prompt = cfg["prompt"] + "\nAvoid: " + cfg["negative_prompt"]
    payload = {"model": MODEL, "prompt": prompt, "n": 1, "quality": "high", "aspect_ratio": "1:1",
               "provider": {"only": ["openai"], "allow_fallbacks": False},
               "input_references": [reference(crop), reference(style)]}
    report = {"status": "requesting", "model": MODEL, "local_only": False, "prompt": prompt,
              "request_options": {k: v for k, v in payload.items() if k not in ("prompt", "input_references")},
              "provider_capability": capability, "inputs": {"scene_sha256": qs.sha(folder / "scene_input.png"),
              "style_sha256": qs.sha(folder / "style_input.png"), "crop": cfg["crop"]},
              "baseline_raw_sha256": candidate["raw_sha256"], "baseline_wall_seconds": candidate["wall_seconds"],
              "resolution_note": "Endpoint advertises aspect ratio, not exact size; native output retained, 1024px comparison normalized only if needed",
              "visual_review": "not_reviewed", "geometry_review": "not_reviewed", "usage": None}
    def save():
        qs.write(folder / "report.json", report)
        page(folder, report)
    save()
    print(f"OUTPUT={folder}", flush=True)
    started = time.time()
    try:
        result = request_json("/images", key, payload)
        report["request_wall_seconds"] = round(time.time() - started, 3)
        report["usage"] = result.get("usage")
        raw = decode(result)
        raw.save(folder / "api_raw.png")
        report["native_size"] = list(raw.size)
        report["raw_sha256"] = qs.sha(folder / "api_raw.png")
        comparison = raw if raw.size == (1024, 1024) else raw.resize((1024, 1024), Image.Resampling.LANCZOS)
        qs.pixel_grid(comparison).save(folder / "api_grid.png")
        report["status"] = "awaiting_visual_review"
        save()
        print(json.dumps({"seconds": report["request_wall_seconds"], "usage": report["usage"], "size": raw.size}), flush=True)
        return folder
    except (Exception, KeyboardInterrupt) as exc:
        report["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        report["error"] = {"type": type(exc).__name__, "message": "Request/output failed; no retry; verify billing before rerunning"}
        report["request_wall_seconds"] = round(time.time() - started, 3)
        save()
        raise RuntimeError(report["error"]["message"]) from None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-external", action="store_true")
    parser.add_argument("--mode", choices=("single", "seam-zoom"), default="single")
    args = parser.parse_args()
    if args.mode == "seam-zoom":
        from seam_zoom import run
        run(args.allow_external)
    else:
        pilot(args.allow_external)
