from __future__ import annotations

import argparse
import time

from .adaptive_gain import AdaptiveGainMapper
from .config import load_config, project_root
from .tracker import HandTracker


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=8.0)
    args = parser.parse_args()

    root = project_root()
    config = load_config(root / "config.json")
    tracker = HandTracker(config.camera)
    mapper = AdaptiveGainMapper(config.adaptive_gain)
    samples = []

    try:
        tracker.open()
        end_at = time.monotonic() + max(1.0, args.seconds)
        while time.monotonic() < end_at:
            hand, frame = tracker.read()
            if frame is None:
                raise RuntimeError("La camara no entrego frames.")
            if hand is not None:
                state = mapper.map(hand)
                samples.append((state.hand_scale, state.gain))
                print(f"hand_scale={state.hand_scale:.3f} gain={state.gain:.2f}")
            time.sleep(0.05)
    finally:
        tracker.close()

    if not samples:
        print("No se detecto mano durante la prueba.")
        return

    avg_scale = sum(scale for scale, _gain in samples) / len(samples)
    avg_gain = sum(gain for _scale, gain in samples) / len(samples)
    max_gain = max(gain for _scale, gain in samples)
    print(f"Resumen: muestras={len(samples)} hand_scale_prom={avg_scale:.3f} gain_prom={avg_gain:.2f} gain_max={max_gain:.2f}")


if __name__ == "__main__":
    main()
