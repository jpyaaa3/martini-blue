"""Genesis scene and application loop."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any

import numpy as np

from .mounted_camera import (
    attach_to_first_link,
    forward_camera_offset,
    render_rgb,
    render_rgb_depth,
    third_person_camera_offset,
)
from .road_map import ROAD_TOP_Z_M
from .map_file import DEFAULT_MAP
from .map_cache import prepare_map
from .vehicle import VehicleConfig, VehicleState
from .viewer import start_viewer
from .motion_blur import camera_twist, apply_motion_blur


@dataclass(frozen=True)
class AppConfig:
    viewer: str = 'auto'
    backend: str = "gpu"
    camera_width: int = 960
    camera_height: int = 540
    camera_fov_deg: float = 75.0
    camera_max_fps: float = 30.0
    web_host: str = "127.0.0.1"
    web_port: int = 8765
    car_mesh_scale: float = 0.1
    camera_mount_obj: tuple[float, float, float] = (3.0, 0.0, 3.0)
    sky_color: tuple[float, float, float] = (0.529, 0.808, 0.922)
    ground_color: tuple[float, float, float, float] = (0.45, 0.45, 0.45, 1.0)
    map_path: Path = DEFAULT_MAP
    map_cache_dir: Path | None = None


class VisionDemo:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.vehicle_config = VehicleConfig()
        self.vehicle_state = VehicleState()
        self.gs: Any = None
        self.scene: Any = None
        self.block: Any = None
        self.camera: Any = None
        self.observer_camera: Any = None

    def _create_scene(self) -> None:
        asset_dir = Path(__file__).with_name("assets")
        map_assets = prepare_map(self.config.map_path, asset_dir, self.config.map_cache_dir)
        print("[vision] importing Genesis...", flush=True)
        import genesis as gs

        self.gs = gs
        backend = gs.gpu if self.config.backend == "gpu" else gs.cpu
        print(f"[vision] initializing Genesis backend={self.config.backend}...", flush=True)
        gs.init(backend=backend, logging_level="warning")
        print("[vision] creating scene...", flush=True)
        self.scene = gs.Scene(
            sim_options=gs.options.SimOptions(dt=1.0 / 60.0, gravity=(0.0, 0.0, 0.0)),
            vis_options=gs.options.VisOptions(
                background_color=self.config.sky_color,
                ambient_light=(0.35, 0.35, 0.35),
            ),
            viewer_options=gs.options.ViewerOptions(
                camera_pos=(4.5, -5.5, 3.2),
                camera_lookat=(0.0, 0.0, 0.25),
                camera_fov=40.0,
                refresh_rate=60,
            ),
            show_viewer=False,
        )
        self.scene.add_entity(
            gs.morphs.Plane(),
            surface=gs.surfaces.Rough(color=self.config.ground_color),
        )
        self.scene.add_entity(
            gs.morphs.Mesh(
                file=str(map_assets / "static_scene.obj"),
                fixed=True,
                collision=False,
                decimate=False,
                file_meshes_are_zup=True,
            ),
            surface=gs.surfaces.Rough(
                diffuse_texture=gs.textures.ImageTexture(
                    image_path=str(map_assets / "static_scene.png"),
                ),
            ),
        )
        car_mesh = asset_dir / "car_textured.obj"
        self.block = self.scene.add_entity(
            gs.morphs.Mesh(
                file=str(car_mesh),
                scale=self.config.car_mesh_scale,
                pos=self.vehicle_state.position(center_z=ROAD_TOP_Z_M),
                fixed=True,
                collision=False,
                file_meshes_are_zup=True,
            ),
            surface=gs.surfaces.Rough(
                diffuse_texture=gs.textures.ImageTexture(image_path=str(asset_dir / "car_texture.png")),
            ),
        )
        self.camera = self.scene.add_camera(
            res=(self.config.camera_width, self.config.camera_height),
            fov=self.config.camera_fov_deg,
            GUI=False,
            debug=False,
        )
        self.observer_camera = self.scene.add_camera(
            res=(self.config.camera_width, self.config.camera_height),
            pos=(-2.2, 0.0, 0.75),
            lookat=(0.25, 0.0, 0.19),
            up=(0.0, 0.0, 1.0),
            fov=40.0,
            GUI=False,
            debug=False,
        )
        print("[vision] building scene...", flush=True)
        self.scene.build()
        camera_position = tuple(
            coordinate * self.config.car_mesh_scale
            for coordinate in self.config.camera_mount_obj
        )
        attach_to_first_link(
            self.camera,
            self.block,
            forward_camera_offset(camera_position),
        )
        attach_to_first_link(
            self.observer_camera,
            self.block,
            third_person_camera_offset(),
        )
        self._apply_vehicle_pose()
        self.scene.step()
        print(
            f"[vision] Genesis scene ready | backend={self.config.backend} | "
            f"camera={self.config.camera_width}x{self.config.camera_height}",
            flush=True,
        )

    def _apply_vehicle_pose(self) -> None:
        self.block.set_pos(
            np.asarray(self.vehicle_state.position(center_z=ROAD_TOP_Z_M))
        )
        self.block.set_quat(np.asarray(self.vehicle_state.quaternion_wxyz()))

    def run(self) -> None:
        viewer = start_viewer(self.config.viewer, self.config.web_host, self.config.web_port)
        last_tick = time.perf_counter()
        last_capture = 0.0
        capture_period = 1.0 / max(self.config.camera_max_fps, 1.0)
        measured_fps = 0.0
        first_frame_reported = False
        try:
            self._create_scene()
            while not viewer.stop_requested():
                now = time.perf_counter()
                dt = now - last_tick
                last_tick = now
                controls = viewer.controls()
                previous_pose = (
                    self.vehicle_state.x,
                    self.vehicle_state.y,
                    self.vehicle_state.yaw,
                )
                if viewer.consume_reset():
                    self.vehicle_state.reset()
                    previous_pose = (0., 0., 0.)

                self.vehicle_state.update(controls, dt, self.vehicle_config)
                current_pose = (
                    self.vehicle_state.x,
                    self.vehicle_state.y,
                    self.vehicle_state.yaw,
                )
                if current_pose != previous_pose:
                    self._apply_vehicle_pose()
                    self.scene.step()

                if viewer.frame_requested() and now - last_capture >= capture_period:
                    capture_interval = now - last_capture
                    settings = viewer.blur_settings()
                    mount = tuple(v*self.config.car_mesh_scale for v in self.config.camera_mount_obj)
                    velocity, omega = camera_twist(previous_pose, current_pose, dt, mount)
                    if settings.enabled and (np.linalg.norm(velocity) + np.linalg.norm(omega)) > 1e-6:
                        mounted, depth = render_rgb_depth(self.camera)
                        mounted = apply_motion_blur(mounted, depth, self.config.camera_fov_deg,
                                                    velocity, omega, settings.exposure_time_s)
                    else:
                        mounted = render_rgb(self.camera)
                    viewer.publish_frame("mounted", mounted)
                    viewer.publish_frame(
                        "observer",
                        render_rgb(self.observer_camera),
                    )
                    measured_fps = 1.0 / max(capture_interval, 1e-6)
                    last_capture = now
                    if not first_frame_reported:
                        first_frame_reported = True
                        print("[vision] mounted-camera first frame ready", flush=True)
                viewer.publish_state(self.vehicle_state, camera_fps=measured_fps)
                frame_remaining = (1.0 / 60.0) - (time.perf_counter() - now)
                if frame_remaining > 0.0:
                    time.sleep(frame_remaining)
        except KeyboardInterrupt:
            pass
        finally:
            viewer.close()
