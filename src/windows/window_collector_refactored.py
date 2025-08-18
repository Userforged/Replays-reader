"""
Window Collector (Refactorisé) - Orchestrateur de détection de rounds SF6

Architecture SOLID appliquée :
- Single Responsibility : Orchestration uniquement
- Open/Closed : Extensible via injection de dépendances
- Liskov Substitution : Interfaces cohérentes
- Interface Segregation : Composants spécialisés
- Dependency Inversion : Dépendances injectées

Cette version démontre l'application des principes SOLID sur le WindowCollector original.
"""

from typing import List, Dict, Optional
import sys
import os

# Imports des composants SOLID
sys.path.append(os.path.dirname(__file__))
from frame_processor import FrameProcessor
from round_detector import RoundDetector
from window_manager import WindowManager


class WindowCollectorRefactored:
    """
    Collecteur de rounds SF6 refactorisé selon les principes SOLID.

    Responsabilité unique : Orchestrer le processus de détection des rounds
    en coordonnant les composants spécialisés.
    """

    def __init__(self,
                 frame_processor: Optional[FrameProcessor] = None,
                 round_detector: Optional[RoundDetector] = None,
                 window_manager: Optional[WindowManager] = None,
                 debug: bool = False):
        """
        Initialise le collecteur avec injection de dépendances.

        Args:
            frame_processor: Processeur de frames (injecté pour testabilité)
            round_detector: Détecteur de rounds (injecté pour extensibilité)
            window_manager: Gestionnaire de fenêtres (injecté pour flexibilité)
            debug: Mode debug pour les logs
        """
        # Injection de dépendances avec valeurs par défaut
        self.frame_processor = frame_processor or FrameProcessor()
        self.round_detector = round_detector or RoundDetector()
        self.window_manager = window_manager or WindowManager()

        self.debug = debug
        self.validated_rounds: List[Dict] = []
        self.last_round_time: Optional[str] = None

    def analyze_frames(self, frames_data: List[Dict]) -> Dict:
        """
        Point d'entrée principal : analyse une séquence de frames.

        Args:
            frames_data: Liste des frames avec données OCR brutes

        Returns:
            Résultats d'analyse avec rounds détectés
        """
        if self.debug:
            print(f"🔍 WindowCollectorRefactored - Analysing {len(frames_data)} frames")

        # Phase 1: Nettoyage OCR des frames
        processed_frames = self._process_frames(frames_data)

        # Phase 2: Analyse des fenêtres de collecte
        self._analyze_windows(processed_frames)

        # Phase 3: Compilation des résultats
        return self._compile_results()

    def _process_frames(self, frames_data: List[Dict]) -> List[Dict]:
        """
        Phase 1 : Traitement et nettoyage des frames OCR.

        Délégation au FrameProcessor (SRP).
        """
        if self.debug:
            print("🧹 Phase 1: Nettoyage OCR des frames...")

        processed_frames = []
        for frame in frames_data:
            processed_frame = self.frame_processor.process_frame(frame)
            processed_frames.append(processed_frame)

        if self.debug:
            stats = self.frame_processor.get_processing_stats()
            print(f"✅ {stats['frames_processed']} frames nettoyées")

        return processed_frames

    def _analyze_windows(self, processed_frames: List[Dict]):
        """
        Phase 2 : Analyse des fenêtres de collecte.

        Orchestration entre RoundDetector et WindowManager (SRP).
        """
        if self.debug:
            print("🎯 Phase 2: Analyse des fenêtres de collecte...")

        for i, frame in enumerate(processed_frames):
            timer_value = frame.get('timer_clean')

            # Calculer le gap depuis le dernier round
            gap_seconds = self._calculate_gap_seconds(
                self.last_round_time,
                frame.get('timestamp')
            )

            # Vérifier si on doit démarrer une nouvelle collecte
            if not self.window_manager.collecting:
                if self.round_detector.should_start_round(timer_value, gap_seconds):
                    self._start_new_round(frame, i)
            else:
                # Ajouter à la collecte courante
                self.window_manager.add_to_window(frame)

                # Vérifier si on doit arrêter la collecte
                if self.round_detector.should_end_round(timer_value):
                    self._finalize_current_round()

        # Finaliser le dernier round s'il reste ouvert
        if self.window_manager.collecting:
            self._finalize_current_round()

    def _start_new_round(self, frame: Dict, frame_index: int):
        """
        Démarre une nouvelle collecte de round.

        Args:
            frame: Frame déclencheuse
            frame_index: Index de la frame
        """
        if self.debug:
            timer = frame.get('timer_clean', '?')
            timestamp = frame.get('timestamp', '?')
            print(f"🟢 TRIGGER: timer={timer} à frame {frame_index} ({timestamp}), gap confirmé")

        self.window_manager.start_window(frame, frame_index)
        self.round_detector.reset_history()

    def _finalize_current_round(self):
        """Finalise le round en cours et l'ajoute aux résultats."""
        round_data = self.window_manager.close_window()

        if round_data:
            # Validation finale du round
            if self._validate_round(round_data):
                self.validated_rounds.append(round_data)
                self.last_round_time = round_data.get('start_time')

                if self.debug:
                    self._log_round_validation(round_data)

    def _validate_round(self, round_data: Dict) -> bool:
        """
        Validation finale d'un round détecté.

        Args:
            round_data: Données du round à valider

        Returns:
            True si le round est valide
        """
        # Critères de validation
        has_timer = round_data.get('timer_start') is not None
        has_data = bool(round_data.get('character1') or round_data.get('player1'))
        good_coherence = round_data.get('coherence_score', 0) >= 0.5
        enough_frames = round_data.get('frames_count', 0) >= 3

        return has_timer and has_data and good_coherence and enough_frames

    def _log_round_validation(self, round_data: Dict):
        """Log de validation d'un round (mode debug)."""
        player1 = round_data.get('player1', '?')
        player2 = round_data.get('player2', '?')
        char1 = round_data.get('character1', '?')
        char2 = round_data.get('character2', '?')
        coherence = round_data.get('coherence_score', 0)
        start_time = round_data.get('start_time', '?')

        print(f"✅ Round validé: {start_time} - {player1} ({char1}) vs {player2} ({char2}) (cohérence: {coherence:.2f})")

    def _calculate_gap_seconds(self, time1: Optional[str], time2: Optional[str]) -> int:
        """Calcule l'écart en secondes entre 2 timestamps."""
        if not time1 or not time2:
            return 999  # Gap très large si pas de timestamp précédent

        try:
            def time_to_seconds(time_str):
                parts = time_str.split(':')
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

            return time_to_seconds(time2) - time_to_seconds(time1)
        except:
            return 999

    def _compile_results(self) -> Dict:
        """
        Phase 3 : Compilation des résultats finaux.

        Returns:
            Dictionnaire avec rounds détectés et statistiques
        """
        processing_stats = self.frame_processor.get_processing_stats()

        return {
            'rounds': self.validated_rounds,
            'stats': {
                'total_frames': processing_stats['frames_processed'],
                'rounds_detected': len(self.validated_rounds),
                'frames_with_valid_timer': processing_stats['frames_with_valid_timer'],
                'frames_with_characters': processing_stats['frames_with_characters'],
                'frames_with_players': processing_stats['frames_with_players']
            }
        }