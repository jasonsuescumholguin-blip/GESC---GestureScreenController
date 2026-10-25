from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def clamp_point(self, x: float, y: float) -> tuple[int, int]:
        return (
            max(self.x, min(self.right - 1, int(round(x)))),
            max(self.y, min(self.bottom - 1, int(round(y)))),
        )

    def contains(self, x: float, y: float) -> bool:
        return self.x <= x < self.right and self.y <= y < self.bottom


def active_camera_rect(
    frame_width: int,
    frame_height: int,
    scale: float,
    aspect: float | None = None,
    top_margin: float | None = None,
    bottom_margin: float | None = None,
    side_margin: float | None = None,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
) -> Rect:
    if aspect and top_margin is not None and bottom_margin is not None and side_margin is not None:
        aspect = max(0.5, min(3.0, aspect))
        top = int(frame_height * max(0.0, min(0.45, top_margin)))
        bottom = int(frame_height * (1.0 - max(0.0, min(0.55, bottom_margin))))
        max_width = int(frame_width * (1.0 - 2.0 * max(0.0, min(0.45, side_margin))))
        available_height = max(1, bottom - top)
        width = min(max_width, int(available_height * aspect))
        height = min(available_height, int(width / aspect))
        free_x = max(0, frame_width - width)
        free_y = max(0, available_height - height)
        x = int(free_x * max(0.0, min(1.0, offset_x)))
        y = top + int(free_y * max(0.0, min(1.0, offset_y)))
        return Rect(x=x, y=y, width=width, height=height)

    scale = max(0.2, min(1.0, scale))
    width = int(frame_width * scale)
    height = int(frame_height * scale)
    return Rect(
        x=(frame_width - width) // 2,
        y=(frame_height - height) // 2,
        width=width,
        height=height,
    )


def normalize_in_rect(x: float, y: float, rect: Rect) -> tuple[float, float]:
    nx = (x - rect.x) / max(1, rect.width)
    ny = (y - rect.y) / max(1, rect.height)
    return max(0.0, min(1.0, nx)), max(0.0, min(1.0, ny))


def map_normalized_to_rect(nx: float, ny: float, rect: Rect) -> tuple[int, int]:
    x = rect.x + nx * rect.width
    y = rect.y + ny * rect.height
    return rect.clamp_point(x, y)
