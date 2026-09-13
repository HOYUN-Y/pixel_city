"""S1/S2 판정 도구 — 원본 edge를 결과 위에 얹어 "구조가 살아 있는가"를 눈과 숫자로 본다.

결과 이미지마다 두 가지를 낸다.

  eval/ov_<이름>.png   원본 라인아트를 빨강 반투명으로 중첩. 도로가 끊겼는지 바로 보인다.
  retention            원본 선 위에 결과에서도 경계가 잡히는 비율 (0~1)

retention은 순위를 매기는 보조 숫자다. 최종 판정은 사람이 한다.

    prototype2/.venv/bin/python prototype2/scripts/overlay.py
"""
import argparse, glob, json, os

import numpy as np
from PIL import Image, ImageFilter

P2 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CTL = os.path.join(P2, "inputs", "conditions", "edge.png")
EVAL = os.path.join(P2, "eval")
TOL = 2          # 선이 몇 px 밀리는 건 봐준다. 픽셀아트 스냅만으로도 이 정도는 움직인다
THRESH = 40      # 결과에서 "경계"로 칠 밝기 차


def edges_of(img):
    """결과 이미지의 경계 마스크. FIND_EDGES + 임계값이면 충분하다 (opencv 안 쓴다)."""
    e = img.convert("L").filter(ImageFilter.FIND_EDGES)
    return e.point(lambda v: 255 if v >= THRESH else 0)


def metrics(ctl, img):
    src = ctl.convert("L").point(lambda v: 255 if v >= 128 else 0)
    raw = edges_of(img)
    got_wide = raw.filter(ImageFilter.MaxFilter(TOL * 2 + 1))
    src_wide = src.filter(ImageFilter.MaxFilter(TOL * 2 + 1))
    s = np.asarray(src, dtype=np.uint8) > 0
    g = np.asarray(raw, dtype=np.uint8) > 0
    gw = np.asarray(got_wide, dtype=np.uint8) > 0
    sw = np.asarray(src_wide, dtype=np.uint8) > 0
    recall = float((s & gw).sum() / s.sum()) if s.any() else 0.0
    precision = float((g & sw).sum() / g.sum()) if g.any() else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"recall": recall, "precision": precision, "f1": f1,
            "edge_density_ratio": float(g.sum() / s.sum()) if s.any() else 0.0,
            "source_edge_pixels": int(s.sum()), "result_edge_pixels": int(g.sum())}


def retention(ctl, img):
    """이전 보고서 호환용. 신규 판정에는 metrics의 precision/F1도 함께 본다."""
    return metrics(ctl, img)["recall"]


def main(pattern, control=CTL, report=None):
    ctl = Image.open(control).convert("L")
    red = Image.new("RGB", ctl.size, (255, 40, 40))
    os.makedirs(EVAL, exist_ok=True)
    rows = []
    for p in sorted(glob.glob(pattern)):
        img = Image.open(p).convert("RGB").resize(ctl.size, Image.LANCZOS)
        out = os.path.join(EVAL, "ov_" + os.path.basename(p))
        Image.composite(red, img, ctl.point(lambda v: int(v * 0.7))).save(out)
        rows.append((metrics(ctl, img), os.path.basename(p)))
    rows.sort(key=lambda x: x[0]["f1"], reverse=True)
    for m, n in rows:
        print(f"  F1 {m['f1']:.3f}  recall {m['recall']:.3f}  precision {m['precision']:.3f}"
              f"  density {m['edge_density_ratio']:.2f}  {n}")
    if rows:
        print(f"오버레이 {len(rows)}장 -> {os.path.relpath(EVAL, P2)}/ov_*.png")
    else:
        print("결과 이미지가 없다. 먼저 s1_edit.py를 돌린다.")
    if report:
        os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
        with open(report, "w", encoding="utf-8") as f:
            json.dump({"control": os.path.abspath(control),
                       "results": [{"name": n, **{k: round(v, 6) for k, v in m.items()}}
                                   for m, n in rows]},
                      f, ensure_ascii=False, indent=2)
    return rows


def selfcheck(control=CTL):
    ctl = Image.open(control).convert("L")
    own = metrics(ctl, ctl.convert("RGB"))
    blank = metrics(ctl, Image.new("RGB", ctl.size, (30, 30, 30)))
    assert own["recall"] > 0.5 and own["precision"] > 0.5, "자기 자신은 대부분 유지돼야 한다"
    assert blank["recall"] < 0.05, "민무늬는 0에 가까워야"
    print("selfcheck ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", default=os.path.join(P2, "outputs", "candidates", "*.png"))
    ap.add_argument("--control", default=CTL, help="결과와 같은 구간의 edge.png")
    ap.add_argument("--report", help="retention 결과 JSON 경로")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    selfcheck(a.control)
    if not a.check:
        main(a.glob, a.control, a.report)
