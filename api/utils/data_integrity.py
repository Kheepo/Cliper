"""Data integrity and validation utilities.

Provides:
- File checksum calculation and verification
- Data validation and consistency checks
- Backup and recovery mechanisms
- Transaction integrity monitoring
- Corruption detection and repair
"""

import hashlib
import os
import shutil
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass
from enum import Enum

import aiofiles
import asyncio
from pydantic import BaseModel, validator

from api.utils.enhanced_logging import get_logger
from api.config.production import get_settings


logger = get_logger(__name__)
settings = get_settings()


class ChecksumAlgorithm(str, Enum):
    """Supported checksum algorithms."""
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    SHA512 = "sha512"
    CRC32 = "crc32"


class ValidationStatus(str, Enum):
    """Validation status."""
    VALID = "valid"
    INVALID = "invalid"
    CORRUPTED = "corrupted"
    MISSING = "missing"
    UNKNOWN = "unknown"


@dataclass
class FileChecksum:
    """File checksum information."""
    file_path: str
    algorithm: ChecksumAlgorithm
    checksum: str
    file_size: int
    created_at: datetime
    last_verified: Optional[datetime] = None
    verification_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'file_path': self.file_path,
            'algorithm': self.algorithm.value,
            'checksum': self.checksum,
            'file_size': self.file_size,
            'created_at': self.created_at.isoformat(),
            'last_verified': self.last_verified.isoformat() if self.last_verified else None,
            'verification_count': self.verification_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileChecksum':
        """Create from dictionary."""
        return cls(
            file_path=data['file_path'],
            algorithm=ChecksumAlgorithm(data['algorithm']),
            checksum=data['checksum'],
            file_size=data['file_size'],
            created_at=datetime.fromisoformat(data['created_at']),
            last_verified=datetime.fromisoformat(data['last_verified']) if data.get('last_verified') else None,
            verification_count=data.get('verification_count', 0)
        )


class ValidationResult(BaseModel):
    """Validation result."""
    status: ValidationStatus
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime
    
    class Config:
        use_enum_values = True


