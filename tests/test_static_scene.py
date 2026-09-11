from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

from vision_demo.static_scene import COLORS, build_static_scene
from vision_demo.road_map import ASPHALT, three_crossroad_render_tiles


ASSETS = Path(__file__).parents[1] / "src/vision_demo/assets"


def test_export_is_one_textured_mesh_and_matches_generator():
    scene = trimesh.load_scene(ASSETS / "static_scene.obj", process=False)
    assert len(scene.geometry) == 1
    loaded = next(iter(scene.geometry.values()))
    expected, atlas = build_static_scene(ASSETS)
    assert len(loaded.faces) == len(expected.faces)
    np.testing.assert_allclose(loaded.bounds, expected.bounds)
    assert loaded.visual.kind == "texture"
    assert np.isfinite(loaded.visual.uv).all()
    assert ((loaded.visual.uv >= 0) & (loaded.visual.uv <= 1)).all()
    np.testing.assert_array_equal(np.asarray(loaded.visual.material.image), np.asarray(atlas))
    with Image.open(ASSETS / "static_scene.png") as saved:
        np.testing.assert_array_equal(np.asarray(saved), np.asarray(atlas))


def test_road_markings_are_baked_at_correct_world_positions():
    mesh, atlas = build_static_scene(ASSETS)
    road_tiles = [t for t in three_crossroad_render_tiles() if t.material == ASPHALT]
    # Each road rectangle has four vertices and two upward-facing triangles.
    assert len(road_tiles) == 7
    assert np.all(mesh.face_normals[:14, 2] > 0.99)
    for tile in three_crossroad_render_tiles():
        if tile.material == ASPHALT:
            continue
        point = np.array(tile.center_xy_m)
        for index, road in enumerate(road_tiles):
            low = np.array(road.center_xy_m) - np.array(road.size_xy_m) / 2
            fraction = (point - low) / road.size_xy_m
            if np.all((fraction >= 0) & (fraction <= 1)):
                uv = mesh.visual.uv[index*4:index*4+4]
                sample = uv[0] + fraction[0] * (uv[1]-uv[0]) + fraction[1] * (uv[3]-uv[0])
                pixel = (round(sample[0]*atlas.width), round((1-sample[1])*atlas.height))
                assert atlas.getpixel(pixel) == COLORS[tile.material]
                break
        else:
            raise AssertionError("Marking is outside all road surfaces")
