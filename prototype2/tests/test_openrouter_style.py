import base64
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import openrouter_style as ors


class OpenRouterStyleTest(unittest.TestCase):
    def test_requires_explicit_upload_permission(self):
        with patch.object(ors, "request_json") as request:
            with self.assertRaisesRegex(ValueError, "allow-external"):
                ors.pilot()
            request.assert_not_called()

    def test_requires_key_without_network(self):
        with patch.dict(ors.os.environ, {"OPENROUTER_API_KEY": ""}), patch.object(ors, "request_json") as request:
            with self.assertRaisesRegex(ValueError, "not set"):
                ors.pilot(True)
            request.assert_not_called()

    def test_endpoint_requires_two_references_and_fixed_provider(self):
        data = {"endpoints": [{"provider_tag": "openai", "supported_parameters": {
            "quality": {"values": ["high"]}, "aspect_ratio": {"values": ["1:1"]},
            "input_references": {"max": 16}, "n": {"min": 1, "max": 10}}}]}
        self.assertEqual(ors.validate_capabilities(data)["provider_tag"], "openai")
        data["endpoints"][0]["supported_parameters"]["input_references"]["max"] = 1
        with self.assertRaisesRegex(ValueError, "Two reference"):
            ors.validate_capabilities(data)

    def test_image_validation_and_reference_roundtrip(self):
        raw = Image.fromarray(np.random.default_rng(1).integers(0, 256, (512, 512, 3), dtype=np.uint8))
        encoded = ors.reference(raw)["image_url"]["url"].split(",", 1)[1]
        result = {"data": [{"b64_json": encoded}]}
        self.assertEqual(ors.decode(result).tobytes(), raw.tobytes())
        with self.assertRaises(ValueError):
            ors.decode({"data": []})
        encoded = ors.reference(Image.new("RGB", (512, 512)))["image_url"]["url"].split(",", 1)[1]
        with self.assertRaisesRegex(ValueError, "Near-uniform"):
            ors.decode({"data": [{"b64_json": encoded}]})

    def test_redirects_are_not_followed(self):
        self.assertIsNone(ors.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.com"))
