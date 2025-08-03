import cv2 as cv
import numpy as np
import easyocr
import os
from difflib import get_close_matches

class ImageAnalyzer:
    """Analyzes Street Fighter 6 game screenshots to extract match information."""

    DEFAULT_OUTPUT_DIR = 'output'
    DEFAULT_ANALYZED_SUBDIR = 'analyzed'

    def __init__(self, output_directory=None, analyzed_frames_subdirectory=None, save_analyzed_images=True):
        self.ocr_reader = None
        self.output_directory = output_directory or self.DEFAULT_OUTPUT_DIR
        self.analyzed_frames_subdirectory = analyzed_frames_subdirectory or self.DEFAULT_ANALYZED_SUBDIR
        self.save_analyzed_images = save_analyzed_images

        self.region_colors = {
            'timer': (57, 12, 96),
            'character1': (210, 0, 92),
            'character2': (35, 106, 192),
        }

        self.region_labels = {
            'timer': 'TIMER',
            'character1': 'PLAYER 1',
            'character2': 'PLAYER 2',
        }

    def initialize_ocr(self):
        if self.ocr_reader is None:
            self.ocr_reader = easyocr.Reader(['en'])

    def analyze_image(self, image_path, regions_to_analyze=None):
        if regions_to_analyze is None:
            regions_to_analyze = ['timer', 'character1', 'character2']

        self.initialize_ocr()

        image = cv.imread(image_path)
        if image is None:
            raise ValueError(f"Unable to load image: {image_path}")

        return self.analyze_frame(image, regions_to_analyze)

    def analyze_frame(self, frame, regions_to_analyze=None):
        if regions_to_analyze is None:
            regions_to_analyze = ['timer', 'character1', 'character2']

        self.initialize_ocr()

        detection_results = {}

        for region_name in regions_to_analyze:
            region_image, boundaries = self.extract_region(frame, region_name)

            if region_image is None or boundaries is None:
                detection_results[region_name] = ''
                continue

            enhanced = self.enhance_image_for_ocr(region_image)
            if region_name == 'timer':
                detection_results[region_name] = self._extract_timer_digits(enhanced) if enhanced is not None else ''
            else:
                detection_results[region_name] = self._extract_character_name(enhanced) if enhanced is not None else ''

        return detection_results

    def visualize_regions(self, image_path, regions_to_show=None):
        if regions_to_show is None:
            regions_to_show = ['timer', 'character1', 'character2']

        image = cv.imread(image_path)
        if image is None:
            raise ValueError(f"Unable to load image: {image_path}")

        print(f"📐 Image dimensions: {image.shape[1]}x{image.shape[0]} pixels")

        annotated_image = self.annotate_frame_with_regions(image, regions_to_show, show_text=False)

        if self.save_analyzed_images:
            self._ensure_output_directories()
            output_path = os.path.join(
                self.output_directory,
                self.analyzed_frames_subdirectory,
                'regions_' + os.path.basename(image_path)
            )
            cv.imwrite(output_path, annotated_image)
            return output_path
        
        return None

    def annotate_frame_with_regions(self, frame, regions_to_show, show_text=True, detection_results=None):
        annotated = frame.copy()

        for region_name in regions_to_show:
            _, boundaries = self.extract_region(frame, region_name)

            if boundaries is None:
                continue

            left_x, top_y, right_x, bottom_y = boundaries
            color = self.region_colors.get(region_name, (255, 255, 255))

            cv.rectangle(annotated, (left_x, top_y), (right_x, bottom_y), color, 2)

            if show_text and detection_results and region_name in detection_results:
                text = detection_results[region_name] or f"No {region_name}"
            else:
                text = self.region_labels.get(region_name, region_name.upper())

            font = cv.FONT_HERSHEY_SIMPLEX
            scale = 0.5
            thickness = 2 if not show_text else 1
            (text_width, text_height), _ = cv.getTextSize(text, font, scale, thickness)
            text_x = left_x + (right_x - left_x - text_width) // 2
            text_y = top_y - 10

            cv.putText(annotated, text, (text_x, text_y), font, scale, color, thickness)

        return annotated

    def extract_region(self, image, region_name):
        height, width = image.shape[:2]

        if region_name == 'timer':
            boundaries = self._calculate_timer_boundaries(height, width)
        elif region_name == 'character1':
            boundaries = self._calculate_character1_boundaries(height, width)
        elif region_name == 'character2':
            boundaries = self._calculate_character2_boundaries(height, width)
        else:
            return None, None

        left_x, top_y, right_x, bottom_y = self._validate_boundaries(
            left_x=boundaries[0], top_y=boundaries[1],
            right_x=boundaries[2], bottom_y=boundaries[3],
            height=height, width=width, region_name=region_name
        )

        if left_x is None:
            return None, None

        region = image[top_y:bottom_y, left_x:right_x]
        return region, (left_x, top_y, right_x, bottom_y)

    def enhance_image_for_ocr(self, image):
        if image is None or image.size == 0:
            return None

        try:
            gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
            clahe = cv.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            upscaled = cv.resize(enhanced, None, fx=2, fy=2, interpolation=cv.INTER_CUBIC)
            return upscaled
        except cv.error as e:
            print(f"⚠ Error enhancing image: {e}")
            return None

    def _calculate_timer_boundaries(self, height, width):
        top = int(height * 0.04)
        bottom = int(height * 0.18)
        left = int(width * 0.46)
        right = int(width * 0.54)
        return left, top, right, bottom

    def _calculate_character1_boundaries(self, height, width):
        top = int(height * 0.02)
        bottom = int(height * 0.15)
        left = int(width * 0)
        right = int(width * 0.1)
        return left, top, right, bottom

    def _calculate_character2_boundaries(self, height, width):
        top = int(height * 0.02)
        bottom = int(height * 0.15)
        left = int(width * 0.9)
        right = int(width * 1)
        return left, top, right, bottom

    def _validate_boundaries(self, left_x, top_y, right_x, bottom_y, height, width, region_name):
        left_x = max(0, min(left_x, width - 1))
        top_y = max(0, min(top_y, height - 1))
        right_x = max(left_x + 1, min(right_x, width))
        bottom_y = max(top_y + 1, min(bottom_y, height))

        if (right_x - left_x) < 1 or (bottom_y - top_y) < 1:
            print(f"⚠ Region '{region_name}' too small or invalid")
            return None, None, None, None

        return left_x, top_y, right_x, bottom_y

    def _extract_timer_digits(self, enhanced_image):
        results = self.ocr_reader.readtext(enhanced_image)
        digits = ''
        for detection in results:
            text = detection[1]
            digits += ''.join(filter(str.isdigit, text))
        return digits

    def _extract_character_name(self, enhanced_image):
        results = self.ocr_reader.readtext(enhanced_image)
        text = ''
        for detection in results:
            text += detection[1] + ' '
        return text.strip()

    def _ensure_output_directories(self):
        if not os.path.exists(self.output_directory):
            os.makedirs(self.output_directory)

        analyzed_path = os.path.join(self.output_directory, self.analyzed_frames_subdirectory)
        if not os.path.exists(analyzed_path):
            os.makedirs(analyzed_path)
