"""Environment-specific configuration management for production deployment.

This module provides:
- Environment-specific settings
- Secrets management
- Configuration validation
- Runtime environment detection
- Secure credential handling
- Configuration hot-reloading
"""

import os
import json
import yaml
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import logging
from functools import lru_cache
import hashlib
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..utils.logging_config import get_logger

logger = get_logger('environment')


class Environment(Enum):
    """Application environments."""
    DEVELOPMENT = 'development'
    TESTING = 'testing'
    STAGING = 'staging'
    PRODUCTION = 'production'


class ConfigSource(Enum):
    """Configuration sources in order of precedence."""
    ENVIRONMENT_VARIABLES = 'env_vars'
    CONFIG_FILE = 'config_file'
    SECRETS_FILE = 'secrets_file'
    VAULT = 'vault'
    DEFAULT = 'default'


@dataclass
class DatabaseConfig:
    """Database configuration."""
    url: str
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo: bool = False
    ssl_mode: str = 'prefer'
    
    def __post_init__(self):
        if not self.url:
            raise ValueError("Database URL is required")


@dataclass
class RedisConfig:
    """Redis configuration."""
    url: str
    max_connections: int = 100
    retry_on_timeout: bool = True
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    health_check_interval: int = 30
    
    def __post_init__(self):
        if not self.url:
            raise ValueError("Redis URL is required")


@dataclass
class SecurityConfig:
    """Security configuration."""
    secret_key: str
    jwt_algorithm: str = 'HS256'
    jwt_expiration_hours: int = 24
    password_min_length: int = 8
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    cors_origins: List[str] = field(default_factory=list)
    trusted_hosts: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.secret_key:
            raise ValueError("Secret key is required")
        if len(self.secret_key) < 32:
            raise ValueError("Secret key must be at least 32 characters")


@dataclass
class StorageConfig:
    """Storage configuration."""
    upload_dir: str
    max_file_size_mb: int = 100
    allowed_extensions: List[str] = field(default_factory=lambda: ['.mp4', '.avi', '.mov', '.mkv'])
    cleanup_interval_hours: int = 24
    retention_days: int = 30
    
    def __post_init__(self):
        if not self.upload_dir:
            raise ValueError("Upload directory is required")
        
        # Create directory if it doesn't exist
        Path(self.upload_dir).mkdir(parents=True, exist_ok=True)


@dataclass
class MonitoringConfig:
    """Monitoring and observability configuration."""
    enable_metrics: bool = True
    enable_tracing: bool = True
    metrics_port: int = 9090
    log_level: str = 'INFO'
    structured_logging: bool = True
    correlation_id_header: str = 'X-Correlation-ID'
    health_check_interval: int = 30
    
    def __post_init__(self):
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(f"Log level must be one of: {valid_log_levels}")


@dataclass
class PerformanceConfig:
    """Performance and scaling configuration."""
    worker_processes: int = 1
    worker_connections: int = 1000
    max_requests_per_worker: int = 1000
    request_timeout: int = 30
    keepalive_timeout: int = 2
    max_concurrent_requests: int = 100
    rate_limit_requests_per_minute: int = 60
    
    def __post_init__(self):
        if self.worker_processes < 1:
            self.worker_processes = 1
        if self.worker_connections < 1:
            self.worker_connections = 1000


@dataclass
class FeatureFlags:
    """Feature flags for gradual rollouts."""
    enable_websockets: bool = True
    enable_caching: bool = True
    enable_rate_limiting: bool = True
    enable_circuit_breakers: bool = True
    enable_compression: bool = True
    enable_background_tasks: bool = True
    enable_health_checks: bool = True
    experimental_features: List[str] = field(default_factory=list)


