import cv2 as cv
import numpy as np
import easyocr
import os
import argparse
import sys
from difflib import get_close_matches

OUTPUT_DIRECTORY = 'output'
ANALYZED_FRAMES_SUBDIRECTORY = 'analyzed'

# Contexte couleur pour les variations (en HSV) - Structure unique fusionnée
VALID_VARIATIONS = {
    'C': {
        'color_ranges': {
            'darker': np.array([120, 50, 50]),   # Violet foncé
            'lighter': np.array([160, 255, 255]) # Violet clair
        }
    },
    'M': {
        'color_ranges': {
            'darker': np.array([10, 100, 100]),  # Orange foncé
            'lighter': np.array([25, 255, 255])  # Orange clair
        }
    },
    'D': {
        'color_ranges': {
            'darker': np.array([90, 50, 100]),   # Bleu clair foncé
            'lighter': np.array([110, 255, 255]) # Bleu clair
        }
    }
}

def calculate_street_fighter_timer_boundaries(image_height, image_width):
    timer_top_position_percentage = 0.04
    timer_bottom_position_percentage = 0.15
    timer_left_position_percentage = 0.45
    timer_right_position_percentage = 0.55

    timer_top_boundary = int(image_height * timer_top_position_percentage)
    timer_bottom_boundary = int(image_height * timer_bottom_position_percentage)
    timer_left_boundary = int(image_width * timer_left_position_percentage)
    timer_right_boundary = int(image_width * timer_right_position_percentage)

    return timer_left_boundary, timer_top_boundary, timer_right_boundary, timer_bottom_boundary

def calculate_street_fighter_character1_boundaries(image_height, image_width):
    character1_top_position_percentage = 0.02
    character1_bottom_position_percentage = 0.1
    character1_left_position_percentage = 0
    character1_right_position_percentage = 0.1

    character1_top_boundary = int(image_height * character1_top_position_percentage)
    character1_bottom_boundary = int(image_height * character1_bottom_position_percentage)
    character1_left_boundary = int(image_width * character1_left_position_percentage)
    character1_right_boundary = int(image_width * character1_right_position_percentage)

    return character1_left_boundary, character1_top_boundary, character1_right_boundary, character1_bottom_boundary

def calculate_street_fighter_character2_boundaries(image_height, image_width):
    character2_top_position_percentage = 0.02
    character2_bottom_position_percentage = 0.1
    character2_left_position_percentage = 0.9
    character2_right_position_percentage = 1

    character2_top_boundary = int(image_height * character2_top_position_percentage)
    character2_bottom_boundary = int(image_height * character2_bottom_position_percentage)
    character2_left_boundary = int(image_width * character2_left_position_percentage)
    character2_right_boundary = int(image_width * character2_right_position_percentage)

    return character2_left_boundary, character2_top_boundary, character2_right_boundary, character2_bottom_boundary

def calculate_street_fighter_variation1_boundaries(image_height, image_width):
    variation1_top_position_percentage = 0.02
    variation1_bottom_position_percentage = 0.05
    variation1_left_position_percentage = 0.1
    variation1_right_position_percentage = 0.15

    variation1_top_boundary = int(image_height * variation1_top_position_percentage)
    variation1_bottom_boundary = int(image_height * variation1_bottom_position_percentage)
    variation1_left_boundary = int(image_width * variation1_left_position_percentage)
    variation1_right_boundary = int(image_width * variation1_right_position_percentage)

    return variation1_left_boundary, variation1_top_boundary, variation1_right_boundary, variation1_bottom_boundary

def calculate_street_fighter_variation2_boundaries(image_height, image_width):
    variation2_top_position_percentage = 0.02
    variation2_bottom_position_percentage = 0.05
    variation2_left_position_percentage = 0.85
    variation2_right_position_percentage = 0.9

    variation2_top_boundary = int(image_height * variation2_top_position_percentage)
    variation2_bottom_boundary = int(image_height * variation2_bottom_position_percentage)
    variation2_left_boundary = int(image_width * variation2_left_position_percentage)
    variation2_right_boundary = int(image_width * variation2_right_position_percentage)

    return variation2_left_boundary, variation2_top_boundary, variation2_right_boundary, variation2_bottom_boundary

