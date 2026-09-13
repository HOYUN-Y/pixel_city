import importlib.util
import json
import os
import unittest

P2 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "tile_pipeline", os.path.join(P2, "scripts", "tile_pipeline.py"))
tp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tp)


class TilePipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(P2, "configs", "pipeline.json"), encoding="utf-8") as f:
            cls.cfg = json.load(f)
        cls.manifest = tp.build_manifest(cls.cfg)

    def test_expected_global_grid(self):
        self.assertEqual((self.manifest["global_camera"]["width"],
                          self.manifest["global_camera"]["height"]), (9134, 5528))
        self.assertEqual(self.manifest["grid"],
                         {"rows": 8, "cols": 12, "tile_size": 1024,
                          "overlap": 128, "core": 768})
        self.assertEqual(len(self.manifest["tiles"]), 96)

    def test_tiles_cover_canvas_and_seeds_are_unique(self):
        g, grid = self.manifest["global_camera"], self.manifest["grid"]
        self.assertGreaterEqual(grid["cols"] * grid["core"], g["width"])
        self.assertGreaterEqual(grid["rows"] * grid["core"], g["height"])
        seeds = [t["seed"] for t in self.manifest["tiles"]]
        self.assertEqual(len(seeds), len(set(seeds)))

    def test_pilot_is_contiguous_two_by_two(self):
        tiles = {t["id"]: (t["row"], t["col"]) for t in self.manifest["tiles"]}
        coords = {tiles[t] for t in self.cfg["pilot_tiles"]}
        self.assertEqual(coords, {(1, 2), (1, 3), (2, 2), (2, 3)})


if __name__ == "__main__":
    unittest.main()
