"""
Écrivain JSON asynchrone pour streaming des résultats OCR.
Consomme un générateur async d'OCR et écrit directement dans le fichier.
"""
import asyncio
import json
import os
from datetime import datetime
from typing import AsyncGenerator, Dict, Any


class AsyncJsonWriter:
    """
    Écrivain JSON asynchrone qui consomme les résultats OCR et écrit en streaming.
    """
    
    def __init__(self, output_path: str, info_data: Dict[str, Any]):
        self.output_path = output_path
        self.info_data = info_data
        self.frames_written = 0
        
    async def consume_and_write(self, ocr_generator: AsyncGenerator[Dict[str, Any], None]):
        """
        Consomme les résultats OCR et les écrit directement dans le JSON.
        
        Args:
            ocr_generator: Générateur async de résultats OCR
        """
        print(f"📝 Initialisation JSON streaming: {self.output_path}")
        
        # Initialiser le fichier JSON avec structure et info
        await self._initialize_json_file()
        
        # Traitement streaming des résultats OCR
        async for ocr_result in ocr_generator:
            frame_data = self._create_frame_data(ocr_result)
            await self._append_frame_to_json(frame_data)
            self.frames_written += 1
            
            if self.frames_written % 10 == 0:
                print(f"📝 Frames écrites: {self.frames_written}")
                
            # Point de concurrence - permet à d'autres coroutines de s'exécuter
            await asyncio.sleep(0)
        
        # Finaliser le fichier avec métadonnées complètes
        await self._finalize_json_metadata()
        
        print(f"✅ JSON writer terminé: {self.frames_written} frames écrites")
        return self.frames_written
        
    async def _initialize_json_file(self):
        """Initialise le fichier JSON avec structure et métadonnées."""
        initial_structure = {
            "info": self.info_data,
            "frames": []
        }
        
        # Écriture asynchrone dans thread pool pour éviter blocage I/O
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._write_json_file, initial_structure)
        
    async def _append_frame_to_json(self, frame_data: Dict[str, Any]):
        """Ajoute une frame au fichier JSON existant."""
        # Lecture/écriture asynchrone dans thread pool
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._append_frame_sync, frame_data)
        
    def _append_frame_sync(self, frame_data: Dict[str, Any]):
        """Version synchrone pour thread pool - ajoute frame au JSON."""
        try:
            # Lire le JSON existant
            with open(self.output_path, "r", encoding="utf-8") as json_file:
                data = json.load(json_file)
                
            # Ajouter la nouvelle frame
            if isinstance(data, dict) and "frames" in data:
                data["frames"].append(frame_data)
            else:
                # Fallback pour compatibilité
                data = {"info": self.info_data, "frames": [frame_data]}
                
            # Réécrire le fichier
            with open(self.output_path, "w", encoding="utf-8") as json_file:
                json.dump(data, json_file, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"❌ Erreur écriture JSON: {e}")
            
    async def _finalize_json_metadata(self):
        """Finalise les métadonnées JSON avec count final."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._finalize_metadata_sync)
        
    def _finalize_metadata_sync(self):
        """Version synchrone pour thread pool - finalise métadonnées."""
        try:
            with open(self.output_path, "r", encoding="utf-8") as json_file:
                data = json.load(json_file)
                
            if isinstance(data, dict) and "info" in data:
                data["info"]["total_frames_analyzed"] = self.frames_written
                data["info"]["analysis_completed_date"] = datetime.now().strftime("%Y-%m-%d")
                
            with open(self.output_path, "w", encoding="utf-8") as json_file:
                json.dump(data, json_file, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"❌ Erreur finalisation JSON: {e}")
            
    def _write_json_file(self, data: Dict[str, Any]):
        """Écrit le fichier JSON complet (thread pool)."""
        with open(self.output_path, "w", encoding="utf-8") as json_file:
            json.dump(data, json_file, indent=2, ensure_ascii=False)
            
    def _create_frame_data(self, ocr_result: Dict[str, Any]) -> Dict[str, Any]:
        """Convertit résultat OCR en format frame pour JSON."""
        return {
            "timestamp": ocr_result["timestamp"],
            "timer_value": ocr_result.get("timer", ""),
            "character1": ocr_result.get("character1", ""),
            "character2": ocr_result.get("character2", ""),
            "player1": ocr_result.get("player1", ""),
            "player2": ocr_result.get("player2", "")
        }