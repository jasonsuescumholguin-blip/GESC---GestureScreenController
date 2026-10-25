from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import time

from .config import GestureConfig
from .tracker import HandFrame


class MouseAction(str, Enum):
    NONE = "none"
    LEFT_CLICK = "left_click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    DRAG_START = "drag_start"
    DRAG_END = "drag_end"
    SCROLL = "scroll"
    NEXT_MONITOR = "next_monitor"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    BACK = "back"
    FORWARD = "forward"


@dataclass(frozen=True)
class GestureEvent:
    action: MouseAction
    scroll_y: int = 0
    steps: int = 1
    block_move: bool = False
    precision_mode: bool = False


class GestureInterpreter:
    def __init__(self, config: GestureConfig) -> None:
        self.config = config
        self._left_pinching = False
        self._right_pinching = False
        self._double_pinching = False
        self._dragging = False
        self._pinch_started_at = 0.0
        self._last_scroll_y: float | None = None
        self._last_scroll_at = 0.0
        self._scroll_active = False
        self._scroll_accumulator = 0.0
        self._two_fists_since: float | None = None
        self._last_monitor_switch_at = 0.0
        self._last_zoom_distance: float | None = None
        self._last_zoom_at = 0.0
        self._last_click_at = 0.0
        self._aux_pose: str | None = None
        self._aux_open_since: float | None = None
        self._aux_index_raise_at = 0.0
        self._aux_index_cycle_ready = False
        self._aux_dragging = False
        self._aux_drag_candidate_since: float | None = None
        self._aux_drag_release_since: float | None = None
        self._swipe_start: tuple[float, float, float] | None = None
        self._last_swipe_at = 0.0
        self._touch_pose: str | None = None
        self._last_touch_command_at = 0.0
        self.precision_active = False
        self.debug_text = "gesture: none"

    def update(self, hand: HandFrame) -> GestureEvent:
        now = time.monotonic()
        self.debug_text = "gesture: none"
        self.precision_active = False

        zoom = self._zoom_event(hand, now)
        if zoom:
            return zoom

        touch = self._touch_command_event(hand, now)
        if touch:
            return touch

        auxiliary = self._auxiliary_hand_event(hand, now)
        if auxiliary:
            if auxiliary.action != MouseAction.NONE or auxiliary.block_move:
                return auxiliary

        scroll = self._scroll_event(hand)
        if scroll:
            return scroll

        if self._is_fist(hand.landmarks):
            self.debug_text = "gesture: main rest"
            return GestureEvent(MouseAction.NONE, block_move=True)

        if len(hand.all_hands) >= 2 or not self.config.single_hand_clicks_enabled:
            return GestureEvent(MouseAction.NONE, precision_mode=self.precision_active)

        return self._single_hand_click_event(hand, now)

    def _single_hand_click_event(self, hand: HandFrame, now: float) -> GestureEvent:
        palm_scale = self._palm_scale(hand.landmarks)
        left_distance = hand.distance(4, 8) / palm_scale
        right_distance = hand.distance(4, 12) / palm_scale
        double_distance = hand.distance(4, 16) / palm_scale
        self.debug_text = f"pinch ratios i={left_distance:.2f} m={right_distance:.2f} r={double_distance:.2f}"

        left_pinching = self._left_pinching
        if not self._left_pinching and left_distance <= self.config.pinch_threshold:
            left_pinching = True
        elif self._left_pinching and left_distance >= self.config.click_release_threshold:
            left_pinching = False

        right_pinching = self._right_pinching
        if not self._right_pinching and right_distance <= self.config.right_pinch_threshold:
            right_pinching = True
        elif self._right_pinching and right_distance >= self.config.click_release_threshold:
            right_pinching = False

        double_pinching = self._double_pinching
        if not self._double_pinching and double_distance <= self.config.double_pinch_threshold:
            double_pinching = True
        elif self._double_pinching and double_distance >= self.config.click_release_threshold:
            double_pinching = False

        if right_pinching and not self._right_pinching and not left_pinching:
            self._right_pinching = True
            if self._click_ready(now):
                self._last_click_at = now
                return GestureEvent(MouseAction.RIGHT_CLICK, block_move=True)
        if not right_pinching:
            self._right_pinching = False
        elif self._right_pinching:
            return GestureEvent(MouseAction.NONE)

        if double_pinching and not self._double_pinching and not left_pinching and not right_pinching:
            self._double_pinching = True
            if self._click_ready(now):
                self._last_click_at = now
                return GestureEvent(MouseAction.DOUBLE_CLICK, block_move=True)
        if not double_pinching:
            self._double_pinching = False
        elif self._double_pinching:
            return GestureEvent(MouseAction.NONE)

        if left_pinching and not self._left_pinching:
            self._left_pinching = True
            self._pinch_started_at = now
            if self._click_ready(now):
                self._last_click_at = now
                return GestureEvent(MouseAction.LEFT_CLICK, block_move=True)
            return GestureEvent(MouseAction.NONE)

        if left_pinching and self._left_pinching and not self._dragging:
            if self.config.drag_enabled and now - self._pinch_started_at >= self.config.drag_hold_seconds:
                self._dragging = True
                return GestureEvent(MouseAction.DRAG_START, block_move=False)

        if left_pinching and self._left_pinching and not self._dragging:
            return GestureEvent(MouseAction.NONE)

        if not left_pinching and self._left_pinching:
            self._left_pinching = False
            held = now - self._pinch_started_at
            if self._dragging:
                self._dragging = False
                return GestureEvent(MouseAction.DRAG_END)
            if held < self.config.drag_hold_seconds:
                return GestureEvent(MouseAction.NONE)

        return GestureEvent(MouseAction.NONE)

    def _auxiliary_hand_event(self, hand: HandFrame, now: float) -> GestureEvent | None:
        if len(hand.all_hands) < 2:
            self._aux_open_since = None
            self._swipe_start = None
            self._aux_drag_candidate_since = None
            self._aux_drag_release_since = None
            if self._aux_dragging:
                self._aux_dragging = False
                self._aux_pose = None
                return GestureEvent(MouseAction.DRAG_END, block_move=False)
            return None

        auxiliary = hand.all_hands[1]

        thumb_drag = self._thumb_drag_event(auxiliary, now)
        if thumb_drag:
            return thumb_drag

        if self._is_fist(auxiliary):
            self._aux_open_since = None
            self._swipe_start = None
            self._aux_drag_candidate_since = None
            self._aux_drag_release_since = None
            self._aux_pose = "fist"
            if self._aux_dragging:
                self._aux_dragging = False
                return GestureEvent(MouseAction.DRAG_END, block_move=False)
            self.debug_text = "gesture: aux rest"
            return None

        aux_drag_pinching = self._is_aux_drag_pinch(auxiliary)
        if self.config.drag_enabled and self.config.aux_drag_pinch_enabled and aux_drag_pinching:
            self._aux_open_since = None
            self._swipe_start = None
            self._aux_drag_release_since = None
            self.debug_text = "gesture: aux pinch hold -> drag"
            if self._aux_dragging:
                return GestureEvent(MouseAction.NONE, block_move=False)
            if self._aux_drag_candidate_since is None:
                self._aux_drag_candidate_since = now
                return GestureEvent(MouseAction.NONE, block_move=False)
            if now - self._aux_drag_candidate_since >= self.config.drag_hold_seconds:
                self._aux_dragging = True
                self._aux_pose = "drag_pinch"
                return GestureEvent(MouseAction.DRAG_START, block_move=False)
            return GestureEvent(MouseAction.NONE, block_move=False)

        if self._aux_dragging:
            if not self._is_aux_drag_release(auxiliary):
                return GestureEvent(MouseAction.NONE, block_move=False)
            self._aux_dragging = False
            self._aux_pose = None
            self._aux_drag_candidate_since = None
            self._aux_drag_release_since = None
            return GestureEvent(MouseAction.DRAG_END, block_move=False)
        self._aux_drag_candidate_since = None
        self._aux_drag_release_since = None

        if self._is_open_palm_landmarks(auxiliary):
            self.precision_active = True
            self._aux_pose = "open"
            if self._aux_open_since is None:
                self._aux_open_since = now
                self._swipe_start = None
                self.debug_text = "gesture: precision ready"
                return GestureEvent(MouseAction.NONE, precision_mode=True)

            self.debug_text = "gesture: precision"
            return GestureEvent(MouseAction.NONE, precision_mode=True)

        self._aux_open_since = None
        self._swipe_start = None

        if self._is_index_only_pose(auxiliary):
            self.debug_text = "gesture: aux index -> left/double click"
            if self._aux_pose == "index":
                return GestureEvent(MouseAction.NONE, block_move=True)
            self._aux_pose = "index"
            if self._aux_index_cycle_ready and now - self._aux_index_raise_at <= self.config.aux_double_click_seconds:
                self._aux_index_cycle_ready = False
                self._aux_index_raise_at = 0.0
                self._last_click_at = now
                return GestureEvent(MouseAction.LEFT_CLICK, block_move=True)
            self._aux_index_raise_at = now
            self._aux_index_cycle_ready = False
            if self._click_ready(now):
                self._last_click_at = now
                return GestureEvent(MouseAction.LEFT_CLICK, block_move=True)
            return GestureEvent(MouseAction.NONE, block_move=True)

        if self._aux_pose == "index":
            self._aux_index_cycle_ready = True

        if self._is_two_finger_pose(auxiliary):
            self.debug_text = "gesture: aux two fingers -> right click"
            if self._aux_pose == "two":
                return GestureEvent(MouseAction.NONE, block_move=True)
            self._aux_pose = "two"
            if self._click_ready(now):
                self._last_click_at = now
                return GestureEvent(MouseAction.RIGHT_CLICK, block_move=True)
            return GestureEvent(MouseAction.NONE, block_move=True)

        self._aux_pose = None
        return None

    def _zoom_event(self, hand: HandFrame, now: float) -> GestureEvent | None:
        two_open_palms = len(hand.all_hands) >= 2 and all(self._is_open_palm_landmarks(landmarks) for landmarks in hand.all_hands[:2])
        if not two_open_palms:
            self._last_zoom_distance = None
            return None

        self.precision_active = False
        centers = [self._palm_center(landmarks) for landmarks in hand.all_hands[:2]]
        distance = abs(centers[0][0] - centers[1][0])
        if self._last_zoom_distance is None:
            self._last_zoom_distance = distance
            return GestureEvent(MouseAction.NONE, block_move=True)

        delta = distance - self._last_zoom_distance
        self._last_zoom_distance = distance
        if now - self._last_zoom_at < self.config.zoom_cooldown_seconds:
            return GestureEvent(MouseAction.NONE, block_move=True)

        if delta >= self.config.zoom_delta_threshold:
            self._last_zoom_at = now
            steps = self._zoom_steps(delta)
            self.debug_text = f"gesture: zoom in x{steps}"
            return GestureEvent(MouseAction.ZOOM_IN, steps=steps, block_move=True)
        if delta <= -self.config.zoom_delta_threshold:
            self._last_zoom_at = now
            steps = self._zoom_steps(abs(delta))
            self.debug_text = f"gesture: zoom out x{steps}"
            return GestureEvent(MouseAction.ZOOM_OUT, steps=steps, block_move=True)

        return GestureEvent(MouseAction.NONE, block_move=True)

    def _touch_command_event(self, hand: HandFrame, now: float) -> GestureEvent | None:
        if not self.config.touch_commands_enabled or len(hand.all_hands) < 2:
            self._touch_pose = None
            return None

        main = hand.landmarks
        auxiliary = hand.all_hands[1]
        if self._is_fist(main) or self._is_fist(auxiliary):
            self._touch_pose = None
            return None

        index_distance = self._inter_hand_distance(main, auxiliary, 8, 8)
        pinky_distance = self._inter_hand_distance(main, auxiliary, 20, 20)
        threshold = max(0.08, self.config.touch_command_threshold)
        release_threshold = max(threshold + 0.02, self.config.touch_command_release_threshold)

        if self._touch_pose is not None:
            active_distance = index_distance if self._touch_pose == "index" else pinky_distance
            if active_distance <= release_threshold:
                self.debug_text = f"gesture: touch {self._touch_pose} hold"
                return GestureEvent(MouseAction.NONE, block_move=True)
            self._touch_pose = None
            return None

        index_touch = (
            index_distance <= threshold
            and pinky_distance > threshold
            and index_distance + 0.08 < pinky_distance
            and self._is_finger_extended(main, 8, 6)
            and self._is_finger_extended(auxiliary, 8, 6)
        )
        pinky_touch = (
            pinky_distance <= threshold
            and index_distance > threshold
            and pinky_distance + 0.08 < index_distance
            and self._is_finger_extended(main, 20, 18)
            and self._is_finger_extended(auxiliary, 20, 18)
        )

        if not index_touch and not pinky_touch:
            if min(index_distance, pinky_distance) <= threshold:
                self.debug_text = "gesture: touch ambiguous"
                return GestureEvent(MouseAction.NONE, block_move=True)
            return None

        if now - self._last_touch_command_at < self.config.touch_command_cooldown_seconds:
            self.debug_text = "gesture: touch cooldown"
            return GestureEvent(MouseAction.NONE, block_move=True)

        self._last_touch_command_at = now
        if index_touch:
            self._touch_pose = "index"
            self.debug_text = "gesture: index touch -> forward"
            return GestureEvent(MouseAction.FORWARD, block_move=True)

        self._touch_pose = "pinky"
        self.debug_text = "gesture: pinky touch -> back"
        return GestureEvent(MouseAction.BACK, block_move=True)

    def _thumb_drag_event(self, auxiliary: list[tuple[float, float, float]], now: float) -> GestureEvent | None:
        if not self.config.drag_enabled or not self.config.aux_thumb_drag_enabled:
            return None

        thumb_only = self._is_thumb_only_pose(auxiliary)
        if thumb_only:
            self._aux_open_since = None
            self._swipe_start = None
            self._aux_drag_release_since = None
            self.debug_text = "gesture: aux thumb hold -> drag"
            if self._aux_dragging:
                return GestureEvent(MouseAction.NONE, block_move=False)
            if self._aux_drag_candidate_since is None or self._aux_pose != "thumb_drag":
                self._aux_drag_candidate_since = now
                self._aux_pose = "thumb_drag"
                return GestureEvent(MouseAction.NONE, block_move=False)
            if now - self._aux_drag_candidate_since >= self.config.aux_thumb_drag_hold_seconds:
                self._aux_dragging = True
                return GestureEvent(MouseAction.DRAG_START, block_move=False)
            return GestureEvent(MouseAction.NONE, block_move=False)

        if self._aux_pose == "thumb_drag" and not self._aux_dragging:
            self._aux_pose = None
            self._aux_drag_candidate_since = None
            return None

        if not self._aux_dragging:
            return None

        if self._aux_drag_release_since is None:
            self._aux_drag_release_since = now
            if self.config.aux_thumb_drag_release_grace_seconds <= 0:
                self._aux_dragging = False
                self._aux_pose = None
                self._aux_drag_candidate_since = None
                self._aux_drag_release_since = None
                return GestureEvent(MouseAction.DRAG_END, block_move=False)
            self.debug_text = "gesture: drag release grace"
            return GestureEvent(MouseAction.NONE, block_move=False)

        if now - self._aux_drag_release_since < self.config.aux_thumb_drag_release_grace_seconds:
            self.debug_text = "gesture: drag release grace"
            return GestureEvent(MouseAction.NONE, block_move=False)

        self._aux_dragging = False
        self._aux_pose = None
        self._aux_drag_candidate_since = None
        self._aux_drag_release_since = None
        return GestureEvent(MouseAction.DRAG_END, block_move=False)

    def _swipe_event(self, hand: HandFrame, now: float) -> GestureEvent | None:
        if not self.config.swipe_enabled or self._aux_open_since is None:
            self._swipe_start = None
            return None
        if now - self._last_swipe_at < self.config.swipe_cooldown_seconds:
            self._swipe_start = None
            return None
        if now - self._aux_open_since < self.config.swipe_aux_hold_seconds:
            self._swipe_start = None
            return None
        if not self._is_index_only_pose(hand.landmarks):
            self._swipe_start = None
            return None

        ix, iy, _ = hand.landmarks[8]
        if self._swipe_start is None:
            self._swipe_start = (ix, iy, now)
            return None

        start_x, start_y, started_at = self._swipe_start
        elapsed = now - started_at
        if elapsed > self.config.swipe_max_duration_seconds:
            self._swipe_start = (ix, iy, now)
            return None

        dx = ix - start_x
        dy = iy - start_y
        if abs(dx) < self.config.swipe_min_distance:
            return None
        if abs(dy) > abs(dx) * self.config.swipe_vertical_tolerance:
            self._swipe_start = (ix, iy, now)
            return None

        self._last_swipe_at = now
        self._swipe_start = None
        if dx < 0:
            self.debug_text = "gesture: swipe back"
            return GestureEvent(MouseAction.BACK, block_move=True, precision_mode=True)
        self.debug_text = "gesture: swipe forward"
        return GestureEvent(MouseAction.FORWARD, block_move=True, precision_mode=True)

    def _scroll_event(self, hand: HandFrame) -> GestureEvent | None:
        if self._left_pinching or self._right_pinching or self._aux_dragging:
            self._reset_scroll()
            return None

        if not self._scroll_active:
            if not self._is_main_scroll_pose(hand.landmarks):
                self._reset_scroll()
                return None
            self._scroll_active = True
            self._last_scroll_y = self._scroll_center_y(hand.landmarks)
            self._scroll_accumulator = 0.0
            self.debug_text = "gesture: scroll ready"
            return GestureEvent(MouseAction.NONE, block_move=True, precision_mode=self.precision_active)

        if not self._is_main_scroll_pose(hand.landmarks):
            self._reset_scroll()
            return None

        current_y = self._scroll_center_y(hand.landmarks)
        if self._last_scroll_y is None:
            self._last_scroll_y = current_y
            return GestureEvent(MouseAction.NONE, block_move=True, precision_mode=self.precision_active)

        delta = self._last_scroll_y - current_y
        self._last_scroll_y = current_y
        if self.config.scroll_invert:
            delta = -delta

        if abs(delta) < self.config.scroll_deadzone:
            self.debug_text = "gesture: scroll hold"
            return GestureEvent(MouseAction.NONE, block_move=True, precision_mode=self.precision_active)

        multiplier = self.config.scroll_precision_multiplier if self.precision_active else 1.0
        self._scroll_accumulator += delta * self.config.scroll_gain * multiplier
        ticks = int(self._scroll_accumulator)
        if ticks == 0:
            self.debug_text = f"gesture: scroll accumulating {self._scroll_accumulator:.2f}"
            return GestureEvent(MouseAction.NONE, block_move=True, precision_mode=self.precision_active)

        max_ticks = max(1, self.config.scroll_max_ticks)
        ticks = max(-max_ticks, min(max_ticks, ticks))
        self._scroll_accumulator -= ticks

        now = time.monotonic()
        if self.config.scroll_cooldown_seconds > 0 and now - self._last_scroll_at < self.config.scroll_cooldown_seconds:
            self.debug_text = "gesture: scroll cooldown"
            return GestureEvent(MouseAction.NONE, block_move=True, precision_mode=self.precision_active)

        self._last_scroll_at = now
        self.debug_text = f"gesture: scroll {ticks:+d}"
        return GestureEvent(MouseAction.SCROLL, ticks, block_move=True, precision_mode=self.precision_active)

    def _reset_scroll(self) -> None:
        self._last_scroll_y = None
        self._scroll_active = False
        self._scroll_accumulator = 0.0

    def _zoom_steps(self, delta: float) -> int:
        threshold = max(0.001, self.config.zoom_delta_threshold)
        max_steps = max(1, self.config.zoom_max_steps)
        return max(1, min(max_steps, int(delta / threshold)))

    def _scroll_center_y(self, landmarks: list[tuple[float, float, float]]) -> float:
        indices = [0, 5, 9, 13, 17]
        return sum(landmarks[index][1] for index in indices) / len(indices)

    def _folded_finger_count(self, landmarks: list[tuple[float, float, float]]) -> int:
        return sum(1 for tip, pip in [(8, 6), (12, 10), (16, 14), (20, 18)] if landmarks[tip][1] > landmarks[pip][1])

    def _is_open_palm_landmarks(self, landmarks: list[tuple[float, float, float]]) -> bool:
        fingers = [(8, 6), (12, 10), (16, 14), (20, 18)]
        extended = sum(1 for tip, pip in fingers if landmarks[tip][1] < landmarks[pip][1])
        return extended >= 4

    def _is_fist(self, landmarks: list[tuple[float, float, float]]) -> bool:
        return self._folded_finger_count(landmarks) >= 4 and self._is_thumb_closed(landmarks)

    def _is_thumb_closed(self, landmarks: list[tuple[float, float, float]]) -> bool:
        palm_scale = self._palm_scale(landmarks)
        thumb_tip_to_palm = self._distance_to_point(landmarks[4], self._palm_center(landmarks))
        thumb_tip_to_index_base = self._distance_landmarks(landmarks, 4, 5)
        threshold = max(0.55, self.config.fist_thumb_threshold)
        return min(thumb_tip_to_palm, thumb_tip_to_index_base) / palm_scale <= threshold

    def _is_two_finger_pose(self, landmarks: list[tuple[float, float, float]]) -> bool:
        index = landmarks[8][1] < landmarks[6][1]
        middle = landmarks[12][1] < landmarks[10][1]
        ring = landmarks[16][1] > landmarks[14][1]
        pinky = landmarks[20][1] > landmarks[18][1]
        return index and middle and ring and pinky

    def _is_main_scroll_pose(self, landmarks: list[tuple[float, float, float]]) -> bool:
        margin = max(0.0, min(0.12, self.config.scroll_finger_extension_margin))
        index = self._is_finger_extended(landmarks, 8, 6, margin)
        middle = self._is_finger_extended(landmarks, 12, 10, margin)
        ring = landmarks[16][1] > landmarks[14][1]
        pinky = landmarks[20][1] > landmarks[18][1]
        return index and middle and ring and pinky

    def _is_index_only_pose(self, landmarks: list[tuple[float, float, float]]) -> bool:
        index = self._is_finger_extended(landmarks, 8, 6)
        middle = landmarks[12][1] > landmarks[10][1]
        ring = landmarks[16][1] > landmarks[14][1]
        pinky = landmarks[20][1] > landmarks[18][1]
        return index and middle and ring and pinky

    def _is_thumb_only_pose(self, landmarks: list[tuple[float, float, float]]) -> bool:
        palm_scale = self._palm_scale(landmarks)
        thumb_tip_to_palm = self._distance_to_point(landmarks[4], self._palm_center(landmarks)) / palm_scale
        thumb_tip_to_index_base = self._distance_landmarks(landmarks, 4, 5) / palm_scale
        thumb_extended = max(thumb_tip_to_palm, thumb_tip_to_index_base) >= self.config.aux_thumb_drag_extension_threshold
        index_folded = landmarks[8][1] > landmarks[6][1]
        middle_folded = landmarks[12][1] > landmarks[10][1]
        ring_folded = landmarks[16][1] > landmarks[14][1]
        pinky_folded = landmarks[20][1] > landmarks[18][1]
        return thumb_extended and index_folded and middle_folded and ring_folded and pinky_folded

    def _is_aux_drag_pinch(self, landmarks: list[tuple[float, float, float]]) -> bool:
        if self._is_fist(landmarks):
            return False
        palm_scale = self._palm_scale(landmarks)
        pinch_ratio = self._distance_landmarks(landmarks, 4, 8) / palm_scale
        index_alive = landmarks[8][1] < landmarks[5][1]
        return index_alive and pinch_ratio <= self.config.aux_drag_pinch_threshold

    def _is_aux_drag_release(self, landmarks: list[tuple[float, float, float]]) -> bool:
        if self._is_fist(landmarks):
            return True
        palm_scale = self._palm_scale(landmarks)
        pinch_ratio = self._distance_landmarks(landmarks, 4, 8) / palm_scale
        return pinch_ratio >= self.config.aux_drag_release_threshold

    def _palm_center(self, landmarks: list[tuple[float, float, float]]) -> tuple[float, float]:
        indices = [0, 5, 9, 13, 17]
        x = sum(landmarks[index][0] for index in indices) / len(indices)
        y = sum(landmarks[index][1] for index in indices) / len(indices)
        return x, y

    def _palm_scale(self, landmarks: list[tuple[float, float, float]]) -> float:
        wrist_to_middle = self._distance_landmarks(landmarks, 0, 9)
        palm_width = self._distance_landmarks(landmarks, 5, 17)
        return max(0.03, wrist_to_middle, palm_width)

    def _is_finger_extended(self, landmarks: list[tuple[float, float, float]], tip: int, pip: int, margin: float = 0.0) -> bool:
        return landmarks[tip][1] < landmarks[pip][1] - margin

    def _inter_hand_distance(
        self,
        main: list[tuple[float, float, float]],
        auxiliary: list[tuple[float, float, float]],
        main_index: int,
        auxiliary_index: int,
    ) -> float:
        distance = self._distance_points(main[main_index], auxiliary[auxiliary_index])
        scale = (self._palm_scale(main) + self._palm_scale(auxiliary)) / 2.0
        return distance / max(0.03, scale)

    def _distance_landmarks(self, landmarks: list[tuple[float, float, float]], first: int, second: int) -> float:
        ax, ay, _ = landmarks[first]
        bx, by, _ = landmarks[second]
        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5

    def _distance_to_point(self, landmark: tuple[float, float, float], point: tuple[float, float]) -> float:
        ax, ay, _ = landmark
        bx, by = point
        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5

    def _distance_points(self, first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
        ax, ay, _ = first
        bx, by, _ = second
        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5

    def _click_ready(self, now: float) -> bool:
        return now - self._last_click_at >= self.config.click_cooldown_seconds

    def reset(self) -> None:
        was_dragging = self._dragging
        self._left_pinching = False
        self._right_pinching = False
        self._double_pinching = False
        self._dragging = False
        self._reset_scroll()
        self._two_fists_since = None
        self._last_zoom_distance = None
        self._aux_pose = None
        self._aux_open_since = None
        self._aux_index_raise_at = 0.0
        self._aux_index_cycle_ready = False
        self._aux_dragging = False
        self._aux_drag_candidate_since = None
        self._aux_drag_release_since = None
        self._swipe_start = None
        self._touch_pose = None
        self._last_touch_command_at = 0.0
        self.precision_active = False
        if was_dragging:
            self._pinch_started_at = 0.0
