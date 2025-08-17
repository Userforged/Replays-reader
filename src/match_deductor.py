"""
Module de déduction des matches et rounds à partir des données d'analyse JSON.

Version refactorisée utilisant le pipeline Characters First avec composants spécialisés.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import json
from .text_validator import TextValidator
from .frame_processor import FrameProcessor
from .round_detector import RoundDetector
from .set_grouper import SetGrouper
from .match_grouper import MatchGrouper


class MatchDeductor:
    """
    Orchestrateur principal pour la déduction des matches Street Fighter 6.
    
    Utilise le pipeline Characters First avec composants spécialisés :
    - FrameProcessor : Traitement des frames (phases 1-3)
    - RoundDetector : Détection des rounds
    - SetGrouper : Groupage en sets
    - MatchGrouper : Groupage en matches
    """
    
    def __init__(self, min_round_duration_seconds=120, 
                 min_match_gap_seconds=180,
                 timer_tolerance_ratio=0.3,
                 output_fields=None,
                 debug=False,
                 characters_file="characters.json",
                 players_config_file="players.json",
                 restricted_players_file=None):
        """
        Initialise l'orchestrateur avec les composants spécialisés.
        
        Args:
            min_round_duration_seconds: Durée minimum d'un round (défaut: 2 minutes)
            min_match_gap_seconds: Gap minimum entre matches (défaut: 3 minutes) 
            timer_tolerance_ratio: Ratio de tolérance pour timer manquant (défaut: 30%)
            output_fields: Dict définissant les champs à inclure dans la sortie
            debug: Mode debug pour logs détaillés
            characters_file: Fichier JSON avec la liste des personnages SF6
            players_config_file: Fichier JSON avec la configuration des joueurs et API
            restricted_players_file: Fichier JSON avec liste restreinte de joueurs (optionnel)
        """
        self.debug = debug
        
        # Gérer la liste restreinte de joueurs si fournie
        resolved_players = None
        if restricted_players_file:
            resolved_players = self._resolve_restricted_players(restricted_players_file)
            if self.debug:
                print(f"[MatchDeductor] Liste restreinte résolue: {len(resolved_players)} joueurs")
        
        # Initialiser le validateur de texte avec support des joueurs
        self.text_validator = TextValidator(
            characters_file=characters_file, 
            players_config_file=players_config_file,
            debug=debug
        )
        
        # Si on a des joueurs restreints, les stocker pour usage ultérieur
        if resolved_players:
            self.restricted_players = resolved_players
            if self.debug:
                print(f"[MatchDeductor] Utilisation de {len(resolved_players)} joueurs restreints")
        else:
            self.restricted_players = None
        
        # Initialiser les composants spécialisés
        self.frame_processor = FrameProcessor(self.text_validator, debug=debug)
        self.round_detector = RoundDetector(
            min_round_duration=min_round_duration_seconds,
            timer_tolerance=timer_tolerance_ratio,
            debug=debug
        )
        self.set_grouper = SetGrouper(
            max_set_gap=300,  # 5 minutes max entre rounds d'un set
            min_rounds_per_set=2,
            debug=debug
        )
        self.match_grouper = MatchGrouper(
            min_match_gap=min_match_gap_seconds,
            min_sets_per_match=1,
            min_rounds_per_match=3,
            debug=debug
        )
        
        # Configuration des champs de sortie par défaut
        default_fields = {
            'match_fields': ['start_time', 'character1', 'character2'],
            'include_rounds_in_matches': False,
            'include_sets_in_matches': True,
            'include_round_details': True
        }
        self.output_fields = output_fields or default_fields
    
    def analyze_frames(self, frames_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Point d'entrée principal pour l'analyse des frames.
        
        Orchestrate le pipeline complet :
        1. Traitement des frames (Characters First pipeline)
        2. Détection des rounds 
        3. Groupage en sets
        4. Groupage en matches
        5. Génération des statistiques
        
        Args:
            frames_data: Liste des frames avec données OCR
            
        Returns:
            Dict avec matches détectés et statistiques
        """
        if not frames_data:
            return self._create_empty_result()
        
        self._log_debug(f"🚀 MatchDeductor: Analyse de {len(frames_data)} frames")
        
        # Phase 1-3: Traitement des frames avec Characters First pipeline
        processed_frames = self.frame_processor.process_frames(frames_data)
        self._log_debug(f"   → {len(processed_frames)} frames traitées")
        
        # Récupérer les données intermédiaires pour usage ultérieur
        pipeline_data = self.frame_processor.get_processed_data()
        
        # Phase 4: Détection des rounds
        parsed_frames = self._prepare_frames_for_round_detection(processed_frames)
        rounds = self.round_detector.detect_rounds(parsed_frames)
        self._log_debug(f"   → {len(rounds)} rounds détectés")
        
        if not rounds:
            return self._create_empty_result(stats={'total_frames_analyzed': len(frames_data)})
        
        # Phase 5: Groupage en sets
        sets = self.set_grouper.group_rounds_into_sets(rounds)
        self._log_debug(f"   → {len(sets)} sets créés")
        
        if not sets:
            return self._create_empty_result(stats={'total_frames_analyzed': len(frames_data), 'total_rounds_detected': len(rounds)})
        
        # Phase 6: Groupage en matches
        matches = self.match_grouper.group_sets_into_matches(sets)
        self._log_debug(f"   → {len(matches)} matches finaux")
        
        # Phase 7: Enrichissement avec les noms de joueurs
        enriched_matches = self._enrich_matches_with_players(matches, pipeline_data['player_validated_frames'])
        
        # Phase 8: Génération du résultat final
        result = self._create_final_result(enriched_matches, rounds, sets, frames_data)
        
        return result
    
    def _prepare_frames_for_round_detection(self, processed_frames: List[Dict]) -> List[Dict]:
        """
        Prépare les frames traitées pour la détection de rounds.
        
        Convertit le format des frames pour le RoundDetector.
        """
        parsed_frames = []
        
        for frame in processed_frames:
            # Extraire timestamp
            timestamp_str = frame.get('timestamp', '')
            timestamp = self._parse_timestamp(timestamp_str)
            
            # Convertir timer en entier si possible
            timer_value = None
            timer_raw = frame.get('timer_value', '')
            if timer_raw and str(timer_raw).strip().isdigit():
                timer_value = int(timer_raw)
            
            parsed_frame = {
                'timestamp': timestamp,
                'timestamp_str': timestamp_str,
                'timer_value': timer_value,
                'character1': frame.get('character1', ''),
                'character2': frame.get('character2', ''),
                'player1': frame.get('player1', ''),
                'player2': frame.get('player2', ''),
                '_original_frame': frame
            }
            
            parsed_frames.append(parsed_frame)
        
        return parsed_frames
    
    def _enrich_matches_with_players(self, matches: List[Dict], player_validated_frames: List[Dict]) -> List[Dict]:
        """
        Enrichit les matches avec les noms de joueurs extraits des frames validées.
        """
        enriched_matches = []
        
        for match in matches:
            # Copier le match
            enriched_match = match.copy()
            
            # Extraire les joueurs pour cette période temporelle
            match_players = self._extract_player_names_for_match(
                match['start_time'], 
                match['end_time'], 
                player_validated_frames
            )
            
            # Mettre à jour les joueurs du match
            enriched_match.update(match_players)
            
            # Enrichir aussi les sets avec les joueurs
            if 'sets' in enriched_match:
                enriched_sets = []
                for set_data in enriched_match['sets']:
                    enriched_set = set_data.copy()
                    set_players = self._extract_player_names_for_set(
                        set_data['start_time'],
                        set_data['end_time'], 
                        player_validated_frames
                    )
                    enriched_set.update(set_players)
                    enriched_sets.append(enriched_set)
                
                enriched_match['sets'] = enriched_sets
            
            enriched_matches.append(enriched_match)
        
        return enriched_matches
    
    def _extract_player_names_for_match(self, match_start: datetime, match_end: datetime, 
                                       player_frames: List[Dict]) -> Dict[str, str]:
        """
        Extrait les noms des joueurs pour une période de match spécifique.
        """
        # Ajouter une marge réduite pour éviter les débordements sur les matches précédents
        match_start_with_margin = match_start - timedelta(seconds=30)
        match_end_with_margin = match_end + timedelta(minutes=2)
        
        # Collecter les noms de joueurs
        player1_counts = {}
        player2_counts = {}
        
        for frame_data in player_frames:
            frame_timestamp_str = frame_data.get('timestamp', '')
            frame_timestamp = self._parse_timestamp(frame_timestamp_str)
            
            if match_start_with_margin <= frame_timestamp <= match_end_with_margin:
                player1_name = frame_data.get('player1', '').strip()
                player2_name = frame_data.get('player2', '').strip()
                
                if player1_name:
                    player1_counts[player1_name] = player1_counts.get(player1_name, 0) + 1
                if player2_name:
                    player2_counts[player2_name] = player2_counts.get(player2_name, 0) + 1
        
        # Prendre les noms les plus fréquents
        player1 = max(player1_counts.items(), key=lambda x: x[1])[0] if player1_counts else ''
        player2 = max(player2_counts.items(), key=lambda x: x[1])[0] if player2_counts else ''
        
        return {
            'player1': player1,
            'player2': player2
        }
    
    def _extract_player_names_for_set(self, set_start: datetime, set_end: datetime,
                                     player_frames: List[Dict]) -> Dict[str, str]:
        """
        Extrait les noms des joueurs pour une période de set spécifique.
        """
        # Ajouter une petite marge
        set_start_with_margin = set_start - timedelta(seconds=30)
        set_end_with_margin = set_end + timedelta(seconds=30)
        
        # Collecter les noms de joueurs
        player1_counts = {}
        player2_counts = {}
        
        for frame_data in player_frames:
            frame_timestamp_str = frame_data.get('timestamp', '')
            frame_timestamp = self._parse_timestamp(frame_timestamp_str)
            
            if set_start_with_margin <= frame_timestamp <= set_end_with_margin:
                player1_name = frame_data.get('player1', '').strip()
                player2_name = frame_data.get('player2', '').strip()
                
                if player1_name:
                    player1_counts[player1_name] = player1_counts.get(player1_name, 0) + 1
                if player2_name:
                    player2_counts[player2_name] = player2_counts.get(player2_name, 0) + 1
        
        # Prendre les noms les plus fréquents
        player1 = max(player1_counts.items(), key=lambda x: x[1])[0] if player1_counts else ''
        player2 = max(player2_counts.items(), key=lambda x: x[1])[0] if player2_counts else ''
        
        return {
            'player1': player1,
            'player2': player2
        }
    
    def _create_final_result(self, matches: List[Dict], rounds: List[Dict], 
                           sets: List[Dict], frames_data: List[Dict]) -> Dict[str, Any]:
        """
        Crée le résultat final avec matches et statistiques.
        """
        # Calculer statistiques globales
        stats = self._calculate_global_statistics(matches, rounds, sets, frames_data)
        
        # Formater les matches selon la configuration
        formatted_matches = self._format_matches_for_output(matches)
        
        return {
            'matches': formatted_matches,
            'stats': stats
        }
    
    def _calculate_global_statistics(self, matches: List[Dict], rounds: List[Dict], 
                                   sets: List[Dict], frames_data: List[Dict]) -> Dict[str, Any]:
        """
        Calcule les statistiques globales de l'analyse.
        """
        # Statistiques de base
        total_frames = len(frames_data)
        total_matches = len(matches)
        total_sets = len(sets)
        total_rounds = len(rounds)
        
        # Taux de détection du timer
        timer_detections = sum(1 for f in frames_data if f.get('timer_value', '').strip())
        timer_detection_rate = timer_detections / total_frames if total_frames > 0 else 0.0
        
        # Statistiques des composants
        round_stats = self.round_detector.calculate_round_confidence({}) if hasattr(self.round_detector, 'calculate_round_confidence') else {}
        set_stats = self.set_grouper.calculate_set_statistics(sets)
        match_stats = self.match_grouper.calculate_match_statistics(matches)
        
        return {
            'total_frames_analyzed': total_frames,
            'total_matches_detected': total_matches,
            'total_sets_detected': total_sets,
            'total_rounds_detected': total_rounds,
            'timer_detection_rate': round(timer_detection_rate, 3),
            'round_statistics': round_stats,
            'set_statistics': set_stats,
            'match_statistics': match_stats
        }
    
    def _format_matches_for_output(self, matches: List[Dict]) -> List[Dict]:
        """
        Formate les matches selon la configuration de sortie.
        """
        formatted_matches = []
        
        for match in matches:
            # Copier les champs configurés
            formatted_match = {}
            match_fields = self.output_fields.get('match_fields', ['start_time', 'character1', 'character2'])
            
            for field in match_fields:
                if field in match:
                    value = match[field]
                    # Convertir datetime en string pour sérialisation JSON
                    if isinstance(value, datetime):
                        formatted_match[field] = value.strftime('%H:%M:%S')
                    else:
                        formatted_match[field] = value
            
            # Ajouter champs standards
            formatted_match.update({
                'sets_count': match.get('sets_count', 0),
                'total_rounds': match.get('total_rounds', 0),
                'player1': match.get('player1', ''),
                'player2': match.get('player2', ''),
                'winner': match.get('winner'),
                'duration_seconds': match.get('duration_seconds', 0)
            })
            
            # Inclure sets si configuré
            if self.output_fields.get('include_sets_in_matches', True) and 'sets' in match:
                formatted_match['sets'] = self._format_sets_for_output(match['sets'])
            
            formatted_matches.append(formatted_match)
        
        return formatted_matches
    
    def _format_sets_for_output(self, sets: List[Dict]) -> List[Dict]:
        """
        Formate les sets pour la sortie.
        """
        formatted_sets = []
        
        for set_data in sets:
            formatted_set = {
                'set_number': set_data.get('set_number', 0),
                'start_time': set_data['start_time'].strftime('%H:%M:%S') if isinstance(set_data['start_time'], datetime) else set_data['start_time'],
                'character1': set_data.get('character1', ''),
                'character2': set_data.get('character2', ''),
                'rounds_count': set_data.get('rounds_count', 0),
                'player1': set_data.get('player1', ''),
                'player2': set_data.get('player2', '')
            }
            
            # Inclure rounds si configuré
            if self.output_fields.get('include_round_details', True) and 'rounds' in set_data:
                formatted_set['rounds'] = self._format_rounds_for_output(set_data['rounds'])
            
            formatted_sets.append(formatted_set)
        
        return formatted_sets
    
    def _format_rounds_for_output(self, rounds: List[Dict]) -> List[Dict]:
        """
        Formate les rounds pour la sortie.
        """
        formatted_rounds = []
        
        for round_data in rounds:
            formatted_round = {
                'start_time': round_data['start_time'].strftime('%H:%M:%S') if isinstance(round_data['start_time'], datetime) else round_data['start_time'],
                'confidence': round(round_data.get('confidence', 0.0), 2)
            }
            
            formatted_rounds.append(formatted_round)
        
        return formatted_rounds
    
    def _create_empty_result(self, stats: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Crée un résultat vide avec statistiques minimales.
        """
        default_stats = {
            'total_frames_analyzed': 0,
            'total_matches_detected': 0,
            'total_sets_detected': 0,
            'total_rounds_detected': 0,
            'timer_detection_rate': 0.0
        }
        
        if stats:
            default_stats.update(stats)
        
        return {
            'matches': [],
            'stats': default_stats
        }
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """
        Parse un timestamp string en objet datetime.
        
        Gère les formats HH:MM:SS et MM:SS.
        """
        if not timestamp_str:
            return datetime.min
        
        timestamp_str = str(timestamp_str).strip()
        
        try:
            # Format HH:MM:SS
            if timestamp_str.count(':') == 2:
                return datetime.strptime(timestamp_str, '%H:%M:%S')
            # Format MM:SS (assume heure 0)
            elif timestamp_str.count(':') == 1:
                return datetime.strptime(f"0:{timestamp_str}", '%H:%M:%S')
            else:
                self._log_debug(f"⚠️ Format timestamp non reconnu: {timestamp_str}")
                return datetime.min
        except ValueError as e:
            self._log_debug(f"⚠️ Erreur parsing timestamp '{timestamp_str}': {e}")
            return datetime.min
    
    def _resolve_restricted_players(self, restricted_file: str) -> List[str]:
        """
        Résout une liste restreinte de joueurs depuis un fichier.
        
        Args:
            restricted_file: Chemin vers le fichier de joueurs restreints
            
        Returns:
            Liste enrichie des noms de joueurs
        """
        try:
            # Charger le fichier restreint
            with open(restricted_file, 'r', encoding='utf-8') as f:
                restricted_data = json.load(f)
            
            # Extraire les noms des joueurs
            restricted_names = self._extract_player_names_from_data(restricted_data)
            
            if not restricted_names:
                if self.debug:
                    print(f"[MatchDeductor] Aucun joueur trouvé dans {restricted_file}")
                return []
            
            # Utiliser PlayerProvider pour résoudre les noms
            from .player_provider import PlayerProvider
            full_provider = PlayerProvider('players.json')
            resolved_names = full_provider.resolve_restricted_players(restricted_names)
            
            if self.debug:
                print(f"[MatchDeductor] Résolution: {len(restricted_names)} → {len(resolved_names)} noms")
            
            return resolved_names
            
        except Exception as e:
            if self.debug:
                print(f"[MatchDeductor] Erreur résolution joueurs restreints: {e}")
            return []
    
    def _extract_player_names_from_data(self, restricted_data: Dict) -> List[str]:
        """
        Extrait les noms de joueurs depuis les données JSON.
        
        Args:
            restricted_data: Données JSON du fichier restreint
            
        Returns:
            Liste des noms de joueurs extraits
        """
        restricted_names = []
        
        # Gérer différents formats de fichier
        if 'players' in restricted_data:
            for player in restricted_data['players']:
                if isinstance(player, dict) and 'name' in player:
                    restricted_names.append(player['name'])
                elif isinstance(player, str):
                    restricted_names.append(player)
        
        if 'static_players' in restricted_data:
            for player in restricted_data['static_players']:
                if isinstance(player, str):
                    restricted_names.append(player)
        
        return restricted_names
    
    def _log_debug(self, message: str):
        """Log message si debug activé."""
        if self.debug:
            print(f"[MatchDeductor] {message}")