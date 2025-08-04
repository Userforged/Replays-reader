import cv2 as cv
import numpy as np
import easyocr
import os
import json
from difflib import get_close_matches
from image_converter import ImageConverter

class ImageAnalyzer:
    """Analyzes Street Fighter 6 game screenshots to extract match information."""

    DEFAULT_OUTPUT_DIR = 'output'
    DEFAULT_ANALYZED_SUBDIR = 'analyzed'
    DEFAULT_CONFIG_FILE = 'rois_config.json'

    def __init__(self, output_directory=None, analyzed_frames_subdirectory=None, config_file=None, debug=False):
        self.ocr_reader = None
        self.output_directory = output_directory or self.DEFAULT_OUTPUT_DIR
        self.analyzed_frames_subdirectory = analyzed_frames_subdirectory or self.DEFAULT_ANALYZED_SUBDIR
        self.config_file = config_file or self.DEFAULT_CONFIG_FILE
        self.debug = debug
        self.debug_counter = 0
        self.image_converter = ImageConverter(debug=debug, output_directory=self.output_directory)
        
        # Charger la configuration des ROIs
        self.rois = self._load_rois_config()

    def _load_rois_config(self):
        """Charge la configuration des ROIs depuis le fichier JSON."""
        try:
            if self.debug:
                print(f"[ImageAnalyzer] Loading ROIs config from: {self.config_file}")
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            rois = config.get('rois', [])
            if self.debug:
                print(f"[ImageAnalyzer] ✅ Loaded {len(rois)} ROI configurations")
                for roi in rois:
                    print(f"[ImageAnalyzer]   - {roi['name']}: {roi['label']}")
            
            return rois
            
        except FileNotFoundError:
            if self.debug:
                print(f"[ImageAnalyzer] ⚠️  Config file '{self.config_file}' not found, using fallback ROIs")
            return self._get_fallback_rois()
        except json.JSONDecodeError as e:
            if self.debug:
                print(f"[ImageAnalyzer] ❌ Invalid JSON in config file: {e}")
            print(f"⚠ Warning: Invalid JSON in config file '{self.config_file}', using fallback ROIs")
            return self._get_fallback_rois()
        except Exception as e:
            if self.debug:
                print(f"[ImageAnalyzer] ❌ Error loading config: {e}")
            print(f"⚠ Warning: Error loading config file '{self.config_file}', using fallback ROIs")
            return self._get_fallback_rois()
    
    def _get_fallback_rois(self):
        """ROIs de fallback en cas de problème avec le fichier de config."""
        if self.debug:
            print("[ImageAnalyzer] 🔄 Using hardcoded fallback ROI configuration")
        
        return [
            {
                'name': 'timer',
                'label': 'TIMER', 
                'type': 'font',
                'font_color': {
                    'lighter': [96, 12, 57],
                    'darker': [234, 92, 243]
                },
                'ocr_whitelist': '0123456789',
                'boundaries': {
                    'color': [96, 12, 57],
                    'top': 0.04,
                    'bottom': 0.18,
                    'left': 0.46,
                    'right': 0.54
                }
            },
            {
                'name': 'character1',
                'label': 'PLAYER 1',
                'type': 'font', 
                'ocr_whitelist': 'ABCDEFGHIJKLMNOPQRSTUVWXYZ.- ',
                'boundaries': {
                    'color': [92, 0, 210],
                    'top': 0.02,
                    'bottom': 0.15,
                    'left': 0,
                    'right': 0.1
                }
            },
            {
                'name': 'character2',
                'label': 'PLAYER 2',
                'type': 'font',
                'ocr_whitelist': 'ABCDEFGHIJKLMNOPQRSTUVWXYZ.- ',
                'boundaries': {
                    'color': [192, 106, 35],
                    'top': 0.02,
                    'bottom': 0.15,
                    'left': 0.9,
                    'right': 1
                }
            }
        ]
    
    def _get_roi(self, roi_name):
        """Récupère les informations d'une ROI (Region of Interest) par son nom."""
        for roi in self.rois:
            if roi['name'] == roi_name:
                # Convertir les listes en tuples pour les couleurs (compatibilité OpenCV)
                if 'font_color' in roi:
                    for color_key in ['lighter', 'darker']:
                        if color_key in roi['font_color'] and isinstance(roi['font_color'][color_key], list):
                            roi['font_color'][color_key] = tuple(roi['font_color'][color_key])
                if 'boundaries' in roi and 'color' in roi['boundaries'] and isinstance(roi['boundaries']['color'], list):
                    roi['boundaries']['color'] = tuple(roi['boundaries']['color'])
                return roi
        return None

    def initialize_ocr(self):
        if self.ocr_reader is None:
            if self.debug:
                print("[ImageAnalyzer] Initializing OCR reader")
            self.ocr_reader = easyocr.Reader(['en'])
            if self.debug:
                print("[ImageAnalyzer] OCR reader initialized")

    def analyze_image(self, image_path, rois_to_analyze=None):
        if self.debug:
            print(f"[ImageAnalyzer] analyze_image: path='{image_path}', rois={rois_to_analyze}")
        
        if rois_to_analyze is None:
            rois_to_analyze = ['timer', 'character1', 'character2']
            if self.debug:
                print(f"[ImageAnalyzer] Using default ROIs: {rois_to_analyze}")

        self.initialize_ocr()

        if self.debug:
            print(f"[ImageAnalyzer] Loading image: {image_path}")
        image = cv.imread(image_path)
        if image is None:
            if self.debug:
                print(f"[ImageAnalyzer] Failed to load image: {image_path}")
            raise ValueError(f"Unable to load image: {image_path}")
        
        if self.debug:
            print(f"[ImageAnalyzer] Image loaded successfully: {image.shape}")
        return self.analyze_frame(image, rois_to_analyze)

    def analyze_frame(self, frame, rois_to_analyze=None):
        if self.debug:
            print(f"[ImageAnalyzer] analyze_frame: frame_shape={frame.shape}, rois={rois_to_analyze}")
        
        if rois_to_analyze is None:
            rois_to_analyze = ['timer', 'character1', 'character2']

        self.initialize_ocr()

        detection_results = {}

        for roi_name in rois_to_analyze:
            if self.debug:
                print(f"[ImageAnalyzer] Processing ROI: {roi_name}")
            
            roi_image, boundaries = self.extract_roi(frame, roi_name)

            if roi_image is None or boundaries is None:
                if self.debug:
                    print(f"[ImageAnalyzer] ROI {roi_name} extraction failed")
                detection_results[roi_name] = ''
                continue

            if self.debug:
                print(f"[ImageAnalyzer] ROI {roi_name} extracted: {roi_image.shape}, boundaries={boundaries}")
            
            self.debug_counter += 1
            
            roi_info = self._get_roi(roi_name)
            
            if self.debug:
                if roi_info and 'font_color' in roi_info:
                    print(f"[ImageAnalyzer] 🎨 ROI '{roi_name}' has font_color config: {roi_info['font_color']}")
                    print(f"[ImageAnalyzer] ✨ Font color-based enhancement will be applied for better OCR")
                else:
                    print(f"[ImageAnalyzer] 📝 ROI '{roi_name}' uses standard OCR processing (no font_color)")
            
            self.image_converter.set_debug_counter(self.debug_counter)
            
            enhanced = self.image_converter.enhance_for_ocr(roi_image, roi_info)
            if enhanced is None:
                if self.debug:
                    print(f"[ImageAnalyzer] Enhancement failed for ROI {roi_name}")
                detection_results[roi_name] = ''
                continue
            
            if self.debug and roi_info and 'font_color' in roi_info:
                print(f"[ImageAnalyzer] 🔍 Enhanced image for '{roi_name}' now ready for color-optimized OCR")
                print(f"[ImageAnalyzer] 🔥 Expected improvement: better detection of text in colors {roi_info['font_color']}")

            if roi_name == 'timer':
                if self.debug:
                    print(f"[ImageAnalyzer] 🔢 Extracting timer digits from '{roi_name}' using enhanced image")
                detection_results[roi_name] = self._extract_timer_digits(enhanced, roi_info)
            else:
                if self.debug:
                    print(f"[ImageAnalyzer] 🎮 Extracting character name from '{roi_name}' using enhanced image")
                detection_results[roi_name] = self._extract_character_name(enhanced, roi_info)
            
            if self.debug:
                print(f"[ImageAnalyzer] ROI {roi_name} result: '{detection_results[roi_name]}'")

        if self.debug:
            print(f"[ImageAnalyzer] Final detection results: {detection_results}")
        return detection_results

    def visualize_rois(self, image_path, rois_to_show=None):
        if rois_to_show is None:
            rois_to_show = ['timer', 'character1', 'character2']

        image = cv.imread(image_path)
        if image is None:
            raise ValueError(f"Unable to load image: {image_path}")

        print(f"📐 Image dimensions: {image.shape[1]}x{image.shape[0]} pixels")

        annotated_image = self.annotate_frame_with_rois(image, rois_to_show, show_text=False)

        if self.debug:
            self._ensure_output_directories()
            output_path = os.path.join(
                self.output_directory,
                self.analyzed_frames_subdirectory,
                'rois_' + os.path.basename(image_path)
            )
            cv.imwrite(output_path, annotated_image)
            return output_path
        
        return None

    def annotate_frame_with_rois(self, frame, rois_to_show, show_text=True, detection_results=None):
        annotated = frame.copy()

        for roi_name in rois_to_show:
            roi_info = self._get_roi(roi_name)
            if not roi_info:
                continue
                
            _, boundaries = self.extract_roi(frame, roi_name)

            if boundaries is None:
                continue

            left_x, top_y, right_x, bottom_y = boundaries
            color = roi_info['boundaries']['color']

            cv.rectangle(annotated, (left_x, top_y), (right_x, bottom_y), color, 2)

            if show_text and detection_results and roi_name in detection_results:
                text = detection_results[roi_name] or f"No {roi_name}"
            else:
                text = roi_info['label']

            font = cv.FONT_HERSHEY_SIMPLEX
            scale = 0.5
            thickness = 2 if not show_text else 1
            (text_width, text_height), _ = cv.getTextSize(text, font, scale, thickness)
            text_x = left_x + (right_x - left_x - text_width) // 2
            text_y = top_y - 10

            cv.putText(annotated, text, (text_x, text_y), font, scale, color, thickness)

        return annotated

    def extract_roi(self, image, roi_name):
        height, width = image.shape[:2]
        if self.debug:
            print(f"[ImageAnalyzer] extract_roi: {roi_name}, image_size={width}x{height}")

        roi_info = self._get_roi(roi_name)
        if not roi_info:
            if self.debug:
                print(f"[ImageAnalyzer] Unknown ROI name: {roi_name}")
            return None, None
        
        boundaries = self._calculate_roi_boundaries(height, width, roi_info['boundaries'])

        if self.debug:
            print(f"[ImageAnalyzer] Raw boundaries for {roi_name}: {boundaries}")

        left_x, top_y, right_x, bottom_y = self._validate_boundaries(
            left_x=boundaries[0], top_y=boundaries[1],
            right_x=boundaries[2], bottom_y=boundaries[3],
            height=height, width=width, roi_name=roi_name
        )

        if left_x is None:
            if self.debug:
                print(f"[ImageAnalyzer] Invalid boundaries for {roi_name}")
            return None, None

        if self.debug:
            print(f"[ImageAnalyzer] Validated boundaries for {roi_name}: ({left_x}, {top_y}, {right_x}, {bottom_y})")
        
        roi = image[top_y:bottom_y, left_x:right_x]
        if self.debug:
            print(f"[ImageAnalyzer] Extracted ROI {roi_name} shape: {roi.shape}")
        return roi, (left_x, top_y, right_x, bottom_y)



    def _calculate_roi_boundaries(self, height, width, boundaries_config):
        """Calcule les boundaries d'une ROI (Region of Interest) à partir de sa configuration."""
        top = int(height * boundaries_config['top'])
        bottom = int(height * boundaries_config['bottom'])
        left = int(width * boundaries_config['left'])
        right = int(width * boundaries_config['right'])
        return left, top, right, bottom

    def _validate_boundaries(self, left_x, top_y, right_x, bottom_y, height, width, roi_name):
        left_x = max(0, min(left_x, width - 1))
        top_y = max(0, min(top_y, height - 1))
        right_x = max(left_x + 1, min(right_x, width))
        bottom_y = max(top_y + 1, min(bottom_y, height))

        if (right_x - left_x) < 1 or (bottom_y - top_y) < 1:
            print(f"⚠ ROI '{roi_name}' too small or invalid")
            return None, None, None, None

        return left_x, top_y, right_x, bottom_y

    def _extract_timer_digits(self, enhanced_image, roi_info=None):
        if self.debug:
            print(f"[ImageAnalyzer] _extract_timer_digits: processing image shape {enhanced_image.shape}")
        
        ocr_params = {}
        if roi_info and 'ocr_whitelist' in roi_info:
            whitelist = roi_info['ocr_whitelist']
            ocr_params['allowlist'] = whitelist
            if self.debug:
                print(f"[ImageAnalyzer] 🔍 Using OCR whitelist: '{whitelist}' for precise digit detection")
        
        results = self.ocr_reader.readtext(enhanced_image, **ocr_params)
        if self.debug:
            print(f"[ImageAnalyzer] OCR results for timer: {len(results)} detections")
        
        digits = ''
        for i, detection in enumerate(results):
            text = detection[1]
            extracted_digits = ''.join(filter(str.isdigit, text))
            if self.debug:
                print(f"[ImageAnalyzer] Detection {i}: '{text}' -> digits: '{extracted_digits}'")
            digits += extracted_digits
        
        if self.debug:
            print(f"[ImageAnalyzer] Final timer digits: '{digits}'")
        return digits

    def _extract_character_name(self, enhanced_image, roi_info=None):
        if self.debug:
            print(f"[ImageAnalyzer] _extract_character_name: processing image shape {enhanced_image.shape}")
        
        ocr_params = {}
        if roi_info and 'ocr_whitelist' in roi_info:
            whitelist = roi_info['ocr_whitelist']
            ocr_params['allowlist'] = whitelist
            if self.debug:
                print(f"[ImageAnalyzer] 🔍 Using OCR whitelist: '{whitelist}' for character detection")
        
        results = self.ocr_reader.readtext(enhanced_image, **ocr_params)
        if self.debug:
            print(f"[ImageAnalyzer] OCR results for character: {len(results)} detections")
        
        text = ''
        for i, detection in enumerate(results):
            detected_text = detection[1]
            if self.debug:
                print(f"[ImageAnalyzer] Detection {i}: '{detected_text}' (confidence: {detection[2]:.3f})")
            text += detected_text + ' '
        
        final_text = text.strip()
        if self.debug:
            print(f"[ImageAnalyzer] Final character text: '{final_text}'")
        return final_text

    def _ensure_output_directories(self):
        if not os.path.exists(self.output_directory):
            os.makedirs(self.output_directory)

        analyzed_path = os.path.join(self.output_directory, self.analyzed_frames_subdirectory)
        if not os.path.exists(analyzed_path):
            os.makedirs(analyzed_path)
