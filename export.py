import cv2 as cv
import numpy as np
import os
from datetime import datetime

# Import de la classe ImageAnalyzer depuis analyze.py
from image_analyzer import ImageAnalyzer

OUTPUT_DIRECTORY = 'output'
ANALYZED_FRAMES_SUBDIRECTORY = 'analyzed_frames'
RESULTS_CSV_FILENAME = 'match_results.csv'  # Renommé pour refléter toutes les données

def process_street_fighter_video_for_data_extraction(video_file_path, output_frames_subfolder=ANALYZED_FRAMES_SUBDIRECTORY):
    if not os.path.exists(OUTPUT_DIRECTORY):
        os.makedirs(OUTPUT_DIRECTORY)

    analyzed_frames_output_folder = os.path.join(OUTPUT_DIRECTORY, output_frames_subfolder)
    if not os.path.exists(analyzed_frames_output_folder):
        os.makedirs(analyzed_frames_output_folder)

    # Créer l'analyseur d'images
    analyzer = ImageAnalyzer()

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

    while True:
        frame_read_success, current_video_frame = video_capture.read()
        if not frame_read_success:
            break

        current_video_timestamp = current_frame_index / video_frames_per_second

        # Traiter seulement une frame par seconde
        if current_video_timestamp.is_integer():
            print(f"\n🎬 Analyse de la frame à {int(current_video_timestamp)}s")

            # Analyser la frame avec l'ImageAnalyzer
            results = analyzer.analyze_frame(current_video_frame)

            # Créer l'image annotée
            annotated_frame = analyzer.annotate_frame_with_regions(
                current_video_frame,
                list(results.keys()),
                show_text=True,
                detection_results=results
            )

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