from __future__ import annotations

import ctypes
import time

from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key
from pynput.mouse import Button, Controller

from .config import MouseConfig


class PointerFilter:
    def __init__(self, config: MouseConfig) -> None:
        self.config = config
        self._smoothed: tuple[float, float] | None = None
        self._last_raw: tuple[int, int] | None = None
        self._dynamic_target: tuple[float, float] | None = None
        self._motion_factor = 1.0
        self._last_update_at: float | None = None

    def update(self, x: int, y: int, distance_gain: float = 1.0) -> tuple[int, int]:
        now = time.monotonic()
        if self._smoothed is None:
            self._smoothed = (float(x), float(y))
            self._last_raw = (x, y)
            self._dynamic_target = (float(x), float(y))
            self._last_update_at = now
            return x, y

        sx, sy = self._smoothed
        raw_dx = x - self._last_raw[0] if self._last_raw else 0
        raw_dy = y - self._last_raw[1] if self._last_raw else 0
        raw_distance = (raw_dx * raw_dx + raw_dy * raw_dy) ** 0.5
        self._last_raw = (x, y)
        dt = max(1 / 240, min(0.12, now - self._last_update_at)) if self._last_update_at else 1 / 60
        self._last_update_at = now

        # Sudden landmark jumps usually come from momentary mis-detections.
        if raw_distance > self.config.max_jump_px:
            return int(round(sx)), int(round(sy))

        target_x, target_y = self._dynamic_target_for(x, y, raw_dx, raw_dy, raw_distance, distance_gain)
        dx = target_x - sx
        dy = target_y - sy
        distance = (dx * dx + dy * dy) ** 0.5
        if distance < self.config.deadzone_px:
            if self.config.adaptive_filter_enabled and raw_distance <= self.config.still_speed_px:
                self._smoothed = (target_x, target_y)
                return int(round(target_x)), int(round(target_y))
            return int(round(sx)), int(round(sy))

        alpha = self._adaptive_alpha(raw_distance, distance, dt)
        self._smoothed = (sx + dx * alpha, sy + dy * alpha)
        return int(round(self._smoothed[0])), int(round(self._smoothed[1]))

    def current(self) -> tuple[int, int] | None:
        if self._smoothed is None:
            return None
        return int(round(self._smoothed[0])), int(round(self._smoothed[1]))

    def reanchor(self, x: int, y: int, strength: float | None = None) -> tuple[int, int]:
        if strength is None:
            strength = self.config.grid_reentry_snap_strength
        strength = max(0.0, min(1.0, strength))
        if self._smoothed is None or strength >= 1.0:
            self._smoothed = (float(x), float(y))
        else:
            sx, sy = self._smoothed
            self._smoothed = (sx + (x - sx) * strength, sy + (y - sy) * strength)
        self._dynamic_target = (float(x), float(y))
        self._last_raw = (x, y)
        self._last_update_at = time.monotonic()
        self._motion_factor = 1.0
        return int(round(self._smoothed[0])), int(round(self._smoothed[1]))

    def reset(self) -> None:
        self._smoothed = None
        self._last_raw = None
        self._dynamic_target = None
        self._motion_factor = 1.0
        self._last_update_at = None

    def _adaptive_alpha(self, raw_distance: float, error_distance: float, dt: float) -> float:
        if not self.config.adaptive_filter_enabled:
            return max(0.02, min(1.0, self.config.smoothing))

        slow_speed = max(0.0, self.config.precision_slow_speed_px)
        fast_speed = max(slow_speed + 1.0, self.config.precision_fast_speed_px)
        frame_normalized_speed = raw_distance * (1 / 60) / max(dt, 1 / 240)
        speed_blend = self._smoothstep((frame_normalized_speed - slow_speed) / (fast_speed - slow_speed))

        precision_alpha = max(0.03, min(0.85, self.config.precision_smoothing))
        travel_alpha = max(precision_alpha, min(1.0, self.config.travel_smoothing))
        catchup_alpha = max(travel_alpha, min(1.0, self.config.catchup_smoothing))

        alpha = precision_alpha + (travel_alpha - precision_alpha) * speed_blend

        catchup_error = max(float(self.config.deadzone_px) + 1.0, self.config.catchup_error_px)
        error_blend = self._smoothstep((error_distance - self.config.deadzone_px) / (catchup_error - self.config.deadzone_px))
        alpha = max(alpha, precision_alpha + (catchup_alpha - precision_alpha) * error_blend)

        if raw_distance <= self.config.still_speed_px and error_distance <= self.config.still_snap_error_px:
            alpha = max(alpha, max(precision_alpha, min(1.0, self.config.still_snap_smoothing)))

        return max(0.02, min(1.0, alpha))

    def _smoothstep(self, value: float) -> float:
        value = max(0.0, min(1.0, value))
        return value * value * (3.0 - 2.0 * value)

    def _dynamic_target_for(
        self,
        x: int,
        y: int,
        raw_dx: int,
        raw_dy: int,
        raw_distance: float,
        distance_gain: float,
    ) -> tuple[float, float]:
        if not self.config.precision_accel_enabled:
            self._dynamic_target = (float(x), float(y))
            self._motion_factor = 1.0
            return self._dynamic_target

        if self._dynamic_target is None:
            self._dynamic_target = (float(x), float(y))

        slow_speed = max(0.0, self.config.precision_slow_speed_px)
        fast_speed = max(slow_speed + 1.0, self.config.precision_fast_speed_px)
        slow_factor = max(0.05, min(1.0, self.config.precision_slow_factor))
        fast_factor = max(slow_factor, min(2.5, self.config.precision_fast_factor))
        blend = max(0.0, min(1.0, (raw_distance - slow_speed) / (fast_speed - slow_speed)))
        blend = blend * blend * (3.0 - 2.0 * blend)
        target_factor = slow_factor + (fast_factor - slow_factor) * blend

        smoothing = max(0.0, min(1.0, self.config.precision_factor_smoothing))
        target_factor *= max(0.5, min(3.0, distance_gain))
        self._motion_factor += (target_factor - self._motion_factor) * smoothing

        tx, ty = self._dynamic_target
        tx += raw_dx * self._motion_factor
        ty += raw_dy * self._motion_factor

        anchor = max(0.0, min(0.2, self.config.precision_anchor_strength))
        tx += (x - tx) * anchor
        ty += (y - ty) * anchor
        self._dynamic_target = (tx, ty)
        return self._dynamic_target


