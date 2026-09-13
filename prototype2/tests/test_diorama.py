"""Behavioral checks for crop invariance, source isolation and review gates."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import diorama_map as dm
import geometry


class DioramaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg, cls.ramps, cls.tex, cls.manifest = dm.setup()

    def test_projection_matches_frozen_golden_points(self):
        meta = json.loads((geometry.DATA / "meta.json").read_text())
        for p in meta["golden"]:
            u, v = geometry.proj(p["e"], p["n"], p["h"], 1.)
            self.assertAlmostEqual(u, p["u"], places=6)
            self.assertAlmostEqual(v, p["v"], places=6)
        self.assertFalse(any(getattr(m, "__file__", None) and
                             "/prototype1/" in m.__file__ for m in list(sys.modules.values())))

    def test_pilot_crop_keeps_world_pattern_alignment(self):
        a, _, _ = dm.render_region(self.cfg, self.ramps, self.tex, self.manifest, 2304, 2304, 256)
        b, _, _ = dm.render_region(self.cfg, self.ramps, self.tex, self.manifest, 2337, 2346, 160)
        expected = np.asarray(a)[42:202, 33:193]
        self.assertLess(float(np.any(expected != np.asarray(b), axis=2).mean()), .005)

    def test_full_generation_waits_for_matching_user_review(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(dm, "EVAL", Path(temp)):
            with self.assertRaisesRegex(RuntimeError, "waits for user review"):
                dm.approved()
            dm.write(Path(temp) / "approval.json", {"approved_by": "user", "signature": {}})
            with self.assertRaisesRegex(RuntimeError, "must match"):
                dm.approved()

    def test_shadow_translation_does_not_wrap_edges(self):
        a = np.zeros((20, 20), bool)
        a[-1, -1] = True
        self.assertFalse(dm.shift(a, 9, 9).any())
        a[:] = False
        a[0, 0] = True
        b = dm.shift(a, 9, 9)
        self.assertEqual(b.sum(), 1)
        self.assertTrue(b[9, 9])

    def test_full_output_pipeline_on_isolated_synthetic_tiles(self):
        # Exercise approval-gated downstream code with synthetic data only.
        # No real-map approval is created and no repository outputs are touched.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            work, data, evidence = root / "work", root / "snapshot", root / "eval"
            (work / "tiles").mkdir(parents=True)
            evidence.mkdir()
            manifest = {"global_camera": {"width": 1536, "height": 768},
                        "grid": {"overlap": 128, "core": 768},
                        "tiles": [{"id": f"t{c}", "row": 0, "col": c} for c in range(2)]}
            dm.write(data / "tile_manifest.json", manifest)
            dm.write(work / "build.json", {"signature": {"test": True}})
            dm.write(root / "web/tiles/manifest.json", {
                "width": 1536, "height": 768, "tile_size": 256, "max_zoom": 3})
            sentinel = root / "web/tiles/baseline-preserved.txt"
            sentinel.write_text("baseline")
            for c in range(2):
                y, x = np.indices((1024, 1024))
                a = np.stack((((x + c * 768 - 128) // 256 % 2) * 100 + 50,
                              ((y - 128) // 256 % 2) * 100 + 50, np.full_like(x, 80)), axis=-1).astype('uint8')
                Image.fromarray(a).save(work / "tiles" / f"t{c}.png")
            with patch.multiple(dm, P2=root, WORK=work, DATA=data, EVAL=evidence), \
                 patch.object(dm, "approved"), patch.object(dm, "signature", return_value={"test": True}):
                dm.assemble()
                dm.pyramid()
            with Image.open(work / "mosaic.png") as mosaic:
                self.assertEqual(mosaic.size, (1536, 768))
                self.assertEqual(mosaic.getpixel((0, 0)), (50, 50, 80))
                self.assertEqual(mosaic.getpixel((768, 0)), (150, 50, 80))
            public = dm.read(root / "web/tiles/manifest.json")
            self.assertEqual(public["default_style"], "diorama")
            self.assertEqual(sentinel.read_text(), "baseline")
            self.assertTrue((root / "web/tiles/diorama/3/5/2.png").exists())


if __name__ == "__main__":
    unittest.main()
