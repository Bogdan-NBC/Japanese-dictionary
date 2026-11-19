import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Resolve settings.json relative to this file's directory so it works from any CWD
SETTINGS_FILE = Path(__file__).resolve().parent / "settings.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "theme": "dark",
    "font_size": "normal",
    "require_trigger_key": False,
    "trigger_key": "Alt",
    "hotkey_toggle_hover": "alt+e",
    "hotkey_toggle_snip": "alt+s",
    "show_common_indicators": True,
    "show_jlpt": True,
    "show_definitions": True,
    "ocr_orientation": "auto",  # Options: "auto", "vertical", "horizontal"
}


class SettingsManager:
    def __init__(self, settings_path: Path = SETTINGS_FILE) -> None:
        self.settings_path = settings_path
        self.settings: dict[str, Any] = DEFAULT_SETTINGS.copy()
        self.load_settings()

    def load_settings(self) -> None:
        if self.settings_path.exists():
            try:
                with self.settings_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in DEFAULT_SETTINGS.items():
                        self.settings[k] = data.get(k, v)
                logger.info("Settings loaded successfully from %s", self.settings_path)
            except Exception as e:
                logger.error("Error loading settings: %s", e)
        else:
            self.save_settings()

    def save_settings(self) -> None:
        try:
            with self.settings_path.open("w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
            logger.info("Settings saved successfully to %s", self.settings_path)
        except Exception as e:
            logger.error("Error saving settings: %s", e)

    def get(self, key: str) -> Any:
        return self.settings.get(key, DEFAULT_SETTINGS.get(key))

    def set(self, key: str, value: Any) -> None:
        self.settings[key] = value
        self.save_settings()


# Global settings instance
settings = SettingsManager()
