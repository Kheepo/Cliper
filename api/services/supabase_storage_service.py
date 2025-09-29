from typing import Dict, Any, Optional
from loguru import logger
import os
import uuid
from ..utils.supabase_client import get_supabase_admin_client

class SupabaseStorageService:
    """
    Supabase Storage service for handling file upload/download operations.
    """
    
    def __init__(self):
        self.supabase = get_supabase_admin_client()
        self.bucket_name = "uploads"  # Default bucket for file uploads
        
    async def upload_file(self, file_path: str, destination_path: str, bucket_name: Optional[str] = None) -> str:
        """
        Upload file to Supabase Storage.
        
        Args:
            file_path: Local file path to upload
            destination_path: Destination path in storage bucket
            bucket_name: Storage bucket name (defaults to 'uploads')
            
        Returns:
            Public URL of the uploaded file
        """
        try:
            bucket = bucket_name or self.bucket_name
            
            # Read file content
            with open(file_path, 'rb') as file:
                file_content = file.read()
            
            # Upload to Supabase Storage
            result = self.supabase.storage.from_(bucket).upload(
                path=destination_path,
                file=file_content,
                file_options={"content-type": self._get_content_type(file_path)}
            )
            
            # Check if upload was successful
            if hasattr(result, 'error') and result.error:
                raise Exception(f"Upload failed: {result.error}")
            
            # Get public URL
            public_url_result = self.supabase.storage.from_(bucket).get_public_url(destination_path)
            
            logger.info(f"File uploaded to Supabase Storage: {destination_path}")
            return public_url_result
            
        except Exception as e:
            logger.error(f"Error uploading file to Supabase Storage: {str(e)}")
            raise
    
    async def upload_file_content(self, file_content: bytes, destination_path: str, content_type: str, bucket_name: Optional[str] = None) -> str:
        """
        Upload file content directly to Supabase Storage.
        
        Args:
            file_content: File content as bytes
            destination_path: Destination path in storage bucket
            content_type: MIME type of the file
            bucket_name: Storage bucket name (defaults to 'uploads')
            
        Returns:
            Public URL of the uploaded file
        """
        try:
            bucket = bucket_name or self.bucket_name
            
            # Upload to Supabase Storage
            result = self.supabase.storage.from_(bucket).upload(
                path=destination_path,
                file=file_content,
                file_options={"content-type": content_type}
            )
            
            # Check if upload was successful
            if hasattr(result, 'error') and result.error:
                raise Exception(f"Upload failed: {result.error}")
            
            # Get public URL
            public_url_result = self.supabase.storage.from_(bucket).get_public_url(destination_path)
            
            logger.info(f"File content uploaded to Supabase Storage: {destination_path}")
            return public_url_result
            
        except Exception as e:
            logger.error(f"Error uploading file content to Supabase Storage: {str(e)}")
            raise
    
    async def delete_file(self, file_path: str, bucket_name: Optional[str] = None) -> bool:
        """
        Delete file from Supabase Storage.
        
        Args:
            file_path: Path of the file in storage bucket
            bucket_name: Storage bucket name (defaults to 'uploads')
            
        Returns:
            True if deletion was successful
        """
        try:
            bucket = bucket_name or self.bucket_name
            
            result = self.supabase.storage.from_(bucket).remove([file_path])
            
            if hasattr(result, 'error') and result.error:
                raise Exception(f"Delete failed: {result.error}")
            
            logger.info(f"File deleted from Supabase Storage: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting file from Supabase Storage: {str(e)}")
            raise
    
    async def get_file_url(self, file_path: str, bucket_name: Optional[str] = None) -> str:
        """
        Get public URL for a file in Supabase Storage.
        
        Args:
            file_path: Path of the file in storage bucket
            bucket_name: Storage bucket name (defaults to 'uploads')
            
        Returns:
            Public URL of the file
        """
        try:
            bucket = bucket_name or self.bucket_name
            
            public_url = self.supabase.storage.from_(bucket).get_public_url(file_path)
            
            return public_url
            
        except Exception as e:
            logger.error(f"Error getting file URL from Supabase Storage: {str(e)}")
            raise
    
    async def list_files(self, folder_path: str = "", bucket_name: Optional[str] = None) -> list:
        """
        List files in a Supabase Storage bucket folder.
        
        Args:
            folder_path: Folder path to list files from
            bucket_name: Storage bucket name (defaults to 'uploads')
            
        Returns:
            List of file objects
        """
        try:
            bucket = bucket_name or self.bucket_name
            
            result = self.supabase.storage.from_(bucket).list(folder_path)
            
            if hasattr(result, 'error') and result.error:
                raise Exception(f"List files failed: {result.error}")
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error listing files from Supabase Storage: {str(e)}")
            raise
    
    def generate_unique_filename(self, original_filename: str) -> str:
        """
        Generate a unique filename to avoid conflicts.
        
        Args:
            original_filename: Original filename
            
        Returns:
            Unique filename with UUID prefix
        """
        file_extension = os.path.splitext(original_filename)[1]
        unique_id = str(uuid.uuid4())
        return f"{unique_id}{file_extension}"
    
    async def upload_video(self, file_content: bytes, filename: str, user_id: str) -> str:
        """
        Upload video file to Supabase Storage.
        
        Args:
            file_content: Video file content as bytes
            filename: Original filename
            user_id: User ID for organizing uploads
            
        Returns:
            Public URL of the uploaded video
        """
        try:
            # Generate unique filename
            unique_filename = self.generate_unique_filename(filename)
            
            # Create user-specific path - user_id must be first folder for RLS policy
            destination_path = f"{user_id}/videos/{unique_filename}"
            
            # Determine content type
            content_type = self._get_content_type(filename)
            
            # Upload video content
            public_url = await self.upload_file_content(
                file_content=file_content,
                destination_path=destination_path,
                content_type=content_type,
                bucket_name="uploads"
            )
            
            logger.info(f"Video uploaded successfully: {destination_path}")
            return public_url
            
        except Exception as e:
            logger.error(f"Error uploading video: {str(e)}")
            raise
    
    def _get_content_type(self, file_path: str) -> str:
        """
        Get content type based on file extension.
        
        Args:
            file_path: Path to the file
            
        Returns:
            MIME type string
        """
        import mimetypes
        content_type, _ = mimetypes.guess_type(file_path)
        return content_type or 'application/octet-stream'

# Global instance
supabase_storage_service = SupabaseStorageService()