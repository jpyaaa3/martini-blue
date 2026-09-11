# 비전 시뮬레이션



https://github.com/user-attachments/assets/30df9953-2fb8-44ce-bac0-3bd463d54a97



## 조작법

- `W`: 가속
- `S`: 브레이크  및 후진
- `A` / `D`: 좌회전 / 우회전
- `Space`: 핸드브레이크
- `R`: 초기화
- `Esc`: 종료

## Docker로 실행하기

Ubuntu 데스크톱에서는 `--viewer auto`(기본)가 GLFW + Dear ImGui 창을 우선 사용합니다.
X11/XWayland 디스플레이가 없거나 창 생성에 실패하면 HTML 뷰어로 전환합니다.
`--viewer native`는 네이티브 창을 강제하며 실패 원인을 표시하고,
`--viewer web`은 기존 브라우저 뷰어를 사용합니다.

Ubuntu 호스트용 Docker 설정(기존 WSL 설정과 별도):

```bash
# 저장소 루트에서. XAUTHORITY는 현재 데스크톱 세션의 쿠키 파일이어야 합니다.
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
docker compose -f dockerfile/compose.ubuntu.yaml up -d --build
docker exec -it vision-camera-demo vision-demo --viewer auto
```

XWayland를 사용하는 Wayland 세션도 DISPLAY와 XAUTHORITY가 필요합니다.
디스플레이 인증이 안 되면 웹으로 전환됩니다. 디스플레이 접근 제어를 전역 해제할 필요는 없습니다.
네이티브 창은 같은 두 카메라 배치, 상태 표시, 키보드 조작, 블러/셔터 설정,
녹화 선택을 제공합니다. Browse는 컨테이너 안의 폴더를 고르는 ImGui 창입니다.
호스트에도 파일을 남기려면 마운트된 `/workspace/vision` 아래에 저장하세요.
네이티브 MP4는 30fps로 최신 프레임을 반복하여 실제 경과 시간을 유지하며,
별도 인코딩 스레드로 디스크에 저장합니다. 기존 MP4를 덮어쓰지 않으므로 새 이름을 입력하세요.
창을 닫거나 시뮬레이션을 종료하면 녹화도 마무리됩니다.

WSL용 기존 설정:

```bash
# dockerfile/에서
docker compose up -d --build
docker exec -it vision-camera-demo vision-demo
```

## Docker 없이 실행하기

```bash
python3 -m pip install -e '.[test]'
vision-demo --backend gpu
```

## MP4 녹화

