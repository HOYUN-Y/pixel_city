"""Tests that do not contact VWorld or run a diffusion model."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import vworld_pipeline as vp


class VWorldPipelineTest(unittest.TestCase):
    def test_missing_key_fails_before_browser_or_output(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(vp, "WORK", Path(tmp)), \
             patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "VWORLD_API_KEY"):
                vp.capture_pilots()
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_ephemeral_page_has_attribution_and_orthographic_probe(self):
        cfg = vp.read(vp.CONFIG)
        html = vp.page("DO-NOT-SAVE", {"id": "x", "lon": 127, "lat": 37.5,
                                       "size": 128, "meters_per_pixel": 1}, cfg)
        self.assertIn("logo:true", html)
        self.assertIn("OrthographicFrustum", html)
        self.assertIn("facility_build", html)
        self.assertNotIn("DO-NOT-SAVE", json.dumps(vp.secret_safe({"ok": True}, "DO-NOT-SAVE")))
        self.assertEqual(vp.redact("request?key=DO-NOT-SAVE", "DO-NOT-SAVE"),
                         "request?key=[REDACTED]")

    def test_registration_recovers_known_translation(self):
        building = np.zeros((96, 96), dtype=bool)
        building[24:72, 30:65] = True
        edge = building ^ np.asarray(Image.fromarray(building).filter(ImageFilter.MinFilter(3)))
        rgb = np.zeros((96, 96, 3), dtype=np.uint8)
        moved = vp._shift(edge, 4, -3)
        rgb[moved] = 255
        _, dx, dy = vp.register(Image.fromarray(rgb), building)
        self.assertTrue(abs(dx + 4) <= 1 and abs(dy - 3) <= 1)

    def test_descriptors_vary_per_object(self):
        rgb = np.zeros((20, 20, 3), np.uint8)
        oid = np.zeros((20, 20), np.int32)
        oid[2:12, 2:8], oid[2:12, 10:18] = 1, 2
        rgb[oid == 1] = [180, 80, 60]
        rgb[oid == 2] = np.indices((20, 20))[1][oid == 2, None] * [10, 4, 2]
        got = vp.descriptors(Image.fromarray(rgb), oid, oid != 0)
        self.assertEqual(len(got), 2)
        self.assertNotEqual(got[0]["facade_signature"], got[1]["facade_signature"])

    def test_reference_fallback_is_deterministic_and_mask_locked(self):
        source = Image.fromarray(np.tile(np.arange(32, dtype=np.uint8)[None, :, None], (32, 1, 3)) * 7)
        base = Image.new("RGB", (32, 32), (120, 110, 100))
        oid = np.zeros((32, 32), np.int32)
        oid[4:16, 4:14], oid[4:20, 18:29] = 1, 2
        a = vp.reference_init(source, base, oid, 9)
        b = vp.reference_init(source, base, oid, 9)
        self.assertEqual(a.tobytes(), b.tobytes())
        self.assertTrue(np.all(np.asarray(a)[oid == 0] == np.asarray(base)[oid == 0]))

    def test_two_pixel_output_and_direct_metrics(self):
        y, x = np.indices((64, 64))
        checker = (((x // 8) + (y // 8)) % 2 * 220).astype(np.uint8)
        raw = np.stack((checker, np.roll(checker, 2, axis=0), np.roll(checker, 3, axis=1)), axis=2)
        source = Image.fromarray(raw)
        result = vp.pixelize(source, 2, 64)
        arr = np.asarray(result)
        self.assertTrue(np.array_equal(arr[0::2, 0::2], arr[1::2, 1::2]))
        metrics = vp.direct_metrics(source, source)
        self.assertEqual(metrics["translation_px"], [0, 0])
        self.assertEqual(metrics["edge_recall"], 1.0)

    def test_rpg_decorations_are_deterministic_transparent_layer(self):
        items = [{"kind": "tree", "x": 10, "y": 12},
                 {"kind": "person", "x": 20, "y": 20},
                 {"kind": "car", "x": 28, "y": 25}]
        a = vp.decoration_layer(40, items)
        b = vp.decoration_layer(40, items)
        self.assertEqual(a.mode, "RGBA")
        self.assertEqual(a.tobytes(), b.tobytes())
        self.assertEqual(a.getpixel((0, 0))[3], 0)
        self.assertGreater(int((np.asarray(a)[..., 3] > 0).sum()), 20)

    def test_clean_vworld_removes_top_and_footer_without_size_change(self):
        im = Image.fromarray(np.repeat(np.arange(20, dtype=np.uint8)[:, None, None], 20 * 3, axis=1).reshape(20, 20, 3))
        cleaned = vp._clean_vworld(im, 3, 2)
        self.assertEqual(cleaned.size, im.size)
        self.assertGreater(np.asarray(cleaned)[0].mean(), np.asarray(im)[0].mean())


if __name__ == "__main__":
    unittest.main()
