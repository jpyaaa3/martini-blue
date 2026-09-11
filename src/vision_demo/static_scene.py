"""Bake the static world into one OBJ, one material, and one PNG atlas.

Rebuild committed assets with: python -m vision_demo.static_scene
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import trimesh

from .building_mesh import merge_buildings_by_material
from .map_file import DEFAULT_MAP, MapDefinition, load_map, road_tiles
from .map_mesh import merge_tiles_by_material
from .road_map import ASPHALT, ROAD_TOP_Z_M
from .tree_mesh import merge_trees_by_material


COLORS = {
    "asphalt": (5, 5, 6), "white": (235, 235, 230), "yellow": (255, 184, 5),
    "curb": (133, 138, 143), "sidewalk": (97, 56, 26),
    "house_wall": (199, 173, 128), "roof_red": (122, 26, 18),
    "tower_wall": (97, 110, 122), "market_wall": (184, 112, 31),
    "door": (61, 31, 13), "glass": (51, 148, 209),
    "tree_pad": (184, 158, 115), "tree_trunk": (77, 38, 15),
    "leaf_large": (26, 107, 31), "leaf_small": (41, 140, 46),
}
ATLAS_WIDTH = 4096
ROAD_PIXELS = 2048
ATLAS_HEIGHT = 2112


def build_static_scene(
    asset_dir: Path, definition: MapDefinition | None = None,
) -> tuple[trimesh.Trimesh, Image.Image]:
    definition = definition if definition is not None else load_map(DEFAULT_MAP)
    tiles = road_tiles(definition)
    low = np.min([np.array(t.center_xy_m) - np.array(t.size_xy_m) / 2 for t in tiles], axis=0)
    high = np.max([np.array(t.center_xy_m) + np.array(t.size_xy_m) / 2 for t in tiles], axis=0)
    # Leave a border so filtering at the road ends samples asphalt, not palette cells.
    def pixels(xy):
        normalized = (np.asarray(xy) - low) / (high - low)
        return np.stack((2 + normalized[..., 0] * (ATLAS_WIDTH - 4),
                         2 + (1 - normalized[..., 1]) * (ROAD_PIXELS - 4)), axis=-1)

    atlas = Image.new("RGB", (ATLAS_WIDTH, ATLAS_HEIGHT), COLORS[ASPHALT])
    draw = ImageDraw.Draw(atlas)
    for tile in tiles:
        if tile.material == ASPHALT:
            continue
        a = pixels(np.array(tile.center_xy_m) - np.array(tile.size_xy_m) / 2)
        b = pixels(np.array(tile.center_xy_m) + np.array(tile.size_xy_m) / 2)
        draw.rectangle((round(a[0]), round(b[1]), round(b[0]), round(a[1])), fill=COLORS[tile.material])

    material = trimesh.visual.material.SimpleMaterial(image=atlas, diffuse=(255, 255, 255, 255))
    material.name = "static_atlas"
    parts = []
    # Road markings are pixels; only the union of the road beds needs geometry.
    for tile in tiles:
        if tile.material != ASPHALT:
            continue
        x, y = tile.center_xy_m
        w, h = np.array(tile.size_xy_m) / 2
        vertices = np.array([(x-w, y-h, ROAD_TOP_Z_M), (x+w, y-h, ROAD_TOP_Z_M),
                             (x+w, y+h, ROAD_TOP_Z_M), (x-w, y+h, ROAD_TOP_Z_M)])
        px = pixels(vertices[:, :2])
        uv = np.column_stack((px[:, 0] / ATLAS_WIDTH, 1 - px[:, 1] / ATLAS_HEIGHT))
        part = trimesh.Trimesh(vertices=vertices, faces=((0, 1, 2), (0, 2, 3)), process=False)
        part.visual = trimesh.visual.TextureVisuals(uv=uv, material=material)
        parts.append(part)

    groups = merge_tiles_by_material(definition.surrounds)
    groups.update(merge_buildings_by_material(asset_dir, definition.buildings))
    if definition.trees:
        groups.update(merge_trees_by_material(asset_dir / "tree.obj", definition.trees))
    for index, (name, part) in enumerate(groups.items()):
        left = index * 128
        draw.rectangle((left, ROAD_PIXELS, left + 127, ATLAS_HEIGHT - 1), fill=COLORS[name])
        uv = np.tile(((left + 64) / ATLAS_WIDTH, 1 - (ROAD_PIXELS + 32) / ATLAS_HEIGHT), (len(part.vertices), 1))
        part.visual = trimesh.visual.TextureVisuals(uv=uv, material=material)
        parts.append(part)

    # Concatenate explicitly: automatic visual concatenation can repack materials.
    offsets = np.cumsum([0] + [len(p.vertices) for p in parts[:-1]])
    mesh = trimesh.Trimesh(
        vertices=np.concatenate([p.vertices for p in parts]),
        faces=np.concatenate([p.faces + offset for p, offset in zip(parts, offsets)]),
        process=False,
    )
    mesh.visual = trimesh.visual.TextureVisuals(
        uv=np.concatenate([p.visual.uv for p in parts]), material=material,
    )
    return mesh, atlas


def export_static_scene(
    asset_dir: Path, definition: MapDefinition | None = None,
    output_dir: Path | None = None,
) -> None:
    mesh, atlas = build_static_scene(asset_dir, definition)
    output_dir = output_dir if output_dir is not None else asset_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    atlas.save(output_dir / "static_scene.png")
    # Keep stable, reviewable filenames and exactly one material in the OBJ.
    lines = ["mtllib static_scene.mtl", "o static_scene", "usemtl static_atlas"]
    lines.extend("v %.9f %.9f %.9f" % tuple(v) for v in mesh.vertices)
    lines.extend("vt %.9f %.9f" % tuple(uv) for uv in mesh.visual.uv)
    lines.extend("f " + " ".join(f"{i+1}/{i+1}" for i in face) for face in mesh.faces)
    (output_dir / "static_scene.obj").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output_dir / "static_scene.mtl").write_text(
        "newmtl static_atlas\nKa 1 1 1\nKd 1 1 1\nKs 0 0 0\nd 1\nillum 1\nmap_Kd static_scene.png\n",
        encoding="utf-8",
    )
    print(f"Static scene: 1 mesh, 1 material, {len(mesh.faces)} triangles; atlas {atlas.size}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("assets"))
    args = parser.parse_args()
    export_static_scene(Path(__file__).with_name("assets"), load_map(args.map), args.output)
