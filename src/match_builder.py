"""
Match Builder - Constructeur de structure SF6

Transforme les rounds détectés par WindowCollector en structure hiérarchique SF6 :
detected_rounds → Match/Set/Round models

Responsabilités :
1. Grouper les rounds en sets (même personnages)
2. Grouper les sets en matches (même joueurs)
3. Calculer les temps réels avec rétro-engineering
4. Détecter les gagnants et statistiques
"""

from typing import List, Dict
from datetime import datetime
import sys
import os

# Ajouter src au path pour import
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))
from models.sf6_models import Match, Set, Round, VideoAnalysis, calculate_real_start_time


class MatchBuilder:
    """
    Construit la structure hiérarchique SF6 à partir des rounds détectés.
    """

    def __init__(self, debug: bool = False):
        self.debug = debug

        # Paramètres configurables
        self.max_gap_between_rounds_seconds = 300  # 5 minutes max entre rounds d'un set
        self.max_gap_between_sets_seconds = 600    # 10 minutes max entre sets d'un match

    def build_video_analysis(self, detected_rounds: List[Dict], video_name: str,
                           video_duration: str, analysis_params: Dict) -> VideoAnalysis:
        """
        Point d'entrée principal : construit l'analyse complète d'une vidéo.

        Args:
            detected_rounds: Liste des rounds détectés par WindowCollector
            video_name: Nom de la vidéo analysée
            video_duration: Durée de la vidéo (format "HH:MM:SS")
            analysis_params: Paramètres utilisés pour l'analyse

        Returns:
            VideoAnalysis complète avec structure hiérarchique
        """
        if self.debug:
            print(f"🏗️  MatchBuilder - Construction de l'analyse pour {len(detected_rounds)} rounds")

        # Créer l'objet d'analyse principal
        analysis = VideoAnalysis(
            video_name=video_name,
            video_duration=video_duration,
            analysis_date=datetime.now().isoformat(),
            total_frames_analyzed=analysis_params.get('total_frames', 0),
            detection_method="window_based_with_models",
            parameters=analysis_params
        )

        # Étape 1 : Convertir les rounds détectés en objets Round
        round_objects = self._convert_detected_rounds(detected_rounds)

        # Étape 2 : Grouper les rounds en sets
        sets = self._group_rounds_into_sets(round_objects)

        # Étape 3 : Grouper les sets en matches
        matches = self._group_sets_into_matches(sets)

        # Étape 4 : Ajouter les matches à l'analyse
        for match in matches:
            analysis.add_match(match)

        if self.debug:
            print(f"✅ Construction terminée: {analysis.matches_count} matches, "
                  f"{analysis.sets_count} sets, {analysis.rounds_count} rounds")

        return analysis

    def _convert_detected_rounds(self, detected_rounds: List[Dict]) -> List[Round]:
        """
        Convertit les rounds détectés par WindowCollector en objets Round.
        Applique le rétro-engineering pour calculer les temps réels.
        """
        round_objects = []

        for i, round_data in enumerate(detected_rounds, 1):
            # Extraire les données
            detection_time = round_data.get('start_time', '00:00:00')
            detected_timer = round_data.get('timer_start', 99)
            end_time = round_data.get('end_time')
            timer_end = round_data.get('timer_end')
            frames_count = round_data.get('frames_count', 0)
            confidence = round_data.get('coherence_score', 1.0)

            # Calculer le temps réel de début avec rétro-engineering
            real_start_time = calculate_real_start_time(detection_time, detected_timer)

            # Calculer la durée si possible
            duration_seconds = None
            if end_time and detection_time:
                try:
                    start_dt = datetime.strptime(real_start_time, "%H:%M:%S")
                    end_dt = datetime.strptime(end_time, "%H:%M:%S")
                    duration_seconds = int((end_dt - start_dt).total_seconds())
                except ValueError:
                    pass

            # Créer l'objet Round
            round_obj = Round(
                round_number=i,  # Sera recalculé lors du groupement en sets
                start_time=real_start_time,
                end_time=end_time,
                duration_seconds=duration_seconds,
                timer_start=99,  # Toujours 99 après rétro-engineering
                timer_end=timer_end,
                frames_count=frames_count,
                confidence=confidence
            )

            # Stocker les données originales et validées pour accès ultérieur
            round_obj._original_data = round_data

            # Stocker aussi les données validées si présentes (noms joueurs normalisés)
            # Ces données proviennent du nettoyage OCR fait par WindowCollector
            if 'player1' in round_data or 'player2' in round_data:
                round_obj._validated_data = {
                    'player1': round_data.get('player1', ''),
                    'player2': round_data.get('player2', ''),
                    'character1': round_data.get('character1', ''),
                    'character2': round_data.get('character2', '')
                }

            round_objects.append(round_obj)

            if self.debug and i <= 3:  # Afficher les 3 premiers pour debug
                print(f"Round {i}: {detection_time} (timer {detected_timer}) → {real_start_time} (timer 99)")

        return round_objects

    def _group_rounds_into_sets(self, rounds: List[Round]) -> List[Set]:
        """
        Groupe les rounds en sets basé sur la continuité temporelle et les personnages.

        Un nouveau set commence quand :
        - Gap temporel > max_gap_between_rounds_seconds
        - Changement de personnages détecté
        """
        if not rounds:
            return []

        sets = []
        current_set = None

        for round_obj in rounds:
            # Récupérer les données de personnages depuis les données originales
            round_chars = getattr(round_obj, '_original_data', {})
            char1 = round_chars.get('character1', "Unknown")
            char2 = round_chars.get('character2', "Unknown")

            # Déterminer si on doit créer un nouveau set
            should_create_new_set = False

            if current_set is None:
                should_create_new_set = True
            else:
                # Vérifier changement de personnages
                chars_changed = (current_set.character1 != char1 or
                               current_set.character2 != char2)

                # Calculer gap temporel avec le dernier round du set courant
                gap_seconds = self._calculate_time_gap(
                    current_set.rounds[-1].start_time,
                    round_obj.start_time
                )

                if gap_seconds > self.max_gap_between_rounds_seconds or chars_changed:
                    should_create_new_set = True

            if should_create_new_set:
                # Finaliser le set précédent
                if current_set:
                    current_set.end_time = current_set.rounds[-1].end_time
                    sets.append(current_set)

                # Créer un nouveau set avec les personnages détectés
                current_set = Set(
                    set_number=len(sets) + 1,
                    character1=char1,
                    character2=char2,
                    start_time=round_obj.start_time,
                    rounds=[]
                )

            # Ajouter le round au set courant
            round_obj.round_number = len(current_set.rounds) + 1
            current_set.add_round(round_obj)

        # Finaliser le dernier set
        if current_set:
            current_set.end_time = current_set.rounds[-1].end_time
            sets.append(current_set)

        if self.debug:
            print(f"📦 Sets créés: {len(sets)}")
            for i, set_obj in enumerate(sets, 1):
                print(f"  Set {i}: {set_obj.rounds_count} rounds ({set_obj.start_time}) - "
                      f"{set_obj.character1} vs {set_obj.character2}")

        return sets

    def _group_sets_into_matches(self, sets: List[Set]) -> List[Match]:
        """
        Groupe les sets en matches basé sur la continuité temporelle et les joueurs.

        Un nouveau match commence quand :
        - Gap temporel > max_gap_between_sets_seconds
        - Changement de joueurs détecté
        """
        if not sets:
            return []

        matches = []
        current_match = None

        for set_obj in sets:
            # Récupérer les données de joueurs depuis le premier round du set
            # IMPORTANT: Utiliser les données validées au lieu des données brutes (_original_data)
            if set_obj.rounds:
                first_round = set_obj.rounds[0]
                # Utiliser les données validées (après nettoyage OCR par TextValidator)
                validated_data = getattr(first_round, '_validated_data', {})
                if validated_data:
                    player1 = validated_data.get('player1', "Unknown")
                    player2 = validated_data.get('player2', "Unknown")
                else:
                    # Fallback vers données originales si pas de validation disponible
                    round_players = getattr(first_round, '_original_data', {})
                    player1 = round_players.get('player1', "Unknown")
                    player2 = round_players.get('player2', "Unknown")
            else:
                player1 = player2 = "Unknown"

            # Déterminer si on doit créer un nouveau match
            should_create_new_match = False

            if current_match is None:
                should_create_new_match = True
            else:
                # Vérifier changement de joueurs
                players_changed = (current_match.player1 != player1 or
                                 current_match.player2 != player2)

                # Calculer gap temporel avec le dernier set du match courant
                gap_seconds = self._calculate_time_gap(
                    current_match.sets[-1].end_time or current_match.sets[-1].start_time,
                    set_obj.start_time
                )

                if gap_seconds > self.max_gap_between_sets_seconds or players_changed:
                    should_create_new_match = True

            if should_create_new_match:
                # Finaliser le match précédent
                if current_match:
                    current_match.end_time = current_match.sets[-1].end_time
                    matches.append(current_match)

                # Créer un nouveau match avec les joueurs détectés
                current_match = Match(
                    match_id=len(matches) + 1,
                    player1=player1,
                    player2=player2,
                    start_time=set_obj.start_time,
                    sets=[]
                )

            # Ajouter le set au match courant
            set_obj.set_number = len(current_match.sets) + 1
            current_match.add_set(set_obj)

        # Finaliser le dernier match
        if current_match:
            current_match.end_time = current_match.sets[-1].end_time
            matches.append(current_match)

        if self.debug:
            print(f"🎮 Matches créés: {len(matches)}")
            for i, match in enumerate(matches, 1):
                print(f"  Match {i}: {match.sets_count} sets, {match.total_rounds} rounds ({match.start_time}) - "
                      f"{match.player1} vs {match.player2}")

        return matches

    def _calculate_time_gap(self, time1: str, time2: str) -> int:
        """
        Calcule l'écart en secondes entre 2 timestamps HH:MM:SS.

        Returns:
            Nombre de secondes (positif si time2 > time1)
        """
        try:
            dt1 = datetime.strptime(time1, "%H:%M:%S")
            dt2 = datetime.strptime(time2, "%H:%M:%S")

            return int((dt2 - dt1).total_seconds())
        except (ValueError, TypeError):
            return 0