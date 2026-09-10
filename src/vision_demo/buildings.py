"""Lightweight building asset placement for the three-intersection street."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .road_map import (
    MM_TO_WORLD_M,
    ROAD_BLOCK_WIDTH_MM,
    ROAD_WIDTH_MM,
    SIDEWALK_HEIGHT_M,
    three_crossroad_block_centers,
    three_crossroad_centers,
)


BUILDING_EDGE_INSET_M = ROAD_BLOCK_WIDTH_MM * MM_TO_WORLD_M
BUILDING_XY_SCALE = 0.60
BUILDING_GRID_OFFSET_M = 0.80


@dataclass(frozen=True)
class BuildingPlacement:
    asset: str
    center_xy_m: tuple[float, float]
    footprint_xy_m: tuple[float, float]
    yaw_rad: float
    scale_xy: float = BUILDING_XY_SCALE
    base_z_m: float = SIDEWALK_HEIGHT_M


_ASSET_FOOTPRINTS = {
    "house.obj": (1.8, 1.4),
    "building.obj": (1.6, 1.6),
    "market.obj": (2.6, 1.5),
}


def road_facing_yaw(center_xy_m: tuple[float, float]) -> float:
    """Return a yaw whose local -Y front points at the nearest road."""

    x, y = center_xy_m
    road_half_m = ROAD_WIDTH_MM * MM_TO_WORLD_M * 0.5
    candidates = [
        (abs(y) - road_half_m, 0.0 if y > 0.0 else math.pi),
    ]
    for road_x in three_crossroad_centers():
        direction_x = road_x - x
        candidates.append(
            (
                abs(direction_x) - road_half_m,
                math.pi * 0.5 if direction_x > 0.0 else -math.pi * 0.5,
            )
        )
    return min(candidates, key=lambda candidate: candidate[0])[1]


def street_buildings() -> tuple[BuildingPlacement, ...]:
    """Place a dense two-by-two group of low-poly buildings on every block."""

    pattern = ("house.obj", "building.obj", "market.obj")
    offsets = (
        (-BUILDING_GRID_OFFSET_M, -BUILDING_GRID_OFFSET_M),
        (BUILDING_GRID_OFFSET_M, -BUILDING_GRID_OFFSET_M),
        (-BUILDING_GRID_OFFSET_M, BUILDING_GRID_OFFSET_M),
        (BUILDING_GRID_OFFSET_M, BUILDING_GRID_OFFSET_M),
    )
    placements = []
    for block_index, block_center in enumerate(three_crossroad_block_centers()):
        for slot_index, offset in enumerate(offsets):
            asset = pattern[(block_index * len(offsets) + slot_index) % len(pattern)]
            center = (
                block_center[0] + offset[0],
                block_center[1] + offset[1],
            )
            yaw = road_facing_yaw(center)
            local_footprint = tuple(
                extent * BUILDING_XY_SCALE for extent in _ASSET_FOOTPRINTS[asset]
            )
            footprint = (
                local_footprint[::-1]
                if abs(math.sin(yaw)) > 0.5
                else local_footprint
            )
            placements.append(
                BuildingPlacement(
                    asset=asset,
                    center_xy_m=center,
                    footprint_xy_m=footprint,
                    yaw_rad=yaw,
                )
            )
    return tuple(placements)
