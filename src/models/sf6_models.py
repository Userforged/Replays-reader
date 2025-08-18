"""
SF6 Match Structure Models

Modélisation de la structure hiérarchique des matches Street Fighter 6 :
- Match : Affrontement entre 2 joueurs (peut contenir plusieurs sets)
- Set : Même paire de personnages au sein d'un match (peut contenir plusieurs rounds)
- Round : Combat individuel avec timer qui descend de 99 à 0

Cette modélisation est distincte des données OCR brutes (frames).
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import json


@dataclass
class Round:
    """
    Un round individuel dans SF6.

    Représente un combat avec timer qui descend de 99 à 0.
    """
    round_number: int
    start_time: str                # Format "HH:MM:SS" - temps réel estimé (rétro-engineering)
    end_time: Optional[str] = None # Format "HH:MM:SS" - quand le round se termine
    duration_seconds: Optional[int] = None  # Durée en secondes
    timer_start: int = 99          # Timer de début (toujours 99 en théorie)
    timer_end: Optional[int] = None # Timer de fin
    winner: Optional[str] = None   # Nom du joueur gagnant
    frames_count: int = 0          # Nombre de frames OCR utilisées pour détecter ce round
    confidence: float = 1.0        # Score de confiance de la détection (0.0 à 1.0)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour sérialisation JSON"""
        return {
            "round_number": self.round_number,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "timer_start": self.timer_start,
            "timer_end": self.timer_end,
            "winner": self.winner,
            "frames_count": self.frames_count,
            "confidence": self.confidence
        }


@dataclass
class Set:
    """
    Un set dans SF6.

    Représente une série de rounds entre la même paire de personnages.
    Les joueurs peuvent changer de personnages entre les sets.
    """
    set_number: int
    character1: str                # Personnage du joueur 1
    character2: str                # Personnage du joueur 2
    start_time: str                # Format "HH:MM:SS" - début du premier round
    end_time: Optional[str] = None # Format "HH:MM:SS" - fin du dernier round
    rounds: List[Round] = field(default_factory=list)
    winner: Optional[str] = None   # Nom du joueur gagnant du set

    @property
    def rounds_count(self) -> int:
        """Nombre de rounds dans ce set"""
        return len(self.rounds)

    @property
    def duration_seconds(self) -> Optional[int]:
        """Durée totale du set en secondes"""
        if not self.start_time or not self.end_time:
            return None

        start = self._parse_time(self.start_time)
        end = self._parse_time(self.end_time)
        return int((end - start).total_seconds())

    def _parse_time(self, time_str: str) -> datetime:
        """Parse un timestamp HH:MM:SS vers datetime"""
        return datetime.strptime(time_str, "%H:%M:%S")

    def add_round(self, round_obj: Round) -> None:
        """Ajoute un round au set"""
        self.rounds.append(round_obj)

        # Mettre à jour end_time
        if round_obj.end_time:
            self.end_time = round_obj.end_time

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour sérialisation JSON"""
        return {
            "set_number": self.set_number,
            "character1": self.character1,
            "character2": self.character2,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "rounds_count": self.rounds_count,
            "duration_seconds": self.duration_seconds,
            "winner": self.winner,
            "rounds": [r.to_dict() for r in self.rounds]
        }


@dataclass
class Match:
    """
    Un match complet dans SF6.

    Représente un affrontement entre 2 joueurs, pouvant contenir plusieurs sets.
    Les personnages peuvent changer entre les sets, mais les joueurs restent constants.
    """
    match_id: int
    player1: str                   # Nom du joueur 1
    player2: str                   # Nom du joueur 2
    start_time: str                # Format "HH:MM:SS" - début du premier set
    end_time: Optional[str] = None # Format "HH:MM:SS" - fin du dernier set
    sets: List[Set] = field(default_factory=list)
    winner: Optional[str] = None   # Nom du joueur gagnant du match
    tournament_context: Optional[str] = None  # Ex: "Winners Finals", "Grand Finals"

    @property
    def sets_count(self) -> int:
        """Nombre de sets dans ce match"""
        return len(self.sets)

    @property
    def total_rounds(self) -> int:
        """Nombre total de rounds dans ce match"""
        return sum(s.rounds_count for s in self.sets)

    @property
    def duration_seconds(self) -> Optional[int]:
        """Durée totale du match en secondes"""
        if not self.start_time or not self.end_time:
            return None

        start = self._parse_time(self.start_time)
        end = self._parse_time(self.end_time)
        return int((end - start).total_seconds())

    @property
    def character_pairs(self) -> List[str]:
        """Liste des paires de personnages utilisées dans ce match"""
        pairs = []
        for set_obj in self.sets:
            pair = f"{set_obj.character1} vs {set_obj.character2}"
            if pair not in pairs:
                pairs.append(pair)
        return pairs

    def _parse_time(self, time_str: str) -> datetime:
        """Parse un timestamp HH:MM:SS vers datetime"""
        return datetime.strptime(time_str, "%H:%M:%S")

    def add_set(self, set_obj: Set) -> None:
        """Ajoute un set au match"""
        self.sets.append(set_obj)

        # Mettre à jour end_time
        if set_obj.end_time:
            self.end_time = set_obj.end_time

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour sérialisation JSON"""
        return {
            "match_id": self.match_id,
            "player1": self.player1,
            "player2": self.player2,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "sets_count": self.sets_count,
            "total_rounds": self.total_rounds,
            "duration_seconds": self.duration_seconds,
            "winner": self.winner,
            "tournament_context": self.tournament_context,
            "character_pairs": self.character_pairs,
            "sets": [s.to_dict() for s in self.sets]
        }


