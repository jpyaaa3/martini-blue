"""Procedural tile layout for the first four-way road map."""

from __future__ import annotations

from dataclasses import dataclass


MM_TO_WORLD_M = 0.01
ROAD_BLOCK_WIDTH_MM = 80.0
ROAD_SEGMENT_LENGTH_MM = 60.0
STRIPE_MM = 10.0
CURB_WIDTH_MM = STRIPE_MM
TILE_THICKNESS_M = 0.01
ROAD_TOP_Z_M = TILE_THICKNESS_M
MARKING_Z_OFFSET_M = 0.0005
CURB_HEIGHT_M = 0.05
SIDEWALK_HEIGHT_M = 0.03

ASPHALT = "asphalt"
WHITE = "white"
YELLOW = "yellow"
CURB = "curb"
SIDEWALK = "sidewalk"

ROAD_BANDS: tuple[tuple[str, float], ...] = (
    (ASPHALT, ROAD_BLOCK_WIDTH_MM),
    (WHITE, STRIPE_MM),
    (ASPHALT, ROAD_BLOCK_WIDTH_MM),
    (YELLOW, STRIPE_MM),
    (ASPHALT, ROAD_BLOCK_WIDTH_MM),
    (WHITE, STRIPE_MM),
    (ASPHALT, ROAD_BLOCK_WIDTH_MM),
)
ROAD_WIDTH_MM = sum(width for _, width in ROAD_BANDS)
DEFAULT_ARM_SEGMENTS = 8


@dataclass(frozen=True)
class MapTile:
    center_xy_m: tuple[float, float]
    size_xy_m: tuple[float, float]
    material: str
    z_offset_m: float = 0.0
    height_m: float = TILE_THICKNESS_M

    @property
    def position_xyz_m(self) -> tuple[float, float, float]:
        return (*self.center_xy_m, self.height_m * 0.5 + self.z_offset_m)

    @property
    def size_xyz_m(self) -> tuple[float, float, float]:
        return (*self.size_xy_m, self.height_m)


def _band_centers_mm() -> tuple[tuple[str, float, float], ...]:
    cursor = -ROAD_WIDTH_MM * 0.5
    result = []
    for material, width in ROAD_BANDS:
        result.append((material, cursor + width * 0.5, width))
        cursor += width
    return tuple(result)


def straight_road_segment(
    *,
    axis: str,
    center_m: float,
    white_dash: bool,
) -> tuple[MapTile, ...]:
    """Build one 60 mm-long road slice along X or Y."""

    if axis not in {"x", "y"}:
        raise ValueError("road axis must be 'x' or 'y'")

    segment_m = ROAD_SEGMENT_LENGTH_MM * MM_TO_WORLD_M
    tiles = []
    for material, lateral_mm, width_mm in _band_centers_mm():
        if material == WHITE and not white_dash:
            material = ASPHALT
        lateral_m = lateral_mm * MM_TO_WORLD_M
        width_m = width_mm * MM_TO_WORLD_M
        if axis == "x":
            center = (center_m, lateral_m)
            size = (segment_m, width_m)
        else:
            center = (lateral_m, center_m)
            size = (width_m, segment_m)
        tiles.append(MapTile(center, size, material))
    return tuple(tiles)


def intersection_tiles() -> tuple[MapTile, ...]:
    """Fill the road-width square using black versions of the tile grid."""

    tiles = []
    for _, x_mm, width_mm in _band_centers_mm():
        for _, y_mm, height_mm in _band_centers_mm():
            tiles.append(
                MapTile(
                    (x_mm * MM_TO_WORLD_M, y_mm * MM_TO_WORLD_M),
                    (width_mm * MM_TO_WORLD_M, height_mm * MM_TO_WORLD_M),
                    ASPHALT,
                )
            )
    return tuple(tiles)


