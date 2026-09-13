"""로컬 SDXL로 반복 가능한 픽셀 재질 뱅크를 만든다."""
import argparse
import hashlib
import json
import os
import time

from PIL import Image

P2 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(P2, "configs", "local_style.json")
OUT = os.path.join(P2, "work", "style_bank")


def read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def revision(repo_id):
    try:
        from huggingface_hub import scan_cache_dir
        repo = next(r for r in scan_cache_dir().repos if r.repo_id == repo_id)
        return max(repo.revisions, key=lambda r: r.last_modified).commit_hash
    except Exception:
        return None


def tileable(im, size, colors):
    """중앙부를 축소하고 반전 배치해 네 변이 정확히 이어지는 작은 재질로 만든다."""
    small = im.resize((size, size), Image.Resampling.BOX)
    half = size // 2
    core = small.crop((size // 4, size // 4, size // 4 + half, size // 4 + half))
    out = Image.new("RGB", (size, size))
    out.paste(core, (0, 0))
    out.paste(core.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (half, 0))
    out.paste(core.transpose(Image.Transpose.FLIP_TOP_BOTTOM), (0, half))
    out.paste(core.transpose(Image.Transpose.ROTATE_180), (half, half))
    return out.quantize(colors=colors, method=Image.Quantize.MEDIANCUT).convert("RGB")


def check(cfg):
    assert cfg["size"] % 8 == 0
    assert cfg["texture_size"] % 2 == 0
    assert 2 <= cfg["palette_colors"] <= 256
    assert len(cfg["materials"]) >= 8
    assert cfg["seeds"]
    print(f"local style selfcheck ok — {len(cfg['materials'])}종 × {len(cfg['seeds'])} seeds")


def generate(cfg, out, limit):
    import torch
    from diffusers import StableDiffusionXLPipeline
    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    if device == "cpu":
        raise RuntimeError("로컬 스타일 생성에는 MPS 또는 CUDA가 필요하다")
    dtype = torch.float16
    pipe = StableDiffusionXLPipeline.from_pretrained(
        cfg["model"], torch_dtype=dtype, variant="fp16", local_files_only=True).to(device)
    pipe.set_progress_bar_config(disable=True)
    os.makedirs(os.path.join(out, "raw"), exist_ok=True)
    os.makedirs(os.path.join(out, "textures"), exist_ok=True)
    items, count = [], 0
    for kind, subject in cfg["materials"].items():
        for seed in cfg["seeds"]:
            if count >= limit:
                break
            prompt = f"{subject}, {cfg['common']}"
            started = time.time()
            image = pipe(prompt=prompt, negative_prompt=cfg["negative"],
                         width=cfg["size"], height=cfg["size"],
                         num_inference_steps=cfg["steps"], guidance_scale=cfg["guidance"],
                         generator=torch.Generator(device).manual_seed(seed)).images[0]
            stem = f"{kind}_seed{seed}"
            raw = os.path.join(out, "raw", stem + ".png")
            tex = os.path.join(out, "textures", stem + ".png")
            image.save(raw)
            tileable(image, cfg["texture_size"], cfg["palette_colors"]).save(tex)
            items.append({"kind": kind, "seed": seed, "prompt": prompt,
                          "raw": os.path.relpath(raw, out), "texture": os.path.relpath(tex, out),
                          "seconds": round(time.time() - started, 1), "sha256": digest(tex)})
            count += 1
            print(f"[{count}/{min(limit, len(cfg['materials'])*len(cfg['seeds']))}] {stem} {items[-1]['seconds']}s")
        if count >= limit:
            break
    manifest_path = os.path.join(out, "style_manifest.json")
    previous = read(manifest_path).get("items", []) if os.path.exists(manifest_path) else []
    by_key = {(x["kind"], x["seed"]): x for x in previous}
    by_key.update({(x["kind"], x["seed"]): x for x in items})
    all_items = list(by_key.values())
    selected = {kind: next((x["texture"] for x in all_items
                            if x["kind"] == kind and x["seed"] == cfg["seeds"][0]), None)
                for kind in cfg["materials"]}
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({"model": cfg["model"], "model_revision": revision(cfg["model"]),
                   "config_sha256": digest(CFG), "selected": selected, "items": all_items},
                  f, ensure_ascii=False, indent=2)
    print(manifest_path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("check", "generate"))
    ap.add_argument("--config", default=CFG)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--limit", type=int, default=10**9)
    a = ap.parse_args()
    cfg = read(a.config)
    check(cfg)
    if a.command == "generate":
        generate(cfg, a.out, a.limit)
