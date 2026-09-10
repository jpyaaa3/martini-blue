"""Merge repeated tree OBJ instances into one static mesh per material."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import trimesh

from .trees import TreePlacement


def merge_trees_by_material(
    asset_path: Path,
    placements: Iterable[TreePlacement],
) -> dict[str, trimesh.Trimesh]:
    scene = trimesh.load_scene(asset_path, process=False)
    grouped: dict[str, list[trimesh.Trimesh]] = defaultdict(list)
    for placement in placements:
        transform = np.eye(4, dtype=np.float64)
        transform[:3, 3] = (*placement.center_xy_m, placement.base_z_m)
        for material, geometry in scene.geometry.items():
            part = geometry.copy()
            part.apply_transform(transform)
            grouped[str(material)].append(part)
    return {
        material: trimesh.util.concatenate(parts)
        for material, parts in grouped.items()
    }