class MouseController:
    def __init__(self, config: MouseConfig) -> None:
        self.config = config
        self._mouse = Controller()
        self._keyboard = KeyboardController()
        self._dragging = False

    def move_to(self, x: int, y: int) -> tuple[int, int]:
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
        return self.position()

    def position(self) -> tuple[int, int]:
        point = wintypes_point()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        return int(point.x), int(point.y)

    def left_click(self, count: int = 1) -> None:
        self._mouse.click(Button.left, count)

    def right_click(self) -> None:
        self._mouse.click(Button.right, 1)

    def back(self) -> None:
        with self._keyboard.pressed(Key.alt):
            self._keyboard.press(Key.left)
            self._keyboard.release(Key.left)

    def forward(self) -> None:
        with self._keyboard.pressed(Key.alt):
            self._keyboard.press(Key.right)
            self._keyboard.release(Key.right)

    def drag_start(self) -> None:
        if not self._dragging:
            self._mouse.press(Button.left)
            self._dragging = True

    def drag_end(self) -> None:
        if self._dragging:
            self._mouse.release(Button.left)
            self._dragging = False

    def scroll(self, dy: int) -> None:
        if dy:
            self._mouse.scroll(0, dy)

    def zoom_in(self, steps: int = 1) -> None:
        with self._keyboard.pressed(Key.ctrl):
            for _ in range(max(1, steps)):
                self._keyboard.press("=")
                self._keyboard.release("=")

    def zoom_out(self, steps: int = 1) -> None:
        with self._keyboard.pressed(Key.ctrl):
            for _ in range(max(1, steps)):
                self._keyboard.press("-")
                self._keyboard.release("-")

    def reset(self) -> None:
        self.drag_end()


class wintypes_point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
