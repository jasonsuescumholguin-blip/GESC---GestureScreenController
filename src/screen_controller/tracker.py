from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
import numpy as np

from .config import CameraConfig
from .config import project_root
from .geometry import Rect, active_camera_rect, normalize_in_rect


@dataclass(frozen=True)
class HandFrame:
    frame_width: int
    frame_height: int
    active_rect: Rect
    landmarks: list[tuple[float, float, float]]
    all_hands: list[list[tuple[float, float, float]]]
    index_xy: tuple[float, float]
    normalized_xy: tuple[float, float]

    def distance(self, first: int, second: int) -> float:
        ax, ay, _ = self.landmarks[first]
        bx, by, _ = self.landmarks[second]
        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5

    def landmark(self, index: int) -> tuple[float, float, float]:
        return self.landmarks[index]


class HandTracker:
    def __init__(self, config: CameraConfig) -> None:
        self.config = config
        self.cap: Any | None = None
        self._last_timestamp_ms = 0
        self._last_pointer_xy: tuple[float, float] | None = None
        self._landmarker = self._create_landmarker()

    def _create_landmarker(self):
        model_path = Path(self.config.model_path)
        if not model_path.is_absolute():
            model_path = project_root() / model_path
        if not model_path.exists():
            raise FileNotFoundError(
                "Falta el modelo de MediaPipe: "
                f"{model_path}. Ejecuta .\\scripts\\setup.ps1 para descargarlo."
            )

        base_options = mp.tasks.BaseOptions(model_asset_path=str(model_path))
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.55,
            min_hand_presence_confidence=0.55,
            min_tracking_confidence=0.55,
        )
        return mp.tasks.vision.HandLandmarker.create_from_options(options)

    def open(self) -> None:
        self.cap = cv2.VideoCapture(self.config.index, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            self.cap.release()
            self.cap = cv2.VideoCapture(self.config.index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.config.fps)
        if not self.cap.isOpened():
            raise RuntimeError(f"No se pudo abrir la camara indice {self.config.index}.")

    def read(self) -> tuple[HandFrame | None, Any | None]:
        if self.cap is None:
            self.open()

        ok, frame = self.cap.read()
        if not ok:
            return None, None

        if self.config.mirror:
            frame = cv2.flip(frame, 1)

        height, width = frame.shape[:2]
        active_rect = active_camera_rect(
            width,
            height,
            self.config.active_area_scale,
            self.config.active_area_aspect,
            self.config.active_area_top_margin,
            self.config.active_area_bottom_margin,
            self.config.active_area_side_margin,
            self.config.active_area_offset_x,
            self.config.active_area_offset_y,
        )
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb = np.ascontiguousarray(rgb)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        timestamp_ms = int(cv2.getTickCount() / cv2.getTickFrequency() * 1000)
        if timestamp_ms <= self._last_timestamp_ms:
            timestamp_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = timestamp_ms
        result = self._landmarker.detect_for_video(image, timestamp_ms)

        if not result.hand_landmarks:
            return None, frame

        hands = [[(lm.x, lm.y, lm.z) for lm in detected_hand] for detected_hand in result.hand_landmarks]
        pointer_index = self._select_pointer_hand(hands)
        if pointer_index != 0:
            hands[0], hands[pointer_index] = hands[pointer_index], hands[0]

        hand = hands[0]
        landmarks = hand
        ix = landmarks[8][0] * width
        iy = landmarks[8][1] * height
        self._last_pointer_xy = (landmarks[8][0], landmarks[8][1])
        normalized = normalize_in_rect(ix, iy, active_rect)
        return HandFrame(width, height, active_rect, landmarks, hands, (ix, iy), normalized), frame

    def _select_pointer_hand(self, hands: list[list[tuple[float, float, float]]]) -> int:
        if len(hands) <= 1:
            return 0
        preference = self.config.pointer_hand_preference.lower().strip()
        if preference in {"rightmost", "leftmost"}:
            return self._select_pointer_hand_by_side(hands, preference)
        if self._last_pointer_xy is not None:
            last_x, last_y = self._last_pointer_xy
            distances = []
            for hand in hands:
                ix, iy, _ = hand[8]
                distances.append(((ix - last_x) ** 2 + (iy - last_y) ** 2) ** 0.5)
            closest = min(range(len(distances)), key=distances.__getitem__)
            if distances[closest] < 0.18:
                return closest
        scores = [self._pointer_score(hand) for hand in hands]
        return max(range(len(scores)), key=scores.__getitem__)

    def _select_pointer_hand_by_side(self, hands: list[list[tuple[float, float, float]]], preference: str) -> int:
        centers = [self._hand_center_x(hand) for hand in hands]
        ordered = sorted(range(len(centers)), key=lambda index: centers[index], reverse=preference == "rightmost")
        preferred = ordered[0]
        runner_up = ordered[1]
        margin = max(0.0, min(0.3, self.config.pointer_switch_margin))
        if abs(centers[preferred] - centers[runner_up]) >= margin:
            return preferred

        if self._last_pointer_xy is not None:
            last_x, last_y = self._last_pointer_xy
            distances = []
            for hand in hands:
                ix, iy, _ = hand[8]
                distances.append(((ix - last_x) ** 2 + (iy - last_y) ** 2) ** 0.5)
            return min(range(len(distances)), key=distances.__getitem__)

        return preferred

    def _hand_center_x(self, landmarks: list[tuple[float, float, float]]) -> float:
        indices = [0, 5, 9, 13, 17]
        return sum(landmarks[index][0] for index in indices) / len(indices)

    def _pointer_score(self, landmarks: list[tuple[float, float, float]]) -> float:
        index_tip = landmarks[8]
        index_pip = landmarks[6]
        wrist = landmarks[0]
        index_extended = index_tip[1] < index_pip[1]
        other_folded = sum(1 for tip, pip in [(12, 10), (16, 14), (20, 18)] if landmarks[tip][1] > landmarks[pip][1])
        other_extended = 3 - other_folded
        wrist_to_index = ((index_tip[0] - wrist[0]) ** 2 + (index_tip[1] - wrist[1]) ** 2) ** 0.5
        return (3.0 if index_extended else 0.0) + other_folded - other_extended + wrist_to_index * 0.5

    def close(self) -> None:
        if self.cap is not None:
            self.cap.release()
        self._landmarker.close()