class DataIntegrityManager:
    """Manages data integrity checks and validation."""
    
    def __init__(self, storage_path: Optional[str] = None):
        # Get storage config from settings
        if hasattr(settings, 'storage') and hasattr(settings.storage, 'temp_path'):
            default_path = settings.storage.temp_path
        elif hasattr(settings, 'temp_path'):
            default_path = settings.temp_path
        elif hasattr(settings, 'get_storage_config'):
            default_path = settings.get_storage_config().temp_path
        else:
            default_path = "./temp"
        
        self.storage_path = Path(storage_path or default_path)
        self.checksums_file = self.storage_path / "checksums.json"
        self.checksums: Dict[str, FileChecksum] = {}
        self.verification_interval = 3600  # 1 hour
        
        # Ensure storage directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize checksums synchronously
        self._load_checksums_sync()
        
        # Background verification will be started when needed
        self._verification_task = None
    
    async def calculate_checksum(self, file_path: Union[str, Path], 
                               algorithm: ChecksumAlgorithm = ChecksumAlgorithm.SHA256) -> str:
        """Calculate file checksum."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        hash_func = self._get_hash_function(algorithm)
        
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                while chunk := await f.read(8192):
                    hash_func.update(chunk)
            
            return hash_func.hexdigest()
            
        except Exception as e:
            logger.error(f"Error calculating checksum for {file_path}: {e}")
            raise
    
    def _get_hash_function(self, algorithm: ChecksumAlgorithm):
        """Get hash function for algorithm."""
        if algorithm == ChecksumAlgorithm.MD5:
            return hashlib.md5()
        elif algorithm == ChecksumAlgorithm.SHA1:
            return hashlib.sha1()
        elif algorithm == ChecksumAlgorithm.SHA256:
            return hashlib.sha256()
        elif algorithm == ChecksumAlgorithm.SHA512:
            return hashlib.sha512()
        elif algorithm == ChecksumAlgorithm.CRC32:
            import zlib
            class CRC32Hash:
                def __init__(self):
                    self.crc = 0
                def update(self, data):
                    self.crc = zlib.crc32(data, self.crc)
                def hexdigest(self):
                    return f"{self.crc & 0xffffffff:08x}"
            return CRC32Hash()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    async def register_file(self, file_path: Union[str, Path], 
                          algorithm: ChecksumAlgorithm = ChecksumAlgorithm.SHA256) -> FileChecksum:
        """Register a file for integrity monitoring."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        try:
            checksum = await self.calculate_checksum(file_path, algorithm)
            file_size = file_path.stat().st_size
            
            file_checksum = FileChecksum(
                file_path=str(file_path),
                algorithm=algorithm,
                checksum=checksum,
                file_size=file_size,
                created_at=datetime.utcnow()
            )
            
            self.checksums[str(file_path)] = file_checksum
            await self._save_checksums()
            
            logger.info(f"Registered file for integrity monitoring: {file_path}")
            return file_checksum
            
        except Exception as e:
            logger.error(f"Error registering file {file_path}: {e}")
            raise
    
    async def verify_file(self, file_path: Union[str, Path]) -> ValidationResult:
        """Verify file integrity."""
        file_path = Path(file_path)
        file_path_str = str(file_path)
        
        if file_path_str not in self.checksums:
            return ValidationResult(
                status=ValidationStatus.UNKNOWN,
                message=f"File not registered for integrity monitoring: {file_path}",
                timestamp=datetime.utcnow()
            )
        
        file_checksum = self.checksums[file_path_str]
        
        try:
            # Check if file exists
            if not file_path.exists():
                return ValidationResult(
                    status=ValidationStatus.MISSING,
                    message=f"File missing: {file_path}",
                    timestamp=datetime.utcnow()
                )
            
            # Check file size
            current_size = file_path.stat().st_size
            if current_size != file_checksum.file_size:
                return ValidationResult(
                    status=ValidationStatus.CORRUPTED,
                    message=f"File size mismatch: expected {file_checksum.file_size}, got {current_size}",
                    details={
                        'expected_size': file_checksum.file_size,
                        'actual_size': current_size
                    },
                    timestamp=datetime.utcnow()
                )
            
            # Calculate current checksum
            current_checksum = await self.calculate_checksum(file_path, file_checksum.algorithm)
            
            # Compare checksums
            if current_checksum == file_checksum.checksum:
                # Update verification info
                file_checksum.last_verified = datetime.utcnow()
                file_checksum.verification_count += 1
                await self._save_checksums()
                
                return ValidationResult(
                    status=ValidationStatus.VALID,
                    message=f"File integrity verified: {file_path}",
                    details={
                        'algorithm': file_checksum.algorithm.value,
                        'checksum': current_checksum,
                        'verification_count': file_checksum.verification_count
                    },
                    timestamp=datetime.utcnow()
                )
            else:
                return ValidationResult(
                    status=ValidationStatus.CORRUPTED,
                    message=f"Checksum mismatch: {file_path}",
                    details={
                        'expected_checksum': file_checksum.checksum,
                        'actual_checksum': current_checksum,
                        'algorithm': file_checksum.algorithm.value
                    },
                    timestamp=datetime.utcnow()
                )
                
        except Exception as e:
            logger.error(f"Error verifying file {file_path}: {e}")
            return ValidationResult(
                status=ValidationStatus.INVALID,
                message=f"Verification error: {e}",
                timestamp=datetime.utcnow()
            )
    
    async def verify_all_files(self) -> Dict[str, ValidationResult]:
        """Verify integrity of all registered files."""
        results = {}
        
        for file_path in self.checksums.keys():
            try:
                result = await self.verify_file(file_path)
                results[file_path] = result
            except Exception as e:
                logger.error(f"Error verifying file {file_path}: {e}")
                results[file_path] = ValidationResult(
                    status=ValidationStatus.INVALID,
                    message=f"Verification error: {e}",
                    timestamp=datetime.utcnow()
                )
        
        return results
    
    async def create_backup(self, file_path: Union[str, Path], 
                          backup_dir: Optional[Union[str, Path]] = None) -> Path:
        """Create a backup of a file."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if backup_dir is None:
            backup_dir = self.storage_path / "backups"
        else:
            backup_dir = Path(backup_dir)
        
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Create backup filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = backup_dir / backup_name
        
        try:
            shutil.copy2(file_path, backup_path)
            
            # Register backup for integrity monitoring
            await self.register_file(backup_path)
            
            logger.info(f"Created backup: {file_path} -> {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Error creating backup for {file_path}: {e}")
            raise
    
    async def restore_from_backup(self, original_path: Union[str, Path], 
                                backup_path: Union[str, Path]) -> bool:
        """Restore a file from backup."""
        original_path = Path(original_path)
        backup_path = Path(backup_path)
        
        if not backup_path.exists():
            logger.error(f"Backup file not found: {backup_path}")
            return False
        
        try:
            # Verify backup integrity first
            backup_result = await self.verify_file(backup_path)
            if backup_result.status != ValidationStatus.VALID:
                logger.error(f"Backup file is corrupted: {backup_path}")
                return False
            
            # Create backup of current file if it exists
            if original_path.exists():
                await self.create_backup(original_path)
            
            # Restore from backup
            shutil.copy2(backup_path, original_path)
            
            # Re-register the restored file
            await self.register_file(original_path)
            
            logger.info(f"Restored file from backup: {backup_path} -> {original_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error restoring from backup {backup_path}: {e}")
            return False
    
    async def cleanup_old_backups(self, backup_dir: Optional[Union[str, Path]] = None, 
                                max_age_days: int = 30):
        """Clean up old backup files."""
        if backup_dir is None:
            backup_dir = self.storage_path / "backups"
        else:
            backup_dir = Path(backup_dir)
        
        if not backup_dir.exists():
            return
        
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
        
        try:
            for backup_file in backup_dir.iterdir():
                if backup_file.is_file():
                    file_mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
                    if file_mtime < cutoff_date:
                        # Remove from checksums if registered
                        if str(backup_file) in self.checksums:
                            del self.checksums[str(backup_file)]
                        
                        backup_file.unlink()
                        logger.info(f"Deleted old backup: {backup_file}")
            
            await self._save_checksums()
            
        except Exception as e:
            logger.error(f"Error cleaning up old backups: {e}")
    
    def _load_checksums_sync(self):
        """Load checksums from storage synchronously."""
        try:
            if self.checksums_file.exists():
                import json
                with open(self.checksums_file, 'r') as f:
                    data = json.loads(f.read())
                    
                    for file_path, checksum_data in data.items():
                        self.checksums[file_path] = FileChecksum.from_dict(checksum_data)
                
                logger.info(f"Loaded {len(self.checksums)} file checksums")
                
        except Exception as e:
            logger.error(f"Error loading checksums: {e}")
    
    async def _load_checksums(self):
        """Load checksums from storage."""
        try:
            if self.checksums_file.exists():
                async with aiofiles.open(self.checksums_file, 'r') as f:
                    import json
                    data = json.loads(await f.read())
                    
                    for file_path, checksum_data in data.items():
                        self.checksums[file_path] = FileChecksum.from_dict(checksum_data)
                
                logger.info(f"Loaded {len(self.checksums)} file checksums")
                
        except Exception as e:
            logger.error(f"Error loading checksums: {e}")
    
    async def _save_checksums(self):
        """Save checksums to storage."""
        try:
            data = {}
            for file_path, checksum in self.checksums.items():
                data[file_path] = checksum.to_dict()
            
            async with aiofiles.open(self.checksums_file, 'w') as f:
                import json
                await f.write(json.dumps(data, indent=2))
                
        except Exception as e:
            logger.error(f"Error saving checksums: {e}")
    
    async def _verification_loop(self):
        """Background verification loop."""
        while True:
            try:
                await asyncio.sleep(self.verification_interval)
                
                logger.info("Starting periodic file integrity verification")
                results = await self.verify_all_files()
                
                # Log verification results
                valid_count = sum(1 for r in results.values() if r.status == ValidationStatus.VALID)
                corrupted_count = sum(1 for r in results.values() if r.status == ValidationStatus.CORRUPTED)
                missing_count = sum(1 for r in results.values() if r.status == ValidationStatus.MISSING)
                
                logger.info(f"Verification complete: {valid_count} valid, {corrupted_count} corrupted, {missing_count} missing")
                
                # Alert on corrupted files
                for file_path, result in results.items():
                    if result.status in [ValidationStatus.CORRUPTED, ValidationStatus.MISSING]:
                        logger.error(f"File integrity issue: {file_path} - {result.message}")
                
            except Exception as e:
                logger.error(f"Error in verification loop: {e}")


class ClipValidator:
    """Validates generated clips for quality and integrity."""
    
    def __init__(self, integrity_manager: DataIntegrityManager):
        self.integrity_manager = integrity_manager
    
    async def validate_clip(self, clip_path: Union[str, Path]) -> ValidationResult:
        """Validate a generated clip."""
        clip_path = Path(clip_path)
        
        try:
            # Basic file existence check
            if not clip_path.exists():
                return ValidationResult(
                    status=ValidationStatus.MISSING,
                    message=f"Clip file not found: {clip_path}",
                    timestamp=datetime.utcnow()
                )
            
            # File size check
            file_size = clip_path.stat().st_size
            if file_size == 0:
                return ValidationResult(
                    status=ValidationStatus.CORRUPTED,
                    message=f"Clip file is empty: {clip_path}",
                    timestamp=datetime.utcnow()
                )
            
            # Minimum size check (e.g., 1KB)
            if file_size < 1024:
                return ValidationResult(
                    status=ValidationStatus.CORRUPTED,
                    message=f"Clip file too small: {clip_path} ({file_size} bytes)",
                    details={'file_size': file_size},
                    timestamp=datetime.utcnow()
                )
            
            # File extension check
            if clip_path.suffix.lower() not in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
                return ValidationResult(
                    status=ValidationStatus.INVALID,
                    message=f"Invalid clip file extension: {clip_path.suffix}",
                    timestamp=datetime.utcnow()
                )
            
            # Register for integrity monitoring
            await self.integrity_manager.register_file(clip_path)
            
            # Verify integrity
            integrity_result = await self.integrity_manager.verify_file(clip_path)
            
            if integrity_result.status == ValidationStatus.VALID:
                return ValidationResult(
                    status=ValidationStatus.VALID,
                    message=f"Clip validation successful: {clip_path}",
                    details={
                        'file_size': file_size,
                        'extension': clip_path.suffix,
                        'integrity_verified': True
                    },
                    timestamp=datetime.utcnow()
                )
            else:
                return integrity_result
                
        except Exception as e:
            logger.error(f"Error validating clip {clip_path}: {e}")
            return ValidationResult(
                status=ValidationStatus.INVALID,
                message=f"Validation error: {e}",
                timestamp=datetime.utcnow()
            )
    
    async def validate_clip_metadata(self, clip_data: Dict[str, Any]) -> ValidationResult:
        """Validate clip metadata."""
        try:
            required_fields = ['id', 'video_id', 'user_id', 'duration', 'platform']
            missing_fields = [field for field in required_fields if field not in clip_data]
            
            if missing_fields:
                return ValidationResult(
                    status=ValidationStatus.INVALID,
                    message=f"Missing required fields: {missing_fields}",
                    details={'missing_fields': missing_fields},
                    timestamp=datetime.utcnow()
                )
            
            # Validate duration
            duration = clip_data.get('duration')
            if not isinstance(duration, (int, float)) or duration <= 0:
                return ValidationResult(
                    status=ValidationStatus.INVALID,
                    message=f"Invalid duration: {duration}",
                    timestamp=datetime.utcnow()
                )
            
            # Validate platform
            valid_platforms = ['youtube', 'tiktok', 'instagram', 'twitter']
            platform = clip_data.get('platform')
            if platform not in valid_platforms:
                return ValidationResult(
                    status=ValidationStatus.INVALID,
                    message=f"Invalid platform: {platform}",
                    details={'valid_platforms': valid_platforms},
                    timestamp=datetime.utcnow()
                )
            
            return ValidationResult(
                status=ValidationStatus.VALID,
                message="Clip metadata validation successful",
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error validating clip metadata: {e}")
            return ValidationResult(
                status=ValidationStatus.INVALID,
                message=f"Metadata validation error: {e}",
                timestamp=datetime.utcnow()
            )


# Global instances
data_integrity_manager = DataIntegrityManager()
clip_validator = ClipValidator(data_integrity_manager)


def get_data_integrity_manager() -> DataIntegrityManager:
    """Get the global data integrity manager."""
    return data_integrity_manager


def get_clip_validator() -> ClipValidator:
    """Get the global clip validator."""
    return clip_validator