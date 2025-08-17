"""
Module de détection des rounds Street Fighter 6.

Ce module gère la détection des rounds basée sur les patterns de timer SF6
et la validation avec le contexte des personnages.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


class RoundDetector:
    """
    Détecteur de rounds Street Fighter 6 basé sur les patterns de timer.
    
    Principe : Détecte les débuts de rounds via les transitions de timer
    (patterns low→high, jumps >20 points, moderate starts ≥85)
    """
    
    def __init__(self, min_round_duration: int = 120, timer_tolerance: float = 0.3, debug: bool = False):
        """
        Initialise le détecteur de rounds.
        
        Args:
            min_round_duration: Durée minimum d'un round en secondes
            timer_tolerance: Ratio de tolérance pour timer manquant (0.0-1.0)
            debug: Mode debug pour logs détaillés
        """
        self.min_round_duration = min_round_duration
        self.timer_tolerance = timer_tolerance
        self.debug = debug
    
    def detect_rounds(self, parsed_frames: List[Dict]) -> List[Dict]:
        """
        Détecte les rounds dans les frames parsées.
        
        Args:
            parsed_frames: Frames avec timestamps et timer parsés
            
        Returns:
            Liste des rounds détectés avec métadonnées
        """
        if not parsed_frames:
            return []
        
        self._log_debug(f"🔍 Détection des rounds dans {len(parsed_frames)} frames")
        
        # Détecter les séquences de timer SF6
        rounds = self._detect_timer_sequences(parsed_frames)
        
        self._log_debug(f"   → {len(rounds)} rounds détectés")
        
        return rounds
    
    def _detect_timer_sequences(self, parsed_frames: List[Dict]) -> List[Dict]:
        """
        Détecte les séquences de timer SF6 avec patterns spécifiques.
        
        Patterns détectés:
        - Timer transitions: low (< 50) → high (≥ 80) 
        - Timer jumps: différence > 20 points
        - Moderate starts: timer ≥ 85 après gap
        """
        rounds = []
        
        # Filtrer les frames avec timer valide
        timer_frames = [f for f in parsed_frames if f.get('timer_value') is not None]
        
        if len(timer_frames) < 2:
            self._log_debug("   ⚠️ Pas assez de frames avec timer pour détecter des rounds")
            return rounds
        
        self._log_debug(f"   → Analyse de {len(timer_frames)} frames avec timer")
        
        for i in range(1, len(timer_frames)):
            prev_frame = timer_frames[i-1]
            curr_frame = timer_frames[i]
            
            prev_timer = prev_frame['timer_value']
            curr_timer = curr_frame['timer_value']
            
            # Pattern 1: Timer transition low → high
            if prev_timer < 50 and curr_timer >= 80:
                round_start = self._calculate_real_round_start(curr_frame, curr_timer)
                round_data = self._create_round_data(round_start, curr_frame, curr_timer, "low_to_high")
                rounds.append(round_data)
                self._log_debug(f"   ✅ Round détecté (low→high): timer {prev_timer}→{curr_timer} à {round_start.strftime('%H:%M:%S')}")
            
            # Pattern 2: Timer jump significatif (> 20 points)  
            elif curr_timer - prev_timer > 20:
                round_start = self._calculate_real_round_start(curr_frame, curr_timer)
                round_data = self._create_round_data(round_start, curr_frame, curr_timer, "significant_jump")
                rounds.append(round_data)
                self._log_debug(f"   ✅ Round détecté (jump): timer {prev_timer}→{curr_timer} à {round_start.strftime('%H:%M:%S')}")
            
            # Pattern 3: Moderate start après gap temporel
            elif curr_timer >= 85:
                time_gap = (curr_frame['timestamp'] - prev_frame['timestamp']).total_seconds()
                if time_gap > 30:  # Gap > 30 secondes
                    round_start = self._calculate_real_round_start(curr_frame, curr_timer)
                    round_data = self._create_round_data(round_start, curr_frame, curr_timer, "moderate_start")
                    rounds.append(round_data)
                    self._log_debug(f"   ✅ Round détecté (moderate): timer {curr_timer} après {time_gap:.0f}s gap à {round_start.strftime('%H:%M:%S')}")
        
        # Filtrer et valider les rounds
        validated_rounds = self._validate_rounds(rounds)
        
        return validated_rounds
    
    def _calculate_real_round_start(self, frame: Dict, timer_value: int) -> datetime:
        """
        Calcule le vrai début du round basé sur la valeur de timer détectée.
        
        Logique: Si timer détecté à X, le vrai début = temps_détection - (99-X) - 1 seconde
        """
        detection_time = frame['timestamp']
        seconds_elapsed = 99 - timer_value
        real_start = detection_time - timedelta(seconds=seconds_elapsed + 1)
        
        return real_start
    
    def _create_round_data(self, round_start: datetime, frame: Dict, timer_value: int, pattern: str) -> Dict:
        """
        Crée les données d'un round détecté.
        """
        return {
            'start_time': round_start,
            'detection_time': frame['timestamp'],
            'start_timer_value': timer_value,
            'timer_pattern': pattern,
            'detection_frame': frame,
            'confidence': self._calculate_pattern_confidence(pattern, timer_value)
        }
    
    def _calculate_pattern_confidence(self, pattern: str, timer_value: int) -> float:
        """
        Calcule la confiance de détection basée sur le pattern et la valeur timer.
        """
        base_confidence = {
            'low_to_high': 0.9,      # Pattern le plus fiable
            'significant_jump': 0.8,  # Très fiable
            'moderate_start': 0.7     # Fiable mais peut avoir des faux positifs
        }.get(pattern, 0.5)
        
        # Bonus si timer proche de 99 (début très probable)
        if timer_value >= 95:
            base_confidence = min(0.95, base_confidence + 0.1)
        elif timer_value >= 90:
            base_confidence = min(0.9, base_confidence + 0.05)
        
        return base_confidence
    
    def _validate_rounds(self, rounds: List[Dict]) -> List[Dict]:
        """
        Valide et filtre les rounds détectés.
        
        Critères de validation:
        - Durée minimum respectée
        - Pas de doublons temporels
        - Confiance minimum
        """
        if not rounds:
            return []
        
        validated_rounds = []
        
        # Trier par temps de début
        sorted_rounds = sorted(rounds, key=lambda r: r['start_time'])
        
        for i, round_data in enumerate(sorted_rounds):
            is_valid = True
            
            # Vérifier durée minimum avec le round précédent
            if i > 0:
                prev_round = validated_rounds[-1] if validated_rounds else sorted_rounds[i-1]
                duration = (round_data['start_time'] - prev_round['start_time']).total_seconds()
                
                if duration < self.min_round_duration:
                    self._log_debug(f"   ❌ Round rejeté: durée {duration:.0f}s < {self.min_round_duration}s")
                    is_valid = False
            
            # Vérifier confiance minimum
            if round_data['confidence'] < 0.5:
                self._log_debug(f"   ❌ Round rejeté: confiance {round_data['confidence']:.2f} trop faible")
                is_valid = False
            
            if is_valid:
                # Calculer durée et fin estimée pour ce round
                if i < len(sorted_rounds) - 1:
                    next_round = sorted_rounds[i + 1]
                    round_data['end_time'] = next_round['start_time']
                    round_data['duration_seconds'] = (next_round['start_time'] - round_data['start_time']).total_seconds()
                else:
                    # Dernier round - estimer durée standard
                    round_data['end_time'] = round_data['start_time'] + timedelta(seconds=120)
                    round_data['duration_seconds'] = 120
                
                validated_rounds.append(round_data)
                self._log_debug(f"   ✅ Round validé: {round_data['start_time'].strftime('%H:%M:%S')} (confiance: {round_data['confidence']:.2f})")
        
        return validated_rounds
    
    def calculate_round_confidence(self, round_data: Dict) -> float:
        """
        Calcule la confiance globale d'un round.
        
        Prend en compte:
        - Pattern de détection
        - Valeur de timer
        - Durée du round
        - Cohérence temporelle
        """
        if not round_data:
            return 0.0
        
        # Confiance de base du pattern
        base_confidence = round_data.get('confidence', 0.5)
        
        # Bonus pour durée réaliste (90-180 secondes)
        duration = round_data.get('duration_seconds', 120)
        if 90 <= duration <= 180:
            base_confidence = min(0.95, base_confidence + 0.05)
        elif duration > 300:  # Trop long, probablement faux
            base_confidence *= 0.7
        
        # Bonus pour timer de début élevé
        start_timer = round_data.get('start_timer_value', 50)
        if start_timer >= 95:
            base_confidence = min(0.95, base_confidence + 0.05)
        
        return base_confidence
    
    def _log_debug(self, message: str):
        """Log message si debug activé."""
        if self.debug:
            print(f"[RoundDetector] {message}")