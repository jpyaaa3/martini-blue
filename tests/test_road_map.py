import pytest

from vision_demo.road_map import (
    ASPHALT,
    CURB,
    CURB_HEIGHT_M,
    CURB_WIDTH_MM,
    MM_TO_WORLD_M,
    ROAD_BLOCK_WIDTH_MM,
    ROAD_SEGMENT_LENGTH_MM,
    ROAD_WIDTH_MM,
    SIDEWALK,
    SIDEWALK_HEIGHT_M,
    WHITE,
    YELLOW,
    crossroad_surround_tiles,
    four_way_map,
    four_way_render_tiles,
    intersection_tiles,
    straight_road_segment,
    three_crossroad_block_centers,
    three_crossroad_centers,
    three_crossroad_render_tiles,
    three_crossroad_surround_tiles,
)


def test_road_dimensions_match_design_millimetres() -> None:
    assert ROAD_BLOCK_WIDTH_MM == 80.0
    assert ROAD_BLOCK_WIDTH_MM * MM_TO_WORLD_M == pytest.approx(0.8)
    assert ROAD_SEGMENT_LENGTH_MM == 60.0
    assert ROAD_SEGMENT_LENGTH_MM * MM_TO_WORLD_M == pytest.approx(0.6)
    assert ROAD_WIDTH_MM == 350.0


def test_straight_road_has_four_asphalt_tiles_and_three_marking_slots() -> None:
    solid = straight_road_segment(axis="x", center_m=0.0, white_dash=True)
    gap = straight_road_segment(axis="x", center_m=0.0, white_dash=False)

    assert len(solid) == 7
    assert [tile.material for tile in solid] == [
        ASPHALT,
        WHITE,
        ASPHALT,
        YELLOW,
        ASPHALT,
        WHITE,
        ASPHALT,
    ]
    assert [tile.material for tile in gap].count(WHITE) == 0
    assert sum(tile.size_xy_m[1] for tile in solid) == pytest.approx(3.5)


def test_intersection_fills_entire_road_width_with_black_tiles() -> None:
    tiles = intersection_tiles()
    assert len(tiles) == 49
    assert {tile.material for tile in tiles} == {ASPHALT}
    total_area = sum(tile.size_xy_m[0] * tile.size_xy_m[1] for tile in tiles)
    assert total_area == pytest.approx(3.5 * 3.5)


def test_four_way_map_has_four_arms() -> None:
    tiles = four_way_map(arm_segments=2)
    assert len(tiles) == 49 + 4 * 2 * 7


def test_render_layout_merges_contiguous_tiles() -> None:
    logical = four_way_map(arm_segments=8)
    rendered = four_way_render_tiles(arm_segments=8)

    assert len(logical) == 273
    assert len(rendered) == 41
    assert [tile.material for tile in rendered].count(ASPHALT) == 5
    assert [tile.material for tile in rendered].count(YELLOW) == 4
    assert [tile.material for tile in rendered].count(WHITE) == 32
    assert max(max(tile.size_xy_m) for tile in rendered) == pytest.approx(4.8)


def test_crossroad_surround_uses_merged_curbs_and_sidewalks() -> None:
    tiles = crossroad_surround_tiles(arm_segments=8)
    curbs = [tile for tile in tiles if tile.material == CURB]
    sidewalks = [tile for tile in tiles if tile.material == SIDEWALK]
    curb_width_m = CURB_WIDTH_MM * MM_TO_WORLD_M

    assert len(tiles) == 16
    assert len(curbs) == 12
    assert len(sidewalks) == 4
    assert sum(
        tile.size_xy_m == pytest.approx((curb_width_m, curb_width_m))
        for tile in curbs
    ) == 4
    assert all(min(tile.size_xy_m) == pytest.approx(curb_width_m) for tile in curbs)
    assert all(tile.height_m == CURB_HEIGHT_M for tile in curbs)
    assert all(tile.height_m == SIDEWALK_HEIGHT_M for tile in sidewalks)
    assert all(tile.size_xy_m == pytest.approx((4.7, 4.7)) for tile in sidewalks)


def test_bad_road_layout_arguments_are_rejected() -> None:
    with pytest.raises(ValueError, match="axis"):
        straight_road_segment(axis="z", center_m=0.0, white_dash=True)
    with pytest.raises(ValueError, match="at least one"):
        four_way_map(arm_segments=0)
    with pytest.raises(ValueError, match="at least one"):
        four_way_render_tiles(arm_segments=0)
    with pytest.raises(ValueError, match="at least one"):
        crossroad_surround_tiles(arm_segments=0)


def test_three_crossroads_are_evenly_connected_without_duplicate_asphalt() -> None:
    centers = three_crossroad_centers()
    assert centers == pytest.approx((-8.3, 0.0, 8.3))

    tiles = three_crossroad_render_tiles()
    asphalt = [tile for tile in tiles if tile.material == ASPHALT]
    yellow = [tile for tile in tiles if tile.material == YELLOW]
    white = [tile for tile in tiles if tile.material == WHITE]
    assert len(asphalt) == 7
    assert len(yellow) == 10
    assert len(white) == 80
    assert max(tile.size_xy_m[0] for tile in asphalt) == pytest.approx(29.7)


def test_three_crossroad_sidewalks_form_eight_city_blocks() -> None:
    centers = three_crossroad_block_centers()
    tiles = three_crossroad_surround_tiles()
    assert len(centers) == 8
    assert len([tile for tile in tiles if tile.material == SIDEWALK]) == 8
    assert len([tile for tile in tiles if tile.material == CURB]) == 32
    assert all(abs(y) == pytest.approx(4.15) for _, y in centers)
