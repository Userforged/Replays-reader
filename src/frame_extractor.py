import cv2 as cv
import os
from datetime import datetime
from .video_resolver import VideoResolver

class FrameExtractor:
    OUTPUT_FORMAT = 'png'
    OUTPUT_DIR = 'input'
    FRAMES_DIR = 'frames'

    def __init__(self, video_source, output_name=None, no_prompt=False,
                 frames_per_minute=12, debug=False, manual_format=None):
        self._initialize_basic_properties(
            video_source, frames_per_minute, debug, manual_format
        )
        self._resolve_video_source()
        self._setup_output_configuration(
            video_source, output_name, no_prompt
        )

    def _initialize_basic_properties(self, video_source, frames_per_minute, debug, manual_format):
        """Initialize basic extractor properties."""
        self.video_source = video_source
        self.frames_per_minute = frames_per_minute
        self.frame_interval_seconds = 60.0 / frames_per_minute
        self.debug = debug
        self.manual_format = manual_format

    def _resolve_video_source(self):
        """Resolve video source to processable format using VideoResolver."""
        # Si format manuel spécifié, créer VideoResolver avec ce format en priorité
        if self.manual_format:
            if self.debug:
                print(f"[FrameExtractor] Using manual format: {self.manual_format}")
            self.resolver = VideoResolver(preferred_quality=self.manual_format)
        else:
            self.resolver = VideoResolver()

        if self.debug:
            print(f"[FrameExtractor] Resolving video source: '{self.video_source}'")

        try:
            self.resolved_source = self.resolver.resolve_source(self.video_source)
            self.video_path = self.resolved_source['path']
            self.is_stream = self.resolved_source['is_stream']

            if self.debug:
                print(f"[FrameExtractor] Source resolved:")
                print(f"  Path: '{self.video_path}'")
                print(f"  Is stream: {self.is_stream}")
                print(f"  Source type: {self.resolved_source['metadata']['source_type']}")

        except Exception as e:
            if self.debug:
                print(f"[FrameExtractor] Failed to resolve video source: {e}")
            raise ValueError(f"Cannot resolve video source '{self.video_source}': {e}")

    def _setup_output_configuration(self, video_source, output_name, no_prompt):
        """Setup output directory configuration."""
        self.output_name = self.get_video_name(
            video_source, output_name, no_prompt
        )
        # Don't create directories here - only when actually needed
        self.output_folder = None

    def get_video_name(self, video_source, folder_name=None, no_prompt=False):
        # Generate default name based on source type
        if self.resolver.is_url(video_source):
            # For URLs, try to get title from metadata or use a sanitized version
            metadata = self.resolved_source.get('metadata', {})
            title = metadata.get('title', 'online_video')
            # Sanitize title for filesystem
            import re
            default_name = re.sub(r'[<>:"/\\|?*]', '_', title)[:50]  # Limit length
        else:
            default_name = os.path.splitext(os.path.basename(video_source))[0]

        if self.debug:
            print(f"[FrameExtractor] get_video_name: default_name='{default_name}', folder_name='{folder_name}', no_prompt={no_prompt}")

        if folder_name:
            if self.debug:
                print(f"[FrameExtractor] Using provided folder_name: '{folder_name}'")
            return folder_name
        if no_prompt:
            if self.debug:
                print(f"[FrameExtractor] No prompt mode, using default: '{default_name}'")
            return default_name
        user_input = input(f"Nom du dossier de sortie [{default_name}]: ").strip()
        result = user_input if user_input else default_name
        if self.debug:
            print(f"[FrameExtractor] User input result: '{result}'")
        return result

    def _prepare_output_directory(self):
        if self.debug:
            print(f"[FrameExtractor] _prepare_output_directory: OUTPUT_DIR='{self.OUTPUT_DIR}', FRAMES_DIR='{self.FRAMES_DIR}', output_name='{self.output_name}'")

        if not os.path.exists(self.OUTPUT_DIR):
            if self.debug:
                print(f"[FrameExtractor] Creating OUTPUT_DIR: '{self.OUTPUT_DIR}'")
            os.makedirs(self.OUTPUT_DIR)

        frames_path = os.path.join(self.OUTPUT_DIR, self.FRAMES_DIR)
        if not os.path.exists(frames_path):
            if self.debug:
                print(f"[FrameExtractor] Creating frames_path: '{frames_path}'")
            os.makedirs(frames_path)

        output_folder = os.path.join(frames_path, self.output_name)
        if not os.path.exists(output_folder):
            if self.debug:
                print(f"[FrameExtractor] Creating output_folder: '{output_folder}'")
            os.makedirs(output_folder)
        else:
            if self.debug:
                print(f"[FrameExtractor] output_folder already exists: '{output_folder}'")
            print(f"⚠️ Le dossier {output_folder} existe déjà")

        if self.debug:
            print(f"[FrameExtractor] Final output_folder: '{output_folder}'")
        return output_folder

    def extract_frames(self):
        """Extract frames from video and save to disk."""
        self._log_debug(f"extract_frames: video_path='{self.video_path}' (stream: {self.is_stream})")
        self._validate_video_source()

        # Create output directory only when actually saving files
        if not self.output_folder:
            self.output_folder = self._prepare_output_directory()

        cap = self._open_video_capture()
        video_info = self._get_video_properties(cap)
        self._display_extraction_info(video_info)

        saved_count = self._extract_frames_loop(cap, video_info['fps'])

        cap.release()
        self._log_debug("Video capture released")
        print(f"\nExtraction terminée. {saved_count} images sauvegardées dans {self.output_folder}")

    def _validate_video_source(self):
        """Validate video source (file or stream) is accessible."""
        if self.is_stream:
            # For streams, we already validated via VideoResolver
            self._log_debug(f"Stream source validated: '{self.video_path}'")
            return

        # For local files, check existence and format
        if not os.path.exists(self.video_path):
            self._log_debug(f"Video file not found: '{self.video_path}'")
            raise FileNotFoundError(f"Le fichier vidéo '{self.video_path}' n'existe pas.")

        if not self.video_path.lower().endswith('.mp4'):
            self._log_debug(f"Invalid file format: '{self.video_path}'")
            raise ValueError("Le fichier doit être au format MP4.")

    def _open_video_capture(self):
        """Open and validate video capture."""
        self._log_debug("Opening video capture")
        cap = cv.VideoCapture(self.video_path)

        if not cap.isOpened():
            self._log_debug("Failed to open video capture")
            raise RuntimeError("Erreur: Impossible d'ouvrir la vidéo")

        return cap

    def _get_video_properties(self, cap):
        """Extract video properties for frame extraction."""
        fps = cap.get(cv.CAP_PROP_FPS)
        frame_count = int(cap.get(cv.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps
        frames_per_extraction = int(fps * self.frame_interval_seconds)

        video_info = {
            'fps': fps,
            'frame_count': frame_count,
            'duration': duration,
            'frames_per_extraction': frames_per_extraction
        }

        if self.debug:
            print(f"[FrameExtractor] Video properties: fps={fps}, frame_count={frame_count}, duration={duration:.2f}s")
            print(f"[FrameExtractor] Extraction settings: frames_per_minute={self.frames_per_minute}, interval={self.frame_interval_seconds:.1f}s, frames_per_extraction={frames_per_extraction}")

        return video_info

    def _display_extraction_info(self, video_info):
        """Display extraction configuration information."""
        source_type = "stream" if self.is_stream else "file"
        print(f"\nExtracting frames from {source_type}: {self.video_source}")
        if self.is_stream and self.resolved_source['metadata'].get('title'):
            print(f"Title: {self.resolved_source['metadata']['title']}")
        print(f"Output directory: {self.output_folder}")
        print(f"FPS: {video_info['fps']}")
        print(f"Durée totale: {video_info['duration']:.2f} secondes")
        print(f"Fréquence d'extraction: {self.frames_per_minute} frames par minute ({self.frame_interval_seconds:.1f}s d'intervalle)")
        print(f"Une image sera extraite tous les {video_info['frames_per_extraction']} frames")

    def _extract_frames_loop(self, cap, fps):
        """Main frame extraction loop."""
        frame_number = 0
        saved_count = 0
        next_extraction_time = 0.0

        self._log_debug("Starting frame extraction loop")

        while True:
            ret, frame = cap.read()
            if not ret:
                self._log_debug(f"End of video reached at frame {frame_number}")
                break

            current_time = frame_number / fps

            if current_time >= next_extraction_time:
                saved_count += 1
                self._save_frame(frame, current_time, frame_number)
                next_extraction_time += self.frame_interval_seconds

            frame_number += 1

        return saved_count

    def _save_frame(self, frame, current_time, frame_number):
        """Save individual frame to disk."""
        timestamp = datetime.fromtimestamp(current_time).strftime('%H-%M-%S')
        filename = os.path.join(
            self.output_folder, f'frame_{timestamp}.{self.OUTPUT_FORMAT}'
        )

        self._log_debug(
            f"Extracting frame {frame_number} at time {current_time:.1f}s -> {filename}"
        )

        cv.imwrite(filename, frame)
        print(f"Image sauvegardée: {filename} (temps: {current_time:.1f}s)")

    def _log_debug(self, message):
        """Log debug message if debug mode is enabled."""
        if self.debug:
            print(f"[FrameExtractor] {message}")

    def generate_frames(self):
        """
        Générateur qui yield les frames de la vidéo selon l'intervalle configuré.

        Yields:
            tuple: (frame, timestamp_seconds, formatted_timestamp)
        """
        if self.debug:
            source_type = "stream" if self.is_stream else "file"
            print(f"[FrameExtractor] generate_frames: Starting frame generation from {source_type} '{self.video_source}'")

        # Validate source (already resolved during initialization)
        self._validate_video_source()

        cap = cv.VideoCapture(self.video_path)
        if not cap.isOpened():
            if self.debug:
                print("[FrameExtractor] Failed to open video capture")
            raise RuntimeError("Erreur: Impossible d'ouvrir la vidéo")

        try:
            fps = cap.get(cv.CAP_PROP_FPS)
            total_frames = int(cap.get(cv.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps

            if self.debug:
                print(f"[FrameExtractor] Video properties: fps={fps}, total_frames={total_frames}, duration={duration:.2f}s")
                print(f"[FrameExtractor] Frame interval: {self.frame_interval_seconds:.1f}s")

            current_time = 0.0
            frame_count = 0

            while current_time < duration:
                # Position vidéo au timestamp spécifique
                cap.set(cv.CAP_PROP_POS_MSEC, current_time * 1000)

                ret, frame = cap.read()
                if not ret:
                    if self.debug:
                        print(f"[FrameExtractor] Failed to read frame at {current_time:.1f}s")
                    current_time += self.frame_interval_seconds
                    continue

                # Format timestamp pour affichage
                hours = int(current_time // 3600)
                minutes = int((current_time % 3600) // 60)
                seconds = int(current_time % 60)
                formatted_timestamp = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                if self.debug:
                    print(f"[FrameExtractor] Yielding frame at {current_time:.1f}s ({formatted_timestamp})")

                yield frame, current_time, formatted_timestamp

                frame_count += 1
                current_time += self.frame_interval_seconds

            if self.debug:
                print(f"[FrameExtractor] Frame generation complete. Generated {frame_count} frames.")

        finally:
            cap.release()
            if self.debug:
                print("[FrameExtractor] Video capture released")