def validate_region_boundaries(left_x, top_y, right_x, bottom_y, image_height, image_width, region_name):
    """Valide et corrige les coordonnées d'une région pour éviter les erreurs"""
    # Clamp les coordonnées dans les limites de l'image
    left_x = max(0, min(left_x, image_width - 1))
    top_y = max(0, min(top_y, image_height - 1))
    right_x = max(left_x + 1, min(right_x, image_width))
    bottom_y = max(top_y + 1, min(bottom_y, image_height))

    # Vérifier que la région a une taille minimale
    width = right_x - left_x
    height = bottom_y - top_y

    if width < 1 or height < 1:
        print(f"⚠ Région '{region_name}' trop petite ou invalide: {width}x{height} pixels")
        return None, None, None, None

    return left_x, top_y, right_x, bottom_y

def analyze_dominant_color_in_region(region_image):
    """Analyse la couleur dominante dans une région pour aider à identifier la variation"""
    if region_image is None or region_image.size == 0:
        return None, 0.0

    # Convertir en HSV pour une meilleure analyse des couleurs
    hsv_image = cv.cvtColor(region_image, cv.COLOR_BGR2HSV)

    best_match = None
    best_coverage = 0.0
    color_analysis = {}

    for variation, variation_data in VALID_VARIATIONS.items():
        color_range = variation_data['color_ranges']
        # Créer un masque pour cette couleur
        mask = cv.inRange(hsv_image, color_range['darker'], color_range['lighter'])

        # Calculer le pourcentage de pixels correspondants
        coverage = np.sum(mask > 0) / (mask.shape[0] * mask.shape[1]) * 100
        color_analysis[variation] = coverage

        if coverage > best_coverage:
            best_coverage = coverage
            best_match = variation

    print(f"🎨 Analyse couleur: {color_analysis}")

    # Seuil minimum pour considérer une couleur comme dominante
    if best_coverage > 5.0:  # Au moins 5% de pixels correspondants
        return best_match, best_coverage
    else:
        return None, 0.0

def create_color_enhanced_image_for_variation(region_image, predicted_variation):
    """Crée une version améliorée de l'image en mettant en valeur la couleur prédite"""
    if region_image is None or predicted_variation not in VALID_VARIATIONS:
        return None

    # Convertir en HSV
    hsv_image = cv.cvtColor(region_image, cv.COLOR_BGR2HSV)

    # Créer un masque pour la couleur prédite avec des tolérances élargies
    color_range = VALID_VARIATIONS[predicted_variation]['color_ranges']

    # Élargir les tolérances pour capturer plus de nuances
    darker_expanded = color_range['darker'].copy()
    lighter_expanded = color_range['lighter'].copy()

    darker_expanded[1] = max(0, darker_expanded[1] - 30)    # Saturation plus basse
    darker_expanded[2] = max(0, darker_expanded[2] - 50)    # Valeur plus basse
    lighter_expanded[1] = min(255, lighter_expanded[1])     # Saturation max
    lighter_expanded[2] = min(255, lighter_expanded[2])     # Valeur max

    mask = cv.inRange(hsv_image, darker_expanded, lighter_expanded)

    # Créer une image où seule la couleur cible est conservée
    color_isolated = cv.bitwise_and(region_image, region_image, mask=mask)

    # Convertir en niveaux de gris pour OCR
    gray_isolated = cv.cvtColor(color_isolated, cv.COLOR_BGR2GRAY)

    # Améliorer le contraste des pixels non-noirs
    enhanced = gray_isolated.copy()
    enhanced[enhanced > 0] = 255  # Rendre les pixels détectés complètement blancs

    return enhanced

def extract_street_fighter_timer_region(input_image):
    image_height, image_width = input_image.shape[:2]

    left_x, top_y, right_x, bottom_y = calculate_street_fighter_timer_boundaries(image_height, image_width)
    left_x, top_y, right_x, bottom_y = validate_region_boundaries(left_x, top_y, right_x, bottom_y, image_height, image_width, 'timer')

    if left_x is None:
        return None, None

    timer_region = input_image[top_y:bottom_y, left_x:right_x]
    timer_boundaries = (left_x, top_y, right_x, bottom_y)

    return timer_region, timer_boundaries

