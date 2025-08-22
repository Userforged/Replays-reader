"""
Pipeline asynchrone optimisé pour l'analyse de vidéos YouTube SF6.

Utilise le nouveau pipeline direct avec générateurs async :
FrameExtractor → ImageAnalyzer → AsyncJsonWriter

Usage:
    python async_export.py https://www.youtube.com/watch?v=VIDEO_ID --max-frames 100
"""
import asyncio
import argparse
import os
from datetime import datetime
from typing import Dict, Any, Optional

from src.frame_extractor import FrameExtractor
from src.image_analyzer import ImageAnalyzer
from src.async_json_writer import AsyncJsonWriter
from src.preprocessing_steps import PreprocessingStep

OUTPUT_DIRECTORY = "output"


class AsyncPipeline:
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
        self.frame_queue = None
        self.ocr_queue = None
        
        # Objets partagés
        self.frame_extractor = None
        self.analyzers = []  # Un analyzer par worker OCR
        self.json_output_path = None
        
    async def setup(self):
        """Initialisation asynchrone du pipeline."""
        print(f"🔧 Initialisation du pipeline asynchrone...")
        
        # Créer les queues
        self.frame_queue = asyncio.Queue(maxsize=FRAME_QUEUE_SIZE)
        self.ocr_queue = asyncio.Queue(maxsize=OCR_QUEUE_SIZE)
        
        # Initialiser extracteur et analyzers
        self._create_frame_extractor()
        await self._create_ocr_analyzers()
        
        # Préparer sortie JSON
        self._setup_json_output()
        
        print(f"✅ Pipeline configuré: {self.ocr_workers} workers OCR, queues {FRAME_QUEUE_SIZE}/{OCR_QUEUE_SIZE}")
        
    def _create_frame_extractor(self):
        """Créer l'extracteur de frames pour YouTube."""
        self.frame_extractor = FrameExtractor(
            video_source=self.youtube_url,
            output_name=None,
            no_prompt=True,
            frames_per_minute=self.frames_per_minute,
            debug=False,
            manual_format=self.manual_format,
        )
        
    async def _create_ocr_analyzers(self):
        """Créer les analyzers OCR pour chaque worker."""
        print(f"🔄 Initialisation de {self.ocr_workers} analyzers OCR...")
        
        # Configuration des analyzers (mode async optimisé)
        analyzer_kwargs = {
            "config_file": "rois_config.json",
            "characters_file": "characters.json",
            "debug": False,  # Pas de debug en mode async pour performance
        }
        
        # Créer un seul analyzer en premier pour initialiser les modèles
        print(f"  🔄 Initialisation du premier analyzer (modèles partagés)...")
        first_analyzer = ImageAnalyzer(**analyzer_kwargs)
        self.analyzers.append(first_analyzer)
        print(f"  ✅ Premier analyzer initialisé")
        
        # Pour les autres workers, créer des analyzers qui partagent les modèles
        for i in range(1, self.ocr_workers):
            print(f"  🔄 Clonage analyzer {i+1}/{self.ocr_workers}...")
            # Créer un nouvel analyzer qui partage les modèles déjà initialisés
            analyzer = ImageAnalyzer(**analyzer_kwargs)
            # Partager les modèles OCR déjà chargés pour économiser mémoire et temps
            if first_analyzer.trocr_available:
                analyzer.trocr_processor = first_analyzer.trocr_processor
                analyzer.trocr_model = first_analyzer.trocr_model
                analyzer.trocr_device = first_analyzer.trocr_device
                analyzer.trocr_available = True
            if first_analyzer.easyocr_available:
                analyzer.easyocr_reader = first_analyzer.easyocr_reader
                analyzer.easyocr_available = True
            self.analyzers.append(analyzer)
            print(f"  ✅ Analyzer {i+1}/{self.ocr_workers} cloné")
            
    def _setup_json_output(self):
        """Configurer la sortie JSON."""
        video_name = self.frame_extractor.output_name
        self.json_output_path = os.path.join(OUTPUT_DIRECTORY, f"{video_name}.export.json")
        
        # Créer répertoire si nécessaire
        if not os.path.exists(OUTPUT_DIRECTORY):
            os.makedirs(OUTPUT_DIRECTORY)
            
        # Initialiser fichier JSON avec metadata
        info_data = self._create_info_object()
        initial_structure = {
            "info": info_data,
            "frames": []
        }
        
        with open(self.json_output_path, "w", encoding="utf-8") as f:
            json.dump(initial_structure, f, indent=2, ensure_ascii=False)
            
    def _create_info_object(self) -> Dict[str, Any]:
        """Créer l'objet metadata pour le JSON YouTube."""
        info = {
            "video_name": self.frame_extractor.output_name,
            "source": self.youtube_url,
            "source_type": "youtube_stream",
        }
        
        # Titre vidéo YouTube
        if (hasattr(self.frame_extractor, 'resolved_source') and 
            self.frame_extractor.resolved_source.get("metadata", {}).get("title")):
            info["video_title"] = self.frame_extractor.resolved_source["metadata"]["title"]
        
        # Métadonnées d'analyse
        info.update({
            "analysis_date": datetime.now().strftime("%Y-%m-%d"),
            "frames_per_minute": self.frames_per_minute,
            "total_frames_analyzed": 0,  # Sera mis à jour
            "analysis_parameters": {
                "max_frames": self.max_frames,
                "manual_format": self.manual_format,
                "async_pipeline": True,
                "ocr_workers": self.ocr_workers
            }
        })
        
        return info
        
    async def frame_producer(self):
        """Producer: Extrait les frames et les met dans la queue."""
        print(f"🎬 Démarrage extraction frames...")
        
        print(f"📺 Source YouTube: {self.youtube_url}")
        
        try:
            frame_count = 0
            async for frame_data in self._async_frame_generator():
                frame, timestamp_sec, timestamp_str = frame_data
                
                # Créer paquet de données pour OCR
                frame_packet = {
                    "frame": frame,
                    "timestamp_sec": timestamp_sec,
                    "timestamp_str": timestamp_str,
                    "frame_number": frame_count
                }
                
                # Mettre dans la queue (bloque si pleine)
                await self.frame_queue.put(frame_packet)
                frame_count += 1
                
                if frame_count % 10 == 0:
                    print(f"📊 Frames extraites: {frame_count}")
                    
                # Limite optionnelle
                if self.max_frames and frame_count >= self.max_frames:
                    print(f"🛑 Limite atteinte: {self.max_frames} frames")
                    break
                    
        except Exception as e:
            print(f"❌ Erreur extraction frames: {e}")
        finally:
            # Signal de fin pour les workers OCR
            for _ in range(self.ocr_workers):
                await self.frame_queue.put(None)
            print(f"✅ Extraction terminée: {frame_count} frames")
            
    async def _async_frame_generator(self):
        """Générateur asynchrone de frames utilisant le FrameExtractor async."""
        async for frame, timestamp_sec, timestamp_str in self.frame_extractor.async_generate_frames():
            yield frame, timestamp_sec, timestamp_str
            
    async def ocr_worker(self, worker_id: int):
        """Worker OCR: Traite les frames de la queue et génère les résultats."""
        analyzer = self.analyzers[worker_id]
        processed_count = 0
        
        print(f"🔍 Worker OCR {worker_id+1} démarré")
        
        try:
            while True:
                # Récupérer frame de la queue
                frame_packet = await self.frame_queue.get()
                
                # Signal de fin
                if frame_packet is None:
                    break
                    
                # Traitement OCR
                frame = frame_packet["frame"]
                timestamp_str = frame_packet["timestamp_str"]
                frame_number = frame_packet["frame_number"]
                
                # Analyse avec timeout pour éviter les blocages
                try:
                    ocr_results = await asyncio.wait_for(
                        self._async_analyze_frame(analyzer, frame),
                        timeout=30.0  # 30 secondes max par frame
                    )
                except asyncio.TimeoutError:
                    print(f"⚠️ Timeout OCR worker {worker_id+1} frame {frame_number}")
                    ocr_results = {}
                    
                # Créer données finales
                result_packet = {
                    "timestamp": timestamp_str,
                    "timer_value": ocr_results.get("timer", ""),
                    "character1": ocr_results.get("character1", ""),
                    "character2": ocr_results.get("character2", ""),
                    "player1": ocr_results.get("player1", ""),
                    "player2": ocr_results.get("player2", ""),
                    "frame_number": frame_number,
                    "worker_id": worker_id
                }
                
                # Envoyer résultat vers writer
                await self.ocr_queue.put(result_packet)
                processed_count += 1
                
                if processed_count % 5 == 0:
                    print(f"🔍 Worker {worker_id+1}: {processed_count} frames traitées")
                    
        except Exception as e:
            print(f"❌ Erreur worker OCR {worker_id+1}: {e}")
        finally:
            print(f"✅ Worker OCR {worker_id+1} terminé: {processed_count} frames")
            
    async def _async_analyze_frame(self, analyzer: ImageAnalyzer, frame):
        """Analyse asynchrone d'une frame."""
        # Exécuter l'analyse OCR dans un thread séparé pour éviter de bloquer l'event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, analyzer.analyze_frame, frame)
        
    async def json_writer(self):
        """Writer JSON: Collecte les résultats et écrit par batch."""
        print(f"📝 Writer JSON démarré")
        
        buffer = []
        written_count = 0
        active_workers = self.ocr_workers
        
        try:
            while active_workers > 0:
                try:
                    # Récupérer résultat avec timeout
                    result_packet = await asyncio.wait_for(
                        self.ocr_queue.get(), timeout=5.0
                    )
                    
                    if result_packet is None:
                        active_workers -= 1
                        continue
                        
                    buffer.append(result_packet)
                    
                    # Écriture par batch ou si buffer plein
                    if len(buffer) >= JSON_BUFFER_SIZE:
                        await self._flush_json_buffer(buffer)
                        written_count += len(buffer)
                        buffer.clear()
                        
                        if written_count % 50 == 0:
                            print(f"📝 Frames écrites: {written_count}")
                            
                except asyncio.TimeoutError:
                    # Écrire buffer même si pas plein après timeout
                    if buffer:
                        await self._flush_json_buffer(buffer)
                        written_count += len(buffer)
                        buffer.clear()
                        
        except Exception as e:
            print(f"❌ Erreur writer JSON: {e}")
        finally:
            # Écrire le buffer restant
            if buffer:
                await self._flush_json_buffer(buffer)
                written_count += len(buffer)
                
            # Finaliser metadata
            await self._finalize_json_metadata(written_count)
            print(f"✅ Writer JSON terminé: {written_count} frames écrites")
            
    async def _flush_json_buffer(self, buffer):
        """Écrire un batch de résultats dans le JSON."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sync_write_json_batch, buffer)
        
    def _sync_write_json_batch(self, buffer):
        """Écriture synchrone d'un batch (pour thread executor)."""
        try:
            # Lire fichier existant
            with open(self.json_output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # Ajouter nouvelles frames (triées par frame_number pour ordre correct)
            sorted_buffer = sorted(buffer, key=lambda x: x["frame_number"])
            for result in sorted_buffer:
                # Supprimer métadonnées internes
                frame_data = {k: v for k, v in result.items() 
                             if k not in ["frame_number", "worker_id"]}
                data["frames"].append(frame_data)
                
            # Mettre à jour compteur
            data["info"]["total_frames_analyzed"] = len(data["frames"])
            
            # Réécrire fichier
            with open(self.json_output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"❌ Erreur écriture JSON batch: {e}")
            
    async def _finalize_json_metadata(self, final_count):
        """Finaliser les métadonnées JSON."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sync_finalize_metadata, final_count)
        
    def _sync_finalize_metadata(self, final_count):
        """Finalisation synchrone des métadonnées."""
        try:
            with open(self.json_output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            data["info"]["total_frames_analyzed"] = final_count
            data["info"]["analysis_completed_date"] = datetime.now().strftime("%Y-%m-%d")
            
            # Stats performance
            if self.start_time:
                duration = datetime.now() - self.start_time
                data["info"]["processing_time_seconds"] = duration.total_seconds()
                data["info"]["frames_per_second"] = final_count / duration.total_seconds()
                
            with open(self.json_output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"❌ Erreur finalisation JSON: {e}")
            
    async def run(self):
        """Exécuter le pipeline asynchrone complet."""
        print(f"🚀 Démarrage pipeline asynchrone")
        self.start_time = datetime.now()
        
        # Initialiser
        await self.setup()
        
        # Lancer tous les workers en parallèle
        tasks = []
        
        # Producer de frames
        tasks.append(asyncio.create_task(self.frame_producer()))
        
        # Workers OCR
        for i in range(self.ocr_workers):
            tasks.append(asyncio.create_task(self.ocr_worker(i)))
            
        # Writer JSON
        tasks.append(asyncio.create_task(self.json_writer()))
        
        try:
            # Attendre que tous les workers terminent
            await asyncio.gather(*tasks)
            
        except Exception as e:
            print(f"❌ Erreur pipeline: {e}")
        finally:
            # Stats finales
            if self.start_time:
                duration = datetime.now() - self.start_time
                print(f"⏱️ Durée totale: {duration.total_seconds():.1f}s")
                
        print(f"✅ Pipeline terminé: {self.json_output_path}")


async def analyze_youtube_video_async(youtube_url: str, frames_per_minute: int = 12, 
                                    manual_format: Optional[str] = None,
                                    max_frames: Optional[int] = None, ocr_workers: int = 3):
    """Analyser une vidéo YouTube SF6 avec le pipeline asynchrone."""
    pipeline = AsyncPipeline(
        youtube_url=youtube_url,
        frames_per_minute=frames_per_minute,
        manual_format=manual_format,
        max_frames=max_frames,
        ocr_workers=ocr_workers
    )
    
    await pipeline.run()
    return pipeline.json_output_path


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Analyse asynchrone des données de match depuis une vidéo YouTube SF6"
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
    parser.add_argument(
        "--workers", type=int, default=3,
        help="Nombre de workers OCR parallèles (défaut: 3)"
    )
    
    args = parser.parse_args()
    
    if not args.youtube_url:
        print("❌ Erreur: Veuillez spécifier une URL YouTube à analyser.")
        print("💡 Exemples:")
        print("   python async_export.py https://www.youtube.com/watch?v=VIDEO_ID")
        print("   python async_export.py https://www.youtube.com/watch?v=VIDEO_ID --workers 5 --max-frames 100")
        parser.print_help()
    else:
        print(f"🎯 Analyse asynchrone YouTube: {args.youtube_url}")
        print(f"🔧 Configuration: {args.workers} workers OCR, {args.frames_per_minute} FPM")
            
        try:
            # Exécuter pipeline asynchrone
            asyncio.run(analyze_youtube_video_async(
                youtube_url=args.youtube_url,
                frames_per_minute=args.frames_per_minute,
                manual_format=args.format,
                max_frames=args.max_frames,
                ocr_workers=args.workers
            ))
        except Exception as e:
            print(f"❌ Erreur lors de l'analyse: {e}")
            print("💡 Vérifiez que l'URL YouTube est valide et accessible par yt-dlp")