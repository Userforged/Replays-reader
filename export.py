import cv2 as cv
import numpy as np
import os
import json
import re
from datetime import datetime

from src.image_analyzer import ImageAnalyzer
from src.frame_extractor import FrameExtractor

OUTPUT_DIRECTORY = 'output'
ANALYZED_FRAMES_SUBDIRECTORY = 'analyzed_frames'

def process_street_fighter_video_for_data_extraction(video_file_path, frames_per_minute=12, save_frames=True):
    """
    Analyze Street Fighter 6 video using FrameExtractor generator.
    
    Args:
        video_file_path (str): Path to the video file to analyze
        frames_per_minute (int): Number of frames to analyze per minute (default: 12)
        save_frames (bool): Whether to save analyzed frames to disk (default: True)
    """
    # Generate dynamic filename based on video name
    video_name = os.path.splitext(os.path.basename(video_file_path))[0]
    results_json_filename = f"{video_name}_results.json"
    
    if not os.path.exists(OUTPUT_DIRECTORY):
        os.makedirs(OUTPUT_DIRECTORY)

    # Only create frames folder if we're saving frames
    analyzed_frames_output_folder = None
    if save_frames:
        analyzed_frames_output_folder = os.path.join(OUTPUT_DIRECTORY, ANALYZED_FRAMES_SUBDIRECTORY)
        if not os.path.exists(analyzed_frames_output_folder):
            os.makedirs(analyzed_frames_output_folder)

    # Initialize FrameExtractor and ImageAnalyzer
    frame_extractor = FrameExtractor(
        video_path=video_file_path,
        output_name=None,  # Not used for generation
        no_prompt=True,    # No user interaction
        frames_per_minute=frames_per_minute,
        debug=False        # Set to True for verbose output
    )
    
    analyzer = ImageAnalyzer(
        config_file='rois_config.json',  # ✅ Obligatoire pour métadonnées
        debug=False  # Set to True for verbose output and automatic image saving
    )
    
    json_results_file_path = os.path.join(OUTPUT_DIRECTORY, results_json_filename)
    results_data = []
    
    print(f"🎬 Analyse de la vidéo avec FrameExtractor: {video_file_path}")
    print(f"⏱️  Intervalle d'analyse: {frame_extractor.frame_interval_seconds:.1f}s ({frames_per_minute} frames/minute)")
    
    frame_count = 0
    total_expected_frames = None  # Will be calculated during iteration
    
    try:
        # Use the generator to process frames
        for frame, timestamp_seconds, formatted_timestamp in frame_extractor.generate_frames():
            print(f"\n🔍 Analyse de la frame à {formatted_timestamp}")
            
            # Analyze frame
            results = analyzer.analyze_frame(frame)
            
            # Save annotated frame only if requested
            analyzed_frame_path = None
            if save_frames:
                # Create annotated frame
                annotated_frame = analyzer.annotate_frame_with_rois(
                    frame,
                    list(results.keys()),
                    show_text=True,
                    detection_results=results
                )
                
                # Save annotated frame
                frame_filename = f"analyzed_frame_{formatted_timestamp.replace(':', '-')}.png"
                analyzed_frame_path = os.path.join(analyzed_frames_output_folder, frame_filename)
                cv.imwrite(analyzed_frame_path, annotated_frame)
            
            # Store results
            frame_data = {
                "timestamp": formatted_timestamp,
                "timer_value": results.get('timer', ''),
                "character1": results.get('character1', ''),
                "character2": results.get('character2', '')
            }
            results_data.append(frame_data)
            
            # Display results
            if save_frames:
                print(f"📸 Frame sauvegardée: {analyzed_frame_path}")
            print(f"⏱️  Timer: {results.get('timer', 'Non détecté')}")
            print(f"🎮 P1: {results.get('character1', 'Non détecté')}")
            print(f"🎮 P2: {results.get('character2', 'Non détecté')}")
            
            frame_count += 1
            if frame_count % 10 == 0:
                print(f"📊 Progression: {frame_count} frames analysées")
    
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse: {e}")
        return
    
    # Save results to JSON
    with open(json_results_file_path, 'w', encoding='utf-8') as json_file:
        json.dump(results_data, json_file, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Analyse terminée!")
    print(f"📄 Résultats sauvegardés dans: {json_results_file_path}")
    if save_frames:
        print(f"🖼️  {len(results_data)} frames analysées dans: {analyzed_frames_output_folder}")
    else:
        print(f"🖼️  {len(results_data)} frames analysées (aucune frame sauvegardée)")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Analyse les données de match depuis une vidéo SF6')
    parser.add_argument('video', type=str, nargs='?',
                        help='Chemin vers la vidéo à analyser')
    parser.add_argument('-n', '--no-frames', action='store_true',
                        help='Ne pas sauvegarder les frames analysées (mode rapide)')
    parser.add_argument('--frames-per-minute', type=int, default=12,
                        help='Nombre de frames à analyser par minute (par défaut: 12)')

    args = parser.parse_args()

    if not args.video:
        print("❌ Erreur: Veuillez spécifier un fichier vidéo à analyser.")
        parser.print_help()
    elif not os.path.exists(args.video):
        print(f"❌ Erreur: Le fichier vidéo '{args.video}' n'existe pas.")
    else:
        save_frames = not args.no_frames  # Inverse la logique : -n = ne pas sauvegarder
        print(f"🎯 Analyse de la vidéo: {args.video}")
        if args.no_frames:
            print("⚡ Mode rapide: les frames analysées ne seront pas sauvegardées")
        process_street_fighter_video_for_data_extraction(args.video, args.frames_per_minute, save_frames)
