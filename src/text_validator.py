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
from typing import Any, Dict, List, Optional

from rapidfuzz import process

try:
    from .player_provider import PlayerProvider
    PLAYER_PROVIDER_AVAILABLE = True
except ImportError:
    try:
        from player_provider import PlayerProvider
        PLAYER_PROVIDER_AVAILABLE = True
    except ImportError:
        PlayerProvider = None
        PLAYER_PROVIDER_AVAILABLE = False


class TextValidator:
    """
    Valide et nettoie les textes extraits par OCR selon les règles Street Fighter 6.

    Responsibilities:
    - Validation des timers (00-99)
    - Validation des noms de personnages
    - Correspondance floue (fuzzy matching)
    - Nettoyage des textes OCR bruités
    """

    def __init__(self, characters_file: str = "characters.json",
                 players_database_file: str = "players.json",
                 restricted_players_file: str = None,
                 debug: bool = False):
        """
        Initialise le validateur avec la base de données des personnages et joueurs.

        Args:
            characters_file: Chemin vers le fichier JSON des personnages SF6
            players_database_file: Chemin vers le fichier JSON de la base de données des joueurs
            restricted_players_file: Chemin vers le fichier JSON de la liste restreinte (optionnel)
            debug: Mode debug pour logs détaillés
        """
        self.characters_file = characters_file
        self.players_database_file = players_database_file
        self.restricted_players_file = restricted_players_file
        self.debug = debug

        # Charger les données de référence
        self.character_names = self._load_character_names()
        self.timer_values = self._generate_timer_values()

        # Initialiser PlayerProvider pour validation des joueurs
        self.player_provider = self._initialize_player_provider()

        if self.debug:
            char_count = len(self.character_names) if self.character_names else 0
            player_count = 0
            if self.player_provider:
                try:
                    cache_info = self.player_provider.get_cache_info()
                    player_count = cache_info.get('total_names', cache_info.get('total_players', 0))
                except Exception:
                    pass

            print(
                f"[TextValidator] Initialized with {char_count} characters, "
                f"{len(self.timer_values)} timer values, {player_count} players"
            )

    def _load_character_names(self) -> Optional[List[str]]:
        """Charge la liste des noms de personnages depuis le fichier JSON."""
        try:
            if not os.path.exists(self.characters_file):
                if self.debug:
                    print(
                        f"[TextValidator] ⚠️ Character file not found: {self.characters_file}"
                    )
                return None

            with open(self.characters_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            characters = data.get("characters", [])
            if not characters:
                if self.debug:
                    print(
                        f"[TextValidator] ⚠️ No characters found in {self.characters_file}"
                    )
                return None

            if self.debug:
                print(
                    f"[TextValidator] ✅ Loaded {len(characters)} characters from {self.characters_file}"
                )

            return characters

        except Exception as e:
            if self.debug:
                print(f"[TextValidator] ❌ Error loading characters: {e}")
            return None

    def _generate_timer_values(self) -> List[str]:
        """Génère la liste des valeurs de timer valides (00-99)."""
        return [f"{i:02d}" for i in range(100)]

    def _initialize_player_provider(self) -> Optional['PlayerProvider']:
        """Initialise le PlayerProvider pour validation des joueurs."""
        if not PLAYER_PROVIDER_AVAILABLE:
            if self.debug:
                print("[TextValidator] ⚠️ PlayerProvider not available")
            return None

        try:
            if not os.path.exists(self.players_database_file):
                if self.debug:
                    print(f"[TextValidator] ⚠️ Players database file not found: {self.players_database_file}")
                return None

            # 🔒 Nouveau design: PlayerProvider avec restriction dès le constructeur
            player_provider = PlayerProvider(
                database_file=self.players_database_file,
                restricted_file=self.restricted_players_file
            )

            if self.debug:
                cache_info = player_provider.get_cache_info()
                total_names = cache_info.get('total_names', cache_info.get('total_players', 0))
                print(f"[TextValidator] ✅ PlayerProvider initialized with {total_names} total names")

            return player_provider

        except Exception as e:
            if self.debug:
                print(f"[TextValidator] ❌ Error initializing PlayerProvider: {e}")
            return None

    def validate_timer(self, raw_text: str) -> str:
        """
        Valide et nettoie un texte de timer OCR.

        Args:
            raw_text: Texte brut de l'OCR (ex: "Timer: 45", "4S", "99")

        Returns:
            Timer validé au format "XX" ou chaîne vide si invalide
        """
        # Déléguer à l'API générique avec extraction de chiffres activée
        return self.validate_text(raw_text, expected_values=self.timer_values,
                                fuzzy_score_threshold=70, extract_digits=True)

    def validate_character(self, raw_text: str) -> str:
        """
        Valide et nettoie un nom de personnage OCR.

        Args:
            raw_text: Texte brut de l'OCR (ex: "RYUU", "chunli", "M.BISON")

        Returns:
            Nom de personnage validé ou chaîne vide si invalide
        """
        # Si pas de contraintes du tout, retourner texte nettoyé
        if not self.character_names:
            return self._clean_character_name(raw_text)

        # Déléguer à l'API générique
        return self.validate_text(raw_text, expected_values=self.character_names,
                                fuzzy_score_threshold=60, extract_digits=False)

    def validate_player(self, raw_text: str, threshold: float = 0.5, context_character: str = "") -> str:
        """
        Valide et nettoie un nom de joueur OCR en utilisant PlayerProvider.

        Args:
            raw_text: Texte brut de l'OCR (ex: "DAIGO", "JUSTIN WONG", "801 STRIDER")
            threshold: Seuil pour correspondance floue (0.0-1.0)
            context_character: Personnage joué pour validation croisée (optionnel)

        Returns:
            Nom de joueur validé ou chaîne vide si invalide
        """
        if not raw_text or not raw_text.strip():
            return ""

        # Utiliser PlayerProvider pour obtenir la liste de joueurs
        player_values = None
        if self.player_provider:
            try:
                player_values = self.player_provider.get_all_players()
            except Exception as e:
                if self.debug:
                    print(f"[TextValidator] ❌ Error getting players from PlayerProvider: {e}")
                return raw_text.strip()
        else:
            # Pas de validation disponible, retourner texte nettoyé
            return raw_text.strip()

        if not player_values:
            return raw_text.strip()

        cleaned_text = raw_text.strip()

        # Clean common OCR artifacts and prefixes/suffixes for better matching
        original_cleaned = cleaned_text

        # Remove common country/region prefixes
        for prefix in ['JP ', 'US ', 'KR ', 'FR ', 'UK ', 'CA ', 'BR ']:
            if cleaned_text.upper().startswith(prefix):
                cleaned_text = cleaned_text[len(prefix):].strip()
                break

        # Remove common suffixes and OCR artifacts (récursive cleaning)
        suffixes_to_remove = [
            ' JP', ' US', ' KR', ' FR', ' UK', ' CA', ' BR',  # Country codes
            ' JPI', ' JP 2', ' US 2', ' KR 2',               # OCR artifacts
            ' [L] JPI', ' [L] JP', ' [L]',                   # Bracket artifacts
            ' 2', ' NO', ' No 2', ' NO 2',                   # Number artifacts
            'PI', 'I', '2'                                   # Single char artifacts
        ]

        # Nettoyer récursivement (plusieurs passes)
        for _ in range(3):  # Max 3 passes pour éviter boucle infinie
            original = cleaned_text
            for suffix in suffixes_to_remove:
                if cleaned_text.upper().endswith(suffix.upper()):
                    cleaned_text = cleaned_text[:-len(suffix)].strip()
                    break
            if original == cleaned_text:  # Plus de changements
                break

        # Remove common tournament/sponsor/team prefixes (comprehensive cleaning)
        sponsor_prefixes = [
            'REJECT', 'REJECTZ', 'TEAM ', 'SQUAD ',
            'ZETA', 'TSM ', 'RB ', 'RED BULL ', 'REDBULL',
            'FGC ', 'FCG ', 'UYU ', 'RISE ', 'LIQUID',
            'FNATIC', 'PANDA ', 'ECHO FOX', 'ECHOFOX',
            'WBG ', 'WBG', 'OG ', 'OG', 'NIP', 'NO NIP',
            'C) ', '(', ')', 'GRAND', 'FINALS',
            'CN ', 'CN', 'JP ', 'JP', 'KR ', 'KR', 'US ', 'US',  # Country codes
            'NO ', 'NO', 'DO ', 'DO', 'HK ', 'HK', 'JO ', 'JO',   # More countries
            'KSG', 'KSG '  # Sponsor prefix for XiaoHai (like "CN KSGXIAOHAI")
        ]

        # Multiple pass cleaning for complex OCR artifacts
        for _ in range(3):  # Max 3 passes
            original = cleaned_text

            # Clean sponsor prefixes
            for prefix in sponsor_prefixes:
                if cleaned_text.upper().startswith(prefix.upper()):
                    remaining = cleaned_text[len(prefix):].strip()
                    if remaining:  # Only use if something remains
                        cleaned_text = remaining
                    break

            # Clean mixed patterns like "ZETAKAKERU", "RBMENARD", "NIPPHENOM"
            # Extract player name from sponsor+name combinations
            if len(cleaned_text) > 6:  # Only for longer strings
                # Pattern: SPONSOR+NAME (like ZETAKAKERU, RBMENARD, NIPPHENOM)
                # Order matters: specific patterns first, then general ones
                sponsor_patterns = [
                    ('NIPPHENOM', 'PHENOM'),  # Special case for "NO NIPPHENOM"
                    ('RBMENARD', 'MENARD'),   # Special case for "WBG RBMENARD"
                    ('ZETA', 'ZETA'),
                    ('RB', 'RB'),
                    ('WBG', 'WBG'),
                    ('TSM', 'TSM'),
                    ('OG', 'OG'),
                    ('NIP', 'NIP'),
                ]

                for pattern, extraction in sponsor_patterns:
                    if pattern in cleaned_text.upper():
                        if pattern in ['NIPPHENOM', 'RBMENARD']:
                            # Special extraction patterns - these take priority
                            cleaned_text = extraction
                            if self.debug:
                                print(f"[TextValidator] 🔧 Special pattern extraction: '{original}' -> '{cleaned_text}'")
                            break
                        elif cleaned_text.upper().startswith(pattern):
                            candidate = cleaned_text[len(pattern):].strip()
                            # Check if candidate could be a valid player name (fuzzy match against known players)
                            if candidate and len(candidate) >= 3:
                                if self.player_provider:
                                    try:
                                        matches = self.player_provider.search_player(candidate, threshold=0.4)
                                        if matches:
                                            cleaned_text = candidate
                                            if self.debug:
                                                print(f"[TextValidator] 🔧 Sponsor extraction: '{original}' -> '{cleaned_text}' (found {matches[0]})")
                                            break
                                    except Exception:
                                        pass

            # Stop if no more changes
            if original == cleaned_text:
                break

        if self.debug:
            if original_cleaned != cleaned_text:
                print(f"[TextValidator] 🧹 Player name cleaned: '{original_cleaned}' -> '{cleaned_text}'")
            print(f"[TextValidator] 🔍 Player validation: '{raw_text}' -> '{cleaned_text}' "
                  f"(against {len(player_values)} players)")

        # 1. Correspondance exacte (insensible à la casse)
        for player in player_values:
            if player.upper() == cleaned_text.upper():
                if self.debug:
                    print(f"[TextValidator] ✅ Exact player match: '{cleaned_text}' -> '{player}'")
                return player

        # 2. Si contexte personnage disponible, prioriser les joueurs qui jouent ce personnage
        character_consistent_matches = []
        if context_character and self.player_provider:
            try:
                character_players = self.player_provider.find_players_by_character(context_character)
                if character_players:
                    # Chercher parmi les joueurs qui jouent ce personnage
                    char_result = process.extractOne(cleaned_text, character_players, score_cutoff=int(threshold * 100))
                    if char_result:
                        character_consistent_matches.append((char_result[0], char_result[1], "character_consistent"))
                        if self.debug:
                            print(f"[TextValidator] 🎯 Character-consistent match: '{raw_text}' -> '{char_result[0]}' "
                                  f"(score: {char_result[1]:.1f}, plays {context_character})")
            except Exception as e:
                if self.debug:
                    print(f"[TextValidator] ⚠️ Error in character-consistent search: {e}")

        # 3. Correspondance floue avec rapidfuzz (liste restreinte PRIORITAIRE)
        all_player_matches = []
        fuzzy_threshold = int(threshold * 100)

        # Create uppercase versions for case-insensitive matching
        cleaned_text_upper = cleaned_text.upper()
        player_values_upper = [p.upper() for p in player_values]

        result = process.extractOne(cleaned_text_upper, player_values_upper, score_cutoff=fuzzy_threshold)
        if result:
            # Find the original case version
            original_index = player_values_upper.index(result[0])
            original_player = player_values[original_index]
            all_player_matches.append((original_player, result[1], "rapidfuzz_restricted"))
            if self.debug:
                print(f"[TextValidator] ✅ Restricted list match: '{cleaned_text}' -> '{original_player}' (score: {result[1]:.1f})")

        # 4. Correspondance floue avec PlayerProvider (tous joueurs) - SEULEMENT si pas de match restreint
        if not all_player_matches and self.player_provider:
            try:
                matches = self.player_provider.search_player(cleaned_text, threshold=threshold)
                if matches:
                    # Ajouter le score de correspondance pour le premier match
                    fuzzy_result = process.extractOne(cleaned_text, [matches[0]], score_cutoff=int(threshold * 100))
                    if fuzzy_result:
                        all_player_matches.append((matches[0], fuzzy_result[1], "provider_fuzzy"))
                        if self.debug:
                            print(f"[TextValidator] ✅ Full database match: '{cleaned_text}' -> '{matches[0]}' (score: {fuzzy_result[1]:.1f})")
            except Exception as e:
                if self.debug:
                    print(f"[TextValidator] ⚠️ Error in player fuzzy search: {e}")

        # 5. Enhanced fuzzy matching for partial names (OCR artifacts)
        if not all_player_matches and len(cleaned_text) >= 3:
            # Try matching against partial player names (substring matching)
            partial_matches = []
            for player in player_values:
                player_upper = player.upper()
                text_upper = cleaned_text.upper()

                # Check if cleaned text is contained in player name or vice versa
                if text_upper in player_upper or player_upper in text_upper:
                    # Calculate similarity score manually
                    similarity = max(len(text_upper) / len(player_upper), len(player_upper) / len(text_upper)) * 100
                    if similarity >= 40:  # Lower threshold for partial matches
                        partial_matches.append((player, similarity, "partial"))

            if partial_matches:
                # Take best partial match
                best_partial = max(partial_matches, key=lambda x: x[1])
                all_player_matches.append(best_partial)
                if self.debug:
                    print(f"[TextValidator] 🎯 Partial name match: '{cleaned_text}' -> '{best_partial[0]}' (score: {best_partial[1]:.1f})")

        # 6. Try reverse fuzzy matching (player names against cleaned text)
        if not all_player_matches and len(cleaned_text) >= 4:
            # For complex OCR like "ZETAKAKERU", try matching each player against the full string
            reverse_matches = []
            for player in player_values:
                reverse_result = process.extractOne(player, [cleaned_text], score_cutoff=40)
                if reverse_result:
                    reverse_matches.append((player, reverse_result[1], "reverse_fuzzy"))

            if reverse_matches:
                best_reverse = max(reverse_matches, key=lambda x: x[1])
                all_player_matches.append(best_reverse)
                if self.debug:
                    print(f"[TextValidator] 🔄 Reverse fuzzy match: '{cleaned_text}' -> '{best_reverse[0]}' (score: {best_reverse[1]:.1f})")

        # 7. Sélectionner le meilleur match en priorisant la cohérence personnage
        all_matches = character_consistent_matches + all_player_matches

        if all_matches:
            # Appliquer un bonus aux matches cohérents avec le personnage
            scored_matches = []
            for match_name, score, match_type in all_matches:
                adjusted_score = score

                # Bonus pour cohérence personnage (+20 points)
                if match_type == "character_consistent":
                    adjusted_score += 20
                # Léger malus pour incohérence (-10 points max)
                elif context_character and self.player_provider:
                    try:
                        is_consistent = self.player_provider.validate_player_character_combination(
                            match_name, context_character
                        )
                        if not is_consistent:
                            adjusted_score -= 10
                            if self.debug:
                                expected_char = self.player_provider.get_player_main_character(match_name)
                                print(f"[TextValidator] ⚠️ Player-character mismatch: '{match_name}' "
                                      f"mains '{expected_char}' but detected with '{context_character}' "
                                      f"(score penalty: {score:.1f} -> {adjusted_score:.1f})")
                    except Exception:
                        pass

                scored_matches.append((match_name, adjusted_score, match_type))

            # Prendre le meilleur match ajusté
            best_match = max(scored_matches, key=lambda x: x[1])
            match_name, final_score, match_type = best_match

            if self.debug:
                print(f"[TextValidator] ✅ Best player match: '{raw_text}' -> '{match_name}' "
                      f"(final score: {final_score:.1f}, type: {match_type})")

            return match_name

        # 8. Rejet - retourner texte original nettoyé
        if self.debug:
            print(f"[TextValidator] ❌ Player text rejected: '{raw_text}' (no match in known players)")
        return cleaned_text

    def validate_text(self, raw_text: str, expected_values: Optional[List[str]] = None,
                     fuzzy_score_threshold: int = 60, extract_digits: bool = False) -> str:
        """
        API générique pour valider un texte OCR contre une liste de valeurs attendues.

        Args:
            raw_text: Texte brut de l'OCR
            expected_values: Liste des valeurs valides attendues (optionnel)
            fuzzy_score_threshold: Seuil pour correspondance floue (0-100)
            extract_digits: Si True, extrait automatiquement les chiffres du texte

        Returns:
            Texte validé ou chaîne vide si invalide

        Examples:
            # Timer validation
            validate_text("89", expected_values=["00", "01", ..., "99"])

            # Character validation
            validate_text("RYU", expected_values=["RYU", "CHUN-LI", "KEN"])

            # Custom validation
            validate_text("HIGH", expected_values=["HIGH", "MEDIUM", "LOW"])
        """
        if not raw_text or not raw_text.strip():
            return ""

        cleaned_text = raw_text.strip().upper()

        if self.debug:
            expected_count = len(expected_values) if expected_values else 0
            print(f"[TextValidator] 🔍 Generic validation: '{raw_text}' -> '{cleaned_text}' "
                  f"(against {expected_count} expected values)")

        # Si pas de contraintes, retourner le texte nettoyé
        if not expected_values:
            if self.debug:
                print(f"[TextValidator] ℹ️ No constraints, returning cleaned text: '{cleaned_text}'")
            return cleaned_text

        # 1. Correspondance exacte (cas idéal)
        if cleaned_text in expected_values:
            if self.debug:
                print(f"[TextValidator] ✅ Exact match: '{cleaned_text}'")
            return cleaned_text

        # 2. Extraction des chiffres si demandée (pour timers notamment)
        if extract_digits:
            digits = ''.join(filter(str.isdigit, cleaned_text))
            if digits:
                # Formater sur 2 chiffres si nécessaire pour timers
                if len(digits) == 1:
                    digits = '0' + digits
                elif len(digits) > 2:
                    digits = digits[:2]

                if digits in expected_values:
                    if self.debug:
                        print(f"[TextValidator] ✅ Digits extracted: '{raw_text}' -> '{digits}'")
                    return digits

        # 3. Correspondance floue avec rapidfuzz
        result = process.extractOne(cleaned_text, expected_values, score_cutoff=fuzzy_score_threshold)
        if result:
            best_match, score, _ = result
            if self.debug:
                print(f"[TextValidator] ✅ Fuzzy match: '{raw_text}' -> '{best_match}' (score: {score:.1f})")
            return best_match

        # 4. Rejet
        if self.debug:
            print(f"[TextValidator] ❌ Text rejected: '{raw_text}' (no match in expected values)")
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
        if "timer_value" in frame_data:
            validated_frame["timer_value"] = self.validate_timer(
                frame_data["timer_value"]
            )

        if "character1" in frame_data:
            validated_frame["character1"] = self.validate_character(
                frame_data["character1"]
            )

        if "character2" in frame_data:
            validated_frame["character2"] = self.validate_character(
                frame_data["character2"]
            )

        # Valider les noms de joueurs avec contexte des personnages et liste restreinte
        if "player1" in frame_data:
            context_char = validated_frame.get("character1", "")
            validated_frame["player1"] = self.validate_player(
                frame_data["player1"],
                context_character=context_char
            )

        if "player2" in frame_data:
            context_char = validated_frame.get("character2", "")
            validated_frame["player2"] = self.validate_player(
                frame_data["player2"],
                context_character=context_char
            )

        # Préserver les autres champs tels quels (timestamp, etc.)
        return validated_frame

    def validate_frames_batch(
        self, frames_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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
            print("[TextValidator] ✅ Batch validation completed")

        return validated_frames

    def suggest_players_for_character(self, character_name: str, limit: int = 5) -> List[str]:
        """
        Suggère des joueurs probables basés sur le personnage détecté.

        Args:
            character_name: Nom du personnage détecté
            limit: Nombre maximum de suggestions

        Returns:
            Liste des joueurs qui jouent ce personnage
        """
        if not self.player_provider or not character_name:
            return []

        try:
            players = self.player_provider.find_players_by_character(character_name)
            return players[:limit]
        except Exception as e:
            if self.debug:
                print(f"[TextValidator] ⚠️ Error getting player suggestions for {character_name}: {e}")
            return []

    def enhance_player_detection_with_character_context(
        self, frames_data: List[Dict[str, Any]], confidence_threshold: float = 0.8
    ) -> List[Dict[str, Any]]:
        """
        Améliore la détection des joueurs en utilisant le contexte des personnages.

        Cette méthode post-traite les frames validées pour améliorer la précision
        des noms de joueurs en se basant sur les correspondances joueur-personnage connues.

        Args:
            frames_data: Frames déjà validées
            confidence_threshold: Seuil de confiance pour suggérer automatiquement

        Returns:
            Frames avec détection améliorée des joueurs
        """
        if not self.player_provider:
            return frames_data

        enhanced_frames = []

        # Analyser les patterns joueur-personnage dans toutes les frames
        character_player_patterns = self._analyze_character_player_patterns(frames_data)

        for frame in frames_data:
            enhanced_frame = frame.copy()

            # Améliorer player1 avec character1
            char1 = frame.get('character1', '')
            player1 = frame.get('player1', '')

            if char1:
                if not player1:
                    # Pas de joueur détecté -> suggérer le plus probable
                    suggested = self._suggest_most_likely_player(char1, character_player_patterns)
                    if suggested and self.debug:
                        print(f"[TextValidator] 💡 Auto-suggestion for {char1}: {suggested}")
                        enhanced_frame['player1'] = suggested
                elif player1:
                    # Re-valider avec contexte personnage pour améliorer la précision
                    improved = self.validate_player(
                        player1,
                        context_character=char1,
                        threshold=0.4
                    )
                    if improved and improved != player1:
                        if self.debug:
                            print(f"[TextValidator] 🔧 Player1 improved: '{player1}' -> '{improved}' (with {char1} context)")
                        enhanced_frame['player1'] = improved

            # Améliorer player2 avec character2
            char2 = frame.get('character2', '')
            player2 = frame.get('player2', '')

            if char2:
                if not player2:
                    suggested = self._suggest_most_likely_player(char2, character_player_patterns)
                    if suggested and self.debug:
                        print(f"[TextValidator] 💡 Auto-suggestion for {char2}: {suggested}")
                        enhanced_frame['player2'] = suggested
                elif player2:
                    improved = self.validate_player(
                        player2,
                        context_character=char2,
                        threshold=0.4
                    )
                    if improved and improved != player2:
                        if self.debug:
                            print(f"[TextValidator] 🔧 Player2 improved: '{player2}' -> '{improved}' (with {char2} context)")
                        enhanced_frame['player2'] = improved

            enhanced_frames.append(enhanced_frame)

        return enhanced_frames

    def _analyze_character_player_patterns(self, frames_data: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
        """
        Analyse les patterns joueur-personnage dans les frames pour détecter les associations fréquentes.

        Returns:
            Dict[character] -> Dict[player] -> count
        """
        patterns = {}

        for frame in frames_data:
            char1 = frame.get('character1', '').strip()
            player1 = frame.get('player1', '').strip()
            char2 = frame.get('character2', '').strip()
            player2 = frame.get('player2', '').strip()

            # Compter les associations character1 -> player1
            if char1 and player1:
                if char1 not in patterns:
                    patterns[char1] = {}
                patterns[char1][player1] = patterns[char1].get(player1, 0) + 1

            # Compter les associations character2 -> player2
            if char2 and player2:
                if char2 not in patterns:
                    patterns[char2] = {}
                patterns[char2][player2] = patterns[char2].get(player2, 0) + 1

        return patterns

    def _suggest_most_likely_player(self, character: str, patterns: Dict[str, Dict[str, int]]) -> str:
        """
        Suggère le joueur le plus probable pour un personnage basé sur les patterns détectés.
        """
        if character not in patterns:
            # Pas de pattern détecté -> utiliser mainCharacter database
            suggestions = self.suggest_players_for_character(character, limit=1)
            return suggestions[0] if suggestions else ""

        # Prendre le joueur le plus fréquent pour ce personnage
        player_counts = patterns[character]
        if player_counts:
            most_frequent = max(player_counts.items(), key=lambda x: x[1])
            return most_frequent[0]

        return ""

    def get_validation_stats(
        self,
        original_frames: List[Dict[str, Any]],
        validated_frames: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calcule des statistiques de validation pour analyse.

        Args:
            original_frames: Frames avant validation
            validated_frames: Frames après validation

        Returns:
            Dictionnaire avec statistiques de validation
        """
        stats = {
            "total_frames": len(original_frames),
            "timer_validated": 0,
            "character1_validated": 0,
            "character2_validated": 0,
            "timer_rejected": 0,
            "character1_rejected": 0,
            "character2_rejected": 0,
        }

        for orig, valid in zip(original_frames, validated_frames):
            # Timer
            if orig.get("timer_value") and valid.get("timer_value"):
                stats["timer_validated"] += 1
            elif orig.get("timer_value") and not valid.get("timer_value"):
                stats["timer_rejected"] += 1

            # Character1
            if orig.get("character1") and valid.get("character1"):
                stats["character1_validated"] += 1
            elif orig.get("character1") and not valid.get("character1"):
                stats["character1_rejected"] += 1

            # Character2
            if orig.get("character2") and valid.get("character2"):
                stats["character2_validated"] += 1
            elif orig.get("character2") and not valid.get("character2"):
                stats["character2_rejected"] += 1

        # Calculer les taux
        if stats["total_frames"] > 0:
            stats["timer_validation_rate"] = (
                stats["timer_validated"] / stats["total_frames"]
            )
            stats["character1_validation_rate"] = (
                stats["character1_validated"] / stats["total_frames"]
            )
            stats["character2_validation_rate"] = (
                stats["character2_validated"] / stats["total_frames"]
            )

        return stats

    # ==========================================
    # TEMPORAL INTERPOLATION METHODS
    # ==========================================

    def interpolate_frames_temporal(
        self, frames_data: List[Dict[str, Any]], window_size: int = 5
    ) -> List[Dict[str, Any]]:
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
                print(
                    f"[TextValidator] ⚠️ Trop peu de frames ({len(frames_data)}) pour interpolation"
                )
            return frames_data

        # Assurer fenêtre impaire pour avoir un centre
        if window_size % 2 == 0:
            window_size += 1

        if self.debug:
            print(
                f"[TextValidator] 🔄 Interpolation temporelle sur {len(frames_data)} frames (fenêtre: {window_size})"
            )

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
            interpolated_frame["timer_value"] = self._interpolate_timer_window(
                window, center_index=half_window
            )

            # Character interpolation
            interpolated_frame["character1"] = self._interpolate_character_window(
                window, "character1", center_index=half_window
            )
            interpolated_frame["character2"] = self._interpolate_character_window(
                window, "character2", center_index=half_window
            )

            interpolated_frames[i] = interpolated_frame

        if self.debug:
            changes_count = sum(
                1
                for orig, interp in zip(frames_data, interpolated_frames)
                if orig != interp
            )
            print(f"[TextValidator] ✅ Interpolation: {changes_count} frames modifiées")

        return interpolated_frames

    def _interpolate_timer_window(
        self, window: List[Dict[str, Any]], center_index: int
    ) -> str:
        """
        Interpole la valeur timer en utilisant le contexte de la fenêtre.

        Stratégies :
        1. Validation SF6 : timer doit être décroissant dans un round
        2. Voting system si plusieurs valeurs cohérentes
        3. Extrapolation linéaire si pattern clair
        """
        center_frame = window[center_index]
        current_timer = center_frame.get("timer_value", "")

        # Extraire toutes les valeurs timer de la fenêtre
        timer_values = []
        for frame in window:
            timer_str = frame.get("timer_value", "")
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
        interpolated = self._interpolate_timer_from_neighbors(
            timer_values, center_index
        )
        if interpolated:
            if self.debug:
                print(
                    f"[TextValidator] 🕐 Timer interpolé: '{current_timer}' -> '{interpolated}'"
                )
            return interpolated

        # Voting system en dernier recours
        return self._vote_timer_window(window)

    def _interpolate_character_window(
        self, window: List[Dict[str, Any]], field_name: str, center_index: int
    ) -> str:
        """
        Interpole un champ character en utilisant voting + distance de Levenshtein.
        """
        center_frame = window[center_index]
        current_char = center_frame.get(field_name, "")

        # Extraire valeurs non-vides de la fenêtre
        char_values = []
        for frame in window:
            char_val = frame.get(field_name, "").strip()
            if char_val:
                char_values.append(char_val)

        if not char_values:
            return current_char

        # Si valeur centrale existe, vérifier cohérence avec rapidfuzz
        if current_char:
            best_neighbor = self._find_closest_character_neighbor(
                current_char, char_values
            )
            if best_neighbor and best_neighbor != current_char:
                # Vérifier distance avec rapidfuzz
                distance_score = process.extractOne(current_char, [best_neighbor])
                if distance_score and distance_score[1] >= 80:  # score >= 80%
                    if self.debug:
                        print(
                            f"[TextValidator] 👤 Character corrigé: '{current_char}' -> '{best_neighbor}' (score: {distance_score[1]:.1f})"
                        )
                    return best_neighbor

        # Voting system sur fenêtre
        return self._vote_character_window(window, field_name)

    def _is_timer_coherent_in_sequence(
        self, timer_values: List[tuple], center_index: int
    ) -> bool:
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
                    actual_diff = abs(center_val - neighbor_val)
                    if actual_diff > 10:  # Écart trop important
                        return False
        return True

    def _interpolate_timer_from_neighbors(
        self, timer_values: List[tuple], center_index: int
    ) -> Optional[str]:
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
            timer_val = frame.get("timer_value", "").strip()
            if timer_val and timer_val.isdigit() and len(timer_val) <= 2:
                timer_votes[timer_val] = timer_votes.get(timer_val, 0) + 1

        if timer_votes:
            # Retourner valeur avec le plus de votes
            winner = max(timer_votes.items(), key=lambda x: x[1])
            return winner[0]

        return ""

    def _vote_character_window(
        self, window: List[Dict[str, Any]], field_name: str
    ) -> str:
        """Voting system pour character : valeur la plus fréquente avec validation."""
        char_votes = {}

        for frame in window:
            char_val = frame.get(field_name, "").strip()
            if char_val and self.character_names and char_val in self.character_names:
                char_votes[char_val] = char_votes.get(char_val, 0) + 1

        if char_votes:
            winner = max(char_votes.items(), key=lambda x: x[1])
            return winner[0]

        return ""

    def _find_closest_character_neighbor(
        self, current_char: str, neighbors: List[str]
    ) -> Optional[str]:
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
