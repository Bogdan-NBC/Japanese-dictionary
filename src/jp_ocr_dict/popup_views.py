import re
import tkinter as tk
from collections.abc import Callable
from typing import Any

from settings_manager import settings

JAPANESE_CHAR_REGEX = re.compile(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff\u3400-\u4dbf]")
KANJI_CHAR_REGEX = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")

# Color palettes (VS Code inspired themes)
THEMES = {
    "dark": {
        "bg": "#1e1e1e",
        "fg": "#d4d4d4",
        "header_bg": "#2d2d2d",
        "blue_accent": "#569cd6",
        "green_accent": "#4ec9b0",
        "gray_text": "#808080",
        "light_blue": "#9cdcfe",
        "tag_bg": "#2a2d2e",
        "select_bg": "#264f78",
        "select_fg": "#ffffff",
        "badge_common_bg": "#0e632b",
        "badge_jlpt_bg": "#114e7a",
    },
    "light": {
        "bg": "#ffffff",
        "fg": "#1a1a1a",
        "header_bg": "#f3f3f3",
        "blue_accent": "#0066cc",
        "green_accent": "#008000",
        "gray_text": "#666666",
        "light_blue": "#005577",
        "tag_bg": "#f0f0f0",
        "select_bg": "#add8e6",
        "select_fg": "#000000",
        "badge_common_bg": "#2e7d32",
        "badge_jlpt_bg": "#1565c0",
    },
    "blue": {
        "bg": "#1b263b",
        "fg": "#e0e1dd",
        "header_bg": "#0d1b2a",
        "blue_accent": "#8ecae6",
        "green_accent": "#219ebc",
        "gray_text": "#a3b18a",
        "light_blue": "#a8dadc",
        "tag_bg": "#415a77",
        "select_bg": "#e9c46a",
        "select_fg": "#000000",
        "badge_common_bg": "#2a9d8f",
        "badge_jlpt_bg": "#e76f51",
    },
    "yellow": {
        "bg": "#fefae0",
        "fg": "#283618",
        "header_bg": "#dda15e",
        "blue_accent": "#bc6c25",
        "green_accent": "#606c38",
        "gray_text": "#8c7a6b",
        "light_blue": "#457b9d",
        "tag_bg": "#faedcd",
        "select_bg": "#c1121f",
        "select_fg": "#ffffff",
        "badge_common_bg": "#606c38",
        "badge_jlpt_bg": "#bc6c25",
    },
}

FONT_SIZES = {
    "small": {"base": 10, "title": 14, "kanji": 24, "reading": 11, "pos": 8, "meta": 9},
    "normal": {"base": 11, "title": 16, "kanji": 28, "reading": 12, "pos": 9, "meta": 10},
    "large": {"base": 13, "title": 19, "kanji": 34, "reading": 14, "pos": 11, "meta": 12},
}


def get_active_theme() -> dict[str, str]:
    """Returns the currently configured theme dictionary with dark fallback."""
    theme_name = settings.get("theme")
    if theme_name not in THEMES:
        theme_name = "dark"
    return THEMES[theme_name]


def setup_text_tags(text_widget: tk.Text) -> None:
    """Configures tag styles for the read-only Text widget to render rich text."""
    t = get_active_theme()

    fs_name = settings.get("font_size")
    if fs_name not in FONT_SIZES:
        fs_name = "normal"
    fs = FONT_SIZES[fs_name]

    text_widget.configure(
        bg=t["bg"],
        fg=t["fg"],
        insertbackground=t["fg"],
        selectbackground=t["select_bg"],
        selectforeground=t["select_fg"],
        font=("Segoe UI", fs["base"]),
        padx=12,
        pady=10,
        spacing1=3,
        spacing2=3,
        spacing3=3,
        borderwidth=0,
        highlightthickness=0,
    )

    text_widget.tag_configure(
        "title", font=("Segoe UI", fs["title"], "bold"), foreground=t["blue_accent"]
    )
    text_widget.tag_configure(
        "large_kanji", font=("MS Gothic", fs["kanji"]), foreground=t["blue_accent"]
    )
    text_widget.tag_configure(
        "reading", font=("Segoe UI", fs["reading"], "bold"), foreground=t["green_accent"]
    )
    text_widget.tag_configure(
        "pos", font=("Segoe UI", fs["pos"], "italic"), foreground=t["light_blue"]
    )
    text_widget.tag_configure("meaning", font=("Segoe UI", fs["base"]), foreground=t["fg"])
    text_widget.tag_configure("meta", font=("Segoe UI", fs["meta"]), foreground=t["gray_text"])
    text_widget.tag_configure(
        "meta_label", font=("Segoe UI", fs["meta"], "bold"), foreground=t["gray_text"]
    )
    text_widget.tag_configure(
        "badge_common",
        font=("Segoe UI", fs["pos"], "bold"),
        background=t["badge_common_bg"],
        foreground="#ffffff",
    )
    text_widget.tag_configure(
        "badge_jlpt",
        font=("Segoe UI", fs["pos"], "bold"),
        background=t["badge_jlpt_bg"],
        foreground="#ffffff",
    )
    text_widget.tag_configure("divider", font=("Segoe UI", fs["pos"]), foreground=t["gray_text"])
    text_widget.tag_configure(
        "token_chip",
        font=("Segoe UI", fs["base"], "underline"),
        background=t["tag_bg"],
        foreground=t["blue_accent"],
    )


