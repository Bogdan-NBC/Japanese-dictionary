import sys
from pathlib import Path

# Add package directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "jp_ocr_dict"))

from janome.tokenizer import Tokenizer  # noqa: E402
from ocr import OCRHandler  # noqa: E402


def _make_lightweight_ocr_handler() -> OCRHandler:
    """Creates an OCRHandler with only Janome initialized for fast, headless unit tests."""
    handler = OCRHandler.__new__(OCRHandler)
    handler.last_word = None
    handler.tokenizer = Tokenizer()
    return handler


def test_tokenize_sentence_single_and_multi_word() -> None:
    handler = _make_lightweight_ocr_handler()
    tokens = handler.tokenize_sentence("今日は天気がいいですね")
    surfaces = [t["surface"] for t in tokens]

    assert "今日" in surfaces
    assert "天気" in surfaces
    # Check content word tagging
    content_words = [t["surface"] for t in tokens if t["is_content_word"]]
    assert "今日" in content_words
    assert "天気" in content_words
    assert "は" not in content_words  # Particle は should not be marked content word


def test_tokenize_sentence_verb_auxiliary_gluing() -> None:
    handler = _make_lightweight_ocr_handler()
    # 走っています -> 走って (verb) + い (verb) + ます (auxiliary)
    tokens = handler.tokenize_sentence("公園で走っています")
    surfaces = [t["surface"] for t in tokens]
    assert "公園" in surfaces

    # Check that verb base_form is preserved
    base_forms = [t["base_form"] for t in tokens]
    assert "走る" in base_forms


def test_extract_candidates_at_ratio_beginning_middle_end() -> None:
    handler = _make_lightweight_ocr_handler()
    phrase = "面白い本"

    # Ratio near 0.1 -> cursor on "面白い"
    candidates_start = handler._extract_candidates_at_ratio(phrase, 0.1)
    assert any("面白い" in c for c in candidates_start)

    # Ratio near 0.9 -> cursor on "本"
    candidates_end = handler._extract_candidates_at_ratio(phrase, 0.9)
    assert any("本" in c for c in candidates_end)


def test_suffix_walkback_and_base_form_extraction() -> None:
    handler = _make_lightweight_ocr_handler()
    # Cursor at the end of '食べなかった' (ratio=0.85 lands on the 'た'/'なかっ' suffix)
    candidates = handler._extract_candidates_at_ratio("食べなかった", 0.85)
    assert candidates[0] == "食べる"
    assert "食べなかった" in candidates

    # Complex passive-causative: 食べさせられた -> 食べる
    candidates_complex = handler._extract_candidates_at_ratio("食べさせられた", 0.85)
    assert candidates_complex[0] == "食べる"


def test_extract_candidates_empty_or_no_match() -> None:
    handler = _make_lightweight_ocr_handler()
    assert handler._extract_candidates_at_ratio("", 0.5) == []
    # Roman text only
    cand = handler._extract_candidates_at_ratio("Hello World", 0.5)
    # Should be empty because no Japanese characters matched
    assert cand == []


def test_merge_overlapping_text_chunks() -> None:
    handler = _make_lightweight_ocr_handler()

    parts = [
        "蛍光灯の明かりが鈍く沈んだ",
        "鈍く沈んだ病院の廊下に、",
        "病院の廊下に、女の声が響いていた。",
    ]
    merged = handler._merge_overlapping_text_chunks(parts)
    assert merged == "蛍光灯の明かりが鈍く沈んだ病院の廊下に、女の声が響いていた。"

    # Test empty or single element
    assert handler._merge_overlapping_text_chunks([]) == ""
    assert handler._merge_overlapping_text_chunks(["単語"]) == "単語"

    # Test no overlap
    assert handler._merge_overlapping_text_chunks(["猫", "犬"]) == "猫犬"


