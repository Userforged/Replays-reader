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
from difflib import get_close_matches
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
        close_matches = get_close_matches(cleaned_text, self.timer_values, n=1, cutoff=0.7)
        if close_matches:
            best_match = close_matches[0]
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
        close_matches = get_close_matches(
            cleaned_text, self.character_names, n=1, cutoff=0.6
        )
        
        if close_matches:
            best_match = close_matches[0]
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