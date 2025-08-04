#!/usr/bin/env python3
"""
Street Fighter 6 Analyze Exporting Test

This script processes a folder of extracted frames and:
- Analyzes each frame for timer values and character names using OCR
- Creates annotated frames showing detection regions and results
- Exports all results to a structured JSON file
- Provides progress tracking during batch processing

The script is designed for testing and analyzing small sets of frames without
needing to process full videos.

Usage:
    python test-export.py input/frames/test/
    python test-export.py path/to/frames/ --output-dir custom_analyzed
"""

import cv2 as cv
import numpy as np
import os
import json
import re
from datetime import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from image_analyzer import ImageAnalyzer

OUTPUT_DIRECTORY = 'test/output'
ANALYZED_FRAMES_SUBDIRECTORY = 'analyzed_frames'
RESULTS_JSON_FILENAME = 'test_results.json'

def process_street_fighter_frames_for_data_extraction(frames_folder_path, output_frames_subfolder=ANALYZED_FRAMES_SUBDIRECTORY):
    if not os.path.exists(frames_folder_path):
        print(f"❌ Erreur: Le dossier '{frames_folder_path}' n'existe pas.")
        return

    if not os.path.exists(OUTPUT_DIRECTORY):
        os.makedirs(OUTPUT_DIRECTORY)

    analyzed_frames_output_folder = os.path.join(OUTPUT_DIRECTORY, output_frames_subfolder)
    if not os.path.exists(analyzed_frames_output_folder):
        os.makedirs(analyzed_frames_output_folder)

    analyzer = ImageAnalyzer(
        debug=True  # Active automatiquement save_analyzed_images et save_debug_images
    )

    # Get all image files from the folder
    image_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff')
    image_files = [f for f in os.listdir(frames_folder_path) if f.lower().endswith(image_extensions)]
    image_files.sort()  # Sort by filename
    
    if not image_files:
        print(f"❌ Aucune image trouvée dans le dossier '{frames_folder_path}'.")
        return

    json_results_file_path = os.path.join(OUTPUT_DIRECTORY, RESULTS_JSON_FILENAME)
    results_data = []
    
    print(f"📁 Analyse de {len(image_files)} images dans: {frames_folder_path}")

    for i, image_filename in enumerate(image_files):
        image_path = os.path.join(frames_folder_path, image_filename)
        
        # Extract timestamp from filename if possible (format: frame_HH-MM-SS.ext)
        timestamp_match = re.search(r'(\d{2})-(\d{2})-(\d{2})', image_filename)
        if timestamp_match:
            hours, minutes, seconds = timestamp_match.groups()
            formatted_timestamp = f"{hours}:{minutes}:{seconds}"
        else:
            # Fallback: use sequential numbering
            formatted_timestamp = f"00:{i//60:02d}:{i%60:02d}"
        
        print(f"\n🎬 Analyse de l'image: {image_filename} ({formatted_timestamp})")
        
        # Load and analyze the image
        current_frame = cv.imread(image_path)
        if current_frame is None:
            print(f"⚠️ Impossible de charger l'image: {image_filename}")
            continue
            
        results = analyzer.analyze_frame(current_frame)

        annotated_frame = analyzer.annotate_frame_with_rois(
            current_frame,
            list(results.keys()),
            show_text=True,
            detection_results=results
        )

        analyzed_frame_filename = os.path.join(analyzed_frames_output_folder, f'analyzed_{image_filename}')
        cv.imwrite(analyzed_frame_filename, annotated_frame)

        frame_data = {
            "timestamp": formatted_timestamp,
            "timer_value": results.get('timer', ''),
            "character1": results.get('character1', ''),
            "character2": results.get('character2', '')
        }
        results_data.append(frame_data)

        print(f"📸 Frame sauvegardée: {analyzed_frame_filename}")
        print(f"⏱️  Timer: {results.get('timer', 'Non détecté')}")
        print(f"🎮 P1: {results.get('character1', 'Non détecté')}")
        print(f"🎮 P2: {results.get('character2', 'Non détecté')}")

        if (i + 1) % 10 == 0:
            progress = ((i + 1) / len(image_files)) * 100
            print(f"📊 Progression: {progress:.1f}% ({i + 1}/{len(image_files)} images)")

    with open(json_results_file_path, 'w', encoding='utf-8') as json_file:
        json.dump(results_data, json_file, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Analyse terminée!")
    print(f"📄 Résultats sauvegardés dans: {json_results_file_path}")
    print(f"🖼️  Frames analysées dans: {analyzed_frames_output_folder}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Extrait les données de match depuis un dossier d\'images SF6')
    parser.add_argument('frames_folder', type=str,
                        help='Chemin vers le dossier contenant les frames à analyser')
    parser.add_argument('--output-dir', type=str, default=ANALYZED_FRAMES_SUBDIRECTORY,
                        help='Sous-dossier pour les frames analysées')

    args = parser.parse_args()

    print(f"🎯 Analyse du dossier: {args.frames_folder}")
    process_street_fighter_frames_for_data_extraction(args.frames_folder, args.output_dir)
