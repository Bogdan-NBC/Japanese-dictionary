# API Reference

Detailed technical reference for the public modules and classes of `jp_ocr_dict`.

---

## `jp_ocr_dict.ocr`

### `OCRHandler`

```python
class OCRHandler:
    def __init__(
        self,
        on_snip_ready: Callable[[OCRHandler], None] | None = None,
        on_all_ready: Callable[[OCRHandler], None] | None = None,
        defer_easyocr: bool = True,
    ) -> None:
```

The core vision and linguistic processing handler. Manages MangaOCR, EasyOCR, and Janome tokenizer instances.

#### Methods

##### `pad_to_square(image: Image.Image) -> Image.Image`
Letterboxes an image into a square canvas with sampled background color to preserve native character aspect ratios before feeding into the $224 \times 224$ Vision Transformer.

- **Args**:
  - `image`: Input PIL Image to pad.
- **Returns**:
  - Square PIL Image with identical maximum dimensions.

##### `process_screensnip(image: Image.Image) -> str | None`
Performs optical character recognition on a snipped bitmap. Handles aspect-ratio preservation and chunk slicing for long vertical or horizontal text lines.

- **Args**:
  - `image`: Cropped PIL Image from the screen capture.
- **Returns**:
  - Cleaned Japanese text string, or `None` if recognition yields empty output.

##### `process_screensnip_detailed(image: Image.Image) -> dict[str, Any] | None`
Runs MangaOCR on the cropped image, segments the sentence into lexical tokens, and isolates candidate headwords for initial dictionary lookup.

- **Args**:
  - `image`: Cropped PIL Image.
- **Returns**:
  - Dictionary with keys:
    - `"raw_text"`: Full unsegmented string.
    - `"tokens"`: List of token metadata dictionaries.
    - `"primary_candidates"`: Prioritized list of words for dictionary querying.

##### `tokenize_sentence(text: str) -> list[dict[str, Any]]`
Performs Janome morphological segmentation on Japanese text, gluing trailing auxiliaries onto verbs and adjectives while preserving base lemma forms.

- **Args**:
  - `text`: Japanese sentence or phrase.
- **Returns**:
  - List of dictionaries containing `surface`, `base_form`, `pos`, `is_content_word`, and `candidates`.

##### `process_screenshot(mouse_x: int, mouse_y: int) -> list[str] | None`
Captures a square region surrounding the cursor, identifies text bounding boxes via EasyOCR, and determines candidate words at the pointer ratio using orientation-aware single-track isolation.

##### `_select_target_box_and_bounds(results: list, cursor_x: int, cursor_y: int, img_w: int, img_h: int, is_vertical: bool) -> tuple[int, int, int, int]`
Evaluates candidate detector bounding boxes with perpendicular distance weighting, isolates single column/line tracks, and clamps multi-column detector mergers to avoid capturing adjacent text lines.

##### `_detect_local_orientation(image_np: np.ndarray, cursor_x: int, cursor_y: int, results: list | None = None) -> bool`
Determines whether text at the cursor is vertical or horizontal by inspecting detector bounding box aspect ratios and local ink projection variance across alternating columns and gutters.

---

## `jp_ocr_dict.api`

### `JishoAPIHandler`

```python
class JishoAPIHandler:
    def __init__(self, db: SQLiteDictionary | None = None) -> None:
```

Hybrid dictionary provider combining an in-memory hot cache, an offline-first SQLite database, and asynchronous fallback to remote REST endpoints.

#### Methods

##### `lookup_candidates(candidates: list[str]) -> dict[str, Any] | None`
Iterates through an ordered candidate list (e.g. `[base_form, glued_surface, raw]`) and returns the first matching dictionary definition.

##### `fetch_jisho_info(word: str) -> dict[str, Any] | None`
Fetches definition, reading, JLPT rating, and part-of-speech metadata for a Japanese term.

##### `fetch_kanji_info(kanji_char: str) -> dict[str, Any] | None`
Retrieves stroke count, school grade, JLPT rating, and on/kun/nanori readings for a single Kanji character from SQLite or Kanjiapi.dev.

##### `fetch_kanji_list(text: str) -> list[dict[str, Any]]`
Extracts unique Kanji from `text` preserving compound reading order and fetches metadata for all characters concurrently.

##### `scrape_names_info(word: str) -> list[dict[str, str]]`
Retrieves surname and given name entries from SQLite or scraped from Jisho Names.

---

## `jp_ocr_dict.db_dictionary`

### `SQLiteDictionary`

```python
class SQLiteDictionary:
    def __init__(self, db_path: Path = DB_PATH) -> None:
```

High-performance, local-first SQLite database layer with Write-Ahead Logging (WAL) and B-tree indexing.

#### Methods

##### `get_word(keyword: str) -> dict[str, Any] | None`
Queries the `words` table by exact keyword or slug. Returns parsed JSON metadata or `None`.

##### `save_word(keyword: str, data: dict[str, Any]) -> None`
Persists a word entry using `INSERT ... ON CONFLICT(keyword) DO UPDATE`.

##### `get_kanji(kanji_char: str) -> dict[str, Any] | None`
Queries the `kanji` table by character.

##### `save_kanji(kanji_char: str, data: dict[str, Any]) -> None`
Persists a kanji entry.

##### `get_names(word: str) -> list[dict[str, str]] | None`
Queries the `names` table for name records.

##### `save_names(word: str, data: list[dict[str, str]]) -> None`
Persists name records.

##### `get_stats() -> dict[str, int]`
Returns total count of cached records across `words`, `kanji`, and `names`.

---

## `jp_ocr_dict.settings_manager`

### `SettingsManager`

```python
class SettingsManager:
    def __init__(self, settings_path: Path = SETTINGS_FILE) -> None:
```

Thread-safe configuration manager responsible for reading and persisting user preferences to `settings.json`.

#### Methods

##### `get(key: str) -> Any`
Retrieves a setting value, falling back to `DEFAULT_SETTINGS` if the key is not defined.

##### `set(key: str, value: Any) -> None`
Updates a setting in memory and commits the update to `settings.json`.
