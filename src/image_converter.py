import cv2 as cv
import numpy as np
import os
from .preprocessing_steps import PreprocessingStep

class ImageConverter:
    """Gère les conversions et améliorations d'images pour l'OCR."""

    def __init__(self, debug=False, output_directory=None):
        self.debug = debug
        self.output_directory = output_directory or 'output'
        self.debug_counter = 0

    def enhance_for_ocr(self, image, region_info=None, preprocessing_steps: PreprocessingStep = PreprocessingStep.NONE):
        """
        Améliore l'image pour l'OCR en appliquant les étapes de preprocessing choisies.

        Args:
            image: Image à traiter
            region_info: Informations de la région
            preprocessing_steps: Étapes de preprocessing à appliquer (PreprocessingStep enum)
                               Exemples:
                               - PreprocessingStep.NONE (aucun preprocessing)
                               - PreprocessingStep.LIGHT (grayscale + normalisation)
                               - PreprocessingStep.STANDARD (preset recommandé)
                               - PreprocessingStep.GRAYSCALE | PreprocessingStep.THRESHOLD (combinaison)

        Returns:
            Image améliorée pour l'OCR (ou image originale si NONE)
        """
        if self.debug:
            print(f"[ImageConverter] enhance_for_ocr: input_shape={image.shape if image is not None else 'None'}")
            if preprocessing_steps == PreprocessingStep.NONE:
                print(f"[ImageConverter] 🚫 No preprocessing (NONE) - returning original image")
            else:
                print(f"[ImageConverter] 🔧 Applying preprocessing: {preprocessing_steps}")

        if image is None or image.size == 0:
            if self.debug:
                print("[ImageConverter] Invalid input image for enhancement")
            return None

        # Si aucune étape, retourner l'image originale
        if preprocessing_steps == PreprocessingStep.NONE:
            return image.copy()

        try:
            working_image = image.copy()
            return self._apply_enhancement_pipeline(working_image, region_info, preprocessing_steps)

        except cv.error as e:
            if self.debug:
                print(f"[ImageConverter] Enhancement error: {e}")
            print(f"⚠ Error enhancing image: {e}")
            return None

    def _apply_enhancement_pipeline(self, image, region_info=None,
                                   preprocessing_steps: PreprocessingStep = PreprocessingStep.AGGRESSIVE):
        """Apply image enhancement pipeline with selected steps."""
        working_image = image.copy()

        pipeline_steps = [
            (PreprocessingStep.GRAYSCALE, "Conversion en niveaux de gris",
             lambda img: self._convert_to_grayscale(img)),
            (PreprocessingStep.DENOISING, "Débruitage",
             lambda img: self._apply_denoising(img)),
            (PreprocessingStep.NORMALIZE, "Normalisation de l'histogramme",
             lambda img: self._apply_histogram_normalization(img)),
            (PreprocessingStep.CLAHE, "Enhancement CLAHE",
             lambda img: self._apply_clahe_enhancement(img)),
            (PreprocessingStep.THRESHOLD, "Seuillage binaire",
             lambda img: self._apply_binary_thresholding(img, region_info)),
            (PreprocessingStep.MORPHOLOGY, "Opérations morphologiques",
             lambda img: self._apply_morphological_operations(img, region_info)),
            (PreprocessingStep.UPSCALE, "Upscaling final",
             lambda img: self._apply_upscaling(img)),
        ]

        for step_type, step_name, step_function in pipeline_steps:
            if step_type in preprocessing_steps:
                self._log_debug(f"Executing: {step_name}")
                working_image = step_function(working_image)

        if self.debug:
            active_steps = preprocessing_steps.get_step_names()
            print(f"[ImageConverter] Enhancement pipeline complete with steps {active_steps}: {working_image.shape}")

        return working_image

    def _log_debug(self, message):
        """Log debug message if debug mode is enabled."""
        if self.debug:
            print(f"[ImageConverter] {message}")


    def _convert_to_grayscale(self, image):
        """Convertit l'image en niveaux de gris."""
        if self.debug:
            print("[ImageConverter] Step 1: Converting to grayscale (standard processing)")

        if len(image.shape) == 3:
            gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        self._save_debug_image(gray, "01_grayscale")
        return gray

    def _apply_denoising(self, image):
        """Applique le débruitage à l'image."""
        if self.debug:
            print("[ImageConverter] Step 2: Denoising with fastNlMeansDenoising")

        # Adapter le débruitage selon si l'image est en couleur ou en niveaux de gris
        if len(image.shape) == 3:
            denoised = cv.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)
        else:
            denoised = cv.fastNlMeansDenoising(image, None, h=10, templateWindowSize=7, searchWindowSize=21)

        self._save_debug_image(denoised, "02_denoised")
        return denoised

    def _apply_histogram_normalization(self, image):
        """Applique la normalisation de l'histogramme."""
        if self.debug:
            print("[ImageConverter] Step 3: Histogram normalization")

        normalized = cv.normalize(image, None, 0, 255, cv.NORM_MINMAX)
        self._save_debug_image(normalized, "03_normalized")
        return normalized

    def _apply_clahe_enhancement(self, image):
        """Applique l'amélioration CLAHE."""
        if self.debug:
            print("[ImageConverter] Step 4: Applying CLAHE for contrast enhancement")

        clahe = cv.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

        if len(image.shape) == 3:
            # Pour les images couleur, appliquer CLAHE sur chaque canal
            lab = cv.cvtColor(image, cv.COLOR_BGR2LAB)
            lab[:,:,0] = clahe.apply(lab[:,:,0])  # Appliquer sur le canal L (luminance)
            contrast_enhanced = cv.cvtColor(lab, cv.COLOR_LAB2BGR)
        else:
            # Pour les images en niveaux de gris
            contrast_enhanced = clahe.apply(image)

        self._save_debug_image(contrast_enhanced, "04_clahe")
        return contrast_enhanced

    def _apply_binary_thresholding(self, image, region_info=None):
        """Applique le seuillage binaire pour extraire le texte haute-contraste (GoProTimeOCR technique)."""
        if self.debug:
            print("[ImageConverter] Step 5: Applying binary thresholding for high-contrast text extraction")

        # Paramètres adaptatifs selon le type de ROI
        if region_info and region_info.get('name') == 'timer':
            threshold_value = 70  # Plus agressif pour les chiffres
            max_value = 255
        else:
            threshold_value = 50  # Plus doux pour les noms de personnages
            max_value = 255

        if self.debug:
            print(f"[ImageConverter] Using threshold values: {threshold_value}/{max_value}")

        # Convertir en niveaux de gris si nécessaire
        if len(image.shape) == 3:
            gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Appliquer le seuillage binaire
        _, thresh = cv.threshold(gray, threshold_value, max_value, cv.THRESH_BINARY)

        self._save_debug_image(thresh, "05_binary_threshold")

        if self.debug:
            print(f"[ImageConverter] Binary thresholding applied: {thresh.shape}")

        return thresh

    def _apply_morphological_operations(self, image, region_info=None):
        """Applique les opérations morphologiques pour améliorer la structure du texte (GoProTimeOCR technique)."""
        if self.debug:
            print("[ImageConverter] Step 6: Applying morphological operations for text enhancement")

        # Paramètres adaptatifs selon le type de ROI
        if region_info and region_info.get('name') == 'timer':
            kernel_size = (2, 2)  # Plus petit pour préserver les détails des chiffres
            operation = 'dilation'  # Connecter les segments cassés
            iterations = 1
        else:
            kernel_size = (1, 1)  # Très léger pour les noms de personnages
            operation = 'closing'   # Fermer les petits trous
            iterations = 1

        if self.debug:
            print(f"[ImageConverter] Morphological operation: {operation}, kernel: {kernel_size}, iterations: {iterations}")

        kernel = np.ones(kernel_size, np.uint8)

        if operation == 'dilation':
            result = cv.dilate(image, kernel, iterations=iterations)
        elif operation == 'erosion':
            result = cv.erode(image, kernel, iterations=iterations)
        elif operation == 'closing':
            result = cv.morphologyEx(image, cv.MORPH_CLOSE, kernel)
        elif operation == 'opening':
            result = cv.morphologyEx(image, cv.MORPH_OPEN, kernel)
        else:
            result = image.copy()

        self._save_debug_image(result, "06_morphological")

        if self.debug:
            print(f"[ImageConverter] Morphological operations applied: {result.shape}")

        return result

    def _apply_upscaling(self, image):
        """Applique l'upscaling final."""
        if self.debug:
            print("[ImageConverter] Step 7: Upscaling result 3x for optimal OCR")

        upscaled = cv.resize(image, None, fx=3, fy=3, interpolation=cv.INTER_CUBIC)
        self._save_debug_image(upscaled, "07_final")
        return upscaled


    def set_debug_counter(self, counter):
        """Permet de synchroniser le compteur de debug avec ImageAnalyzer."""
        self.debug_counter = counter

    def _save_debug_image(self, image, step_name):
        """Sauvegarde les images intermédiaires du preprocessing si debug activé."""
        if not self.debug:
            return

        try:
            self._ensure_output_directories()
            debug_dir = os.path.join(self.output_directory, "debug_preprocessing")
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)

            filename = f"debug_{self.debug_counter:03d}_{step_name}.png"
            filepath = os.path.join(debug_dir, filename)
            cv.imwrite(filepath, image)

            if self.debug:
                print(f"[ImageConverter] Debug image saved: {filepath}")

        except Exception as e:
            if self.debug:
                print(f"[ImageConverter] Failed to save debug image: {e}")

    def _ensure_output_directories(self):
        """S'assure que les répertoires de sortie existent."""
        if not os.path.exists(self.output_directory):
            os.makedirs(self.output_directory)