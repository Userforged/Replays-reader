#!/usr/bin/env python3
"""
Script de déduction des matches et rounds Street Fighter 6.

Analyse un fichier JSON de résultats d'analyse pour identifier automatiquement 
le début des matches et rounds basé sur l'évolution des valeurs de timer.

Usage:
    python deduct.py input_results.json [--output output.json] [--debug]
    python deduct.py input_results.json --player-list evo_players.json
    python deduct.py input_results.json --min-round-duration 90 --timer-tolerance 0.4

Options principales:
    --player-list FILE    Fichier JSON avec liste restreinte de joueurs pour améliorer la précision
    --debug              Mode debug avec logs détaillés  
    --min-round-duration Durée minimum d'un round en secondes (défaut: 120)
    --min-match-gap      Gap minimum entre matches en secondes (défaut: 120)
    --timer-tolerance    Tolérance pour timer manquant 0.0-1.0 (défaut: 0.3)
"""

import json
import os
import argparse
from src.match_deductor import MatchDeductor


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
    
    Format de sortie: "HH:MM:SS Player1 (Character1) VS Player2 (Character2)"
    
    Args:
        matches_data: Données de résultats contenant les matches
        
    Returns:
        Liste des lignes formatées
    """
    lines = []
    
    matches = matches_data.get("matches", [])
    
    for match in matches:
        # Pour chaque match, on liste tous ses sets
        sets = match.get("sets", [])
        
        for set_data in sets:
            timestamp = set_data.get("start_time", "00:00:00")
            
            # Formater les noms de personnages : première lettre majuscule, reste minuscule
            char1_raw = set_data.get("character1", "Unknown")
            char2_raw = set_data.get("character2", "Unknown")
            
            # Gérer les cas spéciaux comme "M. BISON", "E. HONDA", "DEE JAY"
            char1 = format_character_name(char1_raw)
            char2 = format_character_name(char2_raw)
            
            # Noms des joueurs depuis les données du match
            player1 = match.get('player1', 'Player1')
            player2 = match.get('player2', 'Player2')
            
            line = f"{timestamp} {player1} ({char1}) VS {player2} ({char2})"
            lines.append(line)
    
    return lines


def enrich_results_with_metadata(results: dict, input_json_path: str, frames_data: list) -> dict:
    """
    Enrichit les résultats avec les métadonnées du fichier source.
    
    Args:
        results: Résultats de MatchDeductor
        input_json_path: Chemin du fichier .export.json
        frames_data: Données des frames pour calculer la durée
    
    Returns:
        Résultats enrichis avec métadonnées
    """
    # Extraire le nom de la vidéo source
    video_name = extract_video_name_from_path(input_json_path)
    
    # Calculer la durée de la vidéo
    video_duration = calculate_video_duration(frames_data)
    
    # Renommer "stats" en "info" et ajouter métadonnées
    if 'stats' in results:
        info = results.pop('stats')  # Récupérer et supprimer 'stats'
    else:
        info = {}
    
    # Ajouter les nouvelles métadonnées au début
    enriched_info = {
        'source_file': input_json_path,
        'video_name': video_name,
        'video_duration': video_duration,
        **info  # Ajouter les stats existantes après
    }
    
    results['info'] = enriched_info
    return results


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
            
        if not isinstance(data, list):
            raise ValueError("Le JSON doit contenir une liste de frames")
            
        print(f"✅ Chargement réussi: {len(data)} frames depuis {json_path}")
        return data
        
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON invalide: {e}")
    except Exception as e:
        raise ValueError(f"Erreur de lecture: {e}")


def save_deduction_results_txt(results: dict, output_path: str):
    """
    Sauvegarde les résultats de déduction dans un fichier TXT human-readable.
    
    Args:
        results: Résultats de la déduction
        output_path: Chemin de sortie
    """
    try:
        # Créer le répertoire de sortie si nécessaire
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        matches = results.get("matches", [])
        
        if not matches:
            # Cas où aucun match n'est détecté
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("# Aucun match détecté dans cette vidéo\n")
                f.write("# \n")
                f.write("# Causes possibles:\n")
                f.write("# - Vidéo sans gameplay Street Fighter 6\n")
                f.write("# - Détection OCR insuffisante (timer/personnages)\n")
                f.write("# - Paramètres de détection trop stricts\n")
                f.write("# \n")
                f.write("# Essayez d'ajuster les paramètres avec --debug pour plus d'infos\n")
            
            print(f"📄 Fichier TXT créé (aucun match): {output_path}")
            return
        
        # Convertir au format human-readable
        lines = format_matches_to_human_readable(results)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for line in lines:
                f.write(line + '\n')
            
        print(f"📄 Résultats TXT sauvegardés: {output_path}")
        print(f"📊 {len(lines)} sets détectés")
        
    except Exception as e:
        print(f"❌ Erreur sauvegarde TXT: {e}")
        raise


def save_deduction_results_json(results: dict, output_path: str):
    """
    Sauvegarde les résultats de déduction dans un fichier JSON détaillé.
    
    Args:
        results: Résultats de la déduction
        output_path: Chemin de sortie
    """
    try:
        # Créer le répertoire de sortie si nécessaire
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
            
        print(f"📄 Résultats JSON sauvegardés: {output_path}")
        
    except Exception as e:
        print(f"❌ Erreur sauvegarde JSON: {e}")
        raise


def print_analysis_summary(results: dict):
    """Affiche un résumé de l'analyse."""
    info = results.get('info', {})
    matches = results.get('matches', [])
    
    print(f"\n📊 Résumé de l'analyse:")
    print(f"═" * 50)
    
    # Métadonnées vidéo
    video_name = info.get('video_name', 'Unknown')
    video_duration = info.get('video_duration', 'Unknown')
    print(f"🎬 Vidéo: {video_name}")
    print(f"⏱️  Durée: {video_duration}")
    
    # Statistiques générales
    print(f"📹 Frames analysées: {info.get('total_frames_analyzed', 0)}")
    print(f"🔍 Frames avec timer: {info.get('frames_with_valid_timer', 0)} "
          f"({info.get('timer_detection_rate', 0):.1%})")
    print(f"🎮 Matches détectés: {info.get('total_matches_detected', 0)}")
    print(f"📦 Sets détectés: {info.get('total_sets_detected', 0)}")
    print(f"🥊 Rounds détectés: {info.get('total_rounds_detected', 0)}")
    
    if matches:
        avg_sets = info.get('avg_sets_per_match', 0)
        avg_rounds = info.get('avg_rounds_per_set', 0)
        print(f"📈 Moyenne sets/match: {avg_sets:.1f}")
        print(f"📈 Moyenne rounds/set: {avg_rounds:.1f}")
    
    # Détail des matches
    if matches:
        print(f"\n🏆 Détail des matches:")
        for i, match in enumerate(matches):
            sets = match.get('sets', [])
            player1 = match.get('player1', '')
            player2 = match.get('player2', '')
            total_rounds = match.get('total_rounds', 0)
            winner = match.get('winner')
            
            # En-tête du match - format enrichi
            match_header = f"  Match {i+1}: {match['start_time']}"
            if player1 and player2:
                match_header += f" {player1} VS {player2}"
            if winner:
                match_header += f" (Winner: {winner})"
            match_header += f" - {len(sets)} sets, {total_rounds} rounds"
            
            print(match_header)
            
            # Afficher chaque set avec toutes les informations
            for j, set_data in enumerate(sets):
                char1 = set_data.get('character1', '')
                char2 = set_data.get('character2', '')
                rounds_count = set_data.get('rounds_count', 0)
                set_player1 = set_data.get('player1', '')
                set_player2 = set_data.get('player2', '')
                set_start = set_data.get('start_time', '')
                
                # Utiliser les joueurs du set s'ils existent, sinon ceux du match
                display_player1 = set_player1 if set_player1 else player1
                display_player2 = set_player2 if set_player2 else player2
                
                # Format enrichi : "Set X: TIME Player1 (Character1) VS Player2 (Character2) (N rounds)"
                set_line = f"    Set {j+1}: {set_start}"
                if display_player1 and display_player2:
                    set_line += f" {display_player1} ({char1}) VS {display_player2} ({char2})"
                else:
                    set_line += f" {char1} vs {char2}"
                set_line += f" ({rounds_count} rounds)"
                
                print(set_line)
                
                # Optionnel : afficher les rounds individuels si debug activé
                if False:  # Changez en True pour afficher les rounds
                    rounds = set_data.get('rounds', [])
                    for k, round_data in enumerate(rounds):
                        round_start = round_data.get('start_time', '')
                        confidence = round_data.get('confidence', 0)
                        print(f"      Round {k+1}: {round_start} (confidence: {confidence:.2f})")


