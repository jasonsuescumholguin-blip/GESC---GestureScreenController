from __future__ import annotations

from dataclasses import dataclass

from screeninfo import get_monitors

from .geometry import Rect


@dataclass(frozen=True)
class Monitor:
    name: str
    rect: Rect
    primary: bool = False


class MonitorManager:
    def __init__(self) -> None:
        self.monitors = self._load_monitors()
        self.active_index = self._primary_index()

    def _load_monitors(self) -> list[Monitor]:
        monitors = []
        for idx, item in enumerate(get_monitors()):
            monitors.append(
                Monitor(
                    name=getattr(item, "name", None) or f"Monitor {idx + 1}",
                    rect=Rect(item.x, item.y, item.width, item.height),
                    primary=bool(getattr(item, "is_primary", False)),
                )
            )
        if not monitors:
            monitors.append(Monitor("Primary", Rect(0, 0, 1920, 1080), True))
        return monitors

    def _primary_index(self) -> int:
        for idx, monitor in enumerate(self.monitors):
            if monitor.primary:
                return idx
        return 0

    @property
    def active(self) -> Monitor:
        return self.monitors[self.active_index]

    @property
    def virtual_desktop(self) -> Rect:
        left = min(m.rect.x for m in self.monitors)
        top = min(m.rect.y for m in self.monitors)
        right = max(m.rect.right for m in self.monitors)
        bottom = max(m.rect.bottom for m in self.monitors)
        return Rect(left, top, right - left, bottom - top)

    def next(self) -> Monitor:
        self.active_index = (self.active_index + 1) % len(self.monitors)
        return self.active

    def previous(self) -> Monitor:
        self.active_index = (self.active_index - 1) % len(self.monitors)
        return self.active

    def neighbor(self, side: str) -> Monitor | None:
        active = self.active.rect
        candidates = []
        for index, monitor in enumerate(self.monitors):
            if index == self.active_index:
                continue
            rect = monitor.rect
            vertical_overlap = min(active.bottom, rect.bottom) - max(active.y, rect.y)
            if vertical_overlap <= 0:
                continue
            if side == "left" and rect.right <= active.x:
                candidates.append((active.x - rect.right, index, monitor))
            elif side == "right" and rect.x >= active.right:
                candidates.append((rect.x - active.right, index, monitor))
        if not candidates:
            return None
        _distance, index, monitor = min(candidates, key=lambda item: item[0])
        return monitor

    def switch_to(self, monitor: Monitor) -> Monitor:
        for index, candidate in enumerate(self.monitors):
            if candidate == monitor:
                self.active_index = index
                return self.active
        return self.active