def extract_street_fighter_character1_region(input_image):
    image_height, image_width = input_image.shape[:2]

    left_x, top_y, right_x, bottom_y = calculate_street_fighter_character1_boundaries(image_height, image_width)
    left_x, top_y, right_x, bottom_y = validate_region_boundaries(left_x, top_y, right_x, bottom_y, image_height, image_width, 'character1')

    if left_x is None:
        return None, None

    character1_region = input_image[top_y:bottom_y, left_x:right_x]
    character1_boundaries = (left_x, top_y, right_x, bottom_y)

    return character1_region, character1_boundaries

def extract_street_fighter_character2_region(input_image):
    image_height, image_width = input_image.shape[:2]

    left_x, top_y, right_x, bottom_y = calculate_street_fighter_character2_boundaries(image_height, image_width)
    left_x, top_y, right_x, bottom_y = validate_region_boundaries(left_x, top_y, right_x, bottom_y, image_height, image_width, 'character2')

    if left_x is None:
        return None, None

    character2_region = input_image[top_y:bottom_y, left_x:right_x]
    character2_boundaries = (left_x, top_y, right_x, bottom_y)

    return character2_region, character2_boundaries

def extract_street_fighter_variation1_region(input_image):
    image_height, image_width = input_image.shape[:2]

    left_x, top_y, right_x, bottom_y = calculate_street_fighter_variation1_boundaries(image_height, image_width)
    left_x, top_y, right_x, bottom_y = validate_region_boundaries(left_x, top_y, right_x, bottom_y, image_height, image_width, 'variation1')

    if left_x is None:
        return None, None

    variation1_region = input_image[top_y:bottom_y, left_x:right_x]
    variation1_boundaries = (left_x, top_y, right_x, bottom_y)

    return variation1_region, variation1_boundaries

def extract_street_fighter_variation2_region(input_image):
    image_height, image_width = input_image.shape[:2]

    left_x, top_y, right_x, bottom_y = calculate_street_fighter_variation2_boundaries(image_height, image_width)
    left_x, top_y, right_x, bottom_y = validate_region_boundaries(left_x, top_y, right_x, bottom_y, image_height, image_width, 'variation2')

    if left_x is None:
        return None, None

    variation2_region = input_image[top_y:bottom_y, left_x:right_x]
    variation2_boundaries = (left_x, top_y, right_x, bottom_y)

    return variation2_region, variation2_boundaries

def extract_selected_regions_from_image(input_image, region_names):
    available_regions = {
        'timer': extract_street_fighter_timer_region,
        'character1': extract_street_fighter_character1_region,
        'character2': extract_street_fighter_character2_region,
        'variation1': extract_street_fighter_variation1_region,
        'variation2': extract_street_fighter_variation2_region
    }

    extracted_regions = {}

    for region_name in region_names:
        if region_name in available_regions:
            region_data, region_boundaries = available_regions[region_name](input_image)
            if region_data is not None and region_boundaries is not None:
                extracted_regions[region_name] = {
                    'region': region_data,
                    'boundaries': region_boundaries
                }
            else:
                print(f"⚠ Région '{region_name}' ignorée (coordonnées invalides)")
        else:
            print(f"⚠ Région '{region_name}' non reconnue. Régions disponibles: {list(available_regions.keys())}")

    return extracted_regions

