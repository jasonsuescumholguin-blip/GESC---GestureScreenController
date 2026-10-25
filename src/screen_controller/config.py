from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import sys


@dataclass
class CameraConfig:
    index: int = 0
    width: int = 960
    height: int = 540
    fps: int = 30
    mirror: bool = True
    active_area_scale: float = 0.75
    active_area_aspect: float = 16 / 9
    active_area_top_margin: float = 0.06
    active_area_bottom_margin: float = 0.24
    active_area_side_margin: float = 0.06
    active_area_offset_x: float = 0.5
    active_area_offset_y: float = 0.5
    pointer_hand_preference: str = "rightmost"
    pointer_switch_margin: float = 0.06
    model_path: str = "models/hand_landmarker.task"


@dataclass
class DebugConfig:
    show_camera: bool = True
    show_control_panel: bool = True
    window_scale: float = 0.85


@dataclass
class MouseConfig:
    smoothing: float = 0.22
    deadzone_px: int = 4
    max_jump_px: int = 260
    screen_edge_snap_zone: float = 0.025
    move_when_unarmed: bool = False
    adaptive_filter_enabled: bool = True
    precision_smoothing: float = 0.30
    travel_smoothing: float = 0.50
    catchup_smoothing: float = 0.78
    catchup_error_px: float = 56.0
    still_speed_px: float = 2.5
    still_snap_error_px: float = 14.0
    still_snap_smoothing: float = 0.76
    grid_reentry_snap_enabled: bool = True
    grid_reentry_snap_strength: float = 0.92
    grid_reentry_min_outside_seconds: float = 0.05
    monitor_handoff_enabled: bool = True
    monitor_handoff_min_seconds: float = 0.18
    monitor_handoff_max_seconds: float = 0.85
    monitor_handoff_release_zone: float = 0.22
    precision_accel_enabled: bool = True
    precision_slow_factor: float = 0.48
    precision_fast_factor: float = 1.28
    precision_slow_speed_px: float = 7.0
    precision_fast_speed_px: float = 52.0
    precision_factor_smoothing: float = 0.18
    precision_anchor_strength: float = 0.025


@dataclass
class AdaptiveGainConfig:
    enabled: bool = True
    reference_hand_scale: float | None = 0.22
    min_gain: float = 1.18
    max_gain: float = 2.2
    gain_smoothing: float = 0.18
    reference_adapt_rate: float = 0.01


@dataclass
class GestureConfig:
    pinch_threshold: float = 0.36
    right_pinch_threshold: float = 0.42
    double_pinch_threshold: float = 0.44
    click_release_threshold: float = 0.62
    click_cooldown_seconds: float = 0.28
    single_hand_clicks_enabled: bool = False
    drag_enabled: bool = True
    drag_hold_seconds: float = 0.38
    aux_thumb_drag_enabled: bool = True
    aux_thumb_drag_hold_seconds: float = 0.18
    aux_thumb_drag_release_grace_seconds: float = 0.12
    aux_thumb_drag_extension_threshold: float = 0.72
    aux_drag_pinch_enabled: bool = False
    aux_drag_pinch_threshold: float = 0.42
    aux_drag_release_threshold: float = 0.72
    aux_double_click_seconds: float = 0.45
    scroll_deadzone: float = 0.004
    scroll_gain: float = 160.0
    scroll_precision_multiplier: float = 0.45
    scroll_finger_extension_margin: float = 0.035
    scroll_cooldown_seconds: float = 0.0
    scroll_max_ticks: int = 7
    scroll_invert: bool = False
    fist_thumb_threshold: float = 1.15
    monitor_switch_hold_seconds: float = 0.55
    monitor_switch_cooldown_seconds: float = 1.2
    zoom_delta_threshold: float = 0.012
    zoom_cooldown_seconds: float = 0.08
    zoom_max_steps: int = 4
    precision_mode_pointer_gain: float = 0.62
    swipe_enabled: bool = False
    swipe_aux_hold_seconds: float = 0.18
    swipe_min_distance: float = 0.18
    swipe_max_duration_seconds: float = 0.42
    swipe_vertical_tolerance: float = 0.45
    swipe_cooldown_seconds: float = 0.75
    touch_commands_enabled: bool = True
    touch_command_threshold: float = 0.34
    touch_command_release_threshold: float = 0.52
    touch_command_cooldown_seconds: float = 0.65


@dataclass
class MonitorConfig:
    edge_switch_enabled: bool = False
    edge_zone: float = 0.06
    edge_dwell_seconds: float = 0.75
    transfer_enabled: bool = True
    transfer_zone: float = 0.025
    transfer_vertical_coverage: float = 0.70
    transfer_dwell_seconds: float = 0.55
    transfer_cooldown_seconds: float = 0.9
    transfer_entry_offset: float = 0.035


@dataclass
class OverlayConfig:
    trace_seconds: float = 0.38
    max_points: int = 38
    show_grid: bool = True
    opacity: float = 0.82
    action_pulse_seconds: float = 0.28


@dataclass
class HotkeyConfig:
    toggle_armed: str = "<ctrl>+<alt>+<space>"
    next_monitor: str = "<ctrl>+<alt>+m"
    quit: str = "<ctrl>+<alt>+q"


@dataclass
class AppConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)
    mouse: MouseConfig = field(default_factory=MouseConfig)
    adaptive_gain: AdaptiveGainConfig = field(default_factory=AdaptiveGainConfig)
    gestures: GestureConfig = field(default_factory=GestureConfig)
    monitors: MonitorConfig = field(default_factory=MonitorConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    hotkeys: HotkeyConfig = field(default_factory=HotkeyConfig)


def _merge_dataclass(cls, values: dict | None):
    defaults = cls()
    if not values:
        return defaults
    allowed = defaults.__dataclass_fields__.keys()
    return cls(**{key: value for key, value in values.items() if key in allowed})


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        return AppConfig()

    data = json.loads(path.read_text(encoding="utf-8"))
    return AppConfig(
        camera=_merge_dataclass(CameraConfig, data.get("camera")),
        debug=_merge_dataclass(DebugConfig, data.get("debug")),
        mouse=_merge_dataclass(MouseConfig, data.get("mouse")),
        adaptive_gain=_merge_dataclass(AdaptiveGainConfig, data.get("adaptive_gain")),
        gestures=_merge_dataclass(GestureConfig, data.get("gestures")),
        monitors=_merge_dataclass(MonitorConfig, data.get("monitors")),
        overlay=_merge_dataclass(OverlayConfig, data.get("overlay")),
        hotkeys=_merge_dataclass(HotkeyConfig, data.get("hotkeys")),
    )


def save_config(config: AppConfig, path: Path) -> None:
    path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]
