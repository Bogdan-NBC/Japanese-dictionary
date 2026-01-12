import ctypes

import jaconv
import numpy as np

from PIL import ImageGrab
from PIL.Image import fromarray

from pytesseract import pytesseract

pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

tessdata_dir_config = r'--tessdata-dir "C:\Program Files\Tesseract-OCR\tessdata" --psm 6'

CAPTURE_WIDTH, CAPTURE_HEIGHT = 300, 100

LANG = 'jpn+jpn_vert'


class OCRHandler:
    """
   Handles Optical Character Recognition (OCR) operations for Japanese text using Tesseract.

   Attributes:
       last_word (str): Stores the last recognized word for comparison.
       common_particles (list): List of common Japanese particles for character compatibility checks.
       hiragana_range (tuple): Range of Unicode code points for Hiragana characters.
       katakana_range (tuple): Range of Unicode code points for Katakana characters.
       ocr_cache (dict): Cache for storing OCR results to avoid redundant processing.
   """

    def __init__(self):
        self.last_word = None
        self.common_particles = ["は", "が", "を", "に", "へ", "と", "で", "から", "まで", "の", "ね", "よ"]
        self.hiragana_range = (ord(u'\u3040'), ord(u'\u309F'))
        self.katakana_range = (ord(u'\u30A0'), ord(u'\u30FF'))
        self.ocr_cache = {}

    def is_hiragana(self, char):
        return self.hiragana_range[0] <= ord(char) <= self.hiragana_range[1]

    def is_katakana(self, char):
        return self.katakana_range[0] <= ord(char) <= self.katakana_range[1]

    def process_screenshot(self, mouse_x, mouse_y):
        """
        Processes a screenshot taken around the mouse cursor to extract Japanese text.

        Args:
            mouse_x (int): The x-coordinate of the mouse cursor.
            mouse_y (int): The y-coordinate of the mouse cursor.

        Returns:
            str: The recognized Japanese text, or None if no text is found or an error occurs.
        """
        capture_left, capture_top = mouse_x - CAPTURE_WIDTH // 2, mouse_y - CAPTURE_HEIGHT // 2

        user32 = ctypes.windll.user32
        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)

        capture_left = max(0, capture_left)
        capture_top = max(0, capture_top)
        capture_right = min(screen_width - 1, capture_left + CAPTURE_WIDTH)
        capture_bottom = min(screen_height - 1, capture_top + CAPTURE_HEIGHT)

        capture_width = capture_right - capture_left
        capture_height = capture_bottom - capture_top

        capture_region = (capture_left, capture_top, capture_right, capture_bottom)

        if capture_region in self.ocr_cache:
            return self.ocr_cache[capture_region]

        cropped_image = ImageGrab.grab(bbox=capture_region)

        preprocessed_image = self.preprocess_image(cropped_image)

        data = pytesseract.image_to_data(preprocessed_image, lang=LANG, config=tessdata_dir_config,
                                         output_type=pytesseract.Output.DICT)

        mouse_x_relative, mouse_y_relative = mouse_x - capture_left, mouse_y - capture_top

        confidences = [(i, int(conf)) for i, conf in enumerate(data['conf']) if int(conf) > 30]
        confidences.sort(key=lambda x: x[1], reverse=True)

        merged_boxes = self.merge_overlapping_boxes(data, confidences)

        for x, y, w, h in merged_boxes:
            # Check if the mouse is within this bounding box
            if x <= mouse_x_relative <= x + w and y <= mouse_y_relative <= y + h:

                padding = 15

                # Adjust the crop's left boundary to the RIGHT edge of this bounding box
                crop_left = mouse_x_relative - padding

                # Ensure we don't go beyond the captured image
                crop_left = max(0, min(crop_left, capture_width - 1))

                try:
                    word_image = cropped_image.crop((crop_left, y - padding,
                                                     capture_left + capture_width, y + h + padding))

                    raw_text = pytesseract.image_to_string(word_image, lang=LANG, config=tessdata_dir_config)
                    text = raw_text.strip()

                    if text and text != self.last_word:
                        self.last_word = text
                        text = ''.join(text.split())
                        self.ocr_cache[capture_region] = text
                        return text

                except pytesseract.TesseractError as e:

                    print(f"Tesseract OCR error: {e}")

                    return None

                except ValueError:

                    print("ValueError occurred during text recognition.")

                    return None

        return None

    def preprocess_image(self, image):
        """
        Preprocesses the given image to improve OCR accuracy.

        Args:
            image (PIL.Image.Image): The image to preprocess.

        Returns:
            PIL.Image.Image: The preprocessed image.
        """
        import cv2
        # 1. Convert to grayscale
        gray_image = image.convert('L')

        # 2. Apply Gaussian blur
        blurred_image = cv2.GaussianBlur(np.array(gray_image), (5, 5), 0)

        # 3. Contrast enhancement (you can experiment with different parameters)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced_image = clahe.apply(blurred_image)

        # 4. Sharpening (optional, experiment with different kernels)
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        sharpened_image = cv2.filter2D(enhanced_image, -1, kernel)

        # 5. Adaptive thresholding
        thresholded_image = cv2.adaptiveThreshold(sharpened_image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                  cv2.THRESH_BINARY, 11, 2)

        # 6. Morphological operations (optional, experiment with kernel size and iterations)
        kernel = np.ones((2, 2), np.uint8)
        eroded_image = cv2.erode(thresholded_image, kernel, iterations=1)
        dilated_image = cv2.dilate(eroded_image, kernel, iterations=1)

        # 7. Convert back to PIL Image
        preprocessed_image = fromarray(dilated_image)

        return preprocessed_image

    def do_bboxes_overlap(self, bbox1, bbox2):
        """
        Checks if two bounding boxes overlap significantly.

        Args:
            bbox1 (tuple): The first bounding box (x, y, width, height).
            bbox2 (tuple): The second bounding box (x, y, width, height).

        Returns:
            bool: True if the boxes overlap significantly, False otherwise.
        """
        x1, y1, w1, h1 = bbox1

        x2, y2, w2, h2 = bbox2

        intersection_width = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))

        intersection_height = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))

        intersection_area = intersection_width * intersection_height

        union_area = w1 * h1 + w2 * h2 - intersection_area

        overlap_ratio = intersection_area / union_area

        return overlap_ratio >= 0.5

    def merge_overlapping_boxes(self, data, confidences):
        """
        Merges overlapping bounding boxes with compatible characters.

        Args:
            data (dict): Tesseract OCR output data.
            confidences (list): List of tuples (index, confidence) for detected words.

        Returns:
            list: List of merged bounding boxes (x, y, width, height).
        """
        merged_boxes = []

        visited = set()

        for i, _ in confidences:

            if i in visited:
                continue

            x, y, w, h = map(int, (data['left'][i], data['top'][i], data['width'][i], data['height'][i]))

            word = data['text'][i]

            current_box = (x, y, w, h, word)

            merged_boxes.append(current_box)

            visited.add(i)

            for j, _ in confidences:

                if j == i or j in visited:
                    continue

                x2, y2, w2, h2 = map(int, (data['left'][j], data['top'][j], data['width'][j], data['height'][j]))

                word2 = data['text'][j]

                if self.do_bboxes_overlap((x, y, w, h), (x2, y2, w2, h2)) and self.are_chars_compatible(word, word2):
                    merged_boxes.pop()

                    new_x = min(x, x2)

                    new_y = min(y, y2)

                    new_w = max(x + w, x2 + w2) - new_x

                    new_h = max(y + h, y2 + h2) - new_y

                    new_word = word + word2

                    current_box = (new_x, new_y, new_w, new_h, new_word)

                    merged_boxes.append(current_box)

                    visited.add(j)

        return [(x, y, w, h) for x, y, w, h, _ in merged_boxes]

    def are_chars_compatible(self, word1, word2):
        """
        Checks if two words have compatible characters for merging.

        Args:
            word1 (str): The first word.
            word2 (str): The second word.

        Returns:
            bool: True if the characters are compatible, False otherwise.
        """
        if not word1 or not word2:
            return False

        def is_hiragana(char):

            return self.hiragana_range[0] <= ord(char) <= self.hiragana_range[1]

        def is_katakana(char):

            return self.katakana_range[0] <= ord(char) <= self.katakana_range[1]

        if all(is_hiragana(c) for c in word1) and all(is_hiragana(c) for c in word2):
            return True

        if all(is_katakana(c) for c in word1) and all(is_katakana(c) for c in word2):
            return True

        word1_hiragana = jaconv.kata2hira(word1)

        word2_hiragana = jaconv.kata2hira(word2)

        if any(particle in word1_hiragana or particle in word2_hiragana for particle in self.common_particles):
            return True

        if ((any(c.isalpha() and not is_hiragana(c) and not is_katakana(c) for c in word1) and

             all(is_hiragana(c) for c in word2)) or

                (all(is_hiragana(c) for c in word1) and

                 any(c.isalpha() and not is_hiragana(c) and not is_katakana(c) for c in word2))):
            return True

        if all(is_katakana(c) for c in word1) and all(is_katakana(c) for c in word2):
            return True

        return False

    def process_screensnip(self, image):
        """
        Processes a screenshot to extract Japanese text.

        Args:
            image (PIL.Image.Image): The screenshot image.

        Returns:
            str: The recognized Japanese text, or None if no text is found or an error occurs.
        """
        try:
            text = pytesseract.image_to_string(image, lang=LANG, config=tessdata_dir_config,
                                               output_type=pytesseract.Output.STRING)

            text = ''.join(text.split())

            return text

        except pytesseract.TesseractError as e:
            print(f"Tesseract OCR error: {e}")
            return None

        except ValueError:
            print("ValueError occurred during text recognition.")
            return None
