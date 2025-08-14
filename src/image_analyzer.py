import cv2 as cv
import os
import json
from PIL import Image
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from difflib import get_close_matches
from .image_converter import ImageConverter
from .preprocessing_steps import PreprocessingStep

try:
    import easyocr
except ImportError:
    easyocr = None


class ImageAnalyzer:
    """Analyzes Street Fighter 6 game screenshots to extract match information."""

    DEFAULT_CONFIG_FILE = 'rois_config.json'

    def __init__(self, timer_roi=None, character1_roi=None,
                 character2_roi=None, config_file=None,
                 characters_file=None, debug=False,
                 debug_save_dir=None):
        if debug and not debug_save_dir:
            raise ValueError("debug_save_dir est requis quand debug=True")
        
        if not config_file:
            raise ValueError(
                "config_file est requis pour charger les métadonnées "
                "des ROIs (model, whitelist, etc.)"
            )
        
        self.timer_roi = timer_roi
        self.character1_roi = character1_roi  
        self.character2_roi = character2_roi
        self.debug_save_dir = debug_save_dir
        
        self.trocr_processor = None
        self.trocr_model = None
        self.trocr_available = False
        
        self.easyocr_reader = None
        self.easyocr_available = False
        
        self.config_file = config_file
        self.characters_file = characters_file
        self.debug = debug
        self.debug_counter = 0
        self.image_converter = ImageConverter(debug=debug, output_directory=debug_save_dir)
        
        if characters_file:
            self.character_names = self._load_character_names()
        else:
            self.character_names = None
        
        self.rois = self._load_rois_config()
            
        self._initialize_trocr()
        self._initialize_easyocr()
        
        # Show OCR status only once during initialization
        if self.debug:
            trocr_status = '✅' if self.trocr_available else '❌'
            easyocr_status = '✅' if self.easyocr_available else '❌'
            print(f"[ImageAnalyzer] Statut OCR - TrOCR: {trocr_status}, "
                  f"EasyOCR: {easyocr_status}")
            if not self.trocr_available and not self.easyocr_available:
                print("[ImageAnalyzer] ⚠️ Aucun modèle OCR disponible")

    def _get_model_cache_kwargs(self, model_name):
        """Prevents model re-downloads by using local cache."""
        del model_name  # Parameter not used but required for interface
        cache_dir = os.path.expanduser('~/.cache/huggingface/transformers')
        return {
            'cache_dir': cache_dir,
            'local_files_only': False,
            'force_download': False
        }
    
    def _initialize_trocr(self):
        try:
            if self.debug:
                print("[ImageAnalyzer] 🔄 Chargement de TrOCR...")
            
            model_name = 'microsoft/trocr-base-printed'
            cache_kwargs = self._get_model_cache_kwargs(model_name)
            
            import torch
            device = torch.device(
                'cuda' if torch.cuda.is_available() else 'cpu'
            )
            
            self.trocr_processor = TrOCRProcessor.from_pretrained(
                model_name, use_fast=True, **cache_kwargs
            )
            self.trocr_model = VisionEncoderDecoderModel.from_pretrained(
                model_name, **cache_kwargs
            ).to(device)
            self.trocr_device = device
            self.trocr_available = True
            
            if self.debug:
                print(f"[ImageAnalyzer] ✅ TrOCR chargé avec succès sur {device}")
                
        except Exception as e:
            self.trocr_available = False
            if self.debug:
                print(f"[ImageAnalyzer] ❌ Erreur TrOCR: {e}")

    def _initialize_easyocr(self):
        if easyocr is None:
            self.easyocr_available = False
            if self.debug:
                print("[ImageAnalyzer] ❌ EasyOCR non disponible (module non installé)")
            return
            
        try:
            if self.debug:
                print("[ImageAnalyzer] 🔄 Chargement de EasyOCR...")
            
            # English only for better performance
            self.easyocr_reader = easyocr.Reader(['en'], gpu=True)
            self.easyocr_available = True
            
            if self.debug:
                print(
                    "[ImageAnalyzer] ✅ EasyOCR chargé avec succès "
                    "(GPU activé)"
                )
                
        except Exception as e:
            self.easyocr_available = False
            if self.debug:
                print(f"[ImageAnalyzer] ❌ Erreur EasyOCR: {e}")

    def _load_rois_config(self):
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            rois = config.get('rois', [])
            if not rois:
                raise ValueError(
                    f"No ROIs found in config file '{self.config_file}'"
                )
            
            if self.debug:
                roi_names = [roi['name'] for roi in rois]
                roi_list = ', '.join(roi_names)
                print(
                    f"[ImageAnalyzer] ✅ Loaded {len(rois)} ROI "
                    f"configurations from {self.config_file}: {roi_list}"
                )
            
            return rois
            
        except FileNotFoundError:
            raise FileNotFoundError(
                f"ROI configuration file '{self.config_file}' not found. "
                f"Please create the file or specify a valid config path."
            )
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON in config file '{self.config_file}': {e}"
            )
        except Exception as e:
            raise RuntimeError(
                f"Error loading config file '{self.config_file}': {e}"
            )

    def _load_character_names(self):
        try:
            with open(self.characters_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            characters = data.get('characters', [])
            if not characters:
                raise ValueError(
                    f"No characters found in file '{self.characters_file}'"
                )
            
            if self.debug:
                print(
                    f"[ImageAnalyzer] ✅ Loaded {len(characters)} character "
                    f"names from {self.characters_file}"
                )
            
            return characters
            
        except FileNotFoundError:
            if self.debug:
                print(
                    f"[ImageAnalyzer] ⚠️ Character names file "
                    f"'{self.characters_file}' not found. Character matching "
                    f"disabled."
                )
            return None
        except json.JSONDecodeError as e:
            if self.debug:
                print(
                    f"[ImageAnalyzer] ❌ Invalid JSON in characters file "
                    f"'{self.characters_file}': {e}"
                )
            return None
        except Exception as e:
            if self.debug:
                print(
                    f"[ImageAnalyzer] ❌ Error loading characters file "
                    f"'{self.characters_file}': {e}"
                )
            return None

    def _match_character_name(self, detected_text,
                              similarity_threshold=0.6):
        """Trouve le nom de personnage le plus proche du texte détecté."""
        if not self.character_names or not detected_text.strip():
            return ""
        
        cleaned_text = detected_text.strip().upper()
        
        if self.debug:
            print(
                f"[ImageAnalyzer] 🔍 Tentative de correspondance pour: "
                f"'{detected_text}' -> '{cleaned_text}'"
            )
        
        # Try exact match first
        if cleaned_text in self.character_names:
            if self.debug:
                print(
                    f"[ImageAnalyzer] ✅ Correspondance exacte: "
                    f"'{detected_text}' -> '{cleaned_text}'"
                )
            return cleaned_text
        
        # Fuzzy matching fallback
        close_matches = get_close_matches(
            cleaned_text, self.character_names, n=1,
            cutoff=similarity_threshold
        )
        
        if close_matches:
            best_match = close_matches[0]
            if self.debug:
                print(
                    f"[ImageAnalyzer] ✅ Correspondance approximative: "
                    f"'{detected_text}' -> '{best_match}'"
                )
            return best_match
        
        # No match found - reject
        if self.debug:
            print(
                f"[ImageAnalyzer] ❌ REJETÉ (pas un personnage): "
                f"'{detected_text}'"
            )
        return ""

    def _get_roi(self, roi_name):
        # Fallback to default ROI config if no JSON config loaded
        if self.rois is None:
            if roi_name == 'timer':
                color = (0, 255, 0)
            elif roi_name == 'character1':
                color = (255, 0, 0)
            else:
                color = (0, 0, 255)
                
            return {
                'name': roi_name,
                'type': 'ocr',
                'boundaries': {
                    'color': color
                },
                'label': roi_name.upper()
            }
        
        for roi in self.rois:
            if roi['name'] == roi_name:
                # Convert list to tuple for OpenCV compatibility
                boundaries = roi.get('boundaries', {})
                if ('boundaries' in roi and 'color' in boundaries and
                        isinstance(boundaries['color'], list)):
                    roi['boundaries']['color'] = tuple(
                        roi['boundaries']['color']
                    )
                return roi
        return None

    def initialize_ocr(self):
        # Kept for compatibility - OCR status shown once in __init__
        pass


    def analyze_frame(self, frame, rois_to_analyze=None,
                      preprocessing: PreprocessingStep = PreprocessingStep.NONE):
        if rois_to_analyze is None:
            rois_to_analyze = ['timer', 'character1', 'character2']

        detection_results = {}

        for roi_name in rois_to_analyze:
            roi_image, boundaries = self._extract_roi(frame, roi_name)

            if roi_image is None or boundaries is None:
                if self.debug:
                    print(f"[ImageAnalyzer] ROI {roi_name} extraction failed")
                detection_results[roi_name] = ''
                continue

            if self.debug:
                width, height = roi_image.shape[1], roi_image.shape[0]
                print(
                    f"[ImageAnalyzer] ⬜ ROI {roi_name} extracted: "
                    f"{width}x{height} with boundaries={boundaries}"
                )
            
            self.debug_counter += 1
            
            roi_info = self._get_roi(roi_name)
            if roi_info:
                roi_type = roi_info.get('type', 'ocr')
            else:
                roi_type = 'ocr'
            
            if roi_type == 'pattern':
                if self.debug:
                    print(
                        f"[ImageAnalyzer] 🔍 ROI '{roi_name}' uses pattern "
                        f"matching"
                    )
                detection_results[roi_name] = self._analyze_pattern_roi(
                    roi_image, roi_info
                )
            else:
                # Récupérer le modèle OCR à utiliser depuis la config
                # (EasyOCR par défaut)
                if roi_info:
                    ocr_model = roi_info.get('model', 'easyocr')
                else:
                    ocr_model = 'easyocr'
                
                if self.debug:
                    print(
                        f"[ImageAnalyzer] 📝 ROI '{roi_name}' uses OCR "
                        f"processing with model: {ocr_model}"
                    )
                
                self.initialize_ocr()
                self.image_converter.set_debug_counter(self.debug_counter)
                
                enhanced = self.image_converter.enhance_for_ocr(
                    roi_image, roi_info, preprocessing
                )
                if enhanced is None:
                    if self.debug:
                        print(f"[ImageAnalyzer] Enhancement failed for ROI {roi_name}")
                    detection_results[roi_name] = ''
                    continue
                
                if self.debug:
                    print(
                        f"[ImageAnalyzer] 🔍 Enhanced image for "
                        f"'{roi_name}' ready for {ocr_model.upper()}"
                    )

                if ocr_model == 'easyocr':
                    detection_results[roi_name] = (
                        self._extract_text_with_easyocr(enhanced, roi_info)
                    )
                else:  # trocr fallback
                    if roi_name == 'timer':
                        detection_results[roi_name] = (
                            self._extract_timer_digits(enhanced, roi_info)
                        )
                    else:
                        detection_results[roi_name] = (
                            self._extract_character_name(enhanced, roi_info)
                        )
            

        if self.debug:
            print(
                f"[ImageAnalyzer] Final detection results: "
                f"{detection_results}"
            )

        if self.debug and self.debug_save_dir:
            annotated_frame = self.annotate_frame_with_rois(
                frame, 
                list(detection_results.keys()),
                show_text=True,
                detection_results=detection_results
            )
            
            timer_str = detection_results.get('timer', 'XX')
            char1_str = detection_results.get('character1', 'Unknown')
            char1_str = char1_str.replace(' ', '_')
            char2_str = detection_results.get('character2', 'Unknown')
            char2_str = char2_str.replace(' ', '_')
            
            debug_filename = (
                f"analyzed_frame_{self.debug_counter:04d}_t{timer_str}_"
                f"{char1_str}_vs_{char2_str}.jpg"
            )
            debug_path = os.path.join(self.debug_save_dir, debug_filename)
            
            os.makedirs(self.debug_save_dir, exist_ok=True)
            cv.imwrite(debug_path, annotated_frame)
            
            if self.debug:
                print(
                    f"[ImageAnalyzer] 💾 Image annotée sauvée: "
                    f"{debug_filename}"
                )
            
            detection_results['debug_image_filename'] = debug_filename
        
        return detection_results

    def visualize_rois(self, image_path, rois_to_show=None):
        if rois_to_show is None:
            rois_to_show = ['timer', 'character1', 'character2']

        image = cv.imread(image_path)
        if image is None:
            raise ValueError(f"Unable to load image: {image_path}")

        width, height = image.shape[1], image.shape[0]
        print(f"📐 Image dimensions: {width}x{height} pixels")

        self.annotate_frame_with_rois(
            image, rois_to_show, show_text=False
        )

        # Visualisation seulement - pas de sauvegarde automatique
        # La sauvegarde est gérée par les notebooks ou l'appelant si
        # nécessaire
        
        return None

    def annotate_frame_with_rois(self, frame, rois_to_show,
                                  show_text=True,
                                  detection_results=None):
        annotated = frame.copy()

        for roi_name in rois_to_show:
            roi_info = self._get_roi(roi_name)
            if not roi_info:
                continue
                
            _, boundaries = self._extract_roi(frame, roi_name)

            if boundaries is None:
                continue

            left_x, top_y, right_x, bottom_y = boundaries
            color = roi_info['boundaries']['color']

            cv.rectangle(annotated, (left_x, top_y), (right_x, bottom_y),
                        color, 2)

            if (show_text and detection_results and
                    roi_name in detection_results):
                text = detection_results[roi_name] or f"No {roi_name}"
            else:
                text = roi_info['label']

            font = cv.FONT_HERSHEY_SIMPLEX
            # Larger font for better readability
            scale = 0.7
            thickness = 2
            (text_width, text_height), _ = cv.getTextSize(
                text, font, scale, thickness
            )
            text_x = left_x + (right_x - left_x - text_width) // 2
            text_y = top_y - 10

            # Black background for text readability
            padding = 4
            bg_x1 = text_x - padding
            bg_y1 = text_y - text_height - padding
            bg_x2 = text_x + text_width + padding
            bg_y2 = text_y + padding
            
            cv.rectangle(annotated, (bg_x1, bg_y1), (bg_x2, bg_y2),
                        (0, 0, 0), -1)

            cv.putText(annotated, text, (text_x, text_y), font, scale,
                      color, thickness)

        return annotated

    def _extract_roi(self, image, roi_name):
        height, width = image.shape[:2]

        # Use direct ROI config if available
        if roi_name == 'timer' and self.timer_roi:
            return self._extract_roi_from_config(image, self.timer_roi)
        elif roi_name == 'character1' and self.character1_roi:
            return self._extract_roi_from_config(image,
                                                 self.character1_roi)
        elif roi_name == 'character2' and self.character2_roi:
            return self._extract_roi_from_config(image,
                                                 self.character2_roi)

        # Fallback to JSON config
        roi_info = self._get_roi(roi_name)
        if not roi_info:
            if self.debug:
                print(f"[ImageAnalyzer] Unknown ROI name: {roi_name}")
            return None, None
        
        boundaries = self._calculate_roi_boundaries(
            height, width, roi_info['boundaries']
        )

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
    
    def _extract_roi_from_config(self, image, roi_config):
        """Extrait une ROI à partir d'une configuration directe.
        
        Args:
            image: Image source
            roi_config: Dict avec left, top, right, bottom
        """
        height, width = image.shape[:2]
        
        # Convertir pourcentages en pixels
        left = int(roi_config['left'] * width)
        top = int(roi_config['top'] * height)
        right = int(roi_config['right'] * width)
        bottom = int(roi_config['bottom'] * height)
        
        # Valider les boundaries
        left_x, top_y, right_x, bottom_y = self._validate_boundaries(
            left_x=left, top_y=top, right_x=right, bottom_y=bottom,
            height=height, width=width, roi_name="direct_config"
        )
        
        if left_x is None:
            return None, None
            
        roi = image[top_y:bottom_y, left_x:right_x]
        return roi, (left_x, top_y, right_x, bottom_y)



    def _calculate_roi_boundaries(self, height, width,
                                  boundaries_config):
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
        del roi_info  # Parameter not used but kept for interface consistency
        if self.debug:
            print(f"[ImageAnalyzer] _extract_timer_digits: processing image shape {enhanced_image.shape}")
        
        if not self.trocr_available:
            if self.debug:
                print("[ImageAnalyzer] ❌ TrOCR non disponible pour extraction timer")
            return ""
        
        try:
            if len(enhanced_image.shape) == 3:
                # OpenCV uses BGR, PIL needs RGB
                pil_image = Image.fromarray(cv.cvtColor(enhanced_image, cv.COLOR_BGR2RGB))
            else:
                pil_image = Image.fromarray(enhanced_image).convert('RGB')
                
            if self.debug:
                print("[ImageAnalyzer] 🔄 Utilisation de TrOCR pour détection timer")
                
            # Prédiction TrOCR
            pixel_values = self.trocr_processor(pil_image, return_tensors="pt").pixel_values.to(self.trocr_device)
            generated_ids = self.trocr_model.generate(pixel_values)
            generated_text = self.trocr_processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            # Extract only digits, limit to 2 for SF6 timer format
            digits = ''.join(filter(str.isdigit, generated_text))
            if len(digits) > 2:
                digits = digits[:2]
            
            if self.debug:
                print(f"[ImageAnalyzer] TrOCR brut: '{generated_text}' -> digits: '{digits}'")
                
            
            return digits
            
        except Exception as e:
            if self.debug:
                print(f"[ImageAnalyzer] ❌ Erreur TrOCR timer: {e}")
            return ""

    def _extract_character_name(self, enhanced_image, roi_info=None):
        del roi_info  # Parameter not used but kept for interface consistency
        """Extrait le nom du personnage en utilisant TrOCR"""
        if self.debug:
            print(f"[ImageAnalyzer] _extract_character_name: processing image shape {enhanced_image.shape}")
        
        if not self.trocr_available:
            if self.debug:
                print("[ImageAnalyzer] ❌ TrOCR non disponible pour extraction character")
            return ""
        
        try:
            if len(enhanced_image.shape) == 3:
                # OpenCV uses BGR, PIL needs RGB
                pil_image = Image.fromarray(cv.cvtColor(enhanced_image, cv.COLOR_BGR2RGB))
            else:
                pil_image = Image.fromarray(enhanced_image).convert('RGB')
                
            if self.debug:
                print("[ImageAnalyzer] 🔄 Utilisation de TrOCR pour détection character")
                
            # Prédiction TrOCR
            pixel_values = self.trocr_processor(pil_image, return_tensors="pt").pixel_values.to(self.trocr_device)
            generated_ids = self.trocr_model.generate(pixel_values)
            generated_text = self.trocr_processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            # Nettoyer le résultat
            final_text = generated_text.strip()
            
            if self.debug:
                print(f"[ImageAnalyzer] TrOCR character: '{final_text}'")
                
            
            return final_text
            
        except Exception as e:
            if self.debug:
                print(f"[ImageAnalyzer] ❌ Erreur TrOCR character: {e}")
            return ""

    def _extract_text_with_easyocr(self, enhanced_image, roi_info=None):
        if self.debug:
            print(f"[ImageAnalyzer] _extract_text_with_easyocr: processing image shape {enhanced_image.shape}")
        
        if not self.easyocr_available:
            if self.debug:
                print("[ImageAnalyzer] ❌ EasyOCR non disponible")
            return ""
        
        try:
            if len(enhanced_image.shape) == 3:
                # Convert BGR to RGB for EasyOCR
                ocr_image = cv.cvtColor(enhanced_image, cv.COLOR_BGR2RGB)
            else:
                # Grayscale works directly with EasyOCR
                ocr_image = enhanced_image
                
            if self.debug:
                print("[ImageAnalyzer] 🔄 Utilisation de EasyOCR pour détection texte")
                
            # Returns list of (bbox, text, confidence)
            results = self.easyocr_reader.readtext(ocr_image)
            
            if not results:
                if self.debug:
                    print("[ImageAnalyzer] EasyOCR: Aucun texte détecté")
                return ""
            
            if self.debug:
                print(f"[ImageAnalyzer] EasyOCR détections multiples: {[(r[1], f'{r[2]:.3f}') for r in results]}")
            
            # Smart strategy for character ROIs: prioritize valid character names
            detected_text = ""
            confidence = 0.0
            
            if roi_info and roi_info.get('name', '').startswith('character') and self.character_names:
                for result in results:
                    text = result[1].strip().upper()
                    conf = result[2]
                    
                    # Check if valid character name (case-insensitive)
                    if text in self.character_names or get_close_matches(text, self.character_names, n=1, cutoff=0.6):
                        detected_text = result[1].strip()
                        confidence = conf
                        if self.debug:
                            print(f"[ImageAnalyzer] ✅ Nom de personnage trouvé: '{detected_text}' (confiance: {confidence:.3f})")
                        break
                
                # Fallback to highest confidence if no valid name found
                if not detected_text:
                    best_result = max(results, key=lambda x: x[2])
                    detected_text = best_result[1].strip()
                    confidence = best_result[2]
                    if self.debug:
                        print(f"[ImageAnalyzer] ⚠️ Aucun nom valide, prise du plus confiant: '{detected_text}' (confiance: {confidence:.3f})")
            else:
                # For other ROIs: take highest confidence
                best_result = max(results, key=lambda x: x[2])
                detected_text = best_result[1].strip()
                confidence = best_result[2]
            
            # Apply character name matching for character ROIs
            if roi_info and roi_info.get('name', '').startswith('character') and self.character_names:
                detected_text = self._match_character_name(detected_text)
            else:
                # Apply whitelist filtering for non-character ROIs (like timer)
                if roi_info and 'ocr_whitelist' in roi_info:
                    whitelist = roi_info['ocr_whitelist']
                    filtered_text = ''.join(char for char in detected_text if char in whitelist)
                    if self.debug and filtered_text != detected_text:
                        print(f"[ImageAnalyzer] EasyOCR texte filtré: '{detected_text}' -> '{filtered_text}'")
                    detected_text = filtered_text
            
            if self.debug:
                print(f"[ImageAnalyzer] EasyOCR résultat final: '{detected_text}' (confiance: {confidence:.3f})")
                
            
            return detected_text
            
        except Exception as e:
            if self.debug:
                print(f"[ImageAnalyzer] ❌ Erreur EasyOCR: {e}")
            return ""

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
        
        templates_dir = os.path.join('templates', roi_info['name'])
        
        if not os.path.exists(templates_dir):
            if self.debug:
                print(f"[ImageAnalyzer] ⚠️  Templates directory not found: {templates_dir}")
            return ''
        
        best_match = ''
        best_confidence = 0.0
        # Minimum confidence threshold for pattern matching
        confidence_threshold = 0.7
        
        for template_file in os.listdir(templates_dir):
            if not template_file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                continue
                
            template_path = os.path.join(templates_dir, template_file)
            template = cv.imread(template_path, cv.IMREAD_GRAYSCALE)
            
            if template is None:
                if self.debug:
                    print(f"[ImageAnalyzer] ⚠️  Could not load template: {template_path}")
                continue
            
            roi_gray = cv.cvtColor(roi_image, cv.COLOR_BGR2GRAY) if len(roi_image.shape) == 3 else roi_image
            
            # Try multiple matching methods for robustness
            methods = [cv.TM_CCOEFF_NORMED, cv.TM_CCORR_NORMED, cv.TM_SQDIFF_NORMED]
            
            for method in methods:
                try:
                    result = cv.matchTemplate(roi_gray, template, method)
                    _, max_val, _, _ = cv.minMaxLoc(result)
                    
                    # TM_SQDIFF_NORMED: lower = better match
                    if method == cv.TM_SQDIFF_NORMED:
                        confidence = 1.0 - max_val
                    else:
                        confidence = max_val
                    
                    if confidence > best_confidence and confidence >= confidence_threshold:
                        best_confidence = confidence
                        # Use filename without extension as result
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

