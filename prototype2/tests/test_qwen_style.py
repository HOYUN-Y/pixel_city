"""Offline tests: no weight downloads and no model inference."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import qwen_style as qs


class QwenStyleTest(unittest.TestCase):
    def fixture(self, root):
        cfg = qs.read(qs.CONFIG)
        source = Image.fromarray(np.tile(np.arange(64, dtype=np.uint8)[None, :, None], (64, 1, 3)) * 3)
        source.save(root / "source.png")
        source.transpose(Image.Transpose.FLIP_LEFT_RIGHT).save(root / "style.png")
        cfg.update(source="source.png", style_reference="style.png", crop=[8, 8, 40, 40],
                   source_sha256=qs.sha(root / "source.png"), style_sha256=qs.sha(root / "style.png"))
        qs.write(root / "config.json", cfg)
        return cfg

    def test_input_roles_hash_and_crop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = self.fixture(root)
            with patch.object(qs, "P2", root):
                source, crop, style = qs.inputs(cfg)
                self.assertEqual(crop.size, (32, 32))
                self.assertEqual(crop.getpixel((0, 0)), source.getpixel((8, 8)))
                self.assertNotEqual(style.tobytes(), source.tobytes())
                cfg["style_sha256"] = "incorrect"
                with self.assertRaisesRegex(ValueError, "hash changed"):
                    qs.inputs(cfg)

    def test_crop_must_not_stretch_or_exceed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = self.fixture(root)
            with patch.object(qs, "P2", root):
                for crop in ([0, 0, 30, 20], [-1, 0, 31, 32], [0, 0, 80, 80]):
                    cfg["crop"] = crop
                    with self.assertRaises(ValueError):
                        qs.inputs(cfg)

    def test_grid_is_exact_without_palette_limiting(self):
        raw = Image.fromarray(np.random.default_rng(8).integers(0, 256, (1024, 1024, 3), dtype=np.uint8))
        before = raw.tobytes()
        grid = qs.pixel_grid(raw)
        self.assertTrue(qs.grid_exact(grid))
        self.assertGreater(len(grid.getcolors(1024 * 1024)), 48)
        self.assertEqual(raw.tobytes(), before)
        self.assertFalse(qs.grid_exact(raw))

    def test_archive_inverse_transform(self):
        # Original y=40 corresponds to archived y=(40-10)*100/80=37.5.
        source = Image.new("RGB", (100, 100))
        a = np.zeros((100, 100, 3), dtype=np.uint8)
        a[35:41, 20:40] = 255
        legacy = Image.fromarray(a)
        cropped = qs.archived_crop(source, [20, 38, 40, 58], legacy, top=10, bottom=10)
        self.assertGreater(cropped.getpixel((512, 100))[0], 200)
        self.assertEqual(cropped.getpixel((512, 900))[0], 0)

    def test_loader_never_downloads_or_falls_back(self):
        import torch
        from diffusers import QwenImageEditPlusPipeline
        cfg = qs.read(qs.CONFIG)
        with patch.dict(os.environ, {}, clear=False), \
             patch.object(torch.backends.mps, "is_available", return_value=True), \
             patch.object(QwenImageEditPlusPipeline, "from_pretrained") as loader:
            qs.local_pipeline(cfg)
            self.assertTrue(loader.call_args.kwargs["local_files_only"])
            self.assertEqual(loader.call_args.kwargs["revision"], cfg["revision"])
            loader.return_value.to.assert_called_once_with("mps")
            self.assertEqual(os.environ["HF_HUB_OFFLINE"], "1")
        with patch.object(torch.backends.mps, "is_available", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "no CPU or remote fallback"):
                qs.local_pipeline(cfg)

    @staticmethod
    def fake_infer(torch, pipe, cfg, crop, style, size, steps, seed, **kwargs):
        image = Image.fromarray(np.random.default_rng(seed).integers(0, 256, (size, size, 3), dtype=np.uint8))
        return image, {"seed": seed, "steps": steps, "size": size, "seconds": 0.01}

    def test_inference_rejects_nan_and_uniform_output(self):
        torch, pipe = MagicMock(), MagicMock()
        torch.mps.current_allocated_memory.return_value = 1
        torch.mps.driver_allocated_memory.return_value = 2
        cfg = qs.read(qs.CONFIG)
        for value in (float("nan"), 0.0):
            pipe.return_value.images = np.full((1, 512, 512, 3), value, dtype=np.float32)
            with self.assertRaises(RuntimeError):
                qs.infer(torch, pipe, cfg, Image.new("RGB", (32, 32)),
                         Image.new("RGB", (32, 32)), 512, 4, 1)
        self.assertEqual(pipe.call_args.kwargs["num_inference_steps"], 4)
        self.assertEqual(len(pipe.call_args.kwargs["image"]), 2)

    def test_prepare_pins_revision_and_records_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            snapshot = root / "snapshot"
            snapshot.mkdir()
            (snapshot / "model_index.json").write_text("{}")
            with patch.object(qs, "P2", root), patch.object(qs, "CONFIG", root / "config.json"), \
                 patch.object(qs, "CACHE", root / "models/cache"), \
                 patch("huggingface_hub.snapshot_download", return_value=str(snapshot)) as download:
                manifest = qs.prepare()
                self.assertEqual(download.call_args.kwargs["revision"], manifest["revision"])
                self.assertEqual(manifest["files"], {"model_index.json": 2})

    def test_full_pilot_records_real_repeat_and_separate_reviews(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            torch = MagicMock()
            torch.mps.recommended_max_memory.return_value = 100
            with patch.object(qs, "P2", root), patch.object(qs, "CONFIG", root / "config.json"), \
                 patch.object(qs, "ROOT", root / "eval"), \
                 patch.object(qs, "local_pipeline", return_value=(torch, SimpleNamespace(q8_audit={}))), \
                 patch.object(qs, "infer", side_effect=self.fake_infer) as infer:
                folder = qs.pilot()
                report = qs.read(folder / "report.json")
                self.assertEqual(infer.call_count, 4)
                self.assertEqual(report["status"], "awaiting_visual_review")
                self.assertEqual(len(report["candidates"]), 2)
                self.assertTrue(report["reproducibility"]["file_identical"])
                self.assertEqual(report["geometry_review"], "not_reviewed")
                self.assertEqual(report["visual_review"], "not_reviewed")
                self.assertFalse(report["smoke"]["quality_candidate"])
                self.assertIn("input_roles", report)
                self.assertTrue((folder / "comparison.png").exists())
                self.assertIn('id="opacity"', (folder / "index.html").read_text())

    def test_smoke_does_not_generate_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            torch = MagicMock()
            torch.mps.recommended_max_memory.return_value = 100
            with patch.object(qs, "P2", root), patch.object(qs, "CONFIG", root / "config.json"), \
                 patch.object(qs, "ROOT", root / "eval"), \
                 patch.object(qs, "local_pipeline", return_value=(torch, SimpleNamespace(q8_audit={}))), \
                 patch.object(qs, "infer", side_effect=self.fake_infer) as infer:
                report = qs.read(qs.pilot(smoke_only=True) / "report.json")
                self.assertEqual(infer.call_count, 1)
                self.assertEqual(report["status"], "smoke_passed")
                self.assertEqual(report["candidates"], [])
                self.assertIsNone(report["reproducibility"])

    def test_failure_is_recorded_without_success_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            with patch.object(qs, "P2", root), patch.object(qs, "CONFIG", root / "config.json"), \
                 patch.object(qs, "ROOT", root / "eval"), \
                 patch.object(qs, "local_pipeline", side_effect=RuntimeError("out of memory")):
                with self.assertRaisesRegex(RuntimeError, "out of memory"):
                    qs.pilot()
                report = qs.read(next((root / "eval/runs").glob("*/report.json")))
                self.assertEqual(report["status"], "failed")
                self.assertEqual(report["candidates"], [])
                self.assertIsNone(report["reproducibility"])

    def test_variant_defaults_and_single_q8_candidate(self):
        self.assertEqual(len(qs.configuration()["seeds"]), 2)
        self.assertEqual(qs.configuration("q8")["seeds"], [20260913])
        with self.assertRaises(ValueError):
            qs.configuration("unknown")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            qs.write(root / "models/qwen_q8_prepared.json", {"quantization": "Q8_0"})
            torch = MagicMock()
            torch.mps.recommended_max_memory.return_value = 100
            with patch.object(qs, "P2", root), patch.object(qs, "CONFIG", root / "config.json"), \
                 patch.object(qs, "ROOT", root / "eval"), patch.object(qs, "CACHE", root / "models/cache"), \
                 patch.object(qs, "local_pipeline", return_value=(torch, SimpleNamespace(q8_audit={}))), \
                 patch.object(qs, "infer", side_effect=self.fake_infer) as infer:
                folder = qs.pilot(variant="q8")
                report = qs.read(folder / "report.json")
                self.assertEqual(infer.call_count, 2)
                self.assertEqual(len(report["candidates"]), 1)
                self.assertEqual(report["reproducibility"]["status"], "not_run")
                self.assertEqual(folder.parent, root / "eval/q8/runs")
                self.assertFalse((root / "eval/index.html").exists())

    def test_q8_hash_and_2511_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = qs.configuration("q8")
            qs.write(root / "transformer/config.json", {"zero_cond_t": True})
            weight = root / "test.gguf"
            weight.write_bytes(b"test")
            cfg["q8"].update(bytes=4, sha256=qs.sha(weight))
            with patch("huggingface_hub.snapshot_download", return_value=str(root)), \
                 patch("huggingface_hub.hf_hub_download", return_value=str(weight)) as download:
                self.assertEqual(qs.q8_paths(cfg), (root, weight))
                self.assertTrue(download.call_args.kwargs["local_files_only"])
                cfg["q8"]["sha256"] = "wrong"
                with self.assertRaisesRegex(ValueError, "SHA256"):
                    qs.q8_paths(cfg)
                qs.write(root / "transformer/config.json", {"zero_cond_t": False})
                with self.assertRaisesRegex(ValueError, "zero_cond_t"):
                    qs.q8_paths(cfg)

    def test_q8_loader_uses_quantized_transformer_offline(self):
        import torch
        from diffusers import QwenImageEditPlusPipeline, QwenImageTransformer2DModel
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qs.write(root / "transformer/config.json", {"zero_cond_t": True})
            cfg = qs.configuration("q8")
            with patch.dict(os.environ, {}, clear=False), \
                 patch.object(torch.backends.mps, "is_available", return_value=True), \
                 patch.object(qs, "q8_paths", return_value=(root, root / "q8.gguf")), \
                 patch.object(qs, "q8_checkpoint", return_value=({}, {"q8_weight_count": 0})) as checkpoint, \
                 patch.object(QwenImageTransformer2DModel, "from_config") as empty, \
                 patch.object(QwenImageTransformer2DModel, "from_single_file") as transformer, \
                 patch.object(QwenImageEditPlusPipeline, "from_pretrained") as pipeline:
                pipeline.return_value.transformer = transformer.return_value
                transformer.return_value.config.zero_cond_t = True
                transformer.return_value.is_quantized = True
                qs.local_pipeline(cfg)
                options = transformer.call_args.kwargs
                self.assertIs(transformer.call_args.args[0], checkpoint.return_value[0])
                self.assertTrue(options["local_files_only"])
                self.assertEqual(options["subfolder"], "transformer")
                self.assertEqual(options["quantization_config"].compute_dtype, torch.bfloat16)
                self.assertIs(pipeline.call_args.kwargs["transformer"], transformer.return_value)
                transformer.return_value.is_quantized = False
                with self.assertRaisesRegex(RuntimeError, "no BF16 fallback"):
                    qs.local_pipeline(cfg)
                checkpoint.side_effect = ValueError("GGUF key mismatch")
                with self.assertRaisesRegex(ValueError, "GGUF key mismatch"):
                    qs.local_pipeline(cfg)

    def test_q8_marker_and_weight_guards(self):
        import torch
        from gguf import GGMLQuantizationType as T
        marker = SimpleNamespace(name="__index_timestep_zero__", tensor_type=T.F32,
                                 shape=np.array([0]), n_elements=0)
        weight = SimpleNamespace(name="weight", tensor_type=T.Q8_0, shape=np.array([32, 1]), n_elements=32)
        packed = SimpleNamespace(quant_type=T.Q8_0)
        expected = {"weight": torch.empty((1, 32), device="meta")}
        with patch("gguf.GGUFReader") as reader, \
             patch("diffusers.models.model_loading_utils.load_gguf_checkpoint") as load:
            reader.return_value.tensors = [marker, weight]
            load.side_effect = lambda _: {marker.name: torch.empty(0), "weight": packed}
            checkpoint, audit = qs.q8_checkpoint("unused.gguf", expected)
            self.assertEqual(set(checkpoint), {"weight"})
            self.assertIs(checkpoint["weight"], packed)
            self.assertFalse(audit["source_file_modified"])
            self.assertEqual(audit["q8_weight_count"], 1)
            packed.quant_type = None
            with self.assertRaisesRegex(RuntimeError, "dequantized"):
                qs.q8_checkpoint("unused.gguf", expected)
            packed.quant_type = T.Q8_0
            for field, value in (("tensor_type", T.F16), ("shape", np.array([1])), ("n_elements", 1)):
                original = getattr(marker, field)
                setattr(marker, field, value)
                with self.assertRaisesRegex(ValueError, "marker"):
                    qs.q8_checkpoint("unused.gguf", expected)
                setattr(marker, field, original)
            with self.assertRaisesRegex(ValueError, "shape mismatch"):
                qs.q8_checkpoint("unused.gguf", {"weight": torch.empty((2, 32), device="meta")})
            reader.return_value.tensors = [marker, weight, SimpleNamespace(name="extra")]
            with self.assertRaisesRegex(ValueError, "key mismatch"):
                qs.q8_checkpoint("unused.gguf", expected)
            reader.return_value.tensors = [marker]
            with self.assertRaisesRegex(ValueError, "key mismatch"):
                qs.q8_checkpoint("unused.gguf", expected)
            reader.return_value.tensors = [weight]
            with self.assertRaisesRegex(ValueError, "marker"):
                qs.q8_checkpoint("unused.gguf", expected)

    def test_progress_is_saved_before_completion(self):
        torch, pipe = MagicMock(), MagicMock()
        torch.mps.current_allocated_memory.return_value = 1
        torch.mps.driver_allocated_memory.return_value = 2
        def run(**kwargs):
            kwargs["callback_on_step_end"](pipe, 0, None, {})
            raise RuntimeError("interrupted step")
        pipe.side_effect = run
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "progress.json"
            with self.assertRaisesRegex(RuntimeError, "interrupted step"):
                qs.infer(torch, pipe, qs.configuration(), None, None, 512, 4, 1, progress_path=path)
            progress = qs.read(path)
            self.assertEqual(progress["step_times"][0]["step"], 1)
            self.assertEqual(progress["sampled_peak_memory"]["mps_driver_bytes"], 2)


if __name__ == "__main__":
    unittest.main()
