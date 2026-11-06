"""Pure gesture-to-control calculations, kept independent of camera libraries."""

from __future__ import annotations

import math
from collections.abc import Sequence


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def steering_from_wrists(
    wrists: Sequence[tuple[float, float]], max_angle_degrees: float = 35.0
) -> float:
    """Return steering in [-1, 1] from two normalized wrist points."""
    if len(wrists) < 2 or max_angle_degrees <= 0:
        return 0.0

    left, right = sorted(wrists[:2], key=lambda point: point[0])
    dx = right[0] - left[0]
    if dx <= 0:
        return 0.0
    angle = math.degrees(math.atan2(right[1] - left[1], dx))
    return clamp(angle / max_angle_degrees, -1.0, 1.0)


def pedal_levels(
    feet: Sequence[tuple[float, float]],
    neutral_y: tuple[float, float] | None,
    press_distance: float = 0.10,
) -> tuple[float, float]:
    """Return left/right pedal pressure from ankle movement above calibration."""
    if len(feet) < 2 or neutral_y is None or press_distance <= 0:
        return 0.0, 0.0

    left, right = sorted(feet[:2], key=lambda point: point[0])
    left_pressure = (neutral_y[0] - left[1]) / press_distance
    right_pressure = (neutral_y[1] - right[1]) / press_distance
    return clamp(left_pressure, 0.0, 1.0), clamp(right_pressure, 0.0, 1.0)


def active_keys(
    steering: float,
    accelerator: float,
    brake: float,
    steer_deadzone: float = 0.22,
    pedal_deadzone: float = 0.45,
) -> frozenset[str]:
    """Map controls to TORCS key names; braking takes priority over throttle."""
    keys: set[str] = set()
    if steering <= -steer_deadzone:
        keys.add("left")
    elif steering >= steer_deadzone:
        keys.add("right")

    if brake >= pedal_deadzone:
        keys.add("down")
    elif accelerator >= pedal_deadzone:
        keys.add("up")
    return frozenset(keys)
