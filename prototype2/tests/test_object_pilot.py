import base64
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import object_pilot as op


class ObjectPilotTests(unittest.TestCase):
    def test_depth_uses_camera_direction_not_height(self):
        self.assertGreater(op.depth((0, -10, 0)), op.depth((0, 10, 0)))
        self.assertGreater(op.depth((0, 0, 10)), op.depth((0, 0, 0)))

    def test_raster_is_order_independent_for_overlapping_planes(self):
        near = {'points': [(0, 0, 10), (20, 0, 10), (20, 20, 10), (0, 20, 10)], 'color': (255, 0, 0), 'surface': 1}
        far = {'points': [(0, 0, 0), (20, 0, 0), (20, 20, 0), (0, 20, 0)], 'color': (0, 0, 255), 'surface': 1}
        cam = op.fit([near, far], 128, 8)
        a, da, _ = op.raster([near, far], cam)
        b, db, _ = op.raster([far, near], cam)
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
        np.testing.assert_array_equal(da, db)
        encoded = np.asarray(op.encode_depth(da)).astype(np.uint32)
        decoded = (encoded[..., 0] << 16) | (encoded[..., 1] << 8) | encoded[..., 2]
        mask = np.isfinite(da)
        self.assertLessEqual(np.max(np.abs(decoded[mask] / op.DEPTH_SCALE - op.DEPTH_OFFSET - da[mask])), .006)
        self.assertTrue((decoded[~mask] == 0).all())

    def test_decode_preserves_alpha_and_rejects_opaque_building(self):
        image = Image.new('RGBA', (512, 512))
        ImageDraw.Draw(image).rectangle((100, 100, 400, 400), fill=(140, 180, 90, 255))
        def response(im):
            stream = io.BytesIO(); im.save(stream, format='PNG')
            return {'data': [{'b64_json': base64.b64encode(stream.getvalue()).decode()}]}
        decoded = op.decode_asset(response(image), True)
        self.assertEqual(decoded.mode, 'RGBA')
        self.assertEqual(decoded.getpixel((0, 0))[3], 0)
        with self.assertRaisesRegex(ValueError, 'transparent'):
            op.decode_asset(response(image.convert('RGB')), True)

    def test_permission_before_input_or_network(self):
        with patch.object(op, 'inputs') as inputs, patch.object(op.api, 'request_json') as request:
            with self.assertRaisesRegex(ValueError, 'allow-external'):
                op.generate()
            with patch.dict(op.os.environ, {'OPENROUTER_API_KEY': ''}):
                with self.assertRaisesRegex(ValueError, 'not set'):
                    op.generate(True)
            inputs.assert_not_called(); request.assert_not_called()

    def mocked_generation(self, folder, fail=False):
        calls = []
        cfg, city, layers, meta = op.inputs()
        style = folder / 'fixture_style.png'
        Image.new('RGB', (32, 32), (90, 140, 170)).save(style)
        cfg['style_reference'] = str(style)
        cfg['style_sha256'] = op.sha(style)
        def request(path, key, payload=None):
            if payload is None:
                return {'endpoints': [{'provider_tag': 'openai', 'supported_parameters': {
                    'quality': {'values': ['high']}, 'aspect_ratio': {'values': ['1:1']},
                    'n': {'min': 1, 'max': 1}, 'input_references': {'max': 16},
                    'background': {'values': ['transparent', 'opaque']}}}]}
            calls.append(payload)
            if fail and len(calls) == 2:
                raise RuntimeError('SECRET-DO-NOT-LOG')
            im = Image.new('RGBA', (512, 512), (0, 0, 0, 0 if payload['background'] == 'transparent' else 255))
            ImageDraw.Draw(im).rectangle((100, 100, 400, 400), fill=(180, 130, 60, 255))
            encoded = op.api.reference(im)['image_url']['url'].split(',')[1]
            return {'data': [{'b64_json': encoded}], 'usage': {'cost': .01}}
        with patch.object(op, 'PREPARED', folder / 'prepared'), patch.object(op, 'RUNS', folder / 'runs'), \
                patch.object(op, 'inputs', return_value=(cfg, city, layers, meta)), \
                patch.object(op.api, 'request_json', side_effect=request), patch.dict(op.os.environ, {'OPENROUTER_API_KEY': 'SECRET-DO-NOT-LOG'}):
            if fail:
                with self.assertRaises(RuntimeError):
                    op.generate(True)
            else:
                op.generate(True)
        run = next((folder / 'runs').iterdir())
        raw = (run / 'report.json').read_text()
        self.assertNotIn('SECRET-DO-NOT-LOG', raw)
        return calls, json.loads(raw)

    def test_exactly_six_distinct_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            calls, report = self.mocked_generation(Path(folder))
        self.assertEqual(len(calls), 6)
        self.assertEqual([len(c['input_references']) for c in calls], [2, 2, 2, 1, 1, 1])
        self.assertEqual(len(set(c['prompt'] for c in calls)), 6)
        for c in calls:
            self.assertEqual(c['provider'], {'only': ['openai'], 'allow_fallbacks': False})
            self.assertEqual(c['n'], 1)
        self.assertEqual(report['status'], 'awaiting_user_review')
        self.assertAlmostEqual(report['total_cost_usd'], .06)

    def test_failure_stops_remaining_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            calls, report = self.mocked_generation(Path(folder), fail=True)
        self.assertEqual(len(calls), 2)
        self.assertEqual(report['status'], 'failed')

    def test_offline_manifest_geometry_and_ground_are_independent(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(op, 'PREPARED', Path(folder) / 'prepare'):
            out = Path(folder) / 'assets'
            with patch.object(op.api, 'request_json') as request:
                manifest = op.build(destination=out)
                request.assert_not_called()
            self.assertEqual(len(manifest['objects']), 18)
            cfg, city, _, meta = op.inputs()
            self.assertEqual(manifest['ai_building_ids'], [4628, 4577, 4485])
            for b in manifest['objects']:
                self.assertEqual(b['height'], city['h'][b['source_index']] / 10)
                self.assertEqual(b['footprint'], op.geo.dec_ring(city['rings'][b['source_index']]))
                with Image.open(out / b['base']) as image:
                    self.assertEqual(image.size, tuple(b['size']))
            for p in meta['golden']:
                u, v = op.geo.proj(p['e'], p['n'], p['h'], 1)
                self.assertAlmostEqual(u, p['u']); self.assertAlmostEqual(v, p['v'])
            ground = np.asarray(Image.open(out / 'ground.png').convert('RGBA'))
            self.assertTrue((ground[..., 3] == 255).all())


if __name__ == '__main__':
    unittest.main()
