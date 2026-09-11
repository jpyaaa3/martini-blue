"""Genesis camera attachment and render-output conversion."""

from __future__ import annotations

from typing import Any

import numpy as np


def look_at_camera_offset(
    position_xyz: tuple[float, float, float],
    target_xyz: tuple[float, float, float],
) -> np.ndarray:
    """Return a camera-to-vehicle transform looking at a vehicle-frame point."""

    position = np.asarray(position_xyz, dtype=np.float64)
    forward = np.asarray(target_xyz, dtype=np.float64) - position
    forward_norm = float(np.linalg.norm(forward))
    if forward_norm <= 1e-9:
        raise ValueError("camera position and target must be different")
    forward /= forward_norm

    world_up = np.array((0.0, 0.0, 1.0), dtype=np.float64)
    right = np.cross(forward, world_up)
    right_norm = float(np.linalg.norm(right))
    if right_norm <= 1e-9:
        raise ValueError("camera view direction cannot be parallel to vehicle up")
    right /= right_norm
    camera_up = np.cross(right, forward)

    transform = np.eye(4, dtype=np.float64)
    transform[:3, :3] = np.column_stack((right, camera_up, -forward))
    transform[:3, 3] = position
    return transform


def forward_camera_offset(
    position_xyz: tuple[float, float, float] = (0.30, 0.0, 0.30),
) -> np.ndarray:
    """Return camera-to-vehicle transform looking along vehicle +X.

    The vehicle frame is +X forward, +Y left and +Z up. Genesis' camera follows
    the OpenGL convention: +X right, +Y up and -Z forward.
    """

    return look_at_camera_offset(
        position_xyz,
        (position_xyz[0] + 1.0, position_xyz[1], position_xyz[2]),
    )


def third_person_camera_offset(
    position_xyz: tuple[float, float, float] = (-2.2, 0.0, 0.75),
    target_xyz: tuple[float, float, float] = (0.25, 0.0, 0.19),
) -> np.ndarray:
    """Return a rear, elevated chase-camera transform in the vehicle frame."""

    return look_at_camera_offset(position_xyz, target_xyz)


def attach_to_first_link(camera: Any, entity: Any, offset: np.ndarray) -> None:
    links = getattr(entity, "links", None)
    if not links:
        raise RuntimeError("Genesis vehicle entity exposes no rigid link for the camera")
    camera.attach(links[0], np.asarray(offset, dtype=np.float64))


def _as_numpy(value: Any) -> np.ndarray:
    current = value
    detach = getattr(current, "detach", None)
    if callable(detach):
        current = detach()
    cpu = getattr(current, "cpu", None)
    if callable(cpu):
        current = cpu()
    numpy = getattr(current, "numpy", None)
    if callable(numpy):
        current = numpy()
    return np.asarray(current)


def rgb_u8(value: Any) -> np.ndarray:
    """Normalize Genesis RGB/RGBA NumPy or Torch output for OpenGL upload."""

    image = _as_numpy(value)
    if image.ndim != 3 or image.shape[2] not in (3, 4):
        raise ValueError(f"expected HxWx3 or HxWx4 RGB image, got {image.shape}")
    image = image[:, :, :3]
    if np.issubdtype(image.dtype, np.floating):
        image = np.nan_to_num(image, nan=0.0, posinf=1.0, neginf=0.0)
        if image.size and float(image.max()) <= 1.5:
            image = image * 255.0
        image = np.clip(image, 0.0, 255.0).astype(np.uint8)
    elif image.dtype != np.uint8:
        image = np.clip(image, 0, 255).astype(np.uint8)
    return np.ascontiguousarray(image)


def render_rgb(camera: Any, *, follow_attachment: bool = True) -> np.ndarray:
    if follow_attachment and hasattr(camera, "move_to_attach"):
        camera.move_to_attach()
    result = camera.render(rgb=True, depth=False)
    rgb = result[0] if isinstance(result, (tuple, list)) else result
    if rgb is None:
        raise RuntimeError("Genesis camera returned no RGB frame")
    return rgb_u8(rgb)


def render_rgb_depth(camera: Any) -> tuple[np.ndarray, np.ndarray]:
    camera.move_to_attach()
    result = camera.render(rgb=True, depth=True)
    if not isinstance(result, (tuple, list)) or result[0] is None or result[1] is None:
        raise RuntimeError("Genesis camera returned no RGB/depth frame")
    rgb = rgb_u8(result[0])
    depth = _as_numpy(result[1]).astype(np.float32)
    if depth.shape == (*rgb.shape[:2], 1):
        depth = depth[..., 0]
    if depth.shape != rgb.shape[:2]:
        raise RuntimeError(f"Unexpected depth shape: {depth.shape}")
    return rgb, depth
