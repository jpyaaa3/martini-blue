"""Genesis scene and application loop."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

import numpy as np

from .camera_window import CameraWindow
from .mounted_camera import attach_to_first_link, forward_camera_offset, render_rgb
from .vehicle import VehicleConfig, VehicleState


@dataclass(frozen=True)
class AppConfig:
    backend: str = "gpu"
    camera_width: int = 960
    camera_height: int = 540
    camera_fov_deg: float = 75.0
    camera_max_fps: float = 30.0
    block_size: tuple[float, float, float] = (1.0, 0.55, 0.30)


class VisionDemo:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.vehicle_config = VehicleConfig()
        self.vehicle_state = VehicleState()
        self._reset_was_down = False
        self.gs: Any = None
        self.scene: Any = None
        self.block: Any = None
        self.camera: Any = None

    def _create_scene(self) -> None:
        print("[vision] importing Genesis...", flush=True)
        import genesis as gs

        self.gs = gs
        backend = gs.gpu if self.config.backend == "gpu" else gs.cpu
        print(f"[vision] initializing Genesis backend={self.config.backend}...", flush=True)
        gs.init(backend=backend, logging_level="warning")
        print("[vision] creating scene...", flush=True)
        self.scene = gs.Scene(
            sim_options=gs.options.SimOptions(dt=1.0 / 60.0, gravity=(0.0, 0.0, 0.0)),
            viewer_options=gs.options.ViewerOptions(
                camera_pos=(4.5, -5.5, 3.2),
                camera_lookat=(0.0, 0.0, 0.25),
                camera_fov=40.0,
                refresh_rate=60,
            ),
            show_viewer=True,
        )
        self.scene.add_entity(gs.morphs.Plane())
        self.block = self.scene.add_entity(
            gs.morphs.Box(
                pos=self.vehicle_state.position(center_z=self.config.block_size[2] * 0.5),
                size=self.config.block_size,
                fixed=True,
            ),
            surface=gs.surfaces.Rough(color=(0.15, 0.48, 0.90, 1.0)),
        )
        self.camera = self.scene.add_camera(
            res=(self.config.camera_width, self.config.camera_height),
            fov=self.config.camera_fov_deg,
            GUI=False,
            debug=False,
        )
        print("[vision] building scene...", flush=True)
        self.scene.build()
        attach_to_first_link(self.camera, self.block, forward_camera_offset())
        self._apply_vehicle_pose()
        self.scene.step()
        print(
            f"[vision] Genesis scene ready | backend={self.config.backend} | "
            f"camera={self.config.camera_width}x{self.config.camera_height}",
            flush=True,
        )

    def _apply_vehicle_pose(self) -> None:
        center_z = self.config.block_size[2] * 0.5
        self.block.set_pos(np.asarray(self.vehicle_state.position(center_z=center_z)))
        self.block.set_quat(np.asarray(self.vehicle_state.quaternion_wxyz()))

    def run(self) -> None:
        self._create_scene()
        window = CameraWindow()
        last_tick = time.perf_counter()
        last_capture = 0.0
        capture_period = 1.0 / max(self.config.camera_max_fps, 1.0)
        measured_fps = 0.0
        first_frame_reported = False
        try:
            while not window.should_close():
                now = time.perf_counter()
                dt = now - last_tick
                last_tick = now
                controls = window.poll_controls()
                reset_down = window.reset_requested()
                if reset_down and not self._reset_was_down:
                    self.vehicle_state.reset()
                self._reset_was_down = reset_down

                self.vehicle_state.update(controls, dt, self.vehicle_config)
                self._apply_vehicle_pose()
                self.scene.step()

                if now - last_capture >= capture_period:
                    capture_interval = now - last_capture
                    window.upload(render_rgb(self.camera))
                    measured_fps = 1.0 / max(capture_interval, 1e-6)
                    last_capture = now
                    if not first_frame_reported:
                        first_frame_reported = True
                        print("[vision] mounted-camera first frame ready", flush=True)
                window.draw(self.vehicle_state, camera_fps=measured_fps)
        except KeyboardInterrupt:
            pass
        finally:
            window.close()
