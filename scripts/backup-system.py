#!/usr/bin/env python3
"""
Automated Backup and Recovery System for Cliper Application
Supports database, file, and configuration backups with encryption and compression.
"""

import os
import sys
import json
import gzip
import shutil
import tarfile
import logging
import argparse
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from cryptography.fernet import Fernet
import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/cliper-backup.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class BackupConfig:
    """Configuration for backup operations"""
    # Database settings
    db_host: str = os.getenv('DB_HOST', 'localhost')
    db_port: int = int(os.getenv('DB_PORT', '5432'))
    db_name: str = os.getenv('DB_NAME', 'cliper')
    db_user: str = os.getenv('DB_USER', 'postgres')
    db_password: str = os.getenv('DB_PASSWORD', '')
    
    # Backup paths
    backup_root: str = os.getenv('BACKUP_ROOT', '/backups')
    app_root: str = os.getenv('APP_ROOT', '/app')
    
    # S3 settings
    s3_bucket: str = os.getenv('BACKUP_S3_BUCKET', '')
    s3_region: str = os.getenv('AWS_REGION', 'us-east-1')
    aws_access_key: str = os.getenv('AWS_ACCESS_KEY_ID', '')
    aws_secret_key: str = os.getenv('AWS_SECRET_ACCESS_KEY', '')
    
    # Encryption
    encryption_key: str = os.getenv('BACKUP_ENCRYPTION_KEY', '')
    
    # Retention settings
    daily_retention: int = int(os.getenv('BACKUP_DAILY_RETENTION', '7'))
    weekly_retention: int = int(os.getenv('BACKUP_WEEKLY_RETENTION', '4'))
    monthly_retention: int = int(os.getenv('BACKUP_MONTHLY_RETENTION', '12'))
    
    # Compression
    compression_level: int = int(os.getenv('BACKUP_COMPRESSION_LEVEL', '6'))
    
    # Notification
    notification_webhook: str = os.getenv('BACKUP_NOTIFICATION_WEBHOOK', '')
    notification_email: str = os.getenv('BACKUP_NOTIFICATION_EMAIL', '')

