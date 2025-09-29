#!/usr/bin/env python3
"""Production deployment script for clip generation system.

This script handles:
- Environment validation
- Database migrations
- Docker deployment
- Health checks
- Rollback capabilities
- Monitoring setup
"""

import os
import sys
import json
import time
import subprocess
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import shutil
import tempfile

try:
    import docker
    import requests
    import yaml
except ImportError as e:
    print(f"Missing required dependency: {e}")
    print("Install with: pip install docker requests pyyaml")
    sys.exit(1)


class DeploymentError(Exception):
    """Custom exception for deployment errors."""
    pass


class Logger:
    """Simple logger for deployment operations."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
    
    def info(self, message: str):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] INFO: {message}")
    
    def error(self, message: str):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] ERROR: {message}", file=sys.stderr)
    
    def warning(self, message: str):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] WARNING: {message}")
    
    def debug(self, message: str):
        if self.verbose:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{timestamp}] DEBUG: {message}")


class DeploymentManager:
    """Manages the deployment process."""
    
    def __init__(self, config_file: str = 'deployment.yml', verbose: bool = False):
        self.logger = Logger(verbose)
        self.config_file = config_file
        self.config = self._load_config()
        self.docker_client = None
        self.backup_dir = None
        
        # Initialize Docker client
        try:
            self.docker_client = docker.from_env()
            self.logger.debug("Docker client initialized")
        except Exception as e:
            raise DeploymentError(f"Failed to initialize Docker client: {e}")
    
    def _load_config(self) -> Dict:
        """Load deployment configuration."""
        config_path = Path(self.config_file)
        
        if not config_path.exists():
            self.logger.warning(f"Config file {self.config_file} not found, using defaults")
            return self._get_default_config()
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            self.logger.debug(f"Configuration loaded from {self.config_file}")
            return config
        except Exception as e:
            raise DeploymentError(f"Failed to load config file: {e}")
    
    def _get_default_config(self) -> Dict:
        """Get default deployment configuration."""
        return {
            'app_name': 'cliper',
            'environment': 'production',
            'docker': {
                'compose_file': 'docker-compose.yml',
                'build_target': 'production',
                'services': ['app', 'worker', 'beat', 'redis', 'nginx']
            },
            'health_checks': {
                'timeout': 300,
                'interval': 10,
                'endpoints': [
                    {'url': 'http://localhost:8000/health', 'expected_status': 200}
                ]
            },
            'backup': {
                'enabled': True,
                'retention_days': 7
            },
            'monitoring': {
                'enabled': True,
                'prometheus_port': 9090,
                'grafana_port': 3000
            }
        }
    
    def validate_environment(self) -> bool:
        """Validate deployment environment."""
        self.logger.info("Validating deployment environment...")
        
        # Check required files
        required_files = [
            'Dockerfile',
            'docker-compose.yml',
            'requirements.txt',
            '.env'
        ]
        
        missing_files = []
        for file_path in required_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            self.logger.error(f"Missing required files: {', '.join(missing_files)}")
            return False
        
        # Check environment variables
        required_env_vars = [
            'SECRET_KEY',
            'SUPABASE_URL',
            'SUPABASE_ANON_KEY',
            'SUPABASE_SERVICE_ROLE_KEY'
        ]
        
        missing_env_vars = []
        for env_var in required_env_vars:
            if not os.getenv(env_var):
                missing_env_vars.append(env_var)
        
        if missing_env_vars:
            self.logger.error(f"Missing required environment variables: {', '.join(missing_env_vars)}")
            return False
        
        # Check Docker
        try:
            self.docker_client.ping()
            self.logger.debug("Docker daemon is running")
        except Exception as e:
            self.logger.error(f"Docker daemon not accessible: {e}")
            return False
        
        # Check disk space
        disk_usage = shutil.disk_usage('.')
        free_gb = disk_usage.free / (1024**3)
        if free_gb < 5.0:  # Require at least 5GB free
            self.logger.error(f"Insufficient disk space: {free_gb:.1f}GB free (minimum 5GB required)")
            return False
        
        self.logger.info("Environment validation passed")
        return True
    
    def create_backup(self) -> str:
        """Create backup of current deployment."""
        if not self.config.get('backup', {}).get('enabled', True):
            self.logger.info("Backup disabled, skipping...")
            return None
        
        self.logger.info("Creating deployment backup...")
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"backup_{timestamp}"
        self.backup_dir = Path(f"backups/{backup_name}")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Backup configuration files
            config_files = ['.env', 'docker-compose.yml', 'nginx.conf']
            for config_file in config_files:
                if Path(config_file).exists():
                    shutil.copy2(config_file, self.backup_dir)
            
            # Backup Docker images
            self._backup_docker_images()
            
            # Backup volumes
            self._backup_docker_volumes()
            
            self.logger.info(f"Backup created: {self.backup_dir}")
            return str(self.backup_dir)
        
        except Exception as e:
            self.logger.error(f"Backup failed: {e}")
            raise DeploymentError(f"Backup creation failed: {e}")
    
    def _backup_docker_images(self):
        """Backup current Docker images."""
        try:
            app_name = self.config.get('app_name', 'cliper')
            images = self.docker_client.images.list(name=f"{app_name}*")
            
            for image in images:
                if image.tags:
                    tag = image.tags[0]
                    backup_file = self.backup_dir / f"{tag.replace(':', '_').replace('/', '_')}.tar"
                    
                    self.logger.debug(f"Backing up image: {tag}")
                    with open(backup_file, 'wb') as f:
                        for chunk in image.save():
                            f.write(chunk)
        
        except Exception as e:
            self.logger.warning(f"Image backup failed: {e}")
    
    def _backup_docker_volumes(self):
        """Backup Docker volumes."""
        try:
            volumes = self.docker_client.volumes.list()
            app_name = self.config.get('app_name', 'cliper')
            
            for volume in volumes:
                if app_name in volume.name:
                    self.logger.debug(f"Backing up volume: {volume.name}")
                    # Note: Volume backup would require additional implementation
                    # depending on the volume driver and storage backend
        
        except Exception as e:
            self.logger.warning(f"Volume backup failed: {e}")
    
    def build_images(self) -> bool:
        """Build Docker images."""
        self.logger.info("Building Docker images...")
        
        try:
            compose_file = self.config.get('docker', {}).get('compose_file', 'docker-compose.yml')
            build_target = self.config.get('docker', {}).get('build_target', 'production')
            
            # Set environment variables for build
            env = os.environ.copy()
            env['BUILD_TARGET'] = build_target
            env['ENVIRONMENT'] = self.config.get('environment', 'production')
            
            # Build images
            cmd = ['docker-compose', '-f', compose_file, 'build', '--no-cache']
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"Image build failed: {result.stderr}")
                return False
            
            self.logger.info("Docker images built successfully")
            return True
        
        except Exception as e:
            self.logger.error(f"Image build error: {e}")
            return False
    
    def deploy_services(self) -> bool:
        """Deploy services using Docker Compose."""
        self.logger.info("Deploying services...")
        
        try:
            compose_file = self.config.get('docker', {}).get('compose_file', 'docker-compose.yml')
            services = self.config.get('docker', {}).get('services', [])
            
            # Set environment variables
            env = os.environ.copy()
            env['ENVIRONMENT'] = self.config.get('environment', 'production')
            env['BUILD_TARGET'] = self.config.get('docker', {}).get('build_target', 'production')
            
            # Deploy services
            if services:
                cmd = ['docker-compose', '-f', compose_file, 'up', '-d'] + services
            else:
                cmd = ['docker-compose', '-f', compose_file, 'up', '-d']
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"Service deployment failed: {result.stderr}")
                return False
            
            self.logger.info("Services deployed successfully")
            return True
        
        except Exception as e:
            self.logger.error(f"Service deployment error: {e}")
            return False
    
    def run_health_checks(self) -> bool:
        """Run health checks on deployed services."""
        self.logger.info("Running health checks...")
        
        health_config = self.config.get('health_checks', {})
        timeout = health_config.get('timeout', 300)
        interval = health_config.get('interval', 10)
        endpoints = health_config.get('endpoints', [])
        
        if not endpoints:
            self.logger.warning("No health check endpoints configured")
            return True
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            all_healthy = True
            
            for endpoint in endpoints:
                url = endpoint.get('url')
                expected_status = endpoint.get('expected_status', 200)
                
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == expected_status:
                        self.logger.debug(f"Health check passed: {url}")
                    else:
                        self.logger.debug(f"Health check failed: {url} (status: {response.status_code})")
                        all_healthy = False
                
                except Exception as e:
                    self.logger.debug(f"Health check failed: {url} (error: {e})")
                    all_healthy = False
            
            if all_healthy:
                self.logger.info("All health checks passed")
                return True
            
            time.sleep(interval)
        
        self.logger.error("Health checks failed within timeout period")
        return False
    
    def setup_monitoring(self) -> bool:
        """Setup monitoring services."""
        monitoring_config = self.config.get('monitoring', {})
        
        if not monitoring_config.get('enabled', True):
            self.logger.info("Monitoring disabled, skipping setup...")
            return True
        
        self.logger.info("Setting up monitoring...")
        
        try:
            # Deploy monitoring services
            cmd = ['docker-compose', 'up', '-d', '--profile', 'monitoring']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.warning(f"Monitoring setup failed: {result.stderr}")
                return False
            
            self.logger.info("Monitoring services deployed")
            return True
        
        except Exception as e:
            self.logger.error(f"Monitoring setup error: {e}")
            return False
    
    def rollback(self, backup_path: str) -> bool:
        """Rollback to previous deployment."""
        self.logger.info(f"Rolling back to backup: {backup_path}")
        
        try:
            # Stop current services
            cmd = ['docker-compose', 'down']
            subprocess.run(cmd, capture_output=True)
            
            # Restore configuration files
            backup_dir = Path(backup_path)
            config_files = ['.env', 'docker-compose.yml', 'nginx.conf']
            
            for config_file in config_files:
                backup_file = backup_dir / config_file
                if backup_file.exists():
                    shutil.copy2(backup_file, config_file)
            
            # Restore Docker images
            for image_file in backup_dir.glob('*.tar'):
                self.logger.debug(f"Restoring image: {image_file}")
                with open(image_file, 'rb') as f:
                    self.docker_client.images.load(f.read())
            
            # Restart services
            cmd = ['docker-compose', 'up', '-d']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"Rollback failed: {result.stderr}")
                return False
            
            self.logger.info("Rollback completed successfully")
            return True
        
        except Exception as e:
            self.logger.error(f"Rollback error: {e}")
            return False
    
    def cleanup_old_backups(self):
        """Clean up old backup files."""
        backup_config = self.config.get('backup', {})
        retention_days = backup_config.get('retention_days', 7)
        
        if not backup_config.get('enabled', True):
            return
        
        self.logger.info(f"Cleaning up backups older than {retention_days} days...")
        
        try:
            backups_dir = Path('backups')
            if not backups_dir.exists():
                return
            
            cutoff_time = time.time() - (retention_days * 24 * 60 * 60)
            
            for backup_dir in backups_dir.iterdir():
                if backup_dir.is_dir() and backup_dir.stat().st_mtime < cutoff_time:
                    self.logger.debug(f"Removing old backup: {backup_dir}")
                    shutil.rmtree(backup_dir)
        
        except Exception as e:
            self.logger.warning(f"Backup cleanup failed: {e}")
    
    def deploy(self) -> bool:
        """Run full deployment process."""
        self.logger.info("Starting deployment process...")
        
        try:
            # Validate environment
            if not self.validate_environment():
                raise DeploymentError("Environment validation failed")
            
            # Create backup
            backup_path = self.create_backup()
            
            # Build images
            if not self.build_images():
                if backup_path:
                    self.logger.info("Build failed, rolling back...")
                    self.rollback(backup_path)
                raise DeploymentError("Image build failed")
            
            # Deploy services
            if not self.deploy_services():
                if backup_path:
                    self.logger.info("Deployment failed, rolling back...")
                    self.rollback(backup_path)
                raise DeploymentError("Service deployment failed")
            
            # Run health checks
            if not self.run_health_checks():
                if backup_path:
                    self.logger.info("Health checks failed, rolling back...")
                    self.rollback(backup_path)
                raise DeploymentError("Health checks failed")
            
            # Setup monitoring
            self.setup_monitoring()
            
            # Cleanup old backups
            self.cleanup_old_backups()
            
            self.logger.info("Deployment completed successfully!")
            return True
        
        except DeploymentError as e:
            self.logger.error(f"Deployment failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected deployment error: {e}")
            return False


def main():
    """Main deployment script entry point."""
    parser = argparse.ArgumentParser(description='Deploy clip generation system')
    parser.add_argument('--config', '-c', default='deployment.yml',
                       help='Deployment configuration file')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--rollback', '-r', metavar='BACKUP_PATH',
                       help='Rollback to specified backup')
    parser.add_argument('--validate-only', action='store_true',
                       help='Only validate environment, do not deploy')
    
    args = parser.parse_args()
    
    try:
        manager = DeploymentManager(args.config, args.verbose)
        
        if args.rollback:
            success = manager.rollback(args.rollback)
        elif args.validate_only:
            success = manager.validate_environment()
        else:
            success = manager.deploy()
        
        sys.exit(0 if success else 1)
    
    except Exception as e:
        print(f"Deployment script error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()