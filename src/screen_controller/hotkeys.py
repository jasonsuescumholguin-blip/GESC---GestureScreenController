from __future__ import annotations

from collections.abc import Callable

from pynput import keyboard

from .config import HotkeyConfig


class HotkeyManager:
    def __init__(
        self,
        config: HotkeyConfig,
        on_toggle_armed: Callable[[], None],
        on_next_monitor: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._listener = keyboard.GlobalHotKeys(
            {
                config.toggle_armed: on_toggle_armed,
                config.next_monitor: on_next_monitor,
                config.quit: on_quit,
            }
        )

    def start(self) -> None:
        self._listener.start()

    def stop(self) -> None:
        self._listener.stop()
