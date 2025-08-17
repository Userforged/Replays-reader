import json
import os

import cv2 as cv

from src.frame_extractor import FrameExtractor
from src.image_analyzer import ImageAnalyzer

OUTPUT_DIRECTORY = "output"
ANALYZED_FRAMES_SUBDIRECTORY = "analyzed_frames"


def _ensure_output_directories_exist(save_frames):
    """Create output directories if they don't exist."""
    if not os.path.exists(OUTPUT_DIRECTORY):
        os.makedirs(OUTPUT_DIRECTORY)

    frames_output_dir = None
    if save_frames:
        frames_output_dir = os.path.join(OUTPUT_DIRECTORY, ANALYZED_FRAMES_SUBDIRECTORY)
        if not os.path.exists(frames_output_dir):
            os.makedirs(frames_output_dir)

    return frames_output_dir


def _create_analyzers(video_source, frames_per_minute, save_frames, manual_format=None):
    """Initialize frame extractor and image analyzer."""
    frame_extractor = FrameExtractor(
        video_source=video_source,
        output_name=None,
        no_prompt=True,
        frames_per_minute=frames_per_minute,
        debug=False,
        manual_format=manual_format,
    )

    # Configure ImageAnalyzer debug mode based on save_frames parameter
    analyzer_kwargs = {
        "config_file": "rois_config.json",
        "characters_file": "characters.json",
        "debug": save_frames,
    }

    if save_frames:
        analyzer_kwargs["debug_save_dir"] = os.path.join(
            OUTPUT_DIRECTORY, ANALYZED_FRAMES_SUBDIRECTORY
        )

    image_analyzer = ImageAnalyzer(**analyzer_kwargs)

    return frame_extractor, image_analyzer


def _create_frame_data(timestamp, analysis_results):
    """Create standardized frame data structure."""
    return {
        "timestamp": timestamp,
        "timer_value": analysis_results.get("timer", ""),
        "character1": analysis_results.get("character1", ""),
        "character2": analysis_results.get("character2", ""),
        "player1": analysis_results.get("player1", ""),
        "player2": analysis_results.get("player2", ""),
    }


def _print_analysis_progress(results, frame_count):
    """Display analysis progress and results."""
    print(f"⏱️  Timer: {results.get('timer', 'Non détecté')}")
    print(f"👤 P1 Name: {results.get('player1', 'Non détecté')}")
    print(f"⚔️  P1 Char: {results.get('character1', 'Non détecté')}")
    print(f"👤 P2 Name: {results.get('player2', 'Non détecté')}")
    print(f"⚔️  P2 Char: {results.get('character2', 'Non détecté')}")

    if frame_count % 10 == 0:
        print(f"📊 Progression: {frame_count} frames analysées")


def _initialize_json_file(json_path):
    """Initialize/clear JSON file with empty array."""
    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump([], json_file)


def _append_frame_to_json(frame_data, json_path):
    """Append a single frame to existing JSON file."""
    # Read existing data
    try:
        with open(json_path, "r", encoding="utf-8") as json_file:
            analysis_results = json.load(json_file)
    except (FileNotFoundError, json.JSONDecodeError):
        analysis_results = []

    # Add new frame
    analysis_results.append(frame_data)

    # Write back to file
    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(analysis_results, json_file, indent=2, ensure_ascii=False)


def _save_results_to_json(analysis_results, json_path):
    """Save analysis results to JSON file (legacy function for compatibility)."""
    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(analysis_results, json_file, indent=2, ensure_ascii=False)


