"""Frozen projection contract; no prototype1 runtime dependency."""
import json
import math
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "inputs/snapshot"
STYLE = json.loads((DATA / "style.json").read_text())
ALPHA, PHI = map(math.radians, (STYLE["alpha_deg"], STYLE["phi_deg"]))


def proj(e, n, h, s):
    return ((e * math.cos(ALPHA) - n * math.sin(ALPHA)) / s,
            -((e * math.sin(ALPHA) + n * math.cos(ALPHA)) * math.sin(PHI)
              + h * math.cos(PHI)) / s)


def expand(en, k):
    cx, cy = (sum(p[i] for p in en) / len(en) for i in (0, 1))
    return [(cx + (e - cx) * k, cy + (n - cy) * k) for e, n in en]


def dec_ring(a):
    x, y = a[:2]
    result = [(x / 10, y / 10)]
    for dx, dy in zip(a[2::2], a[3::2]):
        x, y = x + dx, y + dy
        result.append((x / 10, y / 10))
    return result
