"""Production configuration management.

Provides:
- Environment-specific configurations
- Secrets management
- Configuration validation
- Runtime configuration updates
- Security settings
- Performance tuning
"""

import os
import json
import secrets
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import timedelta

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from cryptography.fernet import Fernet


class Environment(str, Enum):
    """Application environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class LogLevel(str, Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class DatabaseConfig:
    """Database configuration."""
    host: str = "localhost"
    port: int = 5432
    database: str = "clipper"
    username: str = "clipper_user"
    password: str = ""
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    ssl_mode: str = "prefer"
    
    @property
    def url(self) -> str:
        """Get database URL."""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class RedisConfig:
    """Redis configuration."""
    host: str = "localhost"
    port: int = 6379
    database: int = 0
    password: Optional[str] = None
    ssl: bool = False
    pool_size: int = 10
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    retry_on_timeout: bool = True
    
    @property
    def url(self) -> str:
        """Get Redis URL."""
        scheme = "rediss" if self.ssl else "redis"
        auth = f":{self.password}@" if self.password else ""
        return f"{scheme}://{auth}{self.host}:{self.port}/{self.database}"


@dataclass
class SecurityConfig:
    """Security configuration."""
    secret_key: str = ""
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration: int = 3600  # seconds
    password_min_length: int = 8
    password_require_special: bool = True
    max_login_attempts: int = 5
    lockout_duration: int = 900  # seconds
    cors_origins: List[str] = field(default_factory=list)
    trusted_hosts: List[str] = field(default_factory=list)
    rate_limit_per_minute: int = 60
    
    def __post_init__(self):
        """Generate secrets if not provided."""
        if not self.secret_key:
            self.secret_key = secrets.token_urlsafe(32)
        if not self.jwt_secret:
            self.jwt_secret = secrets.token_urlsafe(32)


@dataclass
class StorageConfig:
    """Storage configuration."""
    upload_path: str = "./uploads"
    output_path: str = "./outputs"
    temp_path: str = "./temp"
    max_file_size: int = 500 * 1024 * 1024  # 500MB
    allowed_extensions: List[str] = field(default_factory=lambda: [
        '.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'
    ])
    cleanup_interval: int = 3600  # seconds
    retention_days: int = 30
    
    def __post_init__(self):
        """Create storage directories."""
        for path in [self.upload_path, self.output_path, self.temp_path]:
            Path(path).mkdir(parents=True, exist_ok=True)


@dataclass
class ProcessingConfig:
    """Processing configuration."""
    max_concurrent_jobs: int = 4
    job_timeout: int = 3600  # seconds
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    quality_presets: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        'low': {
            'video_bitrate': '500k',
            'audio_bitrate': '64k',
            'resolution': '480p',
            'fps': 24
        },
        'medium': {
            'video_bitrate': '1500k',
            'audio_bitrate': '128k',
            'resolution': '720p',
            'fps': 30
        },
        'high': {
            'video_bitrate': '5000k',
            'audio_bitrate': '192k',
            'resolution': '1080p',
            'fps': 30
        },
        'ultra': {
            'video_bitrate': '15000k',
            'audio_bitrate': '320k',
            'resolution': '4k',
            'fps': 60
        }
    })
    supported_formats: List[str] = field(default_factory=lambda: [
        'mp4', 'webm', 'avi', 'mov', 'mkv'
    ])


@dataclass
class MonitoringConfig:
    """Monitoring configuration."""
    metrics_enabled: bool = True
    metrics_interval: int = 60  # seconds
    health_check_interval: int = 30  # seconds
    log_level: LogLevel = LogLevel.INFO
    log_file: Optional[str] = None
    log_max_size: int = 100 * 1024 * 1024  # 100MB
    log_backup_count: int = 5
    prometheus_enabled: bool = False
    prometheus_port: int = 9090
    alert_webhook_url: Optional[str] = None
    alert_thresholds: Dict[str, float] = field(default_factory=lambda: {
        'cpu_usage': 80.0,
        'memory_usage': 85.0,
        'disk_usage': 90.0,
        'error_rate': 5.0,
        'response_time': 2000.0  # milliseconds
    })


class ProductionSettings(BaseSettings):
    """Production settings with validation."""
    
    # Environment
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    testing: bool = False
    
    # Application
    app_name: str = "Clipper API"
    app_version: str = "1.0.0"
    api_prefix: str = "/api"
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    
    # Database
    database_url: Optional[str] = None
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "clipper"
    db_user: str = "clipper_user"
    db_password: str = ""
    db_pool_size: int = 10
    db_max_overflow: int = 20
    
    # Redis
    redis_url: Optional[str] = None
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    
    # Security
    secret_key: str = ""
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration: int = 3600
    cors_origins: List[str] = Field(default_factory=list)
    
    # Storage
    upload_path: str = "./uploads"
    output_path: str = "./outputs"
    temp_path: str = "./temp"
    max_file_size: int = 500 * 1024 * 1024
    
    # Processing
    max_concurrent_jobs: int = 4
    job_timeout: int = 3600
    ffmpeg_path: str = "ffmpeg"
    
    # Monitoring
    log_level: LogLevel = LogLevel.INFO
    metrics_enabled: bool = True
    prometheus_enabled: bool = False
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "allow"
    }
    
    @field_validator('environment')
    @classmethod
    def validate_environment(cls, v):
        """Validate environment setting."""
        if isinstance(v, str):
            try:
                return Environment(v.lower())
            except ValueError:
                raise ValueError(f"Invalid environment: {v}")
        return v
    
    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v
    
    @field_validator('secret_key', 'jwt_secret')
    @classmethod
    def validate_secrets(cls, v, info):
        """Validate and generate secrets."""
        if not v:
            return secrets.token_urlsafe(32)
        if len(v) < 32:
            raise ValueError(f"{info.field_name} must be at least 32 characters long")
        return v
    
    @field_validator('workers')
    @classmethod
    def validate_workers(cls, v, info):
        """Validate worker count based on environment."""
        # Note: In V2, we can't access other field values during validation
        # This validation would need to be moved to model_validator if needed
        if v < 1:
            return max(1, os.cpu_count() or 1)
        return v
    
    def get_database_config(self) -> DatabaseConfig:
        """Get database configuration."""
        return DatabaseConfig(
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            username=self.db_user,
            password=self.db_password,
            pool_size=self.db_pool_size,
            max_overflow=self.db_max_overflow
        )
    
    def get_redis_config(self) -> RedisConfig:
        """Get Redis configuration."""
        return RedisConfig(
            host=self.redis_host,
            port=self.redis_port,
            database=self.redis_db,
            password=self.redis_password
        )
    
    def get_security_config(self) -> SecurityConfig:
        """Get security configuration."""
        return SecurityConfig(
            secret_key=self.secret_key,
            jwt_secret=self.jwt_secret,
            jwt_algorithm=self.jwt_algorithm,
            jwt_expiration=self.jwt_expiration,
            cors_origins=self.cors_origins
        )
    
    def get_storage_config(self) -> StorageConfig:
        """Get storage configuration."""
        return StorageConfig(
            upload_path=self.upload_path,
            output_path=self.output_path,
            temp_path=self.temp_path,
            max_file_size=self.max_file_size
        )
    
    def get_processing_config(self) -> ProcessingConfig:
        """Get processing configuration."""
        return ProcessingConfig(
            max_concurrent_jobs=self.max_concurrent_jobs,
            job_timeout=self.job_timeout,
            ffmpeg_path=self.ffmpeg_path
        )
    
    def get_monitoring_config(self) -> MonitoringConfig:
        """Get monitoring configuration."""
        return MonitoringConfig(
            log_level=self.log_level,
            metrics_enabled=self.metrics_enabled,
            prometheus_enabled=self.prometheus_enabled
        )


class SecretsManager:
    """Secure secrets management."""
    
    def __init__(self, key_file: Optional[str] = None):
        self.key_file = key_file or ".secrets.key"
        self.secrets_file = ".secrets.json"
        self._key = self._load_or_generate_key()
        self._cipher = Fernet(self._key)
        self._secrets: Dict[str, str] = {}
        self._load_secrets()
    
    def _load_or_generate_key(self) -> bytes:
        """Load or generate encryption key."""
        key_path = Path(self.key_file)
        
        if key_path.exists():
            with open(key_path, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_path, 'wb') as f:
                f.write(key)
            # Set restrictive permissions
            os.chmod(key_path, 0o600)
            return key
    
    def _load_secrets(self):
        """Load encrypted secrets from file."""
        secrets_path = Path(self.secrets_file)
        
        if secrets_path.exists():
            try:
                with open(secrets_path, 'rb') as f:
                    encrypted_data = f.read()
                
                if encrypted_data:
                    decrypted_data = self._cipher.decrypt(encrypted_data)
                    self._secrets = json.loads(decrypted_data.decode())
            except Exception as e:
                print(f"Warning: Could not load secrets: {e}")
                self._secrets = {}
    
    def _save_secrets(self):
        """Save encrypted secrets to file."""
        try:
            data = json.dumps(self._secrets).encode()
            encrypted_data = self._cipher.encrypt(data)
            
            with open(self.secrets_file, 'wb') as f:
                f.write(encrypted_data)
            
            # Set restrictive permissions
            os.chmod(self.secrets_file, 0o600)
        except Exception as e:
            print(f"Error saving secrets: {e}")
    
    def set_secret(self, key: str, value: str):
        """Set a secret value."""
        self._secrets[key] = value
        self._save_secrets()
    
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a secret value."""
        return self._secrets.get(key, default)
    
    def delete_secret(self, key: str) -> bool:
        """Delete a secret."""
        if key in self._secrets:
            del self._secrets[key]
            self._save_secrets()
            return True
        return False
    
    def list_secrets(self) -> List[str]:
        """List secret keys (not values)."""
        return list(self._secrets.keys())
    
    def rotate_key(self):
        """Rotate encryption key."""
        # Decrypt with old key
        old_secrets = self._secrets.copy()
        
        # Generate new key
        new_key = Fernet.generate_key()
        
        # Backup old key
        backup_key_file = f"{self.key_file}.backup"
        if Path(self.key_file).exists():
            Path(self.key_file).rename(backup_key_file)
        
        # Save new key
        with open(self.key_file, 'wb') as f:
            f.write(new_key)
        os.chmod(self.key_file, 0o600)
        
        # Update cipher and re-encrypt secrets
        self._key = new_key
        self._cipher = Fernet(self._key)
        self._secrets = old_secrets
        self._save_secrets()
        
        print("Encryption key rotated successfully")


