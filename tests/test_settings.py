import sys
from pathlib import Path

# Add package directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "jp_ocr_dict"))

from settings_manager import DEFAULT_SETTINGS, SettingsManager  # noqa: E402


def test_settings_manager_defaults(tmp_path: Path) -> None:
    settings_file = tmp_path / "test_settings.json"
    mgr = SettingsManager(settings_path=settings_file)

    assert mgr.get("theme") == "dark"
    assert mgr.get("font_size") == "normal"
    assert mgr.get("hotkey_toggle_hover") == "alt+e"
    assert mgr.get("hotkey_toggle_snip") == "alt+s"
    assert mgr.get("non_existent_key") is None


def test_settings_manager_save_and_reload(tmp_path: Path) -> None:
    settings_file = tmp_path / "test_settings.json"
    mgr = SettingsManager(settings_path=settings_file)

    mgr.set("theme", "blue")
    mgr.set("font_size", "large")
    mgr.set("require_trigger_key", True)

    assert settings_file.exists()

    # Create new instance pointing to same file
    mgr2 = SettingsManager(settings_path=settings_file)
    assert mgr2.get("theme") == "blue"
    assert mgr2.get("font_size") == "large"
    assert mgr2.get("require_trigger_key") is True


def test_settings_manager_handles_corrupt_json(tmp_path: Path) -> None:
    settings_file = tmp_path / "corrupt_settings.json"
    settings_file.write_text("{this is not valid json!}", encoding="utf-8")

    mgr = SettingsManager(settings_path=settings_file)
    # Should safely fallback to default settings without crashing
    assert mgr.get("theme") == DEFAULT_SETTINGS["theme"]
    assert mgr.get("hotkey_toggle_snip") == "alt+s"
