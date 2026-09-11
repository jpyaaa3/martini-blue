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

## 정적 배경 에셋

도로·연석·보도·건물·나무는 `assets/static_scene.obj` 하나와
`static_scene.png` 텍스처, 단일 재질을 사용합니다. 차량은 별도입니다.
차선은 PNG에 구워져 있고 도로는 7개 사각면(14개 삼각형)입니다.
단일 불투명 재질을 위해 나뭇잎 투명도와 유리의 별도 광택은 사용하지 않습니다.

배치나 색상을 변경한 뒤 에셋을 다시 생성하려면:

```bash
python3 -m vision_demo.static_scene
```

배경 색상은 `src/vision_demo/static_scene.py`의 `COLORS`에서 설정합니다.
