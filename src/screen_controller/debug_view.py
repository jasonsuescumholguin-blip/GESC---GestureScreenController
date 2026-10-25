from __future__ import annotations

import cv2

from .config import DebugConfig
from .tracker import HandFrame


HAND_CONNECTIONS = [
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (5, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (9, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (13, 17),
    (17, 18),
    (18, 19),
    (19, 20),
    (0, 17),
]


class DebugCameraView:
    def __init__(self, config: DebugConfig) -> None:
        self.config = config
        self.enabled = config.show_camera
        self.window_name = "ScreenController camera diagnostic"
        self._visible = False

    def show(
        self,
        frame,
        hand: HandFrame | None,
        armed: bool,
        status: str,
        monitor_name: str,
        cursor_xy: tuple[int, int] | None,
        gesture_debug: str = "",
    ) -> None:
        self.enabled = self.config.show_camera
        if not self.enabled:
            if self._visible:
                self.close()
            return
        if frame is None:
            return

        view = frame.copy()
        height, width = view.shape[:2]
        if hand is not None:
            self._draw_active_rect(view, hand)
            self._draw_hands(view, hand)
            self._draw_pointer(view, hand, cursor_xy)

        mode = "ARMED" if armed else "IDLE"
        color = (0, 220, 160) if armed else (210, 210, 210)
        lines = [
            f"{mode} | {status}",
            f"Monitor: {monitor_name}",
            gesture_debug,
            "Ctrl+Alt+Space arma | Ctrl+Alt+M monitor | Ctrl+Alt+Q salir",
            "Main: indice cursor, indice+medio scroll. Aux: puno rest, palma precision, pinza drag.",
        ]
        for idx, line in enumerate(line for line in lines if line):
            y = 24 + idx * 24
            cv2.putText(view, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(view, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.58, color, 1, cv2.LINE_AA)

        scale = max(0.25, min(1.5, self.config.window_scale))
        if scale != 1.0:
            view = cv2.resize(view, (int(width * scale), int(height * scale)))
        cv2.imshow(self.window_name, view)
        self._visible = True
        cv2.waitKey(1)

    def close(self) -> None:
        if self._visible:
            try:
                cv2.destroyWindow(self.window_name)
            except cv2.error:
                pass
            self._visible = False

    def _draw_active_rect(self, view, hand: HandFrame) -> None:
        rect = hand.active_rect
        cv2.rectangle(view, (rect.x, rect.y), (rect.right, rect.bottom), (40, 220, 180), 2)
        for col in range(1, 4):
            x = rect.x + rect.width * col // 4
            cv2.line(view, (x, rect.y), (x, rect.bottom), (40, 220, 180), 1)
        for row in range(1, 4):
            y = rect.y + rect.height * row // 4
            cv2.line(view, (rect.x, y), (rect.right, y), (40, 220, 180), 1)

    def _draw_hands(self, view, hand: HandFrame) -> None:
        height, width = view.shape[:2]
        for hand_index, landmarks in enumerate(hand.all_hands):
            color = (80, 220, 190) if hand_index == 0 else (220, 170, 80)
            label = "pointer" if hand_index == 0 else "aux"
            for start, end in HAND_CONNECTIONS:
                sx, sy = self._to_px(landmarks[start], width, height)
                ex, ey = self._to_px(landmarks[end], width, height)
                cv2.line(view, (sx, sy), (ex, ey), color, 2)
            for index, landmark in enumerate(landmarks):
                x, y = self._to_px(landmark, width, height)
                radius = 5 if index in (4, 8, 12, 16, 20) else 3
                cv2.circle(view, (x, y), radius, color, -1)
            wx, wy = self._to_px(landmarks[0], width, height)
            cv2.putText(view, label, (wx + 8, wy - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(view, label, (wx + 8, wy - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)

    def _draw_pointer(self, view, hand: HandFrame, cursor_xy: tuple[int, int] | None) -> None:
        ix, iy = int(round(hand.index_xy[0])), int(round(hand.index_xy[1]))
        nx, ny = hand.normalized_xy
        cv2.circle(view, (ix, iy), 10, (255, 255, 255), 2)
        text = f"index cam=({ix},{iy}) norm=({nx:.2f},{ny:.2f})"
        if cursor_xy:
            text += f" screen={cursor_xy[0]},{cursor_xy[1]}"
        cv2.putText(view, text, (12, view.shape[0] - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(view, text, (12, view.shape[0] - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

    def _to_px(self, landmark: tuple[float, float, float], width: int, height: int) -> tuple[int, int]:
        return int(round(landmark[0] * width)), int(round(landmark[1] * height))
