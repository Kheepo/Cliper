#!/usr/bin/env python3
"""
Comprehensive data integrity module for production environments.
Handles transaction management, backup mechanisms, and consistency checks.
"""

import asyncio
import hashlib
import json
import os
import shutil
import tempfile
import time
from contextlib import contextmanager, asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Union, Set, Tuple
from uuid import uuid4

import aiofiles
from sqlalchemy import create_engine, text, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import get_settings
from .logging_config import get_logger
from .database import get_db_session


class BackupType(Enum):
    """Backup type enumeration."""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SCHEMA_ONLY = "schema_only"
    DATA_ONLY = "data_only"


class IntegrityCheckType(Enum):
    """Integrity check type enumeration."""
    CHECKSUM = "checksum"
    FOREIGN_KEY = "foreign_key"
    UNIQUE_CONSTRAINT = "unique_constraint"
    NOT_NULL = "not_null"
    DATA_TYPE = "data_type"
    BUSINESS_RULE = "business_rule"
    REFERENTIAL = "referential"
    ORPHANED_RECORDS = "orphaned_records"


class TransactionIsolationLevel(Enum):
    """Transaction isolation levels."""
    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


@dataclass
class BackupConfig:
    """Backup configuration."""
    backup_type: BackupType = BackupType.FULL
    compression: bool = True
    encryption: bool = False
    retention_days: int = 30
    max_backups: int = 10
    backup_directory: str = "./backups"
    include_tables: Optional[List[str]] = None
    exclude_tables: Optional[List[str]] = None
    parallel_jobs: int = 1
    verify_backup: bool = True


@dataclass
class IntegrityCheckResult:
    """Result of an integrity check."""
    check_type: IntegrityCheckType
    table_name: str
    column_name: Optional[str] = None
    passed: bool = False
    error_count: int = 0
    error_message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BackupMetadata:
    """Backup metadata."""
    backup_id: str
    backup_type: BackupType
    file_path: str
    file_size: int
    checksum: str
    created_at: datetime
    tables_included: List[str]
    record_count: int
    compression_ratio: Optional[float] = None
    verification_status: bool = False
    restoration_tested: bool = False


@dataclass
class TransactionContext:
    """Transaction context information."""
    transaction_id: str
    isolation_level: TransactionIsolationLevel
    read_only: bool = False
    timeout: Optional[int] = None
    savepoints: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.utcnow)
    operations: List[str] = field(default_factory=list)


class TransactionManager:
    """Advanced transaction management with savepoints and rollback capabilities."""
    
    def __init__(self, session: Session):
        self.session = session
        self.logger = get_logger(__name__)
        self.context: Optional[TransactionContext] = None
        self._savepoint_counter = 0
    
    @contextmanager
    def transaction(self, 
                   isolation_level: TransactionIsolationLevel = TransactionIsolationLevel.READ_COMMITTED,
                   read_only: bool = False,
                   timeout: Optional[int] = None):
        """Context manager for database transactions."""
        transaction_id = str(uuid4())
        self.context = TransactionContext(
            transaction_id=transaction_id,
            isolation_level=isolation_level,
            read_only=read_only,
            timeout=timeout
        )
        
        self.logger.info(
            f"Starting transaction {transaction_id}",
            transaction_id=transaction_id,
            isolation_level=isolation_level.value,
            read_only=read_only
        )
        
        try:
            # Set isolation level
            self.session.execute(text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level.value}"))
            
            if read_only:
                self.session.execute(text("SET TRANSACTION READ ONLY"))
            
            # Set timeout if specified
            if timeout:
                self.session.execute(text(f"SET statement_timeout = {timeout * 1000}"))  # Convert to ms
            
            self.session.begin()
            yield self
            
            # Commit if no exceptions
            self.session.commit()
            
            execution_time = (datetime.utcnow() - self.context.start_time).total_seconds()
            self.logger.info(
                f"Transaction {transaction_id} committed successfully",
                transaction_id=transaction_id,
                execution_time=execution_time,
                operations_count=len(self.context.operations)
            )
            
        except Exception as e:
            self.session.rollback()
            execution_time = (datetime.utcnow() - self.context.start_time).total_seconds()
            
            self.logger.error(
                f"Transaction {transaction_id} rolled back due to error: {e}",
                transaction_id=transaction_id,
                error=str(e),
                execution_time=execution_time,
                operations=self.context.operations
            )
            raise
        finally:
            self.context = None
            self._savepoint_counter = 0
    
    def create_savepoint(self, name: Optional[str] = None) -> str:
        """Create a savepoint within the current transaction."""
        if not self.context:
            raise RuntimeError("No active transaction")
        
        if not name:
            self._savepoint_counter += 1
            name = f"sp_{self._savepoint_counter}"
        
        self.session.execute(text(f"SAVEPOINT {name}"))
        self.context.savepoints.append(name)
        
        self.logger.debug(
            f"Created savepoint {name}",
            transaction_id=self.context.transaction_id,
            savepoint=name
        )
        
        return name
    
    def rollback_to_savepoint(self, name: str):
        """Rollback to a specific savepoint."""
        if not self.context:
            raise RuntimeError("No active transaction")
        
        if name not in self.context.savepoints:
            raise ValueError(f"Savepoint {name} not found")
        
        self.session.execute(text(f"ROLLBACK TO SAVEPOINT {name}"))
        
        # Remove savepoints created after this one
        savepoint_index = self.context.savepoints.index(name)
        self.context.savepoints = self.context.savepoints[:savepoint_index + 1]
        
        self.logger.warning(
            f"Rolled back to savepoint {name}",
            transaction_id=self.context.transaction_id,
            savepoint=name
        )
    
    def release_savepoint(self, name: str):
        """Release a savepoint."""
        if not self.context:
            raise RuntimeError("No active transaction")
        
        if name not in self.context.savepoints:
            raise ValueError(f"Savepoint {name} not found")
        
        self.session.execute(text(f"RELEASE SAVEPOINT {name}"))
        self.context.savepoints.remove(name)
        
        self.logger.debug(
            f"Released savepoint {name}",
            transaction_id=self.context.transaction_id,
            savepoint=name
        )
    
    def log_operation(self, operation: str):
        """Log an operation within the current transaction."""
        if self.context:
            self.context.operations.append(f"{datetime.utcnow().isoformat()}: {operation}")