def clear_and_enable(text_widget: tk.Text) -> None:
    text_widget.configure(state="normal")
    text_widget.delete("1.0", tk.END)


def disable_edit(text_widget: tk.Text) -> None:
    text_widget.configure(state="disabled")


def render_words_view(
    text_widget: tk.Text,
    word_info: dict[str, Any] | None,
    sentence_tokens: list[dict[str, Any]] | None = None,
    on_token_click: Callable[[list[str]], None] | None = None,
) -> None:
    """Renders the dictionary entry and optional clickable sentence tokens."""
    clear_and_enable(text_widget)
    t = get_active_theme()

    # Render interactive sentence bar when a phrase or inflected token was snipped
    show_sentence_bar = bool(
        sentence_tokens
        and (
            len(sentence_tokens) > 1
            or (word_info and sentence_tokens[0].get("surface") != word_info.get("slug"))
        )
    )
    if show_sentence_bar and sentence_tokens:
        active_keys = set()
        if word_info:
            for k in (word_info.get("query"), word_info.get("slug")):
                if k:
                    active_keys.add(k)

        text_widget.insert(tk.END, "Snipped: ", "meta_label")
        for idx, tok in enumerate(sentence_tokens):
            surface = tok["surface"]
            is_japanese = bool(JAPANESE_CHAR_REGEX.search(surface))
            if is_japanese and on_token_click:
                tag_name = f"tok_{idx}"
                is_content = bool(tok.get("is_content_word"))
                is_active = bool(
                    active_keys and (tok.get("base_form") in active_keys or surface in active_keys)
                )
                if is_active:
                    chip_bg = t["select_bg"]
                    chip_fg = t["select_fg"]
                    chip_underline = False
                elif is_content:
                    chip_bg = t["tag_bg"]
                    chip_fg = t["blue_accent"]
                    chip_underline = True
                else:
                    chip_bg = t["tag_bg"]
                    chip_fg = t["fg"]
                    chip_underline = False

                text_widget.tag_configure(
                    tag_name,
                    underline=chip_underline,
                    background=chip_bg,
                    foreground=chip_fg,
                )
                candidates = tok["candidates"]
                text_widget.tag_bind(
                    tag_name,
                    "<Button-1>",
                    lambda _e, c=candidates: on_token_click(c),
                )
                text_widget.tag_bind(
                    tag_name,
                    "<Enter>",
                    lambda _e: text_widget.config(cursor="hand2"),
                )
                text_widget.tag_bind(
                    tag_name,
                    "<Leave>",
                    lambda _e: text_widget.config(cursor=""),
                )
                text_widget.insert(tk.END, f" {surface} ", tag_name)
                text_widget.insert(tk.END, " ")
            else:
                text_widget.insert(tk.END, surface + " ", "meta")
        text_widget.insert(tk.END, "\n" + "—" * 34 + "\n", "divider")

    if not word_info:
        text_widget.insert(tk.END, "No definitions found.")
        disable_edit(text_widget)
        return

    slug = word_info.get("slug", "")
    text_widget.insert(tk.END, slug, "title")

    # Show alternate written kanji forms when slug is kana or differs from readings' kanji
    alt_words = list(
        dict.fromkeys(
            r.get("word", "")
            for r in word_info.get("readings", [])
            if r.get("word") and r.get("word") != slug
        )
    )
    if alt_words:
        text_widget.insert(tk.END, f" ({', '.join(alt_words[:2])})", "meta")

    text_widget.insert(tk.END, "  ")

    readings = [r["reading"] for r in word_info.get("readings", []) if r.get("reading")]
    if readings:
        text_widget.insert(tk.END, f"【{', '.join(dict.fromkeys(readings))}】", "reading")

    if settings.get("show_common_indicators") and word_info.get("is_common"):
        text_widget.insert(tk.END, "  ")
        text_widget.insert(tk.END, " Common ", "badge_common")

    if settings.get("show_jlpt"):
        for jlpt in word_info.get("jlpt", []):
            text_widget.insert(tk.END, "  ")
            text_widget.insert(tk.END, f" {jlpt} ", "badge_jlpt")

    text_widget.insert(tk.END, "\n\n")

    if settings.get("show_definitions"):
        senses = word_info.get("senses", [])
        for idx, sense in enumerate(senses):
            text_widget.insert(tk.END, f"{idx + 1}. ", "meta_label")

            pos_list = sense.get("pos", [])
            if pos_list:
                text_widget.insert(tk.END, f"[{', '.join(pos_list)}] ", "pos")

            meanings_str = ", ".join(sense.get("meanings", []))
            text_widget.insert(tk.END, meanings_str, "meaning")

            tags_list = sense.get("tags", [])
            if tags_list:
                text_widget.insert(tk.END, f" ({', '.join(tags_list)})", "meta")

            text_widget.insert(tk.END, "\n")
    else:
        text_widget.insert(tk.END, "(Definitions hidden in settings)\n", "meta")

    kanji_source = f"{slug}{word_info.get('query', '')}" + "".join(
        r.get("word", "") for r in word_info.get("readings", [])[:2]
    )
    kanjis = list(dict.fromkeys(KANJI_CHAR_REGEX.findall(kanji_source)))
    if kanjis:
        text_widget.insert(tk.END, "\n")
        text_widget.insert(tk.END, "—" * 32 + "\n", "divider")
        text_widget.insert(
            tk.END,
            f"Tip: Select the Kanji tab for stroke & grade details ({', '.join(kanjis)})",
            "meta",
        )

    disable_edit(text_widget)


