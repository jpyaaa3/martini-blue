import numpy as np
import pytest

from vision_demo.mounted_camera import forward_camera_offset, rgb_u8


def test_camera_offset_looks_along_block_positive_x() -> None:
    transform = forward_camera_offset()
    camera_forward_in_block = transform[:3, :3] @ np.array((0.0, 0.0, -1.0))
    camera_up_in_block = transform[:3, :3] @ np.array((0.0, 1.0, 0.0))
    assert camera_forward_in_block == pytest.approx((1.0, 0.0, 0.0))
    assert camera_up_in_block == pytest.approx((0.0, 0.0, 1.0))
    assert np.linalg.det(transform[:3, :3]) == pytest.approx(1.0)


def test_float_rgb_is_converted_to_contiguous_uint8() -> None:
    image = np.array([[[0.0, 0.5, 1.0, 0.25]]], dtype=np.float32)
    converted = rgb_u8(image)
    assert converted.dtype == np.uint8
    assert converted.flags.c_contiguous
    assert converted.tolist() == [[[0, 127, 255]]]


def test_bad_rgb_shape_is_rejected() -> None:
    with pytest.raises(ValueError, match="HxWx3"):
        rgb_u8(np.zeros((10, 10), dtype=np.uint8))