def enhance_image_for_ocr_recognition(input_image, is_variation=False):
    """Améliore l'image pour la reconnaissance OCR avec traitement spécial pour les variations"""
    # Vérifier que l'image n'est pas vide
    if input_image is None or input_image.size == 0:
        print("⚠ Image vide reçue pour l'amélioration OCR")
        return None

    try:
        grayscale_image = cv.cvtColor(input_image, cv.COLOR_BGR2GRAY)

        if is_variation:
            # Traitement spécial pour les variations (une seule lettre)
            # Augmenter le contraste plus fortement
            adaptive_histogram_equalizer = cv.createCLAHE(clipLimit=3.0, tileGridSize=(4,4))
            enhanced_grayscale = adaptive_histogram_equalizer.apply(grayscale_image)

            # Upscaling plus important pour les petites lettres
            upscaled_image = cv.resize(enhanced_grayscale, None, fx=4, fy=4, interpolation=cv.INTER_CUBIC)

            # Appliquer un seuillage adaptatif pour améliorer la netteté
            binary_image = cv.adaptiveThreshold(upscaled_image, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C, cv.THRESH_BINARY, 11, 2)

            return binary_image
        else:
            # Traitement normal pour les autres régions
            adaptive_histogram_equalizer = cv.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced_grayscale = adaptive_histogram_equalizer.apply(grayscale_image)
            upscaled_image = cv.resize(enhanced_grayscale, None, fx=2, fy=2, interpolation=cv.INTER_CUBIC)
            return upscaled_image

    except cv.error as e:
        print(f"⚠ Erreur lors de l'amélioration d'image: {e}")
        return None

def correct_variation_with_context(detected_text):
    """Corrige le texte détecté pour les variations en utilisant le contexte C/M/D"""
    if not detected_text:
        return ''

    # Nettoyer le texte détecté (garder seulement les lettres)
    cleaned_text = ''.join(filter(str.isalpha, detected_text.upper()))

    if not cleaned_text:
        return ''

    # Prendre seulement le premier caractère (variations = 1 lettre)
    first_char = cleaned_text[0]

    # Correction basée sur les similarités visuelles communes
    corrections = {
        'O': 'C',    # O confondu avec C
        '0': 'C',    # 0 confondu avec C
        'Q': 'C',    # Q confondu avec C
        'G': 'C',    # G confondu avec C
        'N': 'M',    # N confondu avec M
        'H': 'M',    # H confondu avec M
        'P': 'D',    # P confondu avec D
        'B': 'D',    # B confondu avec D
        'R': 'D',    # R confondu avec D
    }

    # Appliquer les corrections si nécessaire
    corrected_char = corrections.get(first_char, first_char)

    # Vérifier si le caractère corrigé est valide
    if corrected_char in VALID_VARIATIONS:
        return corrected_char

    # Sinon, trouver la correspondance la plus proche
    closest_matches = get_close_matches(corrected_char, list(VALID_VARIATIONS.keys()), n=1, cutoff=0.3)
    if closest_matches:
        return closest_matches[0]
    
    # En dernier recours, retourner le texte original nettoyé
    return corrected_char if corrected_char.isalpha() else ''

def detect_variation_with_color_context(region_image, enhanced_region, ocr_reader, region_name):
    """Détecte la variation en utilisant le contexte couleur ET OCR"""
    
    # Étape 1: Analyser la couleur dominante
    predicted_variation, confidence = analyze_dominant_color_in_region(region_image)
    
    if predicted_variation and confidence > 15.0:  # Confiance élevée dans la couleur
        print(f"🎨 {region_name}: Couleur détectée → {predicted_variation} (confiance: {confidence:.1f}%)")
        
        # Étape 2: Créer une image améliorée basée sur la couleur
        color_enhanced = create_color_enhanced_image_for_variation(region_image, predicted_variation)
        
        if color_enhanced is not None:
            # Upscaler l'image améliorée par couleur
            color_enhanced_upscaled = cv.resize(color_enhanced, None, fx=4, fy=4, interpolation=cv.INTER_CUBIC)
            
            # Tenter OCR sur l'image améliorée par couleur
            try:
                ocr_results = ocr_reader.readtext(
                    color_enhanced_upscaled,
                    allowlist='CMD',
                    paragraph=False,
                    min_size=1
                )
                
                if ocr_results:
                    detected_text = ''.join([result[1] for result in ocr_results])
                    corrected = correct_variation_with_context(detected_text)
                    
                    # Vérifier si le résultat OCR correspond à la prédiction couleur
                    if corrected == predicted_variation:
                        print(f"✅ {region_name}: Couleur + OCR concordent → {corrected}")
                        return corrected
                    elif corrected in VALID_VARIATIONS:
                        print(f"🔀 {region_name}: OCR diffère de la couleur. OCR: {corrected}, Couleur: {predicted_variation}")
                        # Faire confiance à l'OCR si il donne un résultat valide
                        return corrected
            except:
                pass
        
        # Si l'OCR ne fonctionne pas bien, faire confiance à la couleur
        if confidence > 25.0:  # Très haute confiance dans la couleur
            print(f"🎨 {region_name}: Haute confiance couleur → {predicted_variation}")
            return predicted_variation
    
    # Étape 3: Fallback vers la méthode OCR classique
    print(f"📝 {region_name}: Fallback vers OCR classique")
    return detect_variation_with_multiple_attempts(enhanced_region, ocr_reader, region_name)