class ConfigurationManager:
    """Configuration management with environment support."""
    
    def __init__(self, env_file: Optional[str] = None):
        self.env_file = env_file
        self.secrets_manager = SecretsManager()
        self._settings: Optional[ProductionSettings] = None
        self._load_settings()
    
    def _load_settings(self):
        """Load settings from environment and secrets."""
        # Load from environment file if specified
        if self.env_file and Path(self.env_file).exists():
            os.environ.setdefault('ENV_FILE', self.env_file)
        
        # Inject secrets into environment
        self._inject_secrets()
        
        # Load settings
        self._settings = ProductionSettings()
    
    def _inject_secrets(self):
        """Inject secrets into environment variables."""
        secret_mappings = {
            'SECRET_KEY': 'secret_key',
            'JWT_SECRET': 'jwt_secret',
            'DB_PASSWORD': 'db_password',
            'REDIS_PASSWORD': 'redis_password'
        }
        
        for env_var, secret_key in secret_mappings.items():
            if env_var not in os.environ:
                secret_value = self.secrets_manager.get_secret(secret_key)
                if secret_value:
                    os.environ[env_var] = secret_value
    
    @property
    def settings(self) -> ProductionSettings:
        """Get current settings."""
        if self._settings is None:
            self._load_settings()
        return self._settings
    
    def reload_settings(self):
        """Reload settings from environment."""
        self._load_settings()
    
    def update_secret(self, key: str, value: str):
        """Update a secret and reload settings."""
        self.secrets_manager.set_secret(key, value)
        self.reload_settings()
    
    def get_environment_config(self) -> Dict[str, Any]:
        """Get environment-specific configuration."""
        env = self.settings.environment
        
        base_config = {
            'database': self.settings.get_database_config(),
            'redis': self.settings.get_redis_config(),
            'security': self.settings.get_security_config(),
            'storage': self.settings.get_storage_config(),
            'processing': self.settings.get_processing_config(),
            'monitoring': self.settings.get_monitoring_config()
        }
        
        # Environment-specific overrides
        if env == Environment.DEVELOPMENT:
            base_config['monitoring'].log_level = LogLevel.DEBUG
            base_config['security'].cors_origins = ['*']
            base_config['processing'].max_concurrent_jobs = 2
        
        elif env == Environment.STAGING:
            base_config['monitoring'].log_level = LogLevel.INFO
            base_config['monitoring'].metrics_enabled = True
            base_config['processing'].max_concurrent_jobs = 3
        
        elif env == Environment.PRODUCTION:
            base_config['monitoring'].log_level = LogLevel.WARNING
            base_config['monitoring'].metrics_enabled = True
            base_config['monitoring'].prometheus_enabled = True
            base_config['security'].cors_origins = []  # Must be explicitly set
            base_config['processing'].max_concurrent_jobs = max(4, os.cpu_count() or 4)
        
        elif env == Environment.TESTING:
            base_config['monitoring'].log_level = LogLevel.ERROR
            base_config['database'].database = 'clipper_test'
            base_config['redis'].database = 1
            base_config['processing'].max_concurrent_jobs = 1
        
        return base_config
    
    def validate_configuration(self) -> Dict[str, Any]:
        """Validate current configuration."""
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'environment': self.settings.environment.value
        }
        
        # Check required secrets
        required_secrets = ['secret_key', 'jwt_secret']
        if self.settings.environment == Environment.PRODUCTION:
            required_secrets.extend(['db_password'])
        
        for secret in required_secrets:
            if not self.secrets_manager.get_secret(secret):
                validation_results['errors'].append(f"Missing required secret: {secret}")
                validation_results['valid'] = False
        
        # Check file paths
        storage_config = self.settings.get_storage_config()
        for path_name, path_value in [
            ('upload_path', storage_config.upload_path),
            ('output_path', storage_config.output_path),
            ('temp_path', storage_config.temp_path)
        ]:
            if not Path(path_value).exists():
                validation_results['warnings'].append(f"Path does not exist: {path_name}={path_value}")
        
        # Check external dependencies
        processing_config = self.settings.get_processing_config()
        import shutil
        if not shutil.which(processing_config.ffmpeg_path):
            validation_results['errors'].append(f"FFmpeg not found: {processing_config.ffmpeg_path}")
            validation_results['valid'] = False
        
        # Environment-specific validations
        if self.settings.environment == Environment.PRODUCTION:
            if self.settings.debug:
                validation_results['warnings'].append("Debug mode enabled in production")
            
            security_config = self.settings.get_security_config()
            if not security_config.cors_origins:
                validation_results['warnings'].append("CORS origins not configured for production")
        
        return validation_results


# Global configuration manager
_config_manager: Optional[ConfigurationManager] = None


def get_config_manager(env_file: Optional[str] = None) -> ConfigurationManager:
    """Get global configuration manager."""
    global _config_manager
    
    if _config_manager is None:
        _config_manager = ConfigurationManager(env_file)
    
    return _config_manager


def get_settings() -> ProductionSettings:
    """Get current application settings."""
    return get_config_manager().settings


def get_secrets_manager() -> SecretsManager:
    """Get secrets manager."""
    return get_config_manager().secrets_manager


# Export main components
__all__ = [
    'Environment',
    'LogLevel',
    'DatabaseConfig',
    'RedisConfig',
    'SecurityConfig',
    'StorageConfig',
    'ProcessingConfig',
    'MonitoringConfig',
    'ProductionSettings',
    'SecretsManager',
    'ConfigurationManager',
    'get_config_manager',
    'get_settings',
    'get_secrets_manager'
]