def test_select_target_box_vertical_parallel_columns() -> None:
    """
    Ensures that hovering over Column 1 (駄目) unambiguously selects Column 1
    and rejects Column 2 (同士), even if Column 2 is listed first by the detector.
    """
    handler = _make_lightweight_ocr_handler()

    # Column 1 at x in [8, 34], Column 2 at x in [60, 85]
    results = [
        (
            [[60, 10], [85, 10], [85, 220], [60, 220]],
            "同士が、沈痛な面",
            0.95,
        ),  # Col 2 listed first
        ([[8, 10], [34, 10], [34, 220], [8, 220]], "「駄目だったのね」", 0.92),  # Col 1
    ]

    # 1. Hover on Column 1 (x=21, y=55 over 駄目)
    crop_x1, crop_y1, crop_x2, crop_y2 = handler._select_target_box_and_bounds(
        results=results,
        cursor_x=21,
        cursor_y=55,
        img_w=101,
        img_h=251,
        is_vertical=True,
    )
    # Bounds must strictly capture Column 1 and must not cross into Column 2 (x >= 60)
    assert crop_x1 <= 8
    assert crop_x2 < 50
    assert crop_x2 < 60

    # 2. Hover on Column 2 (x=73, y=55 over 同士)
    crop2_x1, crop2_y1, crop2_x2, crop2_y2 = handler._select_target_box_and_bounds(
        results=results,
        cursor_x=73,
        cursor_y=55,
        img_w=101,
        img_h=251,
        is_vertical=True,
    )
    # Bounds must strictly capture Column 2 and must not cross into Column 1 (x <= 34)
    assert crop2_x1 > 40
    assert crop2_x2 >= 85


def test_select_target_box_merged_multicolumn_guard() -> None:
    """
    Ensures that if the text detector merges two parallel columns into a single wide box,
    the bounding logic clamps to a narrow column track centered on the cursor.
    """
    handler = _make_lightweight_ocr_handler()

    # Detector merged both columns into one wide box (width = 77px)
    results = [
        ([[8, 10], [85, 10], [85, 220], [8, 220]], "同士が、沈痛な面「駄目だったのね」", 0.90)
    ]

    # Hover over Column 1 at x=21
    crop_x1, crop_y1, crop_x2, crop_y2 = handler._select_target_box_and_bounds(
        results=results,
        cursor_x=21,
        cursor_y=55,
        img_w=101,
        img_h=251,
        is_vertical=True,
    )
    # Must be clamped so it does not reach Column 2 (x >= 60)
    assert crop_x2 <= 45
    assert (crop_x2 - crop_x1) <= 40


def test_select_target_box_fallback_single_column_isolation() -> None:
    """
    Ensures that when no detector box matches, the fallback produces a single-column
    slice that never touches neighboring columns.
    """
    handler = _make_lightweight_ocr_handler()

    # Empty results (detector missed font)
    results: list = []

    crop_x1, crop_y1, crop_x2, crop_y2 = handler._select_target_box_and_bounds(
        results=results,
        cursor_x=21,
        cursor_y=55,
        img_w=101,
        img_h=251,
        is_vertical=True,
    )
    assert crop_x1 == max(0, 21 - 18)
    assert crop_x2 == min(101, 21 + 18)
    assert crop_x2 < 50
    assert (crop_x2 - crop_x1) == 36


def test_select_target_box_horizontal_line_tracking() -> None:
    """
    Ensures horizontal text tracking rejects lines above and below the cursor.
    """
    handler = _make_lightweight_ocr_handler()

    results = [
        ([[10, 10], [200, 10], [200, 35], [10, 35]], "Line 1 text above", 0.90),
        ([[10, 50], [200, 50], [200, 75], [10, 75]], "Line 2 target line", 0.92),
        ([[10, 90], [200, 90], [200, 115], [10, 115]], "Line 3 text below", 0.88),
    ]

    # Hover over Line 2 (x=100, y=62)
    crop_x1, crop_y1, crop_x2, crop_y2 = handler._select_target_box_and_bounds(
        results=results,
        cursor_x=100,
        cursor_y=62,
        img_w=240,
        img_h=240,
        is_vertical=False,
    )
    assert crop_y1 >= 45
    assert crop_y2 <= 80


