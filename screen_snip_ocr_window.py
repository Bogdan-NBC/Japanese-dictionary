from tkinter import BOTH, YES

import pyautogui
import tkinter as tk

from ocr_window import OCRWindow


class ScreenSnipOCRWindow(OCRWindow):
    def __init__(self, parent, ocr_handler, jisho_api_handler):
        """
        Initializes the ScreenSnipOCRWindow.

        Args:
            parent (tk.Tk): The parent window.
            ocr_handler (OCRHandler): Handles OCR processing.
            jisho_api_handler (JishoAPIHandler): Fetches word information from Jisho API.
        """
        super().__init__(parent)

        self.geometry("400x150")

        self.update_idletasks()
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        x = parent_x + (parent_width / 2) - (self.winfo_width() / 2)
        y = parent_y + (parent_height / 2) - (self.winfo_height() / 2)
        self.geometry('+%d+%d' % (x, y))

        self.ocr_handler = ocr_handler
        self.jisho_api_handler = jisho_api_handler

        take_screen_snip_button = tk.Button(self, text="Take Screen Snip",
                                            command=self.create_screen_canvas)
        take_screen_snip_button.pack()

        self.snip_surface = None
        self.start_x = None
        self.start_y = None
        self.current_x = None
        self.current_y = None
        self.root = parent
        self.title("Japanese Pop-up Dictionary")

        self.menu_frame = tk.Frame(parent)
        self.snipButton = tk.Button(self.menu_frame, width=3, height=1,
                                    command=self.create_screen_canvas)
        self.snipButton.pack()

        self.parent_screen = tk.Toplevel(self.root)
        self.parent_screen.withdraw()
        self.parent_screen.attributes("-transparent", "maroon3")
        self.picture_frame = tk.Frame(self.parent_screen, background="maroon3")
        self.picture_frame.pack(fill=BOTH, expand=YES)

    def create_screen_canvas(self):
        """
        Creates a canvas for capturing the screen snip area.
        """

        self.withdraw()
        self.parent_screen.deiconify()
        self.root.withdraw()

        if self.snip_surface:
            self.snip_surface.destroy()

        self.snip_surface = tk.Canvas(self.picture_frame, cursor="cross", bg="grey11")
        self.snip_surface.pack(fill=BOTH, expand=YES)

        self.snip_surface.bind("<ButtonPress-1>", self.on_button_press)
        self.snip_surface.bind("<B1-Motion>", self.on_snip_drag)
        self.snip_surface.bind("<ButtonRelease-1>", self.on_button_release)

        self.parent_screen.attributes('-fullscreen', True)
        self.parent_screen.attributes('-alpha', .3)
        self.parent_screen.lift()
        self.parent_screen.attributes("-topmost", True)

    def on_button_release(self, event):
        """
        Handles the mouse button release event after drawing the snip rectangle.
        """

        x1 = int(min(self.start_x, self.current_x))
        y1 = int(min(self.start_y, self.current_y))
        x2 = int(abs(self.current_x - self.start_x))
        y2 = int(abs(self.current_y - self.start_y))

        if x2 == 0 or y2 == 0:
            self.exit_screenshot_mode()
            return

        self.take_bounded_screenshot(x1, y1, x2, y2)
        self.exit_screenshot_mode()

    def exit_screenshot_mode(self):
        """
        Exits the screenshot mode and cleans up.
        """
        self.snip_surface.destroy()
        self.parent_screen.withdraw()
        self.deiconify()
        if self.snip_surface:
            self.snip_surface.destroy()
            self.snip_surface = None
        self.menu_frame.pack_forget()

    def on_button_press(self, event):
        """
        Handles the mouse button press event, marking the start of the snip.
        """
        self.start_x = self.snip_surface.canvasx(event.x)
        self.start_y = self.snip_surface.canvasy(event.y)
        self.snip_surface.create_rectangle(0, 0, 1, 1, outline='red', width=3, fill="maroon3")

    def on_snip_drag(self, event):
        """
        Handles mouse dragging during the snip, updating the rectangle.
        """
        self.current_x, self.current_y = (event.x, event.y)
        self.snip_surface.coords(1, self.start_x, self.start_y, self.current_x, self.current_y)

    def take_bounded_screenshot(self, x1, y1, x2, y2):
        """
        Takes a screenshot of the specified region and processes it for OCR.

        Args:
            x1, y1 (int): Top-left coordinates of the snip region.
            x2, y2 (int): Width and height of the snip region.
        """
        image = pyautogui.screenshot(region=(x1, y1, x2, y2))
        try:
            text = self.ocr_handler.process_screensnip(image)

            word_info = self.jisho_api_handler.fetch_jisho_info(text)
            if word_info:
                self.create_info_window(word_info, x1, y1)
            else:
                self.info_window = tk.Toplevel()
                self.info_window.title("Word Information")
                self.info_window.overrideredirect(True)

                message_label = tk.Label(self.info_window, text="no japanese word found")
                message_label.pack(pady=5)

                self.info_window.configure(bg="light yellow")
                message_label.config(bg="light yellow")

                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()

                if y1 + self.info_window.winfo_reqheight() > screen_height:
                    y1 = screen_height - self.info_window.winfo_reqheight() - 20

                if x1 + self.info_window.winfo_reqwidth() > screen_width:
                    x1 = screen_width - self.info_window.winfo_reqwidth() - 20

                self.info_window.geometry(f"+{x1 + 20}+{y1 + 20}")
                self.info_window.bind("<Leave>", self.on_mouse_leave)

        except Exception as e:
            print(f"Error during OCR: {e}")

    def on_closing(self):
        """
        Handles window closing, cleaning up the menu frame.
        """
        self.menu_frame.pack_forget()
        self.parent.destroy()

    def go_back(self):
        """
        Goes back to the parent window, destroying this window.
        """

        self.destroy()
        self.parent.deiconify()
