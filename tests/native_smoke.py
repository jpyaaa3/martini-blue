"""Manual display smoke check: PYTHONPATH=src python tests/native_smoke.py."""
import time
import numpy as np
from vision_demo.native_viewer import NativeViewer
from vision_demo.vehicle import VehicleState


if __name__ == '__main__':
    viewer = NativeViewer()
    try:
        viewer.start()
        for i in range(120):
            if viewer.stop_requested():
                raise RuntimeError('Native window exited unexpectedly')
            viewer.publish_frame('observer', np.full((180,320,3),(25,50,i%255),dtype=np.uint8))
            viewer.publish_frame('mounted', np.full((180,320,3),(i%255,50,25),dtype=np.uint8))
            viewer.publish_state(VehicleState(), camera_fps=30)
            viewer.controls()
            time.sleep(1/30)
        print('Native window, texture upload and event loop passed')
    finally:
        viewer.close()
