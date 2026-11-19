import contextlib
import ctypes
import logging
import os
import re
import sys
import threading
import time
from typing import Any

# Enable offline HuggingFace/Transformers mode before importing manga_ocr so
# cached weights load immediately without network roundtrips on startup.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from janome.tokenizer import Tokenizer  # noqa: E402

try:
    from manga_ocr import MangaOcr  # noqa: E402
except ImportError:
    MangaOcr = None  # type: ignore

import numpy as np  # noqa: E402
from PIL import Image, ImageGrab  # noqa: E402
from settings_manager import settings  # noqa: E402

logger = logging.getLogger(__name__)

# Square capture region handles both vertical (BookWalker) and horizontal text
CAPTURE_WIDTH, CAPTURE_HEIGHT = 240, 240
JAPANESE_CHAR_REGEX = re.compile(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff\u3400-\u4dbf]")
CONTENT_POS = frozenset({"名詞", "動詞", "形容詞", "副詞", "連体詞", "感動詞"})
STRUCTURAL_PARTICLES = frozenset({"は", "が", "を", "に", "で", "と", "の", "へ", "も", "や", "か"})


class OCRHandler:
    def __init__(
        self,
        on_snip_ready: Any = None,
        on_all_ready: Any = None,
        defer_easyocr: bool = True,
    ) -> None:
        if MangaOcr is None:
            raise RuntimeError(
                "MangaOCR is required to run the OCR engine. "
                "Install it with: pip install manga-ocr torch"
            )

        self.last_word: str | None = None
        self.mocr: Any = None
        self.reader: Any = None
        self.tokenizer: Any = None
        self._reader_lock = threading.Lock()

        import torch

        # Hardware detection: Check if CUDA is available on a dedicated GPU
        gpu_avail = torch.cuda.is_available()
        self.is_gpu: bool = gpu_avail

        if gpu_avail:
            try:
                # Enable TF32 for Tensor Cores on Ampere/Ada (e.g. RTX 4070)
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.allow_tf32 = True
                gpu_name = torch.cuda.get_device_name(0)
                logger.info("Dedicated GPU detected: %s (CUDA %s)", gpu_name, torch.version.cuda)
            except Exception:
                logger.info("CUDA GPU is available.")
        else:
            # Optimize CPU thread allocation to prevent thread contention on Windows
            with contextlib.suppress(Exception):
                torch.set_num_threads(min(4, os.cpu_count() or 4))

        # Phase 1: High-priority Snip Engine (MangaOCR + Janome Tokenizer)
        # MangaOCR loads in ~1.5s from local cache without GPU contention
        from concurrent.futures import ThreadPoolExecutor

        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_mocr = executor.submit(self._init_manga_ocr, force_cpu=not gpu_avail)
            future_tokenizer = executor.submit(Tokenizer)

            self.mocr = future_mocr.result()
            self.tokenizer = future_tokenizer.result()

        logger.info(
            "Phase 1: Snip OCR engine ready in %.2fs (GPU=%s).",
            time.perf_counter() - t0,
            gpu_avail,
        )

        if on_snip_ready:
            try:
                on_snip_ready(self)
            except Exception as e:
                logger.error("Error in on_snip_ready callback: %s", e)

        # Phase 2: Background Hover Engine (EasyOCR CRAFT + CRNN)
        if defer_easyocr:

            def _load_easyocr_bg() -> None:
                t1 = time.perf_counter()
                self._ensure_reader_loaded(gpu_avail)
                logger.info("Phase 2: EasyOCR Reader ready in %.2fs.", time.perf_counter() - t1)
                if on_all_ready:
                    try:
                        on_all_ready(self)
                    except Exception as e:
                        logger.error("Error in on_all_ready callback: %s", e)

            threading.Thread(target=_load_easyocr_bg, daemon=True).start()
        else:
            self._ensure_reader_loaded(gpu_avail)
            if on_all_ready:
                on_all_ready(self)

    def _ensure_reader_loaded(self, gpu_avail: bool | None = None) -> Any:
        """Lazily imports and instantiates EasyOCR so startup import time is near zero."""
        if self.reader is not None:
            return self.reader
        with self._reader_lock:
            if self.reader is None:
                if gpu_avail is None:
                    try:
                        import torch

                        gpu_avail = torch.cuda.is_available()
                    except Exception:
                        gpu_avail = False
                try:
                    import easyocr

                    self.reader = easyocr.Reader(["ja", "en"], gpu=gpu_avail)
                except Exception as e:
                    logger.error("Failed to load EasyOCR: %s", e)
        return self.reader

    @staticmethod
    def _init_manga_ocr(force_cpu: bool = False) -> Any:
        """
        Initializes MangaOcr with offline flags to prevent blocking on network checks.
        Falls back to online initialization only if weights are not yet cached locally.
        """
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_OFFLINE"] = "1"
        try:
            return MangaOcr(force_cpu=force_cpu)
        except Exception as e:
            logger.info("Offline load skipped (%s), downloading/verifying online...", e)
            os.environ.pop("HF_HUB_OFFLINE", None)
            os.environ.pop("TRANSFORMERS_OFFLINE", None)
            hf_const = sys.modules.get("huggingface_hub.constants")
            if hf_const is not None and hasattr(hf_const, "HF_HUB_OFFLINE"):
                hf_const.HF_HUB_OFFLINE = False
            return MangaOcr(force_cpu=force_cpu)

    def _capture_hover_region(self, mouse_x: int, mouse_y: int) -> tuple[Image.Image, int, int]:
        """Captures a DPI-aware square region around the cursor and returns (image, rel_x, rel_y)."""
        capture_left = mouse_x - CAPTURE_WIDTH // 2
        capture_top = mouse_y - CAPTURE_HEIGHT // 2

        user32 = ctypes.windll.user32
        v_left = user32.GetSystemMetrics(76)
        v_top = user32.GetSystemMetrics(77)
        v_width = user32.GetSystemMetrics(78)
        v_height = user32.GetSystemMetrics(79)

        if v_width <= 0 or v_height <= 0:
            v_left = 0
            v_top = 0
            v_width = user32.GetSystemMetrics(0)
            v_height = user32.GetSystemMetrics(1)

        v_right = v_left + v_width
        v_bottom = v_top + v_height

        capture_left = max(v_left, capture_left)
        capture_top = max(v_top, capture_top)
        capture_right = min(v_right, capture_left + CAPTURE_WIDTH)
        capture_bottom = min(v_bottom, capture_top + CAPTURE_HEIGHT)

        capture_region = (capture_left, capture_top, capture_right, capture_bottom)
        image = ImageGrab.grab(bbox=capture_region, all_screens=True)
        return image, mouse_x - capture_left, mouse_y - capture_top

    def process_screenshot(self, mouse_x: int, mouse_y: int) -> list[str] | None:
        """
        Captures a square region around the cursor and returns a prioritized list
        of lookup candidates [base_form, glued_surface, raw_text] at the cursor position.
        """
        detail = self.process_screenshot_detailed(mouse_x, mouse_y)
        return detail["candidates"] if detail else None

    def process_screenshot_detailed(self, mouse_x: int, mouse_y: int) -> dict[str, Any] | None:
        """
        Captures a square region around the cursor and returns recognized context,
        interactive sentence tokens, and prioritized lookup candidates at the cursor.
        """
        image, rel_x, rel_y = self._capture_hover_region(mouse_x, mouse_y)
        return self._run_easyocr_with_parsing_detailed(image, rel_x, rel_y)

    @staticmethod
    def _merge_overlapping_text_chunks(parts: list[str]) -> str:
        """
        Merges adjacent text chunks by aligning overlapping suffix/prefix characters.
        Supports exact matching and fuzzy 1-character mismatch to tolerate edge boundaries.
        """
        if not parts:
            return ""
        merged = parts[0]
        for next_part in parts[1:]:
            if not next_part:
                continue
            best_overlap = 0
            max_check = min(len(merged), len(next_part), 12)

            # 1. Exact suffix/prefix match
            for i in range(max_check, 0, -1):
                if merged[-i:] == next_part[:i]:
                    best_overlap = i
                    break

            # 2. Fuzzy match (at most 1 character difference in overlap window >= 3)
            if best_overlap == 0 and len(merged) >= 4 and len(next_part) >= 4:
                for i in range(min(len(merged), len(next_part), 8), 2, -1):
                    suffix = merged[-i:]
                    prefix = next_part[:i]
                    diffs = sum(c1 != c2 for c1, c2 in zip(suffix, prefix, strict=False))
                    if diffs <= 1:
                        best_overlap = i
                        break

            if best_overlap > 0:
                merged += next_part[best_overlap:]
            else:
                merged += next_part
        return merged

    @staticmethod
    def pad_to_square(image: Image.Image) -> Image.Image:
        """
        Letterboxes an image into a square with estimated background color
        before feeding to Vision Transformer (ViT).

        ViT forcibly resizes any input to 224x224. Without square letterboxing,
        an elongated vertical line (e.g. 40x350) is stretched 5.6x horizontally
        and squashed vertically, distorting character strokes into unrecognizable
        squashed noise that triggers language model hallucinations.
        Square padding preserves natural character aspect ratio and stroke geometry.
        """
        w, h = image.size
        if w == h:
            return image

        max_dim = max(w, h)
        margin = 8 if max_dim < 120 else 4
        side = max_dim + 2 * margin

        try:
            arr = np.asarray(image)
            border_pixels = np.concatenate([arr[0, :], arr[-1, :], arr[:, 0], arr[:, -1]], axis=0)
            med = np.median(border_pixels, axis=0)
            if arr.ndim == 3:
                bg_color: Any = tuple(int(round(v)) for v in med)
            else:
                bg_color = int(round(float(med)))
        except Exception:
            bg_color = (255, 255, 255) if image.mode == "RGB" else 255

        square_img = Image.new(image.mode, (side, side), bg_color)
        paste_x = (side - w) // 2
        paste_y = (side - h) // 2
        square_img.paste(image, (paste_x, paste_y))
        return square_img

    def process_screensnip(self, image: Image.Image) -> str | None:
        """
        Runs MangaOCR on a snipped image.
        If the snip is an elongated vertical or horizontal strip, it splits it into
        aspect-ratio-controlled chunks and pads each chunk to a square so that the
        Vision Transformer (224x224 input) preserves character stroke geometry
        without squashing or hallucinating.
        """
        try:
            if image.mode != "RGB":
                image = image.convert("RGB")

            w, h = image.size
            if w <= 0 or h <= 0:
                return None

            # 1. Elongated Vertical Column (e.g. vertical novel line of 20+ characters)
            if (h / w) >= 3.0 and h > 300:
                chunk_h = min(360, max(180, int(w * 5.0)))
                overlap = min(int(chunk_h * 0.35), max(40, int(w * 1.5)))
                stride = max(50, chunk_h - overlap)

                chunks = []
                top = 0
                while top < h:
                    bottom = min(h, top + chunk_h)
                    chunk = image.crop((0, top, w, bottom))
                    chunks.append(self.pad_to_square(chunk))
                    if bottom >= h:
                        break
                    top += stride

                logger.info(
                    "Vertical strip detected (%dx%d, ratio=%.1f). Sliced into %d square-padded chunks for ViT.",
                    w,
                    h,
                    h / w,
                    len(chunks),
                )
                recognized_parts = []
                for chunk in chunks:
                    txt = self.mocr(chunk)
                    if txt:
                        clean = "".join(txt.split())
                        if clean:
                            recognized_parts.append(clean)

                full_text = self._merge_overlapping_text_chunks(recognized_parts)
                return full_text if full_text else None

            # 2. Elongated Horizontal Line
            elif (w / h) >= 3.0 and w > 350:
                chunk_w = min(400, max(180, int(h * 5.0)))
                overlap = min(int(chunk_w * 0.35), max(40, int(h * 1.5)))
                stride = max(50, chunk_w - overlap)

                chunks = []
                left = 0
                while left < w:
                    right = min(w, left + chunk_w)
                    chunk = image.crop((left, 0, right, h))
                    chunks.append(self.pad_to_square(chunk))
                    if right >= w:
                        break
                    left += stride

                logger.info(
                    "Horizontal strip detected (%dx%d, ratio=%.1f). Sliced into %d square-padded chunks for ViT.",
                    w,
                    h,
                    w / h,
                    len(chunks),
                )
                recognized_parts = []
                for chunk in chunks:
                    txt = self.mocr(chunk)
                    if txt:
                        clean = "".join(txt.split())
                        if clean:
                            recognized_parts.append(clean)

                full_text = self._merge_overlapping_text_chunks(recognized_parts)
                return full_text if full_text else None

            # 3. Standard speech bubbles, short vertical/horizontal phrases (pad to square!)
            padded = self.pad_to_square(image)
            text = self.mocr(padded)
            if text:
                return "".join(text.split())
            return None
        except Exception as e:
            logger.error("OCR Error in process_screensnip: %s", e)
            return None

    def process_screensnip_detailed(self, image: Image.Image) -> dict[str, Any] | None:
        """
        Runs MangaOCR on a snipped image and tokenizes the recognized sentence
        into clickable words so full manga speech bubbles can be explored.
        """
        raw_text = self.process_screensnip(image)
        if not raw_text:
            return None

        sentence_tokens = self.tokenize_sentence(raw_text)
        primary_candidates: list[str] = []
        seen: set[str] = set()

        def _add_candidate(cand: str) -> None:
            if cand and cand not in seen and JAPANESE_CHAR_REGEX.search(cand):
                seen.add(cand)
                primary_candidates.append(cand)

        if len(sentence_tokens) == 1:
            for cand in sentence_tokens[0]["candidates"]:
                _add_candidate(cand)
            _add_candidate(raw_text)
        else:
            if len(raw_text) <= 10:
                _add_candidate(raw_text)
            for tok in sentence_tokens:
                if tok["is_content_word"]:
                    for cand in tok["candidates"]:
                        _add_candidate(cand)
            for tok in sentence_tokens:
                if not tok["is_content_word"]:
                    for cand in tok["candidates"]:
                        _add_candidate(cand)
            _add_candidate(raw_text)

        return {
            "raw_text": raw_text,
            "tokens": sentence_tokens,
            "primary_candidates": primary_candidates,
        }

    @staticmethod
    def _is_glued_suffix_token(token: Any) -> bool:
        """Returns True if token is an auxiliary verb, suffix, or dependent inflection."""
        pos_parts = token.part_of_speech.split(",")
        pos_major = pos_parts[0]
        pos_sub = pos_parts[1] if len(pos_parts) > 1 else ""
        return (
            pos_major == "助動詞"
            or pos_sub in ("接続助詞", "接尾")
            or (pos_major in ("動詞", "形容詞") and pos_sub == "非自立")
        )

    def tokenize_sentence(self, text: str) -> list[dict[str, Any]]:
        """
        Splits a Japanese phrase or sentence into interactive word tokens,
        gluing verb/adjective inflections while preserving dictionary base forms.
        """
        tokens = list(self.tokenizer.tokenize(text))
        if not tokens:
            return []

        structured: list[dict[str, Any]] = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            pos_parts = tok.part_of_speech.split(",")
            pos_major = pos_parts[0]
            pos_sub = pos_parts[1] if len(pos_parts) > 1 else ""

            surface = tok.surface
            base_form = tok.base_form if tok.base_form != "*" else surface
            glued = False

            # Glue trailing auxiliary verbs, dependent inflections, and conjunctive particles
            if pos_major in ("動詞", "形容詞"):
                j = i + 1
                while j < len(tokens) and self._is_glued_suffix_token(tokens[j]):
                    surface += tokens[j].surface
                    glued = True
                    j += 1
                i = j
            else:
                i += 1

            is_content = (
                pos_major in ("名詞", "動詞", "形容詞", "副詞", "連体詞", "感動詞")
                and pos_sub != "空白"
                and bool(JAPANESE_CHAR_REGEX.search(surface))
            )

            candidates: list[str] = []
            for cand in (base_form, surface):
                if cand and cand not in candidates and JAPANESE_CHAR_REGEX.search(cand):
                    candidates.append(cand)
            if (
                glued
                and tok.base_form
                and tok.base_form != "*"
                and tok.base_form not in candidates
                and JAPANESE_CHAR_REGEX.search(tok.base_form)
            ):
                candidates.append(tok.base_form)
            if (
                pos_major == "名詞"
                and i < len(tokens)
                and (tokens[i].base_form == "する" or tokens[i].surface == "する")
            ):
                suru_cand = f"{surface}する"
                if suru_cand not in candidates:
                    candidates.append(suru_cand)

            structured.append(
                {
                    "surface": surface,
                    "base_form": base_form,
                    "pos": pos_major,
                    "is_content_word": is_content,
                    "candidates": candidates,
                }
            )

        return structured

    @staticmethod
    def _detect_local_orientation(
        image_np: np.ndarray,
        cursor_x: int,
        cursor_y: int,
        results: list[Any] | None = None,
    ) -> bool:
        """
        Determines whether the text at (cursor_x, cursor_y) is vertically oriented.

        Combines contrast-agnostic local ink projection variance (handling both
        light and dark mode backgrounds) with directional detector bounding boxes
        while rejecting wide multi-column horizontal detector mergers.

        Returns:
            True if vertical orientation is detected, False for horizontal.
        """
        h_img, w_img = image_np.shape[:2]
        r = 55
        x1, x2 = max(0, cursor_x - r), min(w_img, cursor_x + r)
        y1, y2 = max(0, cursor_y - r), min(h_img, cursor_y + r)

        var_x = 0.0
        var_y = 0.0
        has_ink = False
        if (x2 - x1) >= 10 and (y2 - y1) >= 10:
            patch = image_np[y1:y2, x1:x2]
            gray = np.mean(patch[:, :, :3], axis=2) if patch.ndim == 3 else patch.astype(float)
            bg_est = float(np.median(gray))
            ink_mask = np.abs(gray - bg_est) > 25.0
            if np.any(ink_mask):
                has_ink = True
                x_proj = np.sum(ink_mask, axis=0)
                y_proj = np.sum(ink_mask, axis=1)
                var_x = float(np.var(x_proj)) if len(x_proj) > 0 else 0.0
                var_y = float(np.var(y_proj)) if len(y_proj) > 0 else 0.0

                if var_x > var_y * 1.35:
                    return True
                if var_y > var_x * 1.35:
                    return False

        if results:
            vert_count = 0
            horiz_count = 0
            for bbox, _text, _prob in results:
                tl, tr, br, bl = bbox
                w = max(1.0, max(tr[0], br[0]) - min(tl[0], bl[0]))
                h = max(1.0, max(bl[1], br[1]) - min(tl[1], tr[1]))
                cx = (min(tl[0], bl[0]) + max(tr[0], br[0])) / 2.0
                cy = (min(tl[1], tr[1]) + max(bl[1], br[1])) / 2.0
                if abs(cursor_x - cx) < 65 and abs(cursor_y - cy) < 65:
                    if h > w * 1.4:
                        vert_count += 1
                    elif w > h * 1.6 and h < 44:
                        horiz_count += 1
            if vert_count > horiz_count:
                return True
            if horiz_count > vert_count:
                return False

        if not has_ink:
            return True
        if var_x > var_y * 1.15:
            return True
        return not var_y > var_x * 1.15

    @staticmethod
    def _select_target_box_and_bounds(
        results: list[Any],
        cursor_x: int,
        cursor_y: int,
        img_w: int,
        img_h: int,
        is_vertical: bool,
    ) -> tuple[int, int, int, int]:
        """
        Selects the closest detector bounding box to the cursor using an
        orientation-weighted distance metric, preventing jumps to adjacent
        parallel columns or lines.

        Guards against detector mergers by clamping multi-column or multi-line
        boxes, and expands short fragmented detector boxes along the reading axis
        so full words are preserved.

        Returns:
            Tuple (crop_x1, crop_y1, crop_x2, crop_y2).
        """
        best_box = None
        best_score = float("inf")

        for bbox, _text, _prob in results:
            tl, tr, br, bl = bbox
            x_min, x_max = min(tl[0], bl[0]), max(tr[0], br[0])
            y_min, y_max = min(tl[1], tr[1]), max(bl[1], br[1])
            cx = (x_min + x_max) / 2.0
            cy = (y_min + y_max) / 2.0

            dx = max(0.0, x_min - cursor_x, cursor_x - x_max)
            dy = max(0.0, y_min - cursor_y, cursor_y - y_max)

            if is_vertical:
                # Vertical text: horizontal alignment is critical.
                # Disqualify candidate boxes that lie in an adjacent column track.
                if dx > 32:
                    continue
                if dx == 0 and dy == 0:
                    score = abs(cursor_x - cx) * 3.0 + abs(cursor_y - cy) * 0.1
                else:
                    score = 40.0 + (dx * 12.0) + (dy * 0.5)
            else:
                # Horizontal text: vertical alignment is critical.
                # Disqualify candidate boxes that lie in adjacent lines.
                if dy > 32:
                    continue
                if dx == 0 and dy == 0:
                    score = abs(cursor_y - cy) * 3.0 + abs(cursor_x - cx) * 0.1
                else:
                    score = 40.0 + (dy * 12.0) + (dx * 0.5)

            if score < best_score:
                best_score = score
                best_box = (x_min, y_min, x_max, y_max)

        if best_box is not None and best_score < 180.0:
            bx_min, by_min, bx_max, by_max = best_box
            box_w = bx_max - bx_min
            box_h = by_max - by_min

            if is_vertical:
                # If CRAFT merged adjacent columns into a single wide box (>46px),
                # clamp the horizontal crop to the single column containing the cursor.
                if box_w > 46:
                    crop_x1 = max(0, int(cursor_x - 18))
                    crop_x2 = min(img_w, int(cursor_x + 18))
                else:
                    crop_x1 = max(0, int(bx_min - 4))
                    crop_x2 = min(img_w, int(bx_max + 4))

                if box_h < 120:
                    crop_y1 = min(max(0, int(by_min - 4)), max(0, int(cursor_y - 75)))
                    crop_y2 = max(min(img_h, int(by_max + 4)), min(img_h, int(cursor_y + 75)))
                else:
                    crop_y1 = max(0, int(by_min - 4))
                    crop_y2 = min(img_h, int(by_max + 4))
            else:
                # If CRAFT merged adjacent lines into a single tall box (>46px),
                # clamp the vertical crop to the single line containing the cursor.
                if box_h > 46:
                    crop_y1 = max(0, int(cursor_y - 18))
                    crop_y2 = min(img_h, int(cursor_y + 18))
                else:
                    crop_y1 = max(0, int(by_min - 4))
                    crop_y2 = min(img_h, int(by_max + 4))

                if box_w < 120:
                    crop_x1 = min(max(0, int(bx_min - 4)), max(0, int(cursor_x - 75)))
                    crop_x2 = max(min(img_w, int(bx_max + 4)), min(img_w, int(cursor_x + 75)))
                else:
                    crop_x1 = max(0, int(bx_min - 4))
                    crop_x2 = min(img_w, int(bx_max + 4))
        else:
            # Fallback: isolate a single column (vertical) or single line (horizontal)
            if is_vertical:
                half_w, half_h = 18, 90
            else:
                half_w, half_h = 90, 18

            crop_x1 = max(0, int(cursor_x - half_w))
            crop_x2 = min(img_w, int(cursor_x + half_w))
            crop_y1 = max(0, int(cursor_y - half_h))
            crop_y2 = min(img_h, int(cursor_y + half_h))

        return crop_x1, crop_y1, crop_x2, crop_y2

    @staticmethod
    def _find_best_ink_track(
        axis_ink: np.ndarray, origin_offset: int, cursor_coord: int
    ) -> tuple[int, int] | None:
        """
        Finds the contiguous ink track closest to `cursor_coord` along a 1D
        perpendicular projection, bridging tiny intra-character stroke gaps.
        """
        if len(axis_ink) == 0:
            return None
        max_ink = float(np.max(axis_ink))
        if max_ink <= 0:
            return None

        active = (axis_ink > max(2.0, 0.12 * max_ink)).copy()
        # Bridge <= 3px internal gaps inside multi-stroke characters (e.g. 川, 門)
        n = len(active)
        i = 0
        while i < n:
            if active[i]:
                gap_start = i + 1
                gap_end = gap_start
                while gap_end < n and not active[gap_end] and (gap_end - gap_start) <= 3:
                    gap_end += 1
                if gap_end < n and active[gap_end] and (gap_end - gap_start) <= 3:
                    active[gap_start:gap_end] = True
                i = gap_end
            else:
                i += 1

        best_seg: tuple[int, int] | None = None
        best_dist = float("inf")
        idx = 0
        while idx < n:
            if active[idx]:
                seg_start = idx
                while idx < n and active[idx]:
                    idx += 1
                seg_end = idx - 1
                seg_w = seg_end - seg_start + 1
                if 8 <= seg_w <= 42:
                    g1 = origin_offset + seg_start
                    g2 = origin_offset + seg_end + 1
                    dist = float(max(0, g1 - cursor_coord, cursor_coord - g2))
                    if dist <= 14.0:
                        center_dist = abs((g1 + g2) / 2.0 - cursor_coord)
                        score = dist * 10.0 + center_dist
                        if score < best_dist:
                            best_dist = score
                            best_seg = (g1, g2)
            else:
                idx += 1
        return best_seg

    @classmethod
    def _refine_hover_crop_and_ratio(
        cls,
        image_np: np.ndarray,
        crop_bounds: tuple[int, int, int, int],
        cursor_x: int,
        cursor_y: int,
        is_vertical: bool,
    ) -> tuple[tuple[int, int, int, int], float]:
        """
        Centers the crop tightly on the active character column/line around the
        cursor, trims excess leading/trailing whitespace along the reading axis,
        and computes the cursor ratio relative to actual inked pixels.
        """
        crop_x1, crop_y1, crop_x2, crop_y2 = crop_bounds
        h_img, w_img = image_np.shape[:2]
        if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
            return crop_bounds, 0.5

        # 1. Perpendicular ink-track centering (prevents clipping strokes on off-center hovers)
        if is_vertical:
            band_x1 = max(0, cursor_x - 28)
            band_x2 = min(w_img, cursor_x + 28)
            if band_x2 > band_x1:
                band = image_np[crop_y1:crop_y2, band_x1:band_x2]
                gray_b = np.mean(band[:, :, :3], axis=2) if band.ndim == 3 else band.astype(float)
                ink_b = np.abs(gray_b - float(np.median(gray_b))) > 22.0
                track = cls._find_best_ink_track(np.sum(ink_b, axis=0), band_x1, cursor_x)
                if track is not None:
                    crop_x1 = max(0, track[0] - 4)
                    crop_x2 = min(w_img, track[1] + 4)
        else:
            band_y1 = max(0, cursor_y - 28)
            band_y2 = min(h_img, cursor_y + 28)
            if band_y2 > band_y1:
                band = image_np[band_y1:band_y2, crop_x1:crop_x2]
                gray_b = np.mean(band[:, :, :3], axis=2) if band.ndim == 3 else band.astype(float)
                ink_b = np.abs(gray_b - float(np.median(gray_b))) > 22.0
                track = cls._find_best_ink_track(np.sum(ink_b, axis=1), band_y1, cursor_y)
                if track is not None:
                    crop_y1 = max(0, track[0] - 4)
                    crop_y2 = min(h_img, track[1] + 4)

        if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
            return crop_bounds, 0.5

        # 2. Reading-axis ink span trimming & ink-relative ratio mapping
        crop_patch = image_np[crop_y1:crop_y2, crop_x1:crop_x2]
        gray_c = (
            np.mean(crop_patch[:, :, :3], axis=2)
            if crop_patch.ndim == 3
            else crop_patch.astype(float)
        )
        ink_c = np.abs(gray_c - float(np.median(gray_c))) > 22.0
        line_ink = np.sum(ink_c, axis=1 if is_vertical else 0)
        nz = np.where(line_ink >= 2)[0]

        cursor_offset = (cursor_y - crop_y1) if is_vertical else (cursor_x - crop_x1)
        span = (crop_y2 - crop_y1) if is_vertical else (crop_x2 - crop_x1)

        if len(nz) >= 2 and (int(nz[-1]) - int(nz[0])) >= 12:
            ink_start, ink_end = int(nz[0]), int(nz[-1])
            ratio = max(0.0, min(1.0, (cursor_offset - ink_start) / max(1, ink_end - ink_start)))

            trim_start = max(0, ink_start - 6)
            trim_end = min(span, ink_end + 7)
            if (trim_end - trim_start) >= 12:
                if is_vertical:
                    crop_y1_new = crop_y1 + trim_start
                    crop_y2_new = crop_y1 + trim_end
                    crop_y1, crop_y2 = crop_y1_new, crop_y2_new
                else:
                    crop_x1_new = crop_x1 + trim_start
                    crop_x2_new = crop_x1 + trim_end
                    crop_x1, crop_x2 = crop_x1_new, crop_x2_new
        else:
            ratio = max(0.0, min(1.0, cursor_offset / max(1, span)))

        return (crop_x1, crop_y1, crop_x2, crop_y2), ratio

    def _run_easyocr_with_parsing(
        self, image: Image.Image, relative_x: int, relative_y: int
    ) -> list[str] | None:
        detail = self._run_easyocr_with_parsing_detailed(image, relative_x, relative_y)
        return detail["candidates"] if detail else None

    def _run_easyocr_with_parsing_detailed(
        self, image: Image.Image, relative_x: int, relative_y: int
    ) -> dict[str, Any] | None:
        try:
            image_np = np.array(image)
            reader = self._ensure_reader_loaded()
            results = reader.readtext(image_np) if reader is not None else []

            # 1. Determine orientation (user override or auto-detection)
            orientation_setting = settings.get("ocr_orientation")
            if orientation_setting == "vertical":
                is_vertical = True
            elif orientation_setting == "horizontal":
                is_vertical = False
            else:
                is_vertical = self._detect_local_orientation(
                    image_np, relative_x, relative_y, results
                )

            # 2. Extract single-track crop boundaries and refine against ink pixels
            img_w, img_h = image.size
            initial_bounds = self._select_target_box_and_bounds(
                results, relative_x, relative_y, img_w, img_h, is_vertical
            )
            (crop_x1, crop_y1, crop_x2, crop_y2), ratio = self._refine_hover_crop_and_ratio(
                image_np, initial_bounds, relative_x, relative_y, is_vertical
            )

            crop_w = crop_x2 - crop_x1
            crop_h = crop_y2 - crop_y1
            if crop_w <= 4 or crop_h <= 4:
                return None

            # 3. High-accuracy recognition via MangaOCR with square aspect-ratio padding
            cropped_img = image.crop((crop_x1, crop_y1, crop_x2, crop_y2))
            padded_img = self.pad_to_square(cropped_img)
            target_text = "".join(self.mocr(padded_img).split())

            if not target_text or not JAPANESE_CHAR_REGEX.search(target_text):
                return None

            # 4. Map refined ink-relative ratio to candidate words & interactive tokens
            candidates = self._extract_candidates_at_ratio(target_text, ratio)
            if not candidates:
                return None

            self.last_word = candidates[0]
            return {
                "raw_text": target_text,
                "candidates": candidates,
                "tokens": self.tokenize_sentence(target_text),
            }

        except Exception as e:
            logger.error("OCR Parsing Error: %s", e)
            return None

    def _extract_candidates_at_ratio(self, target_text: str, ratio: float) -> list[str]:
        """
        Maps a [0.0, 1.0] spatial ratio inside `target_text` to a Janome token,
        snaps off punctuation/particle boundaries, walks backward across
        conjugation suffixes, glues inflections, and returns prioritized lookups.
        """
        char_len = len(target_text)
        if char_len == 0:
            return []

        char_index = min(char_len - 1, max(0, int(ratio * char_len)))
        tokens = list(self.tokenizer.tokenize(target_text))
        if not tokens:
            return [target_text]

        # Locate token covering char_index
        target_idx = 0
        current_pos = 0
        for i, token in enumerate(tokens):
            token_len = len(token.surface)
            if current_pos <= char_index < (current_pos + token_len):
                target_idx = i
                break
            current_pos += token_len

        # 1. Snap off punctuation/non-Japanese tokens to nearest Japanese token
        if not JAPANESE_CHAR_REGEX.search(tokens[target_idx].surface):
            prefer_forward = target_idx == 0
            snapped_idx = None
            for offset in range(1, len(tokens)):
                order = (
                    (target_idx + offset, target_idx - offset)
                    if prefer_forward
                    else (target_idx - offset, target_idx + offset)
                )
                for cand_idx in order:
                    if 0 <= cand_idx < len(tokens) and JAPANESE_CHAR_REGEX.search(
                        tokens[cand_idx].surface
                    ):
                        snapped_idx = cand_idx
                        break
                if snapped_idx is not None:
                    break
            if snapped_idx is None:
                return []
            target_idx = snapped_idx

        original_idx = target_idx
        original_token = tokens[target_idx]

        # 2. Walk backward from auxiliary verbs, suffixes, or dependent inflections
        while target_idx > 0:
            pos_parts = tokens[target_idx].part_of_speech.split(",")
            pos_major = pos_parts[0]
            pos_sub = pos_parts[1] if len(pos_parts) > 1 else ""
            is_suffix_or_aux = (
                pos_major == "助動詞"
                or pos_sub in ("接尾", "接続助詞", "非自立")
                or (pos_major == "助詞" and pos_sub in ("接続助詞", "並立助詞", "終助詞"))
            )
            if is_suffix_or_aux:
                prev_parts = tokens[target_idx - 1].part_of_speech.split(",")
                prev_major = prev_parts[0]
                prev_sub = prev_parts[1] if len(prev_parts) > 1 else ""
                if prev_major in ("動詞", "形容詞", "名詞", "助動詞") or (
                    prev_major == "助詞" and prev_sub == "接続助詞"
                ):
                    target_idx -= 1
                    continue
            break

        # If walkback stopped on する attached to a preceding noun (e.g. 勉強した -> 勉強)
        if target_idx > 0:
            curr_tok = tokens[target_idx]
            curr_base = curr_tok.base_form if curr_tok.base_form != "*" else curr_tok.surface
            if (
                curr_base == "する"
                and tokens[target_idx - 1].part_of_speech.split(",")[0] == "名詞"
            ):
                target_idx -= 1

        # 3. If cursor landed directly on a 1-char structural particle, snap to adjacent content word
        if (
            tokens[target_idx].part_of_speech.split(",")[0] == "助詞"
            and tokens[target_idx].surface in STRUCTURAL_PARTICLES
        ):
            for adj_idx in (target_idx - 1, target_idx + 1):
                if 0 <= adj_idx < len(tokens):
                    adj_tok = tokens[adj_idx]
                    if adj_tok.part_of_speech.split(",")[0] in CONTENT_POS and (
                        JAPANESE_CHAR_REGEX.search(adj_tok.surface)
                    ):
                        target_idx = adj_idx
                        break

        base_token = tokens[target_idx]
        pos_major = base_token.part_of_speech.split(",")[0]
        base_form = (
            base_token.base_form
            if base_token.base_form and base_token.base_form != "*"
            else base_token.surface
        )
        glued_surface = base_token.surface

        # Forward suffix gluing for verbs/adjectives
        if pos_major in ("動詞", "形容詞", "助動詞"):
            curr = target_idx + 1
            while curr < len(tokens) and self._is_glued_suffix_token(tokens[curr]):
                glued_surface += tokens[curr].surface
                curr += 1
        # Compound noun check (glue adjacent noun suffix/counter)
        elif pos_major == "名詞" and (target_idx + 1) < len(tokens):
            next_tok = tokens[target_idx + 1]
            next_parts = next_tok.part_of_speech.split(",")
            if next_parts[0] == "名詞" and (len(next_parts) > 1 and next_parts[1] == "接尾"):
                glued_surface += next_tok.surface

        extra_compounds: list[str] = []
        if pos_major == "名詞":
            if (target_idx + 1) < len(tokens):
                next_tok = tokens[target_idx + 1]
                next_major = next_tok.part_of_speech.split(",")[0]
                next_base = next_tok.base_form if next_tok.base_form != "*" else next_tok.surface
                if next_base == "する":
                    extra_compounds.append(f"{base_token.surface}する")
                elif next_major == "名詞":
                    extra_compounds.append(f"{base_token.surface}{next_tok.surface}")
            if target_idx > 0 and tokens[target_idx - 1].part_of_speech.split(",")[0] == "名詞":
                extra_compounds.append(f"{tokens[target_idx - 1].surface}{base_token.surface}")

        neighbor_cands: list[str] = []
        for idx in (target_idx - 1, target_idx + 1, original_idx - 1, original_idx + 1):
            if 0 <= idx < len(tokens) and idx != target_idx:
                n_tok = tokens[idx]
                if n_tok.part_of_speech.split(",")[0] in CONTENT_POS:
                    n_base = n_tok.base_form if n_tok.base_form != "*" else n_tok.surface
                    neighbor_cands.extend([n_base, n_tok.surface])

        candidates: list[str] = []
        for cand in (
            base_form,
            glued_surface,
            *extra_compounds,
            base_token.surface,
            *neighbor_cands,
            original_token.surface,
            target_text,
        ):
            if cand and cand not in candidates and JAPANESE_CHAR_REGEX.search(cand):
                candidates.append(cand)

        return candidates
