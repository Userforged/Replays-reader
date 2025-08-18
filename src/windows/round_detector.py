"""
Round Detector - Détection des débuts de rounds SF6

Responsabilité unique : Détecter les transitions de rounds basées sur les patterns de timer.
Principe SRP appliqué - logique de détection séparée de la collection et du traitement.
"""

from typing import List, Optional
from statistics import median


class RoundDetector:
    """
    Détecteur spécialisé pour identifier les débuts de rounds SF6.

    Responsabilités :
    - Analyser les patterns de timer pour détecter les nouveaux rounds
    - Maintenir l'historique des timers pour le lissage
    - Appliquer la logique de détection séquentielle (vs seuils fixes)
    """

    def __init__(self, timer_high_threshold: int = 95, timer_history_size: int = 5):
        """
        Initialise le détecteur.

        Args:
            timer_high_threshold: Seuil minimum pour démarrer une collection
            timer_history_size: Taille de l'historique pour le lissage
        """
        self.timer_high_threshold = timer_high_threshold
        self.timer_history_size = timer_history_size
        self.timer_history: List[int] = []

    def should_start_round(self, timer_value: Optional[int], gap_since_last: int) -> bool:
        """
        Détermine si un nouveau round doit commencer.

        Args:
            timer_value: Valeur du timer détectée
            gap_since_last: Nombre de secondes depuis le dernier round

        Returns:
            True si un nouveau round doit commencer
        """
        if timer_value is None:
            return False

        # Condition 1: Timer élevé (début probable de round)
        if timer_value >= self.timer_high_threshold:
            # Condition 2: Gap temporel suffisant (éviter les faux positifs)
            if gap_since_last >= 30:  # 30 secondes minimum entre rounds
                return True

        return False

    def should_end_round(self, timer_value: Optional[int]) -> bool:
        """
        Détermine si le round en cours doit se terminer (nouveau round détecté).

        Args:
            timer_value: Valeur du timer actuelle

        Returns:
            True si un nouveau round est détecté par progression séquentielle
        """
        if timer_value is None:
            return False

        # Ajouter à l'historique
        self.timer_history.append(timer_value)
        if len(self.timer_history) > self.timer_history_size:
            self.timer_history.pop(0)

        # Besoin d'au moins 3 valeurs pour détecter une progression
        if len(self.timer_history) < 3:
            return False

        # Calculer le timer lissé (médiane pour réduire le bruit OCR)
        smoothed_timer = median(self.timer_history)

        # Détecter un nouveau round par comparaison séquentielle
        return self._detect_new_round_from_progression(timer_value, smoothed_timer)

    def _detect_new_round_from_progression(self, current_timer: int, smoothed_timer: float) -> bool:
        """
        Logique de détection basée sur la progression des timers.

        Détecte un nouveau round quand :
        1. Timer actuel > timer lissé (indication de remontée)
        2. Différence significative (>= 20 points)

        Args:
            current_timer: Timer actuel
            smoothed_timer: Timer lissé sur l'historique

        Returns:
            True si nouveau round détecté
        """
        # Règle principale : timer actuel significativement supérieur au lissé
        if current_timer >= smoothed_timer + 20:
            return True

        # Règle alternative : détection de remontée après descente
        if len(self.timer_history) >= 4:
            # Vérifier si on a une tendance descendante puis montante
            recent_trend = self.timer_history[-3:]
            if recent_trend[0] > recent_trend[1] and current_timer > recent_trend[1] + 15:
                return True

        return False

    def reset_history(self):
        """Remet à zéro l'historique des timers."""
        self.timer_history.clear()

    def get_current_smoothed_timer(self) -> Optional[float]:
        """Retourne le timer lissé actuel."""
        if len(self.timer_history) >= 3:
            return median(self.timer_history)
        return None