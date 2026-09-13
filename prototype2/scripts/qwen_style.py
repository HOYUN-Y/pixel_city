"""Bounded, offline Qwen style-transfer pilot; no changes to existing maps."""
import hashlib
import html
import importlib.metadata
import json
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

P2 = Path(__file__).resolve().parents[1]
CONFIG = P2 / "configs/qwen.json"
CACHE = P2 / "work/models/huggingface"
ROOT = P2 / "eval/vworld/qwen"
ATTRIBUTION = "SOURCE: Ministry of Land, Infrastructure and Transport / VWorld | LOCAL AI INTERPRETATION"


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def configuration(variant="bf16"):
    if variant not in ("bf16", "q8"):
        raise ValueError("Unknown Qwen variant")
    cfg = read(CONFIG)
    cfg["variant"] = variant
    if variant == "q8":
        cfg["seeds"] = [20260913]
    return cfg


def q8_paths(cfg, download=False):
    from huggingface_hub import hf_hub_download, snapshot_download
    snapshot = Path(snapshot_download(cfg["model"], revision=cfg["revision"],
                                     cache_dir=str(CACHE), local_files_only=True))
    if read(snapshot / "transformer/config.json").get("zero_cond_t") is not True:
        raise ValueError("Qwen 2511 requires zero_cond_t=true")
    spec = cfg["q8"]
    weight = Path(hf_hub_download(spec["model"], spec["file"], revision=spec["revision"],
                                 cache_dir=str(CACHE), local_files_only=not download))
    if weight.stat().st_size != spec["bytes"] or sha(weight) != spec["sha256"]:
        raise ValueError("Q8 weight size/SHA256 mismatch")
    return snapshot, weight


def prepare(variant="bf16"):
    """The only command allowed to download weights. Images are never uploaded."""
    from huggingface_hub import snapshot_download
    cfg = configuration(variant)
    if variant == "q8":
        snapshot, weight = q8_paths(cfg, download=True)
        shared = {str(p.relative_to(snapshot)): p.stat().st_size
                  for p in sorted(snapshot.rglob("*")) if p.is_file()
                  and not (p.parent.name == "transformer" and p.suffix == ".safetensors")}
        manifest = {"variant": variant, "base_revision": cfg["revision"],
                    "quantization": "Q8_0", "weight": cfg["q8"],
                    "shared_files": shared, "active_weight_bytes": sum(shared.values()) + weight.stat().st_size,
                    "note": "Active file set, not total cache or runtime memory; BF16 weights retained"}
        write(CACHE.parent / "qwen_q8_prepared.json", manifest)
        print(json.dumps(manifest), flush=True)
        return manifest
    snapshot = snapshot_download(cfg["model"], revision=cfg["revision"],
                                 cache_dir=str(CACHE), max_workers=4)
    manifest = {"model": cfg["model"], "revision": cfg["revision"],
                "snapshot": str(Path(snapshot).relative_to(P2)),
                "files": {str(p.relative_to(snapshot)): p.stat().st_size
                          for p in sorted(Path(snapshot).rglob("*")) if p.is_file()}}
    write(CACHE.parent / "qwen_prepared.json", manifest)
    print(json.dumps({"model": cfg["model"], "revision": cfg["revision"],
                      "download_bytes": sum(manifest["files"].values())}), flush=True)
    return manifest


def inputs(cfg):
    if cfg["region"] != "downtown":
        raise ValueError("Only the reviewed downtown pilot is supported")
    source_path, style_path = P2 / cfg["source"], P2 / cfg["style_reference"]
    for path, expected in ((source_path, cfg["source_sha256"]), (style_path, cfg["style_sha256"])):
        if not path.is_file():
            raise FileNotFoundError(f"Required local input missing: {path}")
        if sha(path) != expected:
            raise ValueError(f"Input hash changed: {path}; review config before generating")
    source, style = Image.open(source_path).convert("RGB"), Image.open(style_path).convert("RGB")
    x0, y0, x1, y1 = cfg["crop"]
    if not (0 <= x0 < x1 <= source.width and 0 <= y0 < y1 <= source.height):
        raise ValueError("Crop is outside the source")
    if x1 - x0 != y1 - y0:
        raise ValueError("Pilot crop must be square; never stretch the camera view")
    return source, source.crop(cfg["crop"]), style


