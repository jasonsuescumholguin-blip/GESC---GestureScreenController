from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .config import AppConfig, save_config


class ControlPanel(QWidget):
    def __init__(
        self,
        config: AppConfig,
        config_path: Path,
        on_reset_pointer: Callable[[], None],
        on_reset_gain: Callable[[], None],
    ) -> None:
        super().__init__()
        self.config = config
        self.config_path = config_path
        self.on_reset_pointer = on_reset_pointer
        self.on_reset_gain = on_reset_gain
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save)

        self.setWindowTitle("ScreenController controls")
        self.setWindowFlags(Qt.WindowType.Tool)
        self.resize(420, 680)

        root = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._pointer_tab(), "Pointer")
        tabs.addTab(self._gain_tab(), "Gain")
        tabs.addTab(self._surface_tab(), "Surface")
        tabs.addTab(self._clicks_tab(), "Clicks")
        tabs.addTab(self._scroll_tab(), "Scroll")
        tabs.addTab(self._zoom_tab(), "Zoom")
        tabs.addTab(self._overlay_tab(), "View")
        root.addWidget(tabs)

        actions = QHBoxLayout()
        save = QPushButton("Save config")
        save.clicked.connect(self._save)
        reset_pointer = QPushButton("Reset pointer")
        reset_pointer.clicked.connect(on_reset_pointer)
        reset_gain = QPushButton("Reset gain")
        reset_gain.clicked.connect(on_reset_gain)
        actions.addWidget(save)
        actions.addWidget(reset_pointer)
        actions.addWidget(reset_gain)
        root.addLayout(actions)

        self.status = QLabel("Changes apply immediately and auto-save.")
        root.addWidget(self.status)

    def _pointer_tab(self) -> QWidget:
        return self._form_tab(
            [
                self._float("Smoothing", self.config.mouse, "smoothing", 0.02, 0.6, 0.01),
                self._int("Deadzone px", self.config.mouse, "deadzone_px", 0, 20),
                self._int("Max jump px", self.config.mouse, "max_jump_px", 80, 800),
                self._float("Edge snap zone", self.config.mouse, "screen_edge_snap_zone", 0.0, 0.08, 0.005),
                self._bool("Move when unarmed", self.config.mouse, "move_when_unarmed"),
                self._bool("Adaptive filter", self.config.mouse, "adaptive_filter_enabled"),
                self._float("Precision smoothing", self.config.mouse, "precision_smoothing", 0.03, 0.85, 0.01),
                self._float("Travel smoothing", self.config.mouse, "travel_smoothing", 0.08, 1.0, 0.01),
                self._float("Catch-up smoothing", self.config.mouse, "catchup_smoothing", 0.1, 1.0, 0.01),
                self._float("Catch-up error px", self.config.mouse, "catchup_error_px", 8.0, 220.0, 1.0),
                self._float("Still speed px", self.config.mouse, "still_speed_px", 0.0, 18.0, 0.5),
                self._float("Still snap error px", self.config.mouse, "still_snap_error_px", 2.0, 60.0, 1.0),
                self._float("Still snap smoothing", self.config.mouse, "still_snap_smoothing", 0.1, 1.0, 0.01),
                self._bool("Grid re-entry snap", self.config.mouse, "grid_reentry_snap_enabled"),
                self._float("Re-entry snap strength", self.config.mouse, "grid_reentry_snap_strength", 0.0, 1.0, 0.01),
                self._float("Re-entry outside time", self.config.mouse, "grid_reentry_min_outside_seconds", 0.0, 0.5, 0.01),
                self._bool("Monitor handoff", self.config.mouse, "monitor_handoff_enabled"),
                self._float("Handoff min seconds", self.config.mouse, "monitor_handoff_min_seconds", 0.0, 0.8, 0.01),
                self._float("Handoff max seconds", self.config.mouse, "monitor_handoff_max_seconds", 0.1, 2.0, 0.05),
                self._float("Handoff release zone", self.config.mouse, "monitor_handoff_release_zone", 0.02, 0.45, 0.01),
                self._bool("Dynamic precision", self.config.mouse, "precision_accel_enabled"),
                self._float("Slow precision factor", self.config.mouse, "precision_slow_factor", 0.1, 1.0, 0.01),
                self._float("Fast travel factor", self.config.mouse, "precision_fast_factor", 1.0, 2.2, 0.02),
                self._float("Slow speed px", self.config.mouse, "precision_slow_speed_px", 1.0, 25.0, 0.5),
                self._float("Fast speed px", self.config.mouse, "precision_fast_speed_px", 20.0, 140.0, 1.0),
                self._float("Factor smoothing", self.config.mouse, "precision_factor_smoothing", 0.02, 0.6, 0.01),
                self._float("Grid anchor", self.config.mouse, "precision_anchor_strength", 0.0, 0.12, 0.005),
            ]
        )

    def _gain_tab(self) -> QWidget:
        return self._form_tab(
            [
                self._bool("Adaptive gain", self.config.adaptive_gain, "enabled"),
                self._float("Reference hand scale", self.config.adaptive_gain, "reference_hand_scale", 0.08, 0.35, 0.005),
                self._float("Min gain", self.config.adaptive_gain, "min_gain", 0.8, 2.0, 0.02),
                self._float("Max gain", self.config.adaptive_gain, "max_gain", 1.0, 3.5, 0.05),
                self._float("Gain smoothing", self.config.adaptive_gain, "gain_smoothing", 0.01, 0.6, 0.01),
                self._float("Reference adapt rate", self.config.adaptive_gain, "reference_adapt_rate", 0.0, 0.05, 0.002),
            ]
        )

    def _surface_tab(self) -> QWidget:
        return self._form_tab(
            [
                self._float("Aspect", self.config.camera, "active_area_aspect", 1.2, 2.4, 0.01),
                self._float("Top margin", self.config.camera, "active_area_top_margin", 0.0, 0.35, 0.01),
                self._float("Bottom margin", self.config.camera, "active_area_bottom_margin", 0.0, 0.45, 0.01),
                self._float("Side margin", self.config.camera, "active_area_side_margin", 0.0, 0.35, 0.01),
                self._float("Grid horizontal position", self.config.camera, "active_area_offset_x", 0.0, 1.0, 0.01),
                self._float("Grid vertical position", self.config.camera, "active_area_offset_y", 0.0, 1.0, 0.01),
                self._choice(
                    "Pointer hand",
                    self.config.camera,
                    "pointer_hand_preference",
                    [("Right side", "rightmost"), ("Left side", "leftmost"), ("Auto legacy", "auto")],
                ),
                self._float("Hand switch margin", self.config.camera, "pointer_switch_margin", 0.0, 0.2, 0.005),
                self._bool("Mirror camera", self.config.camera, "mirror"),
            ]
        )

    def _clicks_tab(self) -> QWidget:
        return self._form_tab(
            [
                self._float("Click cooldown", self.config.gestures, "click_cooldown_seconds", 0.05, 1.0, 0.01),
                self._float("Aux double window", self.config.gestures, "aux_double_click_seconds", 0.15, 0.9, 0.01),
                self._bool("Aux thumb drag", self.config.gestures, "aux_thumb_drag_enabled"),
                self._float("Thumb drag hold", self.config.gestures, "aux_thumb_drag_hold_seconds", 0.03, 0.8, 0.01),
                self._float("Thumb drag release grace", self.config.gestures, "aux_thumb_drag_release_grace_seconds", 0.0, 0.5, 0.01),
                self._float("Thumb extension", self.config.gestures, "aux_thumb_drag_extension_threshold", 0.35, 1.4, 0.01),
                self._bool("Aux pinch drag legacy", self.config.gestures, "aux_drag_pinch_enabled"),
                self._float("Aux drag pinch", self.config.gestures, "aux_drag_pinch_threshold", 0.15, 0.8, 0.01),
                self._float("Aux drag release", self.config.gestures, "aux_drag_release_threshold", 0.3, 1.2, 0.01),
                self._float("Drag hold", self.config.gestures, "drag_hold_seconds", 0.05, 1.0, 0.01),
                self._bool("Single-hand pinches", self.config.gestures, "single_hand_clicks_enabled"),
                self._float("Pinch index", self.config.gestures, "pinch_threshold", 0.15, 0.8, 0.01),
                self._float("Pinch middle", self.config.gestures, "right_pinch_threshold", 0.15, 0.9, 0.01),
                self._float("Pinch ring", self.config.gestures, "double_pinch_threshold", 0.15, 0.9, 0.01),
                self._float("Pinch release", self.config.gestures, "click_release_threshold", 0.25, 1.2, 0.01),
            ]
        )

    def _scroll_tab(self) -> QWidget:
        return self._form_tab(
            [
                self._float("Scroll deadzone", self.config.gestures, "scroll_deadzone", 0.0, 0.03, 0.001),
                self._float("Scroll gain", self.config.gestures, "scroll_gain", 20.0, 360.0, 5.0),
                self._float("Scroll precision", self.config.gestures, "scroll_precision_multiplier", 0.1, 1.0, 0.01),
                self._float("Scroll finger margin", self.config.gestures, "scroll_finger_extension_margin", 0.0, 0.12, 0.005),
                self._float("Scroll cooldown", self.config.gestures, "scroll_cooldown_seconds", 0.0, 0.2, 0.005),
                self._int("Scroll max ticks", self.config.gestures, "scroll_max_ticks", 1, 20),
                self._bool("Invert scroll", self.config.gestures, "scroll_invert"),
                self._float("Fist thumb threshold", self.config.gestures, "fist_thumb_threshold", 0.55, 2.0, 0.02),
            ]
        )

    def _zoom_tab(self) -> QWidget:
        return self._form_tab(
            [
                self._float("Zoom movement threshold", self.config.gestures, "zoom_delta_threshold", 0.002, 0.06, 0.001),
                self._float("Zoom cooldown", self.config.gestures, "zoom_cooldown_seconds", 0.0, 0.4, 0.01),
                self._int("Zoom max steps", self.config.gestures, "zoom_max_steps", 1, 10),
                self._float("Precision mode gain", self.config.gestures, "precision_mode_pointer_gain", 0.2, 1.0, 0.01),
                self._bool("Touch back/forward", self.config.gestures, "touch_commands_enabled"),
                self._float("Touch distance", self.config.gestures, "touch_command_threshold", 0.08, 0.8, 0.01),
                self._float("Touch release", self.config.gestures, "touch_command_release_threshold", 0.1, 1.2, 0.01),
                self._float("Touch cooldown", self.config.gestures, "touch_command_cooldown_seconds", 0.2, 2.0, 0.05),
                self._bool("Swipe commands legacy", self.config.gestures, "swipe_enabled"),
                self._float("Monitor hold", self.config.gestures, "monitor_switch_hold_seconds", 0.2, 1.5, 0.05),
                self._float("Monitor cooldown", self.config.gestures, "monitor_switch_cooldown_seconds", 0.4, 3.0, 0.1),
                self._bool("Monitor transfer", self.config.monitors, "transfer_enabled"),
                self._float("Transfer zone", self.config.monitors, "transfer_zone", 0.01, 0.14, 0.005),
                self._float("Transfer vertical coverage", self.config.monitors, "transfer_vertical_coverage", 0.1, 1.0, 0.05),
                self._float("Transfer dwell", self.config.monitors, "transfer_dwell_seconds", 0.15, 1.5, 0.05),
                self._float("Transfer cooldown", self.config.monitors, "transfer_cooldown_seconds", 0.2, 2.5, 0.05),
                self._float("Transfer entry", self.config.monitors, "transfer_entry_offset", 0.005, 0.15, 0.005),
            ]
        )

    def _overlay_tab(self) -> QWidget:
        return self._form_tab(
            [
                self._bool("Show control panel on start", self.config.debug, "show_control_panel"),
                self._bool("Camera window", self.config.debug, "show_camera"),
                self._float("Camera window scale", self.config.debug, "window_scale", 0.3, 1.5, 0.05),
                self._bool("Overlay grid", self.config.overlay, "show_grid"),
                self._float("Overlay opacity", self.config.overlay, "opacity", 0.1, 1.0, 0.05),
                self._float("Trace seconds", self.config.overlay, "trace_seconds", 0.1, 4.0, 0.1),
                self._int("Max trace points", self.config.overlay, "max_points", 10, 300),
                self._float("Action pulse seconds", self.config.overlay, "action_pulse_seconds", 0.05, 1.2, 0.05),
            ]
        )

    def _form_tab(self, rows: list[tuple[str, QWidget]]) -> QWidget:
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        for label, widget in rows:
            form.addRow(label, widget)

        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setWidget(form_widget)
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.addWidget(scroller)
        return wrapper

    def _float(self, label: str, target, attr: str, minimum: float, maximum: float, step: float) -> tuple[str, QWidget]:
        widget = QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setSingleStep(step)
        widget.setDecimals(3 if step < 0.01 else 2)
        value = getattr(target, attr)
        widget.setValue(float(value) if value is not None else minimum)
        widget.valueChanged.connect(lambda value, target=target, attr=attr: self._set_value(target, attr, float(value)))
        return label, widget

    def _int(self, label: str, target, attr: str, minimum: int, maximum: int) -> tuple[str, QWidget]:
        widget = QSpinBox()
        widget.setRange(minimum, maximum)
        widget.setValue(int(getattr(target, attr)))
        widget.valueChanged.connect(lambda value, target=target, attr=attr: self._set_value(target, attr, int(value)))
        return label, widget

    def _bool(self, label: str, target, attr: str) -> tuple[str, QWidget]:
        widget = QCheckBox()
        widget.setChecked(bool(getattr(target, attr)))
        widget.stateChanged.connect(lambda state, target=target, attr=attr: self._set_value(target, attr, state == Qt.CheckState.Checked.value))
        return label, widget

    def _choice(self, label: str, target, attr: str, options: list[tuple[str, str]]) -> tuple[str, QWidget]:
        widget = QComboBox()
        for text, value in options:
            widget.addItem(text, value)
        current = str(getattr(target, attr))
        index = widget.findData(current)
        widget.setCurrentIndex(max(0, index))
        widget.currentIndexChanged.connect(lambda _index, target=target, attr=attr, widget=widget: self._set_value(target, attr, widget.currentData()))
        return label, widget

    def _set_value(self, target, attr: str, value) -> None:
        setattr(target, attr, value)
        self.status.setText("Unsaved change... auto-saving")
        self._save_timer.start(700)

    def _save(self) -> None:
        save_config(self.config, self.config_path)
        self.status.setText(f"Saved: {self.config_path}")
