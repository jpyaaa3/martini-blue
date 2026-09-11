import numpy as np
import pytest

from vision_demo.motion_blur import BlurSettings, blur_displacement, camera_twist, apply_motion_blur


def test_translation_scales_with_exposure_and_inverse_depth():
    depth = np.full((48, 64), 2., dtype=np.float32)
    a, _ = blur_displacement(depth, 60, (1,0,0), (0,0,0), 1/60)
    b, _ = blur_displacement(depth*2, 60, (1,0,0), (0,0,0), 1/60)
    c, _ = blur_displacement(depth, 60, (1,0,0), (0,0,0), 1/30)
    np.testing.assert_allclose(a, b*2)
    np.testing.assert_allclose(c, a*2)
    assert a[0,0] == pytest.approx(-.34641016)


def test_rotation_is_depth_independent_and_invalid_depth_is_finite():
    d = np.full((10, 10), 2., dtype=np.float32)
    a = blur_displacement(d, 60, (0,0,0), (0,1,0), .02)
    b = blur_displacement(d*5, 60, (0,0,0), (0,1,0), .02)
    np.testing.assert_allclose(a, b)
    d[0,:4] = (0, -1, np.nan, np.inf)
    flow = blur_displacement(d, 60, (1,1,1), (0,1,0), .02)
    assert np.isfinite(flow).all()


def test_camera_mount_rotation_and_forward_translation():
    v, w = camera_twist((0,0,0), (.1,0,0), .1, (.3,0,.3))
    np.testing.assert_allclose(v, (0,0,1), atol=1e-8)
    v, w = camera_twist((0,0,0), (0,0,.1), .1, (.3,0,.3))
    np.testing.assert_allclose(v, (-.3,0,0), atol=1e-8)
    np.testing.assert_allclose(w, (0,-1,0), atol=1e-8)


def test_stationary_image_unchanged_and_moving_edge_blurs():
    image = np.zeros((32,64,3), dtype=np.uint8)
    image[:,32:] = 255
    depth = np.ones((32,64), dtype=np.float32)
    assert apply_motion_blur(image, depth, 60, (0,0,0), (0,0,0), .02) is image
    blurred = apply_motion_blur(image, depth, 60, (5,0,0), (0,0,0), .02)
    assert 0 < blurred[16,31,0] < 255
    assert blurred.dtype == np.uint8
    assert blurred[16,0,0] == 0


def test_large_frame_keeps_output_size_and_stationary_pixels():
    image = np.zeros((270, 960, 3), dtype=np.uint8)
    image[:,480:] = 255
    depth = np.ones((270,960), dtype=np.float32)
    assert apply_motion_blur(image, depth, 60, (0,0,0), (0,0,0), .02) is image
    out = apply_motion_blur(image, depth, 60, (5,0,0), (0,0,0), .02)
    assert out.shape == image.shape
    assert 0 < out[100,479,0] < 255


@pytest.mark.parametrize('value', [0, -1, 1, float('nan'), True, '1/60'])
def test_invalid_exposures_rejected(value):
    with pytest.raises(ValueError):
        BlurSettings.parse({'enabled': True, 'exposure_time_s': value})