def four_way_map(*, arm_segments: int = 8) -> tuple[MapTile, ...]:
    """Build a black four-way junction with marked roads on all four arms."""

    if arm_segments < 1:
        raise ValueError("arm_segments must be at least one")

    tiles = list(intersection_tiles())
    road_half_m = ROAD_WIDTH_MM * MM_TO_WORLD_M * 0.5
    segment_m = ROAD_SEGMENT_LENGTH_MM * MM_TO_WORLD_M
    for axis in ("x", "y"):
        for direction in (-1.0, 1.0):
            for index in range(arm_segments):
                center = direction * (road_half_m + (index + 0.5) * segment_m)
                tiles.extend(
                    straight_road_segment(
                        axis=axis,
                        center_m=center,
                        white_dash=index % 2 == 0,
                    )
                )
    return tuple(tiles)


def four_way_render_tiles(*, arm_segments: int = 8) -> tuple[MapTile, ...]:
    """Return an entity-efficient version of :func:`four_way_map`.

    Contiguous asphalt and yellow sections become arbitrary-length rectangles.
    White marks stay separate because their gaps create the dashed pattern.
    """

    if arm_segments < 1:
        raise ValueError("arm_segments must be at least one")

    road_width_m = ROAD_WIDTH_MM * MM_TO_WORLD_M
    road_half_m = road_width_m * 0.5
    segment_m = ROAD_SEGMENT_LENGTH_MM * MM_TO_WORLD_M
    arm_length_m = arm_segments * segment_m
    arm_center_distance = road_half_m + arm_length_m * 0.5
    stripe_m = STRIPE_MM * MM_TO_WORLD_M
    white_lateral_positions_m = tuple(
        center_mm * MM_TO_WORLD_M
        for material, center_mm, _ in _band_centers_mm()
        if material == WHITE
    )

    tiles = [MapTile((0.0, 0.0), (road_width_m, road_width_m), ASPHALT)]
    for axis in ("x", "y"):
        for direction in (-1.0, 1.0):
            center = direction * arm_center_distance
            if axis == "x":
                road_center = (center, 0.0)
                road_size = (arm_length_m, road_width_m)
                yellow_center = (center, 0.0)
                yellow_size = (arm_length_m, stripe_m)
            else:
                road_center = (0.0, center)
                road_size = (road_width_m, arm_length_m)
                yellow_center = (0.0, center)
                yellow_size = (stripe_m, arm_length_m)
            tiles.append(MapTile(road_center, road_size, ASPHALT))
            tiles.append(
                MapTile(
                    yellow_center,
                    yellow_size,
                    YELLOW,
                    MARKING_Z_OFFSET_M,
                )
            )

            for index in range(0, arm_segments, 2):
                dash_center = direction * (
                    road_half_m + (index + 0.5) * segment_m
                )
                for lateral_m in white_lateral_positions_m:
                    if axis == "x":
                        dash_position = (dash_center, lateral_m)
                        dash_size = (segment_m, stripe_m)
                    else:
                        dash_position = (lateral_m, dash_center)
                        dash_size = (stripe_m, segment_m)
                    tiles.append(
                        MapTile(
                            dash_position,
                            dash_size,
                            WHITE,
                            MARKING_Z_OFFSET_M,
                        )
                    )
    return tuple(tiles)


