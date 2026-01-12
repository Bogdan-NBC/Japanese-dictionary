from tkinter import ttk

from hover_ocr_window import HoverOCRWindow
from screen_snip_ocr_window import ScreenSnipOCRWindow


class MainWindow:
    """
    The main window of the Japanese Pop-up Dictionary application.

    This window provides options to choose between Hover OCR and Screen Snip OCR modes.

    Attributes:
        root (tk.Tk): The root Tkinter window.
        hover_ocr_window (HoverOCRWindow): The window for Hover OCR mode (initially None).
        screen_snip_ocr_window (ScreenSnipOCRWindow): The window for Screen Snip OCR mode (initially None).
        ocr_handler (OCRHandler): Handles OCR processing.
        jisho_api_handler (JishoAPIHandler): Fetches word information from the Jisho API.
        original_x, original_y (int): Store the original position of the main window for repositioning.
    """

    def __init__(self, root, ocr_handler, jisho_api_handler):
        """
        Initializes the MainWindow.

        Args:
            root (tk.Tk): The root Tkinter window.
            ocr_handler (OCRHandler): Handles OCR processing.
            jisho_api_handler (JishoAPIHandler): Fetches word information from the Jisho API.
        """
        self.root = root
        self.root.title("Japanese Pop-up Dictionary")
        self.root.geometry("300x150")
        self.hover_ocr_window = None
        self.screen_snip_ocr_window = None
        self.center_window(self.root)

        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width
             / 2) - (self.root.winfo_width() / 2)
        y = (screen_height / 2) - (self.root.winfo_height() / 2)
        self.root.geometry('+%d+%d'
                           % (x, y))
        style = ttk.Style()
        style.theme_use('clam')

        self.root.geometry("300x150")

        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width
             / 2) - (self.root.winfo_width() / 2)
        y = (screen_height / 2) - (self.root.winfo_height() / 2)
        self.root.geometry('+%d+%d'
                           % (x, y))

        self.ocr_handler = ocr_handler
        self.jisho_api_handler = jisho_api_handler

        hover_ocr_button = ttk.Button(self.root, text="Hover OCR", command=self.show_hover_ocr_window)
        hover_ocr_button.pack(pady=10)

        screen_snip_ocr_button = ttk.Button(self.root, text="Screen Snip OCR", command=self.show_screen_snip_ocr_window)
        screen_snip_ocr_button.pack(pady=10)

    def show_hover_ocr_window(self):
        """
        Displays the HoverOCRWindow if it doesn't exist, otherwise brings it to the front.
        """

        if self.hover_ocr_window is None:
            self.hover_ocr_window = HoverOCRWindow(self.root, self.ocr_handler, self.jisho_api_handler)
        self.show_window(self.hover_ocr_window)

    def show_screen_snip_ocr_window(self):
        """
        Displays the ScreenSnipOCRWindow if it doesn't exist, otherwise brings it to the front
        """
        if self.screen_snip_ocr_window is None:
            self.screen_snip_ocr_window = ScreenSnipOCRWindow(self.root, self.ocr_handler, self.jisho_api_handler)
        self.show_window(self.screen_snip_ocr_window)

    def show_window(self, window):
        """
        Shows the specified window, hiding the main window and preserving its position.

        Args:
            window (tk.Toplevel): The window to show.
        """
        self.original_x = self.root.winfo_x()
        self.original_y = self.root.winfo_y()

        window.deiconify()
        window.geometry('+%d+%d' % (self.original_x, self.original_y))
        window.update_idletasks()

        self.root.withdraw()

        window.bind("<Destroy>", self.on_child_window_destroy)
        self.center_window(window)

    def on_child_window_destroy(self, event):
        """
        Handles the destruction of a child window, resetting references and showing the main window.

        Args:
            event (tk.Event): The window destroy event.
        """
        if event.widget == self.hover_ocr_window:
            self.hover_ocr_window = None
        elif event.widget == self.screen_snip_ocr_window:
            self.screen_snip_ocr_window = None
        self.root.geometry('+%d+%d' % (self.original_x, self.original_y))

    def center_window(self, window):
        """
        Centers the specified window on the screen

        Args:
            window (tk.Tk or tk.Toplevel): The window to center
        """
        window.update_idletasks()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()

        x = (screen_width / 2) - (window.winfo_width() / 2)
        y = (screen_height / 2) - (window.winfo_height() / 2)
        window.geometry('+%d+%d'
                        % (x, y))
