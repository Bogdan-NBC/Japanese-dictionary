from api import JishoAPIHandler
from main_window import MainWindow
from ocr import OCRHandler
import tkinter as tk

if __name__ == "__main__":
    root = tk.Tk()
    ocr_handler = OCRHandler()
    jisho_api_handler = JishoAPIHandler()
    main_ui = MainWindow(root, ocr_handler, jisho_api_handler)
    main_ui.root.mainloop()
