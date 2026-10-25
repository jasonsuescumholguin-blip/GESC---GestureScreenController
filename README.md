# GESC — GestureScreenController

Control a Windows desktop with hand gestures captured by a webcam. GESC maps an adjustable 2D camera grid to the active monitor, with adaptive pointer filtering, distance-sensitive gain, two-hand mouse gestures, a desktop cursor trail, and a live control panel that remembers your settings.

This repository contains the Python application. **Python, a local virtual environment, dependencies, and the hand-tracking model are installed on the user's computer.** No environment, model binary, or executable is bundled.

## Requirements

- Windows with a working webcam and camera access enabled for desktop apps.
- **64-bit Python 3.12 recommended.** Package metadata accepts Python 3.10–3.14; availability of dependency wheels varies by Python version. The existing development installation also runs on Python 3.14. This is not a claim that every supported combination has been tested.
- Internet for initial dependency and MediaPipe model downloads. Normal tracking runs locally.
- Git if cloning, or use GitHub's **Code → Download ZIP** and extract the whole folder.
- One or more monitors. Lateral monitor transfer uses Windows display geometry.

No dedicated GPU or separately installed MediaPipe SDK is required. Setup installs the Python dependencies and downloads Google's Hand Landmarker model. There are no measured minimum CPU/RAM requirements yet; performance depends on the camera, resolution, processor, and visible debug windows.

## Install and run

Open PowerShell in the extracted repository, or clone it:

```powershell
git clone https://github.com/jasonsuescumholguin-blip/GESC---GestureScreenController.git
cd GESC---GestureScreenController
.\scripts\setup.ps1
.\scripts\run.ps1
```

If Python is not the desired interpreter, pass its full path:

```powershell
.\scripts\setup.ps1 -Python 'C:\Path\To\Python312\python.exe'
```

Setup creates `.venv`, installs the project in editable mode, copies `config.example.json` to `config.json` if missing, and downloads `models/hand_landmarker.task`. It stops on command failure and preserves existing settings. An existing `.venv` is reused; changing `-Python` does not replace it.

If PowerShell blocks local scripts, you can allow them for the current terminal session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup.ps1
```

You can also install manually without the setup script:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
Copy-Item config.example.json config.json  # First installation only
.\scripts\download_model.ps1
.\scripts\run.ps1
```

Keep the repository folder together. Source execution resolves the model and settings relative to the project root. The folder must be writable to save settings. A virtual environment is not portable: after moving the project, recreate `.venv` and run setup again.

## First session and shortcuts

The application starts in **IDLE**: camera tracking is running, but mouse actions are disabled by default. The camera preview shows the detection grid and hand landmarks; the separate control panel changes settings. The desktop overlay shows the cursor trail and colored action pulses.

| Shortcut | Action |
| --- | --- |
| `Ctrl+Alt+Space` | Toggle IDLE / ARMED |
| `Ctrl+Alt+M` | Select the next monitor |
| `Ctrl+Alt+Q` | Quit and release held mouse buttons |

1. Keep both hands fully visible, with light on your hands rather than behind them.
2. By default, the hand farther to the **right in the mirrored camera image** is the main pointer hand. The other is auxiliary. This is screen-side selection, not a guaranteed anatomical right-hand identity.
3. Use **Surface** to place the grid in a comfortable area. Leave room below it so the camera can see the rest of your hand near the lower grid edge.
4. Arm the app, point with your main index finger, and test the gestures below.
5. Disarm before changing settings with your physical mouse.

Only the main index tip needs to lie within the grid for its absolute mapping; the auxiliary hand can perform gestures outside the grid as long as the camera detects it. Keep the whole hand inside the camera frame even when the fingertip is at a grid edge.

## Current gestures

The following describes the shipped defaults and current Python interpreter, rather than older prototype gestures.

