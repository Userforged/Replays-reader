import cv2 as cv
import numpy as np
import easyocr
import os
import json
from difflib import get_close_matches
from .image_converter import ImageConverter


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
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            rois = config.get('rois', [])
            if not rois:
                raise ValueError(f"No ROIs found in config file '{self.config_file}'")
            
            if self.debug:
                roi_names = [roi['name'] for roi in rois]
                print(f"[ImageAnalyzer] ✅ Loaded {len(rois)} ROI configurations from {self.config_file}: {', '.join(roi_names)}")
            
            return rois
            
        except FileNotFoundError:
            raise FileNotFoundError(f"ROI configuration file '{self.config_file}' not found. Please create the file or specify a valid config path.")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file '{self.config_file}': {e}")
        except Exception as e:
            raise RuntimeError(f"Error loading config file '{self.config_file}': {e}")

    def _get_roi(self, roi_name):
        """Récupère les informations d'une ROI (Region of Interest) par son nom."""
        for roi in self.rois:
            if roi['name'] == roi_name:
                # Conversion pour compatibilité OpenCV
                if 'boundaries' in roi and 'color' in roi['boundaries'] and isinstance(roi['boundaries']['color'], list):
                    roi['boundaries']['color'] = tuple(roi['boundaries']['color'])
                return roi
        return None

    def initialize_ocr(self):
        if self.ocr_reader is None:
            self.ocr_reader = easyocr.Reader(['en'])
            if self.debug:
                print("[ImageAnalyzer] OCR reader initialized with parameters 'en'.")

    def analyze_image(self, image_path, rois_to_analyze=None):
        if rois_to_analyze is None:
            rois_to_analyze = ['timer', 'character1', 'character2']

        self.initialize_ocr()

        image = cv.imread(image_path)
        if image is None:
            if self.debug:
                print(f"[ImageAnalyzer] Failed to load image: {image_path}")
            raise ValueError(f"Unable to load image: {image_path}")
        
        if self.debug:
            print(f"[ImageAnalyzer] 🖼️ Image {image_path} loaded successfully: {image.shape[1]}x{image.shape[0]}")
        return self.analyze_frame(image, rois_to_analyze, image_path)

    def analyze_frame(self, frame, rois_to_analyze=None, image_path=None):
        if rois_to_analyze is None:
            rois_to_analyze = ['timer', 'character1', 'character2']

        detection_results = {}

        for roi_name in rois_to_analyze:
            roi_image, boundaries = self.extract_roi(frame, roi_name)

            if roi_image is None or boundaries is None:
                if self.debug:
                    print(f"[ImageAnalyzer] ROI {roi_name} extraction failed")
                detection_results[roi_name] = ''
                continue

            if self.debug:
                # Sauvegarder le ROI pour debug
                debug_dir = os.path.join(self.output_directory, 'debug_preprocessing')
                os.makedirs(debug_dir, exist_ok=True)
                
                # Créer le nom de fichier debug
                base_name = os.path.splitext(os.path.basename(image_path if image_path else 'unknown'))[0]
                debug_filename = f"debug_{base_name}_region_{roi_name}.jpg"
                debug_path = os.path.join(debug_dir, debug_filename)
                
                # Sauvegarder l'image ROI
                cv.imwrite(debug_path, roi_image)
                
                print(f"[ImageAnalyzer] ⬜ ROI {roi_name} extracted: {roi_image.shape[1]}x{roi_image.shape[0]} with boundaries={boundaries} -> saved as {debug_filename}")
            
            self.debug_counter += 1
            
            roi_info = self._get_roi(roi_name)
            roi_type = roi_info.get('type', 'ocr') if roi_info else 'ocr'
            
            if roi_type == 'pattern':
                if self.debug:
                    print(f"[ImageAnalyzer] 🔍 ROI '{roi_name}' uses pattern matching")
                detection_results[roi_name] = self._analyze_pattern_roi(roi_image, roi_info)
            else:
                if self.debug:
                    print(f"[ImageAnalyzer] 📝 ROI '{roi_name}' uses OCR processing")
                
                self.initialize_ocr()
                self.image_converter.set_debug_counter(self.debug_counter)
                
                enhanced = self.image_converter.enhance_for_ocr(roi_image, roi_info)
                if enhanced is None:
                    if self.debug:
                        print(f"[ImageAnalyzer] Enhancement failed for ROI {roi_name}")
                    detection_results[roi_name] = ''
                    continue
                
                if self.debug:
                    print(f"[ImageAnalyzer] 🔍 Enhanced image for '{roi_name}' ready for OCR")

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

        roi_info = self._get_roi(roi_name)
        if not roi_info:
            if self.debug:
                print(f"[ImageAnalyzer] Unknown ROI name: {roi_name}")
            return None, None
        
        boundaries = self._calculate_roi_boundaries(height, width, roi_info['boundaries'])

        left_x, top_y, right_x, bottom_y = self._validate_boundaries(
            left_x=boundaries[0], top_y=boundaries[1],
            right_x=boundaries[2], bottom_y=boundaries[3],
            height=height, width=width, roi_name=roi_name
        )

        if left_x is None:
            if self.debug:
                print(f"[ImageAnalyzer] Invalid boundaries for {roi_name}")
            return None, None

        roi = image[top_y:bottom_y, left_x:right_x]
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
        
        # Configuration EasyOCR optimisée pour timer (équivalent PSM 8 = "single word")
        ocr_params = {
            'paragraph': False,    # Désactive la détection de paragraphe - traite comme un mot unique
            'width_ths': 0.9,      # Seuil restrictif pour éviter de séparer les chiffres (99:59 -> "99" "59")
            'height_ths': 0.9,     # Seuil restrictif pour éviter de séparer les lignes 
            'text_threshold': 0.7, # Seuil de confiance pour détecter le texte (optimal pour chiffres)
            'low_text': 0.4,       # Seuil bas pour capturer même les chiffres faibles en contraste
        }
        
        if roi_info and 'ocr_whitelist' in roi_info:
            whitelist = roi_info['ocr_whitelist']
            ocr_params['allowlist'] = whitelist
            if self.debug:
                print(f"[ImageAnalyzer] 🔍 Using OCR whitelist: '{whitelist}' for precise digit detection")
        
        if self.debug:
            print(f"[ImageAnalyzer] 🎯 Using timer-optimized EasyOCR settings (PSM 8 equivalent):")
            print(f"[ImageAnalyzer]   - paragraph=False (single word mode)")
            print(f"[ImageAnalyzer]   - width_ths=0.9, height_ths=0.9 (restrictive merging)")
            print(f"[ImageAnalyzer]   - text_threshold=0.7, low_text=0.4 (optimized for digits)")
        
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

    def _analyze_pattern_roi(self, roi_image, roi_info):
        """
        Analyse une ROI de type 'pattern' en utilisant template matching.
        
        Args:
            roi_image: Image de la ROI extraite
            roi_info: Informations de configuration de la ROI
        
        Returns:
            Résultat de détection (nom du pattern ou chaîne vide)
        """
        if self.debug:
            print(f"[ImageAnalyzer] Pattern matching for ROI '{roi_info['name']}'")
        
        # Répertoire des templates pour cette ROI
        templates_dir = os.path.join('templates', roi_info['name'])
        
        if not os.path.exists(templates_dir):
            if self.debug:
                print(f"[ImageAnalyzer] ⚠️  Templates directory not found: {templates_dir}")
            return ''
        
        best_match = ''
        best_confidence = 0.0
        confidence_threshold = 0.7  # Seuil de confiance minimal
        
        # Scanner tous les templates dans le répertoire
        for template_file in os.listdir(templates_dir):
            if not template_file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                continue
                
            template_path = os.path.join(templates_dir, template_file)
            template = cv.imread(template_path, cv.IMREAD_GRAYSCALE)
            
            if template is None:
                if self.debug:
                    print(f"[ImageAnalyzer] ⚠️  Could not load template: {template_path}")
                continue
            
            # Convertir la ROI en niveaux de gris
            roi_gray = cv.cvtColor(roi_image, cv.COLOR_BGR2GRAY) if len(roi_image.shape) == 3 else roi_image
            
            # Template matching avec différentes méthodes
            methods = [cv.TM_CCOEFF_NORMED, cv.TM_CCORR_NORMED, cv.TM_SQDIFF_NORMED]
            
            for method in methods:
                try:
                    result = cv.matchTemplate(roi_gray, template, method)
                    _, max_val, _, max_loc = cv.minMaxLoc(result)
                    
                    # Pour TM_SQDIFF_NORMED, plus faible = meilleur match
                    if method == cv.TM_SQDIFF_NORMED:
                        confidence = 1.0 - max_val
                    else:
                        confidence = max_val
                    
                    if confidence > best_confidence and confidence >= confidence_threshold:
                        best_confidence = confidence
                        # Utiliser le nom du fichier sans extension comme résultat
                        best_match = os.path.splitext(template_file)[0]
                    
                    if self.debug:
                        method_name = {cv.TM_CCOEFF_NORMED: 'CCOEFF', cv.TM_CCORR_NORMED: 'CCORR', cv.TM_SQDIFF_NORMED: 'SQDIFF'}[method]
                        print(f"[ImageAnalyzer]   {template_file} ({method_name}): {confidence:.3f}")
                        
                except Exception as e:
                    if self.debug:
                        print(f"[ImageAnalyzer] Error matching template {template_file}: {e}")
                    continue
        
        if best_match and best_confidence >= confidence_threshold:
            if self.debug:
                print(f"[ImageAnalyzer] ✅ Best pattern match: '{best_match}' (confidence: {best_confidence:.3f})")
            return best_match
        else:
            if self.debug:
                print(f"[ImageAnalyzer] ❌ No pattern match above threshold {confidence_threshold}")
            return ''

    def _ensure_output_directories(self):
        if not os.path.exists(self.output_directory):
            os.makedirs(self.output_directory)

        analyzed_path = os.path.join(self.output_directory, self.analyzed_frames_subdirectory)
        if not os.path.exists(analyzed_path):
            os.makedirs(analyzed_path)
