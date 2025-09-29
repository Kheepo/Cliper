"""Backup and recovery utilities for the clip generation system.

Provides:
- Automated backup scheduling
- Database backup and restore
- File system backup and restore
- Disaster recovery procedures
- Point-in-time recovery
- Backup verification and testing
"""

import os
import shutil
import tempfile
import tarfile
import gzip
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum

import aiofiles
import asyncpg
from pydantic import BaseModel

from api.utils.enhanced_logging import get_logger
from api.config.production import get_settings
from api.utils.data_integrity import DataIntegrityManager, ValidationResult, ValidationStatus


logger = get_logger(__name__)
settings = get_settings()


class BackupType(str, Enum):
    """Types of backups."""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"


class BackupStatus(str, Enum):
    """Backup status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CORRUPTED = "corrupted"
    VERIFIED = "verified"


class RecoveryStatus(str, Enum):
    """Recovery status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class BackupMetadata:
    """Backup metadata."""
    backup_id: str
    backup_type: BackupType
    created_at: datetime
    completed_at: Optional[datetime]
    status: BackupStatus
    file_path: str
    file_size: int
    checksum: str
    description: str
    includes: List[str]  # What was backed up
    excludes: List[str]  # What was excluded
    compression: bool
    encryption: bool
    retention_days: int
    tags: Dict[str, str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        data['backup_type'] = self.backup_type.value
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BackupMetadata':
        """Create from dictionary."""
        return cls(
            backup_id=data['backup_id'],
            backup_type=BackupType(data['backup_type']),
            created_at=datetime.fromisoformat(data['created_at']),
            completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
            status=BackupStatus(data['status']),
            file_path=data['file_path'],
            file_size=data['file_size'],
            checksum=data['checksum'],
            description=data['description'],
            includes=data['includes'],
            excludes=data['excludes'],
            compression=data['compression'],
            encryption=data['encryption'],
            retention_days=data['retention_days'],
            tags=data['tags']
        )


@dataclass
class RecoveryPoint:
    """Recovery point information."""
    point_id: str
    timestamp: datetime
    backup_id: str
    description: str
    database_state: Dict[str, Any]
    file_state: Dict[str, Any]
    application_state: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'point_id': self.point_id,
            'timestamp': self.timestamp.isoformat(),
            'backup_id': self.backup_id,
            'description': self.description,
            'database_state': self.database_state,
            'file_state': self.file_state,
            'application_state': self.application_state
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RecoveryPoint':
        """Create from dictionary."""
        return cls(
            point_id=data['point_id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            backup_id=data['backup_id'],
            description=data['description'],
            database_state=data['database_state'],
            file_state=data['file_state'],
            application_state=data['application_state']
        )


class BackupManager:
    """Manages backup operations."""
    
    def __init__(self, backup_dir: Optional[str] = None, 
                 integrity_manager: Optional[DataIntegrityManager] = None):
        self.backup_dir = Path(backup_dir or settings.storage.backup_dir)
        self.integrity_manager = integrity_manager or DataIntegrityManager()
        self.metadata_file = self.backup_dir / "backup_metadata.json"
        self.recovery_points_file = self.backup_dir / "recovery_points.json"
        
        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing metadata
        self.backups: Dict[str, BackupMetadata] = {}
        self.recovery_points: Dict[str, RecoveryPoint] = {}
        
        asyncio.create_task(self._load_metadata())
        
        # Start cleanup scheduler
        asyncio.create_task(self._cleanup_scheduler())
    
    async def create_full_backup(self, description: str = "", 
                               tags: Optional[Dict[str, str]] = None) -> BackupMetadata:
        """Create a full system backup."""
        backup_id = f"full_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            logger.info(f"Starting full backup: {backup_id}")
            
            # Create backup metadata
            metadata = BackupMetadata(
                backup_id=backup_id,
                backup_type=BackupType.FULL,
                created_at=datetime.utcnow(),
                completed_at=None,
                status=BackupStatus.IN_PROGRESS,
                file_path="",
                file_size=0,
                checksum="",
                description=description or f"Full backup created at {datetime.utcnow()}",
                includes=["database", "files", "config", "logs"],
                excludes=["temp", "cache"],
                compression=True,
                encryption=False,
                retention_days=30,
                tags=tags or {}
            )
            
            # Create backup archive
            backup_path = self.backup_dir / f"{backup_id}.tar.gz"
            
            with tarfile.open(backup_path, 'w:gz') as tar:
                # Backup database
                db_backup_path = await self._backup_database()
                if db_backup_path:
                    tar.add(db_backup_path, arcname="database.sql")
                
                # Backup files
                files_to_backup = [
                    settings.storage.upload_dir,
                    settings.storage.temp_dir,
                    "api/config",
                    "api/logs"
                ]
                
                for file_path in files_to_backup:
                    path = Path(file_path)
                    if path.exists():
                        if path.is_file():
                            tar.add(path, arcname=path.name)
                        else:
                            tar.add(path, arcname=path.name, recursive=True)
            
            # Calculate checksum
            checksum = await self.integrity_manager.calculate_checksum(backup_path)
            
            # Update metadata
            metadata.file_path = str(backup_path)
            metadata.file_size = backup_path.stat().st_size
            metadata.checksum = checksum
            metadata.completed_at = datetime.utcnow()
            metadata.status = BackupStatus.COMPLETED
            
            # Register with integrity manager
            await self.integrity_manager.register_file(backup_path)
            
            # Save metadata
            self.backups[backup_id] = metadata
            await self._save_metadata()
            
            # Create recovery point
            await self._create_recovery_point(backup_id, "Full backup recovery point")
            
            logger.info(f"Full backup completed: {backup_id} ({metadata.file_size} bytes)")
            return metadata
            
        except Exception as e:
            logger.error(f"Error creating full backup {backup_id}: {e}")
            if backup_id in self.backups:
                self.backups[backup_id].status = BackupStatus.FAILED
                await self._save_metadata()
            raise
    
    async def create_incremental_backup(self, base_backup_id: str, 
                                      description: str = "",
                                      tags: Optional[Dict[str, str]] = None) -> BackupMetadata:
        """Create an incremental backup."""
        backup_id = f"inc_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            logger.info(f"Starting incremental backup: {backup_id}")
            
            # Verify base backup exists
            if base_backup_id not in self.backups:
                raise ValueError(f"Base backup not found: {base_backup_id}")
            
            base_backup = self.backups[base_backup_id]
            if base_backup.status != BackupStatus.COMPLETED:
                raise ValueError(f"Base backup is not completed: {base_backup_id}")
            
            # Create backup metadata
            metadata = BackupMetadata(
                backup_id=backup_id,
                backup_type=BackupType.INCREMENTAL,
                created_at=datetime.utcnow(),
                completed_at=None,
                status=BackupStatus.IN_PROGRESS,
                file_path="",
                file_size=0,
                checksum="",
                description=description or f"Incremental backup from {base_backup_id}",
                includes=["database_changes", "new_files", "modified_files"],
                excludes=["temp", "cache"],
                compression=True,
                encryption=False,
                retention_days=7,
                tags={**tags, "base_backup": base_backup_id} if tags else {"base_backup": base_backup_id}
            )
            
            # Create incremental backup
            backup_path = self.backup_dir / f"{backup_id}.tar.gz"
            
            with tarfile.open(backup_path, 'w:gz') as tar:
                # Backup only changes since base backup
                cutoff_time = base_backup.created_at
                
                # Find modified files
                modified_files = await self._find_modified_files(cutoff_time)
                
                for file_path in modified_files:
                    path = Path(file_path)
                    if path.exists():
                        tar.add(path, arcname=str(path.relative_to(Path.cwd())))
                
                # Create change log
                change_log = {
                    'base_backup': base_backup_id,
                    'cutoff_time': cutoff_time.isoformat(),
                    'modified_files': modified_files,
                    'created_at': datetime.utcnow().isoformat()
                }
                
                # Add change log to archive
                change_log_path = tempfile.mktemp(suffix='.json')
                with open(change_log_path, 'w') as f:
                    json.dump(change_log, f, indent=2)
                
                tar.add(change_log_path, arcname="change_log.json")
                os.unlink(change_log_path)
            
            # Calculate checksum
            checksum = await self.integrity_manager.calculate_checksum(backup_path)
            
            # Update metadata
            metadata.file_path = str(backup_path)
            metadata.file_size = backup_path.stat().st_size
            metadata.checksum = checksum
            metadata.completed_at = datetime.utcnow()
            metadata.status = BackupStatus.COMPLETED
            
            # Register with integrity manager
            await self.integrity_manager.register_file(backup_path)
            
            # Save metadata
            self.backups[backup_id] = metadata
            await self._save_metadata()
            
            logger.info(f"Incremental backup completed: {backup_id} ({metadata.file_size} bytes)")
            return metadata
            
        except Exception as e:
            logger.error(f"Error creating incremental backup {backup_id}: {e}")
            if backup_id in self.backups:
                self.backups[backup_id].status = BackupStatus.FAILED
                await self._save_metadata()
            raise
    
    async def restore_backup(self, backup_id: str, 
                           restore_path: Optional[str] = None) -> bool:
        """Restore from backup."""
        try:
            logger.info(f"Starting restore from backup: {backup_id}")
            
            if backup_id not in self.backups:
                logger.error(f"Backup not found: {backup_id}")
                return False
            
            backup = self.backups[backup_id]
            backup_path = Path(backup.file_path)
            
            if not backup_path.exists():
                logger.error(f"Backup file not found: {backup_path}")
                return False
            
            # Verify backup integrity
            verification = await self.integrity_manager.verify_file(backup_path)
            if verification.status != ValidationStatus.VALID:
                logger.error(f"Backup integrity check failed: {verification.message}")
                return False
            
            # Determine restore path
            if restore_path is None:
                restore_path = tempfile.mkdtemp(prefix="restore_")
            
            restore_dir = Path(restore_path)
            restore_dir.mkdir(parents=True, exist_ok=True)
            
            # Extract backup
            with tarfile.open(backup_path, 'r:gz') as tar:
                tar.extractall(restore_dir)
            
            # Restore database if present
            db_file = restore_dir / "database.sql"
            if db_file.exists():
                await self._restore_database(db_file)
            
            # Restore files
            for item in restore_dir.iterdir():
                if item.name not in ["database.sql", "change_log.json"]:
                    target_path = Path.cwd() / item.name
                    if item.is_file():
                        shutil.copy2(item, target_path)
                    else:
                        if target_path.exists():
                            shutil.rmtree(target_path)
                        shutil.copytree(item, target_path)
            
            logger.info(f"Restore completed from backup: {backup_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error restoring backup {backup_id}: {e}")
            return False
    
    async def verify_backup(self, backup_id: str) -> ValidationResult:
        """Verify backup integrity."""
        try:
            if backup_id not in self.backups:
                return ValidationResult(
                    status=ValidationStatus.INVALID,
                    message=f"Backup not found: {backup_id}",
                    timestamp=datetime.utcnow()
                )
            
            backup = self.backups[backup_id]
            backup_path = Path(backup.file_path)
            
            # Verify file exists
            if not backup_path.exists():
                backup.status = BackupStatus.CORRUPTED
                await self._save_metadata()
                
                return ValidationResult(
                    status=ValidationStatus.MISSING,
                    message=f"Backup file missing: {backup_path}",
                    timestamp=datetime.utcnow()
                )
            
            # Verify integrity
            verification = await self.integrity_manager.verify_file(backup_path)
            
            if verification.status == ValidationStatus.VALID:
                backup.status = BackupStatus.VERIFIED
                await self._save_metadata()
            else:
                backup.status = BackupStatus.CORRUPTED
                await self._save_metadata()
            
            return verification
            
        except Exception as e:
            logger.error(f"Error verifying backup {backup_id}: {e}")
            return ValidationResult(
                status=ValidationStatus.INVALID,
                message=f"Verification error: {e}",
                timestamp=datetime.utcnow()
            )
    
    async def list_backups(self, backup_type: Optional[BackupType] = None,
                         status: Optional[BackupStatus] = None) -> List[BackupMetadata]:
        """List available backups."""
        backups = list(self.backups.values())
        
        if backup_type:
            backups = [b for b in backups if b.backup_type == backup_type]
        
        if status:
            backups = [b for b in backups if b.status == status]
        
        # Sort by creation time (newest first)
        backups.sort(key=lambda b: b.created_at, reverse=True)
        
        return backups
    
    async def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup."""
        try:
            if backup_id not in self.backups:
                logger.error(f"Backup not found: {backup_id}")
                return False
            
            backup = self.backups[backup_id]
            backup_path = Path(backup.file_path)
            
            # Remove file
            if backup_path.exists():
                backup_path.unlink()
            
            # Remove from integrity manager
            if str(backup_path) in self.integrity_manager.checksums:
                del self.integrity_manager.checksums[str(backup_path)]
            
            # Remove metadata
            del self.backups[backup_id]
            await self._save_metadata()
            
            logger.info(f"Deleted backup: {backup_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting backup {backup_id}: {e}")
            return False
    
    async def _backup_database(self) -> Optional[str]:
        """Create database backup."""
        try:
            # Create temporary file for database dump
            db_backup_path = tempfile.mktemp(suffix='.sql')
            
            # Use pg_dump to create backup
            import subprocess
            
            cmd = [
                'pg_dump',
                '--host', settings.database.host,
                '--port', str(settings.database.port),
                '--username', settings.database.user,
                '--dbname', settings.database.name,
                '--file', db_backup_path,
                '--verbose',
                '--clean',
                '--create'
            ]
            
            env = os.environ.copy()
            env['PGPASSWORD'] = settings.database.password
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Database backup created: {db_backup_path}")
                return db_backup_path
            else:
                logger.error(f"Database backup failed: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating database backup: {e}")
            return None
    
    async def _restore_database(self, backup_file: Path) -> bool:
        """Restore database from backup."""
        try:
            import subprocess
            
            cmd = [
                'psql',
                '--host', settings.database.host,
                '--port', str(settings.database.port),
                '--username', settings.database.user,
                '--dbname', settings.database.name,
                '--file', str(backup_file)
            ]
            
            env = os.environ.copy()
            env['PGPASSWORD'] = settings.database.password
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Database restored from: {backup_file}")
                return True
            else:
                logger.error(f"Database restore failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error restoring database: {e}")
            return False
    
    async def _find_modified_files(self, cutoff_time: datetime) -> List[str]:
        """Find files modified after cutoff time."""
        modified_files = []
        
        search_paths = [
            settings.storage.upload_dir,
            settings.storage.temp_dir,
            "api/config",
            "api/logs"
        ]
        
        for search_path in search_paths:
            path = Path(search_path)
            if path.exists():
                for file_path in path.rglob('*'):
                    if file_path.is_file():
                        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if mtime > cutoff_time:
                            modified_files.append(str(file_path))
        
        return modified_files
    
    async def _create_recovery_point(self, backup_id: str, description: str):
        """Create a recovery point."""
        point_id = f"rp_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        recovery_point = RecoveryPoint(
            point_id=point_id,
            timestamp=datetime.utcnow(),
            backup_id=backup_id,
            description=description,
            database_state={"tables": [], "version": "1.0"},
            file_state={"total_files": 0, "total_size": 0},
            application_state={"version": "1.0", "status": "healthy"}
        )
        
        self.recovery_points[point_id] = recovery_point
        await self._save_recovery_points()
    
    async def _load_metadata(self):
        """Load backup metadata."""
        try:
            if self.metadata_file.exists():
                async with aiofiles.open(self.metadata_file, 'r') as f:
                    data = json.loads(await f.read())
                    
                    for backup_id, backup_data in data.items():
                        self.backups[backup_id] = BackupMetadata.from_dict(backup_data)
                
                logger.info(f"Loaded {len(self.backups)} backup records")
            
            if self.recovery_points_file.exists():
                async with aiofiles.open(self.recovery_points_file, 'r') as f:
                    data = json.loads(await f.read())
                    
                    for point_id, point_data in data.items():
                        self.recovery_points[point_id] = RecoveryPoint.from_dict(point_data)
                
                logger.info(f"Loaded {len(self.recovery_points)} recovery points")
                
        except Exception as e:
            logger.error(f"Error loading backup metadata: {e}")
    
    async def _save_metadata(self):
        """Save backup metadata."""
        try:
            data = {}
            for backup_id, backup in self.backups.items():
                data[backup_id] = backup.to_dict()
            
            async with aiofiles.open(self.metadata_file, 'w') as f:
                await f.write(json.dumps(data, indent=2))
                
        except Exception as e:
            logger.error(f"Error saving backup metadata: {e}")
    
    async def _save_recovery_points(self):
        """Save recovery points."""
        try:
            data = {}
            for point_id, point in self.recovery_points.items():
                data[point_id] = point.to_dict()
            
            async with aiofiles.open(self.recovery_points_file, 'w') as f:
                await f.write(json.dumps(data, indent=2))
                
        except Exception as e:
            logger.error(f"Error saving recovery points: {e}")
    
    async def _cleanup_scheduler(self):
        """Background cleanup scheduler."""
        while True:
            try:
                await asyncio.sleep(86400)  # Run daily
                
                logger.info("Starting backup cleanup")
                
                # Clean up expired backups
                current_time = datetime.utcnow()
                expired_backups = []
                
                for backup_id, backup in self.backups.items():
                    if backup.created_at + timedelta(days=backup.retention_days) < current_time:
                        expired_backups.append(backup_id)
                
                for backup_id in expired_backups:
                    await self.delete_backup(backup_id)
                
                logger.info(f"Cleaned up {len(expired_backups)} expired backups")
                
            except Exception as e:
                logger.error(f"Error in backup cleanup scheduler: {e}")


# Global instance
backup_manager = BackupManager()


def get_backup_manager() -> BackupManager:
    """Get the global backup manager."""
    return backup_manager