def pixel_grid(image):
    """Optional 2px grid; no palette limit, median filter or edge painting."""
    if image.size != (1024, 1024):
        raise ValueError("Full candidate must be 1024x1024")
    return image.resize((512, 512), Image.Resampling.BOX).resize(
        (1024, 1024), Image.Resampling.NEAREST)


def grid_exact(image):
    a = np.asarray(image)
    return (a.shape[:2] == (1024, 1024) and
            np.array_equal(a, np.repeat(np.repeat(a[::2, ::2], 2, 0), 2, 1)))


def archived_crop(source, crop, legacy, top=96, bottom=24):
    """Undo the archived RPG's vertical stretch when comparing source coordinates."""
    legacy = legacy.crop((0, 0, source.width, source.height))  # exclude footer
    sx, sy = legacy.width / source.width, legacy.height / (source.height - top - bottom)
    x0, y0, x1, y1 = crop
    box = (x0 * sx, (y0 - top) * sy, x1 * sx, (y1 - top) * sy)
    return legacy.transform((1024, 1024), Image.Transform.EXTENT, box, Image.Resampling.BICUBIC)


def preview(image, path):
    out = Image.new("RGB", (image.width, image.height + 32), "#202832")
    out.paste(image)
    ImageDraw.Draw(out).text((8, image.height + 10), ATTRIBUTION, fill="white")
    out.save(path)


