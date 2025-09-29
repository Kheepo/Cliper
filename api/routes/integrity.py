"""Data integrity API endpoints.

Provides REST API endpoints for:
- File integrity validation
- Checksum management
- Batch validation operations
- Integrity reporting and monitoring
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import logging

from pydantic import BaseModel, Field
from ..utils.data_integrity import (
    get_integrity_manager,
    IntegrityLevel,
    ValidationStatus,
    ChecksumAlgorithm,
    ValidationResult,
    IntegrityReport,
    FileChecksum,
    batch_validate_directory
)
from ..core.auth import get_current_user
from ..core.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrity", tags=["integrity"])


# Pydantic models
class FileValidationRequest(BaseModel):
    """Request model for file validation."""
    file_path: str = Field(..., description="Path to the file to validate")
    level: IntegrityLevel = Field(IntegrityLevel.CHECKSUM, description="Validation level")
    use_cache: bool = Field(True, description="Whether to use cached results")


class BatchValidationRequest(BaseModel):
    """Request model for batch validation."""
    file_paths: List[str] = Field(..., description="List of file paths to validate")
    level: IntegrityLevel = Field(IntegrityLevel.CHECKSUM, description="Validation level")
    max_workers: int = Field(4, ge=1, le=16, description="Maximum number of worker threads")


class DirectoryValidationRequest(BaseModel):
    """Request model for directory validation."""
    directory: str = Field(..., description="Directory path to validate")
    pattern: str = Field("*", description="File pattern to match")
    level: IntegrityLevel = Field(IntegrityLevel.CHECKSUM, description="Validation level")
    recursive: bool = Field(True, description="Whether to scan recursively")


class ChecksumRegistrationRequest(BaseModel):
    """Request model for checksum registration."""
    file_path: str = Field(..., description="Path to the file")
    algorithm: Optional[ChecksumAlgorithm] = Field(None, description="Checksum algorithm")


class ValidationResultResponse(BaseModel):
    """Response model for validation results."""
    file_path: str
    status: ValidationStatus
    checksum_match: bool
    size_match: bool
    metadata_valid: bool
    errors: List[str]
    warnings: List[str]
    validation_time: float
    validated_at: datetime

    class Config:
        from_attributes = True


class IntegrityReportResponse(BaseModel):
    """Response model for integrity reports."""
    total_files: int
    valid_files: int
    invalid_files: int
    corrupted_files: int
    missing_files: int
    total_size: int
    validation_time: float
    generated_at: datetime
    summary: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class FileChecksumResponse(BaseModel):
    """Response model for file checksums."""
    file_path: str
    algorithm: ChecksumAlgorithm
    checksum: str
    file_size: int
    created_at: datetime
    last_verified: Optional[datetime]
    verification_count: int

    class Config:
        from_attributes = True


class IntegrityStatsResponse(BaseModel):
    """Response model for integrity statistics."""
    total_registered_files: int
    verified_files: int
    total_verifications: int
    cache_entries: int
    checksum_algorithm: str


@router.post("/validate", response_model=ValidationResultResponse)
async def validate_file(
    request: FileValidationRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """Validate a single file's integrity.
    
    Performs integrity validation on a file including:
    - Basic file existence and size checks
    - Checksum verification (if registered)
    - Metadata validation for video files
    - Deep content analysis (optional)
    """
    try:
        integrity_manager = get_integrity_manager()
        
        # Validate file path
        file_path = Path(request.file_path)
        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {request.file_path}"
            )
        
        # Perform validation
        result = integrity_manager.validate_file(
            file_path,
            level=request.level,
            use_cache=request.use_cache
        )
        
        logger.info(
            f"File validation completed: {request.file_path} - {result.status.value}"
        )
        
        return ValidationResultResponse.model_validate(result)
    
    except Exception as e:
        logger.error(f"File validation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Validation failed: {str(e)}"
        )


@router.post("/validate/batch", response_model=IntegrityReportResponse)
async def validate_files_batch(
    request: BatchValidationRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """Validate multiple files in batch.
    
    Performs parallel validation of multiple files and returns
    a comprehensive integrity report.
    """
    try:
        integrity_manager = get_integrity_manager()
        
        # Validate file paths
        valid_paths = []
        for file_path in request.file_paths:
            path = Path(file_path)
            if path.exists():
                valid_paths.append(path)
            else:
                logger.warning(f"File not found, skipping: {file_path}")
        
        if not valid_paths:
            raise HTTPException(
                status_code=400,
                detail="No valid file paths provided"
            )
        
        # Perform batch validation
        report = integrity_manager.batch_validate(
            valid_paths,
            level=request.level,
            max_workers=request.max_workers
        )
        
        # Add summary statistics
        summary = {
            "validation_rate": report.valid_files / report.total_files if report.total_files > 0 else 0,
            "corruption_rate": report.corrupted_files / report.total_files if report.total_files > 0 else 0,
            "average_validation_time": sum(r.validation_time for r in report.details) / len(report.details) if report.details else 0,
            "total_errors": sum(len(r.errors) for r in report.details),
            "total_warnings": sum(len(r.warnings) for r in report.details)
        }
        
        response = IntegrityReportResponse.model_validate(report)
        response.summary = summary
        
        logger.info(
            f"Batch validation completed: {report.valid_files}/{report.total_files} files valid"
        )
        
        return response
    
    except Exception as e:
        logger.error(f"Batch validation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Batch validation failed: {str(e)}"
        )


@router.post("/validate/directory", response_model=IntegrityReportResponse)
async def validate_directory(
    request: DirectoryValidationRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """Validate all files in a directory.
    
    Scans a directory for files matching the specified pattern
    and validates their integrity.
    """
    try:
        # Validate directory path
        directory = Path(request.directory)
        if not directory.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Directory not found: {request.directory}"
            )
        
        if not directory.is_dir():
            raise HTTPException(
                status_code=400,
                detail=f"Path is not a directory: {request.directory}"
            )
        
        # Perform directory validation
        report = batch_validate_directory(
            directory,
            pattern=request.pattern,
            level=request.level,
            recursive=request.recursive
        )
        
        # Add summary statistics
        summary = {
            "validation_rate": report.valid_files / report.total_files if report.total_files > 0 else 0,
            "corruption_rate": report.corrupted_files / report.total_files if report.total_files > 0 else 0,
            "average_validation_time": sum(r.validation_time for r in report.details) / len(report.details) if report.details else 0,
            "total_errors": sum(len(r.errors) for r in report.details),
            "total_warnings": sum(len(r.warnings) for r in report.details),
            "directory_scanned": str(directory),
            "pattern_used": request.pattern,
            "recursive_scan": request.recursive
        }
        
        response = IntegrityReportResponse.model_validate(report)
        response.summary = summary
        
        logger.info(
            f"Directory validation completed: {report.valid_files}/{report.total_files} files valid in {directory}"
        )
        
        return response
    
    except Exception as e:
        logger.error(f"Directory validation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Directory validation failed: {str(e)}"
        )


@router.post("/register", response_model=FileChecksumResponse)
async def register_file_checksum(
    request: ChecksumRegistrationRequest,
    current_user = Depends(get_current_user)
):
    """Register a file and calculate its checksum.
    
    Calculates and stores the checksum for a file to enable
    future integrity validation.
    """
    try:
        integrity_manager = get_integrity_manager()
        
        # Validate file path
        file_path = Path(request.file_path)
        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {request.file_path}"
            )
        
        # Register file
        file_checksum = integrity_manager.register_file(file_path)
        
        logger.info(f"File registered: {request.file_path}")
        
        return FileChecksumResponse.model_validate(file_checksum)
    
    except Exception as e:
        logger.error(f"File registration failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Registration failed: {str(e)}"
        )


@router.get("/checksum/{file_path:path}", response_model=FileChecksumResponse)
async def get_file_checksum(
    file_path: str,
    current_user = Depends(get_current_user)
):
    """Get stored checksum information for a file."""
    try:
        integrity_manager = get_integrity_manager()
        
        if file_path not in integrity_manager.checksums:
            raise HTTPException(
                status_code=404,
                detail=f"No checksum found for file: {file_path}"
            )
        
        checksum = integrity_manager.checksums[file_path]
        return FileChecksumResponse.model_validate(checksum)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get checksum: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get checksum: {str(e)}"
        )


@router.get("/checksums", response_model=List[FileChecksumResponse])
async def list_checksums(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    current_user = Depends(get_current_user)
):
    """List all stored checksums with pagination."""
    try:
        integrity_manager = get_integrity_manager()
        
        checksums = list(integrity_manager.checksums.values())
        total = len(checksums)
        
        # Apply pagination
        paginated_checksums = checksums[skip:skip + limit]
        
        response_data = [
            FileChecksumResponse.model_validate(checksum)
            for checksum in paginated_checksums
        ]
        
        return response_data
    
    except Exception as e:
        logger.error(f"Failed to list checksums: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list checksums: {str(e)}"
        )


@router.get("/stats", response_model=IntegrityStatsResponse)
async def get_integrity_stats(
    current_user = Depends(get_current_user)
):
    """Get integrity management statistics."""
    try:
        integrity_manager = get_integrity_manager()
        stats = integrity_manager.get_integrity_stats()
        
        return IntegrityStatsResponse(**stats)
    
    except Exception as e:
        logger.error(f"Failed to get integrity stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get stats: {str(e)}"
        )


@router.delete("/checksum/{file_path:path}")
async def delete_file_checksum(
    file_path: str,
    current_user = Depends(get_current_user)
):
    """Delete stored checksum for a file."""
    try:
        integrity_manager = get_integrity_manager()
        
        if file_path not in integrity_manager.checksums:
            raise HTTPException(
                status_code=404,
                detail=f"No checksum found for file: {file_path}"
            )
        
        del integrity_manager.checksums[file_path]
        
        logger.info(f"Checksum deleted for file: {file_path}")
        
        return {"message": f"Checksum deleted for file: {file_path}"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete checksum: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete checksum: {str(e)}"
        )


@router.post("/cleanup")
async def cleanup_orphaned_checksums(
    current_user = Depends(get_current_user)
):
    """Remove checksums for files that no longer exist."""
    try:
        integrity_manager = get_integrity_manager()
        
        orphaned_files = []
        for file_path in list(integrity_manager.checksums.keys()):
            if not Path(file_path).exists():
                orphaned_files.append(file_path)
        
        # Remove orphaned checksums
        for file_path in orphaned_files:
            del integrity_manager.checksums[file_path]
        
        logger.info(f"Cleaned up {len(orphaned_files)} orphaned checksums")
        
        return {
            "message": f"Cleaned up {len(orphaned_files)} orphaned checksums",
            "orphaned_files": orphaned_files
        }
    
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Cleanup failed: {str(e)}"
        )


@router.get("/report/summary")
async def get_integrity_summary(
    current_user = Depends(get_current_user)
):
    """Get a summary of overall system integrity."""
    try:
        integrity_manager = get_integrity_manager()
        
        # Get basic stats
        stats = integrity_manager.get_integrity_stats()
        
        # Calculate additional metrics
        total_checksums = len(integrity_manager.checksums)
        verified_recently = sum(
            1 for checksum in integrity_manager.checksums.values()
            if checksum.last_verified and 
            (datetime.utcnow() - checksum.last_verified).days <= 7
        )
        
        # Check for files that exist but aren't registered
        settings = get_settings()
        storage_path = Path(settings.STORAGE_PATH)
        
        unregistered_files = 0
        if storage_path.exists():
            all_files = list(storage_path.rglob("*"))
            all_files = [f for f in all_files if f.is_file()]
            registered_paths = set(integrity_manager.checksums.keys())
            unregistered_files = len([
                f for f in all_files 
                if str(f) not in registered_paths
            ])
        
        summary = {
            "total_registered_files": total_checksums,
            "verified_files": stats["verified_files"],
            "verified_recently": verified_recently,
            "unregistered_files": unregistered_files,
            "total_verifications": stats["total_verifications"],
            "cache_entries": stats["cache_entries"],
            "checksum_algorithm": stats["checksum_algorithm"],
            "health_score": min(100, (verified_recently / total_checksums * 100) if total_checksums > 0 else 100)
        }
        
        return summary
    
    except Exception as e:
        logger.error(f"Failed to get integrity summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get summary: {str(e)}"
        )


@router.post("/verify/clip/{clip_id}")
async def verify_clip_integrity(
    clip_id: str,
    level: IntegrityLevel = Query(IntegrityLevel.METADATA, description="Validation level"),
    current_user = Depends(get_current_user)
):
    """Verify integrity of a specific clip and its associated files."""
    try:
        settings = get_settings()
        
        # Find clip files
        clip_dir = Path(settings.STORAGE_PATH) / "clips" / clip_id
        if not clip_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Clip directory not found: {clip_id}"
            )
        
        # Get all files in clip directory
        clip_files = list(clip_dir.rglob("*"))
        clip_files = [f for f in clip_files if f.is_file()]
        
        if not clip_files:
            raise HTTPException(
                status_code=404,
                detail=f"No files found for clip: {clip_id}"
            )
        
        # Validate all clip files
        integrity_manager = get_integrity_manager()
        report = integrity_manager.batch_validate(clip_files, level=level)
        
        # Add clip-specific summary
        summary = {
            "clip_id": clip_id,
            "clip_directory": str(clip_dir),
            "validation_rate": report.valid_files / report.total_files if report.total_files > 0 else 0,
            "corruption_rate": report.corrupted_files / report.total_files if report.total_files > 0 else 0,
            "total_errors": sum(len(r.errors) for r in report.details),
            "total_warnings": sum(len(r.warnings) for r in report.details),
            "integrity_status": "healthy" if report.corrupted_files == 0 else "corrupted"
        }
        
        response = IntegrityReportResponse.model_validate(report)
        response.summary = summary
        
        logger.info(
            f"Clip integrity verification completed: {clip_id} - {summary['integrity_status']}"
        )
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Clip integrity verification failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Clip verification failed: {str(e)}"
        )