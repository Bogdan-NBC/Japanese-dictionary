import contextlib
import logging
import os
import threading
import tkinter as tk
from typing import Any

from hover_ocr_window import HoverOCRWindow
from ocr_window import OCRWindow
from screen_snip_ocr_window import ScreenSnipOCRWindow
from settings_manager import settings
from settings_window import SettingsWindow

logger = logging.getLogger(__name__)

BG_DARK = "#181818"
CARD_BG = "#222222"
CARD_BORDER = "#333333"
TEXT_PRIMARY = "#f0f0f0"
TEXT_MUTED = "#a0a0a0"
ACCENT_BLUE = "#569cd6"
ACCENT_TEAL = "#4ec9b0"
INPUT_BG = "#1c1c1c"
INPUT_BORDER = "#444444"
BTN_PRIMARY = "#0e639c"
BTN_PRIMARY_HOVER = "#1177bb"
BTN_SECONDARY = "#2d2d2d"
BTN_SECONDARY_HOVER = "#3c3c3c"


class MainWindow:
    """
    The main launcher window of the Japanese Pop-up Dictionary application.
    Provides access to Hover OCR, Screen Snip OCR, Quick Lookup, and Options & Settings.
    Loads the heavy OCR neural networks asynchronously so the UI appears instantly.
    """

    def __init__(
        self,
        root: tk.Tk,
        first_handler: Any = None,
        second_handler: Any = None,
    ) -> None:
        self.root = root

        # Support both (root, jisho) and legacy (root, ocr, jisho) constructor signatures
        if second_handler is not None:
            self.ocr_handler = first_handler
            self.jisho_api_handler = second_handler
        else:
            self.jisho_api_handler = first_handler
            self.ocr_handler = None

        self.hover_ocr_window: HoverOCRWindow | None = None
        self.screen_snip_ocr_window: ScreenSnipOCRWindow | None = None
        self.settings_window: SettingsWindow | None = None
        self._quick_lookup_popup: OCRWindow | None = None
        self.original_x: int = 0
        self.original_y: int = 0
        self.snip_ready: bool = False
        self.hover_ready: bool = False
        self.snip_hotkey_registered: bool = False
        self._snip_hotkey_hook: Any = None
        self._hover_hotkey_hook: Any = None

        self.root.title("Japanese Pop-up Dictionary")
        self.root.geometry("360x325")
        self.root.resizable(False, False)
        self.root.configure(bg=BG_DARK)
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_app_exit)

        self.center_window(self.root)

        is_ready = self.ocr_handler is not None
        if is_ready:
            self.snip_ready = True
            self.hover_ready = True

        # Header
        header_frame = tk.Frame(self.root, bg=BG_DARK, padx=16, pady=10)
        header_frame.pack(fill=tk.X)

        tk.Label(
            header_frame,
            text="Japanese OCR Dictionary",
            bg=BG_DARK,
            fg=ACCENT_BLUE,
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")

        tk.Label(
            header_frame,
            text="Instant offline lookups for manga & light novels",
            bg=BG_DARK,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
        ).pack(anchor="w")

        # Main Actions Card
        card = tk.Frame(
            self.root,
            bg=CARD_BG,
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
            padx=14,
            pady=12,
        )
        card.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 8))

        snip_hk = str(settings.get("hotkey_toggle_snip") or "alt+s").upper()
        hover_hk = str(settings.get("hotkey_toggle_hover") or "alt+e").upper()

        self.screen_snip_ocr_button = tk.Button(
            card,
            text=f"Screen Snip OCR   [{snip_hk}]",
            bg=BTN_PRIMARY,
            fg="#ffffff",
            activebackground=BTN_PRIMARY_HOVER,
            activeforeground="#ffffff",
            disabledforeground="#777777",
            font=("Segoe UI", 10, "bold"),
            bd=0,
            pady=8,
            cursor="hand2",
            command=self.show_screen_snip_ocr_window,
            state="normal" if is_ready else "disabled",
        )
        self.screen_snip_ocr_button.pack(fill=tk.X, pady=(0, 7))

        self.hover_ocr_button = tk.Button(
            card,
            text=f"Hover OCR   [{hover_hk}]",
            bg=BTN_SECONDARY,
            fg=TEXT_PRIMARY,
            activebackground=BTN_SECONDARY_HOVER,
            activeforeground="#ffffff",
            disabledforeground="#666666",
            font=("Segoe UI", 10, "bold"),
            bd=0,
            pady=8,
            cursor="hand2",
            command=self.show_hover_ocr_window,
            state="normal" if is_ready else "disabled",
        )
        self.hover_ocr_button.pack(fill=tk.X, pady=(0, 7))

        self.settings_button = tk.Button(
            card,
            text="Options & Settings",
            bg=BTN_SECONDARY,
            fg=TEXT_PRIMARY,
            activebackground=BTN_SECONDARY_HOVER,
            activeforeground="#ffffff",
            font=("Segoe UI", 9),
            bd=0,
            pady=6,
            cursor="hand2",
            command=self.show_settings_window,
        )
        self.settings_button.pack(fill=tk.X, pady=(0, 10))

        # Quick Lookup Bar
        lookup_row = tk.Frame(card, bg=CARD_BG)
        lookup_row.pack(fill=tk.X)

        self.quick_lookup_entry = tk.Entry(
            lookup_row,
            bg=INPUT_BG,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            highlightbackground=INPUT_BORDER,
            highlightcolor="#007acc",
            highlightthickness=1,
            bd=0,
            font=("Segoe UI", 10),
        )
        self.quick_lookup_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=(0, 6))
        self.quick_lookup_entry.bind("<Return>", lambda _e: self.perform_quick_lookup())

        self.quick_lookup_btn = tk.Button(
            lookup_row,
            text="Look up",
            bg=BTN_SECONDARY,
            fg=ACCENT_TEAL,
            activebackground=BTN_SECONDARY_HOVER,
            activeforeground=ACCENT_TEAL,
            font=("Segoe UI", 9, "bold"),
            bd=0,
            padx=10,
            pady=5,
            cursor="hand2",
            command=self.perform_quick_lookup,
        )
        self.quick_lookup_btn.pack(side=tk.RIGHT)

        # Status Bar
        initial_status = "Ready" if is_ready else "Initializing OCR models..."
        self.status_label = tk.Label(
            self.root,
            text=initial_status,
            bg=BG_DARK,
            fg=ACCENT_TEAL if is_ready else TEXT_MUTED,
            font=("Segoe UI", 9, "italic"),
        )
        self.status_label.pack(pady=(0, 10))

        if is_ready:
            self._update_status_ready()
            self._register_global_hotkeys()
        else:
            threading.Thread(target=self._async_load_ocr, daemon=True).start()

    def _async_load_ocr(self) -> None:
        """Asynchronously loads the OCR models on a background thread in phases."""
        try:
            from ocr import OCRHandler

            handler = OCRHandler(
                on_snip_ready=lambda h: self.root.after(0, lambda: self._on_snip_ready(h)),
                on_all_ready=lambda h: self.root.after(0, lambda: self._on_all_ready(h)),
                defer_easyocr=True,
            )
            self.ocr_handler = handler
        except Exception as e:
            logger.error("Failed to initialize OCR in background: %s", e)
            if self.root.winfo_exists():
                self.root.after(0, lambda err=str(e): self._on_ocr_failed(err))

    def _on_snip_ready(self, handler: Any) -> None:
        self.ocr_handler = handler
        self.snip_ready = True
        self.screen_snip_ocr_button.config(state="normal")
        snip_hk = str(settings.get("hotkey_toggle_snip") or "alt+s").upper()
        self.status_label.config(
            text=f"Snip ready ({snip_hk})  •  Loading hover detector...",
            fg=ACCENT_TEAL,
        )
        self._register_global_hotkeys()

    def _on_all_ready(self, handler: Any) -> None:
        self.ocr_handler = handler
        self.hover_ready = True
        self.hover_ocr_button.config(state="normal")
        self._update_status_ready()
        self._register_global_hotkeys()

    def _unregister_launcher_hotkeys(self) -> None:
        try:
            import keyboard

            if self._snip_hotkey_hook:
                keyboard.remove_hotkey(self._snip_hotkey_hook)
                self._snip_hotkey_hook = None
            if self._hover_hotkey_hook:
                keyboard.remove_hotkey(self._hover_hotkey_hook)
                self._hover_hotkey_hook = None
        except Exception:
            pass
        self.snip_hotkey_registered = False

    def _register_launcher_snip_hotkey(self) -> None:
        """Backwards-compatible wrapper that registers launcher global hotkeys."""
        self._register_global_hotkeys()

    def _register_global_hotkeys(self) -> None:
        """Registers launcher hotkeys for any OCR mode whose dedicated window is not open."""
        try:
            import keyboard
        except Exception:
            return

        self._unregister_launcher_hotkeys()

        snip_window_open = bool(
            self.screen_snip_ocr_window and self.screen_snip_ocr_window.winfo_exists()
        )
        hover_window_open = bool(self.hover_ocr_window and self.hover_ocr_window.winfo_exists())

        if self.snip_ready and not snip_window_open:
            try:
                hk = settings.get("hotkey_toggle_snip") or "alt+s"
                self._snip_hotkey_hook = keyboard.add_hotkey(
                    hk, lambda: self.root.after(0, self.trigger_snip_from_hotkey)
                )
                self.snip_hotkey_registered = True
                logger.info("Global launcher snip hotkey registered: %s", hk)
            except Exception as e:
                logger.warning("Could not register launcher snip hotkey: %s", e)

        if self.hover_ready and not hover_window_open:
            try:
                hk = settings.get("hotkey_toggle_hover") or "alt+e"
                self._hover_hotkey_hook = keyboard.add_hotkey(
                    hk, lambda: self.root.after(0, self.trigger_hover_from_hotkey)
                )
                logger.info("Global launcher hover hotkey registered: %s", hk)
            except Exception as e:
                logger.warning("Could not register launcher hover hotkey: %s", e)

    def trigger_snip_from_hotkey(self) -> None:
        if not self.snip_ready or not self.ocr_handler:
            return
        if self.screen_snip_ocr_window is None or not self.screen_snip_ocr_window.winfo_exists():
            self.show_screen_snip_ocr_window()
        if self.screen_snip_ocr_window and self.screen_snip_ocr_window.winfo_exists():
            self.screen_snip_ocr_window.create_screen_canvas()

    def trigger_hover_from_hotkey(self) -> None:
        if not self.hover_ready or not self.ocr_handler:
            return
        if self.hover_ocr_window is None or not self.hover_ocr_window.winfo_exists():
            self.show_hover_ocr_window()
            if self.hover_ocr_window and self.hover_ocr_window.winfo_exists():
                self.hover_ocr_window.start_ocr_thread()
        elif self.hover_ocr_window.winfo_exists():
            self.hover_ocr_window.toggle_ocr()

    def perform_quick_lookup(self) -> None:
        """Looks up Japanese text typed or pasted in the Quick Lookup entry."""
        query = self.quick_lookup_entry.get().strip()
        if not query or not self.jisho_api_handler:
            return

        def _worker() -> None:
            tokens = None
            candidates = [query]
            if self.ocr_handler and hasattr(self.ocr_handler, "tokenize_sentence"):
                tokens = self.ocr_handler.tokenize_sentence(query)
                if len(tokens) == 1:
                    candidates = tokens[0]["candidates"] + (
                        [query] if query not in tokens[0]["candidates"] else []
                    )
                elif len(tokens) > 1:
                    seen: set[str] = set()
                    candidates = []
                    for c in ([query] if len(query) <= 10 else []) + [
                        cand
                        for tok in tokens
                        if tok["is_content_word"]
                        for cand in tok["candidates"]
                    ]:
                        if c not in seen:
                            seen.add(c)
                            candidates.append(c)

            word_info = self.jisho_api_handler.lookup_candidates(candidates)
            if not word_info:
                word_info = {
                    "query": query,
                    "slug": query,
                    "readings": [],
                    "is_common": False,
                    "jlpt": [],
                    "senses": [
                        {
                            "pos": ["Lookup"],
                            "meanings": ["No dictionary match found."],
                            "tags": [],
                        }
                    ],
                }

            def _display() -> None:
                if not self.root.winfo_exists():
                    return
                if self._quick_lookup_popup is None or not self._quick_lookup_popup.winfo_exists():
                    self._quick_lookup_popup = OCRWindow(self.root, self.jisho_api_handler)
                    self._quick_lookup_popup.withdraw()
                px = self.root.winfo_x() + self.root.winfo_width() + 10
                py = self.root.winfo_y()
                self._quick_lookup_popup.show_word_lookup(word_info, px, py, sentence_tokens=tokens)

            with contextlib.suppress(tk.TclError, RuntimeError):
                self.root.after(0, _display)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_ocr_ready(self, handler: Any) -> None:
        self.ocr_handler = handler
        self.snip_ready = True
        self.hover_ready = True
        self.hover_ocr_button.config(state="normal")
        self.screen_snip_ocr_button.config(state="normal")
        self._update_status_ready()
        self._register_global_hotkeys()

    def _update_status_ready(self) -> None:
        is_gpu = getattr(self.ocr_handler, "is_gpu", False)
        if is_gpu:
            try:
                import torch

                device_name = torch.cuda.get_device_name(0)
                short_name = (
                    device_name.replace("NVIDIA GeForce ", "")
                    .replace(" Laptop GPU", "")
                    .replace(" GPU", "")
                )
                mode = f"GPU: {short_name}"
            except Exception:
                mode = "CUDA GPU"
        else:
            mode = "CPU"

        self.status_label.config(
            text=f"● Ready ({mode})",
            fg=ACCENT_TEAL,
        )

    def _on_ocr_failed(self, error_msg: str) -> None:
        self.status_label.config(
            text="Error initializing OCR (see logs)",
            fg="#f48771",
        )

    def show_settings_window(self) -> None:
        """Opens the SettingsWindow (focusing if already open) and reloads hotkeys on save."""
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift()
            self.settings_window.focus_force()
            return
        self.settings_window = SettingsWindow(
            self.root, on_save_callback=self.reload_active_hotkeys
        )

    def reload_active_hotkeys(self) -> None:
        """Reloads global hotkeys and refreshes button shortcut labels across windows."""
        snip_hk = str(settings.get("hotkey_toggle_snip") or "alt+s").upper()
        hover_hk = str(settings.get("hotkey_toggle_hover") or "alt+e").upper()
        self.screen_snip_ocr_button.config(text=f"Screen Snip OCR   [{snip_hk}]")
        self.hover_ocr_button.config(text=f"Hover OCR   [{hover_hk}]")

        if self.hover_ocr_window and self.hover_ocr_window.winfo_exists():
            self.hover_ocr_window.register_hotkeys()
        if self.screen_snip_ocr_window and self.screen_snip_ocr_window.winfo_exists():
            self.screen_snip_ocr_window.register_hotkeys()
        self._register_global_hotkeys()

    def show_hover_ocr_window(self) -> None:
        if self.hover_ocr_window is None or not self.hover_ocr_window.winfo_exists():
            self._unregister_launcher_hotkeys()
            self.hover_ocr_window = HoverOCRWindow(
                self.root, self.ocr_handler, self.jisho_api_handler
            )
            self._register_global_hotkeys()
        self.show_window(self.hover_ocr_window)

    def show_screen_snip_ocr_window(self) -> None:
        if self.screen_snip_ocr_window is None or not self.screen_snip_ocr_window.winfo_exists():
            self._unregister_launcher_hotkeys()
            self.screen_snip_ocr_window = ScreenSnipOCRWindow(
                self.root, self.ocr_handler, self.jisho_api_handler
            )
            self._register_global_hotkeys()
        self.show_window(self.screen_snip_ocr_window)

    def show_window(self, window: tk.Toplevel) -> None:
        if self._quick_lookup_popup and self._quick_lookup_popup.winfo_exists():
            self._quick_lookup_popup.close_info_window()

        self.original_x = self.root.winfo_x()
        self.original_y = self.root.winfo_y()

        window.deiconify()
        window.geometry(f"+{self.original_x}+{self.original_y}")
        window.update_idletasks()

        self.root.withdraw()
        window.bind("<Destroy>", self.on_child_window_destroy)
        self.center_window(window)

    def on_child_window_destroy(self, event: tk.Event) -> None:
        if event.widget not in (self.hover_ocr_window, self.screen_snip_ocr_window):
            return
        if event.widget == self.hover_ocr_window:
            self.hover_ocr_window = None
        elif event.widget == self.screen_snip_ocr_window:
            self.screen_snip_ocr_window = None
        if self.root.winfo_exists():
            self.root.geometry(f"+{self.original_x}+{self.original_y}")
            self.root.after(0, self._register_global_hotkeys)

    def on_app_exit(self) -> None:
        """
        Performs an immediate, clean shutdown of the application:
        1. Releases all Windows low-level keyboard hooks (WH_KEYBOARD_LL) to eliminate OS-level keystroke lag.
        2. Shuts down background network and OCR worker pools.
        3. Closes all active child windows and terminates the process cleanly.
        """
        try:
            import keyboard

            keyboard.unhook_all()
        except Exception:
            pass

        try:
            if self.hover_ocr_window and self.hover_ocr_window.winfo_exists():
                self.hover_ocr_window.stop_ocr()
                self.hover_ocr_window.destroy()
        except Exception:
            pass

        try:
            if self.screen_snip_ocr_window and self.screen_snip_ocr_window.winfo_exists():
                self.screen_snip_ocr_window.exit_screenshot_mode()
                self.screen_snip_ocr_window.destroy()
        except Exception:
            pass

        try:
            if self.jisho_api_handler and hasattr(self.jisho_api_handler, "shutdown"):
                self.jisho_api_handler.shutdown()
        except Exception:
            pass

        try:
            if self.root.winfo_exists():
                self.root.destroy()
        except Exception:
            pass

        os._exit(0)

    @staticmethod
    def center_window(window: tk.Tk | tk.Toplevel) -> None:
        window.update_idletasks()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = int((screen_width / 2) - (window.winfo_width() / 2))
        y = int((screen_height / 2) - (window.winfo_height() / 2))
        window.geometry(f"+{x}+{y}")
