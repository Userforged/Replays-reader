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
        
        # yt-dlp command to extract info without downloading (use absolute path)
        cmd = [
            '/usr/local/bin/yt-dlp',
            '--quiet',
            '--no-warnings', 
            '--print', '%(url)s',  # Print direct URL
            '--print', '%(title)s',  # Print video title
            '--print', '%(duration)s',  # Print duration
            '--print', '%(width)s',  # Print width
            '--print', '%(height)s',  # Print height
            '--format', self.preferred_quality,
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
                raise ValueError(f"yt-dlp failed: {result.stderr}")
                
            lines = result.stdout.strip().split('\n')
            if len(lines) < 5:
                raise ValueError("Unexpected yt-dlp output format")
                
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
                    'quality_selector': self.preferred_quality
                }
            }
            
        except subprocess.TimeoutExpired:
            raise ValueError(f"Timeout while resolving URL: {url}")
        except Exception as e:
            raise ValueError(f"Failed to resolve URL {url}: {str(e)}")
    
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