| Action | Main hand | Auxiliary hand |
| --- | --- | --- |
| Move pointer | Point with index finger | Rest or absent |
| Rest | Closed fist pauses pointer movement | Closed fist permits main-hand actions |
| Left click | Aim at target | Raise index only; fold middle, ring, pinky |
| Double click | Aim at target | Raise, lower, and raise index again within the double-click window |
| Right click | Aim at target | Raise index and middle; fold ring and pinky |
| Drag | Move index to move the held item | Extend **thumb only**, with all four fingers folded; hold briefly, then fold thumb to release |
| Scroll | Extend index and middle, fold ring and pinky, then move the hand vertically | Rest, absent, or open palm for finer scroll |
| Precision pointer | Point with index | Open palm, all four fingers extended |
| Zoom in / out | Open palm | Open palm; separate horizontally to enlarge, bring together to reduce |
| Forward | Touch main and auxiliary index tips | Both index fingers extended |
| Back | Touch main and auxiliary pinky tips | Both pinkies extended |

Click poses block pointer motion while held; lower the fingers to resume. The second left click is sent as a normal OS click, so Windows double-click timing also matters. Drag releases when its pose is lost beyond the configured grace interval, or when the auxiliary hand disappears.

Scroll tracks the palm base instead of the fingertips and ends when the two-finger pose ends, reducing rebound when lowering the fingers. With `scroll_invert=false`, upward hand movement produces positive wheel ticks; enable **Invert scroll** to reverse this.

Zoom sends `Ctrl` + wheel, so behavior depends on the foreground application. Back/forward send `Alt+Left` / `Alt+Right`; they require application support. Finger contact is **2D proximity in the camera image**, not physical touch sensing. Fingers at different depths can appear to touch.

Open-palm recognition currently checks the four non-thumb fingers; it does not require a fully extended thumb. Most pose tests compare fingertip/joint vertical positions, so keep hands reasonably upright and facing the camera.

### Monitor transfer

Hold the cursor near a left/right edge for the configured dwell time to transfer to a detected neighbor on that side. Only the central **70% of the edge's height** participates by default, leaving the top/bottom 15% clear for window controls and the taskbar. Transfer preserves a held drag. No neighbor means no transfer on that side. Arrange displays correctly in Windows Settings first.

The current handoff briefly holds the entry position until the finger moves inward or a timeout expires. This is a prototype behavior: a positional correction may still be noticeable after release. Vertical monitor transfer is not implemented. `Ctrl+Alt+M` is an alternative monitor selector.

## Settings and persistence

The **Pointer, Gain, Surface, Clicks, Scroll, Zoom, View** tabs expose live settings. Changes auto-save to local `config.json` after approximately **700 ms**. Use **Save config** before closing if you changed something immediately beforehand. **Reset pointer** clears filter history; **Reset gain** resets the current gain, but does not replace all configuration values or necessarily relearn the reference hand scale.

`config.example.json` contains generic defaults; `config.json` is deliberately ignored by Git. Back it up before experimenting. To restore defaults, close the app and replace `config.json` with a copy of `config.example.json`. Restart after editing JSON manually. Camera device/resolution and hotkeys are startup settings; most panel values take effect during tracking. Window visibility and history-buffer sizes may require restart.

### Recommended tuning order

