import ctypes
import logging
import os
import sys
import tkinter as tk
from pathlib import Path

# Ensure src/jp_ocr_dict is on sys.path whether run via `python src/jp_ocr_dict/main.py` or `python -m jp_ocr_dict.main`
PACKAGE_DIR = Path(__file__).resolve().parent
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

from api import JishoAPIHandler  # noqa: E402
from main_window import MainWindow  # noqa: E402


def configure_dpi_awareness() -> None:
    """
    Enables Per-Monitor DPI Awareness on Windows so screen capture coordinates
    match physical screen pixels across the entire monitor (fixing right-side drift).
    """
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()


def main() -> None:
    # Disable Windows symlink warning on HuggingFace Hub
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Silence noisy HTTP logs from httpx and HuggingFace Hub
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)

    class HFFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return "unauthenticated requests" not in record.getMessage()

    logging.getLogger("huggingface_hub").addFilter(HFFilter())

    configure_dpi_awareness()

    root = tk.Tk()
    jisho_api_handler = JishoAPIHandler()

    # MainWindow launches immediately (<0.5s) and initializes the OCR models in background
    main_ui = MainWindow(root, jisho_api_handler)
    main_ui.root.mainloop()


if __name__ == "__main__":
    main()
