import cv2 as cv
import os
import json

from src.image_analyzer import ImageAnalyzer
from src.frame_extractor import FrameExtractor

OUTPUT_DIRECTORY = 'output'
ANALYZED_FRAMES_SUBDIRECTORY = 'analyzed_frames'

def _ensure_output_directories_exist(save_frames):
    """Create output directories if they don't exist."""
    if not os.path.exists(OUTPUT_DIRECTORY):
        os.makedirs(OUTPUT_DIRECTORY)

    frames_output_dir = None
    if save_frames:
        frames_output_dir = os.path.join(
            OUTPUT_DIRECTORY, ANALYZED_FRAMES_SUBDIRECTORY
        )
        if not os.path.exists(frames_output_dir):
            os.makedirs(frames_output_dir)
    
    return frames_output_dir


def _create_analyzers(video_path, frames_per_minute, save_frames):
    """Initialize frame extractor and image analyzer."""
    frame_extractor = FrameExtractor(
        video_path=video_path,
        output_name=None,
        no_prompt=True,
        frames_per_minute=frames_per_minute,
        debug=False
    )
    
    # Configure ImageAnalyzer debug mode based on save_frames parameter
    analyzer_kwargs = {
        'config_file': 'rois_config.json',
        'characters_file': 'characters.json',
        'debug': save_frames
    }
    
    if save_frames:
        analyzer_kwargs['debug_save_dir'] = os.path.join(OUTPUT_DIRECTORY, ANALYZED_FRAMES_SUBDIRECTORY)
    
    image_analyzer = ImageAnalyzer(**analyzer_kwargs)
    
    return frame_extractor, image_analyzer


def _create_frame_data(timestamp, analysis_results):
    """Create standardized frame data structure."""
    return {
        "timestamp": timestamp,
        "timer_value": analysis_results.get('timer', ''),
        "character1": analysis_results.get('character1', ''),
        "character2": analysis_results.get('character2', '')
    }


def _print_analysis_progress(results, frame_count):
    """Display analysis progress and results."""
    print(f"⏱️  Timer: {results.get('timer', 'Non détecté')}")
    print(f"🎮 P1: {results.get('character1', 'Non détecté')}")
    print(f"🎮 P2: {results.get('character2', 'Non détecté')}")
    
    if frame_count % 10 == 0:
        print(f"📊 Progression: {frame_count} frames analysées")


def _save_results_to_json(analysis_results, json_path):
    """Save analysis results to JSON file."""
    with open(json_path, 'w', encoding='utf-8') as json_file:
        json.dump(analysis_results, json_file, indent=2, ensure_ascii=False)


def analyze_video(video_file_path, frames_per_minute=12, save_frames=False):
    """Analyze Street Fighter 6 video to extract game data."""
    video_name = os.path.splitext(os.path.basename(video_file_path))[0]
    json_output_path = os.path.join(OUTPUT_DIRECTORY, f"{video_name}_results.json")
    
    frames_output_dir = _ensure_output_directories_exist(save_frames)
    frame_extractor, analyzer = _create_analyzers(video_file_path, frames_per_minute, save_frames)
    
    analysis_results = []
    frame_count = 0
    
    print(f"🎬 Analyse de la vidéo: {video_file_path}")
    print(
        f"⏱️  Intervalle: {frame_extractor.frame_interval_seconds:.1f}s "
        f"({frames_per_minute} frames/minute)"
    )
    
    try:
        for frame, _, timestamp in frame_extractor.generate_frames():
            print(f"\n🔍 Analyse de la frame à {timestamp}")
            
            ocr_results = analyzer.analyze_frame(frame)
            
            frame_data = _create_frame_data(timestamp, ocr_results)
            analysis_results.append(frame_data)
            
            frame_count += 1
            _print_analysis_progress(ocr_results, frame_count)
    
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse: {e}")
        return
    
    _save_results_to_json(analysis_results, json_output_path)
    
    print(f"\n✅ Analyse terminée!")
    print(f"📄 Résultats: {json_output_path}")
    frames_info = (
        f"(frames debug sauvegardées par ImageAnalyzer)" if save_frames 
        else "(mode production)"
    )
    print(f"🖼️  {len(analysis_results)} frames analysées {frames_info}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description='Analyse les données de match depuis une vidéo SF6'
    )
    parser.add_argument(
        'video', type=str, nargs='?',
        help='Chemin vers la vidéo à analyser'
    )
    parser.add_argument(
        '--save-frames', action='store_true',
        help='Activer le mode debug pour sauvegarder les frames analysées'
    )
    parser.add_argument(
        '--frames-per-minute', type=int, default=12,
        help='Nombre de frames à analyser par minute (par défaut: 12)'
    )

    args = parser.parse_args()

    if not args.video:
        print("❌ Erreur: Veuillez spécifier un fichier vidéo à analyser.")
        parser.print_help()
    elif not os.path.exists(args.video):
        print(f"❌ Erreur: Le fichier vidéo '{args.video}' n'existe pas.")
    else:
        save_frames = args.save_frames
        print(f"🎯 Analyse de la vidéo: {args.video}")
        if save_frames:
            print("🐛 Mode debug: frames sauvegardées dans ImageAnalyzer")
        analyze_video(args.video, args.frames_per_minute, save_frames)
