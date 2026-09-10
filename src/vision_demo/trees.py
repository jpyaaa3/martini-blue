"""Street-tree placement along road-facing curb edges."""

from __future__ import annotations

from dataclasses import dataclass

from .road_map import (
    CURB_WIDTH_MM,
    DEFAULT_ARM_SEGMENTS,
    MM_TO_WORLD_M,
    ROAD_SEGMENT_LENGTH_MM,
    ROAD_WIDTH_MM,
    SIDEWALK_HEIGHT_M,
    three_crossroad_block_centers,
    three_crossroad_centers,
)


TREE_PAD_SIZE_M = 40.0 * MM_TO_WORLD_M


@dataclass(frozen=True)
class TreePlacement:
    center_xy_m: tuple[float, float]
    base_z_m: float = SIDEWALK_HEIGHT_M


def street_trees() -> tuple[TreePlacement, ...]:
    """Prioritize sidewalk corners, then add one tree between corner trees."""

    road_half_m = ROAD_WIDTH_MM * MM_TO_WORLD_M * 0.5
    curb_width_m = CURB_WIDTH_MM * MM_TO_WORLD_M
    curb_to_tree_center_m = road_half_m + curb_width_m + TREE_PAD_SIZE_M * 0.5
    block_size_m = DEFAULT_ARM_SEGMENTS * ROAD_SEGMENT_LENGTH_MM * MM_TO_WORLD_M
    corner_offset_m = block_size_m * 0.5 - curb_width_m - TREE_PAD_SIZE_M * 0.5
    points: dict[tuple[float, float], None] = {}

    def add(x: float, y: float) -> None:
        points[(round(x, 9), round(y, 9))] = None

    # Put trees at both corners facing the horizontal road, then one between them.
    for block_x, block_y in three_crossroad_block_centers():
        tree_y = curb_to_tree_center_m if block_y > 0.0 else -curb_to_tree_center_m
        add(block_x - corner_offset_m, tree_y)
        add(block_x + corner_offset_m, tree_y)
        add(block_x, tree_y)

        # Every vertical-road-facing edge gets its far corner and one midpoint.
        outer_y = block_y + (corner_offset_m if block_y > 0.0 else -corner_offset_m)
        for road_x in three_crossroad_centers():
            if abs(abs(road_x - block_x) - (road_half_m + block_size_m * 0.5)) > 1e-9:
                continue
            side = 1.0 if road_x > block_x else -1.0
            tree_x = block_x + side * corner_offset_m
            add(tree_x, outer_y)
            add(tree_x, block_y)

    return tuple(TreePlacement(point) for point in points)
