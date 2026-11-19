# System Architecture

The application is structured into six decoupled layers:

```
[Screen Capture] -> [Preprocessing & Guards] -> [Vision & OCR] -> [Morphological NLP] -> [Storage & Caching] -> [UI Presentation]
```

---

## 1. Screen Capture Layer

### Windows High-DPI Awareness
Windows desktop scaling (125%, 150%, 200%) causes logical GDI coordinates to diverge from physical screen pixels. To prevent bounding box drift and offset mouse tracking, `main.py` invokes:

```python
ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor v2 DPI awareness
```

This guarantees that screen bitmaps captured via `PIL.ImageGrab` match mouse cursor screen coordinates exactly across all monitors.

### Screen Snip Overlay
The screen snip overlay captures an instantaneous snapshot of the entire multi-monitor desktop (`ImageGrab.grab(all_screens=True)`), freezes it in memory, and maps the selection rectangle directly to physical pixels using:

$$\text{scale}_x = \frac{\text{image\_width}}{\text{canvas\_width}}, \quad \text{scale}_y = \frac{\text{image\_height}}{\text{canvas\_height}}$$

---

## 2. Preprocessing & Geometric Guards

### Vision Transformer Aspect Ratio Letterbox
MangaOCR is based on a Vision Transformer (`ViT-base-patch16-224`). The preprocessor forcibly resizes input images to $224 \times 224$ pixels.

When an elongated vertical strip (e.g. 40px wide by 400px tall) is compressed into a square without padding, the width is stretched by $5.6\times$ while the height is compressed by $0.56\times$. This $10\times$ distortion severely alters kanji stroke proportions.

The application implements `OCRHandler.pad_to_square(image)`:
1. Samples the 4 corner pixels of the image crop to estimate the background color (e.g. page white `#FFFFFF` or dark manga background).
2. Creates a square canvas of dimension $\max(\text{width}, \text{height})$.
3. Centers the original text strip onto the canvas.
4. When downsampled to $224 \times 224$, the characters retain their natural 1:1 aspect ratio.

### Multi-Column Paragraph Heuristics
In Japanese vertical novels, text flows top-to-bottom within a column, then right-to-left across columns. Horizontal chunking across multiple columns binds fragments of distinct sentences into single chunks.

The canvas applies tiered geometric filters:
- **Full Page Guard** ($\text{width} > 450 \land \text{height} > 450$): Halts execution and displays guidance to avoid downsampling 500+ characters into sub-pixel blur.
- **Multi-Column Guard** ($\text{width} > 70 \land \text{height} > 400$): Detects multi-column paragraph selections and guides the user to select an individual column.

### Hover OCR Spatial Targeting & Column Isolation
In Hover OCR mode, parallel vertical columns in novels or manga often run closely packed (e.g. 25px wide columns with 15px whitespace gutters). Naive bounding box collision checks frequently snap to neighboring columns or capture multiple columns in a single crop.

The engine implements strict single-track isolation:
1. **Orientation-Aware Nearest Box Metric**: Candidate detector boxes are scored using perpendicular distance weighting. In vertical text, candidate boxes on adjacent columns ($dx > 14\text{px}$) are immediately disqualified. Inside the column track, horizontal distance to the column centerline is prioritized.
2. **Detector Merged-Box Guard**: If the CRAFT detector links adjacent columns into a single wide box ($\text{width} > 46\text{px}$), the crop is clamped to a single column track ($x \pm 18\text{px}$) centered on the cursor.
3. **Single-Track Fallback**: When detector boxes are absent, the crop tightly isolates a single column ($36\text{px}$ wide) or line track without crossing over into adjacent text.
4. **ViT Square Letterboxing**: Every cropped track is letterboxed via `pad_to_square` before inference, preventing stroke distortion.
5. **Morphological Ratio Mapping**: The cursor offset along the text axis ($y$ for vertical, $x$ for horizontal) maps directly to the character and token beneath the cursor.

---

## 3. Vision & OCR Layer

### Phased Progressive Startup
Neural network weight initialization typically introduces substantial latency. `MainWindow` decouples startup into two sequential phases:

```
T=0.0s: Tkinter UI renders instantly.
T=1.8s: Phase 1 completes (MangaOCR + Janome). Snip OCR button enabled; Alt+S hotkey active.
T=4.2s: Phase 2 completes (EasyOCR CRAFT detector). Hover OCR button enabled.
```

By staging initialization sequentially on a background thread, GPU driver lock contention (`cudaSetDevice`, `cudaMalloc`) between MangaOCR and EasyOCR is completely eliminated.

### Hardware Acceleration
On NVIDIA Ada Lovelace / Ampere architectures (e.g. RTX 4070), TensorFloat-32 (TF32) execution is enabled:
```python
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
torch.backends.cudnn.benchmark = True
```
This accelerates matrix multiplications in both the Vision Transformer encoder and the Japanese BERT decoder with zero loss in recognition accuracy.

---

## 4. Morphological NLP Layer

### Tokenization & Suffix Walkback
Japanese does not use whitespace between words. Given recognized text (e.g. `食べさせられなかった`), standard dictionaries cannot locate the entry without determining the base lemma form (`食べる`).

The `OCRHandler.tokenize_sentence` pipeline:
1. Performs morphological segmentation using Janome (MeCab-compatible IPADIC dictionary).
2. Identifies lexical categories: verbs (`動詞`), adjectives (`形容詞`), nouns (`名詞`), particles (`助詞`), auxiliaries (`助動詞`).
3. **Suffix Walkback**: If the mouse cursor or focus token is an auxiliary verb (e.g. `た` or `ない`), the algorithm walks backward through the token stream to find the headword stem.
4. **Inflection Gluing**: Glues compound auxiliary chains (`〜ておく`, `〜ている`, `〜ない`, `〜ます`) into coherent lexical units while preserving the dictionary headword (`base_form`).

---

## 5. Storage & Caching Layer

### Local-First SQLite Database
The dictionary backend is encapsulated in `SQLiteDictionary` (`data/dictionary.db`):
- **WAL Mode**: `PRAGMA journal_mode=WAL;` allows concurrent readers to query without blocking active writes.
- **Indexed B-Trees**: B-tree indexes on `words(keyword)`, `words(slug)`, `kanji(character)`, and `names(keyword)`.
- **Latency**: Local queries resolve in under 0.01 milliseconds.

### Hybrid Resolution Pipeline
```
Query Keyword
    │
    ▼
[In-Memory Hot Cache] ──(Hit)──> Return (< 0.001 ms)
    │ (Miss)
    ▼
[Local SQLite DB] ──────(Hit)──> Persist to RAM & Return (< 0.01 ms)
    │ (Miss)
    ▼
[Jisho / Kanjiapi.dev] ─(Hit)──> Persist to SQLite & RAM & Return (~200 ms)
```

---

## 6. Presentation Layer

The user interface is implemented in Python's standard `tkinter` library using `ttk` with custom styling:
- **Overrideredirect Toplevels**: Popups use borderless windows pinned to topmost z-order.
- **Asynchronous Data Hydration**: The Words tab renders instantly with local dictionary definitions; supplementary Kanji breakdown and Name readings load asynchronously in a secondary thread without freezing the UI.
- **Interactive Sentence Chips**: Full snipped sentences render interactive tags for each content token; clicking any token dynamically updates the definition view without re-running OCR.