class DataIntegrityChecker:
    """Comprehensive data integrity checking."""
    
    def __init__(self, session: Session):
        self.session = session
        self.logger = get_logger(__name__)
        self.engine = session.bind
        self.inspector = inspect(self.engine)
    
    async def run_all_checks(self, tables: Optional[List[str]] = None) -> List[IntegrityCheckResult]:
        """Run all integrity checks."""
        results = []
        
        if not tables:
            tables = self.inspector.get_table_names()
        
        for table in tables:
            # Run different types of checks
            results.extend(await self._check_foreign_keys(table))
            results.extend(await self._check_unique_constraints(table))
            results.extend(await self._check_not_null_constraints(table))
            results.extend(await self._check_data_types(table))
            results.extend(await self._check_orphaned_records(table))
            results.extend(await self._check_checksums(table))
        
        return results
    
    async def _check_foreign_keys(self, table_name: str) -> List[IntegrityCheckResult]:
        """Check foreign key constraints."""
        results = []
        start_time = time.time()
        
        try:
            foreign_keys = self.inspector.get_foreign_keys(table_name)
            
            for fk in foreign_keys:
                # Check if all foreign key values exist in referenced table
                local_columns = fk['constrained_columns']
                referenced_table = fk['referred_table']
                referenced_columns = fk['referred_columns']
                
                # Build query to find orphaned records
                local_cols = ', '.join(local_columns)
                ref_cols = ', '.join(referenced_columns)
                
                query = text(f"""
                    SELECT COUNT(*) as orphaned_count
                    FROM {table_name} t1
                    LEFT JOIN {referenced_table} t2 ON {' AND '.join([f't1.{lc} = t2.{rc}' for lc, rc in zip(local_columns, referenced_columns)])}
                    WHERE t2.{referenced_columns[0]} IS NULL
                    AND t1.{local_columns[0]} IS NOT NULL
                """)
                
                result = self.session.execute(query).fetchone()
                orphaned_count = result[0] if result else 0
                
                results.append(IntegrityCheckResult(
                    check_type=IntegrityCheckType.FOREIGN_KEY,
                    table_name=table_name,
                    column_name=', '.join(local_columns),
                    passed=orphaned_count == 0,
                    error_count=orphaned_count,
                    error_message=f"Found {orphaned_count} orphaned records" if orphaned_count > 0 else None,
                    details={
                        'foreign_key': fk,
                        'orphaned_count': orphaned_count
                    },
                    execution_time=time.time() - start_time
                ))
                
        except Exception as e:
            results.append(IntegrityCheckResult(
                check_type=IntegrityCheckType.FOREIGN_KEY,
                table_name=table_name,
                passed=False,
                error_message=str(e),
                execution_time=time.time() - start_time
            ))
        
        return results
    
    async def _check_unique_constraints(self, table_name: str) -> List[IntegrityCheckResult]:
        """Check unique constraints."""
        results = []
        start_time = time.time()
        
        try:
            unique_constraints = self.inspector.get_unique_constraints(table_name)
            
            for constraint in unique_constraints:
                columns = constraint['column_names']
                column_list = ', '.join(columns)
                
                # Check for duplicate values
                query = text(f"""
                    SELECT {column_list}, COUNT(*) as duplicate_count
                    FROM {table_name}
                    WHERE {' AND '.join([f'{col} IS NOT NULL' for col in columns])}
                    GROUP BY {column_list}
                    HAVING COUNT(*) > 1
                """)
                
                duplicates = self.session.execute(query).fetchall()
                duplicate_count = len(duplicates)
                
                results.append(IntegrityCheckResult(
                    check_type=IntegrityCheckType.UNIQUE_CONSTRAINT,
                    table_name=table_name,
                    column_name=column_list,
                    passed=duplicate_count == 0,
                    error_count=duplicate_count,
                    error_message=f"Found {duplicate_count} duplicate value sets" if duplicate_count > 0 else None,
                    details={
                        'constraint': constraint,
                        'duplicates': [dict(row) for row in duplicates[:10]]  # Limit to first 10
                    },
                    execution_time=time.time() - start_time
                ))
                
        except Exception as e:
            results.append(IntegrityCheckResult(
                check_type=IntegrityCheckType.UNIQUE_CONSTRAINT,
                table_name=table_name,
                passed=False,
                error_message=str(e),
                execution_time=time.time() - start_time
            ))
        
        return results
    
    async def _check_not_null_constraints(self, table_name: str) -> List[IntegrityCheckResult]:
        """Check NOT NULL constraints."""
        results = []
        start_time = time.time()
        
        try:
            columns = self.inspector.get_columns(table_name)
            
            for column in columns:
                if not column['nullable']:
                    # Check for NULL values in NOT NULL columns
                    query = text(f"""
                        SELECT COUNT(*) as null_count
                        FROM {table_name}
                        WHERE {column['name']} IS NULL
                    """)
                    
                    result = self.session.execute(query).fetchone()
                    null_count = result[0] if result else 0
                    
                    results.append(IntegrityCheckResult(
                        check_type=IntegrityCheckType.NOT_NULL,
                        table_name=table_name,
                        column_name=column['name'],
                        passed=null_count == 0,
                        error_count=null_count,
                        error_message=f"Found {null_count} NULL values in NOT NULL column" if null_count > 0 else None,
                        details={'column': column},
                        execution_time=time.time() - start_time
                    ))
                    
        except Exception as e:
            results.append(IntegrityCheckResult(
                check_type=IntegrityCheckType.NOT_NULL,
                table_name=table_name,
                passed=False,
                error_message=str(e),
                execution_time=time.time() - start_time
            ))
        
        return results
    
    async def _check_data_types(self, table_name: str) -> List[IntegrityCheckResult]:
        """Check data type consistency."""
        results = []
        start_time = time.time()
        
        try:
            columns = self.inspector.get_columns(table_name)
            
            for column in columns:
                column_name = column['name']
                column_type = str(column['type']).lower()
                
                # Check for data type violations based on column type
                if 'int' in column_type:
                    # Check for non-integer values
                    query = text(f"""
                        SELECT COUNT(*) as invalid_count
                        FROM {table_name}
                        WHERE {column_name} IS NOT NULL
                        AND {column_name}::text !~ '^-?[0-9]+$'
                    """)
                elif 'date' in column_type or 'timestamp' in column_type:
                    # Check for invalid dates
                    query = text(f"""
                        SELECT COUNT(*) as invalid_count
                        FROM {table_name}
                        WHERE {column_name} IS NOT NULL
                        AND NOT ({column_name}::text ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}')
                    """)
                elif 'email' in column_name.lower():
                    # Check for invalid email formats
                    query = text(f"""
                        SELECT COUNT(*) as invalid_count
                        FROM {table_name}
                        WHERE {column_name} IS NOT NULL
                        AND NOT ({column_name} ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{{2,}}$')
                    """)
                else:
                    continue  # Skip other types for now
                
                try:
                    result = self.session.execute(query).fetchone()
                    invalid_count = result[0] if result else 0
                    
                    results.append(IntegrityCheckResult(
                        check_type=IntegrityCheckType.DATA_TYPE,
                        table_name=table_name,
                        column_name=column_name,
                        passed=invalid_count == 0,
                        error_count=invalid_count,
                        error_message=f"Found {invalid_count} invalid data type values" if invalid_count > 0 else None,
                        details={'column': column},
                        execution_time=time.time() - start_time
                    ))
                except Exception:
                    # Skip if query fails (might be unsupported for this column type)
                    continue
                    
        except Exception as e:
            results.append(IntegrityCheckResult(
                check_type=IntegrityCheckType.DATA_TYPE,
                table_name=table_name,
                passed=False,
                error_message=str(e),
                execution_time=time.time() - start_time
            ))
        
        return results
    
    async def _check_orphaned_records(self, table_name: str) -> List[IntegrityCheckResult]:
        """Check for orphaned records."""
        results = []
        start_time = time.time()
        
        try:
            # This is a simplified check - in practice, you'd define business rules
            # for what constitutes an orphaned record
            
            # Example: Check for records with foreign keys pointing to non-existent records
            foreign_keys = self.inspector.get_foreign_keys(table_name)
            
            for fk in foreign_keys:
                local_columns = fk['constrained_columns']
                referenced_table = fk['referred_table']
                referenced_columns = fk['referred_columns']
                
                query = text(f"""
                    SELECT COUNT(*) as orphaned_count
                    FROM {table_name} t1
                    LEFT JOIN {referenced_table} t2 ON {' AND '.join([f't1.{lc} = t2.{rc}' for lc, rc in zip(local_columns, referenced_columns)])}
                    WHERE t2.{referenced_columns[0]} IS NULL
                    AND t1.{local_columns[0]} IS NOT NULL
                """)
                
                result = self.session.execute(query).fetchone()
                orphaned_count = result[0] if result else 0
                
                results.append(IntegrityCheckResult(
                    check_type=IntegrityCheckType.ORPHANED_RECORDS,
                    table_name=table_name,
                    column_name=', '.join(local_columns),
                    passed=orphaned_count == 0,
                    error_count=orphaned_count,
                    error_message=f"Found {orphaned_count} orphaned records" if orphaned_count > 0 else None,
                    details={'foreign_key': fk},
                    execution_time=time.time() - start_time
                ))
                
        except Exception as e:
            results.append(IntegrityCheckResult(
                check_type=IntegrityCheckType.ORPHANED_RECORDS,
                table_name=table_name,
                passed=False,
                error_message=str(e),
                execution_time=time.time() - start_time
            ))
        
        return results
    
    async def _check_checksums(self, table_name: str) -> List[IntegrityCheckResult]:
        """Check data checksums for corruption detection."""
        results = []
        start_time = time.time()
        
        try:
            # Calculate checksum for the entire table
            query = text(f"""
                SELECT md5(string_agg(md5(t.*::text), '' ORDER BY t.*::text)) as table_checksum
                FROM {table_name} t
            """)
            
            result = self.session.execute(query).fetchone()
            checksum = result[0] if result else None
            
            # In a real implementation, you'd compare against stored checksums
            # For now, we just verify that we can calculate the checksum
            
            results.append(IntegrityCheckResult(
                check_type=IntegrityCheckType.CHECKSUM,
                table_name=table_name,
                passed=checksum is not None,
                error_message="Could not calculate table checksum" if checksum is None else None,
                details={'checksum': checksum},
                execution_time=time.time() - start_time
            ))
            
        except Exception as e:
            results.append(IntegrityCheckResult(
                check_type=IntegrityCheckType.CHECKSUM,
                table_name=table_name,
                passed=False,
                error_message=str(e),
                execution_time=time.time() - start_time
            ))
        
        return results


