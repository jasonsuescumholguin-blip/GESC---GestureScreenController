from __future__ import annotations

from dataclasses import dataclass

from .config import AdaptiveGainConfig
from .tracker import HandFrame


@dataclass(frozen=True)
class AdaptiveGainState:
    gain: float
    hand_scale: float
    reference_scale: float
    normalized_xy: tuple[float, float]


class AdaptiveGainMapper:
    def __init__(self, config: AdaptiveGainConfig) -> None:
        self.config = config
        self._reference_scale = config.reference_hand_scale
        self._gain = 1.0

    def map(self, hand: HandFrame) -> AdaptiveGainState:
        nx, ny = hand.normalized_xy
        scale = self._hand_scale(hand.landmarks)

        if not self.config.enabled:
            return AdaptiveGainState(1.0, scale, self._reference_scale or scale, (nx, ny))

        if self._reference_scale is None:
            self._reference_scale = self.config.reference_hand_scale or scale

        if self.config.reference_adapt_rate > 0:
            rate = max(0.0, min(0.05, self.config.reference_adapt_rate))
            # Adapt only upward quickly enough to learn a comfortable closer hand,
            # while preserving extra gain when the hand appears smaller/farther.
            if scale > self._reference_scale:
                self._reference_scale = self._reference_scale + (scale - self._reference_scale) * rate

        raw_gain = self._reference_scale / max(0.001, scale)
        target_gain = max(self.config.min_gain, min(self.config.max_gain, raw_gain))
        smoothing = max(0.0, min(1.0, self.config.gain_smoothing))
        self._gain = self._gain + (target_gain - self._gain) * smoothing

        return AdaptiveGainState(self._gain, scale, self._reference_scale, (nx, ny))

    def reset(self) -> None:
        self._gain = 1.0

    def _hand_scale(self, landmarks: list[tuple[float, float, float]]) -> float:
        wrist_to_middle = self._distance(landmarks, 0, 9)
        palm_width = self._distance(landmarks, 5, 17)
        index_length = self._distance(landmarks, 5, 8)
        return max(0.001, wrist_to_middle, palm_width, index_length * 0.75)

    def _distance(self, landmarks: list[tuple[float, float, float]], first: int, second: int) -> float:
        ax, ay, _ = landmarks[first]
        bx, by, _ = landmarks[second]
        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
