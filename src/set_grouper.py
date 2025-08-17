"""
Module de groupage des rounds en sets Street Fighter 6.

Ce module gère le regroupement des rounds en sets basé sur la cohérence 
des personnages et la proximité temporelle.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


class SetGrouper:
    """
    Groupeur de sets Street Fighter 6 basé sur la cohérence des personnages.
    
    Principe : Un set = même matchup de personnages (character1 vs character2)
    avec une proximité temporelle raisonnable entre les rounds.
    """
    
    def __init__(self, max_set_gap: int = 300, min_rounds_per_set: int = 2, debug: bool = False):
        """
        Initialise le groupeur de sets.
        
        Args:
            max_set_gap: Gap maximum entre rounds d'un même set (secondes)
            min_rounds_per_set: Nombre minimum de rounds par set
            debug: Mode debug pour logs détaillés
        """
        self.max_set_gap = max_set_gap
        self.min_rounds_per_set = min_rounds_per_set
        self.debug = debug
    
    def group_rounds_into_sets(self, rounds: List[Dict]) -> List[Dict]:
        """
        Groupe les rounds en sets selon la cohérence des personnages.
        
        Args:
            rounds: Liste des rounds détectés
            
        Returns:
            Liste des sets avec leurs rounds groupés
        """
        if not rounds:
            return []
        
        self._log_debug(f"🎮 Groupage de {len(rounds)} rounds en sets")
        
        # Trier les rounds par temps de début
        sorted_rounds = sorted(rounds, key=lambda r: r['start_time'])
        
        # Grouper en sets selon la cohérence des personnages
        sets = self._group_by_character_consistency(sorted_rounds)
        
        # Valider et enrichir les sets
        validated_sets = self._validate_and_enrich_sets(sets)
        
        self._log_debug(f"   → {len(validated_sets)} sets créés")
        
        return validated_sets
    
    def _group_by_character_consistency(self, sorted_rounds: List[Dict]) -> List[Dict]:
        """
        Groupe les rounds par cohérence des personnages.
        
        Un nouveau set commence quand :
        - Les personnages changent (character1 ou character2)
        - Gap temporel trop important (> max_set_gap)
        """
        if not sorted_rounds:
            return []
        
        sets = []
        current_set_rounds = [sorted_rounds[0]]
        current_characters = self._extract_characters_from_round(sorted_rounds[0])
        
        self._log_debug(f"   → Premier set commence avec {current_characters}")
        
        for i in range(1, len(sorted_rounds)):
            round_data = sorted_rounds[i]
            round_characters = self._extract_characters_from_round(round_data)
            
            # Vérifier cohérence des personnages
            characters_match = self._characters_match(current_characters, round_characters)
            
            # Vérifier gap temporel
            prev_round = current_set_rounds[-1]
            time_gap = (round_data['start_time'] - prev_round['start_time']).total_seconds()
            
            # Décider si on continue le set actuel ou on en commence un nouveau
            if characters_match and time_gap <= self.max_set_gap:
                # Continuer le set actuel
                current_set_rounds.append(round_data)
                self._log_debug(f"   → Round ajouté au set actuel: {round_characters} (gap: {time_gap:.0f}s)")
            else:
                # Finir le set actuel et en commencer un nouveau
                if len(current_set_rounds) >= self.min_rounds_per_set:
                    set_data = self._create_set_data(current_set_rounds, current_characters)
                    sets.append(set_data)
                    self._log_debug(f"   → Set finalisé: {current_characters} ({len(current_set_rounds)} rounds)")
                else:
                    self._log_debug(f"   → Set rejeté: {current_characters} (seulement {len(current_set_rounds)} rounds)")
                
                # Commencer nouveau set
                current_set_rounds = [round_data]
                current_characters = round_characters
                
                reason = "personnages changés" if not characters_match else f"gap {time_gap:.0f}s"
                self._log_debug(f"   → Nouveau set: {current_characters} ({reason})")
        
        # Traiter le dernier set
        if len(current_set_rounds) >= self.min_rounds_per_set:
            set_data = self._create_set_data(current_set_rounds, current_characters)
            sets.append(set_data)
            self._log_debug(f"   → Dernier set finalisé: {current_characters} ({len(current_set_rounds)} rounds)")
        else:
            self._log_debug(f"   → Dernier set rejeté: {current_characters} (seulement {len(current_set_rounds)} rounds)")
        
        return sets
    
    def _extract_characters_from_round(self, round_data: Dict) -> Dict[str, str]:
        """
        Extrait les personnages d'un round (depuis la frame de détection).
        """
        detection_frame = round_data.get('detection_frame', {})
        return {
            'character1': detection_frame.get('character1', ''),
            'character2': detection_frame.get('character2', '')
        }
    
    def _characters_match(self, chars1: Dict[str, str], chars2: Dict[str, str]) -> bool:
        """
        Vérifie si deux sets de personnages correspondent (même matchup).
        """
        # Cas simple: correspondance exacte
        if (chars1['character1'] == chars2['character1'] and 
            chars1['character2'] == chars2['character2']):
            return True
        
        # Cas inversé: character1/character2 échangés (rare mais possible)
        if (chars1['character1'] == chars2['character2'] and 
            chars1['character2'] == chars2['character1']):
            return True
        
        # Si un des personnages est manquant, on accepte si l'autre correspond
        if not chars1['character1'] or not chars1['character2'] or not chars2['character1'] or not chars2['character2']:
            if chars1['character1'] and chars2['character1'] and chars1['character1'] == chars2['character1']:
                return True
            if chars1['character2'] and chars2['character2'] and chars1['character2'] == chars2['character2']:
                return True
        
        return False
    
    def _create_set_data(self, rounds: List[Dict], characters: Dict[str, str]) -> Dict:
        """
        Crée les données d'un set à partir de ses rounds.
        """
        if not rounds:
            return {}
        
        # Trier les rounds par temps de début
        sorted_rounds = sorted(rounds, key=lambda r: r['start_time'])
        
        # Calculer métadonnées du set
        start_time = sorted_rounds[0]['start_time']
        end_time = sorted_rounds[-1].get('end_time', sorted_rounds[-1]['start_time'] + timedelta(seconds=120))
        duration = (end_time - start_time).total_seconds()
        
        # Calculer confiance moyenne
        avg_confidence = sum(r.get('confidence', 0.5) for r in rounds) / len(rounds)
        
        # Extraire les noms de joueurs les plus fréquents dans ce set
        player_info = self._extract_dominant_players(rounds)
        
        return {
            'start_time': start_time,
            'end_time': end_time,
            'duration_seconds': duration,
            'character1': characters['character1'],
            'character2': characters['character2'],
            'player1': player_info['player1'],
            'player2': player_info['player2'],
            'rounds_count': len(rounds),
            'rounds': sorted_rounds,
            'confidence': avg_confidence,
            'character_consistency': self._calculate_character_consistency(rounds)
        }
    
    def _calculate_character_consistency(self, rounds: List[Dict]) -> float:
        """
        Calcule la cohérence des personnages dans un set.
        
        Returns:
            Score entre 0.0 et 1.0 (1.0 = parfaitement cohérent)
        """
        if not rounds:
            return 0.0
        
        # Compter les personnages les plus fréquents
        char1_counts = {}
        char2_counts = {}
        
        for round_data in rounds:
            detection_frame = round_data.get('detection_frame', {})
            char1 = detection_frame.get('character1', '')
            char2 = detection_frame.get('character2', '')
            
            if char1:
                char1_counts[char1] = char1_counts.get(char1, 0) + 1
            if char2:
                char2_counts[char2] = char2_counts.get(char2, 0) + 1
        
        # Calculer cohérence pour chaque personnage
        total_rounds = len(rounds)
        
        char1_consistency = max(char1_counts.values()) / total_rounds if char1_counts else 0.0
        char2_consistency = max(char2_counts.values()) / total_rounds if char2_counts else 0.0
        
        # Moyenne pondérée
        return (char1_consistency + char2_consistency) / 2.0
    
    def _extract_dominant_players(self, rounds: List[Dict]) -> Dict[str, str]:
        """
        Extrait les noms de joueurs dominants d'un set basé sur les frames de détection.
        
        Args:
            rounds: Liste des rounds du set
            
        Returns:
            Dict avec player1 et player2 dominants
        """
        player1_counts = {}
        player2_counts = {}
        
        # Compter les occurrences de chaque joueur
        for round_data in rounds:
            detection_frame = round_data.get('detection_frame', {})
            p1 = detection_frame.get('player1', '').strip()
            p2 = detection_frame.get('player2', '').strip()
            
            if p1:
                player1_counts[p1] = player1_counts.get(p1, 0) + 1
            if p2:
                player2_counts[p2] = player2_counts.get(p2, 0) + 1
        
        # Debug: afficher les comptages si debug activé
        if hasattr(self, 'debug') and self.debug:
            print(f"[SetGrouper] 🔍 _extract_dominant_players:")
            print(f"  Player1 counts: {player1_counts}")
            print(f"  Player2 counts: {player2_counts}")
        
        # Trouver les joueurs dominants
        dominant_player1 = max(player1_counts.items(), key=lambda x: x[1])[0] if player1_counts else ''
        dominant_player2 = max(player2_counts.items(), key=lambda x: x[1])[0] if player2_counts else ''
        
        if hasattr(self, 'debug') and self.debug:
            print(f"  Dominant: '{dominant_player1}' vs '{dominant_player2}'")
        
        return {
            'player1': dominant_player1,
            'player2': dominant_player2
        }
    
    def _validate_and_enrich_sets(self, sets: List[Dict]) -> List[Dict]:
        """
        Valide et enrichit les sets avec des métadonnées supplémentaires.
        """
        validated_sets = []
        
        for i, set_data in enumerate(sets):
            # Ajouter numéro de set
            set_data['set_number'] = i + 1
            
            # Vérifier cohérence minimum
            if set_data.get('character_consistency', 0.0) >= 0.5:
                # Enrichir avec données SF6 spécifiques
                set_data['matchup'] = f"{set_data['character1']} vs {set_data['character2']}"
                
                # Calculer score de qualité global
                set_data['quality_score'] = self._calculate_set_quality(set_data)
                
                validated_sets.append(set_data)
                self._log_debug(f"   ✅ Set {i+1} validé: {set_data['matchup']} (qualité: {set_data['quality_score']:.2f})")
            else:
                self._log_debug(f"   ❌ Set {i+1} rejeté: cohérence {set_data.get('character_consistency', 0.0):.2f} trop faible")
        
        return validated_sets
    
    def _calculate_set_quality(self, set_data: Dict) -> float:
        """
        Calcule un score de qualité global pour un set.
        
        Prend en compte:
        - Cohérence des personnages
        - Confiance moyenne des rounds
        - Nombre de rounds
        - Durée réaliste
        """
        if not set_data:
            return 0.0
        
        # Composants du score (normalisés 0.0-1.0)
        character_consistency = set_data.get('character_consistency', 0.0)
        round_confidence = set_data.get('confidence', 0.0)
        
        # Bonus pour nombre de rounds (2-5 rounds = optimal)
        rounds_count = set_data.get('rounds_count', 0)
        rounds_bonus = min(1.0, max(0.0, (rounds_count - 1) / 4.0))  # 2 rounds = 0.25, 5 rounds = 1.0
        
        # Bonus pour durée réaliste (300-900 secondes = optimal)
        duration = set_data.get('duration_seconds', 0)
        if 300 <= duration <= 900:
            duration_bonus = 1.0
        elif duration < 300:
            duration_bonus = duration / 300.0
        else:
            duration_bonus = max(0.0, 1.0 - (duration - 900) / 600.0)  # Décroît après 900s
        
        # Score pondéré
        quality_score = (
            character_consistency * 0.4 +    # Cohérence des personnages = plus important
            round_confidence * 0.3 +         # Confiance des rounds
            rounds_bonus * 0.2 +             # Nombre de rounds
            duration_bonus * 0.1             # Durée réaliste
        )
        
        return min(1.0, quality_score)
    
    def calculate_set_statistics(self, sets: List[Dict]) -> Dict:
        """
        Calcule des statistiques globales sur les sets détectés.
        """
        if not sets:
            return {
                'total_sets': 0,
                'total_rounds': 0,
                'avg_rounds_per_set': 0.0,
                'avg_set_duration': 0.0,
                'avg_quality_score': 0.0,
                'character_consistency_avg': 0.0
            }
        
        total_rounds = sum(s.get('rounds_count', 0) for s in sets)
        total_duration = sum(s.get('duration_seconds', 0) for s in sets)
        avg_quality = sum(s.get('quality_score', 0.0) for s in sets) / len(sets)
        avg_consistency = sum(s.get('character_consistency', 0.0) for s in sets) / len(sets)
        
        return {
            'total_sets': len(sets),
            'total_rounds': total_rounds,
            'avg_rounds_per_set': total_rounds / len(sets),
            'avg_set_duration': total_duration / len(sets),
            'avg_quality_score': avg_quality,
            'character_consistency_avg': avg_consistency
        }
    
    def _log_debug(self, message: str):
        """Log message si debug activé."""
        if self.debug:
            print(f"[SetGrouper] {message}")