def detect_variation_with_multiple_attempts(enhanced_region, ocr_reader, region_name):
    """Tente plusieurs approches pour détecter les variations (méthode classique)"""
    
    # Tentative 1: OCR normal avec allowlist restreinte
    try:
        ocr_results_restricted = ocr_reader.readtext(
            enhanced_region, 
            allowlist='CMD',  # Restreindre aux seules lettres possibles
            paragraph=False
        )
        
        if ocr_results_restricted:
            detected_text = ''.join([result[1] for result in ocr_results_restricted])
            corrected = correct_variation_with_context(detected_text)
            if corrected:
                print(f"🎯 {region_name} détecté avec allowlist: {corrected}")
                return corrected
    except:
        pass
    
    # Tentative 2: OCR normal puis correction
    try:
        ocr_results_normal = ocr_reader.readtext(enhanced_region, paragraph=False)
        if ocr_results_normal:
            detected_text = ''.join([result[1] for result in ocr_results_normal])
            corrected = correct_variation_with_context(detected_text)
            if corrected:
                print(f"🔧 {region_name} corrigé: '{detected_text}' → '{corrected}'")
                return corrected
    except:
        pass
    
    # Tentative 3: OCR avec paramètres plus agressifs
    try:
        ocr_results_aggressive = ocr_reader.readtext(
            enhanced_region,
            allowlist='CMDOQ0NHPBR',  # Inclure les caractères souvent confondus
            paragraph=False,
            min_size=1,
            text_threshold=0.3
        )
        
        if ocr_results_aggressive:
            detected_text = ''.join([result[1] for result in ocr_results_aggressive])
            corrected = correct_variation_with_context(detected_text)
            if corrected:
                print(f"⚡ {region_name} détecté agressivement: '{detected_text}' → '{corrected}'")
                return corrected
    except:
        pass
    
    print(f"❌ {region_name}: Aucune variation détectée")
    return ''

