"""Four-request, single-camera seam/zoom experiment. Never edits the existing map."""
import html
import math
import os
import time
from datetime import datetime, timezone

import numpy as np
from PIL import Image
import openrouter_style as api

qs = api.qs
ROOT = api.ROOT / "seam_zoom/runs"
CROPS = [(96, 160, 864, 928), (672, 160, 1440, 928),
         (96, 736, 864, 1504), (672, 736, 1440, 1504)]
ATTRIBUTION = "국토교통부 / VWorld · AI 재해석 · 로컬 검수용 · 실제 좌표 정합 미검증"


def assemble(images):
    if len(images) != 4 or any(im.size != (1024, 1024) for im in images):
        raise ValueError("Exactly four native 1024px images required")
    out = Image.new("RGB", (1536, 1536))
    for i, im in enumerate(images):
        out.paste(im.crop((128, 128, 896, 896)), ((i % 2) * 768, (i // 2) * 768))
    return out


def pyramid(image, folder):
    """Downsample the whole mosaic before cutting display tiles (not each AI crop)."""
    top = math.ceil(math.log2(max(image.size) / 256))
    for z in range(top + 1):
        factor = 2 ** (top - z)
        level = image if factor == 1 else image.resize(
            (math.ceil(image.width / factor), math.ceil(image.height / factor)), Image.Resampling.BOX)
        for y in range(math.ceil(level.height / 256)):
            for x in range(math.ceil(level.width / 256)):
                path = folder / str(z) / str(x) / f"{y}.png"
                path.parent.mkdir(parents=True, exist_ok=True)
                level.crop((x * 256, y * 256, min(level.width, (x + 1) * 256),
                            min(level.height, (y + 1) * 256))).save(path)
    return top


def seams(images, folder):
    pairs = []
    for a, b, axis in ((0, 1, "vertical"), (2, 3, "vertical"),
                       (0, 2, "horizontal"), (1, 3, "horizontal")):
        boxes = ((768, 0, 1024, 1024), (0, 0, 256, 1024)) if axis == "vertical" else (
            (0, 768, 1024, 1024), (0, 0, 1024, 256))
        aa, bb = images[a].crop(boxes[0]), images[b].crop(boxes[1])
        name = f"overlap_{a}_{b}"
        aa.save(folder / f"{name}_a.png")
        bb.save(folder / f"{name}_b.png")
        difference = np.abs(np.asarray(aa, dtype=float) - np.asarray(bb, dtype=float))
        pairs.append({"a": a, "b": b, "axis": axis, "preview": name,
                      "mean_abs_rgb": round(float(difference.mean()), 3)})
    return pairs


def publish(folder, source, images, report):
    mosaic = assemble(images)
    mosaic.save(folder / "mosaic.png")
    # Each output core represents 576 source pixels (768 * 3/4).
    source_core = source.crop((192, 256, 1344, 1408)).resize((1536, 1536), Image.Resampling.LANCZOS)
    source_core.save(folder / "source.png")
    mosaic.resize((384, 384), Image.Resampling.BOX).save(folder / "preview.png")
    top = pyramid(mosaic, folder / "tiles")
    pyramid(source_core, folder / "source_tiles")
    report["seams"] = seams(images, folder)
    report["review_targets"] = [
        {"label": "중앙 경계의 지붕·건물", "xy": [768, 768]},
        {"label": "궁궐 담장 연결", "xy": [768, 672]},
        {"label": "동측 도로 연결", "xy": [1320, 768]}]
    manifest = {"version": 1, "run_id": folder.name, "status": "awaiting_user_review",
                "width": 1536, "height": 1536, "tile_size": 256, "max_native_zoom": top,
                "tiles": "tiles", "source_tiles": "source_tiles", "preview": "preview.png",
                "mosaic": "mosaic.png", "source": "source.png", "report": "report.json",
                "attribution": ATTRIBUTION, "review_targets": report["review_targets"],
                "review_summary": "경계·미감 검수 전 · 사용자 품질 승인 대기"}
    qs.write(folder / "manifest.json", manifest)
    return manifest


def report_page(folder, report):
    ready = (folder / "manifest.json").exists()
    link = f"/web/pilot/?run={folder.name}"
    cards = "".join(f'<figure><img src="tile_{i}_raw.png"><figcaption>Tile {i} · 원출력</figcaption></figure>'
                    for i in range(4) if (folder / f"tile_{i}_raw.png").exists())
    review = html.escape(str(report.get('visual_review', 'not_reviewed')))
    geometry = html.escape(str(report.get('geometry_review', 'not_reviewed')))
    overlaps = ''.join(f'<li>Tile {pair["a"]} / {pair["b"]}: '
                       f'<a href="{pair["preview"]}_a.png">겹침 A</a> · '
                       f'<a href="{pair["preview"]}_b.png">겹침 B</a> '
                       f'· 평균 RGB 차이 {pair["mean_abs_rgb"]}</li>' for pair in report.get('seams', []))
    (folder / "index.html").write_text(f'''<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>2×2 시험 기록</title>
<style>body{{font:16px system-ui;background:#FBF3E4;color:#3A2A1E;margin:24px}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr))}}img{{width:100%;image-rendering:pixelated}}figure{{margin:12px}}pre{{white-space:pre-wrap}}</style>
<h1>덕수궁·시청 2×2 시험</h1><p>{html.escape(report['status'])} · {ATTRIBUTION}</p>
{'<p><a href="'+link+'">반응형 지도 GUI 열기</a> · <a href="mosaic.png">합성 원본</a></p>' if ready else '<p>미완료: 이전 지도나 대체 이미지를 표시하지 않습니다.</p>'}
<p><a href="report.json">비용·시간·검수 JSON</a></p>
<h2>검수 결과</h2><p>{review}</p><p>{geometry}</p>
<p>생성비: {report.get('total_cost_usd', '집계 대기')} USD · 요청 시간: {report.get('total_request_seconds', '집계 대기')}초</p>
<h2>겹침 비교</h2><p>RGB 차이는 참고 지표이며 건물 연결 합격 판정이 아닙니다.</p><ul>{overlaps}</ul><main>{cards}</main>
<h2>실제 공통 프롬프트</h2><pre>{html.escape(report['prompt'])}</pre></html>''', encoding="utf-8")


def run(allow_external=False):
    if not allow_external:
        raise ValueError("External upload requires --allow-external")
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise ValueError("OPENROUTER_API_KEY is not set")
    cfg = qs.configuration("q8")
    source, _, style = qs.inputs(cfg)
    if source.size != (1536, 1536):
        raise ValueError("Expected fixed 1536px source capture")
    capability = api.validate_capabilities(api.request_json(f"/images/models/{api.MODEL}/endpoints", key))
    folder = ROOT / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder.mkdir(parents=True, exist_ok=False)
    style.save(folder / "style_input.png")
    prompt = cfg["prompt"] + "\nAvoid: " + cfg["negative_prompt"]
    options = {"model": api.MODEL, "n": 1, "quality": "high", "aspect_ratio": "1:1",
               "provider": {"only": ["openai"], "allow_fallbacks": False}}
    report = {"status": "prepared", "run_id": folder.name, "request_limit": 4, "requests_started": 0,
              "prompt": prompt, "request_options": options, "provider_capability": capability,
              "source_sha256": cfg["source_sha256"], "style_sha256": cfg["style_sha256"],
              "crops": CROPS, "local_only": False, "tiles": [], "visual_review": "not_reviewed",
              "geometry_review": "not_reviewed", "note": "Single perspective capture; no full-map registration. Hard core cuts; no seam repair."}
    def save():
        qs.write(folder / "report.json", report)
        report_page(folder, report)
    save()
    print(f"OUTPUT={folder}", flush=True)
    images = []
    try:
        for i, crop in enumerate(CROPS):
            scene = source.crop(crop)
            path = folder / f"tile_{i}_input.png"
            scene.save(path)
            entry = {"id": i, "crop": crop, "input_sha256": qs.sha(path), "status": "requesting"}
            report["tiles"].append(entry)
            report["requests_started"] += 1
            report["status"] = "requesting"
            save()  # Persist intent before crossing the billing boundary.
            started = time.monotonic()
            result = api.request_json("/images", key, {**options, "prompt": prompt,
                                      "input_references": [api.reference(scene), api.reference(style)]})
            entry.update(seconds=round(time.monotonic() - started, 3), usage=result.get("usage"))
            save()
            raw = api.decode(result)
            raw.save(folder / f"tile_{i}_raw.png")
            entry.update(native_size=list(raw.size), raw_sha256=qs.sha(folder / f"tile_{i}_raw.png"))
            if raw.size != (1024, 1024):
                raise ValueError("Native output size differs; retained output, no resizing or retry")
            entry["status"] = "complete"
            images.append(raw)
            save()
            print(f"TILE={i} complete seconds={entry['seconds']} usage={entry['usage']}", flush=True)
        publish(folder, source, images, report)
        report["status"] = "awaiting_user_review"
        costs = [(tile.get("usage") or {}).get("cost") for tile in report["tiles"]]
        report["total_cost_usd"] = sum(costs) if all(isinstance(c, (int, float)) for c in costs) else None
        report["total_request_seconds"] = round(sum(t["seconds"] for t in report["tiles"]), 3)
        save()
        # Pointer is local-only and never selects a partial run.
        qs.write(api.ROOT / "seam_zoom/current.json", {"run_id": folder.name})
        print(f"GUI=http://127.0.0.1:8766/web/pilot/?run={folder.name}", flush=True)
        return folder
    except (Exception, KeyboardInterrupt) as exc:
        report["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        report["error"] = {"type": type(exc).__name__, "message": "Stopped without retry; inspect outputs and verify billing before another run."}
        save()
        raise RuntimeError(report["error"]["message"]) from None
