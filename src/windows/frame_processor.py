"""
Frame Processor - Traitement et nettoyage des frames OCR

Responsabilité unique : Nettoyer et normaliser les données OCR des frames.
Principe SRP appliqué - séparation du traitement OCR de la logique de collection.
"""

from typing import Dict, Optional
import sys
import os

# Import du TextValidator
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from text_validator import TextValidator


class FrameProcessor:
    """
    Processeur spécialisé pour le nettoyage et la validation des frames OCR.

    Responsabilités :
    - Nettoyer les données OCR (timers, personnages, joueurs)
    - Valider et normaliser les valeurs détectées
    - Appliquer les règles métier de validation
    """

    def __init__(self, characters_file: str = "characters.json",
                 restricted_players_file: Optional[str] = None):
        """Initialise le processeur avec les fichiers de validation."""
        self.text_validator = TextValidator(
            characters_file=characters_file,
            restricted_players_file=restricted_players_file
        )
        self.stats = {
            'frames_processed': 0,
            'frames_with_valid_timer': 0,
            'frames_with_characters': 0,
            'frames_with_players': 0
        }

    def process_frame(self, frame: Dict) -> Dict:
        """
        Traite une frame en nettoyant toutes ses données OCR.

        Args:
            frame: Données OCR brutes de la frame

        Returns:
            Frame nettoyée et validée
        """
        self.stats['frames_processed'] += 1

        processed_frame = frame.copy()

        # Nettoyer le timer
        processed_frame['timer_clean'] = self._clean_timer(frame.get('timer_value', ''))
        if processed_frame['timer_clean'] is not None:
            self.stats['frames_with_valid_timer'] += 1

        # Nettoyer les personnages
        char1_clean = self._clean_character(frame.get('character1', ''))
        char2_clean = self._clean_character(frame.get('character2', ''))
        processed_frame['character1_clean'] = char1_clean
        processed_frame['character2_clean'] = char2_clean

        if char1_clean or char2_clean:
            self.stats['frames_with_characters'] += 1

        # Nettoyer les joueurs
        player1_clean = self._clean_player(frame.get('player1', ''))
        player2_clean = self._clean_player(frame.get('player2', ''))
        processed_frame['player1_clean'] = player1_clean
        processed_frame['player2_clean'] = player2_clean

        if player1_clean or player2_clean:
            self.stats['frames_with_players'] += 1

        return processed_frame

    def _clean_timer(self, timer_raw: str) -> Optional[int]:
        """Nettoie et valide une valeur de timer."""
        if not timer_raw:
            return None

        validated = self.text_validator.validate_timer(timer_raw)
        if validated and validated.isdigit():
            return int(validated)
        return None

    def _clean_character(self, character_raw: str) -> Optional[str]:
        """Nettoie et valide un nom de personnage."""
        if not character_raw:
            return None

        return self.text_validator.validate_character(character_raw)

    def _clean_player(self, player_raw: str) -> Optional[str]:
        """Nettoie et valide un nom de joueur."""
        if not player_raw:
            return None

        return self.text_validator.validate_player(player_raw)

    def get_processing_stats(self) -> Dict:
        """Retourne les statistiques de traitement."""
        return self.stats.copy()

    def reset_stats(self):
        """Remet à zéro les statistiques."""
        for key in self.stats:
            self.stats[key] = 0