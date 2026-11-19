import contextlib
import ctypes
import sys
import threading
import tkinter as tk
from tkinter import ttk
from typing import Any

from popup_views import (
    get_active_theme,
    render_kanji_view,
    render_names_view,
    render_words_view,
    setup_text_tags,
)

BG_DARK = "#181818"
CARD_BG = "#222222"
CARD_BORDER = "#333333"
BTN_SECONDARY = "#383838"
BTN_SECONDARY_HOVER = "#484848"


class OCRWindow(tk.Toplevel):
    """
    Base class for OCR windows providing the themed, tabbed pop-up dictionary
    with instant word rendering and asynchronous background loading for Kanji/Names.
    """

    POPUP_WIDTH = 480
    POPUP_HEIGHT = 350

    def __init__(self, parent: tk.Tk, jisho_api_handler: Any = None) -> None:
        super().__init__(parent)
        self.parent = parent
        self.jisho_api_handler = jisho_api_handler
        self.attributes("-topmost", True)
        self.configure(bg=BG_DARK)

        self.info_window: tk.Toplevel | None = None
        self.is_pinned: bool = False
        self.mouse_entered: bool = False
        self.active_tab: str = "words"

        # Thread-safe geometry snapshot (x, y, width, height) read by hover thread
        self.popup_rect: tuple[int, int, int, int] | None = None

        # Current data caches for active popup
        self.current_word_info: dict[str, Any] | None = None
        self.current_kanji_list: list[dict[str, Any]] | None = None
        self.current_names_list: list[dict[str, str]] | None = None
        self.current_sentence_tokens: list[dict[str, Any]] | None = None
        self._kanji_loading: bool = False
        self._names_loading: bool = False
        self._lookup_generation: int = 0
        self.drag_start_x: int = 0
        self.drag_start_y: int = 0

        self.geometry("340x200")
        self.resizable(False, False)

        self.card_frame = tk.Frame(
            self,
            bg=CARD_BG,
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
            padx=16,
            pady=12,
        )
        self.card_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 6))

        back_button_frame = tk.Frame(self, bg=BG_DARK)
        back_button_frame.pack(fill=tk.X, padx=12, pady=(0, 10))

        self.back_button = tk.Button(
            back_button_frame,
            text="← Back",
            bg=BTN_SECONDARY,
            fg="#f0f0f0",
            activebackground=BTN_SECONDARY_HOVER,
            activeforeground="#ffffff",
            font=("Segoe UI", 9),
            bd=0,
            padx=12,
            pady=5,
            cursor="hand2",
            command=self.go_back,
        )
        self.back_button.pack(side=tk.RIGHT)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _get_screen_bounds_for_popup(self) -> tuple[int, int, int, int]:
        """Returns (left, top, right, bottom) across all displays on Windows."""
        if sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                vx = int(user32.GetSystemMetrics(76))
                vy = int(user32.GetSystemMetrics(77))
                vw = int(user32.GetSystemMetrics(78))
                vh = int(user32.GetSystemMetrics(79))
                if vw > 0 and vh > 0:
                    return vx, vy, vx + vw, vy + vh
            except Exception:
                pass
        return 0, 0, self.winfo_screenwidth(), self.winfo_screenheight()

    def go_back(self) -> None:
        self.close_info_window()
        try:
            gx, gy = self.winfo_x(), self.winfo_y()
        except Exception:
            gx, gy = 0, 0
        self.destroy()
        if self.parent and self.parent.winfo_exists():
            self.parent.deiconify()
            if gx != 0 or gy != 0:
                self.parent.geometry(f"+{gx}+{gy}")

    def on_closing(self) -> None:
        if hasattr(self.parent, "on_app_exit"):
            self.parent.on_app_exit()
        else:
            self.parent.destroy()

    def show_word_lookup(
        self,
        word_info: dict[str, Any],
        x: int,
        y: int,
        sentence_tokens: list[dict[str, Any]] | None = None,
    ) -> None:
        """
        Immediately displays the popup with `word_info` and asynchronously
        fetches Kanji and Names in the background without blocking the UI.
        """
        self._lookup_generation += 1
        current_gen = self._lookup_generation

        self.current_word_info = word_info
        self.current_kanji_list = None
        self.current_names_list = None
        if sentence_tokens is not None:
            self.current_sentence_tokens = sentence_tokens

        slug = word_info.get("slug", "") or word_info.get("query", "")
        kanji_source = f"{slug}{word_info.get('query', '')}" + "".join(
            r.get("word", "") for r in word_info.get("readings", [])[:2]
        )
        has_kanji = bool(
            self.jisho_api_handler and self.jisho_api_handler.extract_ordered_kanji(kanji_source)
        )

        self._kanji_loading = has_kanji
        self._names_loading = bool(self.jisho_api_handler and slug)

        self._render_or_update_popup(x, y)

        if self.jisho_api_handler and (has_kanji or slug):
            threading.Thread(
                target=self._background_fetch_extras,
                args=(kanji_source, slug, has_kanji, current_gen),
                daemon=True,
            ).start()

    def _background_fetch_extras(
        self, kanji_source: str, slug: str, has_kanji: bool, generation: int
    ) -> None:
        if has_kanji:
            kanji_list = self.jisho_api_handler.fetch_kanji_list(kanji_source)

            def _apply_kanji() -> None:
                if generation != self._lookup_generation:
                    return
                self.current_kanji_list = kanji_list
                self._kanji_loading = False
                if (
                    self.info_window
                    and self.info_window.winfo_exists()
                    and self.active_tab == "kanji"
                ):
                    self.refresh_active_tab()

            try:
                self.after(0, _apply_kanji)
            except (tk.TclError, RuntimeError):
                return

        if slug:
            names_list = self.jisho_api_handler.scrape_names_info(slug)

            def _apply_names() -> None:
                if generation != self._lookup_generation:
                    return
                self.current_names_list = names_list
                self._names_loading = False
                if (
                    self.info_window
                    and self.info_window.winfo_exists()
                    and self.active_tab == "names"
                ):
                    self.refresh_active_tab()

            with contextlib.suppress(tk.TclError, RuntimeError):
                self.after(0, _apply_names)

    def _on_sentence_token_clicked(self, candidates: list[str]) -> None:
        """Handles clicking a word chip inside the Snipped Sentence Bar."""
        if not self.jisho_api_handler:
            return

        def _worker() -> None:
            word_info = self.jisho_api_handler.lookup_candidates(candidates)
            if word_info and self.info_window and self.info_window.winfo_exists():
                rect = self.popup_rect or (100, 100, self.POPUP_WIDTH, self.POPUP_HEIGHT)
                with contextlib.suppress(tk.TclError, RuntimeError):
                    self.after(
                        0,
                        lambda: self.show_word_lookup(
                            word_info,
                            rect[0],
                            rect[1],
                            sentence_tokens=self.current_sentence_tokens,
                        ),
                    )

        threading.Thread(target=_worker, daemon=True).start()

    def create_info_window(
        self,
        word_info: dict[str, Any],
        kanji_list: list[dict[str, Any]] | None,
        names_list: list[dict[str, str]] | None,
        x: int,
        y: int,
    ) -> None:
        """Backwards-compatible entry point if Kanji and Names were pre-fetched."""
        self.current_word_info = word_info
        self.current_kanji_list = kanji_list
        self.current_names_list = names_list
        self._kanji_loading = False
        self._names_loading = False
        self._render_or_update_popup(x, y)

    def _apply_popup_theme(self) -> None:
        """Applies current theme colors and typography to the popup window."""
        if not self.info_window or not self.info_window.winfo_exists():
            return
        t = get_active_theme()
        self.info_window.configure(
            bg=t["bg"], highlightbackground=t["header_bg"], highlightthickness=1
        )
        self._header_bar.configure(bg=t["header_bg"])
        self._content_frame.configure(bg=t["bg"])
        self._close_btn.configure(bg=t["header_bg"], fg=t["fg"])
        self.copy_btn.configure(
            bg=t["header_bg"], fg=t["fg"], activebackground=t["tag_bg"], activeforeground=t["fg"]
        )
        if self.is_pinned:
            self.pin_btn.configure(bg=t["blue_accent"], fg="#ffffff")
        else:
            self.pin_btn.configure(
                bg=t["header_bg"],
                fg=t["fg"],
                activebackground=t["tag_bg"],
                activeforeground=t["fg"],
            )
        scrollbar_style = ttk.Style()
        scrollbar_style.theme_use("clam")
        scrollbar_style.configure(
            "Popup.Vertical.TScrollbar",
            gripcount=0,
            background=t["tag_bg"],
            troughcolor=t["bg"],
            bordercolor=t["bg"],
            arrowcolor=t["fg"],
            lightcolor=t["tag_bg"],
            darkcolor=t["tag_bg"],
        )
        setup_text_tags(self.info_text)

    def _render_or_update_popup(self, x: int, y: int) -> None:
        v_left, v_top, v_right, v_bottom = self._get_screen_bounds_for_popup()
        popup_width = self.POPUP_WIDTH
        popup_height = self.POPUP_HEIGHT

        target_x = x + 20
        target_y = y + 20

        if target_x + popup_width > v_right:
            target_x = x - popup_width - 20
        if target_y + popup_height > v_bottom:
            target_y = y - popup_height - 20

        target_x = int(max(v_left, min(v_right - popup_width, target_x)))
        target_y = int(max(v_top, min(v_bottom - popup_height, target_y)))

        if self.info_window and self.info_window.winfo_exists():
            self.info_window.deiconify()
            if not self.is_pinned:
                self.info_window.geometry(f"+{target_x}+{target_y}")
                self.popup_rect = (target_x, target_y, popup_width, popup_height)
            self._apply_popup_theme()
            self.refresh_active_tab()
            self.info_window.attributes("-topmost", True)
            self.info_window.lift()
            return

        t = get_active_theme()

        self.info_window = tk.Toplevel(self)
        self.info_window.overrideredirect(True)
        self.info_window.attributes("-topmost", True)
        self.info_window.geometry(f"{popup_width}x{popup_height}+{target_x}+{target_y}")
        self.info_window.configure(
            bg=t["bg"], highlightbackground=t["header_bg"], highlightthickness=1
        )
        self.popup_rect = (target_x, target_y, popup_width, popup_height)

        scrollbar_style = ttk.Style()
        scrollbar_style.theme_use("clam")
        scrollbar_style.configure(
            "Popup.Vertical.TScrollbar",
            gripcount=0,
            background=t["tag_bg"],
            troughcolor=t["bg"],
            bordercolor=t["bg"],
            arrowcolor=t["fg"],
            lightcolor=t["tag_bg"],
            darkcolor=t["tag_bg"],
        )

        self._header_bar = tk.Frame(self.info_window, bg=t["header_bg"], height=34)
        self._header_bar.pack(fill=tk.X, side=tk.TOP)
        self._header_bar.pack_propagate(False)

        self.words_tab = tk.Button(
            self._header_bar,
            text="Words",
            bg=t["header_bg"],
            fg=t["gray_text"],
            activebackground=t["bg"],
            activeforeground=t["fg"],
            bd=0,
            font=("Segoe UI", 10, "bold"),
            padx=12,
            cursor="hand2",
            command=lambda: self.switch_tab("words"),
        )
        self.words_tab.pack(side=tk.LEFT, fill=tk.Y)

        self.kanji_tab = tk.Button(
            self._header_bar,
            text="Kanji",
            bg=t["header_bg"],
            fg=t["gray_text"],
            activebackground=t["bg"],
            activeforeground=t["fg"],
            bd=0,
            font=("Segoe UI", 10, "bold"),
            padx=12,
            cursor="hand2",
            command=lambda: self.switch_tab("kanji"),
        )
        self.kanji_tab.pack(side=tk.LEFT, fill=tk.Y)

        self.names_tab = tk.Button(
            self._header_bar,
            text="Names",
            bg=t["header_bg"],
            fg=t["gray_text"],
            activebackground=t["bg"],
            activeforeground=t["fg"],
            bd=0,
            font=("Segoe UI", 10, "bold"),
            padx=12,
            cursor="hand2",
            command=lambda: self.switch_tab("names"),
        )
        self.names_tab.pack(side=tk.LEFT, fill=tk.Y)

        self._close_btn = tk.Button(
            self._header_bar,
            text="✕",
            bg=t["header_bg"],
            fg=t["fg"],
            activebackground="#e81123",
            activeforeground="#ffffff",
            bd=0,
            font=("Segoe UI", 10, "bold"),
            width=3,
            cursor="hand2",
            command=self.close_info_window,
        )
        self._close_btn.pack(side=tk.RIGHT, fill=tk.Y)

        self.pin_btn = tk.Button(
            self._header_bar,
            text="Pin",
            bg=t["header_bg"],
            fg=t["fg"],
            activebackground=t["tag_bg"],
            activeforeground=t["fg"],
            bd=0,
            font=("Segoe UI", 9, "bold"),
            padx=8,
            cursor="hand2",
            command=self.toggle_pin,
        )
        self.pin_btn.pack(side=tk.RIGHT, fill=tk.Y)

        self.copy_btn = tk.Button(
            self._header_bar,
            text="Copy",
            bg=t["header_bg"],
            fg=t["fg"],
            activebackground=t["tag_bg"],
            activeforeground=t["fg"],
            bd=0,
            font=("Segoe UI", 9, "bold"),
            padx=8,
            cursor="hand2",
            command=self.copy_current_entry,
        )
        self.copy_btn.pack(side=tk.RIGHT, fill=tk.Y)

        self._header_bar.bind("<Button-1>", self.start_drag)
        self._header_bar.bind("<B1-Motion>", self.drag_window)

        self._content_frame = tk.Frame(self.info_window, bg=t["bg"])
        self._content_frame.pack(fill=tk.BOTH, expand=True)

        self.info_text = tk.Text(self._content_frame, wrap=tk.WORD)
        self.info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        setup_text_tags(self.info_text)

        scrollbar = ttk.Scrollbar(
            self._content_frame,
            orient=tk.VERTICAL,
            style="Popup.Vertical.TScrollbar",
            command=self.info_text.yview,
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.info_text.configure(yscrollcommand=scrollbar.set)

        def _on_popup_mousewheel(event: tk.Event) -> str:
            if self.info_text and self.info_text.winfo_exists():
                self.info_text.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        self.info_window.bind("<MouseWheel>", _on_popup_mousewheel)
        self.info_text.bind("<MouseWheel>", _on_popup_mousewheel)

        self.mouse_entered = False
        self.info_window.bind("<Enter>", self.on_mouse_enter)
        self.info_window.bind("<Leave>", self.on_mouse_leave)

        self.switch_tab(self.active_tab)

    def copy_current_entry(self) -> None:
        """Copies the currently displayed word, reading, and primary definitions to clipboard."""
        if not self.info_window or not self.info_window.winfo_exists():
            return
        word_info = self.current_word_info
        if not word_info:
            return

        slug = word_info.get("slug", "")
        readings = list(
            dict.fromkeys(r["reading"] for r in word_info.get("readings", []) if r.get("reading"))
        )
        meanings = [
            ", ".join(s.get("meanings", []))
            for s in word_info.get("senses", [])[:3]
            if s.get("meanings")
        ]
        summary = slug
        if readings:
            summary += f"【{', '.join(readings[:2])}】"
        if meanings:
            summary += f" — {'; '.join(meanings)}"
        if self.current_sentence_tokens and len(self.current_sentence_tokens) > 1:
            sentence = "".join(tok["surface"] for tok in self.current_sentence_tokens)
            summary += f"\n{sentence}"

        try:
            self.info_window.clipboard_clear()
            self.info_window.clipboard_append(summary)
            t = get_active_theme()
            self.copy_btn.configure(text="Copied!", fg=t["green_accent"])
            self.after(
                1200,
                lambda: (
                    self.copy_btn.configure(text="Copy", fg=get_active_theme()["fg"])
                    if self.info_window and self.info_window.winfo_exists()
                    else None
                ),
            )
        except Exception:
            pass

    def start_drag(self, event: tk.Event) -> None:
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def drag_window(self, event: tk.Event) -> None:
        if not self.info_window:
            return
        x = self.info_window.winfo_x() + event.x - self.drag_start_x
        y = self.info_window.winfo_y() + event.y - self.drag_start_y
        self.info_window.geometry(f"+{x}+{y}")
        self.popup_rect = (x, y, self.POPUP_WIDTH, self.POPUP_HEIGHT)

    def switch_tab(self, tab_name: str) -> None:
        self.active_tab = tab_name
        self.refresh_active_tab()

    def refresh_active_tab(self) -> None:
        if not self.info_window or not self.info_window.winfo_exists():
            return

        t = get_active_theme()

        tabs = {"words": self.words_tab, "kanji": self.kanji_tab, "names": self.names_tab}
        for name, button in tabs.items():
            if name == self.active_tab:
                button.configure(bg=t["bg"], fg=t["fg"])
            else:
                button.configure(bg=t["header_bg"], fg=t["gray_text"])

        if self.active_tab == "words":
            render_words_view(
                self.info_text,
                self.current_word_info,
                sentence_tokens=self.current_sentence_tokens,
                on_token_click=self._on_sentence_token_clicked,
            )
        elif self.active_tab == "kanji":
            render_kanji_view(self.info_text, self.current_kanji_list, loading=self._kanji_loading)
        elif self.active_tab == "names":
            render_names_view(self.info_text, self.current_names_list, loading=self._names_loading)

    def toggle_pin(self) -> None:
        t = get_active_theme()

        self.is_pinned = not self.is_pinned
        if self.is_pinned:
            self.pin_btn.configure(bg=t["blue_accent"], fg="#ffffff")
        else:
            self.pin_btn.configure(bg=t["header_bg"], fg=t["fg"])

    def on_mouse_enter(self, _event: tk.Event) -> None:
        self.mouse_entered = True

    def close_info_window(self) -> None:
        if self.info_window:
            self.info_window.destroy()
            self.info_window = None
        self.popup_rect = None
        self.is_pinned = False
        self.mouse_entered = False
        self.current_sentence_tokens = None
        if hasattr(self, "ocr_handler") and self.ocr_handler:
            self.ocr_handler.last_word = None

    def on_mouse_leave(self, _event: tk.Event) -> None:
        if self.is_pinned or not self.info_window:
            return

        if self.mouse_entered:
            x, y = self.info_window.winfo_pointerxy()
            wx = self.info_window.winfo_rootx()
            wy = self.info_window.winfo_rooty()
            w = self.info_window.winfo_width()
            h = self.info_window.winfo_height()

            if not (wx <= x <= wx + w and wy <= y <= wy + h):
                self.close_info_window()
