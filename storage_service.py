"""
Storage Service for video and frame management
Uses local filesystem storage for portability
"""

import os
import io
import shutil
from pathlib import Path
from typing import Optional
from PIL import Image


class StorageService:
    """
    Manages local filesystem storage for videos, frames, and exports
    """
    
    def __init__(
        self,
        storage_root: str = "/workspace/doc_copilot/data/storage",
        **kwargs  # Accept but ignore S3-related kwargs for compatibility
    ):
        """
        Initialize storage service
        
        Args:
            storage_root: Root directory for file storage
        """
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.storage_root / "videos").mkdir(exist_ok=True)
        (self.storage_root / "frames").mkdir(exist_ok=True)
        (self.storage_root / "exports").mkdir(exist_ok=True)
    
    def _get_session_dir(self, session_id: str) -> Path:
        """Get or create session directory"""
        session_dir = self.storage_root / "videos" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir
    
    def save_video(
        self,
        session_id: str,
        video_file_path: str,
        filename: str = "original.mp4"
    ) -> str:
        """
        Save video to local storage
        
        Returns: Relative storage path
        """
        session_dir = self._get_session_dir(session_id)
        dest_path = session_dir / filename
        
        # Copy video file
        shutil.copy2(video_file_path, dest_path)
        
        # Return relative path
        return str(dest_path.relative_to(self.storage_root))
    
    def save_frame(
        self,
        session_id: str,
        frame_filename: str,
        image: Image.Image,
        quality: int = 85
    ) -> str:
        """
        Save frame image to local storage
        
        Returns: Relative storage path
        """
        session_dir = self._get_session_dir(session_id)
        frames_dir = session_dir / "frames"
        frames_dir.mkdir(exist_ok=True)
        
        dest_path = frames_dir / frame_filename
        
        # Save image
        image.save(dest_path, format="JPEG", quality=quality)
        
        # Return relative path
        return str(dest_path.relative_to(self.storage_root))
    
    def load_frame(self, relative_path: str) -> Image.Image:
        """
        Load frame image from local storage
        
        Args:
            relative_path: Relative path from storage root
        
        Returns: PIL Image
        """
        full_path = self.storage_root / relative_path
        
        if not full_path.exists():
            raise FileNotFoundError(f"Frame not found: {relative_path}")
        
        return Image.open(full_path)
    
    def save_export_bundle(
        self,
        session_id: str,
        bundle_filename: str,
        local_path: str
    ) -> str:
        """
        Save export bundle to local storage
        
        Returns: Relative storage path
        """
        session_dir = self._get_session_dir(session_id)
        exports_dir = session_dir / "exports"
        exports_dir.mkdir(exist_ok=True)
        
        dest_path = exports_dir / bundle_filename
        
        # Copy bundle file
        shutil.copy2(local_path, dest_path)
        
        # Return relative path
        return str(dest_path.relative_to(self.storage_root))
    
    def download_file(self, relative_path: str, local_path: str):
        """
        Copy file from storage to specified local path
        
        Args:
            relative_path: Relative path from storage root
            local_path: Destination path
        """
        source_path = self.storage_root / relative_path
        
        if not source_path.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")
        
        # Ensure destination directory exists
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        
        shutil.copy2(source_path, local_path)
    
    def get_file_path(self, relative_path: str) -> str:
        """
        Get absolute file path
        
        Args:
            relative_path: Relative path from storage root
        
        Returns: Absolute file path
        """
        return str(self.storage_root / relative_path)
    
    def generate_presigned_url(
        self,
        relative_path: str,
        expiration: int = 3600
    ) -> str:
        """
        Generate file path for local access
        (Kept for API compatibility with S3 version)
        
        Args:
            relative_path: Relative path from storage root
            expiration: Ignored for local storage
        
        Returns: Absolute file path
        """
        return self.get_file_path(relative_path)
    
    def delete_file(self, relative_path: str):
        """
        Delete file from storage
        
        Args:
            relative_path: Relative path from storage root
        """
        file_path = self.storage_root / relative_path
        
        if file_path.exists():
            file_path.unlink()
    
    def delete_session_files(self, session_id: str):
        """
        Delete all files associated with a session
        
        Args:
            session_id: Session ID
        """
        session_dir = self.storage_root / "videos" / session_id
        
        if session_dir.exists():
            shutil.rmtree(session_dir)
    
    def get_storage_stats(self) -> dict:
        """
        Get storage statistics
        
        Returns: Dictionary with storage info
        """
        total_size = 0
        file_count = 0
        
        for root, dirs, files in os.walk(self.storage_root):
            for file in files:
                file_path = Path(root) / file
                total_size += file_path.stat().st_size
                file_count += 1
        
        return {
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "file_count": file_count,
            "storage_root": str(self.storage_root)
        }