FROM nvidia/cuda:12.8.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYOPENGL_PLATFORM=egl

ARG USERNAME=vision
ARG UID=1000
ARG GID=1000

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-pip python3-dev build-essential sudo \
      libgl1 libegl1 libglvnd0 libglx-mesa0 libglu1-mesa mesa-utils \
      libglfw3 libglib2.0-0 libdbus-1-3 libfontconfig1 libfreetype6 \
      libsm6 libice6 libx11-6 libx11-xcb1 libxcb1 libxcb-randr0 \
      libxcb-render0 libxcb-shape0 libxcb-shm0 libxcb-xfixes0 \
      libxext6 libxrender1 libxrandr2 libxinerama1 libxcursor1 libxi6 \
      libxkbcommon0 libxkbcommon-x11-0 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid "${GID}" "${USERNAME}" \
    && useradd --uid "${UID}" --gid "${GID}" --create-home --shell /bin/bash "${USERNAME}" \
    && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" >/etc/sudoers.d/vision

WORKDIR /workspace/vision
COPY . .
RUN python3 -m pip install --upgrade pip "setuptools>=68,<80" wheel \
    && python3 -m pip install -e ".[test]" \
    && python3 -c "import genesis, torch, PIL; print('vision runtime imports ok')"

USER ${USERNAME}
CMD ["sleep", "infinity"]
