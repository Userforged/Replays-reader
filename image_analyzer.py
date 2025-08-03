"""
Street Fighter 6 Image Analyzer

This module provides the ImageAnalyzer class for detecting and extracting
information from Street Fighter 6 game screenshots, including timer values,
character names, and character variations.
"""

import cv2 as cv
import numpy as np
import easyocr
import os
from difflib import get_close_matches


class ImageAnalyzer:
    """Analyzes Street Fighter 6 game screenshots to extract match information."""

    # Default output directories
    DEFAULT_OUTPUT_DIR = 'output'
    DEFAULT_ANALYZED_SUBDIR = 'analyzed'

    def __init__(self, output_directory=None, analyzed_frames_subdirectory=None):
        """
        Initialize the ImageAnalyzer.

        Args:
            output_directory: Base output directory (default: 'output')
            analyzed_frames_subdirectory: Subdirectory for analyzed frames (default: 'analyzed')
        """
        self.ocr_reader = None
        self.output_directory = output_directory or self.DEFAULT_OUTPUT_DIR
        self.analyzed_frames_subdirectory = analyzed_frames_subdirectory or self.DEFAULT_ANALYZED_SUBDIR

        # Color context for variations (in HSV)
        self.valid_variations = {
            'C': {
                'color_ranges': {
                    'darker': np.array([120, 50, 50]),   # Dark purple
                    'lighter': np.array([160, 255, 255]) # Light purple
                }
            },
            'M': {
                'color_ranges': {
                    'darker': np.array([10, 100, 100]),  # Dark orange
                    'lighter': np.array([25, 255, 255])  # Light orange
                }
            },
            'D': {
                'color_ranges': {
                    'darker': np.array([90, 50, 100]),   # Dark light blue
                    'lighter': np.array([110, 255, 255]) # Light blue
                }
            }
        }

        # Colors for region display (BGR format)
        self.region_colors = {
            'timer': (57, 12, 96),
            'character1': (210, 0, 92),
            'character2': (35, 106, 192),
            'variation1': (255, 202, 243),
            'variation2': (109, 191, 222)
        }

        # Labels for each region
        self.region_labels = {
            'timer': 'TIMER',
            'character1': 'PLAYER 1',
            'character2': 'PLAYER 2',
            'variation1': 'VAR1 (C=Violet/M=Orange/D=Bleu)',
            'variation2': 'VAR2 (C=Violet/M=Orange/D=Bleu)'
        }

    def initialize_ocr(self):
        """Initialize the OCR reader (called only when necessary)."""
        if self.ocr_reader is None:
            self.ocr_reader = easyocr.Reader(['en'])

    def analyze_image(self, image_path, regions_to_analyze=None):
        """
        Analyze an image file and return detection results.

        Args:
            image_path: Path to the image to analyze
            regions_to_analyze: List of regions to analyze (default: all regions)

        Returns:
            dict: Detection results for each region

        Raises:
            ValueError: If the image cannot be loaded
        """
        if regions_to_analyze is None:
            regions_to_analyze = ['timer', 'character1', 'character2', 'variation1', 'variation2']

        # Initialize OCR only if necessary
        self.initialize_ocr()

        # Load image
        image = cv.imread(image_path)
        if image is None:
            raise ValueError(f"Unable to load image: {image_path}")

        return self.analyze_frame(image, regions_to_analyze)

    def analyze_frame(self, frame, regions_to_analyze=None):
        """
        Analyze a frame (numpy array) and return detection results.

        Args:
            frame: Image as numpy array (BGR format)
            regions_to_analyze: List of regions to analyze

        Returns:
            dict: Detection results for each region
        """
        if regions_to_analyze is None:
            regions_to_analyze = ['timer', 'character1', 'character2', 'variation1', 'variation2']

        # Initialize OCR if necessary
        if self.ocr_reader is None:
            self.initialize_ocr()

        # Extract and analyze each region
        detection_results = {}

        for region_name in regions_to_analyze:
            region_image, boundaries = self.extract_region(frame, region_name)

            if region_image is None or boundaries is None:
                detection_results[region_name] = ''
                continue

            # Analyze based on region type
            if region_name in ['variation1', 'variation2']:
                # Special processing for variations
                enhanced = self.enhance_image_for_ocr(region_image, is_variation=True)
                if enhanced is not None:
                    detection_results[region_name] = self._detect_variation_with_color_context(
                        region_image, enhanced, region_name
                    )
                else:
                    detection_results[region_name] = ''
            elif region_name == 'timer':
                # Timer processing
                enhanced = self.enhance_image_for_ocr(region_image, is_variation=False)
                if enhanced is not None:
                    detection_results[region_name] = self._extract_timer_digits(enhanced)
                else:
                    detection_results[region_name] = ''
            else:
                # Character name processing
                enhanced = self.enhance_image_for_ocr(region_image, is_variation=False)
                if enhanced is not None:
                    detection_results[region_name] = self._extract_character_name(enhanced)
                else:
                    detection_results[region_name] = ''

        return detection_results

    def visualize_regions(self, image_path, regions_to_show=None):
        """
        Visualize regions on an image without performing OCR.

        Args:
            image_path: Path to the image
            regions_to_show: List of regions to display

        Returns:
            str: Path to the saved annotated image

        Raises:
            ValueError: If the image cannot be loaded
        """
        if regions_to_show is None:
            regions_to_show = ['timer', 'character1', 'character2', 'variation1', 'variation2']

        # Create output directories
        self._ensure_output_directories()

        # Load image
        image = cv.imread(image_path)
        if image is None:
            raise ValueError(f"Unable to load image: {image_path}")

        print(f"📐 Image dimensions: {image.shape[1]}x{image.shape[0]} pixels")

        # Annotate image
        annotated_image = self.annotate_frame_with_regions(image, regions_to_show, show_text=False)

        # Save
        output_path = os.path.join(
            self.output_directory,
            self.analyzed_frames_subdirectory,
            'regions_' + os.path.basename(image_path)
        )
        cv.imwrite(output_path, annotated_image)

        return output_path

    def annotate_frame_with_regions(self, frame, regions_to_show, show_text=True, detection_results=None):
        """
        Annotate a frame with regions and optionally detected text.

        Args:
            frame: Numpy array image to annotate
            regions_to_show: List of regions to display
            show_text: If True, display detected text
            detection_results: Detection results (required if show_text=True)

        Returns:
            numpy.ndarray: Annotated image
        """
        annotated = frame.copy()

        for region_name in regions_to_show:
            _, boundaries = self.extract_region(frame, region_name)

            if boundaries is None:
                continue

            left_x, top_y, right_x, bottom_y = boundaries
            color = self.region_colors.get(region_name, (255, 255, 255))

            # Draw rectangle
            cv.rectangle(annotated, (left_x, top_y), (right_x, bottom_y), color, 2)

            # Add text
            if show_text and detection_results and region_name in detection_results:
                text = detection_results[region_name] or f"No {region_name}"
            else:
                text = self.region_labels.get(region_name, region_name.upper())

            # Calculate text position
            font = cv.FONT_HERSHEY_SIMPLEX
            scale = 0.5
            thickness = 2 if not show_text else 1
            (text_width, text_height), _ = cv.getTextSize(text, font, scale, thickness)
            text_x = left_x + (right_x - left_x - text_width) // 2
            text_y = top_y - 10

            cv.putText(annotated, text, (text_x, text_y), font, scale, color, thickness)

        return annotated

    def extract_region(self, image, region_name):
        """
        Extract a specific region from the image.

        Args:
            image: Numpy array image
            region_name: Name of the region ('timer', 'character1', etc.)

        Returns:
            tuple: (region_image, boundaries) or (None, None) if failed
        """
        height, width = image.shape[:2]

        # Calculate boundaries based on region
        if region_name == 'timer':
            boundaries = self._calculate_timer_boundaries(height, width)
        elif region_name == 'character1':
            boundaries = self._calculate_character1_boundaries(height, width)
        elif region_name == 'character2':
            boundaries = self._calculate_character2_boundaries(height, width)
        elif region_name == 'variation1':
            boundaries = self._calculate_variation1_boundaries(height, width)
        elif region_name == 'variation2':
            boundaries = self._calculate_variation2_boundaries(height, width)
        else:
            return None, None

        # Validate boundaries
        left_x, top_y, right_x, bottom_y = boundaries
        left_x, top_y, right_x, bottom_y = self._validate_boundaries(
            left_x, top_y, right_x, bottom_y, height, width, region_name
        )

        if left_x is None:
            return None, None

        # Extract region
        region = image[top_y:bottom_y, left_x:right_x]
        return region, (left_x, top_y, right_x, bottom_y)

    def enhance_image_for_ocr(self, image, is_variation=False):
        """
        Enhance an image for OCR recognition.

        Args:
            image: Numpy array image (BGR)
            is_variation: True if it's a variation region

        Returns:
            numpy.ndarray: Enhanced grayscale image
        """
        if image is None or image.size == 0:
            return None

        try:
            gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)

            if is_variation:
                # Special processing for variations
                clahe = cv.createCLAHE(clipLimit=3.0, tileGridSize=(4,4))
                enhanced = clahe.apply(gray)
                upscaled = cv.resize(enhanced, None, fx=4, fy=4, interpolation=cv.INTER_CUBIC)
                binary = cv.adaptiveThreshold(upscaled, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C,
                                            cv.THRESH_BINARY, 11, 2)
                return binary
            else:
                # Normal processing
                clahe = cv.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                enhanced = clahe.apply(gray)
                upscaled = cv.resize(enhanced, None, fx=2, fy=2, interpolation=cv.INTER_CUBIC)
                return upscaled

        except cv.error as e:
            print(f"⚠ Error enhancing image: {e}")
            return None

    # Private methods (start with _)

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

    def _calculate_variation1_boundaries(self, height, width):
        top = int(height * 0.02)
        bottom = int(height * 0.10)
        left = int(width * 0.1)
        right = int(width * 0.15)
        return left, top, right, bottom

    def _calculate_variation2_boundaries(self, height, width):
        top = int(height * 0.02)
        bottom = int(height * 0.10)
        left = int(width * 0.85)
        right = int(width * 0.9)
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
        """Extract timer digits."""
        results = self.ocr_reader.readtext(enhanced_image)
        digits = ''
        for detection in results:
            text = detection[1]
            digits += ''.join(filter(str.isdigit, text))
        return digits

    def _extract_character_name(self, enhanced_image):
        """Extract character name."""
        results = self.ocr_reader.readtext(enhanced_image)
        text = ''
        for detection in results:
            text += detection[1] + ' '
        return text.strip()

    def _detect_variation_with_color_context(self, region_image, enhanced_region, region_name):
        """Detect variation using color and OCR."""
        # Analyze color
        predicted_variation, confidence = self._analyze_dominant_color(region_image)

        if predicted_variation and confidence > 15.0:
            print(f"🎨 {region_name}: Color detected → {predicted_variation} (confidence: {confidence:.1f}%)")

            # Create color-enhanced image
            color_enhanced = self._create_color_enhanced_image(region_image, predicted_variation)

            if color_enhanced is not None:
                color_enhanced_upscaled = cv.resize(color_enhanced, None, fx=4, fy=4,
                                                   interpolation=cv.INTER_CUBIC)

                try:
                    results = self.ocr_reader.readtext(
                        color_enhanced_upscaled,
                        allowlist='CMD',
                        paragraph=False,
                        min_size=1
                    )

                    if results:
                        text = ''.join([r[1] for r in results])
                        corrected = self._correct_variation_text(text)

                        if corrected == predicted_variation:
                            print(f"✅ {region_name}: Color + OCR match → {corrected}")
                            return corrected
                        elif corrected in self.valid_variations:
                            print(f"🔀 {region_name}: OCR differs. OCR: {corrected}, Color: {predicted_variation}")
                            return corrected
                except:
                    pass

            # High confidence in color
            if confidence > 25.0:
                print(f"🎨 {region_name}: High color confidence → {predicted_variation}")
                return predicted_variation

        # Fallback to classic OCR
        print(f"📝 {region_name}: Fallback to classic OCR")
        return self._detect_variation_with_ocr(enhanced_region, region_name)

    def _analyze_dominant_color(self, region_image):
        """Analyze dominant color in a region."""
        if region_image is None or region_image.size == 0:
            return None, 0.0

        hsv = cv.cvtColor(region_image, cv.COLOR_BGR2HSV)

        best_match = None
        best_coverage = 0.0
        color_analysis = {}

        for variation, data in self.valid_variations.items():
            color_range = data['color_ranges']
            mask = cv.inRange(hsv, color_range['darker'], color_range['lighter'])
            coverage = np.sum(mask > 0) / (mask.shape[0] * mask.shape[1]) * 100
            color_analysis[variation] = coverage

            if coverage > best_coverage:
                best_coverage = coverage
                best_match = variation

        print(f"🎨 Color analysis: {color_analysis}")

        return (best_match, best_coverage) if best_coverage > 5.0 else (None, 0.0)

    def _create_color_enhanced_image(self, region_image, predicted_variation):
        """Create color-enhanced image for predicted variation."""
        if region_image is None or predicted_variation not in self.valid_variations:
            return None

        hsv = cv.cvtColor(region_image, cv.COLOR_BGR2HSV)
        color_range = self.valid_variations[predicted_variation]['color_ranges']

        # Expand tolerances
        darker_expanded = color_range['darker'].copy()
        lighter_expanded = color_range['lighter'].copy()

        darker_expanded[1] = max(0, darker_expanded[1] - 30)
        darker_expanded[2] = max(0, darker_expanded[2] - 50)
        lighter_expanded[1] = min(255, lighter_expanded[1])
        lighter_expanded[2] = min(255, lighter_expanded[2])

        mask = cv.inRange(hsv, darker_expanded, lighter_expanded)
        color_isolated = cv.bitwise_and(region_image, region_image, mask=mask)
        gray_isolated = cv.cvtColor(color_isolated, cv.COLOR_BGR2GRAY)

        enhanced = gray_isolated.copy()
        enhanced[enhanced > 0] = 255

        return enhanced

    def _detect_variation_with_ocr(self, enhanced_region, region_name):
        """Detect variation with multiple OCR attempts."""
        # Attempt 1: With allowlist
        try:
            results = self.ocr_reader.readtext(enhanced_region, allowlist='CMD', paragraph=False)
            if results:
                text = ''.join([r[1] for r in results])
                corrected = self._correct_variation_text(text)
                if corrected:
                    print(f"🎯 {region_name} detected with allowlist: {corrected}")
                    return corrected
        except:
            pass

        # Attempt 2: Normal OCR
        try:
            results = self.ocr_reader.readtext(enhanced_region, paragraph=False)
            if results:
                text = ''.join([r[1] for r in results])
                corrected = self._correct_variation_text(text)
                if corrected:
                    print(f"🔧 {region_name} corrected: '{text}' → '{corrected}'")
                    return corrected
        except:
            pass

        print(f"❌ {region_name}: No variation detected")
        return ''

    def _correct_variation_text(self, detected_text):
        """Correct detected text for variations."""
        if not detected_text:
            return ''

        # Clean and take first character
        cleaned = ''.join(filter(str.isalpha, detected_text.upper()))
        if not cleaned:
            return ''

        first_char = cleaned[0]

        # Common corrections
        corrections = {
            'O': 'C', '0': 'C', 'Q': 'C', 'G': 'C',
            'N': 'M', 'H': 'M',
            'P': 'D', 'B': 'D', 'R': 'D',
        }

        corrected = corrections.get(first_char, first_char)

        if corrected in self.valid_variations:
            return corrected

        # Closest match
        matches = get_close_matches(corrected, list(self.valid_variations.keys()), n=1, cutoff=0.3)
        return matches[0] if matches else corrected if corrected.isalpha() else ''

    def _ensure_output_directories(self):
        """Create output directories if necessary."""
        if not os.path.exists(self.output_directory):
            os.makedirs(self.output_directory)

        analyzed_path = os.path.join(self.output_directory, self.analyzed_frames_subdirectory)
        if not os.path.exists(analyzed_path):
            os.makedirs(analyzed_path)