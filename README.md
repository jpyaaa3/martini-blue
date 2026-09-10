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
