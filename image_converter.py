import cv2 as cv
import numpy as np
import os

class ImageConverter:
    """Gère les conversions et améliorations d'images pour l'OCR."""
    
    def __init__(self, debug=False, output_directory=None):
        self.debug = debug
        self.output_directory = output_directory or 'output'
        self.debug_counter = 0
    
    def enhance_for_ocr(self, image, region_info=None):
        """
        Améliore l'image pour l'OCR en appliquant les meilleures pratiques EasyOCR.
        Utilise les informations de couleur de police si disponibles.
        
        Args:
            image: Image à traiter
            region_info: Informations de la région (inclut font_color si disponible)
        
        Returns:
            Image améliorée pour l'OCR
        """
        if self.debug:
            print(f"[ImageConverter] enhance_for_ocr: input_shape={image.shape if image is not None else 'None'}")
            if region_info and 'font_color' in region_info:
                print(f"[ImageConverter] 🔍 Font color enhancement enabled for region '{region_info['name']}'")
                print(f"[ImageConverter] 🎯 Target colors: lighter={region_info['font_color']['lighter']}, darker={region_info['font_color']['darker']}")
            else:
                print(f"[ImageConverter] ⚪ Standard enhancement (no font color targeting)")
        
        if image is None or image.size == 0:
            if self.debug:
                print("[ImageConverter] Invalid input image for enhancement")
            return None

        try:
            working_image = image.copy()
            return self._apply_enhancement_pipeline(working_image, region_info)
            
        except cv.error as e:
            if self.debug:
                print(f"[ImageConverter] Enhancement error: {e}")
            print(f"⚠ Error enhancing image: {e}")
            return None
    
    def _apply_enhancement_pipeline(self, image, region_info=None):
        """
        Applique le pipeline d'amélioration selon la configuration de la région.
        
        Args:
            image: Image à traiter
            region_info: Informations de la région
            
        Returns:
            Image améliorée
        """
        working_image = image.copy()
        has_font_color = region_info and 'font_color' in region_info
        
        # Étape 0: Amélioration par couleur de police si spécifiée
        if has_font_color:
            working_image = self._apply_font_color_enhancement(working_image, region_info)
        
        # Étape 1: Conversion en niveaux de gris (SAUF si font_color est spécifiée)
        if has_font_color:
            working_image = self._preserve_color_info(working_image, region_info)
        else:
            working_image = self._convert_to_grayscale(working_image)
        
        # Étape 2: Débruitage
        working_image = self._apply_denoising(working_image)
        
        # Étape 3: Normalisation de l'histogramme
        working_image = self._apply_histogram_normalization(working_image)
        
        # Étape 4: CLAHE
        working_image = self._apply_clahe_enhancement(working_image)
        
        # Étape 7: Upscaling final
        working_image = self._apply_upscaling(working_image)
        
        if self.debug:
            print(f"[ImageConverter] Enhancement pipeline complete: {working_image.shape}")
        return working_image
    
    def _apply_font_color_enhancement(self, image, region_info):
        """Applique l'amélioration par couleur de police."""
        if self.debug:
            print(f"[ImageConverter] Step 0: 🌈 Applying font color enhancement for '{region_info['name']}'")
            print(f"[ImageConverter] 🔬 Creating color masks for BGR lighter={region_info['font_color']['lighter']} and darker={region_info['font_color']['darker']}")
        
        enhanced = self._enhance_by_font_color(image, region_info['font_color'])
        self._save_debug_image(enhanced, "00_color_enhanced")
        
        if self.debug:
            print(f"[ImageConverter] ✅ Color-based enhancement applied - text should be more prominent")
        return enhanced
    
    def _preserve_color_info(self, image, region_info):
        """Préserve les informations de couleur pour les régions avec font_color."""
        if self.debug:
            print(f"[ImageConverter] Step 1: ⚠️  SKIPPING grayscale conversion for '{region_info['name']}' (preserving color info)")
            print(f"[ImageConverter] 🎨 Color information preserved for font_color-based OCR")
        
        preserved = image.copy()
        self._save_debug_image(preserved, "01_color_preserved")
        return preserved
    
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
    
    def _apply_upscaling(self, image):
        """Applique l'upscaling final."""
        if self.debug:
            print("[ImageConverter] Step 7: Upscaling result 3x for optimal OCR")
        
        upscaled = cv.resize(image, None, fx=3, fy=3, interpolation=cv.INTER_CUBIC)
        self._save_debug_image(upscaled, "07_final")
        return upscaled

    def _enhance_by_font_color(self, image, font_color_config):
        """
        Améliore l'image en isolant les couleurs de police spécifiées.
        Crée un masque pour les couleurs lighter et darker, puis améliore le contraste.
        
        Args:
            image: Image BGR
            font_color_config: Dict avec 'lighter' et 'darker' en BGR
            
        Returns:
            Image améliorée avec le texte de couleur spécifiée renforcé
        """
        if self.debug:
            print(f"[ImageConverter] 🔍 _enhance_by_font_color: Processing font colors {font_color_config}")
        
        # Convertir en HSV pour une meilleure sélection de couleurs
        hsv = cv.cvtColor(image, cv.COLOR_BGR2HSV)
        if self.debug:
            print(f"[ImageConverter] 🔄 Converted BGR to HSV for better color selection")
        
        # Créer des masques pour les couleurs lighter et darker
        masks = []
        
        for color_type, bgr_color in font_color_config.items():
            if self.debug:
                print(f"[ImageConverter] 🎨 Processing {color_type} font color: BGR{bgr_color}")
            
            # Convertir BGR vers HSV pour le seuillage
            bgr_array = np.uint8([[bgr_color]])
            hsv_color = cv.cvtColor(bgr_array, cv.COLOR_BGR2HSV)[0][0]
            
            # Définir une plage de tolérance pour la couleur
            tolerance = 20  # Ajustable selon les besoins
            lower_bound = np.array([
                max(0, hsv_color[0] - tolerance),
                max(0, hsv_color[1] - 50), 
                max(0, hsv_color[2] - 50)
            ])
            upper_bound = np.array([
                min(179, hsv_color[0] + tolerance),
                255,
                255
            ])
            
            # Créer le masque pour cette couleur
            mask = cv.inRange(hsv, lower_bound, upper_bound)
            masks.append(mask)
            
            if self.debug:
                print(f"[ImageConverter] 📊 {color_type} → HSV{tuple(hsv_color)} → Range[{tuple(lower_bound)} - {tuple(upper_bound)}]")
                mask_pixels = np.count_nonzero(mask)
                total_pixels = mask.shape[0] * mask.shape[1]
                percentage = (mask_pixels / total_pixels) * 100
                print(f"[ImageConverter] 🎯 Color mask captured {mask_pixels}/{total_pixels} pixels ({percentage:.1f}%)")
        
        # Combiner tous les masques
        combined_mask = np.zeros_like(masks[0])
        for mask in masks:
            combined_mask = cv.bitwise_or(combined_mask, mask)
        
        if self.debug:
            combined_pixels = np.count_nonzero(combined_mask)
            total_pixels = combined_mask.shape[0] * combined_mask.shape[1]
            combined_percentage = (combined_pixels / total_pixels) * 100
            print(f"[ImageConverter] 🔗 Combined mask statistics: {combined_pixels}/{total_pixels} pixels ({combined_percentage:.1f}%)")
        
        # Appliquer le masque pour isoler le texte coloré
        result = image.copy()
        
        # Assombrir le fond (zones non-masquées)
        background_mask = cv.bitwise_not(combined_mask)
        result[background_mask > 0] = result[background_mask > 0] * 0.3  # Réduire l'intensité du fond
        
        # Éclaircir le texte (zones masquées)
        result[combined_mask > 0] = np.minimum(result[combined_mask > 0] * 1.5, 255)  # Augmenter l'intensité du texte
        
        if self.debug:
            print(f"[ImageConverter] ✨ Font color enhancement applied: background darkened (x0.3), text brightened (x1.5)")
            print(f"[ImageConverter] 🎯 Enhanced image ready for OCR processing")
        
        return result.astype(np.uint8)
    
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