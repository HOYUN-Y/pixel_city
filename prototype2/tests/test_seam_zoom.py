import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import seam_zoom as sz


def fixture_images():
    yy, xx = np.indices((1792, 1792))
    image = Image.fromarray(np.stack(((xx // 8 * 7) % 256, (yy // 8 * 9) % 256,
                                     ((xx + yy) // 16 * 3) % 256), axis=2).astype('uint8'))
    return [image.crop((x, y, x + 1024, y + 1024)) for x, y in ((0, 0), (768, 0), (0, 768), (768, 768))]


CAPABILITY = {"endpoints": [{"provider_tag": "openai", "supported_parameters": {
    "quality": {"values": ["high"]}, "aspect_ratio": {"values": ["1:1"]},
    "input_references": {"max": 16}, "n": {"min": 1, "max": 10}}}]}


class SeamZoomTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.images = fixture_images()

    def test_core_and_overlap(self):
        result = sz.assemble(self.images)
        self.assertEqual(result.size, (1536, 1536))
        for i, image in enumerate(self.images):
            x, y = i % 2 * 768, i // 2 * 768
            self.assertEqual(result.crop((x, y, x + 768, y + 768)).tobytes(), image.crop((128, 128, 896, 896)).tobytes())
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(all(p['mean_abs_rgb'] == 0 for p in sz.seams(self.images, Path(tmp))))
        with self.assertRaises(ValueError):
            sz.assemble(self.images[:3])
        with self.assertRaises(ValueError):
            sz.assemble([Image.new('RGB', (512, 512))] * 4)

    def test_fixed_crops_share_identical_source(self):
        self.assertTrue(all(x1 - x0 == y1 - y0 == 768 for x0, y0, x1, y1 in sz.CROPS))
        self.assertEqual(sz.CROPS[1][0] - sz.CROPS[0][0], 576)
        self.assertEqual(sz.CROPS[2][1] - sz.CROPS[0][1], 576)
        self.assertEqual(sz.CROPS[0][0] + 96, 192)
        self.assertEqual(sz.CROPS[3][2] - 96, 1344)

    def test_pyramid_equals_whole_image_box_downsample(self):
        mosaic = sz.assemble(self.images)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            top = sz.pyramid(mosaic, root)
            self.assertEqual(top, 3)
            for z in range(4):
                size = 1536 // (2 ** (3 - z))
                stitched = Image.new('RGB', (size, size))
                for p in (root / str(z)).glob('*/*.png'):
                    stitched.paste(Image.open(p), (int(p.parent.name) * 256, int(p.stem) * 256))
                expected = mosaic.resize((size, size), Image.Resampling.BOX)
                self.assertEqual(stitched.tobytes(), expected.tobytes())

    def test_permission_and_key_are_checked_before_network(self):
        with patch.object(sz.api, 'request_json') as request:
            with self.assertRaisesRegex(ValueError, 'allow-external'):
                sz.run()
            with patch.dict(sz.os.environ, {'OPENROUTER_API_KEY': ''}):
                with self.assertRaisesRegex(ValueError, 'not set'):
                    sz.run(True)
            request.assert_not_called()

    def mocked_run(self, tmp, fail=None):
        calls = []
        def request(path, key, payload=None):
            if payload is None:
                return CAPABILITY
            calls.append(payload)
            if fail == 'network' and len(calls) == 2:
                raise RuntimeError('NETWORK SECRET SHOULD NOT BE LOGGED')
            image = self.images[len(calls) - 1]
            if fail == 'size' and len(calls) == 2:
                image = image.resize((512, 512))
            return {'data': [{'b64_json': sz.api.reference(image)['image_url']['url'].split(',')[1]}], 'usage': {'cost': .01}}
        cfg = {'prompt': 'layout only', 'negative_prompt': 'no change', 'source_sha256': 'source-hash', 'style_sha256': 'style-hash'}
        with patch.object(sz, 'ROOT', tmp / 'runs'), patch.object(sz.api, 'ROOT', tmp), \
             patch.object(sz.qs, 'configuration', return_value=cfg), \
             patch.object(sz.qs, 'inputs', return_value=(Image.new('RGB', (1536, 1536)), None, self.images[0])), \
             patch.object(sz.api, 'request_json', side_effect=request), \
             patch.dict(sz.os.environ, {'OPENROUTER_API_KEY': 'DO-NOT-PERSIST'}):
            if fail:
                with self.assertRaises(RuntimeError):
                    sz.run(True)
            else:
                sz.run(True)
        folder = next((tmp / 'runs').iterdir())
        report = json.loads((folder / 'report.json').read_text())
        self.assertNotIn('DO-NOT-PERSIST', (folder / 'report.json').read_text())
        self.assertNotIn('NETWORK SECRET', (folder / 'report.json').read_text())
        return calls, folder, report

    def test_only_four_paid_calls_and_no_frontend_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls, folder, report = self.mocked_run(Path(tmp))
            self.assertEqual(len(calls), 4)
            self.assertEqual(report['requests_started'], 4)
            self.assertEqual(report['status'], 'awaiting_user_review')
            self.assertAlmostEqual(report['total_cost_usd'], .04)
            self.assertTrue((folder / 'manifest.json').exists())
            for call in calls:
                self.assertEqual(len(call['input_references']), 2)
                self.assertEqual(call['provider'], {'only': ['openai'], 'allow_fallbacks': False})

    def test_size_mismatch_retained_without_retry_or_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls, folder, report = self.mocked_run(Path(tmp), 'size')
            self.assertEqual(len(calls), 2)
            self.assertEqual(report['status'], 'failed')
            self.assertTrue((folder / 'tile_1_raw.png').exists())
            self.assertFalse((folder / 'manifest.json').exists())
            self.assertFalse((Path(tmp) / 'seam_zoom/current.json').exists())

    def test_network_failure_is_not_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls, folder, report = self.mocked_run(Path(tmp), 'network')
            self.assertEqual(len(calls), 2)
            self.assertEqual(report['status'], 'failed')
            self.assertFalse((folder / 'manifest.json').exists())


if __name__ == '__main__':
    unittest.main()
