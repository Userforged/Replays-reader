#!/usr/bin/env python3
"""
Interactive Street Fighter 6 replay analyzer.
Provides user-friendly CLI interface for video analysis configuration.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from export import analyze_video
from src.interactive_menu import InteractiveMenu


def main():
    """Run interactive Street Fighter 6 replay analysis."""
    try:
        # Check if we have a proper TTY for interactive mode
        import os

        if not os.isatty(0):
            print("⚠️ Mode interactif non disponible dans ce terminal.")
            print("📝 Configuration par défaut utilisée pour test:")
            config = {
                "source_type": "local",
                "source_path": "input/test_video.txt",  # Placeholder for testing
                "frames_per_minute": 12,
                "async_pipeline": False,
                "save_frames": False,
                "workers": 3,
            }
            print(f"   📁 Source: {config['source_path']}")
            print(f"   ⏱️ Frames/min: {config['frames_per_minute']}")
            print(f"   🚀 Pipeline: Séquentiel")
            print()
        else:
            # Run interactive configuration wizard
            menu = InteractiveMenu()
            config = menu.run_source_selection()  # Only source selection for now

            # ROI configuration loop (includes preview)
            resolution_thread = config.get("_resolution_thread")
            roi_choice = menu.roi_configuration_loop(config["source_path"], resolution_thread)

            # Handle final ROI choice
            if roi_choice in ["save_and_launch", "launch_no_save"]:
                if roi_choice == "save_and_launch":
                    print("💾 Export avec ROIs modifiées (gardées en mémoire)...")
                    # Keep modified ROIs in memory for export
                else:
                    print("🚀 Export avec ROIs par défaut (modifications ignorées)...")
                    # Reload original ROIs from file, discarding changes
                    menu.roi_manager.reload_from_file()
                
                # Configuration pour l'export
                export_config = {
                    "source_path": config["source_path"],
                    "frames_per_minute": 12,
                    "save_frames": False,
                    "async_pipeline": False,
                }
                
                print(f"📁 Source: {export_config['source_path']}")
                print(f"⏱️ Frames/minute: {export_config['frames_per_minute']}")
                print(f"🚀 Pipeline: Séquentiel")
                print("-" * 60)
                
                config = export_config
            elif roi_choice == "no":
                print("👍 Vous avez choisi de garder les ROIs actuels")
                print("🚀 Lancement de l'export avec les ROIs par défaut...\n")
                
                # Configuration par défaut pour l'export interactif
                export_config = {
                    "source_path": config["source_path"],
                    "frames_per_minute": 12,  # Valeur par défaut
                    "save_frames": False,     # Par défaut pas de sauvegarde frames
                    "async_pipeline": False,  # Pipeline séquentiel pour le moment
                }
                
                # Lancer l'export avec la configuration
                print(f"📁 Source: {export_config['source_path']}")
                print(f"⏱️ Frames/minute: {export_config['frames_per_minute']}")
                print(f"🚀 Pipeline: Séquentiel")
                print("-" * 60)
                
                # Utiliser la configuration d'export
                config = export_config

        # Extract configuration parameters
        source = config["source_path"]
        frames_per_minute = config.get("frames_per_minute", 12)
        save_frames = config.get("save_frames", False) 
        async_pipeline = config.get("async_pipeline", False)

        # Run pipeline (only sequential available for now)
        if async_pipeline:
            print(
                f"⚠️ Pipeline asynchrone pas encore disponible, utilisation du pipeline séquentiel"
            )

        print("🐌 Pipeline séquentiel")
        analyze_video(
            video_source=source,
            frames_per_minute=frames_per_minute,
            save_frames=save_frames,
        )

        print("\n✅ Analyse terminée avec succès!")
        print("\n📁 Fichiers générés:")

        # Find and display generated files
        from pathlib import Path

        output_dir = Path("output")
        export_files = list(output_dir.glob("*.export.json"))

        if export_files:
            latest_export = max(export_files, key=lambda p: p.stat().st_mtime)
            print(f"   📊 Export brut: {latest_export}")

            # Suggest match deduction
            print(f"\n💡 Étape suivante suggérée:")
            print(f"   python deduct.py {latest_export}")

    except KeyboardInterrupt:
        print("\n\n❌ Analyse interrompue par l'utilisateur.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur lors de l'analyse: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
