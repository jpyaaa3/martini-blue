"""Deterministic kinematic motion for the demo block."""

from __future__ import annotations

from dataclasses import dataclass
import math


def _approach(value: float, target: float, amount: float) -> float:
    if value < target:
        return min(value + amount, target)
    return max(value - amount, target)


@dataclass(frozen=True)
class ControlInput:
    throttle: bool = False
    brake_reverse: bool = False
    steer_left: bool = False
    steer_right: bool = False


@dataclass(frozen=True)
class VehicleConfig:
    acceleration_mps2: float = 3.0
    reverse_acceleration_mps2: float = 2.0
    braking_mps2: float = 6.0
    rolling_drag_mps2: float = 0.8
    max_forward_mps: float = 5.0
    max_reverse_mps: float = 2.0
    max_yaw_rate_rps: float = math.radians(100.0)
    steering_response_per_s: float = 5.0
    steering_return_per_s: float = 7.0
    steering_reference_speed_mps: float = 2.0
    stop_epsilon_mps: float = 0.03
    max_step_s: float = 0.05


@dataclass
class VehicleState:
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0
    speed_mps: float = 0.0
    steering: float = 0.0

    def reset(self) -> None:
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.speed_mps = 0.0
        self.steering = 0.0

    def update(
        self,
        controls: ControlInput,
        dt: float,
        config: VehicleConfig = VehicleConfig(),
    ) -> None:
        """Advance one bounded wall-clock step.

        W accelerates forward. S brakes a forward-moving block and begins
        reversing only after it reaches rest. Pressing both acts as a brake.
        Steering follows the usual vehicle convention, including reversed yaw
        response while backing up.
        """

        step = min(max(float(dt), 0.0), config.max_step_s)
        if step == 0.0:
            return

        if controls.throttle and controls.brake_reverse:
            self.speed_mps = _approach(
                self.speed_mps, 0.0, config.braking_mps2 * step
            )
        elif controls.throttle:
            rate = (
                config.braking_mps2
                if self.speed_mps < 0.0
                else config.acceleration_mps2
            )
            self.speed_mps = min(
                self.speed_mps + rate * step, config.max_forward_mps
            )
        elif controls.brake_reverse:
            rate = (
                config.braking_mps2
                if self.speed_mps > config.stop_epsilon_mps
                else config.reverse_acceleration_mps2
            )
            self.speed_mps = max(
                self.speed_mps - rate * step, -config.max_reverse_mps
            )
        else:
            self.speed_mps = _approach(
                self.speed_mps, 0.0, config.rolling_drag_mps2 * step
            )

        steer_target = float(controls.steer_left) - float(controls.steer_right)
        steer_rate = (
            config.steering_response_per_s
            if steer_target != 0.0
            else config.steering_return_per_s
        )
        self.steering = _approach(self.steering, steer_target, steer_rate * step)

        speed_ratio = min(
            abs(self.speed_mps) / max(config.steering_reference_speed_mps, 1e-6),
            1.0,
        )
        direction = 1.0 if self.speed_mps >= 0.0 else -1.0
        yaw_rate = self.steering * config.max_yaw_rate_rps * speed_ratio * direction
        self.yaw = math.atan2(
            math.sin(self.yaw + yaw_rate * step),
            math.cos(self.yaw + yaw_rate * step),
        )
        self.x += math.cos(self.yaw) * self.speed_mps * step
        self.y += math.sin(self.yaw) * self.speed_mps * step

    def position(self, *, center_z: float) -> tuple[float, float, float]:
        return (self.x, self.y, float(center_z))

    def quaternion_wxyz(self) -> tuple[float, float, float, float]:
        half = self.yaw * 0.5
        return (math.cos(half), 0.0, 0.0, math.sin(half))