def visualize_regions_only(screenshot_file_path):
    """Mode dry-run : dessine seulement les régions sans analyse OCR"""
    # Régions à visualiser - Modifiable facilement
    regions_to_analyze = ['timer', 'character1', 'character2', 'variation1', 'variation2']
    
    if not os.path.exists(screenshot_file_path):
        raise FileNotFoundError(f"Le fichier image '{screenshot_file_path}' n'existe pas.")

    if not os.path.exists(OUTPUT_DIRECTORY):
        os.makedirs(OUTPUT_DIRECTORY)
    
    analyzed_frames_path = os.path.join(OUTPUT_DIRECTORY, ANALYZED_FRAMES_SUBDIRECTORY)
    if not os.path.exists(analyzed_frames_path):
        os.makedirs(analyzed_frames_path)
    
    original_image = cv.imread(screenshot_file_path)
    if original_image is None:
        raise ValueError(f"Impossible de charger l'image : {screenshot_file_path}")
    
    print(f"📐 Dimensions de l'image: {original_image.shape[1]}x{original_image.shape[0]} pixels")
    
    output_image_with_regions = original_image.copy()
    
    # Extraction des régions sélectionnées (sans OCR)
    extracted_regions = extract_selected_regions_from_image(original_image, regions_to_analyze)
    
    # Couleurs pour chaque type de région
    region_colors = {
        'timer': (0, 255, 0),        # Vert
        'character1': (255, 0, 0),   # Bleu
        'character2': (0, 0, 255),   # Rouge
        'variation1': (255, 255, 0), # Cyan
        'variation2': (255, 0, 255)  # Magenta
    }
    
    # Labels pour chaque région
    region_labels = {
        'timer': 'TIMER',
        'character1': 'PLAYER 1',
        'character2': 'PLAYER 2',
        'variation1': 'VAR1 (C=Violet/M=Orange/D=Bleu)',
        'variation2': 'VAR2 (C=Violet/M=Orange/D=Bleu)'
    }
    
    for region_name, region_data in extracted_regions.items():
        left_x, top_y, right_x, bottom_y = region_data['boundaries']
        
        print(f"📍 {region_name}: ({left_x}, {top_y}) à ({right_x}, {bottom_y}) - Taille: {right_x-left_x}x{bottom_y-top_y}")
        
        # Analyse couleur pour les variations
        if region_name in ['variation1', 'variation2']:
            predicted_variation, confidence = analyze_dominant_color_in_region(region_data['region'])
            if predicted_variation:
                print(f"   🎨 Couleur prédite: {predicted_variation} (confiance: {confidence:.1f}%)")
        
        # Dessiner le rectangle
        color = region_colors.get(region_name, (255, 255, 255))
        cv.rectangle(output_image_with_regions, (left_x, top_y), (right_x, bottom_y), color, 2)
        
        # Ajouter le label
        label_text = region_labels.get(region_name, region_name.upper())
        text_font = cv.FONT_HERSHEY_SIMPLEX
        text_scale = 0.5
        text_thickness = 2
        (text_width, text_height), _ = cv.getTextSize(label_text, text_font, text_scale, text_thickness)
        centered_text_x = left_x + (right_x - left_x - text_width) // 2
        text_y_position = top_y - 10
        
        cv.putText(output_image_with_regions, label_text,
                  (centered_text_x, text_y_position),
                  text_font, text_scale, color, text_thickness)
    
    # Sauvegarder l'image avec les régions visualisées
    dry_run_filename = os.path.join(analyzed_frames_path, 'regions_' + os.path.basename(screenshot_file_path))
    cv.imwrite(dry_run_filename, output_image_with_regions)
    
    print(f"✓ Régions visualisées et sauvegardées : {dry_run_filename}")
    return dry_run_filename

