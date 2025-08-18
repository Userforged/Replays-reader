"""
Window Manager - Gestion des fenêtres de collecte de rounds

Responsabilité unique : Gérer le cycle de vie des fenêtres de collecte.
Principe SRP appliqué - gestion d'état séparée de la détection et du traitement.
"""

from typing import Dict, List, Optional
from statistics import mode


class WindowManager:
    """
    Gestionnaire des fenêtres de collecte pour les rounds SF6.

    Responsabilités :
    - Gérer l'état des fenêtres (ouverte/fermée)
    - Collecter et valider les frames dans les fenêtres
    - Calculer la cohérence et la confiance des rounds collectés
    """

    def __init__(self, min_frames_for_round: int = 3, coherence_threshold: float = 0.7):
        """
        Initialise le gestionnaire de fenêtres.

        Args:
            min_frames_for_round: Nombre minimum de frames pour valider un round
            coherence_threshold: Seuil de cohérence pour valider un round
        """
        self.min_frames_for_round = min_frames_for_round
        self.coherence_threshold = coherence_threshold

        self.current_window: List[Dict] = []
        self.is_collecting = False
        self.window_start_time: Optional[str] = None
        self.window_start_frame: Optional[int] = None

    def start_window(self, frame: Dict, frame_index: int):
        """
        Démarre une nouvelle fenêtre de collecte.

        Args:
            frame: Première frame de la fenêtre
            frame_index: Index de la frame dans la séquence
        """
        self.current_window = [frame]
        self.is_collecting = True
        self.window_start_time = frame.get('timestamp')
        self.window_start_frame = frame_index

    def add_to_window(self, frame: Dict):
        """Ajoute une frame à la fenêtre courante."""
        if self.is_collecting:
            self.current_window.append(frame)

    def close_window(self) -> Optional[Dict]:
        """
        Ferme la fenêtre courante et retourne le round validé.

        Returns:
            Données du round si validé, None sinon
        """
        if not self.is_collecting or len(self.current_window) < self.min_frames_for_round:
            self._reset_window()
            return None

        # Calculer la cohérence de la fenêtre
        coherence_score = self._calculate_coherence()

        if coherence_score < self.coherence_threshold:
            self._reset_window()
            return None

        # Extraire les données du round
        round_data = self._extract_round_data(coherence_score)
        self._reset_window()

        return round_data

    def _calculate_coherence(self) -> float:
        """
        Calcule le score de cohérence de la fenêtre.

        Returns:
            Score entre 0.0 et 1.0
        """
        if not self.current_window:
            return 0.0

        total_score = 0.0
        valid_frames = 0

        for frame in self.current_window:
            frame_score = 0.0
            checks = 0

            # Score pour timer valide
            if frame.get('timer_clean') is not None:
                frame_score += 1.0
                checks += 1

            # Score pour personnages détectés
            if frame.get('character1_clean') or frame.get('character2_clean'):
                frame_score += 1.0
                checks += 1

            # Score pour joueurs détectés
            if frame.get('player1_clean') or frame.get('player2_clean'):
                frame_score += 1.0
                checks += 1

            if checks > 0:
                total_score += frame_score / checks
                valid_frames += 1

        return total_score / valid_frames if valid_frames > 0 else 0.0

    def _extract_round_data(self, coherence_score: float) -> Dict:
        """
        Extrait les données du round depuis la fenêtre.

        Args:
            coherence_score: Score de cohérence calculé

        Returns:
            Données structurées du round
        """
        if not self.current_window:
            return {}

        first_frame = self.current_window[0]
        last_frame = self.current_window[-1]

        # Extraire les valeurs consensuelles
        timers = [f.get('timer_clean') for f in self.current_window if f.get('timer_clean') is not None]
        characters1 = [f.get('character1_clean') for f in self.current_window if f.get('character1_clean')]
        characters2 = [f.get('character2_clean') for f in self.current_window if f.get('character2_clean')]
        players1 = [f.get('player1_clean') for f in self.current_window if f.get('player1_clean')]
        players2 = [f.get('player2_clean') for f in self.current_window if f.get('player2_clean')]

        # Utiliser les valeurs les plus fréquentes (mode) ou les premières valides
        return {
            'start_time': first_frame.get('timestamp'),
            'end_time': last_frame.get('timestamp'),
            'timer_start': timers[0] if timers else 99,
            'timer_end': timers[-1] if timers else None,
            'character1': self._get_most_frequent(characters1),
            'character2': self._get_most_frequent(characters2),
            'player1': self._get_most_frequent(players1),
            'player2': self._get_most_frequent(players2),
            'frames_count': len(self.current_window),
            'coherence_score': coherence_score,
            'method': 'window_collection'
        }

    def _get_most_frequent(self, values: List[str]) -> Optional[str]:
        """Retourne la valeur la plus fréquente dans la liste."""
        if not values:
            return None

        try:
            # Utiliser le mode statistique
            return mode(values)
        except:
            # Si pas de mode clair, prendre la première valeur
            return values[0]

    def _reset_window(self):
        """Remet à zéro l'état de la fenêtre."""
        self.current_window = []
        self.is_collecting = False
        self.window_start_time = None
        self.window_start_frame = None

    @property
    def window_size(self) -> int:
        """Retourne la taille de la fenêtre courante."""
        return len(self.current_window)

    @property
    def collecting(self) -> bool:
        """Retourne True si une collecte est en cours."""
        return self.is_collecting