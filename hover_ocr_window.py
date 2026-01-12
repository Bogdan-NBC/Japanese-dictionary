import threading
import time
from time import sleep
from tkinter import ttk
import tkinter as tk
import keyboard
import pyautogui

from ocr_window import OCRWindow


class HoverOCRWindow(OCRWindow):
    """
    A window that performs OCR on the word under the mouse cursor when stationary.

    Attributes:
        parent (tk.Tk): The parent window.
        ocr_handler (OCRHandler): Handles OCR processing.
        jisho_api_handler (JishoAPIHandler): Fetches word information from the Jisho API.
        running (bool): Indicates whether OCR is currently running.
        abort_ocr (bool): Flag to signal OCR thread termination.
        last_mouse_position (tuple): Stores the last mouse position for movement detection.
        ocr_thread (threading.Thread): The thread running the OCR loop.
        loading_window (tk.Toplevel): A window to display a loading indicator.
        error_window (tk.Toplevel): A window to display error messages.
    """

    def __init__(self, parent, ocr_handler, jisho_api_handler):
        super().__init__(parent)
        self.title("Japanese Pop-up Dictionary")

        self.geometry("300x150")

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
        self.running = False

        start_ocr_button = ttk.Button(self, text="Start OCR", command=self.start_ocr_thread)
        start_ocr_button.pack()

        stop_ocr_button = ttk.Button(self, text="Stop OCR", command=self.stop_ocr)
        stop_ocr_button.pack()
        keyboard.add_hotkey('alt+e', self.toggle_ocr)

        self.abort_ocr = False
        self.last_mouse_position = None
        self.ocr_thread = None

        self.loading_window = None
        self.error_window = None
        self.create_loading_window()
        self.loading_window.withdraw()

    def go_back(self):
        """
        Returns to the parent window, closing this window.
        """
        parent_x, parent_y = self.winfo_x(), self.winfo_y()  # Store position before destroying
        self.destroy()
        self.parent.deiconify()
        self.parent.geometry('+%d+%d' % (parent_x, parent_y))  # Use stored position

    def toggle_ocr(self):
        """
        Toggles the OCR functionality on or off.
        """
        if self.running:
            self.stop_ocr()
        else:
            self.start_ocr_thread()

    def start_ocr_thread(self):
        """
        Starts the OCR process in a separate thread if not already running.
        """
        if not self.running and self.ocr_thread is None:
            self.running = True
            self.abort_ocr = False
            self.ocr_thread = threading.Thread(target=self.ocr_loop)
            self.ocr_thread.start()

    def stop_ocr(self):
        """
        Stops the OCR process and cleans up.
        """

        if self.running:
            self.running = False
            self.abort_ocr = True
            if self.ocr_thread:
                self.ocr_thread.join()
                self.ocr_thread = None
            self.ocr_handler.last_word = None

            if self.loading_window:
                self.loading_window.destroy()
                self.loading_window = None

    def ocr_loop(self):
        """
        The main OCR loop that continuously checks mouse position and performs OCR when stationary.
        """
        last_word = None
        last_mouse_position = None
        stationary_time = 0
        mouse_moved = False
        last_ocr_time = 0

        while self.running and not self.abort_ocr:
            try:
                current_mouse_position = pyautogui.position()

                if current_mouse_position == last_mouse_position:
                    stationary_time += 0.1
                    if stationary_time >= 1.0 and mouse_moved:

                        # Debounce the OCR trigger
                        current_time = time.time()
                        if current_time - last_ocr_time < 0.5:
                            continue
                        last_ocr_time = current_time

                        if self.loading_window:
                            self.loading_window.geometry(
                                f"+{current_mouse_position[0] + 10}+{current_mouse_position[1] + 10}")
                            self.loading_window.deiconify()
                            self.loading_window.lift()

                        mouse_x, mouse_y = current_mouse_position
                        text = self.ocr_handler.process_screenshot(mouse_x, mouse_y)

                        self.loading_window.withdraw()

                        if not text:
                            self.show_error_message(current_mouse_position, "No text detected")

                        if text and text != last_word:
                            last_word = text
                            word_info = self.jisho_api_handler.fetch_jisho_info(text)
                            if word_info:
                                self.create_info_window(word_info, mouse_x, mouse_y)

                        stationary_time = 0

                else:
                    last_mouse_position = current_mouse_position
                    stationary_time = 0
                    mouse_moved = True

                sleep(0.1)

            except Exception as e:
                print(f"Error during OCR: {e}")
                self.display_error_message(
                    "OCR failed. Please try adjusting the capture area or improving image quality.")

    def create_loading_window(self, position=None):
        """
        Creates a loading window to indicate that OCR is in progress.

        Args:
            position (tuple, optional): The (x, y) coordinates to position the loading window.
                                        Defaults to (0, 0) if not provided.
        """
        x, y = position or (0, 0)
        self.loading_window = tk.Toplevel(self)
        self.loading_window.overrideredirect(True)
        self.loading_window.geometry(f"+{x + 10}+{y + 10}")
        label = tk.Label(self.loading_window, text="Loading...", font=("Helvetica", 12))
        label.pack()

    def destroy_loading_window(self):
        """
        Destroys the loading window if it exists.
        """
        if self.loading_window:
            self.loading_window.destroy()
            self.loading_window = None

    def show_error_message(self, position, message):
        """
        Displays a temporary error message window at the specified position.

        Args:
            position (tuple): The (x, y) coordinates to position the error window.
            message (str): The error message to display.
        """
        x, y = position
        self.error_window = tk.Toplevel(self)
        self.error_window.overrideredirect(True)
        self.error_window.geometry(f"+{x + 10}+{y + 10}")
        label = tk.Label(self.error_window, text=message, font=("Helvetica", 12), foreground="red")
        label.pack()
        self.error_window.after(1000, self.destroy_error_window)

    def destroy_error_window(self):
        """
        Destroys the error window if it exists.
        """
        if self.error_window:
            self.error_window.destroy()
            self.error_window = None

    def display_error_message(self, message):
        """
       Displays an error message within the HoverOCRWindow.

       Args:
           message (str): The error message to display
       """
        error_label = ttk.Label(self, text=message, foreground="red", font=("Helvetica", 12))
        error_label.pack()
        self.after(1000, error_label.destroy)

    def on_mouse_leave(self, event):
        """
        Handles the event when the mouse leaves the info window.
        """
        if self.info_window:
            self.info_window.destroy()
            self.info_window = None
            self.ocr_handler.last_word = None
            if self.running:
                self.start_ocr_thread()
