import copy
from pathlib import Path

import numpy as np
import pytest

from vision_demo.map_file import DEFAULT_MAP, load_map, parse_map, road_tiles
from vision_demo.road_map import ASPHALT, three_crossroad_surround_tiles
from vision_demo.static_scene import build_static_scene
from vision_demo.main import _parser


ASSETS = DEFAULT_MAP.parent.parent / "assets"
SIMPLE = {"version": 1, "roads": [{"from": [-5, 0], "to": [5, 0], "width": 2}]}


def rectangle(tile):
    x, y = tile.center_xy_m
    w, h = tile.size_xy_m
    return x-w/2, y-h/2, x+w/2, y+h/2


def overlap(a, b):
    return max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))


def test_default_map_preserves_objects_and_nonoverlapping_surrounds():
    definition = load_map(DEFAULT_MAP)
    assert len(definition.buildings) == 32
    assert len(definition.trees) > 0
    for new, old in zip(definition.surrounds, three_crossroad_surround_tiles(), strict=True):
        assert new.material == old.material
        assert new.center_xy_m == pytest.approx(old.center_xy_m)
        assert new.size_xyz_m == pytest.approx(old.size_xyz_m)


@pytest.mark.parametrize("start", [-5, 0])
def test_cross_and_t_junction_have_no_overlapping_road_faces_or_junction_paint(start):
    data = copy.deepcopy(SIMPLE)
    data["roads"].append({"from": [0, start], "to": [0, 5], "width": 2})
    definition = parse_map(data)
    tiles = road_tiles(definition)
    beds = [rectangle(t) for t in tiles if t.material == ASPHALT]
    for i, a in enumerate(beds):
        for b in beds[i+1:]:
            assert overlap(a, b) == 0
    junction = (-1, max(start, -1), 1, 1)
    assert sum((r[2]-r[0])*(r[3]-r[1]) for r in beds) == pytest.approx(20 + (5-start)*2 - (4 if start == -5 else 2))
    for tile in tiles:
        if tile.material != ASPHALT:
            assert overlap(rectangle(tile), junction) < 1e-12


def test_minimal_map_needs_no_buildings_trees_or_sidewalks():
    mesh, atlas = build_static_scene(ASSETS, parse_map(SIMPLE))
    assert len(mesh.faces) == 2
    assert mesh.visual.kind == "texture"
    assert np.isfinite(mesh.visual.uv).all()
    assert atlas.mode == "RGB"


@pytest.mark.parametrize("field,value,match", [
    ("roads", [], "between 1 and 128"),
    ("roads", {}, "array"),
    ("version", 2, "version"),
    ("trees", [{"position": [float("nan"), 0]}], "finite"),
    ("trees", [{"position": [True, 0]}], "finite"),
    ("trees", [{"position": [0]}], "expected"),
    ("buildings", [{"type": "../car", "position": [0, 0]}], "type"),
    ("sidewalks", [{"position": [0, 3], "size": [0.1, 2]}], "twice"),
    ("typo", [], "unknown"),
])
def test_invalid_fields_are_rejected(field, value, match):
    data = copy.deepcopy(SIMPLE)
    data[field] = value
    with pytest.raises(ValueError, match=match):
        parse_map(data)


@pytest.mark.parametrize("end", [[5, 1], [-5, 0]])
def test_diagonal_and_zero_length_roads_are_rejected(end):
    data = copy.deepcopy(SIMPLE)
    data["roads"][0]["to"] = end
    with pytest.raises(ValueError, match="horizontal or vertical"):
        parse_map(data)


def test_parallel_overlaps_are_reported():
    data = copy.deepcopy(SIMPLE)
    data["roads"] *= 2
    with pytest.raises(ValueError, match="parallel"):
        parse_map(data)


def test_invalid_json_reports_filename(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{")
    with pytest.raises(ValueError, match="broken.json"):
        load_map(path)


def test_cli_accepts_map_and_cache_paths():
    args = _parser().parse_args(["--map", "my-map.json", "--map-cache", "cache"])
    assert args.map == Path("my-map.json")
    assert args.map_cache == Path("cache")
