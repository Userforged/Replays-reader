#!/usr/bin/env python3
"""
Script de déduction des matches et rounds Street Fighter 6.

Analyse un fichier JSON de résultats d'analyse pour identifier automatiquement
le début des matches et rounds basé sur l'évolution des valeurs de timer.

Usage:
    python deduct.py input_results.json [--output output.json] [--debug]
    python deduct.py input_results.json --player-list evo_players.json

Options principales:
    --player-list FILE    Fichier JSON avec liste restreinte de joueurs pour améliorer la précision
    --debug              Mode debug avec logs détaillés
"""

import json
import os
import argparse
from src.windows.window_collector import WindowCollector
from src.match_builder import MatchBuilder


def format_character_name(name):
    """
    Formate un nom de personnage : première lettre majuscule, reste minuscule.
    Gère les cas spéciaux comme "M. BISON", "DEE JAY", etc.
    """
    if not name:
        return "Unknown"

    name = name.strip()

    # Cas spéciaux avec points ou espaces
    if "." in name or " " in name:
        # Séparer par espaces et traiter chaque partie
        parts = name.split()
        formatted_parts = []

        for part in parts:
            if "." in part:
                # Garder les points mais capitaliser : "M." reste "M."
                formatted_parts.append(part.upper())
            else:
                # Première lettre majuscule, reste minuscule
                formatted_parts.append(part.capitalize())

        return " ".join(formatted_parts)
    else:
        # Cas simple : première lettre majuscule, reste minuscule
        return name.capitalize()


def format_matches_to_human_readable(matches_data):
    """
    Convertit les données de matches en format human-readable.

    Règle des parenthèses : afficher (Character) seulement si le joueur
    utilise le même personnage pendant tout le match.

    Args:
        matches_data: Données de résultats contenant les matches

    Returns:
        Liste des lignes formatées
    """
    lines = []

    matches = matches_data.get("matches", [])

    for match in matches:
        # Analyser les changements de personnages dans le match
        sets = match.get("sets", [])

        # Collecter tous les personnages utilisés par chaque joueur
        player1_characters = set()
        player2_characters = set()

        for set_data in sets:
            char1 = set_data.get("character1", "").strip()
            char2 = set_data.get("character2", "").strip()

            if char1:
                player1_characters.add(char1)
            if char2:
                player2_characters.add(char2)

        # Déterminer si chaque joueur a un personnage constant
        player1_constant = len(player1_characters) <= 1
        player2_constant = len(player2_characters) <= 1

        # Obtenir le personnage représentatif pour chaque joueur
        player1_char = list(player1_characters)[0] if player1_characters else ""
        player2_char = list(player2_characters)[0] if player2_characters else ""

        # Générer les lignes pour chaque set
        for set_data in sets:
            timestamp = set_data.get("start_time", "00:00:00")

            # Noms des joueurs
            player1 = match.get('player1', 'Player1')
            player2 = match.get('player2', 'Player2')

            # Formater avec ou sans parenthèses selon les changements de personnages
            player1_display = f"{player1} ({format_character_name(player1_char)})" if player1_constant and player1_char else player1
            player2_display = f"{player2} ({format_character_name(player2_char)})" if player2_constant and player2_char else player2

            line = f"{timestamp} {player1_display} VS {player2_display}"
            lines.append(line)

    return lines


def extract_video_name_from_path(json_path: str) -> str:
    """
    Extrait le nom de la vidéo à partir du chemin du fichier .export.json

    Exemples:
        EVODay2.export.json → EVODay2
        path/to/MyVideo.export.json → MyVideo
        https_youtube_com_watch_v_ABC123.export.json → https_youtube_com_watch_v_ABC123
    """
    filename = os.path.basename(json_path)

    # Enlever l'extension .json
    if filename.endswith('.json'):
        filename = filename[:-5]

    # Enlever .export si présent
    if filename.endswith('.export'):
        filename = filename[:-7]

    return filename


def calculate_video_duration(frames_data: list) -> str:
    """
    Calcule la durée de la vidéo basée sur le premier et dernier timestamp.

    Args:
        frames_data: Liste des frames avec timestamps

    Returns:
        Durée au format "HH:MM:SS" ou "Unknown" si impossible à calculer
    """
    if not frames_data:
        return "Unknown"

    try:
        # Extraire les timestamps valides
        timestamps = []
        for frame in frames_data:
            timestamp = frame.get('timestamp', '')
            if timestamp and timestamp != '':
                timestamps.append(timestamp)

        if len(timestamps) < 2:
            return "Unknown"

        # Premier et dernier timestamp
        first_time = timestamps[0]
        last_time = timestamps[-1]

        # Convertir en secondes
        first_seconds = timestamp_to_seconds(first_time)
        last_seconds = timestamp_to_seconds(last_time)

        if first_seconds is None or last_seconds is None:
            return "Unknown"

        # Calculer la durée
        duration_seconds = last_seconds - first_seconds

        # Convertir en format HH:MM:SS
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60

        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    except Exception:
        return "Unknown"


def calculate_time_gap_seconds(time1: str, time2: str) -> int:
    """
    Calcule l'écart en secondes entre 2 timestamps HH:MM:SS.

    Returns:
        Nombre de secondes (positif si time2 > time1)
    """
    try:
        seconds1 = timestamp_to_seconds(time1)
        seconds2 = timestamp_to_seconds(time2)

        if seconds1 is None or seconds2 is None:
            return 0

        return seconds2 - seconds1
    except (ValueError, TypeError):
        return 0

def timestamp_to_seconds(timestamp: str) -> int:
    """
    Convertit un timestamp HH:MM:SS en secondes.

    Args:
        timestamp: Format "HH:MM:SS"

    Returns:
        Nombre de secondes ou None si erreur
    """
    try:
        parts = timestamp.split(':')
        if len(parts) != 3:
            return None

        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])

        return hours * 3600 + minutes * 60 + seconds

    except (ValueError, IndexError):
        return None


