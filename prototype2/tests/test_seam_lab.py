import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import seam_lab as lab


class SeamLabTest(unittest.TestCase):
    def test_context_preserves_all_previous_pixels(self):
        canvas = Image.new('RGB', (1792, 1792)); known = Image.new('L', canvas.size)
        colors = ['red', 'blue', 'green', 'yellow']
        for i, color in enumerate(colors):
            before = canvas.copy(); old = known.copy()
            lab.commit_tile(canvas, known, Image.new('RGB', (1024, 1024), color), i)
            self.assertEqual(Image.composite(canvas, before, old).tobytes(), before.tobytes())
        self.assertEqual(canvas.getpixel((1000, 1000)), (255, 0, 0))
        self.assertEqual(canvas.getpixel((1024, 1000)), (0, 0, 255))
        self.assertEqual(known.getextrema(), (255, 255))

    def test_context_coordinates(self):
        canvas = Image.new('RGB', (1792, 1792)); known = Image.new('L', canvas.size)
        lab.commit_tile(canvas, known, Image.new('RGB', (1024, 1024), 'red'), 0)
        _, mixed, mask = lab.context_tile(Image.new('RGB', (1536, 1536), 'blue'), canvas, known, 1)
        self.assertEqual(mask.getpixel((255, 100)), 255)
        self.assertEqual(mask.getpixel((256, 100)), 0)
        self.assertEqual(mixed.getpixel((255, 100)), (255, 0, 0))
        self.assertEqual(mixed.getpixel((256, 100)), (0, 0, 255))

    def test_budget_and_same_name_block_before_request(self):
        for entries in ([{'group': 'character', 'name': 'old', 'status': 'complete'}],
                        [{'group': 'downtown', 'name': 'new', 'status': 'complete'}],
                        [{'group': 'downtown', 'name': 'old', 'status': 'failed'}]):
            with tempfile.TemporaryDirectory() as tmp, patch.object(lab.api, 'request_json') as call:
                with self.assertRaises(ValueError):
                    lab.paid(Path(tmp), {'requests': entries}, 'secret', 'character', 'new', 'test', [])
                call.assert_not_called()

    def test_paid_intent_failure_no_retry_or_secret(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(lab.api, 'request_json', side_effect=RuntimeError('secret')) as call:
            folder = Path(tmp); report = {'requests': []}
            with self.assertRaisesRegex(RuntimeError, 'No retry'):
                lab.paid(folder, report, 'secret', 'downtown', 'a', 'test', [])
            self.assertEqual(call.call_count, 1)
            self.assertEqual(report['requests'][0]['status'], 'failed')
            self.assertNotIn('secret', (folder / 'report.json').read_text())

    def test_native_size_failure_retains_output(self):
        encoded = lab.api.reference(Image.new('RGB', (512, 512)))['image_url']['url'].split(',')[1]
        with tempfile.TemporaryDirectory() as tmp, patch.object(lab.api, 'request_json', return_value={'usage': {'cost': .01}, 'data': [{'b64_json': encoded}]}):
            folder = Path(tmp); report = {'requests': []}
            with self.assertRaises(RuntimeError):
                lab.paid(folder, report, 'key', 'downtown', 'a', 'test', [])
            self.assertTrue((folder / 'a_raw.png').is_file())
            self.assertEqual(report['total_cost_usd'], .01)

    def test_failure_records_safe_diagnostics_without_retry(self):
        failure = lab.api.RequestFailure('secret response body', http_status=503,
                                         generation_id='gen-123-example')
        with tempfile.TemporaryDirectory() as tmp, patch.object(lab.api, 'request_json', side_effect=failure) as call:
            folder = Path(tmp); report = {'requests': []}
            with self.assertRaises(RuntimeError):
                lab.paid(folder, report, 'secret', 'downtown', 'a', 'test', [])
            entry = report['requests'][0]
            self.assertEqual(entry['error']['http_status'], 503)
            self.assertEqual(entry['generation_id'], 'gen-123-example')
            self.assertIsNone(report['total_cost_usd'])
            self.assertNotIn('secret', (folder / 'report.json').read_text())
            with self.assertRaises(ValueError):
                lab.paid(folder, report, 'secret', 'downtown', 'b', 'test', [])
            self.assertEqual(call.call_count, 1)

    def test_generation_id_rejects_arbitrary_content(self):
        for value in (None, {}, 'https://example.com/secret', 'gen-123\nsecret', 'gen-' + 'a' * 161):
            self.assertIsNone(lab.api.safe_generation_id(value))
        self.assertEqual(lab.api.safe_generation_id('gen-123-abc'), 'gen-123-abc')

    def test_reserved_historical_failure_does_not_exempt_new_failure(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(lab.api, 'request_json', side_effect=RuntimeError('offline')) as call:
            report = {'requests': [{'group': 'downtown', 'name': 'old', 'status': 'failed'}]}
            with self.assertRaises(RuntimeError):
                lab.paid(Path(tmp), report, 'key', 'downtown', 'new', 'test', [], reserved_failures={'old': .75})
            with self.assertRaises(ValueError):
                lab.paid(Path(tmp), report, 'key', 'downtown', 'next', 'test', [], reserved_failures={'old': .75})
            self.assertEqual(call.call_count, 1)
            self.assertIsNone(report['total_cost_usd'])

    def test_true_alpha_survives_response(self):
        im = Image.new('RGBA', (1024, 1024), (0, 0, 0, 0)); im.paste((240, 80, 30, 255), (400, 300, 600, 700))
        encoded = lab.api.reference(im)['image_url']['url'].split(',')[1]
        with tempfile.TemporaryDirectory() as tmp, patch.object(lab.api, 'request_json', return_value={'usage': {'cost': .01}, 'data': [{'b64_json': encoded}]}):
            result = lab.paid(Path(tmp), {'requests': []}, 'key', 'character', 'test', 'prompt', [], True)
            self.assertEqual(result.mode, 'RGBA')
            self.assertEqual(result.getchannel('A').getextrema(), (0, 255))

    def test_config_repair_boxes_are_bounded(self):
        cfg = lab.api.qs.read(lab.CONFIG)
        for specs in cfg['repairs'].values():
            for spec in specs:
                x, y, r, b = spec['context_box']; a, c, d, e = spec['edit_box']
                self.assertEqual((r-x, b-y), (1024, 1024))
                self.assertTrue(0 <= x <= a < d <= r <= 1536)
                self.assertTrue(0 <= y <= c < e <= b <= 1536)


if __name__ == '__main__':
    unittest.main()
