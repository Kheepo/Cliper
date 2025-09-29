"""Environment-specific configurations and secrets management.

Provides configuration management for different deployment environments:
- Development
- Testing
- Staging
- Production

Includes secrets management, validation, and environment-specific overrides.
"""

import os
import json
from typing import Dict, Any, Optional, Union, List
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import logging
from functools import lru_cache

from cryptography.fernet import Fernet
import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from pydantic.env_settings import SettingsSourceCallable

logger = logging.getLogger(__name__)


class Environment(str, Enum):
    """Supported deployment environments."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Supported log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class DatabaseConfig:
    """Database configuration."""
    url: str
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo: bool = False
    ssl_mode: str = "prefer"
    connection_timeout: int = 30
    command_timeout: int = 60


@dataclass
class RedisConfig:
    """Redis configuration."""
    url: str
    max_connections: int = 100
    retry_on_timeout: bool = True
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    health_check_interval: int = 30
    decode_responses: bool = True
    password: Optional[str] = None
    ssl: bool = False
    ssl_cert_reqs: str = "required"


@dataclass
class SecurityConfig:
    """Security configuration."""
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_min_length: int = 8
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    cors_origins: List[str] = field(default_factory=list)
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = field(default_factory=lambda: ["*"])
    cors_allow_headers: List[str] = field(default_factory=lambda: ["*"])
    rate_limit_per_minute: int = 60
    enable_https_redirect: bool = False
    secure_cookies: bool = False


@dataclass
class FFmpegConfig:
    """FFmpeg configuration."""
    binary_path: str = "ffmpeg"
    timeout: int = 300
    max_concurrent_jobs: int = 4
    temp_dir: Optional[str] = None
    quality_preset: str = "medium"
    hardware_acceleration: bool = False
    gpu_device: Optional[str] = None
    memory_limit_mb: int = 1024
    thread_count: Optional[int] = None


@dataclass
class StorageConfig:
    """Storage configuration."""
    upload_dir: str
    max_file_size_mb: int = 100
    allowed_extensions: List[str] = field(default_factory=lambda: [".mp4", ".avi", ".mov", ".mkv"])
    cleanup_interval_hours: int = 24
    retention_days: int = 30
    enable_compression: bool = True
    compression_quality: int = 85
    enable_thumbnails: bool = True
    thumbnail_sizes: List[tuple] = field(default_factory=lambda: [(320, 240), (640, 480)])


@dataclass
class MonitoringConfig:
    """Monitoring and observability configuration."""
    enable_metrics: bool = True
    metrics_port: int = 9090
    enable_tracing: bool = False
    jaeger_endpoint: Optional[str] = None
    sentry_dsn: Optional[str] = None
    log_level: LogLevel = LogLevel.INFO
    structured_logging: bool = True
    log_format: str = "json"
    enable_health_checks: bool = True
    health_check_interval: int = 30
    enable_profiling: bool = False


class SecretsManager:
    """Manages encrypted secrets and sensitive configuration."""
    
    def __init__(self, encryption_key: Optional[str] = None):
        """Initialize secrets manager.
        
        Args:
            encryption_key: Base64-encoded Fernet key for encryption
        """
        if encryption_key:
            self.cipher = Fernet(encryption_key.encode())
        else:
            # Generate a new key if none provided
            key = Fernet.generate_key()
            self.cipher = Fernet(key)
            logger.warning("No encryption key provided, generated new key. Store this securely!")
            logger.warning(f"Generated key: {key.decode()}")
    
    def encrypt_secret(self, value: str) -> str:
        """Encrypt a secret value."""
        return self.cipher.encrypt(value.encode()).decode()
    
    def decrypt_secret(self, encrypted_value: str) -> str:
        """Decrypt a secret value."""
        return self.cipher.decrypt(encrypted_value.encode()).decode()
    
    def load_secrets_file(self, file_path: Path) -> Dict[str, str]:
        """Load and decrypt secrets from file."""
        if not file_path.exists():
            return {}
        
        try:
            with open(file_path, 'r') as f:
                encrypted_secrets = json.load(f)
            
            secrets = {}
            for key, encrypted_value in encrypted_secrets.items():
                try:
                    secrets[key] = self.decrypt_secret(encrypted_value)
                except Exception as e:
                    logger.error(f"Failed to decrypt secret '{key}': {e}")
                    secrets[key] = encrypted_value  # Fallback to original value
            
            return secrets
        
        except Exception as e:
            logger.error(f"Failed to load secrets file {file_path}: {e}")
            return {}
    
    def save_secrets_file(self, secrets: Dict[str, str], file_path: Path) -> None:
        """Encrypt and save secrets to file."""
        try:
            encrypted_secrets = {}
            for key, value in secrets.items():
                encrypted_secrets[key] = self.encrypt_secret(value)
            
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w') as f:
                json.dump(encrypted_secrets, f, indent=2)
            
            # Set restrictive permissions
            os.chmod(file_path, 0o600)
            
        except Exception as e:
            logger.error(f"Failed to save secrets file {file_path}: {e}")
            raise


class EnvironmentSettings(BaseSettings):
    """Environment-specific settings with secrets management."""
    
    # Environment
    environment: Environment = Field(default=Environment.DEVELOPMENT, env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    
    # Application
    app_name: str = Field(default="Clip Generator", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    workers: int = Field(default=1, env="WORKERS")
    
    # Database
    database_url: str = Field(..., env="DATABASE_URL")
    database_pool_size: int = Field(default=10, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=20, env="DATABASE_MAX_OVERFLOW")
    database_echo: bool = Field(default=False, env="DATABASE_ECHO")
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    redis_max_connections: int = Field(default=100, env="REDIS_MAX_CONNECTIONS")
    
    # Security
    secret_key: str = Field(..., env="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # CORS
    cors_origins: str = Field(default="*", env="CORS_ORIGINS")
    
    # Storage
    upload_dir: str = Field(default="./uploads", env="UPLOAD_DIR")
    max_file_size_mb: int = Field(default=100, env="MAX_FILE_SIZE_MB")
    
    # FFmpeg
    ffmpeg_binary: str = Field(default="ffmpeg", env="FFMPEG_BINARY")
    ffmpeg_timeout: int = Field(default=300, env="FFMPEG_TIMEOUT")
    
    # Monitoring
    sentry_dsn: Optional[str] = Field(default=None, env="SENTRY_DSN")
    log_level: LogLevel = Field(default=LogLevel.INFO, env="LOG_LEVEL")
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    
    # Secrets file path
    secrets_file: str = Field(default=".secrets.json", env="SECRETS_FILE")
    encryption_key: Optional[str] = Field(default=None, env="ENCRYPTION_KEY")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "allow"
    }
    
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )
    
    @field_validator('cors_origins')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v
    
    @field_validator('environment')
    @classmethod
    def validate_environment(cls, v):
        """Validate environment value."""
        if isinstance(v, str):
            return Environment(v.lower())
        return v
    
    def get_database_config(self) -> DatabaseConfig:
        """Get database configuration."""
        return DatabaseConfig(
            url=self.database_url,
            pool_size=self.database_pool_size,
            max_overflow=self.database_max_overflow,
            echo=self.database_echo and self.debug,
            ssl_mode="require" if self.environment == Environment.PRODUCTION else "prefer"
        )
    
    def get_redis_config(self) -> RedisConfig:
        """Get Redis configuration."""
        return RedisConfig(
            url=self.redis_url,
            max_connections=self.redis_max_connections,
            ssl=self.environment == Environment.PRODUCTION
        )
    
    def get_security_config(self) -> SecurityConfig:
        """Get security configuration."""
        return SecurityConfig(
            secret_key=self.secret_key,
            algorithm=self.jwt_algorithm,
            access_token_expire_minutes=self.access_token_expire_minutes,
            cors_origins=self.cors_origins,
            secure_cookies=self.environment == Environment.PRODUCTION,
            enable_https_redirect=self.environment == Environment.PRODUCTION,
            rate_limit_per_minute=30 if self.environment == Environment.PRODUCTION else 60
        )
    
    def get_ffmpeg_config(self) -> FFmpegConfig:
        """Get FFmpeg configuration."""
        return FFmpegConfig(
            binary_path=self.ffmpeg_binary,
            timeout=self.ffmpeg_timeout,
            max_concurrent_jobs=2 if self.environment == Environment.PRODUCTION else 4,
            hardware_acceleration=self.environment == Environment.PRODUCTION
        )
    
    def get_storage_config(self) -> StorageConfig:
        """Get storage configuration."""
        return StorageConfig(
            upload_dir=self.upload_dir,
            max_file_size_mb=self.max_file_size_mb,
            retention_days=7 if self.environment == Environment.DEVELOPMENT else 30,
            enable_compression=self.environment != Environment.DEVELOPMENT
        )
    
    def get_monitoring_config(self) -> MonitoringConfig:
        """Get monitoring configuration."""
        return MonitoringConfig(
            enable_metrics=self.enable_metrics,
            sentry_dsn=self.sentry_dsn,
            log_level=self.log_level,
            structured_logging=self.environment != Environment.DEVELOPMENT,
            enable_tracing=self.environment == Environment.PRODUCTION,
            enable_profiling=self.environment == Environment.DEVELOPMENT
        )


class ConfigManager:
    """Manages configuration loading and validation."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize configuration manager.
        
        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = config_dir or Path("config")
        self.secrets_manager = None
        self._settings = None
    
    def load_environment_config(self, environment: Environment) -> Dict[str, Any]:
        """Load environment-specific configuration file."""
        config_file = self.config_dir / f"{environment.value}.yaml"
        
        if not config_file.exists():
            logger.warning(f"Environment config file not found: {config_file}")
            return {}
        
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f) or {}
            
            logger.info(f"Loaded environment config: {config_file}")
            return config
        
        except Exception as e:
            logger.error(f"Failed to load environment config {config_file}: {e}")
            return {}
    
    def initialize_secrets_manager(self, encryption_key: Optional[str] = None) -> SecretsManager:
        """Initialize secrets manager."""
        if not self.secrets_manager:
            self.secrets_manager = SecretsManager(encryption_key)
        return self.secrets_manager
    
    def load_secrets(self, secrets_file: Optional[Path] = None) -> Dict[str, str]:
        """Load secrets from encrypted file."""
        if not self.secrets_manager:
            logger.warning("Secrets manager not initialized")
            return {}
        
        secrets_file = secrets_file or (self.config_dir / ".secrets.json")
        return self.secrets_manager.load_secrets_file(secrets_file)
    
    def get_settings(self, reload: bool = False) -> EnvironmentSettings:
        """Get application settings."""
        if self._settings is None or reload:
            # Load environment-specific config
            env = Environment(os.getenv("ENVIRONMENT", "development").lower())
            env_config = self.load_environment_config(env)
            
            # Initialize secrets manager
            encryption_key = os.getenv("ENCRYPTION_KEY")
            self.initialize_secrets_manager(encryption_key)
            
            # Load secrets
            secrets = self.load_secrets()
            
            # Merge configurations
            config_data = {**env_config, **secrets}
            
            # Create settings with merged config
            self._settings = EnvironmentSettings(**config_data)
            
            logger.info(f"Loaded settings for environment: {self._settings.environment}")
        
        return self._settings
    
    def validate_configuration(self, settings: EnvironmentSettings) -> List[str]:
        """Validate configuration and return list of issues."""
        issues = []
        
        # Check required secrets
        if not settings.secret_key or settings.secret_key == "your-secret-key-here":
            issues.append("SECRET_KEY is not set or using default value")
        
        if not settings.database_url or "your-database-url" in settings.database_url:
            issues.append("DATABASE_URL is not properly configured")
        
        # Production-specific validations
        if settings.environment == Environment.PRODUCTION:
            if settings.debug:
                issues.append("DEBUG should be False in production")
            
            if not settings.sentry_dsn:
                issues.append("SENTRY_DSN should be configured in production")
            
            if "localhost" in settings.database_url:
                issues.append("DATABASE_URL should not use localhost in production")
            
            if "localhost" in settings.redis_url:
                issues.append("REDIS_URL should not use localhost in production")
        
        # Security validations
        if len(settings.secret_key) < 32:
            issues.append("SECRET_KEY should be at least 32 characters long")
        
        return issues


# Global configuration manager instance
_config_manager = ConfigManager()


@lru_cache(maxsize=1)
def get_config_manager() -> ConfigManager:
    """Get global configuration manager instance."""
    return _config_manager


@lru_cache(maxsize=1)
def get_settings() -> EnvironmentSettings:
    """Get application settings."""
    return get_config_manager().get_settings()


def reload_settings() -> EnvironmentSettings:
    """Reload application settings."""
    get_settings.cache_clear()
    get_config_manager.cache_clear()
    return get_settings()


def validate_current_configuration() -> List[str]:
    """Validate current configuration."""
    settings = get_settings()
    return get_config_manager().validate_configuration(settings)