def detect_timer_value_from_screenshot(screenshot_file_path):
    """Mode normal : analyse complète avec OCR"""
    # Régions à analyser - Modifiable facilement
    regions_to_analyze = ['timer', 'character1', 'character2', 'variation1', 'variation2']
    
    if not os.path.exists(screenshot_file_path):
        raise FileNotFoundError(f"Le fichier image '{screenshot_file_path}' n'existe pas.")

    if not os.path.exists(OUTPUT_DIRECTORY):
        os.makedirs(OUTPUT_DIRECTORY)
    
    analyzed_frames_path = os.path.join(OUTPUT_DIRECTORY, ANALYZED_FRAMES_SUBDIRECTORY)
    if not os.path.exists(analyzed_frames_path):
        os.makedirs(analyzed_frames_path)
    
    ocr_reader = easyocr.Reader(['en'])
    
    original_image = cv.imread(screenshot_file_path)
    if original_image is None:
        raise ValueError(f"Impossible de charger l'image : {screenshot_file_path}")
    
    print(f"📐 Dimensions de l'image: {original_image.shape[1]}x{original_image.shape[0]} pixels")
    print("🎨 Détection avec contexte couleur: C=Violet, M=Orange, D=Bleu clair")
    
    output_image_with_annotations = original_image.copy()
    
    # Extraction des régions sélectionnées
    extracted_regions = extract_selected_regions_from_image(original_image, regions_to_analyze)
    
    detection_results = {}
    
    # Couleurs pour chaque type de région
    region_colors = {
        'timer': (0, 255, 0),        # Vert
        'character1': (255, 0, 0),   # Bleu
        'character2': (0, 0, 255),   # Rouge
        'variation1': (255, 255, 0), # Cyan
        'variation2': (255, 0, 255)  # Magenta
    }
    
    for region_name, region_data in extracted_regions.items():
        region_image = region_data['region']
        left_x, top_y, right_x, bottom_y = region_data['boundaries']
        
        print(f"📍 Analyse de {region_name}: ({left_x}, {top_y}) à ({right_x}, {bottom_y}) - Taille: {right_x-left_x}x{bottom_y-top_y}")
        
        # Amélioration spéciale pour les variations
        is_variation = region_name in ['variation1', 'variation2']
        enhanced_region = enhance_image_for_ocr_recognition(region_image, is_variation=is_variation)
        
        if enhanced_region is None:
            print(f"⚠ Impossible d'améliorer la région {region_name}")
            detection_results[region_name] = ''
            continue
        
        # Traitement spécial pour les variations avec contexte couleur
        if is_variation:
            extracted_text = detect_variation_with_color_context(region_image, enhanced_region, ocr_reader, region_name)
        else:
            # Traitement normal pour les autres régions
            ocr_detection_results = ocr_reader.readtext(enhanced_region)
            
            if region_name == 'timer':
                # Pour le timer, on extrait seulement les chiffres
                extracted_text = ''
                for single_detection in ocr_detection_results:
                    detected_text = single_detection[1]
                    extracted_text += ''.join(filter(str.isdigit, detected_text))
            else:
                # Pour les personnages, on extrait tout le texte
                extracted_text = ''
                for single_detection in ocr_detection_results:
                    detected_text = single_detection[1]
                    extracted_text += detected_text + ' '
                extracted_text = extracted_text.strip()
        
        detection_results[region_name] = extracted_text
        
        # Annotation de l'image
        color = region_colors.get(region_name, (255, 255, 255))
        cv.rectangle(output_image_with_annotations, (left_x, top_y), (right_x, bottom_y), color, 2)
        
        display_text = extracted_text if extracted_text else f"Aucun {region_name} détecté"
        text_font = cv.FONT_HERSHEY_SIMPLEX
        text_scale = 0.5
        text_thickness = 1
        (text_width, text_height), _ = cv.getTextSize(display_text, text_font, text_scale, text_thickness)
        centered_text_x = left_x + (right_x - left_x - text_width) // 2
        text_y_position = top_y - 10
        
        cv.putText(output_image_with_annotations, display_text,
                  (centered_text_x, text_y_position),
                  text_font, text_scale, color, text_thickness)
    
    analyzed_screenshot_filename = os.path.join(analyzed_frames_path, 'analyzed_' + os.path.basename(screenshot_file_path))
    cv.imwrite(analyzed_screenshot_filename, output_image_with_annotations)
    
    return detection_results

def main():
    argument_parser = argparse.ArgumentParser(
        description='Analyse une image pour détecter le timer et les noms des personnages de SF6'
    )
    argument_parser.add_argument('image', type=str, help='Chemin vers l\'image à analyser')
    argument_parser.add_argument('--dry', '-D', action='store_true', 
                               help='Mode dry-run : dessine seulement les régions sans analyse OCR')
    
    parsed_arguments = argument_parser.parse_args()
    
    try:
        if parsed_arguments.dry:
            # Mode dry-run : visualisation des régions seulement
            print("🔍 Mode dry-run activé - Visualisation des régions avec analyse couleur")
            output_file = visualize_regions_only(parsed_arguments.image)
            print(f"✓ Régions sauvegardées dans : {output_file}")
        else:
            # Mode normal : analyse complète
            print("🎯 Détection avec contexte couleur: C=Violet, M=Orange, D=Bleu clair")
            detection_results = detect_timer_value_from_screenshot(parsed_arguments.image)
            
            print("=== RÉSULTATS DE DÉTECTION ===")
            for region_name, detected_text in detection_results.items():
                if detected_text:
                    print(f"{region_name.upper()}: {detected_text}")
                else:
                    print(f"{region_name.upper()}: ⚠ Aucun texte détecté")
            
            if any(detection_results.values()):
                print("✓ Analyse réussie")
            else:
                print("⚠ Aucun texte n'a été détecté dans les régions sélectionnées")
            
    except Exception as error:
        print(f"Erreur lors de l'analyse: {str(error)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()