from tkinter import ttk
from tkinter.font import Font

import tkinter as tk


class OCRWindow(tk.Toplevel):
    """
    A base class for OCR-related windows, providing common functionality like a "Back" button.

    Attributes:
        parent (tk.Tk): The parent window.
        info_window (tk.Toplevel): The pop-up window displaying word information (initially None).
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        self.geometry("300x150")

        back_button_frame = ttk.Frame(self)
        back_button_frame.pack(pady=10)

        back_button = ttk.Button(back_button_frame, text="Back", command=self.go_back)
        back_button.pack()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def go_back(self):
        """
        Closes the current OCR window and returns to the parent (main) window.
        """
        self.destroy()
        self.parent.deiconify()
        self.parent.geometry('+%d+%d' % (self.winfo_x(), self.winfo_y()))

    def on_closing(self):
        """
        Handles the window closing event, closing the entire application.
        """
        self.parent.destroy()

    def create_info_window(self, word_info, x, y):
        """
        Creates and displays a pop-up window with word information.

        Args:
            word_info (dict): A dictionary containing word information, including readings and meanings.
            x, y (int): The coordinates for positioning the window.
        """
        self.info_window = tk.Toplevel()
        self.info_window.title("Word Information")
        self.info_window.overrideredirect(True)

        font = Font(family="Courier New", size=12)

        readings_label = tk.Label(self.info_window, text="Readings: " + ", ".join(word_info['readings']))
        meanings_label = tk.Label(self.info_window, text="Meanings: " + ", ".join(word_info['meanings']))

        readings_label.pack(pady=5)
        meanings_label.pack(pady=5)

        self.info_window.configure(bg="light yellow", padx=10, pady=10, relief="solid", borderwidth=1)

        readings_label.config(font=font, bg="light yellow")
        meanings_label.config(font=font, bg="light yellow")

        self.info_window.geometry(f"+{x + 20}+{y + 20}")

        self.info_window.bind("<Leave>", self.on_mouse_leave)

    def on_mouse_leave(self, event):
        """
        Callback for when the mouse leaves the info window, closing it.
        """
        if self.info_window:
            self.info_window.destroy()
            self.info_window = None
