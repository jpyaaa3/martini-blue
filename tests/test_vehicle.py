import math

import pytest

from vision_demo.vehicle import ControlInput, VehicleConfig, VehicleState


def advance(state: VehicleState, controls: ControlInput, seconds: float) -> None:
    for _ in range(round(seconds / 0.01)):
        state.update(controls, 0.01)


def test_w_accelerates_and_obeys_forward_limit() -> None:
    state = VehicleState()
    advance(state, ControlInput(throttle=True), 3.0)
    assert state.speed_mps == pytest.approx(VehicleConfig().max_forward_mps)
    assert state.x > 0.0


def test_s_brakes_before_reversing() -> None:
    state = VehicleState(speed_mps=1.0)
    state.update(ControlInput(brake_reverse=True), 0.1)
    assert 0.0 < state.speed_mps < 1.0
    advance(state, ControlInput(brake_reverse=True), 1.5)
    assert state.speed_mps < 0.0


def test_left_steering_turns_opposite_when_reversing() -> None:
    forward = VehicleState(speed_mps=2.0)
    reverse = VehicleState(speed_mps=-2.0)
    forward.update(ControlInput(steer_left=True), 0.05)
    reverse.update(ControlInput(steer_left=True), 0.05)
    assert forward.yaw > 0.0
    assert reverse.yaw < 0.0


def test_large_frame_time_is_bounded() -> None:
    state = VehicleState()
    state.update(ControlInput(throttle=True), 10.0)
    assert state.speed_mps == pytest.approx(
        VehicleConfig().acceleration_mps2 * VehicleConfig().max_step_s
    )


def test_quaternion_is_wxyz_yaw_rotation() -> None:
    state = VehicleState(yaw=math.pi / 2.0)
    w, x, y, z = state.quaternion_wxyz()
    assert (w, x, y, z) == pytest.approx((math.sqrt(0.5), 0.0, 0.0, math.sqrt(0.5)))