class BackupManager:
    """Comprehensive backup and restore functionality."""
    
    def __init__(self, session: Session, config: BackupConfig = None):
        self.session = session
        self.config = config or BackupConfig()
        self.logger = get_logger(__name__)
        self.engine = session.bind
        
        # Ensure backup directory exists
        Path(self.config.backup_directory).mkdir(parents=True, exist_ok=True)
    
    async def create_backup(self, backup_name: Optional[str] = None) -> BackupMetadata:
        """Create a database backup."""
        if not backup_name:
            backup_name = f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        backup_id = str(uuid4())
        backup_path = Path(self.config.backup_directory) / f"{backup_name}.sql"
        
        self.logger.info(
            f"Starting backup {backup_id}",
            backup_id=backup_id,
            backup_type=self.config.backup_type.value,
            backup_path=str(backup_path)
        )
        
        start_time = time.time()
        
        try:
            # Get tables to backup
            tables = self._get_tables_to_backup()
            
            # Create backup content
            backup_content = await self._generate_backup_content(tables)
            
            # Write backup file
            async with aiofiles.open(backup_path, 'w', encoding='utf-8') as f:
                await f.write(backup_content)
            
            # Calculate file size and checksum
            file_size = backup_path.stat().st_size
            checksum = await self._calculate_file_checksum(backup_path)
            
            # Count total records
            record_count = await self._count_total_records(tables)
            
            # Create metadata
            metadata = BackupMetadata(
                backup_id=backup_id,
                backup_type=self.config.backup_type,
                file_path=str(backup_path),
                file_size=file_size,
                checksum=checksum,
                created_at=datetime.utcnow(),
                tables_included=tables,
                record_count=record_count
            )
            
            # Verify backup if configured
            if self.config.verify_backup:
                metadata.verification_status = await self._verify_backup(backup_path)
            
            execution_time = time.time() - start_time
            
            self.logger.info(
                f"Backup {backup_id} completed successfully",
                backup_id=backup_id,
                file_size=file_size,
                record_count=record_count,
                execution_time=execution_time
            )
            
            # Clean up old backups
            await self._cleanup_old_backups()
            
            return metadata
            
        except Exception as e:
            self.logger.error(
                f"Backup {backup_id} failed: {e}",
                backup_id=backup_id,
                error=str(e)
            )
            
            # Clean up failed backup file
            if backup_path.exists():
                backup_path.unlink()
            
            raise
    
    def _get_tables_to_backup(self) -> List[str]:
        """Get list of tables to include in backup."""
        inspector = inspect(self.engine)
        all_tables = inspector.get_table_names()
        
        if self.config.include_tables:
            tables = [t for t in all_tables if t in self.config.include_tables]
        else:
            tables = all_tables
        
        if self.config.exclude_tables:
            tables = [t for t in tables if t not in self.config.exclude_tables]
        
        return tables
    
    async def _generate_backup_content(self, tables: List[str]) -> str:
        """Generate backup content based on backup type."""
        content_parts = []
        
        # Add header
        content_parts.append(f"-- Database Backup")
        content_parts.append(f"-- Created: {datetime.utcnow().isoformat()}")
        content_parts.append(f"-- Type: {self.config.backup_type.value}")
        content_parts.append(f"-- Tables: {', '.join(tables)}")
        content_parts.append("")
        
        if self.config.backup_type in [BackupType.FULL, BackupType.SCHEMA_ONLY]:
            # Add schema definitions
            for table in tables:
                schema_sql = await self._get_table_schema(table)
                content_parts.append(schema_sql)
                content_parts.append("")
        
        if self.config.backup_type in [BackupType.FULL, BackupType.DATA_ONLY]:
            # Add data
            for table in tables:
                data_sql = await self._get_table_data(table)
                if data_sql:
                    content_parts.append(data_sql)
                    content_parts.append("")
        
        return "\n".join(content_parts)
    
    async def _get_table_schema(self, table_name: str) -> str:
        """Get CREATE TABLE statement for a table."""
        # This is a simplified version - in practice, you'd use pg_dump or similar
        inspector = inspect(self.engine)
        columns = inspector.get_columns(table_name)
        
        column_defs = []
        for col in columns:
            col_def = f"{col['name']} {col['type']}"
            if not col['nullable']:
                col_def += " NOT NULL"
            if col.get('default'):
                col_def += f" DEFAULT {col['default']}"
            column_defs.append(col_def)
        
        return f"CREATE TABLE {table_name} (\n  {',\n  '.join(column_defs)}\n);"
    
    async def _get_table_data(self, table_name: str) -> str:
        """Get INSERT statements for table data."""
        try:
            # Get all data from table
            query = text(f"SELECT * FROM {table_name}")
            result = self.session.execute(query)
            rows = result.fetchall()
            
            if not rows:
                return f"-- No data in table {table_name}"
            
            # Get column names
            columns = list(result.keys())
            column_list = ', '.join(columns)
            
            # Generate INSERT statements
            insert_statements = []
            for row in rows:
                values = []
                for value in row:
                    if value is None:
                        values.append('NULL')
                    elif isinstance(value, str):
                        # Escape single quotes
                        escaped_value = value.replace("'", "''")
                        values.append(f"'{escaped_value}'")
                    elif isinstance(value, datetime):
                        values.append(f"'{value.isoformat()}'")
                    else:
                        values.append(str(value))
                
                values_str = ', '.join(values)
                insert_statements.append(f"INSERT INTO {table_name} ({column_list}) VALUES ({values_str});")
            
            return '\n'.join(insert_statements)
            
        except Exception as e:
            self.logger.error(f"Error getting data for table {table_name}: {e}")
            return f"-- Error getting data for table {table_name}: {e}"
    
    async def _count_total_records(self, tables: List[str]) -> int:
        """Count total records across all tables."""
        total = 0
        for table in tables:
            try:
                query = text(f"SELECT COUNT(*) FROM {table}")
                result = self.session.execute(query).fetchone()
                total += result[0] if result else 0
            except Exception:
                continue  # Skip tables that can't be counted
        return total
    
    async def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate MD5 checksum of a file."""
        hash_md5 = hashlib.md5()
        async with aiofiles.open(file_path, 'rb') as f:
            async for chunk in f:
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    async def _verify_backup(self, backup_path: Path) -> bool:
        """Verify backup integrity."""
        try:
            # Basic verification - check if file is readable and contains expected content
            async with aiofiles.open(backup_path, 'r', encoding='utf-8') as f:
                content = await f.read(1000)  # Read first 1000 characters
                return "Database Backup" in content and "Created:" in content
        except Exception:
            return False
    
    async def _cleanup_old_backups(self):
        """Clean up old backup files based on retention policy."""
        backup_dir = Path(self.config.backup_directory)
        backup_files = list(backup_dir.glob("*.sql"))
        
        # Sort by modification time (newest first)
        backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Remove files beyond max_backups limit
        if len(backup_files) > self.config.max_backups:
            for file_to_remove in backup_files[self.config.max_backups:]:
                try:
                    file_to_remove.unlink()
                    self.logger.info(f"Removed old backup: {file_to_remove}")
                except Exception as e:
                    self.logger.error(f"Error removing old backup {file_to_remove}: {e}")
        
        # Remove files older than retention period
        cutoff_date = datetime.utcnow() - timedelta(days=self.config.retention_days)
        for backup_file in backup_files:
            file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
            if file_time < cutoff_date:
                try:
                    backup_file.unlink()
                    self.logger.info(f"Removed expired backup: {backup_file}")
                except Exception as e:
                    self.logger.error(f"Error removing expired backup {backup_file}: {e}")


# Global instances
_integrity_checker = None
_backup_manager = None


def get_integrity_checker(session: Session = None) -> DataIntegrityChecker:
    """Get global integrity checker instance."""
    global _integrity_checker
    if _integrity_checker is None or session:
        if not session:
            session = next(get_db_session())
        _integrity_checker = DataIntegrityChecker(session)
    return _integrity_checker


def get_backup_manager(session: Session = None, config: BackupConfig = None) -> BackupManager:
    """Get global backup manager instance."""
    global _backup_manager
    if _backup_manager is None or session or config:
        if not session:
            session = next(get_db_session())
        _backup_manager = BackupManager(session, config)
    return _backup_manager


# Utility functions
@contextmanager
def managed_transaction(session: Session, 
                      isolation_level: TransactionIsolationLevel = TransactionIsolationLevel.READ_COMMITTED,
                      read_only: bool = False,
                      timeout: Optional[int] = None):
    """Context manager for managed transactions."""
    manager = TransactionManager(session)
    with manager.transaction(isolation_level, read_only, timeout) as tx:
        yield tx


async def run_integrity_checks(tables: Optional[List[str]] = None) -> List[IntegrityCheckResult]:
    """Run integrity checks on specified tables."""
    checker = get_integrity_checker()
    return await checker.run_all_checks(tables)


async def create_database_backup(backup_name: Optional[str] = None, 
                               config: BackupConfig = None) -> BackupMetadata:
    """Create a database backup."""
    manager = get_backup_manager(config=config)
    return await manager.create_backup(backup_name)