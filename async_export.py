#!/usr/bin/env python3
"""
Pipeline asynchrone optimisé pour l'analyse de vidéos YouTube SF6.

Utilise le nouveau pipeline direct avec générateurs async :
FrameExtractor.async_generate_frames() → ImageAnalyzer.async_analyze_frames() → AsyncJsonWriter

Usage:
    python async_export_new.py https://www.youtube.com/watch?v=VIDEO_ID --max-frames 100
"""
import asyncio
import argparse
import os
from datetime import datetime
from typing import Optional

from src.frame_extractor import FrameExtractor
from src.image_analyzer import ImageAnalyzer
from src.async_json_writer import AsyncJsonWriter
from src.preprocessing_steps import PreprocessingStep

OUTPUT_DIRECTORY = "output"


class AsyncPipelineOptimized:
    """Pipeline asynchrone optimisé utilisant les générateurs async directs."""
    
    def __init__(self, youtube_url: str, frames_per_minute: int = 12, 
                 manual_format: Optional[str] = None,
                 max_frames: Optional[int] = None):
        # Validation URL YouTube
        if not youtube_url.startswith(("https://www.youtube.com/", "https://youtube.com/")):
            raise ValueError("Seules les URLs YouTube sont supportées dans cette version simplifiée")
            
        self.youtube_url = youtube_url
        self.frames_per_minute = frames_per_minute
        self.manual_format = manual_format
        self.max_frames = max_frames
        
        # Compteurs et stats
        self.frames_analyzed = 0
        self.start_time = None
        
        # Components du pipeline
        self.frame_extractor = None
        self.image_analyzer = None
        self.json_writer = None
        self.json_output_path = None
        
    async def setup(self):
        """Initialisation asynchrone du pipeline."""
        print(f"🔧 Initialisation du pipeline asynchrone optimisé...")
        
        # Créer extracteur de frames
        self._create_frame_extractor()
        
        # Créer analyzer OCR 
        self._create_image_analyzer()
        
        # Configurer JSON writer
        await self._setup_json_writer()
        
        print(f"✅ Pipeline configuré: extraction → OCR → JSON streaming")
        
    def _create_frame_extractor(self):
        """Créer l'extracteur de frames pour YouTube."""
        print(f"📺 Configuration FrameExtractor...")
        self.frame_extractor = FrameExtractor(
            video_source=self.youtube_url,
            output_name=None,
            no_prompt=True,
            frames_per_minute=self.frames_per_minute,
            debug=False,
            manual_format=self.manual_format,
        )
        print(f"✅ FrameExtractor configuré avec buffer OpenCV")
        
    def _create_image_analyzer(self):
        """Créer l'analyzer OCR."""
        print(f"🔍 Configuration ImageAnalyzer...")
        self.image_analyzer = ImageAnalyzer(
            config_file="rois_config.json",
            characters_file="characters.json",
            debug=False,  # Pas de debug pour performance
        )
        print(f"✅ ImageAnalyzer configuré (TrOCR sync + EasyOCR async)")
        
    async def _setup_json_writer(self):
        """Configurer le JSON writer."""
        print(f"📝 Configuration AsyncJsonWriter...")
        
        # Chemin de sortie
        video_name = self.frame_extractor.output_name
        self.json_output_path = os.path.join(OUTPUT_DIRECTORY, f"{video_name}.export.json")
        
        # Créer répertoire si nécessaire
        os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)
        
        # Métadonnées info
        info_data = self._create_info_object()
        
        # Créer JSON writer
        self.json_writer = AsyncJsonWriter(self.json_output_path, info_data)
        print(f"✅ AsyncJsonWriter configuré: {self.json_output_path}")
        
    def _create_info_object(self):
        """Créer l'objet metadata pour le JSON YouTube."""
        info = {
            "video_name": self.frame_extractor.output_name,
            "source": self.youtube_url,
            "source_type": "youtube_stream",
        }
        
        # Titre vidéo YouTube si disponible
        if (hasattr(self.frame_extractor, 'resolved_source') and 
            self.frame_extractor.resolved_source.get("metadata", {}).get("title")):
            info["video_title"] = self.frame_extractor.resolved_source["metadata"]["title"]
        
        # Métadonnées d'analyse
        info.update({
            "analysis_date": datetime.now().strftime("%Y-%m-%d"),
            "frames_per_minute": self.frames_per_minute,
            "total_frames_analyzed": 0,  # Sera mis à jour par AsyncJsonWriter
            "analysis_parameters": {
                "max_frames": self.max_frames,
                "manual_format": self.manual_format,
                "async_pipeline_optimized": True,
                "hybrid_ocr": "TrOCR_sync_EasyOCR_async"
            }
        })
        
        return info
        
    async def _limited_frame_generator(self):
        """Générateur de frames avec limite optionnelle."""
        frame_count = 0
        async for frame, timestamp_sec, timestamp_str in self.frame_extractor.async_generate_frames():
            yield frame, timestamp_sec, timestamp_str
            frame_count += 1
            
            if frame_count % 10 == 0:
                print(f"📊 Frames extraites: {frame_count}")
                
            # Limite optionnelle
            if self.max_frames and frame_count >= self.max_frames:
                print(f"🛑 Limite atteinte: {self.max_frames} frames")
                break
                
    async def run(self):
        """Exécuter le pipeline asynchrone optimisé."""
        print(f"🚀 Démarrage pipeline asynchrone optimisé")
        self.start_time = datetime.now()
        
        # Initialiser
        await self.setup()
        
        print(f"🎬 Démarrage du pipeline direct: Frame → OCR → JSON")
        
        try:
            # Pipeline direct avec générateurs async chaînés
            frames_written = await self.json_writer.consume_and_write(
                self.image_analyzer.async_analyze_frames(
                    self._limited_frame_generator(),
                    rois_to_analyze=["timer", "character1", "character2", "player1", "player2"],
                    preprocessing=PreprocessingStep.STANDARD
                )
            )
            
            self.frames_analyzed = frames_written
            
        except Exception as e:
            print(f"❌ Erreur pipeline: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Stats finales
            if self.start_time:
                duration = datetime.now() - self.start_time
                print(f"⏱️ Durée totale: {duration.total_seconds():.1f}s")
                if self.frames_analyzed > 0:
                    print(f"🚀 Performance: {self.frames_analyzed/duration.total_seconds():.2f} frames/s")
                
        print(f"✅ Pipeline terminé: {self.json_output_path}")
        return self.json_output_path


async def analyze_youtube_video_optimized(youtube_url: str, frames_per_minute: int = 12, 
                                        manual_format: Optional[str] = None,
                                        max_frames: Optional[int] = None):
    """Analyser une vidéo YouTube SF6 avec le pipeline asynchrone optimisé."""
    pipeline = AsyncPipelineOptimized(
        youtube_url=youtube_url,
        frames_per_minute=frames_per_minute,
        manual_format=manual_format,
        max_frames=max_frames
    )
    
    return await pipeline.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyse asynchrone optimisée des données de match depuis une vidéo YouTube SF6"
    )
    parser.add_argument(
        "youtube_url", type=str, nargs="?",
        help="URL YouTube à analyser (ex: https://www.youtube.com/watch?v=VIDEO_ID)"
    )
    parser.add_argument(
        "--frames-per-minute", type=int, default=12,
        help="Nombre de frames à analyser par minute (défaut: 12)"
    )
    parser.add_argument(
        "-f", "--format", type=str, default=None,
        help="Format yt-dlp spécifique (ex: -f 299)"
    )
    parser.add_argument(
        "--max-frames", type=int, default=None,
        help="Nombre maximum de frames à analyser (défaut: illimité)"
    )
    
    args = parser.parse_args()
    
    if not args.youtube_url:
        print("❌ Erreur: Veuillez spécifier une URL YouTube à analyser.")
        print("💡 Exemples:")
        print("   python async_export_new.py https://www.youtube.com/watch?v=VIDEO_ID")
        print("   python async_export_new.py https://www.youtube.com/watch?v=VIDEO_ID --max-frames 50")
        parser.print_help()
    else:
        print(f"🎯 Analyse asynchrone optimisée YouTube: {args.youtube_url}")
        print(f"🔧 Configuration: Pipeline direct, {args.frames_per_minute} FPM")
            
        try:
            # Exécuter pipeline asynchrone optimisé
            output_path = asyncio.run(analyze_youtube_video_optimized(
                youtube_url=args.youtube_url,
                frames_per_minute=args.frames_per_minute,
                manual_format=args.format,
                max_frames=args.max_frames
            ))
            print(f"📄 Résultat: {output_path}")
            
        except Exception as e:
            print(f"❌ Erreur lors de l'analyse: {e}")
            print("💡 Vérifiez que l'URL YouTube est valide et accessible par yt-dlp")