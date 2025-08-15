"""
Module de déduction des matches et rounds à partir des données d'analyse JSON.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import json


class MatchDeductor:
    """
    Analyse les données temporelles pour identifier le début des matches et rounds
    de Street Fighter 6 basé sur l'évolution des valeurs de timer.
    """
    
    def __init__(self, min_round_duration_seconds=120, 
                 min_match_gap_seconds=120,
                 timer_tolerance_ratio=0.3,
                 output_fields=None,
                 debug=False):
        """
        Initialise le déducteur avec les paramètres de tolérance.
        
        Args:
            min_round_duration_seconds: Durée minimum d'un round (défaut: 2 minutes)
            min_match_gap_seconds: Gap minimum entre matches (défaut: 2 minutes) 
            timer_tolerance_ratio: Ratio de tolérance pour timer manquant (défaut: 30%)
            output_fields: Dict définissant les champs à inclure dans la sortie
            debug: Mode debug pour logs détaillés
        """
        self.min_round_duration = min_round_duration_seconds
        self.min_match_gap = min_match_gap_seconds
        self.timer_tolerance = timer_tolerance_ratio
        self.debug = debug
        
        # Configuration des champs de sortie par défaut
        default_fields = {
            'match_fields': ['start_time', 'character1', 'character2'],
            'include_rounds_in_matches': False,
            'round_fields': ['start_time', 'confidence']
        }
        self.output_fields = output_fields if output_fields else default_fields
        
    def analyze_frames(self, frames_data: List[Dict]) -> Dict:
        """
        Analyse les données de frames pour détecter matches, sets et rounds.
        
        Args:
            frames_data: Liste des frames avec timestamps et données OCR
            
        Returns:
            Dict contenant les matches, sets et rounds détectés
        """
        if not frames_data:
            return {"matches": [], "stats": {}}
            
        self._log_debug(f"Analyse de {len(frames_data)} frames")
        
        # Parse et valide les données
        parsed_frames = self._parse_and_validate_frames(frames_data)
        
        # Détecte les rounds basés sur les patterns de timer SF6
        detected_rounds = self._detect_timer_sequences(parsed_frames)
        
        # Groupe les rounds en sets (même character1 vs character2)
        sets = self._group_rounds_into_sets(detected_rounds, parsed_frames)
        
        # Groupe les sets en matches (même opposition de joueurs)
        matches = self._group_sets_into_matches(sets)
        
        # Génère les statistiques
        stats = self._generate_stats(frames_data, matches)
        
        return {
            "matches": matches,
            "stats": stats
        }
    
    def _parse_and_validate_frames(self, frames_data: List[Dict]) -> List[Dict]:
        """Parse les timestamps et valide les données de timer."""
        parsed_frames = []
        
        for frame in frames_data:
            try:
                # Parse timestamp
                timestamp_str = frame.get('timestamp', '')
                timestamp_obj = self._parse_timestamp(timestamp_str)
                
                # Parse timer value
                timer_str = frame.get('timer_value', '').strip()
                timer_value = self._parse_timer_value(timer_str)
                
                parsed_frames.append({
                    'timestamp': timestamp_obj,
                    'timestamp_str': timestamp_str,
                    'timer_value': timer_value,
                    'timer_raw': timer_str,
                    'character1': frame.get('character1', ''),
                    'character2': frame.get('character2', '')
                })
                
            except Exception as e:
                self._log_debug(f"Erreur parsing frame: {e}")
                continue
                
        return sorted(parsed_frames, key=lambda x: x['timestamp'])
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse un timestamp au format MM:SS ou HH:MM:SS."""
        parts = timestamp_str.split(':')
        
        if len(parts) == 2:  # MM:SS
            minutes, seconds = map(int, parts)
            return datetime(2000, 1, 1, 0, minutes, seconds)
        elif len(parts) == 3:  # HH:MM:SS
            hours, minutes, seconds = map(int, parts)
            return datetime(2000, 1, 1, hours, minutes, seconds)
        else:
            raise ValueError(f"Format timestamp invalide: {timestamp_str}")
    
    def _parse_timer_value(self, timer_str: str) -> Optional[int]:
        """Parse la valeur du timer, retourne None si invalide."""
        if not timer_str or not timer_str.isdigit():
            return None
            
        timer_val = int(timer_str)
        # Valeurs timer SF6 valides: 0-99
        if 0 <= timer_val <= 99:
            return timer_val
        return None
    
    def _detect_timer_sequences(self, parsed_frames: List[Dict]) -> List[Dict]:
        """
        Détecte les rounds SF6 basés sur les transitions timer.
        Logique: Round = transition timer bas → timer haut (≥90) + pattern décroissant
        
        Returns:
            Liste de rounds détectés avec métadonnées
        """
        rounds = []
        
        # Trouver toutes les transitions timer bas → haut
        round_starts = self._find_round_starts(parsed_frames)
        
        for i, start_info in enumerate(round_starts):
            # Déterminer la fin du round (début du suivant ou fin des données)
            if i + 1 < len(round_starts):
                end_time = round_starts[i + 1]['timestamp']
            else:
                end_time = parsed_frames[-1]['timestamp']
            
            # Analyser la séquence du round
            round_data = self._analyze_round_sequence(
                parsed_frames, start_info['timestamp'], end_time, start_info['timer_value']
            )
            
            if round_data and self._is_valid_round(round_data):
                rounds.append(round_data)
                self._log_debug(f"Round détecté: {start_info['timestamp'].strftime('%H:%M:%S')} → {end_time.strftime('%H:%M:%S')}")
        
        return rounds
    
    def _find_round_starts(self, parsed_frames: List[Dict]) -> List[Dict]:
        """
        Trouve les débuts de round basés sur les patterns de timer SF6.
        Détecte les transitions timer bas → timer haut ou remontées significatives.
        """
        round_starts = []
        prev_timer = None
        
        for frame in parsed_frames:
            current_timer = frame['timer_value']
            
            if current_timer is not None:
                is_round_start = False
                transition_type = "unknown"
                
                if prev_timer is None:
                    # Premier timer détecté
                    if current_timer >= 90:
                        is_round_start = True
                        transition_type = "first_high"
                elif prev_timer < 50 and current_timer >= 90:
                    # Transition classique: timer bas → timer très haut (≥90)
                    is_round_start = True
                    transition_type = "low_to_high"
                elif prev_timer < 80 and current_timer >= 85:
                    # Transition modérée: timer bas → timer moyennement haut (≥85)
                    is_round_start = True
                    transition_type = "moderate_jump"
                elif prev_timer is not None and current_timer > prev_timer + 20:
                    # Saut significatif du timer (>20 points) = probable nouveau round
                    if current_timer >= 80:
                        is_round_start = True
                        transition_type = "significant_jump"
                
                if is_round_start:
                    round_starts.append({
                        'timestamp': frame['timestamp'],
                        'timer_value': current_timer,
                        'prev_timer': prev_timer,
                        'transition_type': transition_type
                    })
                    self._log_debug(f"Début round potentiel: {frame['timestamp_str']} (timer {prev_timer}→{current_timer}, type: {transition_type})")
                
                # Mettre à jour le timer précédent
                prev_timer = current_timer
        
        return round_starts
    
    def _analyze_round_sequence(self, frames: List[Dict], start_time, end_time, start_timer) -> Dict:
        """Analyse une séquence pour valider qu'il s'agit d'un round SF6."""
        # Filtrer les frames de ce round
        round_frames = [
            f for f in frames 
            if start_time <= f['timestamp'] < end_time
        ]
        
        if not round_frames:
            return None
            
        timer_frames = [f for f in round_frames if f['timer_value'] is not None]
        duration_seconds = (end_time - start_time).total_seconds()
        
        # Analyser le pattern de timer
        timer_pattern = self._analyze_timer_pattern(timer_frames)
        
        # Calculer le vrai start_time basé sur la valeur du timer de début
        real_start_time = self._calculate_real_start_time(start_time, start_timer)
        
        return {
            'start_time': real_start_time,
            'end_time': end_time,
            'start_timer_value': start_timer,
            'duration_seconds': duration_seconds,
            'total_frames': len(round_frames),
            'timer_frames': len(timer_frames),
            'timer_coverage': len(timer_frames) / len(round_frames) if round_frames else 0,
            'timer_pattern': timer_pattern
        }
    
    def _analyze_timer_pattern(self, timer_frames: List[Dict]) -> Dict:
        """Analyse le pattern du timer pour validation (doit être décroissant)."""
        if len(timer_frames) < 2:
            return {'is_decreasing': False, 'max_timer': None, 'min_timer': None}
            
        timers = [f['timer_value'] for f in timer_frames]
        max_timer = max(timers)
        min_timer = min(timers)
        
        # Vérifier tendance décroissante générale
        decreasing_count = 0
        total_transitions = 0
        
        for i in range(1, len(timers)):
            if timers[i-1] != timers[i]:  # Ignorer valeurs identiques
                total_transitions += 1
                if timers[i] < timers[i-1]:  # Timer diminue
                    decreasing_count += 1
        
        is_decreasing = (decreasing_count / total_transitions > 0.6) if total_transitions > 0 else False
        
        return {
            'is_decreasing': is_decreasing,
            'max_timer': max_timer,
            'min_timer': min_timer,
            'decreasing_ratio': decreasing_count / total_transitions if total_transitions > 0 else 0
        }
    
    def _is_valid_round(self, round_data: Dict) -> bool:
        """Vérifie si un round détecté est valide selon les critères SF6."""
        duration = round_data['duration_seconds']
        timer_coverage = round_data['timer_coverage']
        timer_pattern = round_data['timer_pattern']
        start_timer = round_data['start_timer_value']
        
        # Critères de validation SF6 (pas de filtre durée - un round peut durer 5-99s)
        coverage_ok = timer_coverage >= (1 - self.timer_tolerance)
        
        # Assouplir la validation du timer de début pour capturer plus de rounds
        # Accepter les rounds qui commencent à ≥80 (au lieu de ≥90)
        start_ok = start_timer >= 80  
        pattern_ok = timer_pattern['is_decreasing']  # Timer doit décompter
        
        if self.debug:
            self._log_debug(f"Validation round: durée={duration}s, "
                          f"couverture={timer_coverage:.2f} ({coverage_ok}), "
                          f"début={start_timer} ({start_ok}), "
                          f"décroissant={pattern_ok}")
        
        return coverage_ok and start_ok and pattern_ok
    
    def _is_valid_set(self, rounds: List[Dict]) -> bool:
        """
        Vérifie si un set détecté est valide selon les critères SF6.
        Un set SF6 doit avoir au minimum 2 rounds (premier à 2 victoires).
        """
        min_rounds_per_set = 2
        is_valid = len(rounds) >= min_rounds_per_set
        
        if self.debug and not is_valid:
            self._log_debug(f"Set rejeté: {len(rounds)} rounds < {min_rounds_per_set} minimum")
        
        return is_valid
    
    def _is_valid_match(self, sets: List[Dict]) -> bool:
        """
        Vérifie si un match détecté est valide selon les critères SF6.
        Un match SF6 doit avoir soit:
        - Au minimum 2 sets OU
        - Un seul set avec 3+ rounds (cas particulier)
        """
        if len(sets) >= 2:
            return True  # 2+ sets = match valide
        
        if len(sets) == 1:
            # Un seul set: doit avoir 3+ rounds pour être un match valide
            rounds_count = sets[0].get('rounds_count', 0)
            return rounds_count >= 3
        
        return False  # Pas de sets = pas de match
    
    def _group_rounds_into_sets(self, detected_rounds: List[Dict], parsed_frames: List[Dict]) -> List[Dict]:
        """
        Groupe les rounds détectés en sets basés sur les mêmes personnages.
        Un set = même character1 vs character2 + rounds consécutifs.
        """
        if not detected_rounds:
            return []
        
        sets = []
        current_set_rounds = []
        current_characters = None
        
        for i, round_data in enumerate(detected_rounds):
            # Extraire les personnages pour ce round
            round_start = round_data['start_time'].strftime('%H:%M:%S')
            round_end = round_data['end_time'].strftime('%H:%M:%S')
            characters = self._extract_match_characters(round_start, round_end, parsed_frames)
            
            char_pair = (characters['character1'], characters['character2'])
            
            if current_characters is None:
                # Premier round
                current_characters = char_pair
                current_set_rounds = [round_data]
            elif current_characters == char_pair:
                # Même personnages -> même set
                current_set_rounds.append(round_data)
            else:
                # Changement de personnages -> nouveau set
                if current_set_rounds and self._is_valid_set(current_set_rounds):
                    set_data = self._create_set_from_rounds(current_set_rounds, len(sets) + 1, current_characters)
                    sets.append(set_data)
                    self._log_debug(f"Set valide créé: {current_characters[0]} vs {current_characters[1]} ({len(current_set_rounds)} rounds)")
                elif current_set_rounds:
                    self._log_debug(f"Set rejeté: {current_characters[0]} vs {current_characters[1]} ({len(current_set_rounds)} rounds - minimum 2 requis)")
                
                current_characters = char_pair
                current_set_rounds = [round_data]
        
        # Ajouter le dernier set
        if current_set_rounds and self._is_valid_set(current_set_rounds):
            set_data = self._create_set_from_rounds(current_set_rounds, len(sets) + 1, current_characters)
            sets.append(set_data)
            self._log_debug(f"Set valide créé: {current_characters[0]} vs {current_characters[1]} ({len(current_set_rounds)} rounds)")
        elif current_set_rounds:
            self._log_debug(f"Set rejeté: {current_characters[0]} vs {current_characters[1]} ({len(current_set_rounds)} rounds - minimum 2 requis)")
        
        self._log_debug(f"Groupage terminé: {len(sets)} sets détectés")
        return sets
    
    def _create_set_from_rounds(self, rounds: List[Dict], set_number: int, characters: Tuple[str, str]) -> Dict:
        """Crée un objet set à partir d'une liste de rounds."""
        if not rounds:
            return {}
        
        # Formater les rounds selon la configuration
        formatted_rounds = []
        round_fields = self.output_fields.get('round_fields', [])
        
        for round_data in rounds:
            formatted_round = {}
            
            if 'start_time' in round_fields:
                formatted_round['start_time'] = round_data['start_time'].strftime('%H:%M:%S')
            if 'end_time' in round_fields:
                formatted_round['end_time'] = round_data['end_time'].strftime('%H:%M:%S')
            if 'confidence' in round_fields:
                formatted_round['confidence'] = self._calculate_round_confidence(round_data)
            if 'duration_seconds' in round_fields:
                formatted_round['duration_seconds'] = int(round_data['duration_seconds'])
                
            formatted_rounds.append(formatted_round)
        
        # Le start_time du set est le même que celui du premier round (déjà calculé)
        set_start_time = rounds[0]['start_time']
        
        set_data = {
            'set_number': set_number,
            'start_time': set_start_time.strftime('%H:%M:%S'),
            'character1': characters[0],
            'character2': characters[1],
            'rounds_count': len(rounds),
            'rounds': formatted_rounds,
            # Données temporelles brutes pour calculs internes
            '_raw_start_time': set_start_time,
            '_raw_end_time': rounds[-1]['end_time']
        }
        
        self._log_debug(f"Set {set_number} créé: {characters[0]} vs {characters[1]} ({len(rounds)} rounds)")
        return set_data
    
    def _group_sets_into_matches(self, sets: List[Dict]) -> List[Dict]:
        """
        Groupe les sets en matches. Un match = série de sets consécutifs
        (les personnages peuvent changer entre sets mais c'est la même opposition de joueurs).
        """
        if not sets:
            return []
        
        matches = []
        current_match_sets = [sets[0]]
        
        for i in range(1, len(sets)):
            prev_set = sets[i-1]
            curr_set = sets[i]
            
            # Calculer le gap entre sets en utilisant les données brutes
            prev_end = prev_set['_raw_end_time']
            curr_start = curr_set['_raw_start_time']
            gap_seconds = (curr_start - prev_end).total_seconds()
            
            if gap_seconds >= self.min_match_gap:
                # Gap important -> nouveau match
                if current_match_sets and self._is_valid_match(current_match_sets):
                    match = self._create_match_from_sets(current_match_sets, len(matches) + 1)
                    matches.append(match)
                    self._log_debug(f"Match valide créé avec {len(current_match_sets)} sets")
                elif current_match_sets:
                    self._log_debug(f"Match rejeté: {len(current_match_sets)} sets - minimum requis non atteint")
                current_match_sets = [curr_set]
            else:
                # Même match (opposition continue)
                current_match_sets.append(curr_set)
        
        # Ajouter le dernier match
        if current_match_sets and self._is_valid_match(current_match_sets):
            match = self._create_match_from_sets(current_match_sets, len(matches) + 1)
            matches.append(match)
            self._log_debug(f"Match valide créé avec {len(current_match_sets)} sets")
        elif current_match_sets:
            self._log_debug(f"Match rejeté: {len(current_match_sets)} sets - minimum requis non atteint")
        
        self._log_debug(f"Groupage terminé: {len(matches)} matches détectés")
        return matches
    
    def _create_match_from_sets(self, sets: List[Dict], match_id: int) -> Dict:
        """Crée un objet match à partir d'une liste de sets."""
        if not sets:
            return {}
        
        # Construire les données du match selon la configuration
        match_data = {}
        match_fields = self.output_fields.get('match_fields', [])
        
        if 'match_id' in match_fields:
            match_data['match_id'] = match_id
        if 'start_time' in match_fields:
            # Le start_time du match est le même que celui du premier set (déjà calculé)
            match_data['start_time'] = sets[0]['start_time']
        if 'end_time' in match_fields:
            match_data['end_time'] = sets[-1]['_raw_end_time'].strftime('%H:%M:%S')
        if 'sets_count' in match_fields:
            match_data['sets_count'] = len(sets)
        
        # Extraire les noms des joueurs si nécessaire
        if 'player1' in match_fields or 'player2' in match_fields:
            player_names = self._extract_player_names(sets)
            if 'player1' in match_fields:
                match_data['player1'] = player_names['player1']
            if 'player2' in match_fields:
                match_data['player2'] = player_names['player2']
        
        if 'winner' in match_fields:
            match_data['winner'] = self._determine_match_winner(sets)
        
        # Nettoyer les clés internes des sets avant inclusion
        clean_sets = []
        for set_data in sets:
            clean_set = {k: v for k, v in set_data.items() if not k.startswith('_')}
            clean_sets.append(clean_set)
        
        # Toujours inclure les sets nettoyés dans le match
        match_data['sets'] = clean_sets
        
        self._log_debug(f"Match {match_id} créé avec {len(sets)} sets")
        return match_data
    
    def _identify_rounds(self, detected_rounds: List[Dict]) -> List[Dict]:
        """Formate les rounds détectés pour la sortie finale."""
        formatted_rounds = []
        round_fields = self.output_fields.get('round_fields', [])
        
        for i, round_data in enumerate(detected_rounds):
            formatted_round = {}
            
            # Construire le round selon la configuration
            if 'round_id' in round_fields:
                formatted_round['round_id'] = i + 1
            if 'start_time' in round_fields:
                formatted_round['start_time'] = round_data['start_time'].strftime('%H:%M:%S')
            if 'end_time' in round_fields:
                formatted_round['end_time'] = round_data['end_time'].strftime('%H:%M:%S')
            if 'duration_seconds' in round_fields:
                formatted_round['duration_seconds'] = int(round_data['duration_seconds'])
            if 'start_timer_value' in round_fields:
                formatted_round['start_timer_value'] = round_data['start_timer_value']
            if 'timer_pattern' in round_fields:
                formatted_round['timer_pattern'] = round_data['timer_pattern']
            if 'confidence' in round_fields:
                formatted_round['confidence'] = self._calculate_round_confidence(round_data)
            
            formatted_rounds.append(formatted_round)
            self._log_debug(f"Round formaté: {i + 1} - {round_data['start_time'].strftime('%H:%M:%S')}")
            
        return formatted_rounds
    
    def _identify_matches(self, rounds: List[Dict], parsed_frames: List[Dict]) -> List[Dict]:
        """Identifie les matches à partir des rounds détectés."""
        if not rounds:
            return []
            
        matches = []
        current_match_rounds = [rounds[0]]
        
        for i in range(1, len(rounds)):
            prev_round = rounds[i-1]
            curr_round = rounds[i]
            
            # Calculer gap entre rounds
            if 'end_time' in prev_round:
                prev_end = datetime.strptime(prev_round['end_time'], '%H:%M:%S')
            else:
                # Si pas d'end_time, estimer en ajoutant une durée approximative
                prev_start = datetime.strptime(prev_round['start_time'], '%H:%M:%S')
                # Durée round SF6 typique: 90-120 secondes
                estimated_duration = prev_round.get('duration_seconds', 90)
                prev_end = prev_start + timedelta(seconds=estimated_duration)
            
            curr_start = datetime.strptime(curr_round['start_time'], '%H:%M:%S')
            gap_seconds = (curr_start - prev_end).total_seconds()
            
            if gap_seconds >= self.min_match_gap:
                # Gap suffisant -> nouveau match
                match = self._create_match_from_rounds(current_match_rounds, len(matches) + 1, parsed_frames)
                matches.append(match)
                current_match_rounds = [curr_round]
            else:
                # Même match
                current_match_rounds.append(curr_round)
        
        # Ajouter le dernier match
        if current_match_rounds:
            match = self._create_match_from_rounds(current_match_rounds, len(matches) + 1, parsed_frames)
            matches.append(match)
            
        return matches
    
    def _create_match_from_rounds(self, rounds: List[Dict], match_id: int, parsed_frames: List[Dict]) -> Dict:
        """Crée un objet match à partir d'une liste de rounds."""
        if not rounds:
            return {}
            
        start_time = rounds[0]['start_time']
        
        # Calculer end_time en fonction de la disponibilité
        if 'end_time' in rounds[-1]:
            end_time = rounds[-1]['end_time']
        else:
            # Estimer end_time en utilisant duration_seconds
            last_start = datetime.strptime(rounds[-1]['start_time'], '%H:%M:%S')
            last_duration = rounds[-1].get('duration_seconds', 90)
            end_time = (last_start + timedelta(seconds=last_duration)).strftime('%H:%M:%S')
        
        # Calculer durée totale
        total_duration = sum(r.get('duration_seconds', 90) for r in rounds)
        
        # Extraire les personnages pour ce match
        characters = self._extract_match_characters(start_time, end_time, parsed_frames)
        
        # Construire les données du match selon la configuration
        match_data = {}
        match_fields = self.output_fields.get('match_fields', [])
        
        if 'match_id' in match_fields:
            match_data['match_id'] = match_id
        if 'start_time' in match_fields:
            match_data['start_time'] = start_time
        if 'end_time' in match_fields:
            match_data['end_time'] = end_time
        if 'total_duration_seconds' in match_fields:
            match_data['total_duration_seconds'] = total_duration
        if 'rounds_count' in match_fields:
            match_data['rounds_count'] = len(rounds)
        if 'character1' in match_fields:
            match_data['character1'] = characters.get('character1', '')
        if 'character2' in match_fields:
            match_data['character2'] = characters.get('character2', '')
        if 'confidence' in match_fields:
            # Calculer confiance moyenne seulement si les rounds ont cette info
            confidences = [r['confidence'] for r in rounds if 'confidence' in r]
            match_data['confidence'] = sum(confidences) / len(confidences) if confidences else 0.8
            
        # Inclure les rounds si demandé
        if self.output_fields.get('include_rounds_in_matches', False):
            match_data['rounds'] = rounds
        
        self._log_debug(f"Match détecté: {match_id} avec {len(rounds)} rounds")
        return match_data
    
    def _extract_match_characters(self, start_time: str, end_time: str, parsed_frames: List[Dict]) -> Dict:
        """Extrait les noms des personnages pour un match donné."""
        # Convertir les temps en objets datetime pour comparaison avec parsed_frames
        start_dt = datetime.strptime(start_time, '%H:%M:%S')
        # Remplacer l'année par celle des parsed_frames pour la comparaison
        start_dt = start_dt.replace(year=2000, month=1, day=1)
        
        end_dt = datetime.strptime(end_time, '%H:%M:%S') 
        end_dt = end_dt.replace(year=2000, month=1, day=1)
        
        # Filtrer les frames du match
        match_frames = [
            f for f in parsed_frames 
            if start_dt <= f['timestamp'] <= end_dt
        ]
        
        if self.debug:
            self._log_debug(f"Extraction personnages pour match {start_time}-{end_time}: {len(match_frames)} frames")
        
        # Compter les occurrences de chaque personnage
        char1_counts = {}
        char2_counts = {}
        
        for frame in match_frames:
            char1 = frame.get('character1', '').strip()
            char2 = frame.get('character2', '').strip()
            
            if char1:
                char1_counts[char1] = char1_counts.get(char1, 0) + 1
            if char2:
                char2_counts[char2] = char2_counts.get(char2, 0) + 1
        
        # Prendre les personnages les plus fréquents
        most_frequent_char1 = max(char1_counts.items(), key=lambda x: x[1])[0] if char1_counts else ''
        most_frequent_char2 = max(char2_counts.items(), key=lambda x: x[1])[0] if char2_counts else ''
        
        if self.debug:
            self._log_debug(f"Personnages détectés: {most_frequent_char1} vs {most_frequent_char2}")
            if char1_counts:
                self._log_debug(f"Character1 counts: {dict(sorted(char1_counts.items(), key=lambda x: x[1], reverse=True)[:3])}")
            if char2_counts:
                self._log_debug(f"Character2 counts: {dict(sorted(char2_counts.items(), key=lambda x: x[1], reverse=True)[:3])}")
        
        return {
            'character1': most_frequent_char1,
            'character2': most_frequent_char2
        }
    
    def _calculate_real_start_time(self, detection_timestamp: datetime, detected_timer_value: int) -> datetime:
        """
        Calcule le vrai start_time d'un round basé sur la valeur du timer détectée.
        
        Logique: Si on détecte un timer à X, le round a commencé quand le timer était à 99.
        Le start_time réel est 1 seconde avant que le timer soit à 99.
        
        Args:
            detection_timestamp: Timestamp de la frame où le timer a été détecté
            detected_timer_value: Valeur du timer détectée (ex: 96)
            
        Returns:
            Timestamp calculé du vrai début de round
        """
        if detected_timer_value is None or detected_timer_value > 99:
            # Si pas de timer valide, utiliser le timestamp de détection
            return detection_timestamp
        
        # Calculer combien de secondes se sont écoulées depuis que le timer était à 99
        seconds_elapsed_since_99 = 99 - detected_timer_value
        
        # Le vrai start_time est 1 seconde avant que le timer soit à 99
        real_start_time = detection_timestamp - timedelta(seconds=seconds_elapsed_since_99 + 1)
        
        self._log_debug(f"Calcul start_time: timer détecté {detected_timer_value} à {detection_timestamp.strftime('%H:%M:%S')} "
                       f"→ vrai début: {real_start_time.strftime('%H:%M:%S')}")
        
        return real_start_time
    
    def _extract_player_names(self, sets: List[Dict]) -> Dict[str, str]:
        """
        Extrait les noms des joueurs pour un match donné.
        
        Utilise les noms de personnages les plus fréquents dans tous les sets du match.
        
        Args:
            sets: Liste des sets du match
            
        Returns:
            Dict avec 'player1' et 'player2'
        """
        if not sets:
            return {'player1': '', 'player2': ''}
        
        # Collecter tous les personnages des sets
        char1_counts = {}
        char2_counts = {}
        
        for set_data in sets:
            char1 = set_data.get('character1', '').strip()
            char2 = set_data.get('character2', '').strip()
            
            if char1:
                char1_counts[char1] = char1_counts.get(char1, 0) + 1
            if char2:
                char2_counts[char2] = char2_counts.get(char2, 0) + 1
        
        # Prendre les personnages les plus fréquents comme représentants des joueurs
        player1 = max(char1_counts.items(), key=lambda x: x[1])[0] if char1_counts else ''
        player2 = max(char2_counts.items(), key=lambda x: x[1])[0] if char2_counts else ''
        
        self._log_debug(f"Joueurs extraits du match: {player1} vs {player2}")
        
        return {
            'player1': player1,
            'player2': player2
        }
    
    def _determine_match_winner(self, sets: List[Dict]) -> Optional[str]:
        """
        Détermine le gagnant d'un match basé sur les sets.
        
        Pour l'instant retourne null.
        TODO: Implémenter logique de comptage des sets gagnés.
        
        Args:
            sets: Liste des sets du match
            
        Returns:
            'player1', 'player2', ou None si match incomplet/indéterminé
        """
        # Placeholder - logique à implémenter plus tard
        return None
    
    def _calculate_round_confidence(self, round_data: Dict) -> float:
        """Calcule la confiance dans la détection d'un round."""
        timer_coverage = round_data['timer_coverage']
        duration = round_data['duration_seconds']
        pattern = round_data['timer_pattern']
        start_timer = round_data['start_timer_value']
        
        # Confiance basée sur plusieurs facteurs
        confidence = 0.0
        
        # 40% basé sur couverture timer
        confidence += timer_coverage * 0.4
        
        # 30% basé sur pattern décroissant
        confidence += pattern['decreasing_ratio'] * 0.3
        
        # 20% basé sur durée typique SF6 (90-180s)
        if 90 <= duration <= 180:
            confidence += 0.2
        elif 60 <= duration <= 240:
            confidence += 0.1
        
        # 10% bonus si commence à 99 (timer SF6 typique)
        if start_timer == 99:
            confidence += 0.1
        elif start_timer >= 95:
            confidence += 0.05
            
        return min(confidence, 1.0)
    
    def _generate_stats(self, original_frames: List[Dict], matches: List[Dict]) -> Dict:
        """Génère des statistiques sur l'analyse."""
        total_frames = len(original_frames)
        frames_with_timer = sum(1 for f in original_frames 
                               if f.get('timer_value', '').strip().isdigit())
        
        # Compter sets et rounds total
        total_sets = sum(len(m.get('sets', [])) for m in matches)
        total_rounds = sum(
            sum(s.get('rounds_count', 0) for s in m.get('sets', []))
            for m in matches
        )
        
        return {
            'total_frames_analyzed': total_frames,
            'frames_with_valid_timer': frames_with_timer,
            'timer_detection_rate': frames_with_timer / total_frames if total_frames > 0 else 0,
            'total_matches_detected': len(matches),
            'total_sets_detected': total_sets,
            'total_rounds_detected': total_rounds,
            'avg_sets_per_match': total_sets / len(matches) if matches else 0,
            'avg_rounds_per_set': total_rounds / total_sets if total_sets else 0
        }
    
    def _log_debug(self, message: str):
        """Log debug si activé."""
        if self.debug:
            print(f"[MatchDeductor] {message}")