# Japanese Desktop OCR Pop-up Dictionary

Welcome to the technical documentation for the **Japanese Desktop OCR Pop-up Dictionary**.

This software is a desktop utility inspired by browser tools like Yomichan and 10ten Japanese Reader, built to provide instant Japanese dictionary lookups across non-selectable graphic environments such as digital manga readers (BookWalker, ComicWalker), vertical light novels, and visual novels.

---

## The Problem

Browser extensions hook directly into HTML DOM text selection APIs to identify words and surface dictionary entries. However, desktop e-book readers and games render Japanese text directly to graphical canvases or Direct3D/OpenGL framebuffers:

- **Non-selectable text**: Characters cannot be highlighted, selected, or inspected via standard accessibility APIs.
- **OCR Challenges**: Traditional OCR solutions (such as Tesseract) struggle significantly with vertical text (*tategaki*), stylized manga fonts, noisy backgrounds, and tiny ruby text annotations (*furigana*).
- **Morphological Complexity**: Japanese words in continuous prose cannot be queried in a dictionary without decomposing conjugated verbs and adjectives (e.g. converting `食べさせられなかった` back to `食べる`).

---

## System Architecture Highlights

1. **Phased Progressive Initialization**: Decouples the primary snip pipeline (MangaOCR + Janome) from secondary hover models (EasyOCR), achieving operational readiness in under 1.8 seconds.
2. **Aspect-Ratio Letterboxing**: Dynamically samples image background pixels to pad vertical strips into 1:1 square inputs, eliminating Vision Transformer character squashing and hallucination.
3. **Multi-Column Paragraph Heuristics**: Detects multi-column selections to avoid horizontal slicing and sentence braiding across vertical columns.
4. **Local-First SQLite Engine**: High-performance indexed dictionary engine operating in Write-Ahead Logging (WAL) mode with sub-millisecond query latency and write-through caching.
5. **Lemma Recovery & Suffix Walkback**: Morphological analyzer that traverses inflection suffixes backward to find base verb stems.

---

## Documentation Contents

- **[Architecture](architecture.md)**: Detailed breakdown of the six pipeline layers from screen capture to Tkinter presentation.
- **[Configuration](configuration.md)**: Configuration parameters, keyboard shortcuts, theming options, and database importation.
- **[API Reference](api_reference.md)**: Class, method, argument, and return-type specifications across all modules.
