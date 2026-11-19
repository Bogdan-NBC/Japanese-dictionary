import contextlib
import logging
import threading
import time
import tkinter as tk
from typing import Any

import keyboard
import pyautogui
from ocr_window import BG_DARK, BTN_SECONDARY, BTN_SECONDARY_HOVER, CARD_BG, OCRWindow
from settings_manager import settings

logger = logging.getLogger(__name__)


class HoverOCRWindow(OCRWindow):
    def __init__(self, parent: tk.Tk, ocr_handler: Any, jisho_api_handler: Any) -> None:
        super().__init__(parent, jisho_api_handler=jisho_api_handler)
        self.title("Japanese Pop-up Dictionary — Hover OCR")
        self.geometry("340x215")

        self.update_idletasks()
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        x = int(parent_x + (parent_width / 2) - (self.winfo_width() / 2))
        y = int(parent_y + (parent_height / 2) - (self.winfo_height() / 2))
        self.geometry(f"+{x}+{y}")

        self.ocr_handler = ocr_handler
        self.running = False
        self.abort_ocr = False
        self.ocr_thread: threading.Thread | None = None

        tk.Label(
            self.card_frame,
            text="Hover OCR",
            bg=CARD_BG,
            fg="#569cd6",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")

        tk.Label(
            self.card_frame,
            text="Hover your cursor over Japanese text to translate.",
            bg=CARD_BG,
            fg="#a0a0a0",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(2, 10))

        btn_row = tk.Frame(self.card_frame, bg=CARD_BG)
        btn_row.pack(fill=tk.X, pady=(0, 8))

        self.start_ocr_button = tk.Button(
            btn_row,
            text="Start Scanning",
            bg="#0e639c",
            fg="#ffffff",
            activebackground="#1177bb",
            activeforeground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            bd=0,
            padx=14,
            pady=7,
            cursor="hand2",
            command=self.start_ocr_thread,
        )
        self.start_ocr_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.stop_ocr_button = tk.Button(
            btn_row,
            text="Stop",
            bg=BTN_SECONDARY,
            fg="#f0f0f0",
            activebackground=BTN_SECONDARY_HOVER,
            activeforeground="#ffffff",
            disabledforeground="#666666",
            font=("Segoe UI", 10),
            bd=0,
            padx=14,
            pady=7,
            cursor="hand2",
            state="disabled",
            command=self.stop_ocr,
        )
        self.stop_ocr_button.pack(side=tk.LEFT)

        hk = str(settings.get("hotkey_toggle_hover") or "alt+e").upper()
        self.hover_status_label = tk.Label(
            self.card_frame,
            text=f"Idle  •  Toggle shortcut: {hk}",
            bg=CARD_BG,
            fg="#a0a0a0",
            font=("Segoe UI", 9),
        )
        self.hover_status_label.pack(anchor="w")

        self.hotkey_hook = None
        self.register_hotkeys()

        self.loading_window: tk.Toplevel | None = None
        self.create_loading_window()
        if self.loading_window:
            self.loading_window.withdraw()

    def register_hotkeys(self) -> None:
        try:
            if self.hotkey_hook:
                keyboard.remove_hotkey(self.hotkey_hook)
                self.hotkey_hook = None
        except Exception:
            pass
        try:
            hk = settings.get("hotkey_toggle_hover")
            if hk:
                self.hotkey_hook = keyboard.add_hotkey(hk, lambda: self.after(0, self.toggle_ocr))
                logger.info("Registered global Hover toggle hotkey: %s", hk)
            self._refresh_status_label()
        except Exception as e:
            logger.error("Error registering hotkey: %s", e)

    def _refresh_status_label(self) -> None:
        if not hasattr(self, "hover_status_label") or not self.winfo_exists():
            return
        hk = str(settings.get("hotkey_toggle_hover") or "alt+e").upper()
        if self.running:
            self.hover_status_label.config(
                text=f"● Scanning active  •  Press {hk} to pause",
                fg="#4ec9b0",
            )
            self.start_ocr_button.config(state="disabled")
            self.stop_ocr_button.config(state="normal")
        else:
            self.hover_status_label.config(
                text=f"Idle  •  Toggle shortcut: {hk}",
                fg="#a0a0a0",
            )
            self.start_ocr_button.config(state="normal")
            self.stop_ocr_button.config(state="disabled")

    def destroy(self) -> None:
        self.running = False
        self.abort_ocr = True
        try:
            if self.hotkey_hook:
                keyboard.remove_hotkey(self.hotkey_hook)
                self.hotkey_hook = None
        except Exception:
            pass
        super().destroy()

    def go_back(self) -> None:
        self.stop_ocr()
        super().go_back()

    def toggle_ocr(self) -> None:
        if self.running:
            self.stop_ocr()
        else:
            self.start_ocr_thread()

    def start_ocr_thread(self) -> None:
        if not self.running and self.ocr_thread is None:
            self.running = True
            self.abort_ocr = False
            self.ocr_thread = threading.Thread(target=self.ocr_loop, daemon=True)
            self.ocr_thread.start()
            self._refresh_status_label()

    def stop_ocr(self) -> None:
        if self.running:
            self.running = False
            self.abort_ocr = True
            self.ocr_thread = None
            if self.ocr_handler:
                self.ocr_handler.last_word = None
            self._set_loading_visible(False)
            self._refresh_status_label()

    def _set_loading_visible(self, visible: bool, x: int = 0, y: int = 0) -> None:
        """Schedules loading indicator updates safely on the main Tkinter thread."""

        def _update() -> None:
            if not self.loading_window or not self.loading_window.winfo_exists():
                return
            if visible:
                self.loading_window.geometry(f"+{x + 12}+{y + 12}")
                self.loading_window.deiconify()
                self.loading_window.lift()
            else:
                self.loading_window.withdraw()

        with contextlib.suppress(RuntimeError, tk.TclError):
            self.after(0, _update)

    @staticmethod
    def _is_trigger_pressed() -> bool:
        tkey = str(settings.get("trigger_key") or "alt").lower()
        if tkey == "alt":
            return (
                keyboard.is_pressed("alt")
                or keyboard.is_pressed("left alt")
                or keyboard.is_pressed("right alt")
            )
        if tkey == "ctrl":
            return (
                keyboard.is_pressed("ctrl")
                or keyboard.is_pressed("left ctrl")
                or keyboard.is_pressed("right ctrl")
            )
        if tkey == "shift":
            return (
                keyboard.is_pressed("shift")
                or keyboard.is_pressed("left shift")
                or keyboard.is_pressed("right shift")
            )
        return keyboard.is_pressed(tkey)

    def ocr_loop(self) -> None:
        last_primary_word: str | None = None
        last_mouse_position: tuple[int, int] | None = None
        stationary_time = 0.0
        mouse_moved = False
        last_ocr_time = 0.0

        while self.running and not self.abort_ocr:
            try:
                mx, my = pyautogui.position()
                current_mouse_position = (mx, my)

                if self.is_pinned:
                    time.sleep(0.05)
                    continue

                rect = self.popup_rect
                if rect is None:
                    last_primary_word = None
                else:
                    wx, wy, w, h = rect
                    # Skip scanning if mouse is hovering inside the active popup
                    if (wx - 5) <= mx <= (wx + w + 5) and (wy - 5) <= my <= (wy + h + 5):
                        time.sleep(0.05)
                        continue

                # Trigger key check
                if settings.get("require_trigger_key") and not self._is_trigger_pressed():
                    if rect is not None and not self.is_pinned and not self.mouse_entered:
                        self.after(0, self.close_info_window)
                        last_primary_word = None
                    time.sleep(0.05)
                    continue

                # Auto-close popup if mouse moves far away
                if rect is not None and not self.is_pinned and not self.mouse_entered:
                    wx, wy, w, h = rect
                    dx = max(wx - mx, 0, mx - (wx + w))
                    dy = max(wy - my, 0, my - (wy + h))
                    if (dx * dx + dy * dy) ** 0.5 > 150:
                        self.after(0, self.close_info_window)
                        last_primary_word = None

                if current_mouse_position == last_mouse_position:
                    stationary_time += 0.05
                    if stationary_time >= 0.15 and mouse_moved:
                        current_time = time.time()
                        if current_time - last_ocr_time < 0.15:
                            time.sleep(0.05)
                            continue
                        last_ocr_time = current_time
                        mouse_moved = False

                        self._set_loading_visible(True, mx, my)
                        try:
                            if hasattr(self.ocr_handler, "process_screenshot_detailed"):
                                hover_result = self.ocr_handler.process_screenshot_detailed(mx, my)
                                candidates = hover_result["candidates"] if hover_result else None
                                tokens = hover_result["tokens"] if hover_result else None
                            else:
                                candidates = self.ocr_handler.process_screenshot(mx, my)
                                tokens = None

                            if candidates:
                                primary = candidates[0]
                                if primary != last_primary_word:
                                    last_primary_word = primary
                                    word_info = self.jisho_api_handler.lookup_candidates(candidates)
                                    if word_info:
                                        self.after(
                                            0,
                                            lambda w=word_info, x=mx, y=my, t=tokens: (
                                                self.show_word_lookup(w, x, y, sentence_tokens=t)
                                            ),
                                        )
                        except Exception as e:
                            logger.error("Hover OCR Logic Error: %s", e)
                        finally:
                            self._set_loading_visible(False)

                        stationary_time = 0.0
                else:
                    last_mouse_position = current_mouse_position
                    stationary_time = 0.0
                    mouse_moved = True

                time.sleep(0.05)

            except Exception as e:
                logger.error("Hover Thread Error: %s", e)
                break

    def create_loading_window(self, position: tuple[int, int] | None = None) -> None:
        x, y = position or (0, 0)
        self.loading_window = tk.Toplevel(self)
        self.loading_window.overrideredirect(True)
        self.loading_window.attributes("-topmost", True)
        self.loading_window.configure(
            bg=BG_DARK, highlightbackground="#4ec9b0", highlightthickness=1
        )
        self.loading_window.geometry(f"+{x + 10}+{y + 10}")
        label = tk.Label(
            self.loading_window,
            text=" Reading... ",
            font=("Segoe UI", 9, "bold"),
            bg="#222222",
            fg="#4ec9b0",
            padx=6,
            pady=3,
        )
        label.pack()