def load_analysis_results(json_path: str) -> list:
    """
    Charge les résultats d'analyse depuis un fichier JSON.

    Args:
        json_path: Chemin vers le fichier JSON

    Returns:
        Liste des frames analysées

    Raises:
        FileNotFoundError: Si le fichier n'existe pas
        ValueError: Si le JSON est invalide
    """
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Le fichier {json_path} n'existe pas")

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Support pour le nouveau format avec structure info/frames
        if isinstance(data, dict) and "frames" in data:
            frames_data = data["frames"]
            if not isinstance(frames_data, list):
                raise ValueError("La clé 'frames' doit contenir une liste")
            print(f"✅ Chargement réussi: {len(frames_data)} frames depuis {json_path}")
            return frames_data
        
        # Support pour l'ancien format (liste directe)
        elif isinstance(data, list):
            print(f"✅ Chargement réussi: {len(data)} frames depuis {json_path}")
            return data
        
        else:
            raise ValueError("Le JSON doit contenir une liste de frames ou un objet avec une clé 'frames'")

    except json.JSONDecodeError as e:
        raise ValueError(f"JSON invalide: {e}")
    except Exception as e:
        raise ValueError(f"Erreur de lecture: {e}")


def main():
    """Fonction principale du script."""
    parser = argparse.ArgumentParser(
        description='Déduit les matches et rounds depuis un JSON d\'analyse SF6',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python deduct.py EVODay2_results.json
  python deduct.py EVODay2_results.json --output matches.txt
  python deduct.py EVODay2_results.json --debug
        """
    )

    parser.add_argument(
        'input_json',
        help='Fichier JSON d\'analyse à traiter'
    )

    parser.add_argument(
        '-o', '--output',
        help='Fichier de sortie (défaut: [input].matches.txt)'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Activer le mode debug avec logs détaillés'
    )


    parser.add_argument(
        '--player-list',
        type=str,
        default='players.json',
        help='Fichier JSON contenant la liste des joueurs (défaut: players.json)'
    )

    args = parser.parse_args()

    # Générer le nom de sortie par défaut
    if not args.output:
        # Extraire le nom de base sans extension (.json, .export.json, etc.)
        base_name = os.path.splitext(args.input_json)[0]

        # Si le fichier se termine par .export, l'enlever aussi
        if base_name.endswith('.export'):
            base_name = base_name[:-7]  # Enlever '.export'

        args.output = f"{base_name}.matches.txt"

    try:
        print("🚀 Déduction des matches Street Fighter 6")
        print("=" * 50)

        # Charger les données
        frames_data = load_analysis_results(args.input_json)

        # Configurer les outils d'analyse
        restricted_file = args.player_list if args.player_list != 'players.json' else None
        collector = WindowCollector(
            debug=args.debug,
            restricted_players_file=restricted_file
        )

        match_builder = MatchBuilder(debug=args.debug)

        # Analyser
        print("🔍 Analyse en cours...")
        if args.debug:
            print(f"  Paramètres: timer_high={collector.timer_high_threshold}, "
                  f"gap={collector.gap_threshold}s, "
                  f"cohérence_min={collector.coherence_threshold}")

        # Étape 1 : Détection des rounds (modélisation frames → rounds)
        collector_results = collector.analyze_frames(frames_data)
        detected_rounds = collector_results.get('rounds', [])

        # Étape 2 : Construction de la structure SF6 (modélisation rounds → matches)
        video_name = os.path.basename(args.input_json).replace('.export.json', '')
        video_duration = "01:53:25"  # TODO: extraire depuis les métadonnées

        analysis_params = {
            'total_frames': len(frames_data),
            'frames_with_timer': collector_results.get('stats', {}).get('total_frames', 0),
            'timer_high_threshold': collector.timer_high_threshold,
            'gap_threshold': collector.gap_threshold,
            'coherence_threshold': collector.coherence_threshold
        }

        video_analysis = match_builder.build_video_analysis(
            detected_rounds, video_name, video_duration, analysis_params
        )

        # Sorties basées sur la nouvelle modélisation

        # Mode normal : fichier matches.txt (vue formatée)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(video_analysis.to_matches_txt())
        print(f"📄 Fichier matches.txt créé: {args.output}")

        # Mode debug : fichier JSON complet (structure détaillée)
        if args.debug:
            json_output = args.output.replace('.matches.txt', '.matches.json')
            with open(json_output, 'w', encoding='utf-8') as f:
                f.write(video_analysis.to_json())
            print(f"📄 Fichier JSON détaillé créé: {json_output}")


        # Afficher résumé basé sur la nouvelle modélisation
        print(f"\n📊 Résumé de l'analyse:")
        print("=" * 50)
        print(f"🎬 Vidéo: {video_analysis.video_name}")
        print(f"⏱️  Durée: {video_analysis.video_duration}")
        print(f"📹 Frames analysées: {video_analysis.total_frames_analyzed}")
        print(f"🔍 Frames avec timer: {video_analysis.frames_with_timer} ({video_analysis.timer_detection_rate:.1%})")
        print(f"🎮 Matches détectés: {video_analysis.matches_count}")
        print(f"📦 Sets détectés: {video_analysis.sets_count}")
        print(f"🥊 Rounds détectés: {video_analysis.rounds_count}")
        print(f"🔧 Méthode: {video_analysis.detection_method}")

        print("\n✅ Analyse terminée avec succès!")

    except KeyboardInterrupt:
        print("\n⚠️ Analyse interrompue par l'utilisateur")
        return 1
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())