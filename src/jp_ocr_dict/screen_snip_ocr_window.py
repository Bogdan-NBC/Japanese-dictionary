import contextlib
import ctypes
import logging
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import BOTH, YES
from typing import Any

import keyboard
from ocr_window import BG_DARK, BTN_SECONDARY, BTN_SECONDARY_HOVER, CARD_BG, OCRWindow
from PIL import Image, ImageGrab
from settings_manager import settings

logger = logging.getLogger(__name__)


class ScreenSnipOCRWindow(OCRWindow):
    def __init__(self, parent: tk.Tk, ocr_handler: Any, jisho_api_handler: Any) -> None:
        super().__init__(parent, jisho_api_handler=jisho_api_handler)
        self.geometry("360x215")
        self.title("Japanese Pop-up Dictionary — Screen Snip")

        self.update_idletasks()
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        x = int(parent_x + (parent_width / 2) - (self.winfo_width() / 2))
        y = int(parent_y + (parent_height / 2) - (self.winfo_height() / 2))
        self.geometry(f"+{x}+{y}")

        self.ocr_handler = ocr_handler
        self.root = parent

        tk.Label(
            self.card_frame,
            text="Screen Snip OCR",
            bg=CARD_BG,
            fg="#569cd6",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")

        tk.Label(
            self.card_frame,
            text="Drag a box over any manga bubble or novel line.",
            bg=CARD_BG,
            fg="#a0a0a0",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(2, 12))

        self.take_snip_button = tk.Button(
            self.card_frame,
            text="Take Screen Snip",
            bg="#0e639c",
            fg="#ffffff",
            activebackground="#1177bb",
            activeforeground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            command=self.create_screen_canvas,
        )
        self.take_snip_button.pack(fill=tk.X, pady=(0, 8))

        hk = str(settings.get("hotkey_toggle_snip") or "alt+s").upper()
        self.snip_shortcut_label = tk.Label(
            self.card_frame,
            text=f"Global shortcut: {hk}  •  Esc to cancel",
            bg=CARD_BG,
            fg="#4ec9b0",
            font=("Segoe UI", 9),
        )
        self.snip_shortcut_label.pack(anchor="w")

        self.snip_surface: tk.Canvas | None = None
        self.start_x: int | None = None
        self.start_y: int | None = None
        self.current_x: int | None = None
        self.current_y: int | None = None
        self.rect_id: int | None = None
        self._is_snipping: bool = False
        self._capture_origin: tuple[int, int] = (0, 0)
        self._recognizing_pill: tk.Toplevel | None = None

        self.frozen_screenshot: Image.Image | None = None

        self.parent_screen = tk.Toplevel(self.root)
        self.parent_screen.withdraw()
        self.picture_frame = tk.Frame(self.parent_screen, bg="black")
        self.picture_frame.pack(fill=BOTH, expand=YES)

        self.hotkey_hook = None
        self.register_hotkeys()

    @staticmethod
    def _get_virtual_screen_bounds() -> tuple[int, int, int, int]:
        if sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                vx = int(user32.GetSystemMetrics(76))
                vy = int(user32.GetSystemMetrics(77))
                vw = int(user32.GetSystemMetrics(78))
                vh = int(user32.GetSystemMetrics(79))
                if vw > 0 and vh > 0:
                    return vx, vy, vw, vh
            except Exception:
                pass
        return 0, 0, 0, 0

    def register_hotkeys(self) -> None:
        try:
            if self.hotkey_hook:
                keyboard.remove_hotkey(self.hotkey_hook)
                self.hotkey_hook = None
        except Exception:
            pass
        try:
            hk = settings.get("hotkey_toggle_snip")
            if hk:
                self.hotkey_hook = keyboard.add_hotkey(
                    hk, lambda: self.after(0, self.create_screen_canvas)
                )
                logger.info("Registered global Snip hotkey: %s", hk)
            if hasattr(self, "snip_shortcut_label") and self.winfo_exists():
                hk_disp = str(hk or "alt+s").upper()
                self.snip_shortcut_label.config(
                    text=f"Global shortcut: {hk_disp}  •  Esc to cancel"
                )
        except Exception as e:
            logger.error("Error registering Snip hotkey: %s", e)

    def destroy(self) -> None:
        self._hide_recognizing_pill()
        try:
            if self.hotkey_hook:
                keyboard.remove_hotkey(self.hotkey_hook)
                self.hotkey_hook = None
        except Exception:
            pass
        try:
            if self.parent_screen and self.parent_screen.winfo_exists():
                self.parent_screen.destroy()
        except Exception:
            pass
        super().destroy()

    def create_screen_canvas(self) -> None:
        """
        Takes an instantaneous snapshot of the desktop first, then overlays
        a frozen selection canvas. This eliminates DPI scaling offsets and window flicker.
        """
        if self._is_snipping:
            return
        self._is_snipping = True
        self._hide_recognizing_pill()

        # Hide our own UI windows
        self.withdraw()
        self.root.withdraw()
        if self.info_window and self.info_window.winfo_exists():
            self.info_window.withdraw()
        self.update_idletasks()

        # Capture the entire screen while clean
        try:
            self.frozen_screenshot = ImageGrab.grab(all_screens=True)
        except Exception:
            self.frozen_screenshot = ImageGrab.grab()

        if self.snip_surface:
            self.snip_surface.destroy()

        self.snip_surface = tk.Canvas(
            self.picture_frame,
            cursor="cross",
            bg="black",
            highlightthickness=0,
        )
        self.snip_surface.pack(fill=BOTH, expand=YES)

        self.snip_surface.bind("<ButtonPress-1>", self.on_button_press)
        self.snip_surface.bind("<B1-Motion>", self.on_snip_drag)
        self.snip_surface.bind("<ButtonRelease-1>", self.on_button_release)
        self.parent_screen.bind("<Escape>", lambda _e: self.exit_screenshot_mode())

        vx, vy, vw, vh = self._get_virtual_screen_bounds()
        prim_w = self.parent_screen.winfo_screenwidth()
        prim_h = self.parent_screen.winfo_screenheight()
        use_virtual = vw > 0 and vh > 0 and (vx != 0 or vy != 0 or vw != prim_w or vh != prim_h)

        if use_virtual:
            self._capture_origin = (vx, vy)
            self.parent_screen.attributes("-fullscreen", False)
            self.parent_screen.overrideredirect(True)
            self.parent_screen.geometry(f"{vw}x{vh}+{vx}+{vy}")
        else:
            self._capture_origin = (0, 0)
            self.parent_screen.overrideredirect(False)
            self.parent_screen.attributes("-fullscreen", True)

        # Guidance banner centered on the primary screen
        try:
            cx = (prim_w // 2) - self._capture_origin[0]
            cy_top = max(16, 16 - self._capture_origin[1])
            self.snip_surface.create_rectangle(
                cx - 310, cy_top, cx + 310, cy_top + 38, fill="#181818", outline="#00ffff", width=2
            )
            self.snip_surface.create_text(
                cx,
                cy_top + 19,
                text="Select a word, phrase, or bubble to look up. Press Esc to cancel.",
                fill="#ffffff",
                font=("Segoe UI", 11, "bold"),
            )
        except Exception:
            pass

        self.parent_screen.attributes("-alpha", 0.28)
        self.parent_screen.lift()
        self.parent_screen.attributes("-topmost", True)
        self.parent_screen.deiconify()
        self.parent_screen.focus_force()

    def on_button_press(self, event: tk.Event) -> None:
        if not self.snip_surface:
            return
        self.start_x = event.x
        self.start_y = event.y
        self.current_x = event.x
        self.current_y = event.y
        if self.rect_id:
            self.snip_surface.delete(self.rect_id)
        self.rect_id = self.snip_surface.create_rectangle(
            event.x, event.y, event.x, event.y, outline="#00ffff", width=2
        )

    def on_snip_drag(self, event: tk.Event) -> None:
        if not self.snip_surface or self.start_x is None or self.start_y is None:
            return
        self.current_x = event.x
        self.current_y = event.y
        if self.rect_id:
            self.snip_surface.coords(
                self.rect_id, self.start_x, self.start_y, self.current_x, self.current_y
            )

    def on_button_release(self, _event: tk.Event) -> None:
        if (
            self.start_x is None
            or self.start_y is None
            or self.current_x is None
            or self.current_y is None
            or self.frozen_screenshot is None
            or not self.snip_surface
        ):
            self.exit_screenshot_mode()
            return

        # Logical canvas selection bounds
        x1 = min(self.start_x, self.current_x)
        y1 = min(self.start_y, self.current_y)
        x2 = max(self.start_x, self.current_x)
        y2 = max(self.start_y, self.current_y)

        # Map logical canvas coordinates to physical screenshot pixels
        canvas_w = max(1, self.snip_surface.winfo_width())
        canvas_h = max(1, self.snip_surface.winfo_height())
        img_w, img_h = self.frozen_screenshot.size

        scale_x = img_w / canvas_w
        scale_y = img_h / canvas_h

        crop_x1 = max(0, min(img_w - 1, int(round(x1 * scale_x))))
        crop_y1 = max(0, min(img_h - 1, int(round(y1 * scale_y))))
        crop_x2 = max(0, min(img_w, int(round(x2 * scale_x))))
        crop_y2 = max(0, min(img_h, int(round(y2 * scale_y))))

        width = crop_x2 - crop_x1
        height = crop_y2 - crop_y1

        popup_x = int(x1 + self._capture_origin[0])
        popup_y = int(y1 + self._capture_origin[1])

        self.exit_screenshot_mode()

        if width < 8 or height < 8:
            logger.info("Snip region too small (%dx%d), ignoring.", width, height)
            return

        # 1. Full page / giant window guard
        if (width > 450 and height > 450) or (width * height > 220000):
            logger.warning("Snip region too large (%dx%d), full page detected.", width, height)
            self.show_page_warning_window(
                popup_x,
                popup_y,
                title="Selection too large",
                message=(
                    "The selected region spans an entire page. MangaOCR is optimized\n"
                    "for single lines or dialogue bubbles (up to ~20 characters).\n\n"
                    "Please drag a smaller box around the specific sentence or word to look up."
                ),
            )
            return

        # 2. Intermediate Multi-Column Guard (e.g. 2, 3, 4 tall vertical columns)
        if width > 70 and height > 400:
            est_cols = max(2, int(round(width / 45.0)))
            logger.warning(
                "Multi-column snip detected (%dx%d, ~%d columns).", width, height, est_cols
            )
            self.show_page_warning_window(
                popup_x,
                popup_y,
                title=f"Multiple columns detected (~{est_cols} vertical lines)",
                message=(
                    f"The selection contains ~{est_cols} full vertical columns (~{est_cols * 35}+ characters).\n"
                    "Horizontal chunking across multiple columns scrambles sentence order.\n\n"
                    "Please select an individual column or phrase to look up."
                ),
            )
            return

        # 3. Intermediate Multi-Line Horizontal Guard
        if width > 400 and height > 250:
            logger.warning("Multi-line horizontal snip detected (%dx%d).", width, height)
            self.show_page_warning_window(
                popup_x,
                popup_y,
                title="Multi-line selection detected",
                message=(
                    "The selection contains a multi-line block of text.\n"
                    "Please drag across one or two lines to look up words."
                ),
            )
            return

        cropped_img = self.frozen_screenshot.crop((crop_x1, crop_y1, crop_x2, crop_y2))

        # Save debug screenshot to system temp when debug logging is enabled
        if logger.isEnabledFor(logging.DEBUG):
            try:
                import tempfile

                debug_path = Path(tempfile.gettempdir()) / "jp_ocr_debug_snip_latest.png"
                cropped_img.save(str(debug_path))
                logger.debug(
                    "Saved cropped snip to %s (%dx%d, scale=%.2f,%.2f)",
                    debug_path,
                    width,
                    height,
                    scale_x,
                    scale_y,
                )
            except Exception as e:
                logger.debug("Could not save debug snip: %s", e)

        self.process_snip(cropped_img, popup_x, popup_y)

    def exit_screenshot_mode(self) -> None:
        self._is_snipping = False
        if self.rect_id and self.snip_surface:
            self.snip_surface.delete(self.rect_id)
            self.rect_id = None
        if self.snip_surface:
            self.snip_surface.destroy()
            self.snip_surface = None
        self.parent_screen.withdraw()
        self.deiconify()
        self.start_x = None
        self.start_y = None
        self.current_x = None
        self.current_y = None

    def _show_recognizing_pill(self, x: int, y: int) -> None:
        self._hide_recognizing_pill()
        try:
            pill = tk.Toplevel(self)
            pill.overrideredirect(True)
            pill.attributes("-topmost", True)
            pill.configure(bg=BG_DARK, highlightbackground="#4ec9b0", highlightthickness=1)
            lbl = tk.Label(
                pill,
                text=" Recognizing... ",
                bg=CARD_BG,
                fg="#4ec9b0",
                font=("Segoe UI", 9, "bold"),
                padx=8,
                pady=4,
            )
            lbl.pack()
            pill.geometry(f"+{x + 12}+{y + 12}")
            self._recognizing_pill = pill
        except Exception:
            self._recognizing_pill = None

    def _hide_recognizing_pill(self) -> None:
        if self._recognizing_pill:
            try:
                if self._recognizing_pill.winfo_exists():
                    self._recognizing_pill.destroy()
            except Exception:
                pass
            self._recognizing_pill = None

    def process_snip(self, cropped_img: Image.Image, popup_x: int, popup_y: int) -> None:
        """Runs MangaOCR on the exact cropped bitmap and displays the interactive dictionary."""
        self._show_recognizing_pill(popup_x, popup_y)

        def worker() -> None:
            try:
                snip_result = self.ocr_handler.process_screensnip_detailed(cropped_img)

                if snip_result:
                    raw_text = snip_result["raw_text"]
                    candidates = snip_result["primary_candidates"]
                    tokens = snip_result["tokens"]
                    word_info = self.jisho_api_handler.lookup_candidates(candidates)

                    if not word_info:
                        word_info = {
                            "query": raw_text,
                            "slug": raw_text,
                            "readings": [],
                            "is_common": False,
                            "jlpt": [],
                            "senses": [
                                {
                                    "pos": ["Recognized Text"],
                                    "meanings": [
                                        "No exact dictionary match for the full selection. "
                                        "Click any word chip above to inspect individual words."
                                    ],
                                    "tags": [],
                                }
                            ],
                        }

                    def _show_result() -> None:
                        self._hide_recognizing_pill()
                        self.show_word_lookup(
                            word_info,
                            popup_x,
                            popup_y,
                            sentence_tokens=tokens,
                        )

                    self.after(0, _show_result)
                else:

                    def _show_empty() -> None:
                        self._hide_recognizing_pill()
                        self.show_no_result_window(popup_x, popup_y)

                    self.after(0, _show_empty)

            except Exception as e:
                logger.error("Error during Snip OCR: %s", e)
                with contextlib.suppress(tk.TclError, RuntimeError):
                    self.after(0, self._hide_recognizing_pill)

        threading.Thread(target=worker, daemon=True).start()

    def show_page_warning_window(
        self,
        x: int,
        y: int,
        title: str = "Selection too large",
        message: str | None = None,
    ) -> None:
        self.close_info_window()
        self.info_window = tk.Toplevel(self)
        self.info_window.title("Selection Guidance")
        self.info_window.overrideredirect(True)
        self.info_window.attributes("-topmost", True)
        self.info_window.configure(bg="#1e1e1e")

        frame = tk.Frame(
            self.info_window,
            bg="#1e1e1e",
            padx=16,
            pady=14,
            highlightthickness=1,
            highlightbackground="#007acc",
        )
        frame.pack(fill=BOTH, expand=YES)

        title_lbl = tk.Label(
            frame,
            text=title,
            bg="#1e1e1e",
            fg="#4ec9b0",
            font=("Segoe UI", 11, "bold"),
        )
        title_lbl.pack(anchor="w", pady=(0, 6))

        if message is None:
            message = (
                "The selected region spans an entire page. MangaOCR is optimized\n"
                "for single lines or dialogue bubbles (up to ~20 characters).\n\n"
                "Please drag a smaller box around the specific sentence or word to look up."
            )
        desc_lbl = tk.Label(
            frame,
            text=message,
            bg="#1e1e1e",
            fg="#cccccc",
            font=("Segoe UI", 9),
            justify="left",
        )
        desc_lbl.pack(anchor="w", pady=(0, 10))

        btn = tk.Button(
            frame,
            text="Dismiss",
            bg=BTN_SECONDARY,
            fg="#f0f0f0",
            activebackground=BTN_SECONDARY_HOVER,
            activeforeground="#ffffff",
            font=("Segoe UI", 9),
            bd=0,
            padx=12,
            pady=5,
            cursor="hand2",
            command=self.close_info_window,
        )
        btn.pack(anchor="e")

        v_left, v_top, v_right, v_bottom = self._get_screen_bounds_for_popup()
        target_x = max(v_left + 20, min(v_right - 480, x))
        target_y = max(v_top + 20, min(v_bottom - 200, y))

        self.info_window.geometry(f"+{target_x}+{target_y}")

    def show_no_result_window(self, x: int, y: int) -> None:
        self.close_info_window()
        self.info_window = tk.Toplevel(self)
        self.info_window.title("Info")
        self.info_window.overrideredirect(True)
        self.info_window.attributes("-topmost", True)
        self.info_window.configure(
            bg="#1e1e1e", highlightbackground="#333333", highlightthickness=1
        )
        message_label = tk.Label(
            self.info_window,
            text="No Japanese text recognized.\n(Select an individual line or word)",
            bg="#1e1e1e",
            fg="#d4d4d4",
            font=("Segoe UI", 10),
            padx=14,
            pady=10,
            justify="center",
        )
        message_label.pack()

        v_left, v_top, v_right, v_bottom = self._get_screen_bounds_for_popup()
        target_x = max(v_left + 20, min(v_right - 320, x + 20))
        target_y = max(v_top + 20, min(v_bottom - 100, y + 20))

        self.info_window.geometry(f"+{target_x}+{target_y}")
        self.info_window.after(3500, self.close_info_window)
