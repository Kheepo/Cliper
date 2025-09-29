#!/usr/bin/env python3
"""
Settings Configuration for Video Processing Metrics Exporter

Provides configuration management for the metrics exporter with
environment variable support and validation.
"""

import os
from typing import List, Optional

from pydantic import BaseSettings, Field, validator


class ExporterSettings(BaseSettings):
    """Configuration settings for the metrics exporter."""
    
    # Exporter settings
    exporter_host: str = Field(default="0.0.0.0", env="EXPORTER_HOST")
    exporter_port: int = Field(default=9200, env="EXPORTER_PORT")
    exporter_workers: int = Field(default=1, env="EXPORTER_WORKERS")
    
    # Collection settings
    collection_interval: int = Field(default=15, env="COLLECTION_INTERVAL")
    collection_timeout: int = Field(default=30, env="COLLECTION_TIMEOUT")
    max_collection_errors: int = Field(default=5, env="MAX_COLLECTION_ERRORS")
    
    # Database settings
    database_url: str = Field(
        default="postgresql://postgres:password@localhost:5432/virality_clipper",
        env="DATABASE_URL"
    )
    database_pool_size: int = Field(default=5, env="DATABASE_POOL_SIZE")
    database_timeout: int = Field(default=30, env="DATABASE_TIMEOUT")
    
    # Redis settings
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        env="REDIS_URL"
    )
    redis_timeout: int = Field(default=10, env="REDIS_TIMEOUT")
    
    # API settings
    api_base_url: str = Field(
        default="http://localhost:8000",
        env="API_BASE_URL"
    )
    api_timeout: int = Field(default=30, env="API_TIMEOUT")
    
    # Flower settings (Celery monitoring)
    flower_url: str = Field(
        default="http://localhost:5555",
        env="FLOWER_URL"
    )
    flower_timeout: int = Field(default=10, env="FLOWER_TIMEOUT")
    
    # Collector settings
    enabled_collectors: List[str] = Field(
        default=[
            "system",
            "database", 
            "redis",
            "celery",
            "video_processing",
            "ai_service",
            "ffmpeg",
            "websocket"
        ],
        env="ENABLED_COLLECTORS"
    )
    
    # System monitoring settings
    system_disk_paths: List[str] = Field(
        default=["/", "/tmp", "/var"],
        env="SYSTEM_DISK_PATHS"
    )
    system_network_interfaces: List[str] = Field(
        default=[],  # Empty means all interfaces
        env="SYSTEM_NETWORK_INTERFACES"
    )
    
    # Video processing settings
    video_storage_paths: List[str] = Field(
        default=[
            "/app/uploads",
            "/app/processed",
            "/app/clips"
        ],
        env="VIDEO_STORAGE_PATHS"
    )
    
    # AI service settings
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    
    # Logging settings
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    log_file: Optional[str] = Field(default=None, env="LOG_FILE")
    
    # Health check settings
    health_check_interval: int = Field(default=60, env="HEALTH_CHECK_INTERVAL")
    health_check_timeout: int = Field(default=10, env="HEALTH_CHECK_TIMEOUT")
    
    # Performance settings
    max_concurrent_collections: int = Field(default=10, env="MAX_CONCURRENT_COLLECTIONS")
    collection_batch_size: int = Field(default=100, env="COLLECTION_BATCH_SIZE")
    
    # Security settings
    metrics_auth_token: Optional[str] = Field(default=None, env="METRICS_AUTH_TOKEN")
    allowed_hosts: List[str] = Field(
        default=["localhost", "127.0.0.1"],
        env="ALLOWED_HOSTS"
    )
    
    # Environment
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    @validator("enabled_collectors")
    def validate_collectors(cls, v):
        """Validate enabled collectors."""
        valid_collectors = {
            "system",
            "database",
            "redis", 
            "celery",
            "video_processing",
            "ai_service",
            "ffmpeg",
            "websocket"
        }
        
        if isinstance(v, str):
            v = [c.strip() for c in v.split(",")]
        
        invalid_collectors = set(v) - valid_collectors
        if invalid_collectors:
            raise ValueError(
                f"Invalid collectors: {invalid_collectors}. "
                f"Valid collectors: {valid_collectors}"
            )
        
        return v
    
    @validator("collection_interval")
    def validate_collection_interval(cls, v):
        """Validate collection interval."""
        if v < 5:
            raise ValueError("Collection interval must be at least 5 seconds")
        if v > 300:
            raise ValueError("Collection interval must be at most 300 seconds")
        return v
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Valid levels: {valid_levels}")
        return v.upper()
    
    @validator("log_format")
    def validate_log_format(cls, v):
        """Validate log format."""
        valid_formats = {"json", "text"}
        if v.lower() not in valid_formats:
            raise ValueError(f"Invalid log format: {v}. Valid formats: {valid_formats}")
        return v.lower()
    
    @validator("environment")
    def validate_environment(cls, v):
        """Validate environment."""
        valid_environments = {"development", "staging", "production"}
        if v.lower() not in valid_environments:
            raise ValueError(
                f"Invalid environment: {v}. Valid environments: {valid_environments}"
            )
        return v.lower()
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"
    
    def get_database_config(self) -> dict:
        """Get database configuration."""
        return {
            "url": self.database_url,
            "pool_size": self.database_pool_size,
            "timeout": self.database_timeout
        }
    
    def get_redis_config(self) -> dict:
        """Get Redis configuration."""
        return {
            "url": self.redis_url,
            "timeout": self.redis_timeout
        }
    
    def get_api_config(self) -> dict:
        """Get API configuration."""
        return {
            "base_url": self.api_base_url,
            "timeout": self.api_timeout
        }
    
    def get_collector_config(self, collector_name: str) -> dict:
        """Get configuration for a specific collector."""
        base_config = {
            "collection_interval": self.collection_interval,
            "collection_timeout": self.collection_timeout,
            "max_errors": self.max_collection_errors
        }
        
        # Collector-specific configurations
        if collector_name == "system":
            base_config.update({
                "disk_paths": self.system_disk_paths,
                "network_interfaces": self.system_network_interfaces
            })
        elif collector_name == "database":
            base_config.update(self.get_database_config())
        elif collector_name == "redis":
            base_config.update(self.get_redis_config())
        elif collector_name == "video_processing":
            base_config.update({
                "storage_paths": self.video_storage_paths,
                "api_config": self.get_api_config()
            })
        elif collector_name == "ai_service":
            base_config.update({
                "openai_api_key": self.openai_api_key,
                "anthropic_api_key": self.anthropic_api_key,
                "api_config": self.get_api_config()
            })
        elif collector_name == "celery":
            base_config.update({
                "flower_url": self.flower_url,
                "flower_timeout": self.flower_timeout,
                "redis_config": self.get_redis_config()
            })
        elif collector_name == "websocket":
            base_config.update({
                "api_config": self.get_api_config()
            })
        
        return base_config
    
    def validate_configuration(self) -> List[str]:
        """Validate the complete configuration and return any issues."""
        issues = []
        
        # Check required URLs are accessible
        required_services = {
            "database": self.database_url,
            "redis": self.redis_url,
            "api": self.api_base_url
        }
        
        for service, url in required_services.items():
            if not url:
                issues.append(f"Missing {service} URL")
            elif not url.startswith(("http://", "https://", "postgresql://", "redis://")):
                issues.append(f"Invalid {service} URL format: {url}")
        
        # Check storage paths exist (in production)
        if self.is_production:
            for path in self.video_storage_paths:
                if not os.path.exists(path):
                    issues.append(f"Video storage path does not exist: {path}")
        
        # Check AI API keys (if AI collector is enabled)
        if "ai_service" in self.enabled_collectors:
            if not self.openai_api_key and not self.anthropic_api_key:
                issues.append("No AI API keys configured but AI service collector is enabled")
        
        # Check port availability
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((self.exporter_host, self.exporter_port))
        except OSError:
            issues.append(f"Port {self.exporter_port} is already in use")
        
        return issues


# Global settings instance
settings = ExporterSettings()


def get_settings() -> ExporterSettings:
    """Get the global settings instance."""
    return settings


def reload_settings() -> ExporterSettings:
    """Reload settings from environment variables."""
    global settings
    settings = ExporterSettings()
    return settings