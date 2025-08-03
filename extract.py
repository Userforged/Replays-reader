import cv2 as cv
import os
from datetime import datetime
import sys
import argparse

# Configuration de l'extraction
FRAMES_INTERVAL_SECONDS = 5  # Extraire une image toutes les X secondes
OUTPUT_FORMAT = 'png'        # Format des images extraites
OUTPUT_DIR = 'output'       # Dossier principal de sortie
FRAMES_DIR = 'frames'       # Sous-dossier pour les frames

def get_video_name(video_path, folder_name=None, no_prompt=False):
    """
    Détermine le nom du dossier de sortie pour les frames
    """
    # Obtenir le nom du fichier sans extension
    default_name = os.path.splitext(os.path.basename(video_path))[0]
    
    # Si un nom de dossier est fourni, l'utiliser
    if folder_name:
        return folder_name
        
    # Si -n est utilisé, utiliser le nom du fichier
    if no_prompt:
        return default_name
        
    # Sinon, demander à l'utilisateur
    user_input = input(f"Nom du dossier de sortie [{default_name}]: ").strip()
    return user_input if user_input else default_name

def extract_frames(video_path, output_name=None, no_prompt=False):
    """
    Extrait des images d'une vidéo à intervalles réguliers.
    """
    # Vérifications préliminaires
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Le fichier vidéo '{video_path}' n'existe pas.")
    
    if not video_path.lower().endswith('.mp4'):
        raise ValueError("Le fichier doit être au format MP4.")
    
    # Déterminer le nom du dossier de sortie
    output_name = get_video_name(video_path, output_name, no_prompt)
    
    # Créer la structure des dossiers
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    frames_path = os.path.join(OUTPUT_DIR, FRAMES_DIR)
    if not os.path.exists(frames_path):
        os.makedirs(frames_path)
    
    output_folder = os.path.join(frames_path, output_name)
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    else:
        print(f"⚠️ Le dossier {output_folder} existe déjà")
    
    # Initialisation de la capture vidéo
    cap = cv.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError("Erreur: Impossible d'ouvrir la vidéo")
    
    # Récupération des métadonnées de la vidéo
    fps = cap.get(cv.CAP_PROP_FPS)
    frame_count = int(cap.get(cv.CAP_PROP_FRAME_COUNT))
    duration = frame_count/fps
    frames_per_extraction = int(fps * FRAMES_INTERVAL_SECONDS)
    
    # Affichage des informations
    print(f"\nExtracting frames from: {video_path}")
    print(f"Output directory: {output_folder}")
    print(f"FPS: {fps}")
    print(f"Durée totale: {duration:.2f} secondes")
    print(f"Intervalle d'extraction: {FRAMES_INTERVAL_SECONDS} secondes")
    print(f"Une image sera extraite tous les {frames_per_extraction} frames")
    
    # Variables de suivi
    frame_number = 0
    saved_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        # Calculer le temps actuel dans la vidéo
        current_time = frame_number / fps
        
        # Extraire une image si on est à un multiple de l'intervalle
        if current_time % FRAMES_INTERVAL_SECONDS == 0:
            timestamp = datetime.fromtimestamp(current_time).strftime('%H-%M-%S')
            filename = os.path.join(output_folder, f'frame_{timestamp}.{OUTPUT_FORMAT}')
            cv.imwrite(filename, frame)
            saved_count += 1
            print(f"Image sauvegardée: {filename} (temps: {current_time:.1f}s)")
            
        frame_number += 1
    
    cap.release()
    print(f"\nExtraction terminée. {saved_count} images sauvegardées dans {output_folder}")

def main():
    parser = argparse.ArgumentParser(
        description=f'Extrait une image toutes les {FRAMES_INTERVAL_SECONDS} secondes d\'une vidéo MP4.'
    )
    parser.add_argument('video', type=str, help='Chemin vers le fichier vidéo MP4')
    parser.add_argument('folder_name', nargs='?', type=str, 
                       help='Nom du dossier de sortie (optionnel)')
    parser.add_argument('-n', action='store_true', 
                       help='Utilise le nom du fichier sans demander')
    
    args = parser.parse_args()
    
    try:
        extract_frames(args.video, args.folder_name, args.n)
    except Exception as e:
        print(f"Erreur : {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()