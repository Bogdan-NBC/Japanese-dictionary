import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from settings_manager import settings

# UI Theme Palette (Dark Mode Ergonomics)
BG_COLOR = "#181818"  # Window background
CARD_BG = "#222222"  # Group card background
CARD_BORDER = "#333333"  # Subtle card border
TEXT_PRIMARY = "#f0f0f0"  # Crisp readable white
TEXT_MUTED = "#a0a0a0"  # Subdued gray
ACCENT_BLUE = "#569cd6"  # Header blue
ACCENT_TEAL = "#4ec9b0"  # Section teal
INPUT_BG = "#1c1c1c"  # Dark combobox / entry field background
INPUT_BORDER = "#444444"  # Input border
FOCUS_BORDER = "#007acc"  # Input focus highlight
BTN_SAVE = "#0e639c"  # Primary Save button
BTN_SAVE_HOVER = "#1177bb"
BTN_CANCEL = "#383838"  # Secondary Cancel button
BTN_CANCEL_HOVER = "#484848"


class SettingsWindow(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Tk | tk.Toplevel,
        on_save_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.parent = parent
        self.on_save_callback = on_save_callback

        self.title("Options & Settings")
        self.geometry("480x640")
        self.minsize(440, 500)
        self.resizable(True, True)
        self.configure(bg=BG_COLOR)
        self.attributes("-topmost", True)

        style = ttk.Style()
        style.theme_use("clam")

        # Scrollbar styling
        style.configure(
            "Dark.Vertical.TScrollbar",
            gripcount=0,
            background="#2d2d2d",
            troughcolor=BG_COLOR,
            bordercolor=BG_COLOR,
            arrowcolor="#d4d4d4",
            lightcolor="#2d2d2d",
            darkcolor="#2d2d2d",
        )

        # Combobox styling: Fixes the white-on-light-gray issue in Tkinter's clam theme
        style.configure(
            "Dark.TCombobox",
            fieldbackground=INPUT_BG,
            background="#2d2d2d",
            foreground=TEXT_PRIMARY,
            bordercolor=INPUT_BORDER,
            darkcolor=INPUT_BG,
            lightcolor=INPUT_BG,
            arrowcolor=TEXT_PRIMARY,
            arrowsize=14,
            padding=4,
        )
        style.map(
            "Dark.TCombobox",
            fieldbackground=[
                ("readonly", INPUT_BG),
                ("disabled", "#141414"),
                ("focus", INPUT_BG),
            ],
            foreground=[
                ("readonly", TEXT_PRIMARY),
                ("disabled", "#666666"),
                ("focus", TEXT_PRIMARY),
            ],
            background=[
                ("readonly", "#2d2d2d"),
                ("active", "#383838"),
            ],
            arrowcolor=[
                ("readonly", TEXT_PRIMARY),
                ("disabled", "#555555"),
            ],
            selectbackground=[
                ("readonly", "#094771"),
            ],
            selectforeground=[
                ("readonly", "#ffffff"),
            ],
        )

        # Style the dropdown popdown listbox
        self.option_add("*TCombobox*Listbox.background", INPUT_BG)
        self.option_add("*TCombobox*Listbox.foreground", TEXT_PRIMARY)
        self.option_add("*TCombobox*Listbox.selectBackground", "#094771")
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.option_add("*TCombobox*Listbox.font", ("Segoe UI", 10))

        # Center settings window relative to parent
        self.update_idletasks()
        px = parent.winfo_x()
        py = parent.winfo_y()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x = int(px + (pw / 2) - (self.winfo_width() / 2))
        y = int(py + (ph / 2) - (self.winfo_height() / 2))
        self.geometry(f"+{x}+{y}")

        # Top Header
        title_label = tk.Label(
            self,
            text="Options and Settings",
            bg=BG_COLOR,
            fg=ACCENT_BLUE,
            font=("Segoe UI", 16, "bold"),
            pady=12,
        )
        title_label.pack(side=tk.TOP, fill=tk.X)

        # Bottom Action Bar (always pinned & visible regardless of scrolling)
        btn_frame = tk.Frame(self, bg=BG_COLOR, pady=10, padx=16)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X)

        save_btn = tk.Button(
            btn_frame,
            text="Save Settings",
            bg=BTN_SAVE,
            fg="#ffffff",
            activebackground=BTN_SAVE_HOVER,
            activeforeground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            bd=0,
            padx=20,
            pady=8,
            cursor="hand2",
            command=self.save_settings,
        )
        save_btn.pack(side=tk.RIGHT, padx=8)

        cancel_btn = tk.Button(
            btn_frame,
            text="Cancel",
            bg=BTN_CANCEL,
            fg="#ffffff",
            activebackground=BTN_CANCEL_HOVER,
            activeforeground="#ffffff",
            font=("Segoe UI", 10),
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            command=self.destroy,
        )
        cancel_btn.pack(side=tk.RIGHT, padx=4)

        # Middle Scrollable Container
        scroll_container = tk.Frame(self, bg=BG_COLOR)
        scroll_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            scroll_container,
            bg=BG_COLOR,
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(
            scroll_container,
            orient=tk.VERTICAL,
            style="Dark.Vertical.TScrollbar",
            command=self.canvas.yview,
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        container = tk.Frame(self.canvas, bg=BG_COLOR, padx=16)
        self.canvas_window = self.canvas.create_window((0, 0), window=container, anchor="nw")

        def _on_frame_configure(_event: tk.Event) -> None:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        def _on_canvas_configure(event: tk.Event) -> None:
            self.canvas.itemconfig(self.canvas_window, width=event.width)

        container.bind("<Configure>", _on_frame_configure)
        self.canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event: tk.Event) -> None:
            try:
                if self.winfo_exists():
                    self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except (tk.TclError, RuntimeError):
                pass

        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.bind(
            "<Destroy>",
            lambda e: self.unbind_all("<MouseWheel>") if e.widget == self else None,
        )

        # ----------------------------------------------------
        # SECTION 1: Popup Style
        # ----------------------------------------------------
        style_frame = tk.LabelFrame(
            container,
            text=" Popup Style ",
            bg=CARD_BG,
            fg=ACCENT_TEAL,
            font=("Segoe UI", 11, "bold"),
            bd=1,
            relief=tk.SOLID,
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
            padx=14,
            pady=10,
        )
        style_frame.pack(fill=tk.X, pady=8)

        tk.Label(
            style_frame, text="Theme:", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Segoe UI", 10)
        ).grid(row=0, column=0, sticky=tk.W, pady=6)
        self.theme_var = tk.StringVar(value=settings.get("theme"))
        theme_combo = ttk.Combobox(
            style_frame,
            textvariable=self.theme_var,
            values=["dark", "light", "blue", "yellow"],
            state="readonly",
            style="Dark.TCombobox",
            width=16,
        )
        theme_combo.grid(row=0, column=1, sticky=tk.W, padx=14, pady=6)

        tk.Label(
            style_frame,
            text="Font Size:",
            bg=CARD_BG,
            fg=TEXT_PRIMARY,
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, sticky=tk.W, pady=6)
        self.font_var = tk.StringVar(value=settings.get("font_size"))
        font_combo = ttk.Combobox(
            style_frame,
            textvariable=self.font_var,
            values=["small", "normal", "large"],
            state="readonly",
            style="Dark.TCombobox",
            width=16,
        )
        font_combo.grid(row=1, column=1, sticky=tk.W, padx=14, pady=6)

        # ----------------------------------------------------
        # SECTION 2: Hover OCR & Orientation
        # ----------------------------------------------------
        interact_frame = tk.LabelFrame(
            container,
            text=" OCR Interactivity & Layout ",
            bg=CARD_BG,
            fg=ACCENT_TEAL,
            font=("Segoe UI", 11, "bold"),
            bd=1,
            relief=tk.SOLID,
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
            padx=14,
            pady=10,
        )
        interact_frame.pack(fill=tk.X, pady=8)

        self.require_key_var = tk.BooleanVar(value=settings.get("require_trigger_key"))
        self.require_key_check = tk.Checkbutton(
            interact_frame,
            text="Require modifier key to trigger Hover",
            variable=self.require_key_var,
            bg=CARD_BG,
            fg=TEXT_PRIMARY,
            selectcolor=INPUT_BG,
            activebackground=CARD_BG,
            activeforeground=TEXT_PRIMARY,
            font=("Segoe UI", 10),
            command=self.toggle_trigger_key_state,
        )
        self.require_key_check.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=6)

        tk.Label(
            interact_frame,
            text="Modifier Key:",
            bg=CARD_BG,
            fg=TEXT_PRIMARY,
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, sticky=tk.W, pady=6)
        self.trigger_key_var = tk.StringVar(value=settings.get("trigger_key"))
        self.trigger_combo = ttk.Combobox(
            interact_frame,
            textvariable=self.trigger_key_var,
            values=["Alt", "Ctrl", "Shift"],
            state="readonly",
            style="Dark.TCombobox",
            width=16,
        )
        self.trigger_combo.grid(row=1, column=1, sticky=tk.W, padx=14, pady=6)

        tk.Label(
            interact_frame,
            text="Text Orientation:",
            bg=CARD_BG,
            fg=TEXT_PRIMARY,
            font=("Segoe UI", 10),
        ).grid(row=2, column=0, sticky=tk.W, pady=6)
        self.orientation_var = tk.StringVar(value=settings.get("ocr_orientation"))
        orientation_combo = ttk.Combobox(
            interact_frame,
            textvariable=self.orientation_var,
            values=["auto", "vertical", "horizontal"],
            state="readonly",
            style="Dark.TCombobox",
            width=16,
        )
        orientation_combo.grid(row=2, column=1, sticky=tk.W, padx=14, pady=6)

        self.toggle_trigger_key_state()

        # ----------------------------------------------------
        # SECTION 3: Global Hotkeys
        # ----------------------------------------------------
        hotkeys_frame = tk.LabelFrame(
            container,
            text=" Global Hotkeys ",
            bg=CARD_BG,
            fg=ACCENT_TEAL,
            font=("Segoe UI", 11, "bold"),
            bd=1,
            relief=tk.SOLID,
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
            padx=14,
            pady=10,
        )
        hotkeys_frame.pack(fill=tk.X, pady=8)

        tk.Label(
            hotkeys_frame,
            text="Toggle Hover OCR:",
            bg=CARD_BG,
            fg=TEXT_PRIMARY,
            font=("Segoe UI", 10),
        ).grid(row=0, column=0, sticky=tk.W, pady=6)
        self.hk_hover_entry = tk.Entry(
            hotkeys_frame,
            bg=INPUT_BG,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            highlightbackground=INPUT_BORDER,
            highlightcolor=FOCUS_BORDER,
            highlightthickness=1,
            bd=0,
            font=("Segoe UI", 10),
            width=18,
        )
        self.hk_hover_entry.grid(row=0, column=1, sticky=tk.W, padx=14, pady=6)
        self.hk_hover_entry.insert(0, settings.get("hotkey_toggle_hover"))

        tk.Label(
            hotkeys_frame,
            text="Toggle Snip OCR:",
            bg=CARD_BG,
            fg=TEXT_PRIMARY,
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, sticky=tk.W, pady=6)
        self.hk_snip_entry = tk.Entry(
            hotkeys_frame,
            bg=INPUT_BG,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            highlightbackground=INPUT_BORDER,
            highlightcolor=FOCUS_BORDER,
            highlightthickness=1,
            bd=0,
            font=("Segoe UI", 10),
            width=18,
        )
        self.hk_snip_entry.grid(row=1, column=1, sticky=tk.W, padx=14, pady=6)
        self.hk_snip_entry.insert(0, settings.get("hotkey_toggle_snip"))

        # ----------------------------------------------------
        # SECTION 4: Display Options
        # ----------------------------------------------------
        display_frame = tk.LabelFrame(
            container,
            text=" Display Elements ",
            bg=CARD_BG,
            fg=ACCENT_TEAL,
            font=("Segoe UI", 11, "bold"),
            bd=1,
            relief=tk.SOLID,
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
            padx=14,
            pady=10,
        )
        display_frame.pack(fill=tk.X, pady=8)

        self.show_stars_var = tk.BooleanVar(value=settings.get("show_common_indicators"))
        self.show_stars_check = tk.Checkbutton(
            display_frame,
            text="Show Common word tag",
            variable=self.show_stars_var,
            bg=CARD_BG,
            fg=TEXT_PRIMARY,
            selectcolor=INPUT_BG,
            activebackground=CARD_BG,
            activeforeground=TEXT_PRIMARY,
            font=("Segoe UI", 10),
        )
        self.show_stars_check.pack(anchor=tk.W, pady=3)

        self.show_jlpt_var = tk.BooleanVar(value=settings.get("show_jlpt"))
        self.show_jlpt_check = tk.Checkbutton(
            display_frame,
            text="Show JLPT level tag",
            variable=self.show_jlpt_var,
            bg=CARD_BG,
            fg=TEXT_PRIMARY,
            selectcolor=INPUT_BG,
            activebackground=CARD_BG,
            activeforeground=TEXT_PRIMARY,
            font=("Segoe UI", 10),
        )
        self.show_jlpt_check.pack(anchor=tk.W, pady=3)

        self.show_def_var = tk.BooleanVar(value=settings.get("show_definitions"))
        self.show_def_check = tk.Checkbutton(
            display_frame,
            text="Show dictionary definition text",
            variable=self.show_def_var,
            bg=CARD_BG,
            fg=TEXT_PRIMARY,
            selectcolor=INPUT_BG,
            activebackground=CARD_BG,
            activeforeground=TEXT_PRIMARY,
            font=("Segoe UI", 10),
        )
        self.show_def_check.pack(anchor=tk.W, pady=3)

    def toggle_trigger_key_state(self) -> None:
        if self.require_key_var.get():
            self.trigger_combo.configure(state="readonly")
        else:
            self.trigger_combo.configure(state="disabled")

    def save_settings(self) -> None:
        settings.set("theme", self.theme_var.get())
        settings.set("font_size", self.font_var.get())
        settings.set("require_trigger_key", self.require_key_var.get())
        settings.set("trigger_key", self.trigger_key_var.get())
        settings.set("ocr_orientation", self.orientation_var.get())
        settings.set("hotkey_toggle_hover", self.hk_hover_entry.get().strip().lower())
        settings.set("hotkey_toggle_snip", self.hk_snip_entry.get().strip().lower())
        settings.set("show_common_indicators", self.show_stars_var.get())
        settings.set("show_jlpt", self.show_jlpt_var.get())
        settings.set("show_definitions", self.show_def_var.get())

        if self.on_save_callback:
            self.on_save_callback()

        self.destroy()
