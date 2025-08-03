import cv2 as cv
import numpy as np
import os
import easyocr
from datetime import datetime

# Import des fonctions depuis analyze.py
from analyze import (
    extract_street_fighter_timer_region,
    extract_street_fighter_character1_region,
    extract_street_fighter_character2_region,
    extract_street_fighter_variation1_region,
    extract_street_fighter_variation2_region,
    enhance_image_for_ocr_recognition,
    detect_variation_with_color_context,
    correct_variation_with_context
)

OUTPUT_DIRECTORY = 'output'
ANALYZED_FRAMES_SUBDIRECTORY = 'analyzed_frames'
RESULTS_CSV_FILENAME = 'match_results.csv'  # Renommé pour refléter toutes les données

def process_street_fighter_video_for_data_extraction(video_file_path, output_frames_subfolder=ANALYZED_FRAMES_SUBDIRECTORY):
    if not os.path.exists(OUTPUT_DIRECTORY):
        os.makedirs(OUTPUT_DIRECTORY)

    analyzed_frames_output_folder = os.path.join(OUTPUT_DIRECTORY, output_frames_subfolder)
    if not os.path.exists(analyzed_frames_output_folder):
        os.makedirs(analyzed_frames_output_folder)

    ocr_text_reader = easyocr.Reader(['en'])

    video_capture = cv.VideoCapture(video_file_path)
    if not video_capture.isOpened():
        print("Erreur: Impossible d'ouvrir la vidéo")
        return

    video_frames_per_second = video_capture.get(cv.CAP_PROP_FPS)
    total_frame_count = int(video_capture.get(cv.CAP_PROP_FRAME_COUNT))
    current_frame_index = 0

    csv_results_file_path = os.path.join(OUTPUT_DIRECTORY, RESULTS_CSV_FILENAME)
    with open(csv_results_file_path, 'w') as csv_file:
        csv_file.write("Timestamp,Timer_Value,Character1,Variation1,Character2,Variation2\n")

    # Couleurs pour chaque type de région (même que dans analyze.py)
    region_colors = {
        'timer': (0, 255, 0),        # Vert
        'character1': (255, 0, 0),   # Bleu
        'character2': (0, 0, 255),   # Rouge
        'variation1': (255, 255, 0), # Cyan
        'variation2': (255, 0, 255)  # Magenta
    }

    while True:
        frame_read_success, current_video_frame = video_capture.read()
        if not frame_read_success:
            break

        current_video_timestamp = current_frame_index / video_frames_per_second

        # Traiter seulement une frame par seconde
        if current_video_timestamp.is_integer():
            print(f"\n🎬 Analyse de la frame à {int(current_video_timestamp)}s")

            # Copie pour l'annotation
            annotated_frame = current_video_frame.copy()

            # Extraction et analyse de toutes les régions
            results = {}

            # Timer
            timer_region, timer_boundaries = extract_street_fighter_timer_region(current_video_frame)
            if timer_region is not None and timer_boundaries is not None:
                enhanced_timer_image = enhance_image_for_ocr_recognition(timer_region, is_variation=False)
                if enhanced_timer_image is not None:
                    results['timer'] = extract_timer_digits_from_processed_image(enhanced_timer_image, ocr_text_reader)
                else:
                    results['timer'] = ''

                # Annotation du timer
                left_x, top_y, right_x, bottom_y = timer_boundaries
                cv.rectangle(annotated_frame, (left_x, top_y), (right_x, bottom_y), region_colors['timer'], 2)
                add_text_annotation(annotated_frame, results['timer'] or "No timer",
                                  timer_boundaries, region_colors['timer'])
            else:
                results['timer'] = ''

            # Character 1
            char1_region, char1_boundaries = extract_street_fighter_character1_region(current_video_frame)
            if char1_region is not None and char1_boundaries is not None:
                enhanced_char1_image = enhance_image_for_ocr_recognition(char1_region, is_variation=False)
                if enhanced_char1_image is not None:
                    results['character1'] = extract_character_name_from_processed_image(enhanced_char1_image, ocr_text_reader)
                else:
                    results['character1'] = ''

                # Annotation
                left_x, top_y, right_x, bottom_y = char1_boundaries
                cv.rectangle(annotated_frame, (left_x, top_y), (right_x, bottom_y), region_colors['character1'], 2)
                add_text_annotation(annotated_frame, results['character1'] or "No char1",
                                  char1_boundaries, region_colors['character1'])
            else:
                results['character1'] = ''

            # Variation 1
            var1_region, var1_boundaries = extract_street_fighter_variation1_region(current_video_frame)
            if var1_region is not None and var1_boundaries is not None:
                enhanced_var1_image = enhance_image_for_ocr_recognition(var1_region, is_variation=True)
                if enhanced_var1_image is not None:
                    results['variation1'] = detect_variation_with_color_context(var1_region, enhanced_var1_image,
                                                                               ocr_text_reader, 'variation1')
                else:
                    results['variation1'] = ''

                # Annotation
                left_x, top_y, right_x, bottom_y = var1_boundaries
                cv.rectangle(annotated_frame, (left_x, top_y), (right_x, bottom_y), region_colors['variation1'], 2)
                add_text_annotation(annotated_frame, results['variation1'] or "No var1",
                                  var1_boundaries, region_colors['variation1'])
            else:
                results['variation1'] = ''

            # Character 2
            char2_region, char2_boundaries = extract_street_fighter_character2_region(current_video_frame)
            if char2_region is not None and char2_boundaries is not None:
                enhanced_char2_image = enhance_image_for_ocr_recognition(char2_region, is_variation=False)
                if enhanced_char2_image is not None:
                    results['character2'] = extract_character_name_from_processed_image(enhanced_char2_image, ocr_text_reader)
                else:
                    results['character2'] = ''

                # Annotation
                left_x, top_y, right_x, bottom_y = char2_boundaries
                cv.rectangle(annotated_frame, (left_x, top_y), (right_x, bottom_y), region_colors['character2'], 2)
                add_text_annotation(annotated_frame, results['character2'] or "No char2",
                                  char2_boundaries, region_colors['character2'])
            else:
                results['character2'] = ''

            # Variation 2
            var2_region, var2_boundaries = extract_street_fighter_variation2_region(current_video_frame)
            if var2_region is not None and var2_boundaries is not None:
                enhanced_var2_image = enhance_image_for_ocr_recognition(var2_region, is_variation=True)
                if enhanced_var2_image is not None:
                    results['variation2'] = detect_variation_with_color_context(var2_region, enhanced_var2_image,
                                                                               ocr_text_reader, 'variation2')
                else:
                    results['variation2'] = ''

                # Annotation
                left_x, top_y, right_x, bottom_y = var2_boundaries
                cv.rectangle(annotated_frame, (left_x, top_y), (right_x, bottom_y), region_colors['variation2'], 2)
                add_text_annotation(annotated_frame, results['variation2'] or "No var2",
                                  var2_boundaries, region_colors['variation2'])
            else:
                results['variation2'] = ''

            # Sauvegarder la frame annotée
            formatted_timestamp = datetime.fromtimestamp(current_video_timestamp).strftime('%H-%M-%S')
            analyzed_frame_filename = os.path.join(analyzed_frames_output_folder, f'analyzed_frame_{formatted_timestamp}.png')
            cv.imwrite(analyzed_frame_filename, annotated_frame)

            # Écrire dans le CSV
            with open(csv_results_file_path, 'a') as csv_file:
                csv_file.write(f"{formatted_timestamp},"
                             f"{results.get('timer', '')},"
                             f"{results.get('character1', '')},"
                             f"{results.get('variation1', '')},"
                             f"{results.get('character2', '')},"
                             f"{results.get('variation2', '')}\n")

            # Afficher les résultats
            print(f"📸 Frame sauvegardée: {analyzed_frame_filename}")
            print(f"⏱️  Timer: {results.get('timer', 'Non détecté')}")
            print(f"🎮 P1: {results.get('character1', 'Non détecté')} [{results.get('variation1', '?')}]")
            print(f"🎮 P2: {results.get('character2', 'Non détecté')} [{results.get('variation2', '?')}]")

        current_frame_index += 1

        # Afficher la progression
        if current_frame_index % 100 == 0:
            progress = (current_frame_index / total_frame_count) * 100
            print(f"📊 Progression: {progress:.1f}% ({current_frame_index}/{total_frame_count} frames)")

    video_capture.release()
    print(f"\n✅ Analyse terminée!")
    print(f"📄 Résultats sauvegardés dans: {csv_results_file_path}")
    print(f"🖼️  Frames analysées dans: {analyzed_frames_output_folder}")