def crossroad_surround_tiles(*, arm_segments: int = 8) -> tuple[MapTile, ...]:
    """Wrap the four road corners with merged curbs and sidewalk blocks.

    Each corner uses two continuous curb boxes, one 10 x 10 mm curb corner,
    and one continuous brown sidewalk box. Road-arm ends remain open.
    """

    if arm_segments < 1:
        raise ValueError("arm_segments must be at least one")

    road_half_m = ROAD_WIDTH_MM * MM_TO_WORLD_M * 0.5
    arm_length_m = arm_segments * ROAD_SEGMENT_LENGTH_MM * MM_TO_WORLD_M
    curb_width_m = CURB_WIDTH_MM * MM_TO_WORLD_M
    inner_curb_center_m = road_half_m + curb_width_m * 0.5
    surround_span_m = arm_length_m - curb_width_m
    surround_center_m = road_half_m + curb_width_m + surround_span_m * 0.5

    tiles = []
    for x_direction in (-1.0, 1.0):
        for y_direction in (-1.0, 1.0):
            corner_center = (
                x_direction * inner_curb_center_m,
                y_direction * inner_curb_center_m,
            )
            tiles.append(
                MapTile(
                    corner_center,
                    (curb_width_m, curb_width_m),
                    CURB,
                    height_m=CURB_HEIGHT_M,
                )
            )
            tiles.append(
                MapTile(
                    (
                        x_direction * surround_center_m,
                        y_direction * inner_curb_center_m,
                    ),
                    (surround_span_m, curb_width_m),
                    CURB,
                    height_m=CURB_HEIGHT_M,
                )
            )
            tiles.append(
                MapTile(
                    (
                        x_direction * inner_curb_center_m,
                        y_direction * surround_center_m,
                    ),
                    (curb_width_m, surround_span_m),
                    CURB,
                    height_m=CURB_HEIGHT_M,
                )
            )
            tiles.append(
                MapTile(
                    (
                        x_direction * surround_center_m,
                        y_direction * surround_center_m,
                    ),
                    (surround_span_m, surround_span_m),
                    SIDEWALK,
                    height_m=SIDEWALK_HEIGHT_M,
                )
            )
    return tuple(tiles)


def three_crossroad_centers(*, arm_segments: int = DEFAULT_ARM_SEGMENTS) -> tuple[float, ...]:
    """Return X coordinates for three equally spaced connected intersections."""

    if arm_segments < 1:
        raise ValueError("arm_segments must be at least one")
    road_width_m = ROAD_WIDTH_MM * MM_TO_WORLD_M
    arm_length_m = arm_segments * ROAD_SEGMENT_LENGTH_MM * MM_TO_WORLD_M
    spacing_m = road_width_m + arm_length_m
    return (-spacing_m, 0.0, spacing_m)


def three_crossroad_render_tiles(
    *, arm_segments: int = DEFAULT_ARM_SEGMENTS
) -> tuple[MapTile, ...]:
    """Build three four-way intersections joined along the X axis.

    Shared connecting roads are emitted once, avoiding duplicate coplanar boxes.
    """

    centers = three_crossroad_centers(arm_segments=arm_segments)
    road_width_m = ROAD_WIDTH_MM * MM_TO_WORLD_M
    road_half_m = road_width_m * 0.5
    segment_m = ROAD_SEGMENT_LENGTH_MM * MM_TO_WORLD_M
    arm_length_m = arm_segments * segment_m
    stripe_m = STRIPE_MM * MM_TO_WORLD_M
    map_half_width_m = abs(centers[0]) + road_half_m + arm_length_m
    white_lateral_positions_m = tuple(
        center_mm * MM_TO_WORLD_M
        for material, center_mm, _ in _band_centers_mm()
        if material == WHITE
    )

    tiles = [
        MapTile((0.0, 0.0), (map_half_width_m * 2.0, road_width_m), ASPHALT)
    ]

    # The vertical arms stop at the horizontal road edge, so no asphalt faces overlap.
    for center_x in centers:
        for y_direction in (-1.0, 1.0):
            arm_center_y = y_direction * (road_half_m + arm_length_m * 0.5)
            tiles.append(
                MapTile(
                    (center_x, arm_center_y),
                    (road_width_m, arm_length_m),
                    ASPHALT,
                )
            )

    # Four horizontal road sections: two outer arms and two connectors.
    horizontal_centers = (
        centers[0] - road_half_m - arm_length_m * 0.5,
        (centers[0] + centers[1]) * 0.5,
        (centers[1] + centers[2]) * 0.5,
        centers[2] + road_half_m + arm_length_m * 0.5,
    )
    for section_center_x in horizontal_centers:
        tiles.append(
            MapTile(
                (section_center_x, 0.0),
                (arm_length_m, stripe_m),
                YELLOW,
                MARKING_Z_OFFSET_M,
            )
        )
        for index in range(0, arm_segments, 2):
            dash_x = section_center_x - arm_length_m * 0.5 + (index + 0.5) * segment_m
            for lateral_y in white_lateral_positions_m:
                tiles.append(
                    MapTile(
                        (dash_x, lateral_y),
                        (segment_m, stripe_m),
                        WHITE,
                        MARKING_Z_OFFSET_M,
                    )
                )

    for center_x in centers:
        for y_direction in (-1.0, 1.0):
            section_center_y = y_direction * (road_half_m + arm_length_m * 0.5)
            tiles.append(
                MapTile(
                    (center_x, section_center_y),
                    (stripe_m, arm_length_m),
                    YELLOW,
                    MARKING_Z_OFFSET_M,
                )
            )
            for index in range(0, arm_segments, 2):
                dash_y = y_direction * (
                    road_half_m + (index + 0.5) * segment_m
                )
                for lateral_x in white_lateral_positions_m:
                    tiles.append(
                        MapTile(
                            (center_x + lateral_x, dash_y),
                            (stripe_m, segment_m),
                            WHITE,
                            MARKING_Z_OFFSET_M,
                        )
                    )
    return tuple(tiles)


