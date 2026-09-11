"""Single-render, static-world motion blur using axial depth and camera twist.

Coordinates are optical: X right, Y down, Z forward. The line gather is an
approximation: it cannot reconstruct newly visible surfaces or moving objects.
"""

from dataclasses import dataclass
import math

import numpy as np

from .mounted_camera import forward_camera_offset


@dataclass(frozen=True)
class BlurSettings:
    enabled: bool = False
    exposure_time_s: float = 1 / 120

    @classmethod
    def parse(cls, data):
        if set(data) != {"enabled", "exposure_time_s"} or type(data["enabled"]) is not bool:
            raise ValueError("Supply enabled (boolean) and exposure_time_s (number)")
        exposure = data["exposure_time_s"]
        if isinstance(exposure, bool) or not isinstance(exposure, (int, float)) or not math.isfinite(exposure):
            raise ValueError("Exposure must be a finite number")
        if not 1 / 4000 <= exposure <= 1 / 15:
            raise ValueError("Exposure must be between 1/4000 and 1/15 second")
        return cls(data["enabled"], float(exposure))


def camera_twist(previous, current, dt, mount):
    """World pose delta / wall time, including the rotating mount's lever arm."""
    if dt <= 0 or dt > 0.5:
        return np.zeros(3), np.zeros(3)
    yaw = current[2]
    rotation = np.array(((math.cos(yaw), -math.sin(yaw), 0),
                         (math.sin(yaw), math.cos(yaw), 0), (0, 0, 1)))
    rate = math.atan2(math.sin(yaw-previous[2]), math.cos(yaw-previous[2])) / dt
    omega = np.array((0., 0., rate))
    velocity = np.array(((current[0]-previous[0])/dt, (current[1]-previous[1])/dt, 0.))
    velocity += np.cross(omega, rotation @ np.asarray(mount))
    optical_to_world = rotation @ forward_camera_offset(tuple(mount))[:3, :3] @ np.diag((1., -1., -1.))
    return optical_to_world.T @ velocity, optical_to_world.T @ omega


def blur_displacement(depth, fov_y_deg, velocity, omega, exposure, max_blur_px=32):
    h, w = depth.shape
    f = h / (2 * math.tan(math.radians(fov_y_deg)/2))
    v, u = np.indices((h, w), dtype=np.float32)
    x, y = (u-(w-1)/2)/f, (v-(h-1)/2)/f
    inverse = np.zeros_like(depth, dtype=np.float32)
    np.divide(1., depth, out=inverse, where=np.isfinite(depth) & (depth > 1e-4))
    vx, vy, vz = velocity
    wx, wy, wz = omega
    dx = f * ((-vx+x*vz)*inverse + x*y*wx-(1+x*x)*wy+y*wz) * exposure
    dy = f * ((-vy+y*vz)*inverse + (1+y*y)*wx-x*y*wy-x*wz) * exposure
    length = np.hypot(dx, dy)
    scale = np.minimum(1., max_blur_px / np.maximum(length, 1e-8))
    return dx*scale, dy*scale


def apply_motion_blur(rgb, depth, fov_y_deg, velocity, omega, exposure):
    """Integrate 2–8 bilinear samples in linear light, centred on current pose."""
    import cv2

    # Avoid oversubscribing the simulation's own CPU workers.
    cv2.setNumThreads(1)
    original_size = (rgb.shape[1], rgb.shape[0])
    # Bound the cost independently of camera resolution. OFF/stationary uses
    # the untouched full-resolution image in the caller.
    scale = min(1., 480 / rgb.shape[1])
    if scale < 1:
        size = (480, max(1, round(rgb.shape[0]*scale)))
        source = rgb
        rgb = cv2.resize(rgb, size, interpolation=cv2.INTER_AREA)
        depth = cv2.resize(depth, size, interpolation=cv2.INTER_NEAREST)
    dx, dy = blur_displacement(depth, fov_y_deg, velocity, omega, exposure, max_blur_px=32*scale)
    length = float(np.max(np.hypot(dx, dy)))
    if length < 0.25:
        return source if scale < 1 else rgb
    samples = min(8, max(2, math.ceil(length)+1))
    h, w = depth.shape
    y, x = np.indices((h, w), dtype=np.float32)
    srgb = np.arange(256, dtype=np.float32)/255
    lut = np.where(srgb <= .04045, srgb/12.92, ((srgb+.055)/1.055)**2.4)
    linear = lut[rgb]
    result = np.zeros_like(linear)
    for t in np.linspace(-.5, .5, samples):
        sx, sy = np.clip(x+t*dx, 0, w-1), np.clip(y+t*dy, 0, h-1)
        result += cv2.remap(linear, sx, sy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    result /= samples
    result = np.where(result <= .0031308, result*12.92, 1.055*result**(1/2.4)-.055)
    output = np.clip(np.rint(result*255), 0, 255).astype(np.uint8)
    if scale < 1:
        output = cv2.resize(output, original_size, interpolation=cv2.INTER_LINEAR)
    return output