def render_kanji_view(
    text_widget: tk.Text, kanji_list: list[dict[str, Any]] | None, loading: bool = False
) -> None:
    """Renders detailed information for a list of Kanji characters."""
    clear_and_enable(text_widget)
    if loading:
        text_widget.insert(tk.END, "Loading Kanji details...", "meta")
        disable_edit(text_widget)
        return

    if not kanji_list:
        text_widget.insert(tk.END, "No Kanji characters found in this word.")
        disable_edit(text_widget)
        return

    for idx, info in enumerate(kanji_list):
        if not info:
            continue

        if idx > 0:
            text_widget.insert(tk.END, "\n" + "—" * 30 + "\n\n", "divider")

        text_widget.insert(tk.END, info.get("kanji", "") + "  ", "large_kanji")

        meta_items = []
        if info.get("stroke_count"):
            meta_items.append(f"{info['stroke_count']} strokes")
        if info.get("grade"):
            meta_items.append(f"Grade {info['grade']}")
        if info.get("jlpt"):
            meta_items.append(info["jlpt"])
        if info.get("unicode"):
            meta_items.append(f"U+{info['unicode']}")

        text_widget.insert(tk.END, " | ".join(meta_items) + "\n", "meta_label")

        kun = info.get("kun_readings", [])
        if kun:
            text_widget.insert(tk.END, "  Kun: ", "meta_label")
            text_widget.insert(tk.END, ", ".join(kun) + "\n", "reading")

        on = info.get("on_readings", [])
        if on:
            text_widget.insert(tk.END, "  On:  ", "meta_label")
            text_widget.insert(tk.END, ", ".join(on) + "\n", "reading")

        names = info.get("name_readings", [])
        if names:
            text_widget.insert(tk.END, "  Nanori: ", "meta_label")
            text_widget.insert(tk.END, ", ".join(names) + "\n", "pos")

        meanings = info.get("meanings", [])
        if meanings:
            text_widget.insert(tk.END, "  Meanings: ", "meta_label")
            text_widget.insert(tk.END, ", ".join(meanings) + "\n", "meaning")

    disable_edit(text_widget)


def render_names_view(
    text_widget: tk.Text, names_list: list[dict[str, str]] | None, loading: bool = False
) -> None:
    """Renders scraped name records."""
    clear_and_enable(text_widget)
    if loading:
        text_widget.insert(tk.END, "Loading Names details...", "meta")
        disable_edit(text_widget)
        return

    if not names_list:
        text_widget.insert(tk.END, "No matching names found.")
        disable_edit(text_widget)
        return

    for idx, name in enumerate(names_list):
        if idx > 0:
            text_widget.insert(tk.END, "\n")

        text_widget.insert(tk.END, name.get("kanji", "") + " ", "title")
        text_widget.insert(tk.END, f"({name.get('reading', '')}) ", "reading")

        tags = name.get("tags", "")
        if tags:
            text_widget.insert(tk.END, f"[{tags}] ", "pos")

        meaning = name.get("meaning", "")
        if meaning:
            text_widget.insert(tk.END, f"- {meaning}", "meaning")

        text_widget.insert(tk.END, "\n")

    disable_edit(text_widget)
