from vision_demo.map_mesh import merge_tiles_by_material
from vision_demo.road_map import (
    ASPHALT,
    CURB,
    SIDEWALK,
    WHITE,
    YELLOW,
    three_crossroad_render_tiles,
    three_crossroad_surround_tiles,
)


def test_map_boxes_merge_into_one_mesh_per_material() -> None:
    tiles = (*three_crossroad_render_tiles(), *three_crossroad_surround_tiles())
    meshes = merge_tiles_by_material(tiles)

    assert set(meshes) == {ASPHALT, WHITE, YELLOW, CURB, SIDEWALK}
    assert len(meshes) == 5
    assert all(len(mesh.faces) > 0 for mesh in meshes.values())
    assert sum(len(mesh.faces) for mesh in meshes.values()) == len(tiles) * 12
