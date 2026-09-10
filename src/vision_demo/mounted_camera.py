"""Genesis camera attachment and render-output conversion."""

from __future__ import annotations

from typing import Any

import numpy as np


def forward_camera_offset(
    position_xyz: tuple[float, float, float] = (0.32, 0.0, 0.28),
) -> np.ndarray:
    """Return camera-to-block transform looking along block +X.

    The block frame is +X forward, +Y left and +Z up. Genesis' camera follows
    the OpenGL convention: +X right, +Y up and -Z forward.
    """

    transform = np.eye(4, dtype=np.float64)
    transform[:3, :3] = np.array(
        (
            (0.0, 0.0, -1.0),
            (-1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        ),
        dtype=np.float64,
    )
    transform[:3, 3] = np.asarray(position_xyz, dtype=np.float64)
    return transform


def attach_to_first_link(camera: Any, entity: Any, offset: np.ndarray) -> None:
    links = getattr(entity, "links", None)
    if not links:
        raise RuntimeError("Genesis block entity exposes no rigid link for the camera")
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


def render_rgb(camera: Any) -> np.ndarray:
    if hasattr(camera, "move_to_attach"):
        camera.move_to_attach()
    try:
        result = camera.render(rgb=True, depth=False, force_render=True)
    except TypeError as exc:
        if "force_render" not in str(exc):
            raise
        result = camera.render(rgb=True, depth=False)
    rgb = result[0] if isinstance(result, (tuple, list)) else result
    if rgb is None:
        raise RuntimeError("Genesis camera returned no RGB frame")
    return rgb_u8(rgb)