def main():
    """Fonction principale du script."""
    parser = argparse.ArgumentParser(
        description='Déduit les matches et rounds depuis un JSON d\'analyse SF6',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python deduct.py EVODay2_results.json
  python deduct.py EVODay2_results.json --output matches.txt
  python deduct.py EVODay2_results.json --debug --min-round-duration 90
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
        '--min-round-duration',
        type=int,
        default=120,
        help='Durée minimum d\'un round en secondes (défaut: 120)'
    )
    
    parser.add_argument(
        '--min-match-gap',
        type=int, 
        default=120,
        help='Gap minimum entre matches en secondes (défaut: 120)'
    )
    
    parser.add_argument(
        '--timer-tolerance',
        type=float,
        default=0.3,
        help='Tolérance pour timer manquant (0.0-1.0, défaut: 0.3)'
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
        
        # Configuration simplifiée des champs de sortie
        output_config = {
            'match_fields': ['start_time', 'sets_count', 'player1', 'player2', 'winner'],
            'include_rounds_in_matches': False,
            'round_fields': ['start_time', 'confidence']
        }
        
        # Configurer le déducteur
        deductor = MatchDeductor(
            min_round_duration_seconds=args.min_round_duration,
            min_match_gap_seconds=args.min_match_gap,
            timer_tolerance_ratio=args.timer_tolerance,
            output_fields=output_config,
            debug=args.debug,
            restricted_players_file=args.player_list if args.player_list != 'players.json' else None
        )
        
        # Analyser
        print(f"🔍 Analyse en cours...")
        if args.debug:
            print(f"  Paramètres: round_min={args.min_round_duration}s, "
                  f"match_gap={args.min_match_gap}s, "
                  f"tolérance={args.timer_tolerance}")
        
        results = deductor.analyze_frames(frames_data)
        
        # Enrichir avec les métadonnées du fichier
        results = enrich_results_with_metadata(results, args.input_json, frames_data)
        
        # Sauvegarder en format TXT (par défaut)
        save_deduction_results_txt(results, args.output)
        
        # Sauvegarder aussi en JSON si mode debug
        if args.debug:
            json_output = args.output.replace('.matches.txt', '.matches.json')
            save_deduction_results_json(results, json_output)
        
        # Afficher résumé
        print_analysis_summary(results)
        
        print(f"\n✅ Analyse terminée avec succès!")
        
    except KeyboardInterrupt:
        print(f"\n⚠️ Analyse interrompue par l'utilisateur")
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