"""Command-line entry point."""

from __future__ import annotations

import argparse
import os


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Genesis mounted-camera driving demo")
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
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.camera_fps <= 0.0:
        raise SystemExit("--camera-fps must be greater than zero")
    # Keep heavyweight graphics imports after argument validation so --help
    # remains usable outside the runtime container.
    from .app import AppConfig, VisionDemo

    VisionDemo(AppConfig(backend=args.backend, camera_max_fps=args.camera_fps)).run()


if __name__ == "__main__":
    main()

