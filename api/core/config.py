"""Configuration settings for the API."""

import os
from typing import Optional
from pydantic_settings import BaseSettings

class StorageConfig:
    """Storage configuration."""
    upload_path: str = "./uploads"
    output_path: str = "./outputs"
    temp_path: str = "./temp"
    max_file_size: int = 500 * 1024 * 1024  # 500MB
    allowed_extensions: list = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv']
    cleanup_interval: int = 3600  # seconds
    retention_days: int = 30


class Settings(BaseSettings):
    """Application settings."""
    
    # Database settings
    database_url: str = os.getenv('DATABASE_URL', 'postgresql://localhost/cliper')
    redis_url: str = os.getenv('REDIS_URL', 'redis://localhost:6379')
    
    # API settings
    api_host: str = os.getenv('API_HOST', '0.0.0.0')
    api_port: int = int(os.getenv('API_PORT', '8000'))
    debug: bool = os.getenv('DEBUG', 'False').lower() == 'true'
    
    # Security settings
    secret_key: str = os.getenv('SECRET_KEY', 'your-secret-key-here')
    algorithm: str = 'HS256'
    access_token_expire_minutes: int = 30
    
    # Supabase settings
    supabase_url: str = os.getenv('SUPABASE_URL', '')
    supabase_anon_key: str = os.getenv('SUPABASE_ANON_KEY', '')
    supabase_service_role_key: str = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')
    
    # Storage settings
    storage: StorageConfig = StorageConfig()
    
    # Monitoring settings
    monitoring_enabled: bool = os.getenv('MONITORING_ENABLED', 'True').lower() == 'true'
    metrics_retention_hours: int = int(os.getenv('METRICS_RETENTION_HOURS', '24'))
    
    # Logging settings
    log_level: str = os.getenv('LOG_LEVEL', 'INFO')
    log_format: str = os.getenv('LOG_FORMAT', 'json')
    
    class Config:
        env_file = '.env'
        case_sensitive = False
        extra = 'ignore'  # Allow extra environment variables

# Global settings instance
settings = Settings()

def get_settings() -> Settings:
    """Get application settings."""
    return settings