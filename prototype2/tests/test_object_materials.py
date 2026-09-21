import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import object_materials as m


def fixture(folder):
    folder.mkdir(parents=True, exist_ok=True)
    assets = []
    for i, name in enumerate(m.JOBS):
        a = np.full((64, 64, 3), (140 + i*10, 130, 100), dtype=np.uint8)
        a[16:48, 16:48] = (30, 70+i*10, 110)
        path = folder / f'{name}_raw.png'
        Image.fromarray(a).save(path)
        assets.append({'name': name, 'raw': path.name, 'sha256': m.op.sha(path), 'status': 'generated'})
    report = {'status': 'awaiting_user_review', 'assets': assets, 'requests_started': 0,
              'snapshot_sha256': m.op.sha(m.op.geo.DATA / 'snapshot.json'),
              'model': 'offline-test-fixture', 'total_cost_usd': 0}
    m.op.write(folder / 'generation.json', report)
    return report


class MaterialTests(unittest.TestCase):
    def test_categories_and_distinct_prompts(self):
        self.assertEqual(m.archetype({'kind': 1, 'height': 60}), 'wood')
        self.assertEqual(m.archetype({'kind': 0, 'height': 29.9}), 'masonry')
        self.assertEqual(m.archetype({'kind': 0, 'height': 30}), 'modern')
        self.assertEqual(len(set(map(m.prompt, m.JOBS))), 6)
        self.assertTrue(all(len(m.prompt(n).encode()) <= 4096 for n in m.JOBS))

    def test_callback_cannot_change_coverage_depth_or_surface(self):
        _, city, _, _ = m.op.inputs()
        cam = m.op.read(m.OLD / 'manifest.json')['camera']
        for oid in (4323, 4485, 4577, 4628):
            faces = m.op.faces(city, oid)
            a, z, s = m.op.raster(faces, cam)
            b, zz, ss = m.op.raster(faces, cam, lambda f,c,x,y: np.full((*x.shape, 3), 123, dtype=np.uint8))
            np.testing.assert_array_equal(np.asarray(a)[..., 3], np.asarray(b)[..., 3])
            np.testing.assert_array_equal(z, zz)
            np.testing.assert_array_equal(s, ss)

    def test_face_mapping_repeats_in_metres_not_face_width(self):
        cam = {'scale': 1, 'cx': 20, 'cy': 40}
        tile = np.zeros((32, 32, 3), dtype=np.uint8)
        tile[:, 8:24] = (100, 150, 200)
        tiles = {'masonry_wall': tile}
        def sample(length, positions):
            face = {'points': [(0,0,0), (length,0,0), (length,0,6), (0,0,6)], 'surface': 2}
            p = np.array([m.op.project((u, 0, 1.5), cam) for u in positions])
            return m.paint_face(face, cam, p[:,0], p[:,1], tiles, 'masonry')
        np.testing.assert_array_equal(sample(6, [1.5, 4.5]), sample(12, [1.5, 10.5]))
        # Seven metres: two 3m bays + 0.5m plain margin on each end.
        np.testing.assert_array_equal(sample(7, [.25, 6.75]), np.zeros((2,3)))

    def test_offline_build_preserves_all_geometry_and_original_assets(self):
        original = m.op.sha(m.OLD / 'manifest.json')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); fixture(root / 'run')
            with patch.object(m.op.api, 'request_json') as network:
                result = m.build(root / 'run', root / 'output')
                network.assert_not_called()
            checks = m.op.read(root / 'output/geometry_checks.json')
            self.assertTrue(checks['ground_equal'])
            self.assertEqual(len(checks['buildings']), 18)
            self.assertTrue(all(b['alpha_equal'] and b['depth_equal'] for b in checks['buildings']))
            self.assertTrue(all(not b['has_light'] for b in result['objects']))
            self.assertEqual(result['ground'], result['ground_base'])
            self.assertEqual(result['generation']['requests_started'], 0)
            with self.assertRaisesRegex(ValueError, 'new'):
                m.build(root / 'run', root / 'output')
        self.assertEqual(original, m.op.sha(m.OLD / 'manifest.json'))

    def test_incomplete_or_tampered_input_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); report = fixture(root / 'run')
            report['status'] = 'failed'; m.op.write(root / 'run/generation.json', report)
            with self.assertRaisesRegex(ValueError, 'completed'):
                m.build(root / 'run', root / 'output')
            report['status'] = 'awaiting_user_review'; report['assets'][0]['sha256'] = 'wrong'
            m.op.write(root / 'run/generation.json', report)
            with self.assertRaisesRegex(ValueError, 'Unverified'):
                m.build(root / 'run', root / 'output')
            self.assertFalse((root / 'output').exists())

    def test_permission_key_and_price_guards(self):
        with patch.object(m.op.api, 'request_json') as network:
            with self.assertRaisesRegex(ValueError, 'allow-external'):
                m.generate()
            with patch.dict(m.os.environ, {'OPENROUTER_API_KEY': ''}):
                with self.assertRaisesRegex(ValueError, 'not set'):
                    m.generate(True)
            network.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'Pricing'):
            m.validate_price({'pricing': []})

    def generation(self, folder, failure=None, cost=.05):
        posts = []
        style=folder/'diagnostic-style.png';Image.new('RGB',(64,64),'#556677').save(style)
        cfg={'style_reference':str(style),'style_sha256':m.op.sha(style)}
        def request(path, key, payload=None):
            if payload is None:
                return {'endpoints': [{'provider_tag': 'openai',
                    'pricing': [{'billable': k, 'cost_usd': v} for k,v in m.EXPECTED_PRICES.items()],
                    'supported_parameters': {'quality': {'values': ['high']}, 'aspect_ratio': {'values': ['1:1']},
                        'input_references': {'max': 2}, 'n': {'min': 1, 'max': 1}, 'background': {'values': ['opaque']}}}]}
            posts.append(payload)
            if failure and len(posts) == failure:
                raise RuntimeError('secret-must-not-appear')
            a = np.full((512, 512, 3), 100, dtype=np.uint8); a[100:400,100:400] = (40,90,140)
            encoded = m.op.api.reference(Image.fromarray(a))['image_url']['url'].split(',')[1]
            return {'data': [{'b64_json': encoded}], 'usage': {'cost': cost}}
        with patch.object(m, 'ROOT', folder), patch.object(m.op,'inputs',return_value=(cfg,None,None,None)), patch.object(m.op.api, 'request_json', side_effect=request), \
                patch.dict(m.os.environ, {'OPENROUTER_API_KEY': 'secret-must-not-appear'}):
            if failure or cost is None or cost == .75:
                with self.assertRaises(RuntimeError):
                    m.generate(True)
            else:
                m.generate(True)
            with self.assertRaisesRegex(ValueError, 'already started'):
                m.generate(True)
        raw = (folder / 'generation.json').read_text()
        self.assertNotIn('secret-must-not-appear', raw)
        return posts, json.loads(raw)

    def test_exact_six_calls_and_no_reexecution(self):
        with tempfile.TemporaryDirectory() as temp:
            posts, report = self.generation(Path(temp))
        self.assertEqual(len(posts), 6)
        self.assertEqual(report['total_cost_usd'], .3)
        self.assertEqual(report['status'], 'awaiting_user_review')
        for post in posts:
            self.assertEqual(post['provider'], {'only': ['openai'], 'allow_fallbacks': False})
            self.assertEqual(len(post['input_references']), 1)
            self.assertEqual(post['n'], 1)

    def test_failure_and_unknown_cost_stop(self):
        for failure, cost, count in [(2, .05, 2), (None, None, 1), (None, .75, 2)]:
            with tempfile.TemporaryDirectory() as temp:
                posts, report = self.generation(Path(temp), failure, cost)
            self.assertEqual(len(posts), count)
            self.assertEqual(report['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
