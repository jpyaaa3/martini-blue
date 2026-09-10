

https://github.com/user-attachments/assets/b325b885-6beb-46d4-b6e7-1c6fb9940dcc

# Vision camera demo

A deliberately small Genesis demo with exactly two native windows:

1. the normal Genesis scene viewer;
2. a GLFW/ImGui window showing a camera mounted on the moving block.

## Controls

- `W`: accelerate
- `S`: brake, then reverse after stopping
- `A` / `D`: steer left / right
- `R`: reset pose and speed
- `Esc`: quit

Keyboard input is accepted while the **Mounted Camera** window has focus.

## Run in the development container

The container stays alive so the demo can be started repeatedly with
`docker exec`, as requested.

```bash
cd /home/user/ws/vision/dockerfile
UID=$(id -u) GID=$(id -g) docker compose up -d --build
docker exec -it vision-camera-demo vision-demo
```

For a CPU trial:

```bash
docker exec -it -e VISION_BACKEND=cpu vision-camera-demo vision-demo --backend cpu
```

On native Linux/X11, the host X server must allow the same local UID to open
windows. WSLg normally works with the mounts and environment in `compose.yaml`.
The default Compose configuration requires the NVIDIA Container Toolkit because
it requests `gpus: all`.

Useful checks:

```bash
docker exec -it vision-camera-demo pytest
docker exec -it vision-camera-demo python3 -m vision_demo.main --help
```

## Run without Docker

```bash
cd /home/user/ws/vision
python3 -m pip install -e '.[test]'
vision-demo --backend gpu
```

The block motion is kinematic on purpose. There is no waypoint/scenario layer,
vehicle suspension, networking, recording, depth stream, or configuration UI
in this first version.
