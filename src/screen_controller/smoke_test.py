from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config, project_root
from .tracker import HandTracker


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=30)
    args = parser.parse_args()

    root = project_root()
    config = load_config(root / "config.json")
    tracker = HandTracker(config.camera)
    seen_hand = 0
    try:
        tracker.open()
        for _ in range(max(1, args.frames)):
            hand, frame = tracker.read()
            if frame is None:
                raise RuntimeError("La camara no entrego frames.")
            if hand is not None:
                seen_hand += 1
        print(f"Smoke OK. Frames leidos: {args.frames}. Frames con mano: {seen_hand}.")
    finally:
        tracker.close()


if __name__ == "__main__":
    main()
