#!/usr/bin/env python3
"""
Automated Recovery System for Cliper Application
Provides restoration capabilities for database, files, and configurations from backups.
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
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from cryptography.fernet import Fernet
import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/cliper-recovery.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class RecoveryConfig:
    """Configuration for recovery operations"""
    # Database settings
    db_host: str = os.getenv('DB_HOST', 'localhost')
    db_port: int = int(os.getenv('DB_PORT', '5432'))
    db_name: str = os.getenv('DB_NAME', 'cliper')
    db_user: str = os.getenv('DB_USER', 'postgres')
    db_password: str = os.getenv('DB_PASSWORD', '')
    
    # Recovery paths
    backup_root: str = os.getenv('BACKUP_ROOT', '/backups')
    app_root: str = os.getenv('APP_ROOT', '/app')
    temp_dir: str = os.getenv('TEMP_DIR', '/tmp/cliper-recovery')
    
    # S3 settings
    s3_bucket: str = os.getenv('BACKUP_S3_BUCKET', '')
    s3_region: str = os.getenv('AWS_REGION', 'us-east-1')
    aws_access_key: str = os.getenv('AWS_ACCESS_KEY_ID', '')
    aws_secret_key: str = os.getenv('AWS_SECRET_ACCESS_KEY', '')
    
    # Encryption
    encryption_key: str = os.getenv('BACKUP_ENCRYPTION_KEY', '')
    
    # Recovery options
    create_backup_before_restore: bool = True
    verify_integrity: bool = True
    stop_services_during_restore: bool = True

class RecoveryManager:
    """Main recovery management class"""
    
    def __init__(self, config: RecoveryConfig):
        self.config = config
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create temp directory
        self.temp_dir = Path(config.temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
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
    
    def list_available_backups(self) -> List[Dict]:
        """List all available backups"""
        backups = []
        
        # Local backups
        backup_root = Path(self.config.backup_root)
        if backup_root.exists():
            for backup_dir in backup_root.iterdir():
                if backup_dir.is_dir():
                    manifest_file = backup_dir / 'manifest.json'
                    if manifest_file.exists():
                        try:
                            with open(manifest_file) as f:
                                manifest = json.load(f)
                            manifest['source'] = 'local'
                            manifest['path'] = str(backup_dir)
                            backups.append(manifest)
                        except Exception as e:
                            logger.warning(f"Failed to read manifest {manifest_file}: {e}")
        
        # S3 backups (if configured)
        if self.s3_client:
            try:
                response = self.s3_client.list_objects_v2(
                    Bucket=self.config.s3_bucket,
                    Prefix='backups/',
                    Delimiter='/'
                )
                
                for prefix in response.get('CommonPrefixes', []):
                    backup_prefix = prefix['Prefix']
                    manifest_key = f"{backup_prefix}manifest.json"
                    
                    try:
                        obj = self.s3_client.get_object(Bucket=self.config.s3_bucket, Key=manifest_key)
                        manifest = json.loads(obj['Body'].read())
                        manifest['source'] = 's3'
                        manifest['path'] = backup_prefix
                        backups.append(manifest)
                    except ClientError:
                        continue
                        
            except Exception as e:
                logger.warning(f"Failed to list S3 backups: {e}")
        
        # Sort by timestamp (newest first)
        backups.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return backups
    
    def download_from_s3(self, s3_key: str, local_path: str) -> bool:
        """Download file from S3"""
        if not self.s3_client:
            return False
        
        try:
            logger.info(f"Downloading {s3_key} from S3...")
            self.s3_client.download_file(self.config.s3_bucket, s3_key, local_path)
            logger.info(f"Download completed: {local_path}")
            return True
        except ClientError as e:
            logger.error(f"S3 download failed: {str(e)}")
            return False
    
    def decrypt_file(self, encrypted_file: str, output_file: str) -> bool:
        """Decrypt an encrypted backup file"""
        if not self.cipher:
            logger.error("Encryption key not available for decryption")
            return False
        
        try:
            with open(encrypted_file, 'rb') as f_in:
                encrypted_data = f_in.read()
                decrypted_data = self.cipher.decrypt(encrypted_data)
                
                with open(output_file, 'wb') as f_out:
                    f_out.write(decrypted_data)
            
            logger.info(f"File decrypted: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Decryption failed: {str(e)}")
            return False
    
    def decompress_file(self, compressed_file: str, output_file: str) -> bool:
        """Decompress a gzipped file"""
        try:
            with gzip.open(compressed_file, 'rb') as f_in:
                with open(output_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            logger.info(f"File decompressed: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Decompression failed: {str(e)}")
            return False
    
    def prepare_backup_file(self, backup_path: str, filename: str) -> Optional[str]:
        """Prepare backup file for restoration (download, decrypt, decompress)"""
        source_file = None
        
        # Determine source file path
        if backup_path.startswith('s3://'):
            # S3 backup
            s3_key = backup_path.replace('s3://' + self.config.s3_bucket + '/', '')
            s3_key = f"{s3_key}{filename}"
            source_file = self.temp_dir / filename
            
            if not self.download_from_s3(s3_key, str(source_file)):
                return None
        else:
            # Local backup
            source_file = Path(backup_path) / filename
            if not source_file.exists():
                logger.error(f"Backup file not found: {source_file}")
                return None
        
        current_file = str(source_file)
        
        # Decrypt if encrypted
        if current_file.endswith('.enc'):
            decrypted_file = current_file[:-4]  # Remove .enc extension
            if not self.decrypt_file(current_file, decrypted_file):
                return None
            current_file = decrypted_file
        
        # Decompress if compressed
        if current_file.endswith('.gz'):
            decompressed_file = current_file[:-3]  # Remove .gz extension
            if not self.decompress_file(current_file, decompressed_file):
                return None
            current_file = decompressed_file
        
        return current_file
    
    def stop_services(self) -> bool:
        """Stop application services before restoration"""
        if not self.config.stop_services_during_restore:
            return True
        
        try:
            logger.info("Stopping application services...")
            
            # Stop Docker Compose services
            cmd = ['docker-compose', 'down']
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.config.app_root)
            
            if result.returncode != 0:
                logger.warning(f"Failed to stop services: {result.stderr}")
                return False
            
            logger.info("Services stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop services: {str(e)}")
            return False
    
    def start_services(self) -> bool:
        """Start application services after restoration"""
        try:
            logger.info("Starting application services...")
            
            # Start Docker Compose services
            cmd = ['docker-compose', 'up', '-d']
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.config.app_root)
            
            if result.returncode != 0:
                logger.error(f"Failed to start services: {result.stderr}")
                return False
            
            logger.info("Services started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start services: {str(e)}")
            return False
    
    def restore_database(self, backup_path: str) -> Tuple[bool, str]:
        """Restore database from backup"""
        try:
            logger.info("Starting database restoration...")
            
            # Find database backup file
            db_files = [f for f in os.listdir(backup_path) if f.startswith('database_')]
            if not db_files:
                return False, "No database backup file found"
            
            db_file = db_files[0]
            prepared_file = self.prepare_backup_file(backup_path, db_file)
            
            if not prepared_file:
                return False, "Failed to prepare database backup file"
            
            # Create backup of current database if requested
            if self.config.create_backup_before_restore:
                logger.info("Creating backup of current database...")
                backup_cmd = [
                    'pg_dump',
                    '-h', self.config.db_host,
                    '-p', str(self.config.db_port),
                    '-U', self.config.db_user,
                    '-d', self.config.db_name,
                    '-f', str(self.temp_dir / f"pre_restore_db_{self.timestamp}.sql")
                ]
                
                env = os.environ.copy()
                env['PGPASSWORD'] = self.config.db_password
                
                subprocess.run(backup_cmd, env=env, check=False)
            
            # Restore database
            logger.info(f"Restoring database from {prepared_file}...")
            
            env = os.environ.copy()
            env['PGPASSWORD'] = self.config.db_password
            
            restore_cmd = [
                'psql',
                '-h', self.config.db_host,
                '-p', str(self.config.db_port),
                '-U', self.config.db_user,
                '-d', self.config.db_name,
                '-f', prepared_file
            ]
            
            result = subprocess.run(restore_cmd, env=env, capture_output=True, text=True)
            
            if result.returncode != 0:
                error_msg = f"Database restoration failed: {result.stderr}"
                logger.error(error_msg)
                return False, error_msg
            
            logger.info("Database restoration completed successfully")
            return True, "Database restored successfully"
            
        except Exception as e:
            error_msg = f"Database restoration failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def restore_files(self, backup_path: str) -> Tuple[bool, str]:
        """Restore application files from backup"""
        try:
            logger.info("Starting file restoration...")
            
            # Find files backup
            file_backups = [f for f in os.listdir(backup_path) if f.startswith('files_')]
            if not file_backups:
                return False, "No files backup found"
            
            files_file = file_backups[0]
            prepared_file = self.prepare_backup_file(backup_path, files_file)
            
            if not prepared_file:
                return False, "Failed to prepare files backup"
            
            # Create backup of current files if requested
            if self.config.create_backup_before_restore:
                logger.info("Creating backup of current files...")
                current_backup = self.temp_dir / f"pre_restore_files_{self.timestamp}.tar.gz"
                
                with tarfile.open(current_backup, 'w:gz') as tar:
                    app_root = Path(self.config.app_root)
                    for path in ['uploads', 'logs', 'config']:
                        full_path = app_root / path
                        if full_path.exists():
                            tar.add(full_path, arcname=path, recursive=True)
            
            # Extract files
            logger.info(f"Restoring files from {prepared_file}...")
            
            with tarfile.open(prepared_file, 'r:gz') as tar:
                tar.extractall(path=self.config.app_root)
            
            logger.info("File restoration completed successfully")
            return True, "Files restored successfully"
            
        except Exception as e:
            error_msg = f"File restoration failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def restore_redis(self, backup_path: str) -> Tuple[bool, str]:
        """Restore Redis data from backup"""
        try:
            logger.info("Starting Redis restoration...")
            
            # Find Redis backup
            redis_files = [f for f in os.listdir(backup_path) if f.startswith('redis_')]
            if not redis_files:
                return False, "No Redis backup found"
            
            redis_file = redis_files[0]
            prepared_file = self.prepare_backup_file(backup_path, redis_file)
            
            if not prepared_file:
                return False, "Failed to prepare Redis backup"
            
            # Stop Redis, restore data, start Redis
            logger.info("Stopping Redis service...")
            subprocess.run(['redis-cli', 'SHUTDOWN', 'NOSAVE'], check=False)
            
            # Copy backup file to Redis data directory
            redis_data_dir = '/var/lib/redis'  # Adjust as needed
            shutil.copy2(prepared_file, f"{redis_data_dir}/dump.rdb")
            
            # Start Redis
            logger.info("Starting Redis service...")
            subprocess.run(['systemctl', 'start', 'redis'], check=False)
            
            logger.info("Redis restoration completed successfully")
            return True, "Redis restored successfully"
            
        except Exception as e:
            error_msg = f"Redis restoration failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def verify_restoration(self) -> Tuple[bool, str]:
        """Verify that restoration was successful"""
        if not self.config.verify_integrity:
            return True, "Verification skipped"
        
        try:
            logger.info("Verifying restoration...")
            
            # Check database connectivity
            db_cmd = [
                'psql',
                '-h', self.config.db_host,
                '-p', str(self.config.db_port),
                '-U', self.config.db_user,
                '-d', self.config.db_name,
                '-c', 'SELECT 1;'
            ]
            
            env = os.environ.copy()
            env['PGPASSWORD'] = self.config.db_password
            
            result = subprocess.run(db_cmd, env=env, capture_output=True, text=True)
            if result.returncode != 0:
                return False, "Database verification failed"
            
            # Check Redis connectivity
            redis_result = subprocess.run(['redis-cli', 'ping'], capture_output=True, text=True)
            if redis_result.returncode != 0 or 'PONG' not in redis_result.stdout:
                return False, "Redis verification failed"
            
            # Check critical files
            app_root = Path(self.config.app_root)
            critical_files = ['requirements.txt', 'package.json', 'docker-compose.yml']
            
            for file in critical_files:
                if not (app_root / file).exists():
                    return False, f"Critical file missing: {file}"
            
            logger.info("Restoration verification completed successfully")
            return True, "Restoration verified successfully"
            
        except Exception as e:
            error_msg = f"Verification failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def run_recovery(self, backup_timestamp: str, components: List[str] = None) -> Dict:
        """Run complete recovery process"""
        logger.info(f"Starting recovery process for backup: {backup_timestamp}")
        
        if components is None:
            components = ['database', 'files', 'redis']
        
        results = {
            'timestamp': self.timestamp,
            'backup_timestamp': backup_timestamp,
            'success': True,
            'errors': [],
            'components_restored': []
        }
        
        # Find backup
        backups = self.list_available_backups()
        backup = None
        
        for b in backups:
            if b['timestamp'] == backup_timestamp:
                backup = b
                break
        
        if not backup:
            results['success'] = False
            results['errors'].append(f"Backup not found: {backup_timestamp}")
            return results
        
        backup_path = backup['path']
        
        try:
            # Stop services
            if not self.stop_services():
                results['errors'].append("Failed to stop services")
            
            # Restore components
            if 'database' in components:
                db_success, db_result = self.restore_database(backup_path)
                if db_success:
                    results['components_restored'].append('database')
                else:
                    results['success'] = False
                    results['errors'].append(db_result)
            
            if 'files' in components:
                files_success, files_result = self.restore_files(backup_path)
                if files_success:
                    results['components_restored'].append('files')
                else:
                    results['success'] = False
                    results['errors'].append(files_result)
            
            if 'redis' in components:
                redis_success, redis_result = self.restore_redis(backup_path)
                if redis_success:
                    results['components_restored'].append('redis')
                else:
                    results['success'] = False
                    results['errors'].append(redis_result)
            
            # Start services
            if not self.start_services():
                results['errors'].append("Failed to start services")
            
            # Verify restoration
            verify_success, verify_result = self.verify_restoration()
            if not verify_success:
                results['success'] = False
                results['errors'].append(verify_result)
            
        except Exception as e:
            results['success'] = False
            results['errors'].append(f"Recovery process failed: {str(e)}")
        
        finally:
            # Cleanup temp files
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                pass
        
        logger.info(f"Recovery process completed: {results['success']}")
        return results

def main():
    parser = argparse.ArgumentParser(description='Cliper Recovery System')
    parser.add_argument('--list', action='store_true', help='List available backups')
    parser.add_argument('--restore', help='Backup timestamp to restore')
    parser.add_argument('--components', nargs='+', choices=['database', 'files', 'redis'], 
                       help='Components to restore (default: all)')
    parser.add_argument('--config', help='Path to configuration file')
    parser.add_argument('--dry-run', action='store_true', help='Perform dry run without actual restoration')
    
    args = parser.parse_args()
    
    # Load configuration
    config = RecoveryConfig()
    
    if args.config and os.path.exists(args.config):
        with open(args.config) as f:
            config_data = json.load(f)
            for key, value in config_data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
    
    # Initialize recovery manager
    recovery_manager = RecoveryManager(config)
    
    if args.list:
        backups = recovery_manager.list_available_backups()
        print("\nAvailable Backups:")
        print("-" * 80)
        for backup in backups:
            print(f"Timestamp: {backup['timestamp']}")
            print(f"Date: {backup.get('date', 'Unknown')}")
            print(f"Source: {backup['source']}")
            print(f"Success: {backup.get('results', {}).get('success', 'Unknown')}")
            print(f"Files: {len(backup.get('results', {}).get('files', []))}")
            print("-" * 40)
        return
    
    if not args.restore:
        parser.error("--restore is required (use --list to see available backups)")
    
    if args.dry_run:
        logger.info("Dry run mode - no actual restoration will be performed")
        logger.info(f"Would restore backup: {args.restore}")
        logger.info(f"Components: {args.components or ['all']}")
        return
    
    # Run recovery
    results = recovery_manager.run_recovery(args.restore, args.components)
    
    # Print results
    print("\nRecovery Results:")
    print(f"Success: {results['success']}")
    print(f"Components Restored: {', '.join(results['components_restored'])}")
    if results['errors']:
        print(f"Errors: {'; '.join(results['errors'])}")
    
    # Exit with appropriate code
    sys.exit(0 if results['success'] else 1)

if __name__ == '__main__':
    main()