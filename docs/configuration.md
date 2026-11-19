# Configuration and Settings

All user preferences are persisted in `src/jp_ocr_dict/settings.json` via the thread-safe `SettingsManager` class.

---

## Configuration Keys

| Key | Type | Default | Description |
|---|---|---|---|
| `theme` | string | `"dark"` | Color theme for the dictionary popup. Options: `"dark"`, `"light"`, `"blue"`, `"yellow"`. |
| `font_size` | string | `"normal"` | Typography scale. Options: `"small"`, `"normal"`, `"large"`. |
| `require_trigger_key` | boolean | `false` | When true, Hover OCR only activates while holding the trigger key. |
| `trigger_key` | string | `"Alt"` | Modifier key used when `require_trigger_key` is enabled. Options: `"Alt"`, `"Ctrl"`, `"Shift"`. |
| `ocr_orientation` | string | `"auto"` | Text reading axis for bounding box estimation. Options: `"auto"`, `"vertical"`, `"horizontal"`. |
| `hotkey_toggle_hover` | string | `"alt+e"` | Global hotkey to start or stop the background hover OCR thread. |
| `hotkey_toggle_snip` | string | `"alt+s"` | Global hotkey to trigger the freeze-screen snip canvas. |
| `show_common_indicators` | boolean | `true` | When true, common Japanese words display a green `Common` badge. |
| `show_jlpt` | boolean | `true` | When true, JLPT levels (`N5` through `N1`) are displayed. |
| `show_definitions` | boolean | `true` | When true, English definition text is displayed. |

---

## Offline Database Setup

To populate the local SQLite database (`src/jp_ocr_dict/data/dictionary.db`):

### 1. Starter Seed (~500 core entries)
For immediate offline testing:
```bash
python scripts/seed_starter_dictionary.py
```

### 2. Full JMdict and KANJIDIC2 (~185,000 entries)
To download and index the entire Electronic Dictionary Research and Development Group (EDRDG) database:
```bash
python scripts/import_jmdict.py
```
This script downloads `JMdict_e.gz` and `kanjidic2.xml.gz` across official mirrors, parses the XML trees via streaming, and performs priority-aware homograph merging. Standalone nouns and high-frequency entries (e.g. `ichi1`, `news1`, `nfXX`) are strictly prioritized over obscure bound suffixes and dialect counters (e.g. ensuring `日` is resolved as `ひ` / `にち` rather than `んち`). All entries are indexed into SQLite inside batched transactions.