class SecretManager:
    """Secure secrets management."""
    
    def __init__(self, encryption_key: Optional[str] = None):
        self.encryption_key = encryption_key or os.environ.get('ENCRYPTION_KEY')
        self._cipher = None
        
        if self.encryption_key:
            self._setup_encryption()
    
    def _setup_encryption(self):
        """Setup encryption for secrets."""
        try:
            # Derive key from password
            password = self.encryption_key.encode()
            salt = b'clip_generation_salt'  # In production, use random salt
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password))
            self._cipher = Fernet(key)
        except Exception as e:
            logger.error(f"Failed to setup encryption: {e}")
            self._cipher = None
    
    def encrypt_secret(self, value: str) -> str:
        """Encrypt a secret value."""
        if not self._cipher:
            logger.warning("No encryption key available, storing secret in plain text")
            return value
        
        try:
            encrypted = self._cipher.encrypt(value.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Failed to encrypt secret: {e}")
            return value
    
    def decrypt_secret(self, encrypted_value: str) -> str:
        """Decrypt a secret value."""
        if not self._cipher:
            return encrypted_value
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_value.encode())
            decrypted = self._cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt secret: {e}")
            return encrypted_value
    
    def load_secrets_file(self, file_path: str) -> Dict[str, str]:
        """Load secrets from encrypted file."""
        try:
            if not os.path.exists(file_path):
                logger.warning(f"Secrets file not found: {file_path}")
                return {}
            
            with open(file_path, 'r') as f:
                encrypted_secrets = json.load(f)
            
            secrets = {}
            for key, encrypted_value in encrypted_secrets.items():
                secrets[key] = self.decrypt_secret(encrypted_value)
            
            logger.info(f"Loaded {len(secrets)} secrets from {file_path}")
            return secrets
        
        except Exception as e:
            logger.error(f"Failed to load secrets file {file_path}: {e}")
            return {}
    
    def save_secrets_file(self, secrets: Dict[str, str], file_path: str):
        """Save secrets to encrypted file."""
        try:
            encrypted_secrets = {}
            for key, value in secrets.items():
                encrypted_secrets[key] = self.encrypt_secret(value)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w') as f:
                json.dump(encrypted_secrets, f, indent=2)
            
            # Set restrictive permissions
            os.chmod(file_path, 0o600)
            
            logger.info(f"Saved {len(secrets)} secrets to {file_path}")
        
        except Exception as e:
            logger.error(f"Failed to save secrets file {file_path}: {e}")


