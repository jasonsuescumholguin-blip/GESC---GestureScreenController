from __future__ import annotations

from pathlib import Path

import cv2
import mediapipe as mp
from screeninfo import get_monitors

from .config import load_config, project_root


def main() -> None:
    root = project_root()
    config = load_config(root / "config.json")

    print("ScreenController doctor")
    print(f"Proyecto: {root}")
    print(f"MediaPipe: {getattr(mp, '__version__', 'unknown')}")
    print(f"OpenCV: {cv2.__version__}")

    model_path = Path(config.camera.model_path)
    if not model_path.is_absolute():
        model_path = root / model_path
    print(f"Modelo: {model_path}")
    print(f"Modelo existe: {model_path.exists()}")

    monitors = get_monitors()
    print(f"Monitores detectados: {len(monitors)}")
    for idx, monitor in enumerate(monitors, start=1):
        primary = " primary" if getattr(monitor, "is_primary", False) else ""
        print(f"  {idx}: x={monitor.x} y={monitor.y} {monitor.width}x{monitor.height}{primary}")

    cap = cv2.VideoCapture(config.camera.index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(config.camera.index)
    ok = cap.isOpened()
    print(f"Camara indice {config.camera.index} abre: {ok}")
    if ok:
        read_ok, frame = cap.read()
        shape = None if frame is None else f"{frame.shape[1]}x{frame.shape[0]}"
        print(f"Primer frame: {read_ok} {shape or ''}".rstrip())
    cap.release()

    if not model_path.exists():
        raise SystemExit("Falta el modelo. Ejecuta .\\scripts\\download_model.ps1 o .\\scripts\\setup.ps1")

    print("Doctor OK.")


if __name__ == "__main__":
    main()
