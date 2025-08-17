"""
Module de groupage des sets en matches Street Fighter 6.

Ce module gère le regroupement des sets en matches complets basé sur
la proximité temporelle et les règles métier SF6.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


class MatchGrouper:
    """
    Groupeur de matches Street Fighter 6 basé sur la proximité temporelle des sets.
    
    Principe : Un match = collection de sets avec proximité temporelle raisonnable
    selon les règles métier SF6.
    """
    
    def __init__(self, min_match_gap: int = 180, min_sets_per_match: int = 1, 
                 min_rounds_per_match: int = 3, debug: bool = False):
        """
        Initialise le groupeur de matches.
        
        Args:
            min_match_gap: Gap minimum entre matches (secondes)
            min_sets_per_match: Nombre minimum de sets par match
            min_rounds_per_match: Nombre minimum de rounds par match (si 1 seul set)
            debug: Mode debug pour logs détaillés
        """
        self.min_match_gap = min_match_gap
        self.min_sets_per_match = min_sets_per_match
        self.min_rounds_per_match = min_rounds_per_match
        self.debug = debug
    
    def group_sets_into_matches(self, sets: List[Dict]) -> List[Dict]:
        """
        Groupe les sets en matches selon la proximité temporelle.
        
        Args:
            sets: Liste des sets détectés
            
        Returns:
            Liste des matches avec leurs sets groupés
        """
        if not sets:
            return []
        
        self._log_debug(f"🥊 Groupage de {len(sets)} sets en matches")
        
        # Trier les sets par temps de début
        sorted_sets = sorted(sets, key=lambda s: s['start_time'])
        
        # Grouper en matches selon la proximité temporelle
        matches = self._group_by_temporal_proximity(sorted_sets)
        
        # Valider et enrichir les matches
        validated_matches = self._validate_and_enrich_matches(matches)
        
        self._log_debug(f"   → {len(validated_matches)} matches créés")
        
        return validated_matches
    
    def _group_by_temporal_proximity(self, sorted_sets: List[Dict]) -> List[Dict]:
        """
        Groupe les sets par proximité temporelle.
        
        Un nouveau match commence quand le gap entre sets > min_match_gap.
        """
        if not sorted_sets:
            return []
        
        matches = []
        current_match_sets = [sorted_sets[0]]
        
        self._log_debug(f"   → Premier match commence à {sorted_sets[0]['start_time'].strftime('%H:%M:%S')}")
        
        for i in range(1, len(sorted_sets)):
            current_set = sorted_sets[i]
            prev_set = current_match_sets[-1]
            
            # Calculer gap entre fin du set précédent et début du set actuel
            time_gap = (current_set['start_time'] - prev_set['end_time']).total_seconds()
            
            # Vérifier cohérence des joueurs
            players_consistent = self._are_players_consistent(current_match_sets, current_set)
            
            # Vérifier règle SF6: les 2 personnages ne peuvent pas changer en même temps
            both_chars_changed = self._both_characters_changed(current_match_sets, current_set)
            
            if time_gap <= self.min_match_gap and players_consistent and not both_chars_changed:
                # Continuer le match actuel
                current_match_sets.append(current_set)
                self._log_debug(f"   → Set ajouté au match actuel (gap: {time_gap:.0f}s, joueurs cohérents)")
            else:
                # Finir le match actuel et en commencer un nouveau
                if self._is_valid_match(current_match_sets):
                    match_data = self._create_match_data(current_match_sets)
                    matches.append(match_data)
                    self._log_debug(f"   → Match finalisé: {len(current_match_sets)} sets, {self._count_total_rounds(current_match_sets)} rounds")
                else:
                    self._log_debug(f"   → Match rejeté: ne respecte pas les critères minimum")
                
                # Commencer nouveau match
                current_match_sets = [current_set]
                
                # Déterminer la raison de la séparation
                if both_chars_changed:
                    reason = "règle SF6: 2 persos changent"
                elif not players_consistent:
                    reason = "joueurs différents"
                else:
                    reason = f"gap {time_gap:.0f}s"
                
                self._log_debug(f"   → Nouveau match ({reason}) à {current_set['start_time'].strftime('%H:%M:%S')}")
        
        # Traiter le dernier match
        if self._is_valid_match(current_match_sets):
            match_data = self._create_match_data(current_match_sets)
            matches.append(match_data)
            self._log_debug(f"   → Dernier match finalisé: {len(current_match_sets)} sets, {self._count_total_rounds(current_match_sets)} rounds")
        else:
            self._log_debug(f"   → Dernier match rejeté: ne respecte pas les critères minimum")
        
        return matches
    
    def _is_valid_match(self, sets: List[Dict]) -> bool:
        """
        Vérifie si une collection de sets forme un match valide selon les règles SF6.
        
        Règles de validation:
        - ≥2 sets OU 1 set avec ≥3 rounds (comme spécifié dans CLAUDE.md)
        """
        if not sets:
            return False
        
        sets_count = len(sets)
        total_rounds = self._count_total_rounds(sets)
        
        # Règle SF6: Soit ≥2 sets, soit 1 set avec ≥3 rounds
        if sets_count >= self.min_sets_per_match:
            return True
        elif sets_count == 1 and total_rounds >= self.min_rounds_per_match:
            return True
        
        return False
    
    def _count_total_rounds(self, sets: List[Dict]) -> int:
        """Compte le total de rounds dans une collection de sets."""
        return sum(s.get('rounds_count', 0) for s in sets)
    
    def _are_players_consistent(self, existing_sets: List[Dict], new_set: Dict) -> bool:
        """
        Vérifie si les joueurs d'un nouveau set sont cohérents avec ceux des sets existants.
        
        Args:
            existing_sets: Sets déjà dans le match
            new_set: Nouveau set à ajouter
            
        Returns:
            True si les joueurs sont cohérents, False sinon
        """
        if not existing_sets:
            return True
        
        # Extraire les joueurs du nouveau set
        new_player1 = new_set.get('player1', '').strip()
        new_player2 = new_set.get('player2', '').strip()
        
        # Si pas de joueurs détectés dans le nouveau set, accepter (OCR peut échouer)
        if not new_player1 and not new_player2:
            return True
        
        # Analyser les joueurs des sets existants pour trouver le pattern dominant
        player1_candidates = {}
        player2_candidates = {}
        
        for existing_set in existing_sets:
            p1 = existing_set.get('player1', '').strip()
            p2 = existing_set.get('player2', '').strip()
            
            if p1:
                player1_candidates[p1] = player1_candidates.get(p1, 0) + 1
            if p2:
                player2_candidates[p2] = player2_candidates.get(p2, 0) + 1
        
        # Pas de joueurs détectés dans les sets existants, accepter
        if not player1_candidates and not player2_candidates:
            return True
        
        # Trouver les joueurs dominants
        dominant_player1 = max(player1_candidates.items(), key=lambda x: x[1])[0] if player1_candidates else ''
        dominant_player2 = max(player2_candidates.items(), key=lambda x: x[1])[0] if player2_candidates else ''
        
        # Vérifier cohérence
        # Accepter si au moins un joueur correspond (peut y avoir des erreurs OCR)
        player1_match = not new_player1 or not dominant_player1 or new_player1 == dominant_player1
        player2_match = not new_player2 or not dominant_player2 or new_player2 == dominant_player2
        
        # Accepter aussi le cas où les joueurs sont inversés (player1/player2 peuvent être échangés)
        player1_inverted = not new_player1 or not dominant_player2 or new_player1 == dominant_player2
        player2_inverted = not new_player2 or not dominant_player1 or new_player2 == dominant_player1
        
        # Cohérent si ordre normal OU ordre inversé
        normal_order = player1_match and player2_match
        inverted_order = player1_inverted and player2_inverted
        
        is_consistent = normal_order or inverted_order
        
        if not is_consistent:
            self._log_debug(f"   ⚠️ Joueurs incohérents: match={dominant_player1} vs {dominant_player2}, "
                          f"nouveau set={new_player1} vs {new_player2}")
        
        return is_consistent
    
    def _both_characters_changed(self, existing_sets: List[Dict], new_set: Dict) -> bool:
        """
        Vérifie si les 2 personnages ont changé entre le dernier set et le nouveau.
        
        Règle SF6: Dans un match, maximum 1 joueur peut changer de personnage
        entre sets. Si les 2 changent = nouveau match obligatoire.
        
        Args:
            existing_sets: Sets déjà dans le match
            new_set: Nouveau set à évaluer
            
        Returns:
            True si les 2 personnages ont changé (= nouveau match), False sinon
        """
        if not existing_sets:
            return False
        
        # Prendre le dernier set pour comparaison
        last_set = existing_sets[-1]
        last_char1 = last_set.get('character1', '').strip()
        last_char2 = last_set.get('character2', '').strip()
        
        new_char1 = new_set.get('character1', '').strip()
        new_char2 = new_set.get('character2', '').strip()
        
        # Ignorer si des personnages sont manquants (erreurs OCR)
        if not all([last_char1, last_char2, new_char1, new_char2]):
            return False
        
        # Vérifier si les 2 personnages ont changé
        char1_changed = last_char1 != new_char1
        char2_changed = last_char2 != new_char2
        
        both_changed = char1_changed and char2_changed
        
        if both_changed:
            self._log_debug(f"   🚫 Règle SF6: 2 persos changent {last_char1} vs {last_char2} → {new_char1} vs {new_char2} = NOUVEAU MATCH")
        
        return both_changed
    
    def _create_match_data(self, sets: List[Dict]) -> Dict:
        """
        Crée les données d'un match à partir de ses sets.
        """
        if not sets:
            return {}
        
        # Trier les sets par temps de début
        sorted_sets = sorted(sets, key=lambda s: s['start_time'])
        
        # Calculer métadonnées du match
        start_time = sorted_sets[0]['start_time']
        end_time = sorted_sets[-1]['end_time']
        duration = (end_time - start_time).total_seconds()
        total_rounds = self._count_total_rounds(sets)
        
        # Extraire joueurs principaux du match
        players = self._extract_match_players(sets)
        
        # Calculer confiance moyenne
        avg_confidence = sum(s.get('confidence', 0.5) for s in sets) / len(sets)
        
        return {
            'start_time': start_time,
            'end_time': end_time,
            'duration_seconds': duration,
            'sets_count': len(sets),
            'total_rounds': total_rounds,
            'sets': sorted_sets,
            'player1': players.get('player1', ''),
            'player2': players.get('player2', ''),
            'winner': None,  # À déterminer par analyse ultérieure
            'confidence': avg_confidence,
            'match_quality': self._calculate_match_quality(sets),
            'character_diversity': self._calculate_character_diversity(sets)
        }
    
    def _extract_match_players(self, sets: List[Dict]) -> Dict[str, str]:
        """
        Extrait les joueurs principaux d'un match en analysant tous les sets.
        
        Utilise la logique de fréquence pour identifier les joueurs constants.
        """
        player1_counts = {}
        player2_counts = {}
        
        # Analyser tous les rounds de tous les sets
        for set_data in sets:
            rounds = set_data.get('rounds', [])
            for round_data in rounds:
                detection_frame = round_data.get('detection_frame', {})
                
                player1 = detection_frame.get('player1', '').strip()
                player2 = detection_frame.get('player2', '').strip()
                
                if player1:
                    player1_counts[player1] = player1_counts.get(player1, 0) + 1
                if player2:
                    player2_counts[player2] = player2_counts.get(player2, 0) + 1
        
        # Sélectionner les joueurs les plus fréquents
        most_frequent_player1 = max(player1_counts.items(), key=lambda x: x[1])[0] if player1_counts else ''
        most_frequent_player2 = max(player2_counts.items(), key=lambda x: x[1])[0] if player2_counts else ''
        
        return {
            'player1': most_frequent_player1,
            'player2': most_frequent_player2
        }
    
    def _calculate_match_quality(self, sets: List[Dict]) -> float:
        """
        Calcule un score de qualité global pour un match.
        
        Prend en compte:
        - Qualité moyenne des sets
        - Diversité des personnages
        - Cohérence temporelle
        - Respect des règles SF6
        """
        if not sets:
            return 0.0
        
        # Qualité moyenne des sets
        avg_set_quality = sum(s.get('quality_score', 0.0) for s in sets) / len(sets)
        
        # Bonus pour diversité des personnages (changements = plus intéressant)
        character_diversity = self._calculate_character_diversity(sets)
        diversity_bonus = min(1.0, character_diversity / 2.0)  # Max bonus pour 2+ changements
        
        # Bonus pour respecter les règles SF6 strictes
        sf6_rules_bonus = 0.0
        sets_count = len(sets)
        total_rounds = self._count_total_rounds(sets)
        
        if sets_count >= 2:
            sf6_rules_bonus = 1.0  # Respecte la règle "≥2 sets"
        elif sets_count == 1 and total_rounds >= 3:
            sf6_rules_bonus = 0.8  # Respecte la règle "1 set avec ≥3 rounds"
        
        # Bonus pour durée réaliste (5-30 minutes)
        total_duration = sum(s.get('duration_seconds', 0) for s in sets)
        if 300 <= total_duration <= 1800:  # 5-30 minutes
            duration_bonus = 1.0
        elif total_duration < 300:
            duration_bonus = total_duration / 300.0
        else:
            duration_bonus = max(0.0, 1.0 - (total_duration - 1800) / 1200.0)
        
        # Score pondéré
        quality_score = (
            avg_set_quality * 0.4 +      # Qualité des sets = plus important
            sf6_rules_bonus * 0.3 +      # Respect des règles SF6
            diversity_bonus * 0.2 +      # Diversité des personnages
            duration_bonus * 0.1         # Durée réaliste
        )
        
        return min(1.0, quality_score)
    
    def _calculate_character_diversity(self, sets: List[Dict]) -> int:
        """
        Calcule la diversité des personnages dans un match.
        
        Returns:
            Nombre de changements de personnages détectés
        """
        if len(sets) <= 1:
            return 0
        
        changes = 0
        prev_chars = (sets[0].get('character1', ''), sets[0].get('character2', ''))
        
        for i in range(1, len(sets)):
            current_chars = (sets[i].get('character1', ''), sets[i].get('character2', ''))
            
            if current_chars != prev_chars:
                changes += 1
                prev_chars = current_chars
        
        return changes
    
    def _validate_and_enrich_matches(self, matches: List[Dict]) -> List[Dict]:
        """
        Valide et enrichit les matches avec des métadonnées supplémentaires.
        """
        validated_matches = []
        
        for i, match_data in enumerate(matches):
            # Ajouter index du match
            match_data['match_index'] = i
            
            # Enrichir avec données SF6 spécifiques
            match_data['matchup_summary'] = self._create_matchup_summary(match_data['sets'])
            
            # Calculer métriques de performance
            match_data['performance_metrics'] = self._calculate_performance_metrics(match_data)
            
            validated_matches.append(match_data)
            
            self._log_debug(f"   ✅ Match {i} validé: {match_data['player1']} vs {match_data['player2']} "
                          f"({match_data['sets_count']} sets, qualité: {match_data['match_quality']:.2f})")
        
        return validated_matches
    
    def _create_matchup_summary(self, sets: List[Dict]) -> str:
        """
        Crée un résumé textuel des matchups dans le match.
        """
        if not sets:
            return ""
        
        matchups = []
        for set_data in sets:
            char1 = set_data.get('character1', '?')
            char2 = set_data.get('character2', '?')
            matchups.append(f"{char1} vs {char2}")
        
        # Supprimer les doublons en préservant l'ordre
        unique_matchups = []
        for matchup in matchups:
            if matchup not in unique_matchups:
                unique_matchups.append(matchup)
        
        return " → ".join(unique_matchups)
    
    def _calculate_performance_metrics(self, match_data: Dict) -> Dict:
        """
        Calcule des métriques de performance pour le match.
        """
        sets = match_data.get('sets', [])
        
        if not sets:
            return {}
        
        total_rounds = match_data.get('total_rounds', 0)
        total_duration = match_data.get('duration_seconds', 0)
        
        return {
            'avg_round_duration': total_duration / total_rounds if total_rounds > 0 else 0,
            'sets_per_hour': (len(sets) * 3600) / total_duration if total_duration > 0 else 0,
            'rounds_per_set': total_rounds / len(sets) if sets else 0,
            'character_changes': match_data.get('character_diversity', 0),
            'temporal_consistency': self._calculate_temporal_consistency(sets)
        }
    
    def _calculate_temporal_consistency(self, sets: List[Dict]) -> float:
        """
        Calcule la cohérence temporelle d'un match (gaps réguliers entre sets).
        
        Returns:
            Score entre 0.0 et 1.0 (1.0 = gaps très réguliers)
        """
        if len(sets) <= 1:
            return 1.0
        
        # Calculer tous les gaps entre sets
        gaps = []
        for i in range(1, len(sets)):
            gap = (sets[i]['start_time'] - sets[i-1]['end_time']).total_seconds()
            gaps.append(gap)
        
        if not gaps:
            return 1.0
        
        # Calculer l'écart-type des gaps (plus c'est petit, plus c'est régulier)
        avg_gap = sum(gaps) / len(gaps)
        variance = sum((gap - avg_gap) ** 2 for gap in gaps) / len(gaps)
        std_dev = variance ** 0.5
        
        # Normaliser : écart-type faible = cohérence élevée
        # Considérer qu'un écart-type de 60s ou moins = très cohérent
        consistency = max(0.0, 1.0 - (std_dev / 60.0))
        
        return min(1.0, consistency)
    
    def calculate_match_statistics(self, matches: List[Dict]) -> Dict:
        """
        Calcule des statistiques globales sur les matches détectés.
        """
        if not matches:
            return {
                'total_matches': 0,
                'total_sets': 0,
                'total_rounds': 0,
                'avg_sets_per_match': 0.0,
                'avg_rounds_per_match': 0.0,
                'avg_match_duration': 0.0,
                'avg_quality_score': 0.0,
                'character_diversity_avg': 0.0
            }
        
        total_sets = sum(m.get('sets_count', 0) for m in matches)
        total_rounds = sum(m.get('total_rounds', 0) for m in matches)
        total_duration = sum(m.get('duration_seconds', 0) for m in matches)
        avg_quality = sum(m.get('match_quality', 0.0) for m in matches) / len(matches)
        avg_diversity = sum(m.get('character_diversity', 0) for m in matches) / len(matches)
        
        return {
            'total_matches': len(matches),
            'total_sets': total_sets,
            'total_rounds': total_rounds,
            'avg_sets_per_match': total_sets / len(matches),
            'avg_rounds_per_match': total_rounds / len(matches),
            'avg_match_duration': total_duration / len(matches),
            'avg_quality_score': avg_quality,
            'character_diversity_avg': avg_diversity
        }
    
    def _log_debug(self, message: str):
        """Log message si debug activé."""
        if self.debug:
            print(f"[MatchGrouper] {message}")