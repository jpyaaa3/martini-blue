"""Genesis scene and application loop."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any

import numpy as np

from .building_mesh import merge_buildings_by_material
from .buildings import street_buildings
from .map_mesh import merge_tiles_by_material
from .mounted_camera import (
    attach_to_first_link,
    forward_camera_offset,
    render_rgb,
    third_person_camera_offset,
)
from .road_map import (
    ASPHALT,
    CURB,
    ROAD_TOP_Z_M,
    SIDEWALK,
    WHITE,
    YELLOW,
    three_crossroad_render_tiles,
    three_crossroad_surround_tiles,
)
from .tree_mesh import merge_trees_by_material
from .trees import street_trees
from .vehicle import VehicleConfig, VehicleState
from .web_viewer import WebViewer


@dataclass(frozen=True)
class AppConfig:
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
    asphalt_color: tuple[float, float, float, float] = (0.02, 0.02, 0.025, 1.0)
    road_white: tuple[float, float, float, float] = (0.92, 0.92, 0.90, 1.0)
    road_yellow: tuple[float, float, float, float] = (1.0, 0.72, 0.02, 1.0)
    curb_gray: tuple[float, float, float, float] = (0.52, 0.54, 0.56, 1.0)
    sidewalk_brown: tuple[float, float, float, float] = (0.38, 0.22, 0.10, 1.0)


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
        road_surfaces = {
            ASPHALT: gs.surfaces.Rough(color=self.config.asphalt_color),
            WHITE: gs.surfaces.Rough(color=self.config.road_white),
            YELLOW: gs.surfaces.Rough(color=self.config.road_yellow),
            CURB: gs.surfaces.Rough(color=self.config.curb_gray),
            SIDEWALK: gs.surfaces.Rough(color=self.config.sidewalk_brown),
        }
        map_tiles = (
            *three_crossroad_render_tiles(),
            *three_crossroad_surround_tiles(),
        )
        for material, mesh in merge_tiles_by_material(map_tiles).items():
            self.scene.add_entity(
                gs.morphs.MeshSet(
                    files=(mesh,),
                    fixed=True,
                    collision=False,
                ),
                surface=road_surfaces[material],
            )
        asset_dir = Path(__file__).with_name("assets")
        building_surfaces = {
            "house_wall": gs.surfaces.Rough(color=(0.78, 0.68, 0.50, 1.0)),
            "roof_red": gs.surfaces.Rough(color=(0.48, 0.10, 0.07, 1.0)),
            "tower_wall": gs.surfaces.Rough(color=(0.38, 0.43, 0.48, 1.0)),
            "market_wall": gs.surfaces.Rough(color=(0.72, 0.44, 0.12, 1.0)),
            "door": gs.surfaces.Rough(color=(0.24, 0.12, 0.05, 1.0)),
            "glass": gs.surfaces.Smooth(color=(0.20, 0.58, 0.82, 1.0)),
        }
        for material, mesh in merge_buildings_by_material(
            asset_dir, street_buildings()
        ).items():
            self.scene.add_entity(
                gs.morphs.MeshSet(
                    files=(mesh,),
                    fixed=True,
                    collision=False,
                ),
                surface=building_surfaces[material],
            )
        tree_surfaces = {
            "tree_pad": gs.surfaces.Rough(color=(0.72, 0.62, 0.45, 1.0)),
            "tree_trunk": gs.surfaces.Rough(color=(0.30, 0.15, 0.06, 1.0)),
            "leaf_large": gs.surfaces.Rough(color=(0.10, 0.42, 0.12, 0.75)),
            "leaf_small": gs.surfaces.Rough(color=(0.16, 0.55, 0.18, 0.75)),
        }
        for material, mesh in merge_trees_by_material(
            asset_dir / "tree.obj", street_trees()
        ).items():
            self.scene.add_entity(
                gs.morphs.MeshSet(
                    files=(mesh,),
                    fixed=True,
                    collision=False,
                ),
                surface=tree_surfaces[material],
            )
        car_mesh = asset_dir / "car.obj"
        self.block = self.scene.add_entity(
            gs.morphs.Mesh(
                file=str(car_mesh),
                scale=self.config.car_mesh_scale,
                pos=self.vehicle_state.position(center_z=ROAD_TOP_Z_M),
                fixed=True,
                collision=False,
                file_meshes_are_zup=True,
            ),
            surface=gs.surfaces.Rough(color=(0.15, 0.48, 0.90, 1.0)),
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
        viewer = WebViewer(host=self.config.web_host, port=self.config.web_port)
        viewer.start()
        print(f"[vision] HTML viewer: http://localhost:{viewer.port}", flush=True)
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
                    viewer.publish_frame("mounted", render_rgb(self.camera))
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