1. **Surface:** position and size the grid with relaxed shoulders. A smaller grid reduces arm travel but magnifies landmark noise.
2. **Gain:** adjust near-distance gain first, then maximum gain at the farthest intended position (roughly up to 1.5 m was the prototype's usage target, not a guaranteed detection range).
3. **Pointer:** balance slow-motion stability and fast-motion response. Change one value at a time.
4. **Clicks / Scroll / Zoom:** tune activation timing and action intensity only after pointer motion feels comfortable.

In the tables, **higher smoothing alpha means faster response and less averaging**, not more smoothing. Pixel values refer to mapped desktop coordinates unless stated otherwise. Timing values are seconds. Some speed calculations are per sample, so changing camera throughput can change feel.

### Pointer — smoothing, acceleration, re-entry

Keys in this table belong to `mouse`.

| Panel / JSON key | Effect of increasing the value |
| --- | --- |
| Smoothing / `smoothing` | Faster response when adaptive filtering is disabled. |
| Deadzone px / `deadzone_px` | Suppresses more small movements; can reduce fine control. Not a hard freeze in every adaptive-filter branch. |
| Max jump px / `max_jump_px` | Accepts larger frame-to-frame jumps; lower rejects more tracking spikes but can reject valid fast motion. |
| Edge snap zone / `screen_edge_snap_zone` | Snaps to screen borders earlier; helps edge reach but reduces usable fine movement near borders. |
| Adaptive filter / `adaptive_filter_enabled` | Enables speed/error-based filtering instead of the fixed alpha above. |
| Precision smoothing / `precision_smoothing` | Faster slow-motion response, less averaging. Lower improves stability with more delay. |
| Travel smoothing / `travel_smoothing` | Faster response during travel. |
| Catch-up smoothing / `catchup_smoothing` | Faster convergence when filtered position trails its target. |
| Catch-up error px / `catchup_error_px` | Requires a larger lag to reach full catch-up strength. |
| Still speed px / `still_speed_px` | Classifies more small input movements as nearly still. |
| Still snap error px / `still_snap_error_px` | Allows stationary catch-up over a larger residual error. |
| Still snap smoothing / `still_snap_smoothing` | Removes that small residual error faster. |
| Grid re-entry snap / `grid_reentry_snap_enabled` | Enables rapid realignment when the fingertip returns to the grid. |
| Re-entry snap strength / `grid_reentry_snap_strength` | More immediate realignment; 1 is an exact reset to the mapped position. |
| Re-entry outside time / `grid_reentry_min_outside_seconds` | Requires a longer excursion before treating return as re-entry. |
| Monitor handoff / `monitor_handoff_enabled` | Enables the temporary hold after lateral transfer. |
| Handoff min seconds / `monitor_handoff_min_seconds` | Keeps the entry hold longer before inward movement can release it. |
| Handoff max seconds / `monitor_handoff_max_seconds` | Allows a longer hold before forced release. Keep at least as large as min. |
| Handoff release zone / `monitor_handoff_release_zone` | Requires more inward movement from the outgoing grid edge to release the hold. |
| Dynamic precision / `precision_accel_enabled` | Enables speed-based movement gain on top of grid mapping. |
| Slow precision factor / `precision_slow_factor` | Larger slow-motion displacement; lower allows finer adjustments. |
| Fast travel factor / `precision_fast_factor` | Larger fast-motion displacement. |
| Slow speed px / `precision_slow_speed_px` | Extends the slow-motion regime to higher input speeds. |
| Fast speed px / `precision_fast_speed_px` | Requires faster input to reach maximum travel gain. Keep greater than slow speed. |
| Factor smoothing / `precision_factor_smoothing` | Adapts movement gain faster; lower makes transitions more gradual. |
| Grid anchor / `precision_anchor_strength` | Pulls the dynamic target toward the absolute grid position faster. Very low values retain offset longer. |
| Move when unarmed / `move_when_unarmed` | Allows pointer movement in IDLE when enabled; gestures remain disabled. Leave off for a true idle state. |

The grid provides absolute screen coordinates. Dynamic precision integrates movement with a varying gain and gently anchors it back to those coordinates. The adaptive filter then smooths the target, with special re-entry and handoff handling. This is not a literal increase in camera resolution; smaller grids still have a precision/noise tradeoff.

### Gain — apparent distance

Keys belong to `adaptive_gain`. Hand size is an apparent-distance proxy, not metric depth sensing; hand orientation and anatomy also affect it. It changes motion gain rather than physically translating the grid.

| Panel / key | Increasing it / behavior |
| --- | --- |
| Adaptive gain / `enabled` | Enables hand-size-dependent gain. Disable for constant distance gain of 1. |
| Reference hand scale / `reference_hand_scale` | Raises gain at a given observed hand size. Default 0.22; normalized landmark distance. |
| Min gain / `min_gain` | More sensitivity even nearby. Default 1.18. |
| Max gain / `max_gain` | More sensitivity when the hand appears small/far away. Default 2.2; keep ≥ min. |
| Gain smoothing / `gain_smoothing` | Follows estimated distance changes faster; lower resists fluctuations. |
| Reference adapt rate / `reference_adapt_rate` | Learns larger/closer observed hand scales faster. Zero freezes reference adaptation. |

Distance gain is applied through dynamic precision. If dynamic precision is disabled, changing these gain values does not change pointer displacement through that layer.

### Surface — grid and hand assignment

Keys belong to `camera`.

| Panel / key | Increasing it / behavior |
| --- | --- |
| Aspect / `active_area_aspect` | Wider grid relative to height; default 16:9. |
| Top margin / `active_area_top_margin` | Reserves more camera space above the grid. |
| Bottom margin / `active_area_bottom_margin` | Reserves more below the grid, helping avoid clipped hands. |
| Side margin / `active_area_side_margin` | Reduces the maximum grid width. |
| Grid horizontal position / `active_area_offset_x` | Moves through available horizontal space: 0 left, 1 right. |
| Grid vertical position / `active_area_offset_y` | Moves through available vertical space: 0 top, 1 bottom. If no free height remains, this has no visible effect. |
| Pointer hand / `pointer_hand_preference` | `rightmost`, `leftmost`, or legacy `auto`, based on camera-image position. |
| Hand switch margin / `pointer_switch_margin` | Requires more horizontal separation before side-based assignment; near ties use prior pointer proximity. |
| Mirror camera / `mirror` | Flips camera horizontally; also changes the meaning of image-side hand selection. |

Offsets move within the available area; the grid still fits the aspect/margins. `active_area_scale` is a fallback for the legacy grid mode and does not control size when aspect/margins are active. Change margins/aspect to change the current grid size.

### Clicks and drag

Keys belong to `gestures`. Thresholds for landmark distances are relative to palm size, unless indicated otherwise.

| Panel / key | Increasing it / behavior |
| --- | --- |
| Click cooldown / `click_cooldown_seconds` | More time between fresh clicks, reducing repeats. |
| Aux double window / `aux_double_click_seconds` | More time to lower/raise the auxiliary index for the second click; Windows also applies its own timing. |
| Aux thumb drag / `aux_thumb_drag_enabled` | Enables the recommended thumb-only drag. Master `drag_enabled` must also be true. |
| Thumb drag hold / `aux_thumb_drag_hold_seconds` | Requires a longer deliberate hold before mouse-down. |
| Thumb drag release grace / `aux_thumb_drag_release_grace_seconds` | Tolerates pose dropouts longer but delays release. |
| Thumb extension / `aux_thumb_drag_extension_threshold` | Requires a more extended thumb; reduces accidental activation. Other four fingers must remain folded. |

**Legacy experiments, disabled by default:** `aux_drag_pinch_enabled` enables auxiliary thumb/index pinch drag. Higher `aux_drag_pinch_threshold` accepts a looser pinch; higher `aux_drag_release_threshold` requires more separation to release; `drag_hold_seconds` sets its hold delay. Keep release threshold above activation threshold.

`single_hand_clicks_enabled` enables old main-hand pinches: thumb/index left, thumb/middle right, thumb/ring double. Higher `pinch_threshold`, `right_pinch_threshold`, or `double_pinch_threshold` accepts more separation. `click_release_threshold` controls release separation. These compete with pointing and are not the recommended scheme. Leave legacy modes off when tuning the two-hand system.

### Scroll

Keys belong to `gestures`.

| Panel / key | Increasing it / behavior |
| --- | --- |
| Scroll deadzone / `scroll_deadzone` | Ignores more small per-frame palm movement; lower is more responsive. Normalized camera y units. |
| Scroll gain / `scroll_gain` | Produces more wheel ticks for the same hand travel. |
| Scroll precision / `scroll_precision_multiplier` | Scrolls faster while auxiliary palm is open; lower gives finer scrolling. |
| Scroll finger margin / `scroll_finger_extension_margin` | Requires more clearly extended index/middle fingers. Normalized camera y margin. |
| Scroll cooldown / `scroll_cooldown_seconds` | Limits emission frequency; high values can feel less fluid. |
| Scroll max ticks / `scroll_max_ticks` | Permits larger wheel bursts per update. |
| Invert scroll / `scroll_invert` | Reverses wheel direction. |
| Fist thumb threshold / `fist_thumb_threshold` | Accepts more thumb separation as a closed fist; affects rest recognition, not scroll activation. |

### Zoom, contact commands, and monitor transitions

Unless prefixed with `monitors.`, keys belong to `gestures`.

| Panel / key | Increasing it / behavior |
| --- | --- |
| Zoom movement threshold / `zoom_delta_threshold` | Requires more horizontal palm separation change per update; lower is more sensitive. Normalized camera width. |
| Zoom cooldown / `zoom_cooldown_seconds` | More spacing between zoom emissions. |
| Zoom max steps / `zoom_max_steps` | Allows larger Ctrl+wheel bursts. |
| Precision mode gain / `precision_mode_pointer_gain` | Faster motion with auxiliary open palm; lower gives finer aiming. |
| Touch back/forward / `touch_commands_enabled` | Enables index/pinky contact commands. |
| Touch distance / `touch_command_threshold` | Accepts tips farther apart; larger values are easier but more prone to false contacts. |
| Touch release / `touch_command_release_threshold` | Requires more separation before contact can reset. Keep above touch distance. |
| Touch cooldown / `touch_command_cooldown_seconds` | More spacing between contact commands. |
| Monitor transfer / `monitors.transfer_enabled` | Enables edge dwell transfer. |
| Transfer zone / `monitors.transfer_zone` | Makes each active edge strip wider, as a fraction of monitor width. |
| Transfer vertical coverage / `monitors.transfer_vertical_coverage` | Enables a taller centered edge strip; 0.70 excludes 15% at top and bottom. |
| Transfer dwell / `monitors.transfer_dwell_seconds` | Requires a longer edge hold before transfer. |
| Transfer cooldown / `monitors.transfer_cooldown_seconds` | Prevents another transfer for longer. |
| Transfer entry / `monitors.transfer_entry_offset` | Places cursor farther inside the destination monitor. |

The panel still displays **Swipe commands legacy**, **Monitor hold**, and **Monitor cooldown**. The current gesture update path does not invoke the old swipe/two-fist monitor logic; these controls do not enable those old actions. Use contact commands and edge transfer/shortcut instead. Legacy `monitors.edge_switch_*` settings are separate from the active `transfer_*` feature.

### View and startup-only configuration

| Key | Behavior |
| --- | --- |
| `debug.show_control_panel` | Show control panel at launch. |
| `debug.show_camera` | Show camera debug view during tracking. |
| `debug.window_scale` | Size of camera preview, not inference resolution. |
| `overlay.show_grid` | Show desktop overlay grid. |
| `overlay.opacity` | Higher makes the overlay more visible. |
| `overlay.trace_seconds` | Higher retains the cursor trail longer. |
| `overlay.max_points` | Larger history buffer; restart to recreate the buffer. |
| `overlay.action_pulse_seconds` | Higher keeps click/drag/scroll/zoom feedback visible longer. |
| `camera.index` | Camera device index, usually 0; restart after changing. |
| `camera.width`, `camera.height`, `camera.fps` | Requested capture settings; actual values depend on the webcam/driver. Restart. |
| `camera.model_path` | Path relative to project root, or absolute path to the downloaded `.task` model. Restart. |
| `hotkeys.toggle_armed`, `hotkeys.next_monitor`, `hotkeys.quit` | Global shortcuts in pynput syntax, e.g. `<ctrl>+<alt>+<space>`. Restart. |

## Diagnostics and validation

After setup, run from the repository root:

```powershell
.\scripts\check.ps1                           # Compile every Python source without starting control
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m screen_controller --self-test
.\scripts\doctor.ps1                          # Inspect model, displays, camera
.\scripts\smoke.ps1                           # Read 30 camera frames; does not control the mouse
.\scripts\gain-test.ps1                       # Print detected hand scale and adaptive gain
```

`--self-test` initializes the UI/model without starting the capture/control loop. It needs the model and Windows desktop access; it does not validate actual gestures. `doctor` reports camera status; inspect its output even if it prints Doctor OK. Smoke can pass without seeing a hand; it checks camera frames, not gesture accuracy. Close other camera apps before camera diagnostics. Automated tests cannot establish ergonomic quality, display alignment on every DPI setup, or reliable gesture recognition for every user.

Publication validation passed on Windows with Python 3.14.6, MediaPipe 1.1.1, PySide6 6.12.0, and OpenCV contrib 5.0.0.93: dependency/model setup, Python and PowerShell syntax, four regression tests, `pip check`, and the UI/model self-test. Live camera gesture tests were not repeated for this publication. Dependency ranges are not a lockfile, so future installs may resolve different versions.

### Troubleshooting

- **No camera:** enable Windows camera access for desktop apps; close competing camera users; try another `camera.index` and restart.
- **Missing model:** rerun `scripts/download_model.ps1`. If an older interrupted installation left a corrupt model, remove that `.task` file and download it again.
- **`mediapipe` has no `solutions`:** this version uses `mp.tasks`, not the old Solutions API. Make sure you run this checkout with its `.venv`, and do not have a local file named `mediapipe.py`.
- **No dependency wheels / unsupported Python:** use 64-bit Python 3.12 and a fresh `.venv`; do not reuse an environment created with another interpreter.
- **Hand identity switches:** keep hands on their assigned camera sides; adjust Surface → Pointer hand. When only one hand is detected it becomes the main hand, so an auxiliary hand alone can be misassigned.
- **Jitter or lag:** improve lighting, keep the full hand visible, enlarge the grid, then tune Pointer smoothing and Gain. Raising max gain or shrinking the grid also magnifies tracking error.
- **Clicks or drag trigger accidentally:** keep legacy pinches disabled; use a folded auxiliary rest pose, and increase thumb hold/extension if needed.
- **Cannot operate Task Manager or elevated windows:** Windows can block input from a lower-integrity process. This app has no UIAccess integration and does not bypass secure desktop/UAC restrictions.
- **Different feel after updating:** back up local `config.json`; newly added keys use defaults, while saved old values override new defaults.

## Resource use, privacy, and updates

Camera acquisition and inference continue in IDLE; IDLE disables actions rather than suspending capture. This is a prototype, not yet an optimized background service or startup installer. Hide the camera preview to reduce display overhead, and quit to release the camera. Reducing capture resolution may help depending on hardware; requesting a lower FPS is not a guaranteed software processing cap.

The application processes camera frames locally. It contains no frame upload or recording feature. Setup contacts Python package servers and Google's model storage. The model URL is in `scripts/download_model.ps1`; third-party dependencies and model licensing remain governed by their respective upstream terms.

For a cloned installation, close the app, back up `config.json`, run `git pull`, and rerun setup if dependencies changed. Editable installation loads source changes the next time the app starts. A separately packaged executable requires a new build to include source changes. No executable is produced as part of this repository publication.

## Project layout

```text
src/screen_controller/  Tracking, gesture interpretation, filtering, OS input, Qt UI
scripts/               Setup, run, diagnostics, optional legacy build tooling
tests/                 Regression checks without webcam or injected mouse actions
config.example.json    Generic defaults; copied locally on first setup
config.json            Your local settings (ignored)
models/                Downloaded Hand Landmarker model (ignored)
.venv/                 Local Python environment (ignored)
```

The existing `build.ps1` and PyInstaller spec are retained for future packaging work. They are not part of normal source installation. No application license has been selected in this repository yet.
