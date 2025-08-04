#!/usr/bin/env python3
"""
Street Fighter 6 Frame Extraction Test

This script provides functionality to:
- Extract frames from MP4 video files at specified intervals
- Save extracted frames as PNG images with timestamp naming
- Organize output in structured folder hierarchy
- Support custom frame extraction rates

The extracted frames can then be analyzed using the test-export.py script
or other image analysis tools.

Usage:
    python test-extract.py video.mp4
    python test-extract.py video.mp4 custom_folder_name
    python test-extract.py video.mp4 -n  # No prompt mode
"""

import sys
import argparse
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from frame_extractor import FrameExtractor

def main():
    parser = argparse.ArgumentParser(
        description='Extrait une image toutes les 5 secondes d\'une vidéo MP4.'
    )
    parser.add_argument('video', type=str, help='Chemin vers le fichier vidéo MP4')
    parser.add_argument('folder_name', nargs='?', type=str,
                        help='Nom du dossier de sortie (optionnel)')
    parser.add_argument('-n', action='store_true',
                        help='Utilise le nom du fichier sans demander')

    args = parser.parse_args()

    try:
        extractor = FrameExtractor(args.video, args.folder_name, args.n, debug=True)
        extractor.extract_frames()
    except Exception as e:
        print(f"Erreur : {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
