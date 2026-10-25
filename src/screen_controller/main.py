from __future__ import annotations

import sys
import ctypes
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from .adaptive_gain import AdaptiveGainMapper
from .config import load_config, project_root
from .control_panel import ControlPanel
from .debug_view import DebugCameraView
from .geometry import map_normalized_to_rect
from .gestures import GestureInterpreter, MouseAction
from .hotkeys import HotkeyManager
from .monitors import MonitorManager
from .mouse_control import MouseController, PointerFilter
from .overlay import OverlayWindow, ensure_app
from .tracker import HandTracker


class UiBridge(QObject):
    cursor = Signal(int, int)
    action = Signal(str)
    armed = Signal(bool)
    status = Signal(str)
    monitor_changed = Signal(object)


class ScreenControllerApp:
    def __init__(self, config_path: Path) -> None:
        self._set_dpi_awareness()
        self.config_path = config_path
        self.config = load_config(config_path)
        self.monitors = MonitorManager()
        self.mouse = MouseController(self.config.mouse)
        self.pointer_filter = PointerFilter(self.config.mouse)
        self.adaptive_gain = AdaptiveGainMapper(self.config.adaptive_gain)
        self.gestures = GestureInterpreter(self.config.gestures)
        self.tracker = HandTracker(self.config.camera)
        self.debug_view = DebugCameraView(self.config.debug)

        self.armed = False
        self.running = True
        self.status_text = "IDLE"
        self._edge_side: str | None = None
        self._edge_since = 0.0
        self._transfer_side: str | None = None
        self._transfer_since = 0.0
        self._last_transfer_at = 0.0
        self._pointer_inside_grid = False
        self._pointer_outside_since: float | None = None
        self._monitor_handoff_side: str | None = None
        self._monitor_handoff_started_at = 0.0
        self._monitor_handoff_point: tuple[int, int] | None = None

        self.qt_app = ensure_app()
        self.bridge = UiBridge()
        self.overlay = OverlayWindow(
            self.config.overlay,
            self.monitors.virtual_desktop,
            self.monitors.monitors,
            self.config.monitors,
        )
        self.overlay.set_monitor(self.monitors.active)
        self.control_panel = ControlPanel(
            self.config,
            self.config_path,
            on_reset_pointer=self.pointer_filter.reset,
            on_reset_gain=self.adaptive_gain.reset,
        )

        self.bridge.cursor.connect(self.overlay.add_cursor_point)
        self.bridge.action.connect(self.overlay.add_action_pulse)
        self.bridge.armed.connect(self.overlay.set_armed)
        self.bridge.status.connect(self.overlay.set_status)
        self.bridge.monitor_changed.connect(self.overlay.set_monitor)

        self.hotkeys = HotkeyManager(
            self.config.hotkeys,
            on_toggle_armed=self.toggle_armed,
            on_next_monitor=self.next_monitor,
            on_quit=self.quit,
        )

    def _set_dpi_awareness(self) -> None:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    def run(self) -> int:
        self.hotkeys.start()
        self.overlay.show()
        if self.config.debug.show_control_panel:
            self.control_panel.show()

        worker = threading.Thread(target=self._camera_loop, name="camera-loop", daemon=True)
        worker.start()

        shutdown_timer = QTimer()
        shutdown_timer.timeout.connect(self._check_running)
        shutdown_timer.start(250)

        try:
            return self.qt_app.exec()
        finally:
            self.running = False
            worker.join(timeout=1.5)
            self.hotkeys.stop()
            self.mouse.reset()
            self.tracker.close()
            self.debug_view.close()

    def _check_running(self) -> None:
        if not self.running:
            self.qt_app.quit()

    def toggle_armed(self) -> None:
        self.armed = not self.armed
        if not self.armed:
            self.mouse.reset()
            self.pointer_filter.reset()
            self.adaptive_gain.reset()
            self.gestures.reset()
        self.bridge.armed.emit(self.armed)
        self._set_status("ARMED" if self.armed else "IDLE")

    def next_monitor(self) -> None:
        monitor = self.monitors.next()
        self.bridge.monitor_changed.emit(monitor)
        self._set_status(f"MONITOR {self.monitors.active_index + 1}")

    def previous_monitor(self) -> None:
        monitor = self.monitors.previous()
        self.bridge.monitor_changed.emit(monitor)
        self._set_status(f"MONITOR {self.monitors.active_index + 1}")

    def quit(self) -> None:
        self.running = False

    def _set_status(self, status: str) -> None:
        self.status_text = status
        self.bridge.status.emit(status)

    def _camera_loop(self) -> None:
        try:
            self.tracker.open()
        except Exception as exc:
            self.bridge.status.emit(f"CAMERA ERROR: {exc}")
            return

        while self.running:
            hand, _frame = self.tracker.read()
            if hand is None:
                if self.armed:
                    self.mouse.reset()
                    self.pointer_filter.reset()
                    self.adaptive_gain.reset()
                    self.gestures.reset()
                self._set_status("NO HAND" if self.armed else "IDLE")
                self.debug_view.show(
                    _frame,
                    None,
                    self.armed,
                    self.status_text,
                    self.monitors.active.name,
                    None,
                    self.gestures.debug_text,
                )
                time.sleep(0.01)
                continue

            gain_state = self.adaptive_gain.map(hand)
            nx, ny = gain_state.normalized_xy
            x, y = map_normalized_to_rect(nx, ny, self.monitors.active.rect)
            x, y = self._snap_target_to_screen_edges(nx, ny, x, y)
            handoff_point = self._monitor_handoff_point_for(nx)
            if handoff_point is not None:
                x, y = handoff_point
            pointer_reentered_grid = self._update_pointer_grid_state(hand)

            event = self.gestures.update(hand) if self.armed else None
            precision_mode = bool(event and event.precision_mode)
            stable_point = self.pointer_filter.current()
            distance_gain = gain_state.gain
            if precision_mode:
                distance_gain *= self.config.gestures.precision_mode_pointer_gain

            should_move = not event or not event.block_move
            if should_move:
                if handoff_point is not None:
                    stable_point = self.pointer_filter.reanchor(x, y, 1.0)
                elif pointer_reentered_grid and self.config.mouse.grid_reentry_snap_enabled:
                    stable_point = self.pointer_filter.reanchor(x, y)
                else:
                    stable_point = self.pointer_filter.update(x, y, distance_gain)
            elif stable_point is None:
                stable_point = self.pointer_filter.update(x, y, distance_gain)

            if should_move and (self.armed or self.config.mouse.move_when_unarmed):
                stable_point = self.mouse.move_to(*stable_point)

            if stable_point is None:
                stable_point = self.pointer_filter.update(x, y, distance_gain)
            self.bridge.cursor.emit(*stable_point)

            if event:
                self._apply_gesture(event)
            if self.armed and stable_point is not None and handoff_point is None:
                self._maybe_transfer_monitor(stable_point)

            self.debug_view.show(
                _frame,
                hand,
                self.armed,
                self.status_text,
                self.monitors.active.name,
                stable_point,
                f"{self.gestures.debug_text} | gain={gain_state.gain:.2f} hand={gain_state.hand_scale:.3f} ref={gain_state.reference_scale:.3f}",
            )
            time.sleep(0.001)

    def _update_pointer_grid_state(self, hand) -> bool:
        ix, iy = hand.index_xy
        inside = hand.active_rect.contains(ix, iy)
        now = time.monotonic()
        was_inside = self._pointer_inside_grid
        reentered = False

        if inside:
            if not was_inside and self._pointer_outside_since is not None:
                minimum = max(0.0, self.config.mouse.grid_reentry_min_outside_seconds)
                reentered = now - self._pointer_outside_since >= minimum
            self._pointer_outside_since = None
        else:
            if was_inside or self._pointer_outside_since is None:
                self._pointer_outside_since = now

        self._pointer_inside_grid = inside
        return reentered

    def _monitor_handoff_point_for(self, nx: float) -> tuple[int, int] | None:
        if self._monitor_handoff_side is None or self._monitor_handoff_point is None:
            return None
        config = self.config.mouse
        if not config.monitor_handoff_enabled:
            self._clear_monitor_handoff()
            return None

        now = time.monotonic()
        elapsed = now - self._monitor_handoff_started_at
        if elapsed >= max(config.monitor_handoff_min_seconds, config.monitor_handoff_max_seconds):
            self._clear_monitor_handoff()
            return None

        release_zone = max(0.02, min(0.45, config.monitor_handoff_release_zone))
        if elapsed >= max(0.0, config.monitor_handoff_min_seconds):
            if self._monitor_handoff_side == "right" and nx < 1.0 - release_zone:
                self._clear_monitor_handoff()
                return None
            if self._monitor_handoff_side == "left" and nx > release_zone:
                self._clear_monitor_handoff()
                return None

        return self._monitor_handoff_point

    def _start_monitor_handoff(self, side: str, point: tuple[int, int]) -> None:
        if not self.config.mouse.monitor_handoff_enabled:
            self._clear_monitor_handoff()
            return
        self._monitor_handoff_side = side
        self._monitor_handoff_started_at = time.monotonic()
        self._monitor_handoff_point = point
        self._pointer_inside_grid = True
        self._pointer_outside_since = None

    def _clear_monitor_handoff(self) -> None:
        self._monitor_handoff_side = None
        self._monitor_handoff_point = None
        self._monitor_handoff_started_at = 0.0

    def _apply_gesture(self, event) -> None:
        if event.action == MouseAction.LEFT_CLICK:
            self.bridge.action.emit(event.action.value)
            self.mouse.left_click(1)
            self._set_status("LEFT CLICK")
        elif event.action == MouseAction.DOUBLE_CLICK:
            self.bridge.action.emit(event.action.value)
            self.mouse.left_click(2)
            self._set_status("DOUBLE CLICK")
        elif event.action == MouseAction.RIGHT_CLICK:
            self.bridge.action.emit(event.action.value)
            self.mouse.right_click()
            self._set_status("RIGHT CLICK")
        elif event.action == MouseAction.DRAG_START:
            self.bridge.action.emit(event.action.value)
            self.mouse.drag_start()
            self._set_status("DRAG")
        elif event.action == MouseAction.DRAG_END:
            self.bridge.action.emit(event.action.value)
            self.mouse.drag_end()
            self._set_status("ARMED")
        elif event.action == MouseAction.SCROLL:
            self.bridge.action.emit(event.action.value)
            self.mouse.scroll(event.scroll_y)
            self._set_status("SCROLL")
        elif event.action == MouseAction.NEXT_MONITOR:
            self.bridge.action.emit(event.action.value)
            self.next_monitor()
        elif event.action == MouseAction.ZOOM_IN:
            self.bridge.action.emit(event.action.value)
            self.mouse.zoom_in(event.steps)
            self._set_status(f"ZOOM IN x{event.steps}")
        elif event.action == MouseAction.ZOOM_OUT:
            self.bridge.action.emit(event.action.value)
            self.mouse.zoom_out(event.steps)
            self._set_status(f"ZOOM OUT x{event.steps}")
        elif event.action == MouseAction.BACK:
            self.bridge.action.emit(event.action.value)
            self.mouse.back()
            self._set_status("BACK")
        elif event.action == MouseAction.FORWARD:
            self.bridge.action.emit(event.action.value)
            self.mouse.forward()
            self._set_status("FORWARD")
        else:
            self._set_status("ARMED")

    def _maybe_switch_monitor_by_edge(self, nx: float) -> None:
        config = self.config.monitors
        if not config.edge_switch_enabled or len(self.monitors.monitors) <= 1:
            return

        side = None
        if nx <= config.edge_zone:
            side = "left"
        elif nx >= 1.0 - config.edge_zone:
            side = "right"

        now = time.monotonic()
        if side is None:
            self._edge_side = None
            self._edge_since = 0.0
            return

        if side != self._edge_side:
            self._edge_side = side
            self._edge_since = now
            return

        if now - self._edge_since >= config.edge_dwell_seconds:
            if side == "left":
                self.previous_monitor()
            else:
                self.next_monitor()
            self._edge_since = now + 0.5

    def _snap_target_to_screen_edges(self, nx: float, ny: float, x: int, y: int) -> tuple[int, int]:
        zone = max(0.0, min(0.08, self.config.mouse.screen_edge_snap_zone))
        if zone <= 0:
            return x, y

        rect = self.monitors.active.rect
        if nx <= zone:
            x = rect.x
        elif nx >= 1.0 - zone:
            x = rect.right - 1

        if ny <= zone:
            y = rect.y
        elif ny >= 1.0 - zone:
            y = rect.bottom - 1

        return x, y

    def _maybe_transfer_monitor(self, point: tuple[int, int]) -> None:
        config = self.config.monitors
        if not config.transfer_enabled or len(self.monitors.monitors) <= 1:
            self._transfer_side = None
            self._transfer_since = 0.0
            return

        now = time.monotonic()
        if now - self._last_transfer_at < config.transfer_cooldown_seconds:
            return

        rect = self.monitors.active.rect
        zone_px = max(8, int(rect.width * max(0.0, min(0.2, config.transfer_zone))))
        top, bottom = self._transfer_vertical_bounds(rect)
        if not top <= point[1] <= bottom:
            self._transfer_side = None
            self._transfer_since = 0.0
            return

        side = None
        if point[0] <= rect.x + zone_px and self.monitors.neighbor("left") is not None:
            side = "left"
        elif point[0] >= rect.right - 1 - zone_px and self.monitors.neighbor("right") is not None:
            side = "right"

        if side is None:
            self._transfer_side = None
            self._transfer_since = 0.0
            return

        if side != self._transfer_side:
            self._transfer_side = side
            self._transfer_since = now
            self._set_status(f"TRANSFER {side.upper()}")
            return

        if now - self._transfer_since < config.transfer_dwell_seconds:
            return

        target = self.monitors.neighbor(side)
        if target is None:
            return

        source_y_ratio = (point[1] - rect.y) / max(1, rect.height)
        entry = max(0.0, min(0.2, config.transfer_entry_offset))
        if side == "left":
            new_x = target.rect.right - 1 - int(target.rect.width * entry)
        else:
            new_x = target.rect.x + int(target.rect.width * entry)
        new_y = target.rect.y + int(target.rect.height * max(0.0, min(1.0, source_y_ratio)))
        monitor = self.monitors.switch_to(target)
        self.bridge.monitor_changed.emit(monitor)
        self.pointer_filter.reset()
        stable_point = self.pointer_filter.update(new_x, new_y, 1.0)
        if self.armed or self.config.mouse.move_when_unarmed:
            stable_point = self.mouse.move_to(*stable_point)
        self.bridge.cursor.emit(*stable_point)
        self._start_monitor_handoff(side, stable_point)
        self._last_transfer_at = now
        self._transfer_side = None
        self._transfer_since = 0.0
        self._set_status(f"MONITOR {self.monitors.active_index + 1}")

    def _transfer_vertical_bounds(self, rect) -> tuple[int, int]:
        coverage = max(0.1, min(1.0, self.config.monitors.transfer_vertical_coverage))
        blind = (1.0 - coverage) / 2.0
        top = rect.y + int(rect.height * blind)
        bottom = rect.bottom - 1 - int(rect.height * blind)
        return top, bottom


def main() -> None:
    if "--self-test" in sys.argv:
        root = project_root()
        app = ScreenControllerApp(root / "config.json")
        print("self-test OK")
        print(f"config={root / 'config.json'}")
        print(f"model={root / app.config.camera.model_path}")
        app.tracker.close()
        app.debug_view.close()
        return

    root = project_root()
    app = ScreenControllerApp(root / "config.json")
    sys.exit(app.run())
