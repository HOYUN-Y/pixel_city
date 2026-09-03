"""S1 — 단일 컷 판정. base_rgb를 edge로 잡아둔 채 픽셀아트로 다시 그린다.

conditions.py가 만든 두 장을 쓴다.
  inputs/source/base_rgb.png     img2img 초기 이미지 (구도·색·건물 위치를 붙잡는다)
  inputs/conditions/edge.png     ControlNet 조건 (흑백 라인아트 = canny 입력 그대로)

강도 3단계 × seed 3개 = 9장을 outputs/candidates/에 쓰고, 설정을 같은 이름 .json에 남긴다.
마지막에 기준선 + 9장을 한 장으로 붙인 contact sheet를 eval/에 만든다.

**판정 질문은 하나다: 도로가 살아 있으면서 디테일이 늘었는가.**

    python prototype2/scripts/s1_edit.py --check     # 모델 없이 입력·설정만 검사
    python prototype2/scripts/s1_edit.py             # 9장 생성 (첫 실행은 ~10GB 내려받음)
"""
import argparse, json, os, sys, time

P2 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(P2, "configs", "s1.json")
IN = os.path.join(P2, "inputs")          # --inputs 로 갈아끼운다 (구간을 바꿔 볼 때)
SRC = CTL = None                         # set_paths()가 채운다
OUT = os.path.join(P2, "outputs", "candidates")
EVAL = os.path.join(P2, "eval")
TAG = ""                                 # 결과 파일명 접두. 구간이 다르면 섞이면 안 된다


def set_paths(indir, tag):
    global SRC, CTL, TAG
    SRC = os.path.join(indir, "source", "base_rgb.png")
    CTL = os.path.join(indir, "conditions", "edge.png")
    TAG = tag


def grid(cfg):
    return [(s, sd) for s in cfg["strengths"] for sd in cfg["seeds"]]


def contact(cfg, base, paths, combos, cols=3, cell=340):
    """기준선 1장 + 실제로 만든 결과. 행=강도, 열=seed. 눈으로 한 번에 비교하려고 만든다."""
    from PIL import Image, ImageDraw
    cols = min(cols, len(cfg["seeds"]))
    rows = -(-len(paths) // cols)                  # --limit로 줄여 돌려도 깨지지 않게
    W, H, pad = cols * cell, (rows + 1) * cell, 18
    sheet = Image.new("RGB", (W + pad * 2, H + pad * (rows + 2) + 20), (24, 24, 28))
    dr = ImageDraw.Draw(sheet)
    sheet.paste(base.resize((cell, cell), Image.LANCZOS), (pad, pad))
    dr.text((pad + 4, pad + cell + 2), "base_rgb (기준선)", fill=(200, 200, 200))
    for i, (st, sd) in enumerate(combos):
        r, c = i // cols, i % cols
        y = pad + (r + 1) * (cell + pad) + 20
        sheet.paste(Image.open(paths[i]).resize((cell, cell), Image.LANCZOS),
                    (pad + c * cell, y))
        dr.text((pad + c * cell + 4, y + cell + 2), f"strength {st}  seed {sd}",
                fill=(200, 200, 200))
    os.makedirs(EVAL, exist_ok=True)
    p = os.path.join(EVAL, f"contact_s1{TAG}.png")
    sheet.save(p)
    return p


def selfcheck(cfg):
    from PIL import Image
    for p in (SRC, CTL):
        assert os.path.exists(p), f"먼저 conditions.py를 돌린다: {p} 없음"
    a, b = Image.open(SRC), Image.open(CTL)
    assert a.size == b.size, (a.size, b.size)
    assert a.size[0] % 8 == 0, "SDXL은 8의 배수 해상도를 요구한다"
    assert len(grid(cfg)) == len(cfg["strengths"]) * len(cfg["seeds"])
    assert all(0.0 < s < 1.0 for s in cfg["strengths"]), "strength는 0~1"
    assert "text" in cfg["negative"], "텍스트·워터마크 금지가 빠졌다"
    print(f"selfcheck ok — {a.size[0]}² {len(grid(cfg))}장 예정")


def main(cfg, limit, mode):
    import torch
    from PIL import Image
    from diffusers import (StableDiffusionXLControlNetImg2ImgPipeline,
                            StableDiffusionXLControlNetPipeline, ControlNetModel)

    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    cn = ControlNetModel.from_pretrained(cfg["controlnet"], torch_dtype=torch.float16)
    # img2img: 기존 렌더를 초기 latent로 → 색·면을 붙잡지만 그만큼 못 벗어난다
    # txt2img: 라인아트로 구조만 잡고 색·질감은 처음부터 그린다
    Pipe = (StableDiffusionXLControlNetImg2ImgPipeline if mode == "img2img"
            else StableDiffusionXLControlNetPipeline)
    pipe = Pipe.from_pretrained(cfg["base"], controlnet=cn,
                                torch_dtype=torch.float16, variant="fp16").to(dev)
    pipe.set_progress_bar_config(disable=True)

    base, ctl = Image.open(SRC).convert("RGB"), Image.open(CTL).convert("RGB")
    os.makedirs(OUT, exist_ok=True)
    paths, combos = [], grid(cfg)[:limit]
    for i, (st, sd) in enumerate(combos, 1):
        t = time.time()
        kw = (dict(image=base, control_image=ctl, strength=st)
              if mode == "img2img" else
              dict(image=ctl, controlnet_conditioning_scale=st))  # txt2img는 st가 조건 강도
        if mode == "img2img":
            kw["controlnet_conditioning_scale"] = cfg["control_scale"]
        img = pipe(prompt=cfg["prompt"], negative_prompt=cfg["negative"],
                   num_inference_steps=cfg["steps"], guidance_scale=cfg["guidance"],
                   generator=torch.Generator(dev).manual_seed(sd), **kw).images[0]
        name = f"s1{TAG}_st{int(st*100):03d}_seed{sd}"
        p = os.path.join(OUT, name + ".png")
        img.save(p)
        # 설정을 결과 옆에 남긴다. 어느 장이 어떤 설정이었는지 나중에 못 찾으면 판정이 무의미하다.
        json.dump({**cfg, "strength": st, "seed": sd, "device": dev,
                   "sec": round(time.time() - t, 1)},
                  open(os.path.join(OUT, name + ".json"), "w"),
                  ensure_ascii=False, indent=1)
        paths.append(p)
        print(f"  [{i}/{len(combos)}] {name}  {time.time()-t:.0f}s")
    print("contact sheet:", os.path.relpath(contact(cfg, base, paths, combos), P2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=CFG)
    ap.add_argument("--limit", type=int, default=99, help="먼저 N장만 (속도 확인용)")
    ap.add_argument("--inputs", default=IN, help="conditions.py --out 로 만든 디렉터리")
    ap.add_argument("--tag", default="", help="결과 파일명 접두 (구간 구분)")
    ap.add_argument("--strengths", help="쉼표로. 설정 파일 값을 덮어쓴다")
    ap.add_argument("--mode", default="img2img", choices=["img2img", "txt2img"])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    set_paths(a.inputs, a.tag)
    cfg = json.load(open(a.config, encoding="utf-8"))
    if a.strengths:
        cfg["strengths"] = [float(x) for x in a.strengths.split(",")]
    selfcheck(cfg)
    if not a.check:
        main(cfg, a.limit, a.mode)
