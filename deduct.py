#!/usr/bin/env python3
"""
Script de déduction des matches et rounds Street Fighter 6.

Analyse un fichier JSON de résultats d'analyse pour identifier automatiquement 
le début des matches et rounds basé sur l'évolution des valeurs de timer.

Usage:
    python deduct.py input_results.json [--output output.json] [--debug]
"""

import json
import os
import argparse
from src.match_deductor import MatchDeductor


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


def save_deduction_results(results: dict, output_path: str):
    """
    Sauvegarde les résultats de déduction dans un fichier JSON.
    
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
            
        print(f"📄 Résultats sauvegardés: {output_path}")
        
    except Exception as e:
        print(f"❌ Erreur sauvegarde: {e}")
        raise


def print_analysis_summary(results: dict):
    """Affiche un résumé de l'analyse."""
    stats = results.get('stats', {})
    matches = results.get('matches', [])
    
    print(f"\n📊 Résumé de l'analyse:")
    print(f"═" * 50)
    
    # Statistiques générales
    print(f"📹 Frames analysées: {stats.get('total_frames_analyzed', 0)}")
    print(f"⏱️  Frames avec timer: {stats.get('frames_with_valid_timer', 0)} "
          f"({stats.get('timer_detection_rate', 0):.1%})")
    print(f"🎮 Matches détectés: {stats.get('total_matches_detected', 0)}")
    print(f"📦 Sets détectés: {stats.get('total_sets_detected', 0)}")
    print(f"🥊 Rounds détectés: {stats.get('total_rounds_detected', 0)}")
    
    if matches:
        avg_sets = stats.get('avg_sets_per_match', 0)
        avg_rounds = stats.get('avg_rounds_per_set', 0)
        print(f"📈 Moyenne sets/match: {avg_sets:.1f}")
        print(f"📈 Moyenne rounds/set: {avg_rounds:.1f}")
    
    # Détail des matches
    if matches:
        print(f"\n🏆 Détail des matches:")
        for i, match in enumerate(matches):
            sets = match.get('sets', [])
            print(f"  Match {i+1}: {match['start_time']} ({len(sets)} sets)")
            
            # Afficher chaque set
            for j, set_data in enumerate(sets):
                char1 = set_data.get('character1', '')
                char2 = set_data.get('character2', '')
                rounds_count = set_data.get('rounds_count', 0)
                print(f"    Set {j+1}: {char1} vs {char2} ({rounds_count} rounds)")


def main():
    """Fonction principale du script."""
    parser = argparse.ArgumentParser(
        description='Déduit les matches et rounds depuis un JSON d\'analyse SF6',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python deduct.py EVODay2_results.json
  python deduct.py EVODay2_results.json --output matches.json
  python deduct.py EVODay2_results.json --debug --min-round-duration 90
        """
    )
    
    parser.add_argument(
        'input_json',
        help='Fichier JSON d\'analyse à traiter'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='Fichier de sortie (défaut: [input].matches.json)'
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
    
    args = parser.parse_args()
    
    # Générer le nom de sortie par défaut
    if not args.output:
        # Extraire le nom de base sans extension (.json, .export.json, etc.)
        base_name = os.path.splitext(args.input_json)[0]
        
        # Si le fichier se termine par .export, l'enlever aussi
        if base_name.endswith('.export'):
            base_name = base_name[:-7]  # Enlever '.export'
        
        args.output = f"{base_name}.matches.json"
    
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
            debug=args.debug
        )
        
        # Analyser
        print(f"🔍 Analyse en cours...")
        if args.debug:
            print(f"  Paramètres: round_min={args.min_round_duration}s, "
                  f"match_gap={args.min_match_gap}s, "
                  f"tolérance={args.timer_tolerance}")
        
        results = deductor.analyze_frames(frames_data)
        
        # Sauvegarder
        save_deduction_results(results, args.output)
        
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