def three_crossroad_block_centers(
    *, arm_segments: int = DEFAULT_ARM_SEGMENTS
) -> tuple[tuple[float, float], ...]:
    """Return the eight sidewalk-block centers surrounding the road chain."""

    centers = three_crossroad_centers(arm_segments=arm_segments)
    road_half_m = ROAD_WIDTH_MM * MM_TO_WORLD_M * 0.5
    arm_length_m = arm_segments * ROAD_SEGMENT_LENGTH_MM * MM_TO_WORLD_M
    block_offset_m = road_half_m + arm_length_m * 0.5
    x_centers = (
        centers[0] - road_half_m - arm_length_m * 0.5,
        (centers[0] + centers[1]) * 0.5,
        (centers[1] + centers[2]) * 0.5,
        centers[2] + road_half_m + arm_length_m * 0.5,
    )
    return tuple(
        (x, y_direction * block_offset_m)
        for y_direction in (-1.0, 1.0)
        for x in x_centers
    )


def three_crossroad_surround_tiles(
    *, arm_segments: int = DEFAULT_ARM_SEGMENTS
) -> tuple[MapTile, ...]:
    """Create eight sidewalk blocks, each bounded by lightweight curb strips."""

    block_size_m = arm_segments * ROAD_SEGMENT_LENGTH_MM * MM_TO_WORLD_M
    curb_width_m = CURB_WIDTH_MM * MM_TO_WORLD_M
    curb_offset_m = (block_size_m - curb_width_m) * 0.5
    tiles: list[MapTile] = []
    for center_x, center_y in three_crossroad_block_centers(
        arm_segments=arm_segments
    ):
        tiles.append(
            MapTile(
                (center_x, center_y),
                (block_size_m, block_size_m),
                SIDEWALK,
                height_m=SIDEWALK_HEIGHT_M,
            )
        )
        for x_offset, y_offset, size in (
            (-curb_offset_m, 0.0, (curb_width_m, block_size_m)),
            (curb_offset_m, 0.0, (curb_width_m, block_size_m)),
            (0.0, -curb_offset_m, (block_size_m, curb_width_m)),
            (0.0, curb_offset_m, (block_size_m, curb_width_m)),
        ):
            tiles.append(
                MapTile(
                    (center_x + x_offset, center_y + y_offset),
                    size,
                    CURB,
                    height_m=CURB_HEIGHT_M,
                )
            )
    return tuple(tiles)
