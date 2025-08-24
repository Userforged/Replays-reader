#!/usr/bin/env python3
"""
Interactive CLI menu system for Street Fighter 6 replay analysis.
Provides user-friendly interfaces for source selection, input, and ROI configuration.
"""

import asyncio
import json
import os
import random
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import inquirer
import numpy as np

from roi_manager import RoiManager
from video_resolver import VideoResolver


class InteractiveMenu:
    """Interactive CLI menu system for SF6 replay analysis configuration."""

    def __init__(self):
        self.video_resolver = VideoResolver()
        self.roi_manager = RoiManager("rois_config.json")
        self.roi_manager.load()
        self._resolution_result = None
        self._resolution_error = None
        self._resolution_complete = threading.Event()
        # Frame caching for consistent ROI editing session
        self._cached_frame = None
        self._cached_frame_metadata = None
        self._current_video_source = None

    def welcome_banner(self):
        """Display welcome banner."""
        print("=" * 60)
        print("🥊 STREET FIGHTER 6 REPLAY ANALYZER 🥊")
        print("=" * 60)
        print("Configuration interactive pour l'analyse de replays SF6")
        print()

    def select_source_type(self) -> str:
        """Interactive source type selection menu."""
        questions = [
            inquirer.List(
                "source_type",
                message="🎯 Quel type de source voulez-vous analyser ?",
                choices=[
                    "📁 Fichier vidéo local",
                    "🎬 URL YouTube",
                ],
                carousel=True,
            ),
        ]

        answers = inquirer.prompt(questions)
        if not answers:  # User pressed Ctrl+C
            print("\n❌ Configuration annulée.")
            exit(0)

        return "local" if "local" in answers["source_type"] else "url"

    def input_local_file(self) -> str:
        """Interactive local file input with validation."""
        while True:
            questions = [
                inquirer.Path(
                    "filepath",
                    message="📁 Chemin vers le fichier vidéo",
                    path_type=inquirer.Path.FILE,
                    exists=True,
                ),
            ]

            answers = inquirer.prompt(questions)
            if not answers:
                print("\n❌ Configuration annulée.")
                exit(0)

            filepath = answers["filepath"]

            # Validate video file extensions
            video_extensions = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".webm", ".m4v"}
            if Path(filepath).suffix.lower() in video_extensions:
                return filepath
            else:
                print(
                    f"⚠️ Extension non supportée. Extensions valides: {', '.join(video_extensions)}"
                )

                retry_question = [
                    inquirer.Confirm(
                        "retry",
                        message="Voulez-vous essayer un autre fichier ?",
                        default=True,
                    )
                ]
                retry_answer = inquirer.prompt(retry_question)
                if not retry_answer or not retry_answer["retry"]:
                    print("❌ Configuration annulée.")
                    exit(0)

    def input_url_source(self) -> tuple[str, Optional[threading.Thread]]:
        """Interactive URL input with validation and async resolution."""
        while True:
            questions = [
                inquirer.Text(
                    "url",
                    message="🌐 URL YouTube ou ID de la vidéo",
                    validate=lambda _, x: self.video_resolver.is_youtube_url_or_id(x)
                    or "URL YouTube ou ID invalide (ex: SeVcgGFqG8E ou https://www.youtube.com/watch?v=SeVcgGFqG8E)",
                ),
            ]

            answers = inquirer.prompt(questions)
            if not answers:
                print("\n❌ Configuration annulée.")
                exit(0)

            url = answers["url"].strip()

            # Convert YouTube ID to full URL if needed
            normalized_url = self.video_resolver.normalize_youtube_url(url)
            if normalized_url != url:
                print(f"🔄 ID YouTube détectée, conversion: {url} → {normalized_url}")
                url = normalized_url

            # Start async resolution in background
            resolution_thread = self._start_async_resolution(url)

            # Return immediately to continue with menu
            return url, resolution_thread

    def _start_async_resolution(self, url: str) -> threading.Thread:
        """Start video resolution in background thread."""
        # Reset state
        self._resolution_result = None
        self._resolution_error = None
        self._resolution_complete.clear()

        def resolve_video():
            """Background resolution task."""
            try:
                result = self.video_resolver.resolve_source(url)
                self._resolution_result = result
            except Exception as e:
                self._resolution_error = str(e)
            finally:
                self._resolution_complete.set()

        thread = threading.Thread(target=resolve_video, daemon=True)
        thread.start()
        return thread

    def _format_duration(self, duration_seconds: int) -> str:
        """Format duration in seconds to readable h:m:s format."""
        if not duration_seconds:
            return "N/A"

        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60

        if hours > 0:
            return f"{hours}h{minutes:02d}m{seconds:02d}s"
        else:
            return f"{minutes}m{seconds:02d}s"

    def _wait_for_resolution(self, timeout: float = 30.0) -> bool:
        """Wait for resolution to complete with timeout."""
        return self._resolution_complete.wait(timeout)

    def get_resolution_result(self) -> Optional[Dict[str, Any]]:
        """Get the resolution result if available."""
        if self._resolution_complete.is_set():
            if self._resolution_error:
                raise Exception(self._resolution_error)
            return self._resolution_result
        return None

    def configure_analysis_options(self) -> Dict[str, Any]:
        """Interactive analysis options configuration."""
        questions = [
            inquirer.Text(
                "frames_per_minute",
                message="⏱️ Fréquence d'extraction (frames par minute)",
                default="12",
                validate=lambda _, x: x.isdigit()
                and int(x) > 0
                or "Nombre entier positif requis",
            ),
            inquirer.List(
                "pipeline_type",
                message="🚀 Type de pipeline à utiliser",
                choices=[
                    "⚡ Pipeline asynchrone (3-5x plus rapide)",
                    "🐌 Pipeline séquentiel (compatible)",
                ],
                default="⚡ Pipeline asynchrone (3-5x plus rapide)",
            ),
            inquirer.Confirm(
                "save_frames",
                message="💾 Sauvegarder les frames extraites ? (debug)",
                default=False,
            ),
        ]

        # Async workers question (conditional)
        answers = inquirer.prompt(questions)
        if not answers:
            print("\n❌ Configuration annulée.")
            exit(0)

        config = {
            "frames_per_minute": int(answers["frames_per_minute"]),
            "async_pipeline": "asynchrone" in answers["pipeline_type"],
            "save_frames": answers["save_frames"],
        }

        # Ask for workers count if async pipeline selected
        if config["async_pipeline"]:
            worker_question = [
                inquirer.Text(
                    "workers",
                    message="👥 Nombre de workers OCR parallèles",
                    default="3",
                    validate=lambda _, x: x.isdigit()
                    and 1 <= int(x) <= 8
                    or "Entre 1 et 8 workers",
                )
            ]
            worker_answer = inquirer.prompt(worker_question)
            if not worker_answer:
                print("\n❌ Configuration annulée.")
                exit(0)
            config["workers"] = int(worker_answer["workers"])

        return config

    def roi_configuration_menu(self) -> bool:
        """Interactive ROI configuration menu."""
        current_rois = [roi["name"] for roi in self.roi_manager.get_all_rois()]

        questions = [
            inquirer.Confirm(
                "modify_rois",
                message=f"🎯 Modifier les ROIs ? (actuels: {', '.join(current_rois)})",
                default=False,
            )
        ]

        answers = inquirer.prompt(questions)
        if not answers:
            return False

        if not answers["modify_rois"]:
            return False

        # ROI modification submenu
        while True:
            roi_questions = [
                inquirer.List(
                    "roi_action",
                    message="🎯 Configuration des ROIs",
                    choices=[
                        "👁️  Visualiser les ROIs actuels",
                        "✏️  Modifier les coordonnées d'un ROI",
                        "📊 Afficher les informations détaillées",
                        "✅ Terminer la configuration ROI",
                    ],
                    carousel=True,
                )
            ]

            roi_answers = inquirer.prompt(roi_questions)
            if not roi_answers:
                break

            action = roi_answers["roi_action"]

            if "Visualiser" in action:
                self._display_roi_summary()
            elif "Modifier" in action:
                self._modify_roi_coordinates()
            elif "Afficher" in action:
                self._display_roi_details()
            elif "Terminer" in action:
                break

        return True

    def _display_roi_summary(self):
        """Display current ROI configuration summary."""
        print("\n📊 Configuration ROI actuelle:")
        print("-" * 40)

        for roi in self.roi_manager.get_all_rois():
            roi_name = roi["name"]
            roi_config = self.roi_manager.get_roi(roi_name)
            bounds = roi_config["boundaries"]
            print(f"🎯 {roi_name.upper()}")
            print(
                f"   📍 Position: ({bounds['left']:.2f}, {bounds['top']:.2f}) → "
                f"({bounds['right']:.2f}, {bounds['bottom']:.2f})"
            )
            print(f"   🤖 Modèle: {roi_config['model']}")
        print()

    def _modify_roi_coordinates(self):
        """Interactive ROI coordinate modification."""
        roi_names = [roi["name"] for roi in self.roi_manager.get_all_rois()]

        questions = [
            inquirer.List(
                "roi_name",
                message="Quel ROI modifier ?",
                choices=[f"🎯 {name.upper()}" for name in roi_names] + ["❌ Annuler"],
            )
        ]

        answers = inquirer.prompt(questions)
        if not answers or "Annuler" in answers["roi_name"]:
            return

        roi_name = answers["roi_name"].split(" ")[1].lower()
        current_bounds = self.roi_manager.get_roi(roi_name)["boundaries"]

        print(f"\n📍 Coordonnées actuelles pour {roi_name.upper()}:")
        print(f"   Left: {current_bounds['left']}, Top: {current_bounds['top']}")
        print(
            f"   Right: {current_bounds['right']}, Bottom: {current_bounds['bottom']}"
        )

        coord_questions = [
            inquirer.Text(
                "left",
                message="Left (0.0-1.0)",
                default=str(current_bounds["left"]),
                validate=lambda _, x: self._validate_coordinate(x),
            ),
            inquirer.Text(
                "top",
                message="Top (0.0-1.0)",
                default=str(current_bounds["top"]),
                validate=lambda _, x: self._validate_coordinate(x),
            ),
            inquirer.Text(
                "right",
                message="Right (0.0-1.0)",
                default=str(current_bounds["right"]),
                validate=lambda _, x: self._validate_coordinate(x),
            ),
            inquirer.Text(
                "bottom",
                message="Bottom (0.0-1.0)",
                default=str(current_bounds["bottom"]),
                validate=lambda _, x: self._validate_coordinate(x),
            ),
        ]

        coord_answers = inquirer.prompt(coord_questions)
        if not coord_answers:
            return

        # Update ROI boundaries
        new_bounds = {
            "left": float(coord_answers["left"]),
            "top": float(coord_answers["top"]),
            "right": float(coord_answers["right"]),
            "bottom": float(coord_answers["bottom"]),
        }

        # Validate bounds make sense
        if (
            new_bounds["left"] >= new_bounds["right"]
            or new_bounds["top"] >= new_bounds["bottom"]
        ):
            print("❌ Coordonnées invalides: left < right et top < bottom requis.")
            return

        self.roi_manager.update_roi(roi_name, new_bounds)
        # Note: Changes kept in memory only - not saved to rois_config.json
        print(f"✅ ROI {roi_name.upper()} mis à jour avec succès (temporairement)!")

    def _display_roi_details(self):
        """Display detailed ROI information."""
        print("\n📋 Détails des ROIs:")
        print("=" * 50)

        for roi in self.roi_manager.get_all_rois():
            roi_name = roi["name"]
            roi_config = self.roi_manager.get_roi(roi_name)
            print(f"\n🎯 {roi_name.upper()}")
            print(f"   📍 Boundaries: {roi_config['boundaries']}")
            print(f"   🤖 Model: {roi_config['model']}")
            print(f"   🎨 Color: {roi_config['color']}")
            if "whitelist" in roi_config:
                print(f"   ✅ Whitelist: {roi_config['whitelist']}")
        print()

    def _validate_coordinate(self, value: str) -> bool:
        """Validate coordinate input."""
        try:
            coord = float(value)
            return 0.0 <= coord <= 1.0
        except ValueError:
            return False

    def _generate_timeline_bar(self, current_time: float, total_duration: float, bar_length: int = 15) -> str:
        """
        Generate a visual timeline bar showing current position.
        
        Args:
            current_time: Current timestamp in seconds
            total_duration: Total video duration in seconds  
            bar_length: Length of the progress bar
            
        Returns:
            Timeline string like "===|=======" 
        """
        if total_duration <= 0:
            return "=" * bar_length
            
        # Calculate position (0 to bar_length)
        position = int((current_time / total_duration) * bar_length)
        position = max(0, min(position, bar_length - 1))  # Clamp to valid range
        
        # Build timeline: "===" + "|" + "==="
        before = "=" * position
        after = "=" * (bar_length - position - 1)
        
        return f"{before}|{after}"

    def run_source_selection(self) -> Dict[str, Any]:
        """Run source selection part of the configuration wizard."""
        self.welcome_banner()

        # Step 1: Source type selection
        source_type = self.select_source_type()

        # Step 2: Source input
        if source_type == "local":
            source_path = self.input_local_file()
            resolution_thread = None
        else:
            source_path, resolution_thread = self.input_url_source()

        return {
            "source_type": source_type,
            "source_path": source_path,
            "_resolution_thread": resolution_thread,
        }

    def ask_roi_configuration(self) -> str:
        """Ask user about ROI configuration preferences."""
        questions = [
            inquirer.List(
                "roi_choice",
                message="🎯 Voulez-vous modifier les Regions of Interest pour cette vidéo",
                choices=[
                    "👍 Garder les ROIs actuels et lancer l'export",
                    "⚙️ Modifier les ROIs",
                    "👁️ Voir les ROIs sur une image au hasard",
                ],
                carousel=True,
            )
        ]

        answers = inquirer.prompt(questions)
        if not answers:  # User pressed Ctrl+C
            print("\n❌ Configuration annulée.")
            exit(0)

        choice = answers["roi_choice"]
        if "Modifier" in choice:
            return "yes"
        elif "Garder" in choice:
            return "no"
        elif "Voir" in choice:
            return "preview"

        return "no"  # Default fallback

    def roi_modification_menu(self, video_source: str) -> str:
        """Menu for modifying ROIs with save/launch options."""
        print("⚙️ Configuration des Regions of Interest")
        print("=" * 50)

        while True:
            # Get available ROIs from RoiManager
            available_rois = self.roi_manager.get_all_rois()

            # Build dynamic menu choices
            choices = []

            # Add modification option for each ROI
            for roi_data in available_rois:
                roi_name = roi_data["name"]
                roi_display_name = roi_name.upper()
                choices.append(f"🔧 Modifier la ROI {roi_display_name}")

            # Add save/launch options
            choices.extend(
                [
                    "💾 Sauvegarder et lancer l'export",
                    "🚀 Lancer l'export sans sauvegarder",
                    "🎲 Tirer une nouvelle image au hasard",
                ]
            )

            questions = [
                inquirer.List(
                    "modification_choice",
                    message="🎯 Que voulez-vous faire",
                    choices=choices,
                    carousel=True,
                )
            ]

            answers = inquirer.prompt(questions)
            if not answers:
                print("\n❌ Configuration annulée.")
                exit(0)

            choice = answers["modification_choice"]

            if "Modifier la ROI" in choice:
                # Extract ROI name from choice
                roi_name = choice.split("ROI ")[-1].lower()
                print(f"🔧 Modification de la ROI {roi_name.upper()} sélectionnée")
                success = self._visual_roi_modification(roi_name, video_source)
                if success:
                    print(f"✅ ROI {roi_name.upper()} modifiée avec succès!")
                else:
                    print(f"❌ Modification de la ROI {roi_name.upper()} annulée")

            elif "Sauvegarder et lancer" in choice:
                print("💾 Sauvegarde et lancement de l'export sélectionnés")
                return "save_and_launch"

            elif "Lancer l'export sans sauvegarder" in choice:
                print("🚀 Lancement sans sauvegarde sélectionné")
                return "launch_no_save"

            elif "Tirer une nouvelle image" in choice:
                # Extract a new random frame and show preview
                print("🎲 Sélection d'une nouvelle frame aléatoire...")
                # Force extraction of a new random frame
                frame, metadata = self._extract_random_frame_from_video(video_source, "nouvelle sélection", force_new=True)
                if frame is not None:
                    # Show preview with the new frame
                    annotated_frame = self.roi_manager.preview_rois_on_image(frame, show_labels=True)
                    frame_info = f"Frame #{metadata['frame_number']} ({metadata['timestamp']:.1f}s)"
                    self._display_frame_with_rois(annotated_frame, f"Nouvelle Frame - {frame_info}")
                    print("✅ Nouvelle frame sélectionnée ! Cette frame sera utilisée pour les prochaines modifications de ROI.")
                else:
                    print("⚠️ Impossible de sélectionner une nouvelle frame")
                print()  # Empty line for readability

    def roi_configuration_loop(
        self, video_source: str, resolution_thread: Optional[threading.Thread] = None
    ) -> str:
        """Loop to ask ROI configuration with preview option."""
        while True:
            roi_choice = self.ask_roi_configuration()

            if roi_choice == "preview":
                # Wait for resolution if still in progress
                if resolution_thread and resolution_thread.is_alive():
                    print("⏳ Attente de la résolution vidéo...")
                    if self._wait_for_resolution(timeout=30):
                        try:
                            result = self.get_resolution_result()
                            if (
                                result
                                and result.get("is_stream")
                                and result.get("metadata", {}).get("title")
                            ):
                                print(
                                    f'📺 Nom de la vidéo: "{result["metadata"]["title"]}"'
                                )
                                # Note: Les détails précis (durée, frames) seront affichés par OpenCV
                        except Exception as e:
                            print(f"❌ Erreur de résolution: {str(e)}")
                    else:
                        print("⚠️ Timeout de résolution, tentative avec URL directe...")

                success = self.preview_rois_on_random_frame(video_source)
                if not success:
                    print("⚠️  Impossible d'afficher l'aperçu des ROIs")
                # Continue la boucle pour re-poser la question
                print()  # Ligne vide pour lisibilité
            elif roi_choice == "yes":
                # Lancer le menu de modification des ROIs
                modification_result = self.roi_modification_menu(video_source)
                return modification_result
            else:
                # Retourner le choix final (no)
                return roi_choice

    def _extract_random_frame_from_video(self, video_source: str, purpose: str = "analyse", force_new: bool = False) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
        """
        Extract a random frame from video with metadata.
        
        Used by both preview_rois_on_random_frame and _visual_roi_modification
        to ensure consistent frame selection logic.
        
        Features frame caching: once a frame is selected for a video source,
        the same frame is reused for all operations in the session unless
        force_new=True is specified.
        
        Args:
            video_source: Video source (local file or URL)
            purpose: Description for logging ("analyse", "édition", etc.)
            force_new: Force extraction of a new random frame
            
        Returns:
            Tuple of (frame, metadata) where metadata contains:
            - frame_number: Selected frame number
            - timestamp: Time in seconds  
            - fps: Video FPS
            - total_frames: Total video frames
            - duration_seconds: Video duration
        """
        # Check if we can use cached frame
        if (not force_new and 
            self._cached_frame is not None and 
            self._current_video_source == video_source):
            print(f"🎬 Réutilisation de la frame précédemment sélectionnée pour {purpose}...")
            frame_info = f"#{self._cached_frame_metadata['frame_number']} ({self._cached_frame_metadata['timestamp']:.1f}s)"
            print(f"🎯 Frame utilisée: {frame_info}")
            return self._cached_frame.copy(), self._cached_frame_metadata.copy()
        try:
            print(f"🎬 Extraction d'une frame aléatoire pour {purpose}...")
            
            # Resolve video source
            resolved = self.video_resolver.resolve_source(video_source)
            video_path = resolved["path"]
            
            # Open video
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"❌ Impossible d'ouvrir la vidéo: {video_source}")
                return None, {}
            
            # Get video properties
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration_seconds = total_frames / fps if fps > 0 else 0
            
            # Format duration with h:m:s
            duration_hms = self._format_duration(int(duration_seconds))
            print(
                f"⏰ Durée: {int(duration_seconds)}s ({duration_hms}) - {total_frames} frames"
            )
            
            # Skip first and last 10% to avoid intro/outro
            start_frame = int(total_frames * 0.1)
            end_frame = int(total_frames * 0.9)
            
            # Random frame selection
            random_frame_number = random.randint(start_frame, end_frame)
            random_time = random_frame_number / fps if fps > 0 else 0
            
            # Generate visual timeline
            timeline = self._generate_timeline_bar(random_time, duration_seconds)
            
            print(f"🎯 Frame sélectionnée: #{random_frame_number} {timeline} à {random_time:.1f}s (sur {duration_seconds:.0f}s)")
            
            # Seek to random frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, random_frame_number)
            
            # Read frame
            ret, frame = cap.read()
            cap.release()
            
            if not ret or frame is None:
                print("❌ Impossible de lire la frame")
                return None, {}
            
            # Cache the frame and metadata
            metadata = {
                "frame_number": random_frame_number,
                "timestamp": random_time,
                "fps": fps,
                "total_frames": total_frames,
                "duration_seconds": duration_seconds,
                "duration_formatted": duration_hms
            }
            
            # Update cache
            self._cached_frame = frame.copy()
            self._cached_frame_metadata = metadata.copy()
            self._current_video_source = video_source
            
            return frame, metadata
            
        except Exception as e:
            print(f"❌ Erreur lors de l'extraction de frame: {str(e)}")
            return None, {}
    
    def preview_rois_on_random_frame(self, video_source: str) -> bool:
        """Preview ROIs on a random frame from the video."""
        # Extract random frame using refactored method
        frame, metadata = self._extract_random_frame_from_video(video_source, "prévisualisation")
        
        if frame is None:
            return False
            
        try:
            # Draw ROIs on frame using RoiManager method
            annotated_frame = self.roi_manager.preview_rois_on_image(
                frame, show_labels=True
            )
            
            # Display frame
            frame_info = f"Frame #{metadata['frame_number']} ({metadata['timestamp']:.1f}s)"
            self._display_frame_with_rois(
                annotated_frame,
                f"ROIs Preview - {frame_info}",
            )
            
            return True
            
        except Exception as e:
            print(f"❌ Erreur lors de l'affichage: {str(e)}")
            return False

    def _visual_roi_modification(self, roi_name: str, video_source: str) -> bool:
        """
        Launch visual ROI editor using the new ImageViewer integration.
        
        Uses the same frame extraction logic as preview_rois_on_random_frame
        to ensure consistent behavior.
        
        Args:
            roi_name: Name of the ROI to modify
            video_source: Video source for frame extraction
            
        Returns:
            True if ROI was modified successfully
        """
        # Extract random frame using refactored method (same as preview)
        frame, metadata = self._extract_random_frame_from_video(video_source, f"édition de {roi_name.upper()}")
        
        if frame is None:
            return False
        
        try:
            print(f"🎯 Lancement de l'éditeur visuel pour {roi_name.upper()}...")
            print("💡 Utilisez la souris pour déplacer/redimensionner, ENTRÉE pour sauvegarder, ESC pour annuler")
            
            # Launch visual editor using new API
            success = self.roi_manager.edit_roi_on_image(frame, roi_name)
            
            if success:
                frame_info = f"Frame #{metadata['frame_number']} ({metadata['timestamp']:.1f}s)"
                print(f"✅ ROI {roi_name.upper()} modifiée avec succès sur {frame_info}")
            
            return success
            
        except Exception as e:
            print(f"❌ Erreur lors de l'édition visuelle: {str(e)}")
            return False

    def _display_frame_with_rois(self, frame: np.ndarray, window_title: str):
        """Display frame with ROIs in a window."""
        try:
            # Resize frame if too large
            height, width = frame.shape[:2]
            max_height, max_width = 800, 1200

            if height > max_height or width > max_width:
                scale = min(max_height / height, max_width / width)
                new_width = int(width * scale)
                new_height = int(height * scale)
                frame = cv2.resize(frame, (new_width, new_height))

            # Display frame
            cv2.imshow(window_title, frame)

            print(
                "🪟 Fenêtre ouverte avec les ROIs affichées - Appuyez sur n'importe quelle touche pour fermer..."
            )

            # Wait for key press
            cv2.waitKey(0)
            cv2.destroyAllWindows()

            print("✅ Fenêtre refermée.")

        except Exception as e:
            print(f"❌ Erreur d'affichage: {str(e)}")
            # Fallback: save frame to file
            try:
                output_path = "output/roi_preview.jpg"
                cv2.imwrite(output_path, frame)
                print(f"💾 Frame sauvegardée: {output_path}")
            except Exception as save_error:
                print(f"❌ Erreur de sauvegarde: {str(save_error)}")

    def run_configuration_wizard(self) -> Dict[str, Any]:
        """Run the complete interactive configuration wizard."""
        self.welcome_banner()

        # Step 1: Source type selection
        source_type = self.select_source_type()

        # Step 2: Source input
        if source_type == "local":
            source_path = self.input_local_file()
        else:
            source_path = self.input_url_source()

        # Step 3: Analysis options
        analysis_config = self.configure_analysis_options()

        # Step 4: ROI configuration (optional)
        self.roi_configuration_menu()

        # Final configuration summary
        config = {
            "source_type": source_type,
            "source_path": source_path,
            **analysis_config,
        }

        print("\n" + "=" * 60)
        print("📋 CONFIGURATION FINALE")
        print("=" * 60)
        print(f"📁 Source: {config['source_path']}")
        print(f"⏱️  Frames/min: {config['frames_per_minute']}")
        print(
            f"🚀 Pipeline: {'Asynchrone' if config['async_pipeline'] else 'Séquentiel'}"
        )
        if config.get("workers"):
            print(f"👥 Workers: {config['workers']}")
        print(f"💾 Sauvegarder frames: {'Oui' if config['save_frames'] else 'Non'}")
        print()

        confirm_question = [
            inquirer.Confirm(
                "proceed",
                message="🚀 Lancer l'analyse avec cette configuration ?",
                default=True,
            )
        ]

        confirm_answer = inquirer.prompt(confirm_question)
        if not confirm_answer or not confirm_answer["proceed"]:
            print("❌ Analyse annulée.")
            exit(0)

        return config


def main():
    """Test the interactive menu system."""
    menu = InteractiveMenu()
    config = menu.run_configuration_wizard()
    print(f"Configuration générée: {config}")


if __name__ == "__main__":
    main()
