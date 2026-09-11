"""Command-line entry point."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .map_file import DEFAULT_MAP, load_map


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Genesis mounted-camera driving demo")
    parser.add_argument('--viewer', choices=('auto','native','web'), default='auto', help='Ubuntu display: native first; otherwise web')
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP, help="JSON map file (default: bundled maps/default.json)")
    parser.add_argument("--map-cache", type=Path, help="generated map cache directory")
    parser.add_argument(
        "--backend",
        choices=("gpu", "cpu"),
        default=os.environ.get("VISION_BACKEND", "gpu"),
        help="Genesis compute backend (default: VISION_BACKEND or gpu)",
    )
    parser.add_argument(
        "--camera-fps",
        type=float,
        default=30.0,
        help="maximum mounted-camera render rate",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("VISION_HOST", "127.0.0.1"),
        help="HTML viewer bind address (default: VISION_HOST or 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("VISION_PORT", "8765")),
        help="HTML viewer port (default: VISION_PORT or 8765)",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.camera_fps <= 0.0:
        raise SystemExit("--camera-fps must be greater than zero")
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be between 1 and 65535")
    try:
        load_map(args.map)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    # Keep heavyweight graphics imports after argument validation so --help
    # remains usable outside the runtime container.
    from .app import AppConfig, VisionDemo

    VisionDemo(
        AppConfig(
            viewer=args.viewer,
            map_path=args.map,
            map_cache_dir=args.map_cache,
            backend=args.backend,
            camera_max_fps=args.camera_fps,
            web_host=args.host,
            web_port=args.port,
        )
    ).run()


if __name__ == "__main__":
    main()
