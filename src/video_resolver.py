"""
Module for resolving video URLs to direct streams using yt-dlp.
Handles both local files and online video sources.
"""

import re
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class VideoResolver:
    """
    Resolves video sources to processable streams.
    Supports local files and online URLs via yt-dlp.
    """
    
    def __init__(self, preferred_quality: str = "best[height<=1080]"):
        """
        Initialize video resolver.
        
        Args:
            preferred_quality: yt-dlp format selector for quality preference
        """
        self.preferred_quality = preferred_quality
        
        # Formats prioritaires pour l'OCR (par ordre de préférence)
        # Logique de dégradation: 1080p60 → 1080p30 → 1080p any → 720p60 → 720p30 → 720p any → fallbacks
        self.ocr_optimized_formats = [
            # 1080p 60fps (priorité absolue)
            "312",           # mp4 1920x1080 60fps ~6339k 
            "299",           # mp4 1920x1080 60fps ~4993k
            "617",           # mp4 1920x1080 60fps ~6087k (VP9)
            
            # 1080p 30fps (si pas de 60fps)
            "137",           # mp4 1920x1080 30fps ~4000k
            "616",           # mp4 1920x1080 30fps (VP9)
            
            # 1080p n'importe quel fps (si pas de 30/60)
            "best[height=1080][ext=mp4][vcodec!*=none]",
            "best[height=1080][vcodec!*=none]",
            
            # 720p 60fps (dégradation résolution)
            "298",           # mp4 1280x720 60fps ~1788k
            "302",           # webm 1280x720 60fps (VP9)
            
            # 720p 30fps 
            "136",           # mp4 1280x720 30fps ~3333k
            "247",           # webm 1280x720 30fps (VP9)
            
            # 720p n'importe quel fps
            "best[height=720][ext=mp4][vcodec!*=none]",
            "best[height=720][vcodec!*=none]",
            
            # Fallbacks génériques
            "best[height<=1080][ext=mp4][vcodec!*=none]",
            self.preferred_quality
        ]
        
    def is_url(self, source: str) -> bool:
        """Check if source is a URL or local file path."""
        url_pattern = re.compile(
            r'^https?://',  # http or https
            re.IGNORECASE
        )
        return bool(url_pattern.match(source))
    
    def is_local_file(self, source: str) -> bool:
        """Check if source is a local file that exists."""
        if self.is_url(source):
            return False
        return Path(source).exists()
    
    def resolve_source(self, source: str) -> Dict[str, Any]:
        """
        Resolve video source to processable format.
        
        Args:
            source: Either local file path or URL
            
        Returns:
            Dict with 'path', 'is_stream', 'metadata'
            
        Raises:
            ValueError: If source cannot be resolved
        """
        if self.is_local_file(source):
            return self._resolve_local_file(source)
        elif self.is_url(source):
            return self._resolve_url(source)
        else:
            raise ValueError(f"Source not found or invalid: {source}")
    
    def _resolve_local_file(self, file_path: str) -> Dict[str, Any]:
        """Resolve local file - just validate and return."""
        path = Path(file_path)
        if not path.exists():
            raise ValueError(f"Local file not found: {file_path}")
            
        return {
            'path': str(path.absolute()),
            'is_stream': False,
            'metadata': {
                'source_type': 'local_file',
                'original_source': file_path,
                'file_size': path.stat().st_size
            }
        }
    
    def _resolve_url(self, url: str) -> Dict[str, Any]:
        """Resolve URL to direct stream using yt-dlp."""
        logger.info(f"Resolving URL with yt-dlp: {url}")
        
        # Si preferred_quality n'est pas dans la liste optimisée, c'est un format manuel
        if self.preferred_quality not in self.ocr_optimized_formats:
            logger.info(f"Manual format specified: {self.preferred_quality}")
            result = self._try_format(url, self.preferred_quality)
            if result:
                logger.info(f"Successfully resolved with manual format: {self.preferred_quality}")
                result['metadata']['quality_selector'] = self.preferred_quality
                return result
            else:
                raise ValueError(f"Manual format {self.preferred_quality} failed for URL: {url}")
        
        # Sinon, essayer les formats optimisés pour l'OCR par ordre de priorité
        for format_spec in self.ocr_optimized_formats:
            logger.info(f"Trying format: {format_spec}")
            
            result = self._try_format(url, format_spec)
            if result:
                logger.info(f"Successfully resolved with format: {format_spec}")
                result['metadata']['quality_selector'] = format_spec
                return result
                
        raise ValueError(f"Failed to resolve URL with any supported format: {url}")
    
    def _try_format(self, url: str, format_spec: str) -> Optional[Dict[str, Any]]:
        """Try to resolve URL with specific format."""
        cmd = [
            '/usr/local/bin/yt-dlp',
            '--quiet',
            '--no-warnings', 
            '--print', '%(url)s',  # Print direct URL
            '--print', '%(title)s',  # Print video title
            '--print', '%(duration)s',  # Print duration
            '--print', '%(width)s',  # Print width
            '--print', '%(height)s',  # Print height
            '--format', format_spec,
            url
        ]
        
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30  # 30 second timeout
            )
            
            if result.returncode != 0:
                # Format not available or other error
                logger.debug(f"Format {format_spec} failed: {result.stderr}")
                return None
                
            lines = result.stdout.strip().split('\n')
            if len(lines) < 5:
                logger.debug(f"Unexpected yt-dlp output for format {format_spec}")
                return None
                
            direct_url, title, duration, width, height = lines
            
            return {
                'path': direct_url,  # Direct stream URL
                'is_stream': True,
                'metadata': {
                    'source_type': 'online_stream',
                    'original_source': url,
                    'title': title,
                    'duration': int(duration) if duration.isdigit() else None,
                    'width': int(width) if width.isdigit() else None,
                    'height': int(height) if height.isdigit() else None,
                    'quality_selector': format_spec  # Will be updated by caller
                }
            }
            
        except subprocess.TimeoutExpired:
            logger.debug(f"Timeout for format {format_spec}")
            return None
        except Exception as e:
            logger.debug(f"Error with format {format_spec}: {str(e)}")
            return None
    
    def get_stream_info(self, source: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about video source without resolving stream.
        Useful for validation and metadata display.
        """
        if self.is_local_file(source):
            path = Path(source)
            return {
                'type': 'local_file',
                'exists': True,
                'size': path.stat().st_size,
                'path': str(path.absolute())
            }
        elif self.is_url(source):
            # Quick info extraction without getting stream URL (use absolute path)
            cmd = [
                '/usr/local/bin/yt-dlp',
                '--quiet',
                '--no-warnings',
                '--dump-json',
                '--format', self.preferred_quality,
                source
            ]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
                if result.returncode == 0:
                    info = json.loads(result.stdout)
                    return {
                        'type': 'online_stream',
                        'exists': True,
                        'title': info.get('title', 'Unknown'),
                        'duration': info.get('duration'),
                        'uploader': info.get('uploader', 'Unknown'),
                        'view_count': info.get('view_count'),
                        'upload_date': info.get('upload_date')
                    }
            except Exception as e:
                logger.warning(f"Could not get stream info: {e}")
                
        return None


# Convenience function for backward compatibility
def resolve_video_source(source: str, quality: str = "best[height<=1080]") -> Dict[str, Any]:
    """
    Convenience function to resolve video source.
    
    Args:
        source: Local file path or URL
        quality: yt-dlp quality selector
        
    Returns:
        Resolved source information
    """
    resolver = VideoResolver(quality)
    return resolver.resolve_source(source)