from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import ctypes
import time

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from .config import OverlayConfig
from .config import MonitorConfig
from .geometry import Rect
from .monitors import Monitor


GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080


class WinRect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


@dataclass
class TracePoint:
    x: int
    y: int
    at: float


@dataclass
class ActionPulse:
    action: str
    x: int
    y: int
    at: float


@dataclass(frozen=True)
class ScreenMap:
    physical: Rect
    logical: Rect
    dpr: float


class OverlayWindow(QWidget):
    def __init__(
        self,
        config: OverlayConfig,
        virtual_desktop: Rect,
        monitors: list[Monitor] | None = None,
        monitor_config: MonitorConfig | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.monitor_config = monitor_config
        self.virtual_desktop = virtual_desktop
        self.monitors = monitors or []
        self.screen_maps = self._build_screen_maps(monitors or [])
        self.logical_desktop = self._logical_desktop()
        self.monitor: Monitor | None = None
        self.armed = False
        self.status = "IDLE"
        self.trace: deque[TracePoint] = deque(maxlen=config.max_points)
        self.pulses: deque[ActionPulse] = deque(maxlen=12)
        self.cursor: tuple[int, int] | None = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setGeometry(
            self.logical_desktop.x,
            self.logical_desktop.y,
            self.logical_desktop.width,
            self.logical_desktop.height,
        )

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._expire_trace)
        self._timer.start(33)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._make_click_through()

    def _make_click_through(self) -> None:
        hwnd = int(self.winId())
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(
            hwnd,
            GWL_EXSTYLE,
            style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW,
        )

    def set_monitor(self, monitor: Monitor) -> None:
        self.monitor = monitor
        self.update()

    def set_armed(self, armed: bool) -> None:
        self.armed = armed
        self.status = "ARMED" if armed else "IDLE"
        self.update()

    def set_status(self, status: str) -> None:
        self.status = status
        self.update()

    def add_cursor_point(self, x: int, y: int) -> None:
        self.cursor = (x, y)
        self.trace.append(TracePoint(x, y, time.monotonic()))
        self.update()

    def add_action_pulse(self, action: str) -> None:
        if self.cursor is None:
            return
        x, y = self.cursor
        self.pulses.append(ActionPulse(action, x, y, time.monotonic()))
        self.update()

    def _expire_trace(self) -> None:
        cutoff = time.monotonic() - self.config.trace_seconds
        while self.trace and self.trace[0].at < cutoff:
            self.trace.popleft()
        pulse_cutoff = time.monotonic() - self.config.action_pulse_seconds
        while self.pulses and self.pulses[0].at < pulse_cutoff:
            self.pulses.popleft()
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(self.config.opacity)

        if self.monitor is not None:
            self._draw_monitor(painter, self.monitor.rect)
            self._draw_transfer_zones(painter, self.monitor)
        self._draw_trace(painter)
        self._draw_action_pulses(painter)
        self._draw_status(painter)

    def _local_point(self, x: int, y: int) -> QPointF:
        lx, ly = self._physical_to_widget(x, y)
        return QPointF(lx, ly)

    def _local_rect(self, rect: Rect) -> tuple[int, int, int, int]:
        left, top = self._physical_to_widget(rect.x, rect.y)
        right, bottom = self._physical_to_widget(rect.right, rect.bottom)
        return (
            int(round(left)),
            int(round(top)),
            int(round(right - left)),
            int(round(bottom - top)),
        )

    def _physical_to_widget(self, x: int, y: int) -> tuple[float, float]:
        window = self._window_physical_rect()
        if window is not None:
            dpr = max(0.5, float(self.devicePixelRatioF()))
            return (x - window.x) / dpr, (y - window.y) / dpr

        lx, ly = self._physical_to_logical(x, y)
        return lx - self.logical_desktop.x, ly - self.logical_desktop.y

    def _window_physical_rect(self) -> Rect | None:
        try:
            raw = WinRect()
            if ctypes.windll.user32.GetWindowRect(int(self.winId()), ctypes.byref(raw)):
                return Rect(raw.left, raw.top, raw.right - raw.left, raw.bottom - raw.top)
        except Exception:
            return None
        return None

    def _build_screen_maps(self, monitors: list[Monitor]) -> list[ScreenMap]:
        screens = QApplication.screens()
        if not screens or not monitors:
            return []

        sorted_monitors = sorted(monitors, key=lambda item: (item.rect.x, item.rect.y))
        sorted_screens = sorted(screens, key=lambda item: (item.geometry().x(), item.geometry().y()))
        maps: list[ScreenMap] = []
        for monitor, screen in zip(sorted_monitors, sorted_screens):
            geometry = screen.geometry()
            maps.append(
                ScreenMap(
                    physical=monitor.rect,
                    logical=Rect(geometry.x(), geometry.y(), geometry.width(), geometry.height()),
                    dpr=max(0.5, float(screen.devicePixelRatio())),
                )
            )
        return maps

    def _logical_desktop(self) -> Rect:
        if not self.screen_maps:
            return self.virtual_desktop
        left = min(item.logical.x for item in self.screen_maps)
        top = min(item.logical.y for item in self.screen_maps)
        right = max(item.logical.right for item in self.screen_maps)
        bottom = max(item.logical.bottom for item in self.screen_maps)
        return Rect(left, top, right - left, bottom - top)

    def _physical_to_logical(self, x: int, y: int) -> tuple[float, float]:
        for item in self.screen_maps:
            if item.physical.x <= x < item.physical.right and item.physical.y <= y < item.physical.bottom:
                return (
                    item.logical.x + (x - item.physical.x) / item.dpr,
                    item.logical.y + (y - item.physical.y) / item.dpr,
                )
        return float(x - self.virtual_desktop.x + self.logical_desktop.x), float(y - self.virtual_desktop.y + self.logical_desktop.y)

    def _draw_monitor(self, painter: QPainter, rect: Rect) -> None:
        x, y, width, height = self._local_rect(rect)
        border = QColor(70, 210, 185, 180) if self.armed else QColor(180, 180, 180, 110)
        painter.setPen(QPen(border, 3))
        painter.drawRect(x + 2, y + 2, width - 4, height - 4)

        if self.config.show_grid:
            painter.setPen(QPen(QColor(255, 255, 255, 32), 1))
            for col in range(1, 4):
                gx = x + width * col // 4
                painter.drawLine(gx, y, gx, y + height)
            for row in range(1, 4):
                gy = y + height * row // 4
                painter.drawLine(x, gy, x + width, gy)

    def _draw_transfer_zones(self, painter: QPainter, monitor: Monitor) -> None:
        if self.monitor_config is None or not self.monitor_config.transfer_enabled:
            return
        x, y, width, height = self._local_rect(monitor.rect)
        zone = max(8, int(width * max(0.0, min(0.2, self.monitor_config.transfer_zone))))
        coverage = max(0.1, min(1.0, self.monitor_config.transfer_vertical_coverage))
        blind = int(height * (1.0 - coverage) / 2.0)
        zone_y = y + blind
        zone_height = max(1, height - blind * 2)
        color = QColor(80, 220, 190, 48) if self.armed else QColor(180, 180, 180, 24)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        if self._has_neighbor(monitor, "left"):
            painter.drawRect(x, zone_y, zone, zone_height)
        if self._has_neighbor(monitor, "right"):
            painter.drawRect(x + width - zone, zone_y, zone, zone_height)

    def _has_neighbor(self, monitor: Monitor, side: str) -> bool:
        active = monitor.rect
        for candidate in self.monitors:
            if candidate == monitor:
                continue
            rect = candidate.rect
            vertical_overlap = min(active.bottom, rect.bottom) - max(active.y, rect.y)
            if vertical_overlap <= 0:
                continue
            if side == "left" and rect.right <= active.x:
                return True
            if side == "right" and rect.x >= active.right:
                return True
        return False

    def _draw_trace(self, painter: QPainter) -> None:
        now = time.monotonic()
        if len(self.trace) > 1:
            points = [self._local_point(point.x, point.y) for point in self.trace]
            trace_seconds = max(0.05, self.config.trace_seconds)
            for start, end, source in zip(points, points[1:], list(self.trace)[1:]):
                age = max(0.0, min(1.0, (now - source.at) / trace_seconds))
                opacity = int(165 * (1.0 - age) ** 1.5)
                width = max(1.2, 5.0 * (1.0 - age))
                painter.setPen(QPen(QColor(80, 220, 190, opacity), width))
                painter.drawLine(start, end)

        if self.cursor:
            point = self._local_point(*self.cursor)
            painter.setPen(QPen(QColor(255, 255, 255, 230), 2))
            painter.setBrush(QColor(80, 220, 190, 210))
            painter.drawEllipse(point, 8, 8)

    def _draw_action_pulses(self, painter: QPainter) -> None:
        if not self.pulses:
            return

        now = time.monotonic()
        duration = max(0.05, self.config.action_pulse_seconds)
        for pulse in list(self.pulses):
            age = (now - pulse.at) / duration
            if age < 0 or age > 1:
                continue
            color = self._action_color(pulse.action)
            opacity = int(220 * (1.0 - age))
            radius = 10 + 20 * age
            point = self._local_point(pulse.x, pulse.y)
            painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), opacity), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(point, radius, radius)

    def _action_color(self, action: str) -> QColor:
        colors = {
            "left_click": QColor(80, 220, 190),
            "double_click": QColor(255, 210, 90),
            "right_click": QColor(120, 170, 255),
            "drag_start": QColor(255, 145, 80),
            "drag_end": QColor(255, 190, 120),
            "scroll": QColor(185, 135, 255),
            "zoom_in": QColor(105, 230, 130),
            "zoom_out": QColor(245, 120, 145),
            "back": QColor(245, 165, 80),
            "forward": QColor(105, 190, 255),
            "next_monitor": QColor(255, 255, 255),
        }
        return colors.get(action, QColor(255, 255, 255))

    def _draw_status(self, painter: QPainter) -> None:
        if self.monitor is None:
            return
        rect = self.monitor.rect
        x, y, _, _ = self._local_rect(rect)
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        text = f"{self.status} | {self.monitor.name}"
        color = QColor(70, 210, 185, 210) if self.armed else QColor(230, 230, 230, 150)
        painter.setPen(color)
        painter.drawText(x + 18, y + 30, text)


def ensure_app() -> QApplication:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
