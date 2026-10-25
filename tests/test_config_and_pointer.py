"""Regression checks that do not open a camera or inject OS input."""
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest

from screen_controller.config import AppConfig, MouseConfig, load_config, save_config
from screen_controller.geometry import active_camera_rect, map_normalized_to_rect, normalize_in_rect
from screen_controller.mouse_control import PointerFilter


class ConfigTests(unittest.TestCase):
    def test_shipped_example_matches_defaults_and_has_portable_paths(self):
        root = Path(__file__).resolve().parents[1]
        config = load_config(root / "config.example.json")
        self.assertEqual(asdict(config), asdict(AppConfig()))
        self.assertFalse(Path(config.camera.model_path).is_absolute())

    def test_personalized_values_survive_save_and_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            config = load_config(path)
            config.camera.active_area_offset_x = 0.93
            config.gestures.scroll_invert = True
            config.adaptive_gain.max_gain = 2.7
            save_config(config, path)
            self.assertEqual(asdict(load_config(path)), asdict(config))


class MappingTests(unittest.TestCase):
    def test_shifted_grid_reaches_entire_negative_origin_monitor(self):
        grid = active_camera_rect(960, 540, .75, 16 / 9, .06, .24, .06, 1, 1)
        from screen_controller.geometry import Rect
        monitor = Rect(-1920, -200, 1920, 1080)
        for point, expected in [
            ((grid.x, grid.y), (-1920, -200)),
            ((grid.right, grid.bottom), (-1, 879)),
        ]:
            actual = map_normalized_to_rect(*normalize_in_rect(*point, grid), monitor)
            self.assertEqual(actual, expected)

    def test_reentry_resets_dynamic_history_instead_of_replaying_jump(self):
        pointer = PointerFilter(MouseConfig())
        pointer.update(20, 20)
        self.assertEqual(pointer.reanchor(1800, 900, 1), (1800, 900))
        self.assertEqual(pointer.update(1800, 900), (1800, 900))


if __name__ == "__main__":
    unittest.main()
