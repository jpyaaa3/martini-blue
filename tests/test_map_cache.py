import json
import shutil

from vision_demo import map_cache
from vision_demo.map_file import DEFAULT_MAP


def test_cache_reuses_valid_assets_and_rebuilds_for_changes_or_corruption(tmp_path, monkeypatch):
    assets = tmp_path / "assets"
    shutil.copytree(DEFAULT_MAP.parent.parent / "assets", assets)
    path = tmp_path / "map.json"
    data = {"version": 1, "roads": [{"from": [-5, 0], "to": [5, 0], "width": 2}]}
    path.write_text(json.dumps(data))
    calls = []
    original = map_cache.export_static_scene

    def track(*args):
        calls.append(args)
        return original(*args)

    monkeypatch.setattr(map_cache, "export_static_scene", track)
    cache = tmp_path / "cache"
    first = map_cache.prepare_map(path, assets, cache)
    assert len(calls) == 1
    timestamp = (first / "static_scene.obj").stat().st_mtime_ns
    path.write_text(json.dumps(data, indent=4))
    assert map_cache.prepare_map(path, assets, cache) == first
    assert len(calls) == 1
    assert (first / "static_scene.obj").stat().st_mtime_ns == timestamp

    (first / "static_scene.png").write_bytes(b"broken")
    assert map_cache.prepare_map(path, assets, cache) == first
    assert len(calls) == 2
    assert (first / "static_scene.png").read_bytes().startswith(b"\x89PNG")

    data["roads"][0]["width"] = 3
    path.write_text(json.dumps(data))
    second = map_cache.prepare_map(path, assets, cache)
    assert second != first
    assert len(calls) == 3

    asset = assets / "house.obj"
    asset.write_text(asset.read_text() + "\n# changed source asset\n")
    third = map_cache.prepare_map(path, assets, cache)
    assert third != second
    assert len(calls) == 4
