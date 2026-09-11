"""Content-addressed, integrity-checked static map assets."""

import hashlib
import json
import os
from pathlib import Path
import tempfile

from .map_file import load_map
from .static_scene import export_static_scene


OUTPUT_FILES = ("static_scene.obj", "static_scene.mtl", "static_scene.png")


def default_cache_dir() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    return base / "vision-demo" / "maps"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_map(map_path: Path, asset_dir: Path, cache_dir: Path | None = None) -> Path:
    """Validate before using a cache; rebuild on map, generator, or asset changes."""
    definition = load_map(map_path)
    # Hash the parsed snapshot used by the builder, not a second read of the map.
    fingerprint = hashlib.sha256(repr(definition).encode("utf-8"))
    sources = sorted(Path(__file__).parent.glob("*.py"))
    sources += sorted(p for p in asset_dir.iterdir()
                      if p.suffix in (".obj", ".mtl") and not p.name.startswith("static_scene."))
    for source in sources:
        fingerprint.update(source.name.encode("utf-8"))
        fingerprint.update(bytes.fromhex(_digest(source)))
    cache_dir = cache_dir if cache_dir is not None else default_cache_dir()
    target = cache_dir / fingerprint.hexdigest()
    try:
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        if all(manifest[name] == _digest(target / name) for name in OUTPUT_FILES):
            print(f"[vision] map cache hit: {map_path}", flush=True)
            return target
    except (OSError, ValueError, KeyError, TypeError):
        pass

    print(f"[vision] baking map: {map_path}", flush=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bake-", dir=cache_dir) as temporary:
        staging = Path(temporary)
        export_static_scene(asset_dir, definition, staging)
        manifest = {name: _digest(staging / name) for name in OUTPUT_FILES}
        (staging / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        target.mkdir(parents=True, exist_ok=True)
        for name in (*OUTPUT_FILES, "manifest.json"):
            os.replace(staging / name, target / name)
    return target
