import sys
import argparse
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
        extractor = FrameExtractor(args.video, args.folder_name, args.n)
        extractor.extract_frames()
    except Exception as e:
        print(f"Erreur : {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