class ConfigurationManager:
    """Centralized configuration management."""
    
    def __init__(self, environment: Optional[Environment] = None):
        self.environment = environment or self._detect_environment()
        self.secret_manager = SecretManager()
        self.config_cache = {}
        self.config_file_hashes = {}
        
        logger.info(f"Initialized configuration manager for {self.environment.value} environment")
    
    def _detect_environment(self) -> Environment:
        """Auto-detect the current environment."""
        env_name = os.environ.get('ENVIRONMENT', 'development').lower()
        
        try:
            return Environment(env_name)
        except ValueError:
            logger.warning(f"Unknown environment '{env_name}', defaulting to development")
            return Environment.DEVELOPMENT
    
    def _get_config_file_path(self, config_type: str) -> str:
        """Get configuration file path for the current environment."""
        base_dir = os.environ.get('CONFIG_DIR', 'config')
        return os.path.join(base_dir, f"{config_type}.{self.environment.value}.yaml")
    
    def _load_yaml_file(self, file_path: str) -> Dict[str, Any]:
        """Load YAML configuration file with caching and change detection."""
        if not os.path.exists(file_path):
            logger.warning(f"Configuration file not found: {file_path}")
            return {}
        
        # Check if file has changed
        with open(file_path, 'rb') as f:
            content = f.read()
            file_hash = hashlib.md5(content).hexdigest()
        
        if file_path in self.config_file_hashes:
            if self.config_file_hashes[file_path] == file_hash:
                # File hasn't changed, return cached config
                return self.config_cache.get(file_path, {})
        
        # Load and cache new configuration
        try:
            with open(file_path, 'r') as f:
                config = yaml.safe_load(f) or {}
            
            self.config_cache[file_path] = config
            self.config_file_hashes[file_path] = file_hash
            
            logger.info(f"Loaded configuration from {file_path}")
            return config
        
        except Exception as e:
            logger.error(f"Failed to load configuration file {file_path}: {e}")
            return {}
    
    def _get_env_var(self, key: str, default: Any = None) -> Any:
        """Get environment variable with type conversion."""
        value = os.environ.get(key, default)
        
        if value is None:
            return default
        
        # Convert string values to appropriate types
        if isinstance(default, bool):
            return value.lower() in ('true', '1', 'yes', 'on')
        elif isinstance(default, int):
            try:
                return int(value)
            except ValueError:
                return default
        elif isinstance(default, float):
            try:
                return float(value)
            except ValueError:
                return default
        elif isinstance(default, list):
            if isinstance(value, str):
                return [item.strip() for item in value.split(',') if item.strip()]
            return value
        
        return value
    
    def get_database_config(self) -> DatabaseConfig:
        """Get database configuration."""
        # Load from file
        file_config = self._load_yaml_file(self._get_config_file_path('database'))
        
        # Override with environment variables
        return DatabaseConfig(
            url=self._get_env_var('DATABASE_URL', file_config.get('url', '')),
            pool_size=self._get_env_var('DB_POOL_SIZE', file_config.get('pool_size', 10)),
            max_overflow=self._get_env_var('DB_MAX_OVERFLOW', file_config.get('max_overflow', 20)),
            pool_timeout=self._get_env_var('DB_POOL_TIMEOUT', file_config.get('pool_timeout', 30)),
            pool_recycle=self._get_env_var('DB_POOL_RECYCLE', file_config.get('pool_recycle', 3600)),
            echo=self._get_env_var('DB_ECHO', file_config.get('echo', False)),
            ssl_mode=self._get_env_var('DB_SSL_MODE', file_config.get('ssl_mode', 'prefer'))
        )
    
    def get_redis_config(self) -> RedisConfig:
        """Get Redis configuration."""
        file_config = self._load_yaml_file(self._get_config_file_path('redis'))
        
        return RedisConfig(
            url=self._get_env_var('REDIS_URL', file_config.get('url', 'redis://localhost:6379')),
            max_connections=self._get_env_var('REDIS_MAX_CONNECTIONS', file_config.get('max_connections', 100)),
            retry_on_timeout=self._get_env_var('REDIS_RETRY_ON_TIMEOUT', file_config.get('retry_on_timeout', True)),
            socket_timeout=self._get_env_var('REDIS_SOCKET_TIMEOUT', file_config.get('socket_timeout', 5)),
            socket_connect_timeout=self._get_env_var('REDIS_SOCKET_CONNECT_TIMEOUT', file_config.get('socket_connect_timeout', 5)),
            health_check_interval=self._get_env_var('REDIS_HEALTH_CHECK_INTERVAL', file_config.get('health_check_interval', 30))
        )
    
    def get_security_config(self) -> SecurityConfig:
        """Get security configuration."""
        file_config = self._load_yaml_file(self._get_config_file_path('security'))
        
        # Load secrets
        secrets_file = os.environ.get('SECRETS_FILE', 'secrets/secrets.json')
        secrets = self.secret_manager.load_secrets_file(secrets_file)
        
        secret_key = (
            self._get_env_var('SECRET_KEY') or
            secrets.get('secret_key') or
            file_config.get('secret_key') or
            self._generate_secret_key()
        )
        
        return SecurityConfig(
            secret_key=secret_key,
            jwt_algorithm=self._get_env_var('JWT_ALGORITHM', file_config.get('jwt_algorithm', 'HS256')),
            jwt_expiration_hours=self._get_env_var('JWT_EXPIRATION_HOURS', file_config.get('jwt_expiration_hours', 24)),
            password_min_length=self._get_env_var('PASSWORD_MIN_LENGTH', file_config.get('password_min_length', 8)),
            max_login_attempts=self._get_env_var('MAX_LOGIN_ATTEMPTS', file_config.get('max_login_attempts', 5)),
            lockout_duration_minutes=self._get_env_var('LOCKOUT_DURATION_MINUTES', file_config.get('lockout_duration_minutes', 15)),
            cors_origins=self._get_env_var('CORS_ORIGINS', file_config.get('cors_origins', [])),
            trusted_hosts=self._get_env_var('TRUSTED_HOSTS', file_config.get('trusted_hosts', []))
        )
    
    def get_storage_config(self) -> StorageConfig:
        """Get storage configuration."""
        file_config = self._load_yaml_file(self._get_config_file_path('storage'))
        
        return StorageConfig(
            upload_dir=self._get_env_var('UPLOAD_DIR', file_config.get('upload_dir', 'uploads')),
            max_file_size_mb=self._get_env_var('MAX_FILE_SIZE_MB', file_config.get('max_file_size_mb', 100)),
            allowed_extensions=self._get_env_var('ALLOWED_EXTENSIONS', file_config.get('allowed_extensions', ['.mp4', '.avi', '.mov', '.mkv'])),
            cleanup_interval_hours=self._get_env_var('CLEANUP_INTERVAL_HOURS', file_config.get('cleanup_interval_hours', 24)),
            retention_days=self._get_env_var('RETENTION_DAYS', file_config.get('retention_days', 30))
        )
    
    def get_monitoring_config(self) -> MonitoringConfig:
        """Get monitoring configuration."""
        file_config = self._load_yaml_file(self._get_config_file_path('monitoring'))
        
        return MonitoringConfig(
            enable_metrics=self._get_env_var('ENABLE_METRICS', file_config.get('enable_metrics', True)),
            enable_tracing=self._get_env_var('ENABLE_TRACING', file_config.get('enable_tracing', True)),
            metrics_port=self._get_env_var('METRICS_PORT', file_config.get('metrics_port', 9090)),
            log_level=self._get_env_var('LOG_LEVEL', file_config.get('log_level', 'INFO')),
            structured_logging=self._get_env_var('STRUCTURED_LOGGING', file_config.get('structured_logging', True)),
            correlation_id_header=self._get_env_var('CORRELATION_ID_HEADER', file_config.get('correlation_id_header', 'X-Correlation-ID')),
            health_check_interval=self._get_env_var('HEALTH_CHECK_INTERVAL', file_config.get('health_check_interval', 30))
        )
    
    def get_performance_config(self) -> PerformanceConfig:
        """Get performance configuration."""
        file_config = self._load_yaml_file(self._get_config_file_path('performance'))
        
        return PerformanceConfig(
            worker_processes=self._get_env_var('WORKER_PROCESSES', file_config.get('worker_processes', 1)),
            worker_connections=self._get_env_var('WORKER_CONNECTIONS', file_config.get('worker_connections', 1000)),
            max_requests_per_worker=self._get_env_var('MAX_REQUESTS_PER_WORKER', file_config.get('max_requests_per_worker', 1000)),
            request_timeout=self._get_env_var('REQUEST_TIMEOUT', file_config.get('request_timeout', 30)),
            keepalive_timeout=self._get_env_var('KEEPALIVE_TIMEOUT', file_config.get('keepalive_timeout', 2)),
            max_concurrent_requests=self._get_env_var('MAX_CONCURRENT_REQUESTS', file_config.get('max_concurrent_requests', 100)),
            rate_limit_requests_per_minute=self._get_env_var('RATE_LIMIT_RPM', file_config.get('rate_limit_requests_per_minute', 60))
        )
    
    def get_feature_flags(self) -> FeatureFlags:
        """Get feature flags configuration."""
        file_config = self._load_yaml_file(self._get_config_file_path('features'))
        
        return FeatureFlags(
            enable_websockets=self._get_env_var('ENABLE_WEBSOCKETS', file_config.get('enable_websockets', True)),
            enable_caching=self._get_env_var('ENABLE_CACHING', file_config.get('enable_caching', True)),
            enable_rate_limiting=self._get_env_var('ENABLE_RATE_LIMITING', file_config.get('enable_rate_limiting', True)),
            enable_circuit_breakers=self._get_env_var('ENABLE_CIRCUIT_BREAKERS', file_config.get('enable_circuit_breakers', True)),
            enable_compression=self._get_env_var('ENABLE_COMPRESSION', file_config.get('enable_compression', True)),
            enable_background_tasks=self._get_env_var('ENABLE_BACKGROUND_TASKS', file_config.get('enable_background_tasks', True)),
            enable_health_checks=self._get_env_var('ENABLE_HEALTH_CHECKS', file_config.get('enable_health_checks', True)),
            experimental_features=self._get_env_var('EXPERIMENTAL_FEATURES', file_config.get('experimental_features', []))
        )
    
    def _generate_secret_key(self) -> str:
        """Generate a secure secret key."""
        import secrets
        secret_key = secrets.token_urlsafe(32)
        
        logger.warning("Generated new secret key. In production, set SECRET_KEY environment variable.")
        
        # Save to secrets file for persistence
        secrets_file = os.environ.get('SECRETS_FILE', 'secrets/secrets.json')
        secrets_dict = self.secret_manager.load_secrets_file(secrets_file)
        secrets_dict['secret_key'] = secret_key
        self.secret_manager.save_secrets_file(secrets_dict, secrets_file)
        
        return secret_key
    
    def validate_configuration(self) -> List[str]:
        """Validate all configuration and return list of issues."""
        issues = []
        
        try:
            # Validate database config
            db_config = self.get_database_config()
            if not db_config.url:
                issues.append("Database URL is not configured")
        except Exception as e:
            issues.append(f"Database configuration error: {e}")
        
        try:
            # Validate Redis config
            redis_config = self.get_redis_config()
            if not redis_config.url:
                issues.append("Redis URL is not configured")
        except Exception as e:
            issues.append(f"Redis configuration error: {e}")
        
        try:
            # Validate security config
            security_config = self.get_security_config()
            if len(security_config.secret_key) < 32:
                issues.append("Secret key is too short (minimum 32 characters)")
        except Exception as e:
            issues.append(f"Security configuration error: {e}")
        
        try:
            # Validate storage config
            storage_config = self.get_storage_config()
            if not os.path.exists(storage_config.upload_dir):
                issues.append(f"Upload directory does not exist: {storage_config.upload_dir}")
        except Exception as e:
            issues.append(f"Storage configuration error: {e}")
        
        # Environment-specific validations
        if self.environment == Environment.PRODUCTION:
            if 'SECRET_KEY' not in os.environ:
                issues.append("SECRET_KEY environment variable must be set in production")
            if 'DATABASE_URL' not in os.environ:
                issues.append("DATABASE_URL environment variable must be set in production")
        
        return issues
    
    def get_all_config(self) -> Dict[str, Any]:
        """Get all configuration as a dictionary (for debugging)."""
        return {
            'environment': self.environment.value,
            'database': self.get_database_config().__dict__,
            'redis': self.get_redis_config().__dict__,
            'security': {**self.get_security_config().__dict__, 'secret_key': '[REDACTED]'},
            'storage': self.get_storage_config().__dict__,
            'monitoring': self.get_monitoring_config().__dict__,
            'performance': self.get_performance_config().__dict__,
            'features': self.get_feature_flags().__dict__
        }


# Global configuration manager instance
_config_manager: Optional[ConfigurationManager] = None


@lru_cache(maxsize=1)
def get_config_manager() -> ConfigurationManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager()
    return _config_manager


def reload_configuration():
    """Reload configuration (clears cache)."""
    global _config_manager
    _config_manager = None
    get_config_manager.cache_clear()
    logger.info("Configuration reloaded")