def analyze_video(
    video_source, frames_per_minute=12, save_frames=False, manual_format=None, max_frames=None
):
    """Analyze Street Fighter 6 video to extract game data."""
    # For output naming, use the resolved video name from FrameExtractor
    frame_extractor, analyzer = _create_analyzers(
        video_source, frames_per_minute, save_frames, manual_format
    )

    # Use the output name determined by FrameExtractor for JSON file
    video_name = frame_extractor.output_name
    json_output_path = os.path.join(OUTPUT_DIRECTORY, f"{video_name}.export.json")

    # Initialize JSON file (clear if exists)
    _initialize_json_file(json_output_path)

    analysis_results = []
    frame_count = 0

    source_type = "stream" if frame_extractor.is_stream else "fichier"
    print(f"🎬 Analyse du {source_type}: {video_source}")
    if frame_extractor.is_stream and frame_extractor.resolved_source["metadata"].get(
        "title"
    ):
        print(f"📺 Titre: {frame_extractor.resolved_source['metadata']['title']}")
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

            # Write frame immediately to JSON file
            _append_frame_to_json(frame_data, json_output_path)

            frame_count += 1
            _print_analysis_progress(ocr_results, frame_count)
            
            # Check if max_frames limit is reached
            if max_frames and frame_count >= max_frames:
                print(f"\n🛑 Limite atteinte: {max_frames} frames analysées")
                break

    except Exception as e:
        print(f"❌ Erreur lors de l'analyse: {e}")
        return

    # Final file is already written incrementally, just show completion
    print(f"\n✅ Analyse terminée!")
    print(f"📄 Résultats: {json_output_path}")
    frames_info = (
        f"(frames debug sauvegardées par ImageAnalyzer)"
        if save_frames
        else "(mode production)"
    )
    print(f"🖼️  {len(analysis_results)} frames analysées {frames_info}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyse les données de match depuis une vidéo SF6"
    )
    parser.add_argument(
        "video",
        type=str,
        nargs="?",
        help="Chemin vers la vidéo locale ou URL en ligne à analyser",
    )
    parser.add_argument(
        "--save-frames",
        action="store_true",
        help="Activer le mode debug pour sauvegarder les frames analysées",
    )
    parser.add_argument(
        "--frames-per-minute",
        type=int,
        default=12,
        help="Nombre de frames à analyser par minute (par défaut: 12)",
    )
    parser.add_argument(
        "-f",
        "--format",
        type=str,
        default=None,
        help="Format yt-dlp spécifique à utiliser (bypasse la sélection automatique). Ex: -f 299",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Nombre maximum de frames à analyser (par défaut: illimité)",
    )

    args = parser.parse_args()

    if not args.video:
        print("❌ Erreur: Veuillez spécifier un fichier vidéo ou une URL à analyser.")
        print("💡 Exemples:")
        print("   python export.py input/match.mp4")
        print("   python export.py https://www.youtube.com/watch?v=VIDEO_ID")
        print("   python export.py https://www.youtube.com/watch?v=VIDEO_ID -f 312")
        print(
            "   python export.py https://www.youtube.com/watch?v=VIDEO_ID --format best"
        )
        parser.print_help()
    else:
        save_frames = args.save_frames
        source_type = (
            "URL" if args.video.startswith(("http://", "https://")) else "fichier"
        )
        print(f"🎯 Analyse du {source_type}: {args.video}")
        if args.format:
            print(f"🔧 Format manuel spécifié: {args.format}")
        if save_frames:
            print("🐛 Mode debug: frames sauvegardées dans ImageAnalyzer")
        if args.max_frames:
            print(f"🔢 Limite: {args.max_frames} frames maximum")
        try:
            analyze_video(args.video, args.frames_per_minute, save_frames, args.format, args.max_frames)
        except Exception as e:
            print(f"❌ Erreur lors de l'analyse: {e}")
            if args.video.startswith(("http://", "https://")):
                print("💡 Vérifiez que yt-dlp peut accéder à cette URL")


def process_street_fighter_video_for_data_extraction(
    video_source, save_frames=False, manual_format=None
):
    """
    Convenience function for backward compatibility and programmatic use.

    Args:
        video_source: Local file path or online video URL
        save_frames: Whether to save debug frames
        manual_format: Optional manual yt-dlp format specification
    """
    return analyze_video(
        video_source,
        frames_per_minute=12,
        save_frames=save_frames,
        manual_format=manual_format,
    )
