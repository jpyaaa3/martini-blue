"""HTTP viewer for mounted-camera video and keyboard control."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlsplit

import numpy as np
from PIL import Image

from .vehicle import ControlInput, VehicleState


_CONTROL_DEADMAN_S = 0.30


class _ViewerState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.frame_ready = threading.Condition(self.lock)
        self.frames: dict[str, bytes | None] = {
            "mounted": None,
            "observer": None,
        }
        self.frame_seq: dict[str, int] = {"mounted": 0, "observer": 0}
        self.frame_at_ms: dict[str, int] = {"mounted": 0, "observer": 0}
        self.frame_requested_at: dict[str, float] = {
            "mounted": 0.0,
            "observer": 0.0,
        }
        self.keys: frozenset[str] = frozenset()
        self.control_at = 0.0
        self.reset_pending = False
        self.stop = False
        self.telemetry: dict[str, float] = {
            "speed_mps": 0.0,
            "steering": 0.0,
            "x": 0.0,
            "y": 0.0,
            "camera_fps": 0.0,
        }


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], state: _ViewerState, html: bytes) -> None:
        self.viewer_state = state
        self.viewer_html = html
        super().__init__(address, _Handler)


class _Handler(BaseHTTPRequestHandler):
    server: _Server
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_bytes(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json_body(self) -> dict[str, Any]:
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 4096)
            value = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def do_GET(self) -> None:  # noqa: N802
        target = urlsplit(self.path)
        path = target.path
        if path == "/":
            self._send_bytes(
                HTTPStatus.OK,
                "text/html; charset=utf-8",
                self.server.viewer_html,
            )
        elif path == "/api/state":
            with self.server.viewer_state.lock:
                body = json.dumps(self.server.viewer_state.telemetry).encode()
            self._send_bytes(HTTPStatus.OK, "application/json", body)
        elif path in ("/frame/mounted.jpg", "/frame/observer.jpg"):
            raw_after = parse_qs(target.query).get("after", ["-1"])[0]
            try:
                after = int(raw_after)
            except ValueError:
                after = -1
            self._send_latest_frame(path.split("/")[2].split(".")[0], after)
        else:
            self._send_bytes(HTTPStatus.NOT_FOUND, "text/plain", b"not found")

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        body = self._json_body()
        state = self.server.viewer_state
        if path == "/api/control":
            allowed = {"w", "a", "s", "d", "space"}
            raw_keys = body.get("keys", [])
            if not isinstance(raw_keys, list):
                raw_keys = []
            keys = frozenset(
                str(key).lower()
                for key in raw_keys
                if str(key).lower() in allowed
            )
            with state.lock:
                state.keys = keys
                state.control_at = time.monotonic()
                state.reset_pending = (
                    state.reset_pending or bool(body.get("reset", False))
                )
            self._send_bytes(HTTPStatus.NO_CONTENT, "text/plain", b"")
        elif path == "/api/quit":
            with state.frame_ready:
                state.stop = True
                state.keys = frozenset()
                state.frame_ready.notify_all()
            self._send_bytes(HTTPStatus.NO_CONTENT, "text/plain", b"")
        else:
            self._send_bytes(HTTPStatus.NOT_FOUND, "text/plain", b"not found")

    def _send_latest_frame(self, stream: str, after: int) -> None:
        state = self.server.viewer_state
        with state.frame_ready:
            state.frame_requested_at[stream] = time.monotonic()
            state.frame_ready.wait_for(
                lambda: state.stop or state.frame_seq[stream] != after,
                timeout=2.0,
            )
            frame = state.frames[stream]
            sequence = state.frame_seq[stream]
            captured_at = state.frame_at_ms[stream]
        if frame is None:
            self._send_bytes(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "text/plain",
                b"camera frame not ready",
            )
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(frame)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("X-Frame-Seq", str(sequence))
        self.send_header("X-Captured-At-Ms", str(captured_at))
        self.end_headers()
        try:
            self.wfile.write(frame)
        except (BrokenPipeError, ConnectionResetError):
            return


class WebViewer:
    def __init__(self, *, host: str, port: int) -> None:
        html_path = Path(__file__).with_name("static") / "index.html"
        self._state = _ViewerState()
        self._server = _Server(
            (str(host), int(port)),
            self._state,
            html_path.read_bytes(),
        )
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="vision-html-viewer",
            daemon=True,
        )
        self._closed = False

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    def start(self) -> None:
        self._thread.start()

    def controls(self) -> ControlInput:
        with self._state.lock:
            keys = self._state.keys
            fresh = time.monotonic() - self._state.control_at <= _CONTROL_DEADMAN_S
        if not fresh:
            keys = frozenset()
        return ControlInput(
            throttle="w" in keys,
            brake_reverse="s" in keys,
            steer_left="a" in keys,
            steer_right="d" in keys,
            handbrake="space" in keys,
        )

    def consume_reset(self) -> bool:
        with self._state.lock:
            pending = self._state.reset_pending
            self._state.reset_pending = False
        return pending

    def stop_requested(self) -> bool:
        with self._state.lock:
            return self._state.stop

    def frame_requested(self, *, max_age_s: float = 0.5) -> bool:
        """Return whether a browser has recently asked for camera frames."""

        cutoff = time.monotonic() - max_age_s
        with self._state.lock:
            return any(
                requested_at >= cutoff
                for requested_at in self._state.frame_requested_at.values()
            )

    def publish_frame(self, stream: str, frame_rgb: np.ndarray) -> None:
        if stream not in self._state.frames:
            raise ValueError(f"unknown camera stream: {stream}")
        buffer = BytesIO()
        Image.fromarray(np.asarray(frame_rgb)).save(
            buffer,
            format="JPEG",
            quality=85,
            optimize=False,
        )
        with self._state.frame_ready:
            self._state.frames[stream] = buffer.getvalue()
            self._state.frame_seq[stream] += 1
            self._state.frame_at_ms[stream] = time.time_ns() // 1_000_000
            self._state.frame_ready.notify_all()

    def publish_state(self, state: VehicleState, *, camera_fps: float) -> None:
        with self._state.lock:
            self._state.telemetry = {
                "speed_mps": float(state.speed_mps),
                "steering": float(state.steering),
                "x": float(state.x),
                "y": float(state.y),
                "camera_fps": float(camera_fps),
            }

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        with self._state.frame_ready:
            self._state.stop = True
            self._state.frame_ready.notify_all()
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2.0)
