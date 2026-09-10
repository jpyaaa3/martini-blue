"""Batch reusable OBJ buildings into one static mesh per material."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import trimesh

from .buildings import BuildingPlacement


def merge_buildings_by_material(
    asset_dir: Path,
    placements: Iterable[BuildingPlacement],
) -> dict[str, trimesh.Trimesh]:
    """Load placed OBJ assets and collapse all instances to six draw meshes."""

    grouped: dict[str, list[trimesh.Trimesh]] = defaultdict(list)
    cached: dict[str, trimesh.Scene] = {}
    for placement in placements:
        scene = cached.get(placement.asset)
        if scene is None:
            scene = trimesh.load_scene(asset_dir / placement.asset, process=False)
            cached[placement.asset] = scene

        cosine = np.cos(placement.yaw_rad)
        sine = np.sin(placement.yaw_rad)
        transform = np.array(
            (
                (
                    cosine * placement.scale_xy,
                    -sine * placement.scale_xy,
                    0.0,
                    placement.center_xy_m[0],
                ),
                (
                    sine * placement.scale_xy,
                    cosine * placement.scale_xy,
                    0.0,
                    placement.center_xy_m[1],
                ),
                (0.0, 0.0, 1.0, placement.base_z_m),
                (0.0, 0.0, 0.0, 1.0),
            ),
            dtype=np.float64,
        )
        for material, geometry in scene.geometry.items():
            part = geometry.copy()
            part.apply_transform(transform)
            grouped[str(material)].append(part)

    return {
        material: trimesh.util.concatenate(parts)
        for material, parts in grouped.items()
    }
