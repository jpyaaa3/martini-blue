"""Convert logical map boxes into one static mesh per material."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

import numpy as np
import trimesh

from .road_map import MapTile


def merge_tiles_by_material(tiles: Iterable[MapTile]) -> dict[str, trimesh.Trimesh]:
    """Merge disconnected boxes sharing a material into a single draw entity."""

    grouped: dict[str, list[trimesh.Trimesh]] = defaultdict(list)
    for tile in tiles:
        transform = np.eye(4, dtype=np.float64)
        transform[:3, 3] = tile.position_xyz_m
        grouped[tile.material].append(
            trimesh.creation.box(extents=tile.size_xyz_m, transform=transform)
        )
    return {
        material: trimesh.util.concatenate(parts)
        for material, parts in grouped.items()
    }