뷰어 하단의 **Mounted motion blur**를 켜면 차량 카메라에 깊이 기반 모션 블러가
적용됩니다. **Shutter 1/** 값은 런타임에 15~4000 사이에서 변경할 수 있습니다.
120은 1/120초이며 숫자가 작을수록 노출 시간이 길어져 더 번집니다.
기본은 OFF, 1/120초입니다. 씬 재빌드 없이 다음 프레임부터 적용되며
녹화 영상에도 반영됩니다. 추적 카메라에는 적용하지 않습니다.
정지 상태에서는 모션 블러가 발생하지 않습니다.

정적 장면의 깊이·카메라 병진/회전으로 픽셀 이동을 계산하는 후처리 근사이며,
최대 32픽셀·8샘플로 제한합니다. 깊이 경계나 새로 드러나는 표면은 정확히
재현하지 못하며 디포커스·노이즈·노출에 따른 밝기 변화는 아직 모델링하지 않습니다.
ON에서는 깊이 출력 및 CPU 후처리 비용이 추가됩니다.
후처리는 가로 최대 480픽셀에서 계산한 뒤 원래 크기로 복원하므로,
블러 적용 중에는 미세한 디테일도 줄어듭니다. OFF/정지 상태는 원본 해상도를 유지합니다.

HTML 뷰어 하단에서 파일명을 입력하고 **Browse…**로 PC의 저장 위치를 고릅니다.
**Start recording**으로 시작하고 **Stop recording**으로 MP4 저장을 마무리합니다.
기본은 두 카메라를 나란히 녹화하며, 선택란에서 차량 카메라 또는 추적 카메라만
녹화할 수도 있습니다. 조작 패널은 영상에 들어가지 않으며 오디오는 없습니다.

Browse를 사용하지 않으면 중지 시 브라우저 다운로드로 저장합니다.
저장 창은 지원 브라우저의 localhost 또는 HTTPS 환경에서 사용할 수 있습니다.
MP4 녹화를 지원하지 않는 브라우저에서는 시작 버튼 대신 안내가 표시됩니다.
녹화는 브라우저에서 최대 30fps로 처리되며 실제 카메라 갱신 속도를 높이지는 않습니다.
녹화 중에는 뷰어 탭을 열어 두세요. **Stop simulation**도 녹화를 먼저 마무리합니다.

영상은 저장 전까지 메모리에 보관하며 256 MB에 도달하면 자동으로 중지·저장합니다.
저장 실패 시 표시되는 **Download** 링크로 다시 저장할 수 있습니다.
다음 녹화의 저장 위치는 Browse로 다시 선택하며, 선택하지 않으면 다운로드로 저장합니다.

녹화 상태·저장 오류 처리 테스트는 `node tests/recording.test.cjs`로 실행합니다.
실제 브라우저 녹화 테스트(선택):

```bash
python3 -m pip install playwright
python3 -m playwright install --with-deps chromium
python3 -m pytest tests/test_recording_browser.py
```

## JSON으로 맵 편집하기

기본 맵은 [default.json](src/vision_demo/maps/default.json)입니다.
현재의 교차로 3개, 보도 8개, 건물과 나무 배치가 이 파일에 들어 있습니다.
작은 T자 도로 예제는 [example.json](src/vision_demo/maps/example.json)입니다.
파일을 복사해 수정한 뒤 다음처럼 실행합니다.

```bash
vision-demo --map src/vision_demo/maps/example.json
# Docker 사용 시 경로는 컨테이너 기준입니다. 저장소는 /workspace/vision에 마운트됩니다.
docker exec -it vision-camera-demo vision-demo --map src/vision_demo/maps/example.json
```

최소 맵은 다음과 같습니다. 좌표·길이는 모두 시뮬레이션 월드의 미터 단위이며,
회전은 +Z축 기준 반시계 방향 각도(도)입니다.

```json
{
  "version": 1,
  "roads": [
    {"from": [-8, 0], "to": [8, 0], "width": 3.5},
    {"from": [0, 0], "to": [0, 8], "width": 3.5}
  ],
  "sidewalks": [
    {"position": [4.75, 4.75], "size": [6, 6], "curb_width": 0.12}
  ],
  "buildings": [
    {"type": "house", "position": [4, 4], "rotation": 0, "scale": 0.6}
  ],
  "trees": [
    {"position": [2.1, 6]}
  ]
}
```

| 항목 | 의미와 기본값 |
| --- | --- |
| `roads` | 필수. 중심선 시작점 `from`, 끝점 `to`, 전체 폭 `width`. 1~128개 지원. |
| 도로 차선 옵션 | `stripe_width`: 0.1, `dash_length`: 0.6, `dash_gap`: 0.6. 중앙 황색 실선과 양쪽 흰색 점선을 생성. |
| `sidewalks` | 선택. `position`은 중심, `size`는 연석을 포함한 외곽 크기. `height`: 0.03, `curb_width`: 0.12, `curb_height`: 0.05. |
| `buildings` | 선택. `type`은 `house`, `building`, `market`. `position` 필수, `rotation`: 0, 수평 `scale`: 0.6, 바닥 높이 `base_z`: 0.03. |
| `trees` | 선택. `position` 필수, `base_z`: 0.03. |

가로·세로 직선 도로를 지원합니다. 도로가 교차하면 겹치는 바닥 면을 합치고
교차 영역의 차선을 제거합니다. 같은 방향 도로의 면이 겹치면 하나의 도로로
합쳐 적어야 합니다. 대각선·곡선 도로는 아직 지원하지 않습니다.
보도 위치와 건물·나무 배치는 파일에서 지정하며, 보도마다 연석을 자동 생성합니다.
건물의 `rotation: 0`일 때 정면은 -Y 방향입니다.
차량 시작·리셋 위치는 기존처럼 원점이므로 원점을 도로 안에 두세요.

맵을 변경한 뒤 앱을 재시작하면 씬 생성 전에 JSON을 읽습니다.
도로·연석·보도·건물·나무를 단일 OBJ·단일 PNG·단일 불투명 재질로 굽고
캐시에 저장합니다. 나뭇잎 투명도와 유리의 별도 광택은 사용하지 않으며 차량은 별도입니다.
맵·생성 코드·원본 OBJ/MTL이 같으면 캐시를 재사용하고, 누락되거나 손상된 캐시는 재생성합니다.
기본 캐시는 `$XDG_CACHE_HOME/vision-demo/maps` 또는 `~/.cache/vision-demo/maps`이며
`--map-cache 경로`로 바꿀 수 있습니다. 실행 중 자동 재로딩은 하지 않습니다.

독립 OBJ/PNG를 내보내려면:

```bash
python3 -m vision_demo.static_scene --map src/vision_demo/maps/example.json --output /tmp/my-map
```

인자 없이 실행하면 기본 JSON을 저장소의 `assets/static_scene.*`로 내보냅니다.
배경 색상은 `src/vision_demo/static_scene.py`의 `COLORS`에서 설정합니다.
