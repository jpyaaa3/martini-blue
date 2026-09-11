import numpy as np
import pytest

from vision_demo.mounted_camera import (
    forward_camera_offset,
    render_rgb,
    render_rgb_depth,
    rgb_u8,
    third_person_camera_offset,
)


def test_rgb_depth_render_follows_attachment_and_keeps_depth_in_metres():
    class Camera:
        moved = False

        def move_to_attach(self):
            self.moved = True

        def render(self, **kwargs):
            assert self.moved
            assert kwargs == {"rgb": True, "depth": True}
            return np.zeros((2,3,3), dtype=np.uint8), np.full((2,3), 2.5), None, None

    rgb, depth = render_rgb_depth(Camera())
    assert rgb.shape == (2,3,3)
    assert depth.dtype == np.float32
    np.testing.assert_array_equal(depth, 2.5)


def test_camera_offset_looks_along_block_positive_x() -> None:
    transform = forward_camera_offset()
    assert transform[:3, 3] == pytest.approx((0.30, 0.0, 0.30))
    camera_forward_in_block = transform[:3, :3] @ np.array((0.0, 0.0, -1.0))
    camera_up_in_block = transform[:3, :3] @ np.array((0.0, 1.0, 0.0))
    assert camera_forward_in_block == pytest.approx((1.0, 0.0, 0.0))
    assert camera_up_in_block == pytest.approx((0.0, 0.0, 1.0))
    assert np.linalg.det(transform[:3, :3]) == pytest.approx(1.0)


def test_third_person_camera_is_behind_and_looks_at_vehicle() -> None:
    transform = third_person_camera_offset()
    position = transform[:3, 3]
    camera_forward = transform[:3, :3] @ np.array((0.0, 0.0, -1.0))
    expected_forward = np.array((0.25, 0.0, 0.19)) - position
    expected_forward /= np.linalg.norm(expected_forward)

    assert position == pytest.approx((-2.2, 0.0, 0.75))
    assert camera_forward == pytest.approx(expected_forward)
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


def test_observer_render_does_not_follow_an_attachment() -> None:
    class Camera:
        def move_to_attach(self):
            raise AssertionError("observer camera is not attached")

        def render(self, **kwargs):
            assert "force_render" not in kwargs
            return np.zeros((2, 3, 3), dtype=np.uint8), None, None, None

    frame = render_rgb(Camera(), follow_attachment=False)
    assert frame.shape == (2, 3, 3)
