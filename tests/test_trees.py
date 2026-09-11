from pathlib import Path

import pytest
import trimesh

from vision_demo.tree_mesh import merge_trees_by_material
from vision_demo.trees import TREE_PAD_SIZE_M, street_trees
from vision_demo.road_map import (
    CURB_WIDTH_MM,
    MM_TO_WORLD_M,
    ROAD_WIDTH_MM,
    three_crossroad_centers,
)


def test_tree_has_four_outward_facing_objects() -> None:
    asset_path = (
        Path(__file__).parents[1] / "src" / "vision_demo" / "assets" / "tree.obj"
    )
    lines = asset_path.read_text().splitlines()
    assert sum(line.startswith("o ") for line in lines) == 4
    scene = trimesh.load_scene(asset_path, process=False)
    assert len(scene.geometry) == 4
    assert all(geometry.volume > 0.0 for geometry in scene.geometry.values())
    assert TREE_PAD_SIZE_M == pytest.approx(0.4)
    assert scene.geometry["tree_trunk"].extents[:2] == pytest.approx((0.1, 0.1))
    material_lines = (asset_path.parent / "buildings.mtl").read_text().splitlines()
    assert material_lines.count("d 0.75") == 2


def test_tree_pads_touch_the_road_side_of_the_curb() -> None:
    placements = street_trees()
    assert len(placements) == 48
    assert len({placement.center_xy_m for placement in placements}) == 48
    road_centers = three_crossroad_centers()
    expected_center_distance = (
        ROAD_WIDTH_MM * MM_TO_WORLD_M * 0.5
        + CURB_WIDTH_MM * MM_TO_WORLD_M
        + TREE_PAD_SIZE_M * 0.5
    )
    for placement in placements:
        x, y = placement.center_xy_m
        nearest_road_distance = min(abs(y), *(abs(x - road_x) for road_x in road_centers))
        assert nearest_road_distance == pytest.approx(expected_center_distance)


def test_tree_layout_prioritizes_corners_and_uses_one_midpoint() -> None:
    points = {placement.center_xy_m for placement in street_trees()}
    # Road-facing corners and the single midpoint of the lower-left block.
    assert {(-14.53, -2.07), (-12.45, -2.07), (-10.37, -2.07)} <= points
    # Its vertical-road edge also has the far corner and one midpoint.
    assert {(-10.37, -6.23), (-10.37, -4.15)} <= points


def test_tree_instances_merge_to_four_material_meshes() -> None:
    asset_path = (
        Path(__file__).parents[1] / "src" / "vision_demo" / "assets" / "tree.obj"
    )
    meshes = merge_trees_by_material(asset_path, street_trees())
    assert set(meshes) == {"tree_pad", "tree_trunk", "leaf_large", "leaf_small"}
    assert all(len(mesh.faces) > 0 for mesh in meshes.values())
