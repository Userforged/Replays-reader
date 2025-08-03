import cv2 as cv
import os
from datetime import datetime

class FrameExtractor:
    FRAMES_INTERVAL_SECONDS = 5
    OUTPUT_FORMAT = 'png'
    OUTPUT_DIR = 'input'
    FRAMES_DIR = 'frames'

    def __init__(self, video_path, output_name=None, no_prompt=False):
        self.video_path = video_path
        self.output_name = self.get_video_name(video_path, output_name, no_prompt)
        self.output_folder = self._prepare_output_directory()

    def get_video_name(self, video_path, folder_name=None, no_prompt=False):
        default_name = os.path.splitext(os.path.basename(video_path))[0]
        if folder_name:
            return folder_name
        if no_prompt:
            return default_name
        user_input = input(f"Nom du dossier de sortie [{default_name}]: ").strip()
        return user_input if user_input else default_name

    def _prepare_output_directory(self):
        if not os.path.exists(self.OUTPUT_DIR):
            os.makedirs(self.OUTPUT_DIR)

        frames_path = os.path.join(self.OUTPUT_DIR, self.FRAMES_DIR)
        if not os.path.exists(frames_path):
            os.makedirs(frames_path)

        output_folder = os.path.join(frames_path, self.output_name)
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        else:
            print(f"⚠️ Le dossier {output_folder} existe déjà")

        return output_folder

    def extract_frames(self):
        if not os.path.exists(self.video_path):
            raise FileNotFoundError(f"Le fichier vidéo '{self.video_path}' n'existe pas.")

        if not self.video_path.lower().endswith('.mp4'):
            raise ValueError("Le fichier doit être au format MP4.")

        cap = cv.VideoCapture(self.video_path)
        if not cap.isOpened():
            raise RuntimeError("Erreur: Impossible d'ouvrir la vidéo")

        fps = cap.get(cv.CAP_PROP_FPS)
        frame_count = int(cap.get(cv.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps
        frames_per_extraction = int(fps * self.FRAMES_INTERVAL_SECONDS)

        print(f"\nExtracting frames from: {self.video_path}")
        print(f"Output directory: {self.output_folder}")
        print(f"FPS: {fps}")
        print(f"Durée totale: {duration:.2f} secondes")
        print(f"Intervalle d'extraction: {self.FRAMES_INTERVAL_SECONDS} secondes")
        print(f"Une image sera extraite tous les {frames_per_extraction} frames")

        frame_number = 0
        saved_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            current_time = frame_number / fps

            if current_time % self.FRAMES_INTERVAL_SECONDS == 0:
                timestamp = datetime.fromtimestamp(current_time).strftime('%H-%M-%S')
                filename = os.path.join(self.output_folder, f'frame_{timestamp}.{self.OUTPUT_FORMAT}')
                cv.imwrite(filename, frame)
                saved_count += 1
                print(f"Image sauvegardée: {filename} (temps: {current_time:.1f}s)")

            frame_number += 1

        cap.release()
        print(f"\nExtraction terminée. {saved_count} images sauvegardées dans {self.output_folder}")