@dataclass
class VideoAnalysis:
    """
    Résultat complet de l'analyse d'une vidéo SF6.

    Contient tous les matches détectés plus les métadonnées.
    """
    video_name: str
    video_duration: str            # Format "HH:MM:SS"
    analysis_date: str             # Format ISO 8601
    matches: List[Match] = field(default_factory=list)

    # Métadonnées techniques
    total_frames_analyzed: int = 0
    frames_with_timer: int = 0
    detection_method: str = "window_based"
    parameters: Dict[str, Any] = field(default_factory=dict)

    @property
    def matches_count(self) -> int:
        """Nombre total de matches détectés"""
        return len(self.matches)

    @property
    def sets_count(self) -> int:
        """Nombre total de sets détectés"""
        return sum(m.sets_count for m in self.matches)

    @property
    def rounds_count(self) -> int:
        """Nombre total de rounds détectés"""
        return sum(m.total_rounds for m in self.matches)

    @property
    def timer_detection_rate(self) -> float:
        """Taux de détection des timers (0.0 à 1.0)"""
        if self.total_frames_analyzed == 0:
            return 0.0
        return self.frames_with_timer / self.total_frames_analyzed

    def add_match(self, match: Match) -> None:
        """Ajoute un match à l'analyse"""
        self.matches.append(match)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour sérialisation JSON"""
        return {
            "video_name": self.video_name,
            "video_duration": self.video_duration,
            "analysis_date": self.analysis_date,
            "matches_count": self.matches_count,
            "sets_count": self.sets_count,
            "rounds_count": self.rounds_count,
            "timer_detection_rate": self.timer_detection_rate,
            "total_frames_analyzed": self.total_frames_analyzed,
            "frames_with_timer": self.frames_with_timer,
            "detection_method": self.detection_method,
            "parameters": self.parameters,
            "matches": [m.to_dict() for m in self.matches]
        }

    def to_json(self, indent: int = 2) -> str:
        """Exporte en JSON formaté"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_matches_txt(self) -> str:
        """
        Exporte au format matches.txt (vue formatée).

        Format: timestamp Player1 (Character1) VS Player2 (Character2)

        Règle spéciale : Si un joueur utilise plusieurs personnages dans le match,
        ne pas afficher le nom du personnage entre parenthèses.
        """
        lines = []
        for match in self.matches:
            if not match.sets:
                continue

            # Analyser les personnages utilisés par chaque joueur dans ce match
            player1_chars = set()
            player2_chars = set()

            for set_obj in match.sets:
                if set_obj.character1:
                    player1_chars.add(set_obj.character1)
                if set_obj.character2:
                    player2_chars.add(set_obj.character2)

            # Déterminer si chaque joueur utilise un seul personnage
            player1_single_char = len(player1_chars) <= 1
            player2_single_char = len(player2_chars) <= 1

            # Obtenir le personnage représentatif (le premier rencontré)
            player1_char = list(player1_chars)[0] if player1_chars else ""
            player2_char = list(player2_chars)[0] if player2_chars else ""

            # Formater les noms selon la règle
            if player1_single_char and player1_char:
                player1_display = f"{match.player1} ({self._format_character_name(player1_char)})"
            else:
                player1_display = match.player1

            if player2_single_char and player2_char:
                player2_display = f"{match.player2} ({self._format_character_name(player2_char)})"
            else:
                player2_display = match.player2

            line = f"{match.start_time} {player1_display} VS {player2_display}"
            lines.append(line)

        return '\n'.join(lines) + '\n'

    def _format_character_name(self, name: str) -> str:
        """
        Formate un nom de personnage : première lettre majuscule, reste minuscule.
        Gère les cas spéciaux comme "M. BISON", "DEE JAY", etc.
        """
        if not name:
            return "Unknown"

        name = name.strip()

        # Cas spéciaux avec points ou espaces
        if "." in name or " " in name:
            # Séparer par espaces et traiter chaque partie
            parts = name.split()
            formatted_parts = []

            for part in parts:
                if "." in part:
                    # Garder les points mais capitaliser : "M." reste "M."
                    formatted_parts.append(part.upper())
                else:
                    # Première lettre majuscule, reste minuscule
                    formatted_parts.append(part.capitalize())

            return " ".join(formatted_parts)
        else:
            # Cas simple : première lettre majuscule, reste minuscule
            return name.capitalize()


def calculate_real_start_time(detection_time: str, detected_timer: int, target_timer: int = 99) -> str:
    """
    Calcule le temps réel de début d'un round basé sur le rétro-engineering.

    Args:
        detection_time: Temps où le timer a été détecté (format "HH:MM:SS")
        detected_timer: Valeur du timer détectée (ex: 97)
        target_timer: Valeur cible pour le calcul (par défaut 99)

    Returns:
        Temps estimé du début réel (format "HH:MM:SS")

    Exemple:
        detection_time="01:10:35", detected_timer=97
        → real_start="01:10:33" (35s - 2s car 99-97=2)
    """
    try:
        # Parser le temps de détection
        time_parts = detection_time.split(':')
        hours = int(time_parts[0])
        minutes = int(time_parts[1])
        seconds = int(time_parts[2])

        # Calculer les secondes écoulées depuis le début théorique
        seconds_elapsed = target_timer - detected_timer

        # Soustraire pour obtenir le début réel
        total_seconds = hours * 3600 + minutes * 60 + seconds - seconds_elapsed

        # Convertir en format HH:MM:SS
        real_hours = total_seconds // 3600
        real_minutes = (total_seconds % 3600) // 60
        real_secs = total_seconds % 60

        # Gérer les cas négatifs (début de vidéo)
        if total_seconds < 0:
            return "00:00:00"

        return f"{real_hours:02d}:{real_minutes:02d}:{real_secs:02d}"

    except (ValueError, IndexError):
        # Fallback vers le temps de détection en cas d'erreur
        return detection_time