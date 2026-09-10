from pathlib import Path
import math

import pytest
import trimesh

from vision_demo.building_mesh import merge_buildings_by_material
from vision_demo.buildings import (
    BUILDING_EDGE_INSET_M,
    road_facing_yaw,
    street_buildings,
)
from vision_demo.road_map import (
    MM_TO_WORLD_M,
    ROAD_SEGMENT_LENGTH_MM,
    three_crossroad_block_centers,
)


def test_building_assets_have_requested_object_counts() -> None:
    asset_dir = Path(__file__).parents[1] / "src" / "vision_demo" / "assets"
    expected = {"house.obj": 4, "building.obj": 7, "market.obj": 3}
    for filename, object_count in expected.items():
        lines = (asset_dir / filename).read_text().splitlines()
        assert sum(line.startswith("o ") for line in lines) == object_count
        assert "mtllib buildings.mtl" in lines
        scene = trimesh.load_scene(asset_dir / filename, process=False)
        assert all(geometry.volume > 0.0 for geometry in scene.geometry.values())


def test_single_floor_asset_and_door_heights() -> None:
    asset_dir = Path(__file__).parents[1] / "src" / "vision_demo" / "assets"
    house = trimesh.load_scene(asset_dir / "house.obj", process=False)
    tower = trimesh.load_scene(asset_dir / "building.obj", process=False)
    market = trimesh.load_scene(asset_dir / "market.obj", process=False)
    assert house.geometry["house_wall"].bounds[1, 2] == pytest.approx(0.6)
    assert market.geometry["market_wall"].bounds[1, 2] == pytest.approx(0.7)
    assert house.geometry["door"].bounds[1, 2] == pytest.approx(0.52)
    assert market.geometry["door"].bounds[1, 2] == pytest.approx(0.52)
    assert tower.geometry["door"].bounds[1, 2] == pytest.approx(0.52)


def test_buildings_stay_one_road_block_width_inside_sidewalk_blocks() -> None:
    block_size_m = 8 * ROAD_SEGMENT_LENGTH_MM * MM_TO_WORLD_M
    block_centers = three_crossroad_block_centers()
    placements = street_buildings()
    assert len(placements) == 32
    assert {placement.asset for placement in placements} == {
        "house.obj",
        "building.obj",
        "market.obj",
    }
    for placement in placements:
        block_center = min(
            block_centers,
            key=lambda center: (
                (placement.center_xy_m[0] - center[0]) ** 2
                + (placement.center_xy_m[1] - center[1]) ** 2
            ),
        )
        clearance_x = (
            block_size_m * 0.5
            - abs(placement.center_xy_m[0] - block_center[0])
            - placement.footprint_xy_m[0] * 0.5
        )
        clearance_y = (
            block_size_m * 0.5
            - abs(placement.center_xy_m[1] - block_center[1])
            - placement.footprint_xy_m[1] * 0.5
        )
        assert clearance_x >= BUILDING_EDGE_INSET_M
        assert clearance_y >= BUILDING_EDGE_INSET_M


def test_building_instances_merge_to_one_mesh_per_material() -> None:
    asset_dir = Path(__file__).parents[1] / "src" / "vision_demo" / "assets"
    meshes = merge_buildings_by_material(asset_dir, street_buildings())
    assert set(meshes) == {
        "house_wall",
        "roof_red",
        "tower_wall",
        "market_wall",
        "door",
        "glass",
    }
    assert all(len(mesh.faces) > 0 for mesh in meshes.values())


def test_buildings_face_the_nearest_contacting_road() -> None:
    yaws = {placement.yaw_rad for placement in street_buildings()}
    assert yaws == {0.0, math.pi, math.pi * 0.5, -math.pi * 0.5}
    assert road_facing_yaw((4.15, 3.35)) == 0.0
    assert road_facing_yaw((3.35, 4.95)) == pytest.approx(-math.pi * 0.5)