class BackupManager:
    """Main backup management class"""
    
    def __init__(self, config: BackupConfig):
        self.config = config
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.backup_dir = Path(config.backup_root) / self.timestamp
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize encryption if key is provided
        self.cipher = None
        if config.encryption_key:
            try:
                self.cipher = Fernet(config.encryption_key.encode())
            except Exception as e:
                logger.warning(f"Failed to initialize encryption: {e}")
        
        # Initialize S3 client if configured
        self.s3_client = None
        if config.s3_bucket and config.aws_access_key:
            try:
                self.s3_client = boto3.client(
                    's3',
                    region_name=config.s3_region,
                    aws_access_key_id=config.aws_access_key,
                    aws_secret_access_key=config.aws_secret_key
                )
            except Exception as e:
                logger.warning(f"Failed to initialize S3 client: {e}")
    
    def backup_database(self) -> Tuple[bool, str]:
        """Backup PostgreSQL database"""
        try:
            logger.info("Starting database backup...")
            
            # Create database dump
            dump_file = self.backup_dir / f"database_{self.timestamp}.sql"
            
            # Set PGPASSWORD environment variable
            env = os.environ.copy()
            env['PGPASSWORD'] = self.config.db_password
            
            # Run pg_dump
            cmd = [
                'pg_dump',
                '-h', self.config.db_host,
                '-p', str(self.config.db_port),
                '-U', self.config.db_user,
                '-d', self.config.db_name,
                '--no-password',
                '--verbose',
                '--clean',
                '--if-exists',
                '--create',
                '-f', str(dump_file)
            ]
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode != 0:
                error_msg = f"Database backup failed: {result.stderr}"
                logger.error(error_msg)
                return False, error_msg
            
            # Compress the dump
            compressed_file = dump_file.with_suffix('.sql.gz')
            with open(dump_file, 'rb') as f_in:
                with gzip.open(compressed_file, 'wb', compresslevel=self.config.compression_level) as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Remove uncompressed file
            dump_file.unlink()
            
            # Encrypt if configured
            if self.cipher:
                encrypted_file = compressed_file.with_suffix('.sql.gz.enc')
                with open(compressed_file, 'rb') as f_in:
                    encrypted_data = self.cipher.encrypt(f_in.read())
                    with open(encrypted_file, 'wb') as f_out:
                        f_out.write(encrypted_data)
                compressed_file.unlink()
                final_file = encrypted_file
            else:
                final_file = compressed_file
            
            logger.info(f"Database backup completed: {final_file}")
            return True, str(final_file)
            
        except Exception as e:
            error_msg = f"Database backup failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def backup_files(self) -> Tuple[bool, str]:
        """Backup application files"""
        try:
            logger.info("Starting file backup...")
            
            # Define directories to backup
            backup_paths = [
                'uploads',
                'logs',
                'config',
                '.env',
                'requirements.txt',
                'package.json',
                'docker-compose.yml',
                'Dockerfile',
                'nginx'
            ]
            
            # Create tar archive
            archive_file = self.backup_dir / f"files_{self.timestamp}.tar.gz"
            
            with tarfile.open(archive_file, 'w:gz', compresslevel=self.config.compression_level) as tar:
                app_root = Path(self.config.app_root)
                
                for path in backup_paths:
                    full_path = app_root / path
                    if full_path.exists():
                        if full_path.is_file():
                            tar.add(full_path, arcname=path)
                        else:
                            tar.add(full_path, arcname=path, recursive=True)
                        logger.info(f"Added to archive: {path}")
                    else:
                        logger.warning(f"Path not found, skipping: {path}")
            
            # Encrypt if configured
            if self.cipher:
                encrypted_file = archive_file.with_suffix('.tar.gz.enc')
                with open(archive_file, 'rb') as f_in:
                    encrypted_data = self.cipher.encrypt(f_in.read())
                    with open(encrypted_file, 'wb') as f_out:
                        f_out.write(encrypted_data)
                archive_file.unlink()
                final_file = encrypted_file
            else:
                final_file = archive_file
            
            logger.info(f"File backup completed: {final_file}")
            return True, str(final_file)
            
        except Exception as e:
            error_msg = f"File backup failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def backup_redis(self) -> Tuple[bool, str]:
        """Backup Redis data"""
        try:
            logger.info("Starting Redis backup...")
            
            # Create Redis dump
            redis_file = self.backup_dir / f"redis_{self.timestamp}.rdb"
            
            # Use redis-cli to create backup
            cmd = ['redis-cli', '--rdb', str(redis_file)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                error_msg = f"Redis backup failed: {result.stderr}"
                logger.error(error_msg)
                return False, error_msg
            
            # Compress the dump
            compressed_file = redis_file.with_suffix('.rdb.gz')
            with open(redis_file, 'rb') as f_in:
                with gzip.open(compressed_file, 'wb', compresslevel=self.config.compression_level) as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            redis_file.unlink()
            
            # Encrypt if configured
            if self.cipher:
                encrypted_file = compressed_file.with_suffix('.rdb.gz.enc')
                with open(compressed_file, 'rb') as f_in:
                    encrypted_data = self.cipher.encrypt(f_in.read())
                    with open(encrypted_file, 'wb') as f_out:
                        f_out.write(encrypted_data)
                compressed_file.unlink()
                final_file = encrypted_file
            else:
                final_file = compressed_file
            
            logger.info(f"Redis backup completed: {final_file}")
            return True, str(final_file)
            
        except Exception as e:
            error_msg = f"Redis backup failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def upload_to_s3(self, file_path: str) -> Tuple[bool, str]:
        """Upload backup file to S3"""
        if not self.s3_client or not self.config.s3_bucket:
            return False, "S3 not configured"
        
        try:
            file_path = Path(file_path)
            s3_key = f"backups/{self.timestamp}/{file_path.name}"
            
            logger.info(f"Uploading {file_path.name} to S3...")
            
            self.s3_client.upload_file(
                str(file_path),
                self.config.s3_bucket,
                s3_key,
                ExtraArgs={
                    'ServerSideEncryption': 'AES256',
                    'StorageClass': 'STANDARD_IA'
                }
            )
            
            s3_url = f"s3://{self.config.s3_bucket}/{s3_key}"
            logger.info(f"Upload completed: {s3_url}")
            return True, s3_url
            
        except ClientError as e:
            error_msg = f"S3 upload failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def create_backup_manifest(self, backup_results: Dict) -> str:
        """Create backup manifest file"""
        manifest = {
            'timestamp': self.timestamp,
            'date': datetime.now().isoformat(),
            'config': asdict(self.config),
            'results': backup_results,
            'backup_dir': str(self.backup_dir)
        }
        
        manifest_file = self.backup_dir / 'manifest.json'
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        logger.info(f"Backup manifest created: {manifest_file}")
        return str(manifest_file)
    
    def cleanup_old_backups(self):
        """Clean up old backup files based on retention policy"""
        try:
            logger.info("Starting backup cleanup...")
            
            backup_root = Path(self.config.backup_root)
            if not backup_root.exists():
                return
            
            now = datetime.now()
            
            for backup_dir in backup_root.iterdir():
                if not backup_dir.is_dir():
                    continue
                
                try:
                    # Parse timestamp from directory name
                    dir_timestamp = datetime.strptime(backup_dir.name, '%Y%m%d_%H%M%S')
                    age_days = (now - dir_timestamp).days
                    
                    # Determine if backup should be kept
                    should_delete = False
                    
                    if age_days > self.config.monthly_retention * 30:
                        should_delete = True
                    elif age_days > self.config.weekly_retention * 7 and dir_timestamp.weekday() != 6:  # Keep Sunday backups
                        should_delete = True
                    elif age_days > self.config.daily_retention:
                        should_delete = True
                    
                    if should_delete:
                        logger.info(f"Removing old backup: {backup_dir}")
                        shutil.rmtree(backup_dir)
                    
                except ValueError:
                    # Skip directories that don't match timestamp format
                    continue
            
            logger.info("Backup cleanup completed")
            
        except Exception as e:
            logger.error(f"Backup cleanup failed: {str(e)}")
    
    def send_notification(self, success: bool, message: str):
        """Send backup notification"""
        try:
            if self.config.notification_webhook:
                import requests
                
                payload = {
                    'timestamp': self.timestamp,
                    'success': success,
                    'message': message,
                    'backup_dir': str(self.backup_dir)
                }
                
                response = requests.post(self.config.notification_webhook, json=payload, timeout=30)
                response.raise_for_status()
                logger.info("Notification sent successfully")
                
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
    
    def run_backup(self) -> Dict:
        """Run complete backup process"""
        logger.info(f"Starting backup process: {self.timestamp}")
        
        results = {
            'timestamp': self.timestamp,
            'success': True,
            'errors': [],
            'files': []
        }
        
        # Backup database
        db_success, db_result = self.backup_database()
        if db_success:
            results['files'].append(db_result)
            # Upload to S3 if configured
            if self.s3_client:
                s3_success, s3_result = self.upload_to_s3(db_result)
                if s3_success:
                    results['files'].append(s3_result)
        else:
            results['success'] = False
            results['errors'].append(db_result)
        
        # Backup files
        files_success, files_result = self.backup_files()
        if files_success:
            results['files'].append(files_result)
            # Upload to S3 if configured
            if self.s3_client:
                s3_success, s3_result = self.upload_to_s3(files_result)
                if s3_success:
                    results['files'].append(s3_result)
        else:
            results['success'] = False
            results['errors'].append(files_result)
        
        # Backup Redis
        redis_success, redis_result = self.backup_redis()
        if redis_success:
            results['files'].append(redis_result)
            # Upload to S3 if configured
            if self.s3_client:
                s3_success, s3_result = self.upload_to_s3(redis_result)
                if s3_success:
                    results['files'].append(s3_result)
        else:
            results['success'] = False
            results['errors'].append(redis_result)
        
        # Create manifest
        manifest_file = self.create_backup_manifest(results)
        results['manifest'] = manifest_file
        
        # Cleanup old backups
        self.cleanup_old_backups()
        
        # Send notification
        if results['success']:
            message = f"Backup completed successfully: {len(results['files'])} files created"
        else:
            message = f"Backup completed with errors: {'; '.join(results['errors'])}"
        
        self.send_notification(results['success'], message)
        
        logger.info(f"Backup process completed: {results['success']}")
        return results

def main():
    parser = argparse.ArgumentParser(description='Cliper Backup System')
    parser.add_argument('--config', help='Path to configuration file')
    parser.add_argument('--dry-run', action='store_true', help='Perform dry run without actual backup')
    parser.add_argument('--cleanup-only', action='store_true', help='Only perform cleanup of old backups')
    
    args = parser.parse_args()
    
    # Load configuration
    config = BackupConfig()
    
    if args.config and os.path.exists(args.config):
        with open(args.config) as f:
            config_data = json.load(f)
            for key, value in config_data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
    
    # Initialize backup manager
    backup_manager = BackupManager(config)
    
    if args.cleanup_only:
        backup_manager.cleanup_old_backups()
        return
    
    if args.dry_run:
        logger.info("Dry run mode - no actual backup will be performed")
        logger.info(f"Backup directory would be: {backup_manager.backup_dir}")
        logger.info(f"Configuration: {asdict(config)}")
        return
    
    # Run backup
    results = backup_manager.run_backup()
    
    # Exit with appropriate code
    sys.exit(0 if results['success'] else 1)

if __name__ == '__main__':
    main()