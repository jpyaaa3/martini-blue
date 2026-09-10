import json
import threading
import time
from urllib.request import Request, urlopen

import numpy as np

from vision_demo.vehicle import VehicleState
from vision_demo.web_viewer import WebViewer


def request(url: str, *, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    method = "GET" if body is None else "POST"
    value = Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    return urlopen(value, timeout=2.0)


def test_html_viewer_serves_page_and_accepts_controls() -> None:
    viewer = WebViewer(host="127.0.0.1", port=0)
    viewer.start()
    base = f"http://127.0.0.1:{viewer.port}"
    try:
        with request(base + "/") as response:
            assert response.status == 200
            page = response.read()
            assert b"Mounted Camera" in page
            assert b"'/frame/' + stream + '.jpg?after='" in page
            assert b"/stream/observer.mjpg" not in page

        with request(
            base + "/api/control",
            body={"keys": ["w", "a", "space", "invalid"], "reset": True},
        ) as response:
            assert response.status == 204
        assert viewer.controls().throttle is True
        assert viewer.controls().steer_left is True
        assert viewer.controls().handbrake is True
        assert viewer.consume_reset() is True
        assert viewer.consume_reset() is False
    finally:
        viewer.close()


def test_html_viewer_encodes_frame_and_publishes_telemetry() -> None:
    viewer = WebViewer(host="127.0.0.1", port=0)
    viewer.start()
    base = f"http://127.0.0.1:{viewer.port}"
    try:
        viewer.publish_frame("mounted", np.zeros((8, 12, 3), dtype=np.uint8))
        assert viewer._state.frames["mounted"] is not None
        assert viewer._state.frames["mounted"].startswith(b"\xff\xd8")
        assert viewer._state.frames["observer"] is None

        with request(base + "/frame/mounted.jpg?after=-1") as response:
            assert response.status == 200
            assert response.headers["Content-Type"] == "image/jpeg"
            assert response.headers["X-Frame-Seq"] == "1"
            assert int(response.headers["X-Captured-At-Ms"]) > 0
            assert response.read().startswith(b"\xff\xd8")

        viewer.publish_frame("mounted", np.full((8, 12, 3), 255, dtype=np.uint8))
        with request(base + "/frame/mounted.jpg?after=1") as response:
            assert response.headers["X-Frame-Seq"] == "2"
            assert response.read().startswith(b"\xff\xd8")

        viewer.publish_state(
            VehicleState(x=1.5, y=-2.0, speed_mps=3.0, steering=0.25),
            camera_fps=20.0,
        )
        with request(base + "/api/state") as response:
            state = json.loads(response.read())
        assert state == {
            "speed_mps": 3.0,
            "steering": 0.25,
            "x": 1.5,
            "y": -2.0,
            "camera_fps": 20.0,
        }
    finally:
        viewer.close()


def test_frame_demand_tracks_browser_requests() -> None:
    viewer = WebViewer(host="127.0.0.1", port=0)
    viewer.start()
    base = f"http://127.0.0.1:{viewer.port}"
    received: list[bytes] = []

    def fetch_frame() -> None:
        with request(base + "/frame/mounted.jpg?after=0") as response:
            received.append(response.read())

    thread = threading.Thread(target=fetch_frame)
    try:
        assert viewer.frame_requested() is False
        thread.start()
        deadline = time.monotonic() + 1.0
        while not viewer.frame_requested() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert viewer.frame_requested() is True
        viewer.publish_frame("mounted", np.zeros((8, 12, 3), dtype=np.uint8))
        thread.join(timeout=1.0)
        assert received and received[0].startswith(b"\xff\xd8")
    finally:
        viewer.close()
        thread.join(timeout=1.0)