def test_suffix_walkback_extended_inflections() -> None:
    """
    Verifies backward morphological walkback across ています, てしまった, くない, and した.
    """
    handler = _make_lightweight_ocr_handler()

    cands_teiru = handler._extract_candidates_at_ratio("走っています", 0.85)
    assert cands_teiru[0] == "走る"

    cands_shimatta = handler._extract_candidates_at_ratio("見てしまった", 0.85)
    assert cands_shimatta[0] == "見る"

    cands_kunai = handler._extract_candidates_at_ratio("面白くない", 0.85)
    assert cands_kunai[0] == "面白い"

    cands_suru = handler._extract_candidates_at_ratio("勉強した", 0.85)
    assert cands_suru[0] == "勉強"
    assert "勉強する" in cands_suru


def test_screensnip_compound_word_candidate_priority() -> None:
    """
    Verifies that snipping a multi-token compound word prioritizes the full compound
    headword (e.g. 日本語能力) before constituent sub-tokens (日本語, 能力).
    """
    from PIL import Image

    handler = _make_lightweight_ocr_handler()
    handler.process_screensnip = lambda _img: "日本語能力"  # type: ignore[method-assign]

    dummy_img = Image.new("RGB", (60, 20), (255, 255, 255))
    detail = handler.process_screensnip_detailed(dummy_img)
    assert detail is not None
    assert detail["raw_text"] == "日本語能力"
    assert detail["primary_candidates"][0] == "日本語能力"
    assert "日本語" in detail["primary_candidates"]
    assert "能力" in detail["primary_candidates"]


def test_extract_candidates_snaps_off_punctuation_and_particles() -> None:
    """
    Verifies that hovering on quotation/punctuation marks or 1-char particle boundaries
    snaps cleanly to the adjacent content word instead of returning bare punctuation/particles.
    """
    handler = _make_lightweight_ocr_handler()

    # Cursor on opening quote 「 of 「魔法使い」
    quote_cands = handler._extract_candidates_at_ratio("「魔法使い」", 0.0)
    assert quote_cands
    assert any("魔法" in c for c in quote_cands)

    # Cursor on structural particle を in 魔法を使う
    particle_cands = handler._extract_candidates_at_ratio("魔法を使う", 0.45)
    assert particle_cands[0] in ("魔法", "使う")
    assert "魔法" in particle_cands
    assert "使う" in particle_cands


def test_select_target_box_expands_fragmented_short_boxes() -> None:
    """
    Verifies that short 1-character detector fragments expand along the reading axis
    while preserving narrow single-column width isolation.
    """
    handler = _make_lightweight_ocr_handler()
    results = [
        ([[40, 110], [66, 110], [66, 132], [40, 132]], "魔", 0.90),
    ]
    crop_x1, crop_y1, crop_x2, crop_y2 = handler._select_target_box_and_bounds(
        results=results,
        cursor_x=53,
        cursor_y=120,
        img_w=240,
        img_h=240,
        is_vertical=True,
    )
    assert (crop_x2 - crop_x1) < 40
    assert (crop_y2 - crop_y1) >= 120


def test_refine_hover_crop_and_ratio_trims_whitespace_and_centers_track() -> None:
    """
    Verifies that _refine_hover_crop_and_ratio trims trailing whitespace along the
    reading axis and computes ratio relative to the inked character span.
    """
    import numpy as np

    # White 120x200 image with a vertical dark text column at x in [50..72], y in [20..80]
    img = np.full((200, 120, 3), 255, dtype=np.uint8)
    img[20:80, 50:72] = 10

    bounds, ratio = OCRHandler._refine_hover_crop_and_ratio(
        image_np=img,
        crop_bounds=(40, 0, 82, 180),
        cursor_x=64,  # slightly off-center
        cursor_y=75,  # near bottom of the inked text (20..80), though y=75 is <0.5 of 0..180!
        is_vertical=True,
    )
    cx1, cy1, cx2, cy2 = bounds
    assert cx1 >= 44 and cx2 <= 78
    assert cy2 <= 95
    assert ratio > 0.85