def report_page(folder, report):
    variant_label = "Qwen Q8_0" if report["config"].get("variant") == "q8" else "Qwen BF16"
    entries = [("source.png", "VWorld / same crop"),
               ("legacy.png", "Archived SDXL RPG / unapproved, re-aligned")]
    for item in report["candidates"]:
        entries.extend([(item["raw"], f"{variant_label} / seed {item['seed']} / raw"),
                        (item["grid"], f"{variant_label} / seed {item['seed']} / 2px grid")])
    entries = [(f, label) for f, label in entries if (folder / f).exists()]
    cards = "".join(f'<figure><figcaption>{html.escape(label)}</figcaption><a href="{f}">'
                    f'<img src="{f}" alt="{html.escape(label)}"></a></figure>' for f, label in entries)
    selects = "".join(f'<option value="{item["raw"]}">seed {item["seed"]}</option>'
                      for item in report["candidates"])
    comparison = ""
    if report["candidates"]:
        first = report["candidates"][0]["raw"]
        comparison = f'''<h2>원본 중첩 검수</h2><label>후보 <select id="candidate">{selects}</select></label>
<label>AI 불투명도 <input id="opacity" type="range" min="0" max="100" value="50"></label>
<div class="overlay"><img src="source.png" alt="원본"><img id="ai" src="{first}" alt="AI 중첩"></div>
<script>const ai=document.getElementById('ai');document.getElementById('opacity').oninput=e=>ai.style.opacity=e.target.value/100;
document.getElementById('candidate').onchange=e=>ai.src=e.target.value;</script>'''
    page = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Qwen local city pilot</title><style>body{{background:#f5f2e9;color:#20302a;font:16px system-ui;margin:24px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,360px),1fr));gap:16px}}figure{{margin:0}}img{{max-width:100%;image-rendering:pixelated}}
figcaption{{padding:12px 0}}.overlay{{position:relative;max-width:1024px}}.overlay img{{display:block;width:100%}}#ai{{position:absolute;inset:0;opacity:.5}}
label{{display:inline-block;margin:12px}}pre{{white-space:pre-wrap}}a{{color:#215f50}}</style>
<h1>서울 픽셀 도시 — 로컬 Qwen 시험</h1><p>{variant_label} · 상태: {html.escape(report['status'])} · 전체 지도 아님 · 사용자 미감 승인 전</p>
<p>현재 원근 시점·건물 배치 유지, 외관 재해석. 자동 구조 통과 판정 없음. 기존 SDXL은 새 A/B 추론이 아니라 이전 결과의 좌표 보정 비교입니다.</p>
<p>{ATTRIBUTION} · 원본·참고 이미지는 로컬 검수용이며 공개 배포하지 않습니다.</p>
<div class="cards">{cards}</div>{comparison}<h2>화풍 참고 (장면 구성에는 사용하지 않음)</h2><img src="style_reference.png" alt="사용자 화풍 참고">
<h2>검수 기준</h2><p>지붕·창문·수목의 선명도 / 색 구분 / 건물 누락·추가 / 큰 형태 변형 / 도로·담장 연결을 별도로 확인합니다.</p>
<p><a href="report.json">설정·실행·재현성 기록</a> · <a href="source_attribution.png">원본 출처 표기</a></p>
<details><summary>실제 프롬프트</summary><pre>{html.escape(report['config']['prompt'])}</pre></details></html>'''
    (folder / "index.html").write_text(page)
    thumb = 384
    sheet = Image.new("RGB", (thumb * len(entries), thumb + 70), "#f5f2e9")
    draw = ImageDraw.Draw(sheet)
    for i, (file, label) in enumerate(entries):
        draw.text((i * thumb + 6, 8), label, fill="#20302a")
        sheet.paste(Image.open(folder / file).resize((thumb, thumb), Image.Resampling.NEAREST), (i * thumb, 32))
    draw.text((8, thumb + 46), ATTRIBUTION, fill="#20302a")
    sheet.save(folder / "comparison.png")
    root = ROOT / "q8" if report["config"].get("variant") == "q8" else ROOT
    root.mkdir(parents=True, exist_ok=True)
    relative = folder.relative_to(root).as_posix()
    (root / "index.html").write_text(f'<!doctype html><meta charset="utf-8"><title>Qwen pilot</title>'
                                  f'<a href="{relative}/index.html">최신 Qwen 로컬 시안 · {html.escape(report["status"])}</a>')


def q8_checkpoint(weight, expected):
    """Remove only the verified ComfyUI 2511 marker, never model weights."""
    from gguf import GGUFReader, GGMLQuantizationType
    from diffusers.models.model_loading_utils import load_gguf_checkpoint
    marker_name = "__index_timestep_zero__"
    reader = GGUFReader(str(weight))
    tensors = {t.name: t for t in reader.tensors}
    if len(tensors) != len(reader.tensors):
        raise ValueError("Duplicate GGUF keys")
    marker = tensors.pop(marker_name, None)
    if (marker is None or marker.tensor_type != GGMLQuantizationType.F32
            or list(marker.shape) != [0] or marker.n_elements != 0):
        raise ValueError("Invalid or missing Qwen 2511 marker")
    if set(tensors) != set(expected):
        raise ValueError(f"GGUF key mismatch: missing={sorted(set(expected) - set(tensors))}, "
                         f"unexpected={sorted(set(tensors) - set(expected))}")
    for name, tensor in tensors.items():
        if tuple(tensor.shape[::-1]) != tuple(expected[name].shape):
            raise ValueError(f"GGUF shape mismatch: {name}")
    quantized_names = {name for name, t in tensors.items() if t.tensor_type == GGMLQuantizationType.Q8_0}
    if not quantized_names:
        raise ValueError("Expected Q8_0 weights")
    audit = {"removed_marker": marker_name, "marker_type": "F32", "marker_shape": [0],
             "reason": "ComfyUI 2511 detection; Diffusers uses zero_cond_t=true",
             "validated_weight_count": len(tensors), "q8_weight_count": len(quantized_names),
             "source_file_modified": False}
    del reader, tensors, marker
    checkpoint = load_gguf_checkpoint(str(weight))
    checkpoint.pop(marker_name)
    if any(getattr(checkpoint[name], "quant_type", None) != GGMLQuantizationType.Q8_0
           for name in quantized_names):
        raise RuntimeError("Q8 weights were dequantized during loading")
    return checkpoint, audit


def local_pipeline(cfg):
    # Set before importing HF libraries. A missing model is an error, not a download.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    import torch
    from diffusers import QwenImageEditPlusPipeline
    if not torch.backends.mps.is_available():
        raise RuntimeError("Apple MPS required; no CPU or remote fallback")
    watermark = os.environ.get("PYTORCH_MPS_HIGH_WATERMARK_RATIO")
    if watermark is not None and float(watermark) <= 0:
        raise RuntimeError("Do not disable the MPS memory safety watermark")
    if os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK") == "1":
        raise RuntimeError("CPU fallback must not be enabled")
    extra = {}
    if cfg.get("variant") == "q8":
        from diffusers import QwenImageTransformer2DModel, GGUFQuantizationConfig
        from accelerate import init_empty_weights
        snapshot, weight = q8_paths(cfg)
        # Diffusers' single-file loader warns rather than fails for unexpected keys.
        # Verify the complete key set before allocating real model parameters.
        with init_empty_weights():
            expected = QwenImageTransformer2DModel.from_config(read(snapshot / "transformer/config.json"))
        checkpoint, audit = q8_checkpoint(weight, expected.state_dict())
        del expected
        transformer = QwenImageTransformer2DModel.from_single_file(
            checkpoint, config=str(snapshot), subfolder="transformer",
            quantization_config=GGUFQuantizationConfig(compute_dtype=torch.bfloat16),
            torch_dtype=torch.bfloat16, local_files_only=True)
        if transformer.config.zero_cond_t is not True or not getattr(transformer, "is_quantized", False):
            raise RuntimeError("Expected quantized Qwen 2511 transformer; no BF16 fallback")
        if any(p.is_meta for p in transformer.parameters()):
            raise RuntimeError("Q8 transformer has unloaded parameters")
        del checkpoint
        extra["transformer"] = transformer
    pipe = QwenImageEditPlusPipeline.from_pretrained(
        cfg["model"], revision=cfg["revision"], cache_dir=str(CACHE),
        local_files_only=True, torch_dtype=torch.bfloat16, **extra)
    pipe.vae.enable_tiling()
    pipe.to("mps")
    if cfg.get("variant") == "q8":
        from gguf import GGMLQuantizationType
        retained = sum(getattr(p, "quant_type", None) == GGMLQuantizationType.Q8_0
                       for p in pipe.transformer.parameters())
        if retained != audit["q8_weight_count"]:
            raise RuntimeError("Q8 weight count changed after MPS transfer")
        pipe.q8_audit = {**audit, "q8_weights_on_mps": retained}
    return torch, pipe


def infer(torch, pipe, cfg, crop, style, size, steps, seed, progress_path=None):
    started = time.monotonic()
    wall_started = time.time()
    step_times = []
    peaks = {"mps_allocated_bytes": 0, "mps_driver_bytes": 0}

    def sample():
        peaks["mps_allocated_bytes"] = max(peaks["mps_allocated_bytes"], torch.mps.current_allocated_memory())
        peaks["mps_driver_bytes"] = max(peaks["mps_driver_bytes"], torch.mps.driver_allocated_memory())

    def progress(pipeline, step, timestep, kwargs):
        sample()
        step_times.append({"step": step + 1, "elapsed_seconds": round(time.monotonic() - started, 3),
                           "wall_elapsed_seconds": round(time.time() - wall_started, 3)})
        if progress_path is not None:
            write(progress_path, {"size": size, "steps": steps, "seed": seed, "step_times": step_times,
                                  "sampled_peak_memory": peaks,
                                  "updated_at": datetime.now(timezone.utc).isoformat()})
        print(f"seed={seed} size={size} step={step + 1}/{steps} elapsed={time.monotonic() - started:.1f}s "
              f"wall_elapsed={time.time() - wall_started:.1f}s "
              f"driver_GiB={peaks['mps_driver_bytes'] / 2**30:.1f}", flush=True)
        return kwargs

    sample()
    with torch.inference_mode():
        output = pipe(image=[crop, style], prompt=cfg["prompt"], negative_prompt=cfg["negative_prompt"],
                      width=size, height=size, num_inference_steps=steps,
                      true_cfg_scale=cfg["true_cfg_scale"], guidance_scale=cfg["guidance_scale"],
                      generator=torch.Generator("cpu").manual_seed(seed),
                      callback_on_step_end=progress, output_type="np").images[0]
    torch.mps.synchronize()
    sample()
    if output.shape != (size, size, 3) or not np.isfinite(output).all():
        raise RuntimeError("Invalid shape or non-finite model output")
    image = Image.fromarray((np.clip(output, 0, 1) * 255).round().astype(np.uint8))
    if np.asarray(image).std() < 1:
        raise RuntimeError("Near-uniform model output; inspect numerical compatibility")
    return image, {"seconds": round(time.monotonic() - started, 3), "size": size, "steps": steps,
                   "wall_seconds": round(time.time() - wall_started, 3), "step_times": step_times,
                   "seed": seed, "sampled_peak_memory": peaks,
                   "memory_note": "MPS samples at load, step boundaries and after decode; not system-wide peak RSS"}


def pilot(region="downtown", smoke_only=False, variant="bf16"):
    cfg = configuration(variant)
    if region != cfg["region"]:
        raise ValueError("Only the configured downtown pilot may run")
    source, crop, style = inputs(cfg)  # validate before model loading or output writes
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    root = ROOT / "q8" if variant == "q8" else ROOT
    folder = root / "runs" / stamp
    folder.mkdir(parents=True, exist_ok=False)
    crop.resize((cfg["size"], cfg["size"]), Image.Resampling.LANCZOS).save(folder / "source.png")
    style.save(folder / "style_reference.png")
    source.crop((0, source.height - 24, source.width, source.height)).save(folder / "source_attribution.png")
    legacy = P2 / "eval/vworld/rpg/downtown_rpg_s60.png"
    if legacy.exists():
        archived_crop(source, cfg["crop"], Image.open(legacy).convert("RGB")).save(folder / "legacy.png")
    report = {"status": "loading", "config": cfg, "local_only": True, "device": "mps", "dtype": "bfloat16",
              "input_roles": ["VWorld scene: camera/layout/appearance", "user image: style only"],
              "platform": platform.platform(), "python": platform.python_version(),
              "versions": {p: importlib.metadata.version(p) for p in ("torch", "diffusers", "transformers", "Pillow", "numpy", "huggingface-hub", "accelerate")},
              "legacy_sha256": sha(legacy) if legacy.exists() else None,
              "legacy_transform": {"top_crop": 96, "bottom_crop": 24, "inverse_vertical_stretch": True},
              "candidates": [], "reproducibility": None, "visual_review": "not_reviewed", "geometry_review": "not_reviewed"}

    def save():
        write(folder / "report.json", report)
        report_page(folder, report)

    save()
    print(f"OUTPUT={folder}", flush=True)
    try:
        start = time.monotonic()
        wall_start = time.time()
        torch, pipe = local_pipeline(cfg)
        if variant == "q8":
            report["weights"] = read(CACHE.parent / "qwen_q8_prepared.json")
            report["versions"]["gguf"] = importlib.metadata.version("gguf")
            report["q8_compatibility"] = pipe.q8_audit
        report["load_seconds"] = round(time.monotonic() - start, 3)
        report["load_wall_seconds"] = round(time.time() - wall_start, 3)
        report["recommended_max_memory_bytes"] = torch.mps.recommended_max_memory()
        report["status"] = "smoke_running"
        save()
        smoke, stats = infer(torch, pipe, cfg, crop, style, cfg["smoke_size"], cfg["smoke_steps"], cfg["seeds"][0],
                             progress_path=folder / "smoke_progress.json")
        smoke.save(folder / "smoke.png")
        report["smoke"] = {**stats, "sha256": sha(folder / "smoke.png"), "quality_candidate": False}
        report["status"] = "smoke_passed" if smoke_only else "generating"
        save()
        if smoke_only:
            return folder
        for seed in cfg["seeds"]:
            raw, stats = infer(torch, pipe, cfg, crop, style, cfg["size"], cfg["steps"], seed,
                               progress_path=folder / f"seed_{seed}_progress.json")
            stem = f"seed_{seed}"
            raw.save(folder / f"{stem}_raw.png")
            grid = pixel_grid(raw)
            grid.save(folder / f"{stem}_grid.png")
            preview(raw, folder / f"{stem}_preview.png")
            preview(grid, folder / f"{stem}_grid_preview.png")
            report["candidates"].append({**stats, "raw": f"{stem}_raw.png", "grid": f"{stem}_grid.png",
                                          "raw_sha256": sha(folder / f"{stem}_raw.png"),
                                          "grid_sha256": sha(folder / f"{stem}_grid.png"),
                                          "pixel_grid_exact": grid_exact(grid)})
            save()
        if variant == "q8":
            report["reproducibility"] = {"status": "not_run", "reason": "Approved single-candidate Q8 trial"}
            report["status"] = "awaiting_visual_review"
            save()
            return folder
        report["status"] = "repeat_running"
        save()
        repeat, stats = infer(torch, pipe, cfg, crop, style, cfg["size"], cfg["steps"], cfg["seeds"][0])
        repeat.save(folder / "repeat_raw.png")
        first = Image.open(folder / report["candidates"][0]["raw"])
        difference = np.abs(np.asarray(first).astype(np.int16) - np.asarray(repeat).astype(np.int16))
        report["reproducibility"] = {**stats, "sha256": sha(folder / "repeat_raw.png"),
                                      "file_identical": sha(folder / "repeat_raw.png") == report["candidates"][0]["raw_sha256"],
                                      "pixel_identical": bool(not difference.any()),
                                      "max_channel_difference": int(difference.max()),
                                      "mean_channel_difference": float(difference.mean())}
        report["status"] = "awaiting_visual_review"
        save()
        return folder
    except (Exception, KeyboardInterrupt) as exc:
        report["failed_stage"] = report["status"]
        report["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        save()
        raise
