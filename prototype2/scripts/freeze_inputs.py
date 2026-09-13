"""One-time, content-verified snapshot for independent prototype2 rendering."""
import json
import hashlib
import shutil
from pathlib import Path

P2 = Path(__file__).resolve().parents[1]
DEST = P2 / "inputs" / "snapshot"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze():
    marker = DEST / "snapshot.json"
    if marker.exists():
        manifest = json.loads(marker.read_text())
        for name, sha in manifest["files"].items():
            if digest(DEST / name) != sha:
                raise RuntimeError(f"Snapshot changed: {name}")
        print("Snapshot verified (no prototype1 reads)")
        return
    sources = {name: P2.parent / "prototype1/web/data" / name
               for name in ("city.json", "layers.json", "meta.json", "poi.json")}
    sources["style.json"] = P2.parent / "prototype1/poc/style.json"
    sources["tile_manifest.json"] = P2 / "work/fullmap/tile_manifest.json"
    original = json.loads(sources["tile_manifest.json"].read_text())
    for name, sha in original["input_sha256"].items():
        if digest(sources[name]) != sha:
            raise RuntimeError(f"Input differs from baseline: {name}")
    DEST.mkdir(parents=True, exist_ok=True)
    for name, src in sources.items():
        shutil.copyfile(src, DEST / name)
    manifest = {"source": "prototype1; frozen for prototype2, no live imports",
                "files": {name: digest(DEST / name) for name in sources}}
    marker.write_text(json.dumps(manifest, indent=2) + "\n")
    print(marker)


if __name__ == "__main__":
    freeze()