def add_text_annotation(frame, text, boundaries, color):
    """Ajoute une annotation de texte centrée au-dessus de la région"""
    left_x, top_y, right_x, bottom_y = boundaries

    text_font = cv.FONT_HERSHEY_SIMPLEX
    text_scale = 0.5
    text_thickness = 1

    # Calculer la taille du texte
    (text_width, text_height), _ = cv.getTextSize(text, text_font, text_scale, text_thickness)

    # Centrer le texte horizontalement
    centered_text_x = left_x + (right_x - left_x - text_width) // 2
    text_y_position = top_y - 10

    # S'assurer que le texte reste dans l'image
    if text_y_position < 20:
        text_y_position = bottom_y + 20

    cv.putText(frame, text,
              (centered_text_x, text_y_position),
              text_font, text_scale, color, text_thickness)

def extract_timer_digits_from_processed_image(enhanced_image, ocr_reader):
    """Extrait seulement les chiffres du timer"""
    ocr_detection_results = ocr_reader.readtext(enhanced_image)
    extracted_timer_digits = ''
    for single_detection in ocr_detection_results:
        detected_text = single_detection[1]
        extracted_timer_digits += ''.join(filter(str.isdigit, detected_text))
    return extracted_timer_digits

def extract_character_name_from_processed_image(enhanced_image, ocr_reader):
    """Extrait le nom du personnage"""
    ocr_detection_results = ocr_reader.readtext(enhanced_image)
    extracted_text = ''
    for single_detection in ocr_detection_results:
        detected_text = single_detection[1]
        extracted_text += detected_text + ' '
    return extracted_text.strip()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Extrait les données de match depuis une vidéo SF6')
    parser.add_argument('video', type=str, nargs='?', default='video.mp4',
                       help='Chemin vers la vidéo à analyser (par défaut: video.mp4)')
    parser.add_argument('--output-dir', type=str, default=ANALYZED_FRAMES_SUBDIRECTORY,
                       help='Sous-dossier pour les frames analysées')

    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(f"❌ Erreur: Le fichier vidéo '{args.video}' n'existe pas.")
    else:
        print(f"🎯 Analyse de la vidéo: {args.video}")
        print(f"🎨 Détection avec contexte couleur: C=Violet, M=Orange, D=Bleu clair")
        process_street_fighter_video_for_data_extraction(args.video, args.output_dir)