#!/usr/bin/env python3
"""
TextValidator: Centralise la logique de validation des textes OCR pour Street Fighter 6.

Cette classe sépare la validation du texte de l'extraction OCR, permettant une meilleure
séparation des responsabilités :
- ImageAnalyzer : extraction OCR pure (texte brut)
- TextValidator : validation et nettoyage des textes selon les règles SF6
- MatchDeductor : logique métier de détection des matches
"""

import json
import os
from rapidfuzz import process
from typing import Optional, List, Union, Dict, Any


class TextValidator:
    """
    Valide et nettoie les textes extraits par OCR selon les règles Street Fighter 6.
    
    Responsibilities:
    - Validation des timers (00-99)
    - Validation des noms de personnages 
    - Correspondance floue (fuzzy matching)
    - Nettoyage des textes OCR bruités
    """
    
    def __init__(self, characters_file: str = "characters.json", debug: bool = False):
        """
        Initialise le validateur avec la base de données des personnages.
        
        Args:
            characters_file: Chemin vers le fichier JSON des personnages SF6
            debug: Mode debug pour logs détaillés
        """
        self.characters_file = characters_file
        self.debug = debug
        
        # Charger les données de référence
        self.character_names = self._load_character_names()
        self.timer_values = self._generate_timer_values()
        
        if self.debug:
            char_count = len(self.character_names) if self.character_names else 0
            print(f"[TextValidator] Initialized with {char_count} characters, {len(self.timer_values)} timer values")
    
    def _load_character_names(self) -> Optional[List[str]]:
        """Charge la liste des noms de personnages depuis le fichier JSON."""
        try:
            if not os.path.exists(self.characters_file):
                if self.debug:
                    print(f"[TextValidator] ⚠️ Character file not found: {self.characters_file}")
                return None
            
            with open(self.characters_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            characters = data.get('characters', [])
            if not characters:
                if self.debug:
                    print(f"[TextValidator] ⚠️ No characters found in {self.characters_file}")
                return None
            
            if self.debug:
                print(f"[TextValidator] ✅ Loaded {len(characters)} characters from {self.characters_file}")
            
            return characters
            
        except Exception as e:
            if self.debug:
                print(f"[TextValidator] ❌ Error loading characters: {e}")
            return None
    
    def _generate_timer_values(self) -> List[str]:
        """Génère la liste des valeurs de timer valides (00-99)."""
        return [f"{i:02d}" for i in range(100)]
    
    def validate_timer(self, raw_text: str) -> str:
        """
        Valide et nettoie un texte de timer OCR.
        
        Args:
            raw_text: Texte brut de l'OCR (ex: "Timer: 45", "4S", "99")
            
        Returns:
            Timer validé au format "XX" ou chaîne vide si invalide
        """
        if not raw_text or not raw_text.strip():
            return ""
        
        cleaned_text = raw_text.strip()
        
        if self.debug:
            print(f"[TextValidator] 🕐 Timer validation: '{raw_text}' -> '{cleaned_text}'")
        
        # 1. Correspondance exacte (cas idéal)
        if cleaned_text in self.timer_values:
            if self.debug:
                print(f"[TextValidator] ✅ Timer exact match: '{cleaned_text}'")
            return cleaned_text
        
        # 2. Extraction des chiffres du texte brut
        digits = ''.join(filter(str.isdigit, cleaned_text))
        
        if digits:
            # Formater sur 2 chiffres si nécessaire
            if len(digits) == 1:
                digits = '0' + digits
            elif len(digits) > 2:
                digits = digits[:2]  # Prendre les 2 premiers chiffres
            
            # Vérifier que c'est dans la plage valide
            if digits in self.timer_values:
                if self.debug:
                    print(f"[TextValidator] ✅ Timer digits extracted: '{raw_text}' -> '{digits}'")
                return digits
        
        # 3. Correspondance floue sur les timer values
        result = process.extractOne(cleaned_text, self.timer_values, score_cutoff=70)
        if result:
            best_match, score, _ = result
            if self.debug:
                print(f"[TextValidator] ✅ Timer fuzzy match: '{raw_text}' -> '{best_match}'")
            return best_match
        
        # 4. Rejet
        if self.debug:
            print(f"[TextValidator] ❌ Timer rejected: '{raw_text}'")
        return ""
    
    def validate_character(self, raw_text: str) -> str:
        """
        Valide et nettoie un nom de personnage OCR.
        
        Args:
            raw_text: Texte brut de l'OCR (ex: "RYUU", "chunli", "M.BISON")
            
        Returns:
            Nom de personnage validé ou chaîne vide si invalide
        """
        if not raw_text or not raw_text.strip():
            return ""
        
        if not self.character_names:
            # Pas de base de données de personnages, retourner le texte nettoyé
            return self._clean_character_name(raw_text)
        
        cleaned_text = raw_text.strip().upper()
        
        if self.debug:
            print(f"[TextValidator] 👤 Character validation: '{raw_text}' -> '{cleaned_text}'")
        
        # 1. Correspondance exacte
        if cleaned_text in self.character_names:
            if self.debug:
                print(f"[TextValidator] ✅ Character exact match: '{cleaned_text}'")
            return cleaned_text
        
        # 2. Correspondance floue
        result = process.extractOne(
            cleaned_text, self.character_names, score_cutoff=60
        )
        
        if result:
            best_match, score, _ = result
            if self.debug:
                print(f"[TextValidator] ✅ Character fuzzy match: '{raw_text}' -> '{best_match}'")
            return best_match
        
        # 3. Rejet
        if self.debug:
            print(f"[TextValidator] ❌ Character rejected: '{raw_text}'")
        return ""
    
    def _clean_character_name(self, raw_text: str) -> str:
        """Nettoie un nom de personnage sans validation (fallback)."""
        return raw_text.strip().upper()
    
    def validate_frame(self, frame_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valide une frame complète en appliquant les validations appropriées.
        
        Args:
            frame_data: Données brutes d'une frame avec champs OCR
            
        Returns:
            Frame avec champs validés
        """
        validated_frame = frame_data.copy()
        
        # Valider les différents champs
        if 'timer_value' in frame_data:
            validated_frame['timer_value'] = self.validate_timer(frame_data['timer_value'])
        
        if 'character1' in frame_data:
            validated_frame['character1'] = self.validate_character(frame_data['character1'])
        
        if 'character2' in frame_data:
            validated_frame['character2'] = self.validate_character(frame_data['character2'])
        
        # Préserver les autres champs tels quels (timestamp, etc.)
        return validated_frame
    
    def validate_frames_batch(self, frames_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Valide un lot de frames de manière efficace.
        
        Args:
            frames_data: Liste des frames à valider
            
        Returns:
            Liste des frames validées
        """
        if self.debug:
            print(f"[TextValidator] 📊 Validating batch of {len(frames_data)} frames")
        
        validated_frames = []
        for frame in frames_data:
            validated_frame = self.validate_frame(frame)
            validated_frames.append(validated_frame)
        
        if self.debug:
            print(f"[TextValidator] ✅ Batch validation completed")
        
        return validated_frames
    
    def get_validation_stats(self, original_frames: List[Dict[str, Any]], 
                           validated_frames: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calcule des statistiques de validation pour analyse.
        
        Args:
            original_frames: Frames avant validation
            validated_frames: Frames après validation
            
        Returns:
            Dictionnaire avec statistiques de validation
        """
        stats = {
            'total_frames': len(original_frames),
            'timer_validated': 0,
            'character1_validated': 0,
            'character2_validated': 0,
            'timer_rejected': 0,
            'character1_rejected': 0,
            'character2_rejected': 0
        }
        
        for orig, valid in zip(original_frames, validated_frames):
            # Timer
            if orig.get('timer_value') and valid.get('timer_value'):
                stats['timer_validated'] += 1
            elif orig.get('timer_value') and not valid.get('timer_value'):
                stats['timer_rejected'] += 1
            
            # Character1
            if orig.get('character1') and valid.get('character1'):
                stats['character1_validated'] += 1
            elif orig.get('character1') and not valid.get('character1'):
                stats['character1_rejected'] += 1
            
            # Character2
            if orig.get('character2') and valid.get('character2'):
                stats['character2_validated'] += 1
            elif orig.get('character2') and not valid.get('character2'):
                stats['character2_rejected'] += 1
        
        # Calculer les taux
        if stats['total_frames'] > 0:
            stats['timer_validation_rate'] = stats['timer_validated'] / stats['total_frames']
            stats['character1_validation_rate'] = stats['character1_validated'] / stats['total_frames']
            stats['character2_validation_rate'] = stats['character2_validated'] / stats['total_frames']
        
        return stats
    
    # ==========================================
    # TEMPORAL INTERPOLATION METHODS  
    # ==========================================
    
    def interpolate_frames_temporal(self, frames_data: List[Dict[str, Any]], 
                                  window_size: int = 5) -> List[Dict[str, Any]]:
        """
        Applique l'interpolation temporelle sur une séquence de frames.
        
        Combine plusieurs techniques :
        - Voting system sur fenêtre glissante
        - Distance de Levenshtein avec rapidfuzz  
        - Règles métier SF6
        
        Args:
            frames_data: Liste des frames avec données OCR brutes
            window_size: Taille de la fenêtre glissante (doit être impaire)
            
        Returns:
            Liste des frames avec interpolation temporelle appliquée
        """
        if len(frames_data) < 3:
            if self.debug:
                print(f"[TextValidator] ⚠️ Trop peu de frames ({len(frames_data)}) pour interpolation")
            return frames_data
        
        # Assurer fenêtre impaire pour avoir un centre
        if window_size % 2 == 0:
            window_size += 1
            
        if self.debug:
            print(f"[TextValidator] 🔄 Interpolation temporelle sur {len(frames_data)} frames (fenêtre: {window_size})")
        
        interpolated_frames = frames_data.copy()
        half_window = window_size // 2
        
        # Parcourir chaque frame (sauf les bords)
        for i in range(half_window, len(frames_data) - half_window):
            # Extraire fenêtre autour de la frame i
            window_start = i - half_window
            window_end = i + half_window + 1
            window = frames_data[window_start:window_end]
            
            # Interpoler chaque champ
            interpolated_frame = interpolated_frames[i].copy()
            
            # Timer interpolation
            interpolated_frame['timer_value'] = self._interpolate_timer_window(
                window, center_index=half_window
            )
            
            # Character interpolation  
            interpolated_frame['character1'] = self._interpolate_character_window(
                window, 'character1', center_index=half_window
            )
            interpolated_frame['character2'] = self._interpolate_character_window(
                window, 'character2', center_index=half_window
            )
            
            interpolated_frames[i] = interpolated_frame
        
        if self.debug:
            changes_count = sum(1 for orig, interp in zip(frames_data, interpolated_frames) 
                              if orig != interp)
            print(f"[TextValidator] ✅ Interpolation: {changes_count} frames modifiées")
        
        return interpolated_frames
    
    def _interpolate_timer_window(self, window: List[Dict[str, Any]], center_index: int) -> str:
        """
        Interpole la valeur timer en utilisant le contexte de la fenêtre.
        
        Stratégies :
        1. Validation SF6 : timer doit être décroissant dans un round
        2. Voting system si plusieurs valeurs cohérentes  
        3. Extrapolation linéaire si pattern clair
        """
        center_frame = window[center_index]
        current_timer = center_frame.get('timer_value', '')
        
        # Extraire toutes les valeurs timer de la fenêtre
        timer_values = []
        for frame in window:
            timer_str = frame.get('timer_value', '')
            if timer_str and timer_str.isdigit() and len(timer_str) <= 2:
                timer_values.append((int(timer_str), timer_str))
            else:
                timer_values.append((None, timer_str))
        
        center_timer_num, center_timer_str = timer_values[center_index]
        
        # Si timer central est valide et cohérent, le garder
        if center_timer_num is not None:
            if self._is_timer_coherent_in_sequence(timer_values, center_index):
                return center_timer_str
        
        # Essayer interpolation par neighbors
        interpolated = self._interpolate_timer_from_neighbors(timer_values, center_index)
        if interpolated:
            if self.debug:
                print(f"[TextValidator] 🕐 Timer interpolé: '{current_timer}' -> '{interpolated}'")
            return interpolated
            
        # Voting system en dernier recours
        return self._vote_timer_window(window)
    
    def _interpolate_character_window(self, window: List[Dict[str, Any]], 
                                    field_name: str, center_index: int) -> str:
        """
        Interpole un champ character en utilisant voting + distance de Levenshtein.
        """
        center_frame = window[center_index]
        current_char = center_frame.get(field_name, '')
        
        # Extraire valeurs non-vides de la fenêtre
        char_values = []
        for frame in window:
            char_val = frame.get(field_name, '').strip()
            if char_val:
                char_values.append(char_val)
        
        if not char_values:
            return current_char
        
        # Si valeur centrale existe, vérifier cohérence avec rapidfuzz
        if current_char:
            best_neighbor = self._find_closest_character_neighbor(current_char, char_values)
            if best_neighbor and best_neighbor != current_char:
                # Vérifier distance avec rapidfuzz
                distance_score = process.extractOne(current_char, [best_neighbor])
                if distance_score and distance_score[1] >= 80:  # score >= 80%
                    if self.debug:
                        print(f"[TextValidator] 👤 Character corrigé: '{current_char}' -> '{best_neighbor}' (score: {distance_score[1]:.1f})")
                    return best_neighbor
        
        # Voting system sur fenêtre
        return self._vote_character_window(window, field_name)
    
    def _is_timer_coherent_in_sequence(self, timer_values: List[tuple], center_index: int) -> bool:
        """Vérifie si le timer central respecte la logique SF6 (décroissant)."""
        center_val = timer_values[center_index][0]
        if center_val is None:
            return False
        
        # Vérifier cohérence avec voisins directs
        for offset in [-1, 1]:
            neighbor_idx = center_index + offset
            if 0 <= neighbor_idx < len(timer_values):
                neighbor_val = timer_values[neighbor_idx][0]
                if neighbor_val is not None:
                    # Timer doit diminuer au fil du temps (tolérance de ±3)
                    expected_diff = abs(offset * 3)  # ~3 secondes par frame
                    actual_diff = abs(center_val - neighbor_val)
                    if actual_diff > 10:  # Écart trop important
                        return False
        return True
    
    def _interpolate_timer_from_neighbors(self, timer_values: List[tuple], center_index: int) -> Optional[str]:
        """Essaie d'interpoler timer depuis voisins valides."""
        # Chercher voisins valides
        left_val, right_val = None, None
        
        for i in range(center_index - 1, -1, -1):
            if timer_values[i][0] is not None:
                left_val = timer_values[i][0]
                break
                
        for i in range(center_index + 1, len(timer_values)):
            if timer_values[i][0] is not None:
                right_val = timer_values[i][0]
                break
        
        # Interpolation linéaire si on a les deux voisins
        if left_val is not None and right_val is not None:
            if left_val > right_val:  # Cohérent avec timer décroissant
                interpolated_val = (left_val + right_val) // 2
                if 0 <= interpolated_val <= 99:
                    return f"{interpolated_val:02d}"
        
        # Si un seul voisin, estimer
        if left_val is not None:
            estimated = max(0, left_val - 3)  # -3 secondes estimated
            return f"{estimated:02d}"
        elif right_val is not None:
            estimated = min(99, right_val + 3)  # +3 secondes estimated
            return f"{estimated:02d}"
            
        return None
    
    def _vote_timer_window(self, window: List[Dict[str, Any]]) -> str:
        """Voting system pour timer : valeur la plus fréquente."""
        timer_votes = {}
        
        for frame in window:
            timer_val = frame.get('timer_value', '').strip()
            if timer_val and timer_val.isdigit() and len(timer_val) <= 2:
                timer_votes[timer_val] = timer_votes.get(timer_val, 0) + 1
        
        if timer_votes:
            # Retourner valeur avec le plus de votes
            winner = max(timer_votes.items(), key=lambda x: x[1])
            return winner[0]
        
        return ''
    
    def _vote_character_window(self, window: List[Dict[str, Any]], field_name: str) -> str:
        """Voting system pour character : valeur la plus fréquente avec validation."""
        char_votes = {}
        
        for frame in window:
            char_val = frame.get(field_name, '').strip()
            if char_val and self.character_names and char_val in self.character_names:
                char_votes[char_val] = char_votes.get(char_val, 0) + 1
        
        if char_votes:
            winner = max(char_votes.items(), key=lambda x: x[1])
            return winner[0]
        
        return ''
    
    def _find_closest_character_neighbor(self, current_char: str, neighbors: List[str]) -> Optional[str]:
        """Trouve le voisin character le plus proche avec rapidfuzz."""
        if not neighbors or not self.character_names:
            return None
        
        # Filtrer les voisins valides (dans character_names)
        valid_neighbors = [n for n in neighbors if n in self.character_names]
        if not valid_neighbors:
            return None
        
        # Trouver le plus proche avec rapidfuzz
        result = process.extractOne(current_char, valid_neighbors, score_cutoff=60)
        if result:
            return result[0]
        
        return None