"""
Module de traitement des frames avec pipeline Characters First.

Ce module implémente les 3 premières phases du pipeline de déduction :
- Phase 1: Character Detection (highest confidence)  
- Phase 2: Timer Refinement (with character context)
- Phase 3: Player Detection (with character+timer context)
"""

from typing import List, Dict, Any, Optional
from .text_validator import TextValidator


class FrameProcessor:
    """
    Processeur de frames implémentant le pipeline Characters First.
    
    Principe : Les personnages sont les données les plus fiables et doivent
    être détectés en premier pour guider la validation du timer et des joueurs.
    """
    
    def __init__(self, text_validator: TextValidator, debug: bool = False):
        """
        Initialise le processeur de frames.
        
        Args:
            text_validator: Instance de TextValidator pour la validation
            debug: Mode debug pour logs détaillés
        """
        self.text_validator = text_validator
        self.debug = debug
        
        # Stockage des données par phase pour usage downstream
        self.character_validated_frames = []
        self.timer_enhanced_frames = []
        self.player_validated_frames = []
    
    def process_frames(self, frames_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Traite les frames selon le pipeline Characters First.
        
        Args:
            frames_data: Frames brutes avec données OCR
            
        Returns:
            Frames enrichies avec toutes les validations appliquées
        """
        if not frames_data:
            return []
        
        self._log_debug(f"🚀 FrameProcessor: traitement de {len(frames_data)} frames")
        
        # Phase 1: Character Detection (highest confidence)
        character_frames = self._phase1_character_detection(frames_data)
        
        # Phase 2: Timer Refinement (with character context)
        timer_frames = self._phase2_timer_refinement(character_frames)
        
        # Phase 3: Player Detection (with character+timer context)
        player_frames = self._phase3_player_detection(timer_frames)
        
        return player_frames
    
    def _phase1_character_detection(self, frames_data: List[Dict]) -> List[Dict]:
        """
        Phase 1: Détection et validation des personnages (données les plus fiables).
        
        Les personnages ont la plus haute confiance car:
        - ROI stable et bien définie
        - Liste fermée de 26 personnages SF6
        - Peu d'ambiguïté dans la détection OCR
        
        Returns:
            Frames avec personnages validés et interpolés
        """
        self._log_debug("  📝 Phase 1: Character Detection (highest confidence)")
        
        # Interpolation temporelle pour corriger les erreurs OCR ponctuelles
        self._log_debug("    → Interpolation temporelle des personnages...")
        interpolated_frames = self.text_validator.interpolate_frames_temporal(frames_data)
        
        # Validation spécifique des personnages (priorité absolue)
        character_validated_frames = []
        for frame in interpolated_frames:
            enhanced_frame = frame.copy()
            
            # Valider character1 et character2 avec haute priorité
            if 'character1' in frame:
                enhanced_frame['character1'] = self.text_validator.validate_character(frame['character1'])
            if 'character2' in frame:
                enhanced_frame['character2'] = self.text_validator.validate_character(frame['character2'])
            
            character_validated_frames.append(enhanced_frame)
        
        # Stocker pour usage dans les phases suivantes
        self.character_validated_frames = character_validated_frames
        
        if self.debug:
            char_stats = self._calculate_character_detection_stats(character_validated_frames)
            self._log_debug(f"    → Character detection: {char_stats}")
        
        return character_validated_frames
    
    def _phase2_timer_refinement(self, character_frames: List[Dict]) -> List[Dict]:
        """
        Phase 2: Raffinement des timers en utilisant le contexte des personnages.
        
        Les personnages détectés en Phase 1 aident à:
        - Valider les transitions de rounds (même personnages = même set)
        - Détecter les patterns temporels cohérents
        - Filtrer les faux positifs de timer
        
        Args:
            character_frames: Frames avec personnages validés
            
        Returns:
            Frames avec timers raffinés
        """
        self._log_debug("  ⏱️  Phase 2: Timer Refinement (with character context)")
        
        # Valider les timers avec contexte personnage
        timer_enhanced_frames = []
        for frame in character_frames:
            enhanced_frame = frame.copy()
            
            # Raffiner timer avec contexte des personnages
            if 'timer_value' in frame:
                char1 = frame.get('character1', '')
                char2 = frame.get('character2', '')
                character_context = f"{char1}vs{char2}" if char1 and char2 else ""
                
                enhanced_frame['timer_value'] = self.text_validator.validate_timer(
                    frame['timer_value']
                )
                
                # Ajouter métadonnées de contexte pour la suite
                enhanced_frame['_character_context'] = character_context
            
            timer_enhanced_frames.append(enhanced_frame)
        
        # Stocker pour usage dans la phase suivante
        self.timer_enhanced_frames = timer_enhanced_frames
        
        if self.debug:
            timer_stats = self._calculate_timer_detection_stats(timer_enhanced_frames)
            self._log_debug(f"    → Timer refinement: {timer_stats}")
        
        return timer_enhanced_frames
    
    def _phase3_player_detection(self, timer_character_frames: List[Dict]) -> List[Dict]:
        """
        Phase 3: Détection des joueurs avec contexte personnage + timer.
        
        Utilise les données des phases précédentes pour:
        - Prioriser les joueurs cohérents avec les personnages
        - Analyser les patterns temporels pour suggestions
        - Appliquer la validation probabiliste
        
        Args:
            timer_character_frames: Frames avec personnages et timers validés
            
        Returns:
            Frames avec joueurs détectés et validés
        """
        self._log_debug("  👤 Phase 3: Player Detection (with character+timer context)")
        
        # Validation des joueurs avec contexte complet
        player_enhanced_frames = []
        for frame in timer_character_frames:
            enhanced_frame = frame.copy()
            
            # Valider player1 avec contexte character1 (restriction déjà dans PlayerProvider)
            if 'player1' in frame:
                char1 = frame.get('character1', '')
                enhanced_frame['player1'] = self.text_validator.validate_player(
                    frame['player1'], 
                    context_character=char1
                )
            
            # Valider player2 avec contexte character2 (restriction déjà dans PlayerProvider)
            if 'player2' in frame:
                char2 = frame.get('character2', '')
                enhanced_frame['player2'] = self.text_validator.validate_player(
                    frame['player2'],
                    context_character=char2
                )
            
            player_enhanced_frames.append(enhanced_frame)
        
        # Amélioration avec patterns temporels
        if self.text_validator.player_provider:
            self._log_debug("    → Amélioration avec patterns temporels...")
            player_enhanced_frames = self.text_validator.enhance_player_detection_with_character_context(
                player_enhanced_frames
            )
        
        # Stocker pour usage downstream
        self.player_validated_frames = player_enhanced_frames
        
        if self.debug:
            player_stats = self._calculate_player_detection_stats(player_enhanced_frames)
            self._log_debug(f"    → Player detection: {player_stats}")
        
        return player_enhanced_frames
    
    def get_processed_data(self) -> Dict[str, List[Dict]]:
        """
        Retourne toutes les données traitées par les différentes phases.
        
        Returns:
            Dict avec les données de chaque phase pour usage downstream
        """
        return {
            'character_validated_frames': self.character_validated_frames,
            'timer_enhanced_frames': self.timer_enhanced_frames,
            'player_validated_frames': self.player_validated_frames
        }
    
    # ================================================================================================
    # STATISTICS AND MONITORING METHODS
    # ================================================================================================
    
    def _calculate_character_detection_stats(self, frames: List[Dict]) -> str:
        """Calcule statistiques de détection des personnages."""
        total_frames = len(frames)
        char1_detected = sum(1 for f in frames if f.get('character1', '').strip())
        char2_detected = sum(1 for f in frames if f.get('character2', '').strip())
        
        return f"char1: {char1_detected}/{total_frames} ({char1_detected/total_frames:.1%}), " \
               f"char2: {char2_detected}/{total_frames} ({char2_detected/total_frames:.1%})"
    
    def _calculate_timer_detection_stats(self, frames: List[Dict]) -> str:
        """Calcule statistiques de détection des timers."""
        total_frames = len(frames)
        timer_detected = sum(1 for f in frames if f.get('timer_value', '').strip())
        
        return f"timer: {timer_detected}/{total_frames} ({timer_detected/total_frames:.1%})"
    
    def _calculate_player_detection_stats(self, frames: List[Dict]) -> str:
        """Calcule statistiques de détection des joueurs."""
        total_frames = len(frames)
        player1_detected = sum(1 for f in frames if f.get('player1', '').strip())
        player2_detected = sum(1 for f in frames if f.get('player2', '').strip())
        
        return f"player1: {player1_detected}/{total_frames} ({player1_detected/total_frames:.1%}), " \
               f"player2: {player2_detected}/{total_frames} ({player2_detected/total_frames:.1%})"
    
    def _log_debug(self, message: str):
        """Log message si debug activé."""
        if self.debug:
            print(f"[FrameProcessor] {message}")