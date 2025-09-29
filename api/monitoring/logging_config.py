"""Centralized logging configuration and aggregation system."""

import os
import json
import logging
import logging.handlers
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio
from dataclasses import dataclass, asdict
from pathlib import Path
import gzip
import shutil
from concurrent.futures import ThreadPoolExecutor
import redis
from elasticsearch import Elasticsearch
from pythonjsonlogger import jsonlogger

@dataclass
class LogConfig:
    """Logging configuration settings."""
    log_level: str = "INFO"
    log_format: str = "json"  # json or text
    log_dir: str = "logs"
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    backup_count: int = 10
    enable_console: bool = True
    enable_file: bool = True
    enable_elasticsearch: bool = False
    enable_redis: bool = True
    elasticsearch_host: str = "localhost:9200"
    redis_url: str = "redis://localhost:6379"
    service_name: str = "cliper-api"
    environment: str = "development"
    
class StructuredFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional context."""
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        
        # Add standard fields
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['service'] = getattr(record, 'service', 'cliper-api')
        log_record['environment'] = getattr(record, 'environment', os.getenv('ENVIRONMENT', 'development'))
        log_record['version'] = getattr(record, 'version', '1.0.0')
        
        # Add request context if available
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id
        if hasattr(record, 'correlation_id'):
            log_record['correlation_id'] = record.correlation_id
            
        # Add performance metrics if available
        if hasattr(record, 'duration'):
            log_record['duration'] = record.duration
        if hasattr(record, 'memory_usage'):
            log_record['memory_usage'] = record.memory_usage
            
class ElasticsearchHandler(logging.Handler):
    """Custom handler for sending logs to Elasticsearch."""
    
    def __init__(self, elasticsearch_host: str, index_prefix: str = "cliper-logs"):
        super().__init__()
        self.es_client = Elasticsearch([elasticsearch_host])
        self.index_prefix = index_prefix
        self.executor = ThreadPoolExecutor(max_workers=2)
        
    def emit(self, record):
        try:
            # Format the record
            log_entry = self.format(record)
            
            # Create index name with date
            index_name = f"{self.index_prefix}-{datetime.now().strftime('%Y.%m.%d')}"
            
            # Send to Elasticsearch asynchronously
            self.executor.submit(self._send_to_elasticsearch, index_name, log_entry)
            
        except Exception as e:
            self.handleError(record)
            
    def _send_to_elasticsearch(self, index_name: str, log_entry: str):
        try:
            doc = json.loads(log_entry)
            self.es_client.index(index=index_name, body=doc)
        except Exception as e:
            print(f"Failed to send log to Elasticsearch: {e}")
            
class RedisHandler(logging.Handler):
    """Custom handler for sending logs to Redis for real-time monitoring."""
    
    def __init__(self, redis_url: str, key_prefix: str = "cliper:logs"):
        super().__init__()
        self.redis_client = redis.from_url(redis_url)
        self.key_prefix = key_prefix
        
    def emit(self, record):
        try:
            log_entry = self.format(record)
            
            # Store in Redis list (FIFO)
            key = f"{self.key_prefix}:{record.levelname.lower()}"
            self.redis_client.lpush(key, log_entry)
            
            # Keep only last 1000 entries per level
            self.redis_client.ltrim(key, 0, 999)
            
            # Set expiration for the key (24 hours)
            self.redis_client.expire(key, 86400)
            
            # Also store in a general log stream
            general_key = f"{self.key_prefix}:all"
            self.redis_client.lpush(general_key, log_entry)
            self.redis_client.ltrim(general_key, 0, 4999)  # Keep more for general logs
            self.redis_client.expire(general_key, 86400)
            
        except Exception as e:
            self.handleError(record)
            
class LogAggregator:
    """Central log aggregation and management system."""
    
    def __init__(self, config: LogConfig):
        self.config = config
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """Setup the main logger with all handlers."""
        # Create logs directory
        log_dir = Path(self.config.log_dir)
        log_dir.mkdir(exist_ok=True)
        
        # Get root logger
        logger = logging.getLogger()
        logger.setLevel(getattr(logging, self.config.log_level.upper()))
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Setup formatters
        if self.config.log_format == "json":
            formatter = StructuredFormatter(
                '%(timestamp)s %(level)s %(name)s %(message)s'
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s'
            )
            
        # Console handler
        if self.config.enable_console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
            
        # File handler with rotation
        if self.config.enable_file:
            file_handler = logging.handlers.RotatingFileHandler(
                log_dir / f"{self.config.service_name}.log",
                maxBytes=self.config.max_file_size,
                backupCount=self.config.backup_count
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
            # Error file handler
            error_handler = logging.handlers.RotatingFileHandler(
                log_dir / f"{self.config.service_name}-errors.log",
                maxBytes=self.config.max_file_size,
                backupCount=self.config.backup_count
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(formatter)
            logger.addHandler(error_handler)
            
        # Elasticsearch handler
        if self.config.enable_elasticsearch:
            try:
                es_handler = ElasticsearchHandler(self.config.elasticsearch_host)
                es_handler.setFormatter(StructuredFormatter())
                logger.addHandler(es_handler)
            except Exception as e:
                print(f"Failed to setup Elasticsearch handler: {e}")
                
        # Redis handler
        if self.config.enable_redis:
            try:
                redis_handler = RedisHandler(self.config.redis_url)
                redis_handler.setFormatter(StructuredFormatter())
                logger.addHandler(redis_handler)
            except Exception as e:
                print(f"Failed to setup Redis handler: {e}")
                
        return logger
        
    def compress_old_logs(self):
        """Compress old log files to save space."""
        log_dir = Path(self.config.log_dir)
        
        for log_file in log_dir.glob("*.log.*"):
            if not log_file.name.endswith('.gz'):
                try:
                    with open(log_file, 'rb') as f_in:
                        with gzip.open(f"{log_file}.gz", 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    
                    # Remove original file
                    log_file.unlink()
                    print(f"Compressed log file: {log_file}")
                    
                except Exception as e:
                    print(f"Failed to compress {log_file}: {e}")
                    
    def get_log_stats(self) -> Dict[str, Any]:
        """Get logging statistics."""
        log_dir = Path(self.config.log_dir)
        stats = {
            "total_log_files": 0,
            "total_size_mb": 0,
            "compressed_files": 0,
            "files": []
        }
        
        if log_dir.exists():
            for log_file in log_dir.glob("*.log*"):
                file_size = log_file.stat().st_size
                stats["total_log_files"] += 1
                stats["total_size_mb"] += file_size / (1024 * 1024)
                
                if log_file.name.endswith('.gz'):
                    stats["compressed_files"] += 1
                    
                stats["files"].append({
                    "name": log_file.name,
                    "size_mb": round(file_size / (1024 * 1024), 2),
                    "modified": datetime.fromtimestamp(log_file.stat().st_mtime).isoformat()
                })
                
        stats["total_size_mb"] = round(stats["total_size_mb"], 2)
        return stats
        
    async def get_recent_logs(self, level: str = "all", limit: int = 100) -> list:
        """Get recent logs from Redis."""
        try:
            redis_client = redis.from_url(self.config.redis_url)
            key = f"cliper:logs:{level}"
            
            logs = redis_client.lrange(key, 0, limit - 1)
            return [json.loads(log) for log in logs]
            
        except Exception as e:
            self.logger.error(f"Failed to get recent logs: {e}")
            return []
            
# Global log aggregator instance
log_config = LogConfig(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_format=os.getenv("LOG_FORMAT", "json"),
    enable_elasticsearch=os.getenv("ENABLE_ELASTICSEARCH", "false").lower() == "true",
    enable_redis=os.getenv("ENABLE_REDIS_LOGGING", "true").lower() == "true",
    elasticsearch_host=os.getenv("ELASTICSEARCH_HOST", "localhost:9200"),
    redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
    service_name=os.getenv("SERVICE_NAME", "cliper-api"),
    environment=os.getenv("ENVIRONMENT", "development")
)

log_aggregator = LogAggregator(log_config)

# Context manager for adding request context to logs
class LogContext:
    """Context manager for adding request-specific context to logs."""
    
    def __init__(self, **context):
        self.context = context
        self.old_factory = logging.getLogRecordFactory()
        
    def __enter__(self):
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record
            
        logging.setLogRecordFactory(record_factory)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self.old_factory)
        
# Utility functions
def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name."""
    return logging.getLogger(name)
    
def log_performance(func):
    """Decorator to log function performance."""
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        start_time = datetime.now()
        
        try:
            result = func(*args, **kwargs)
            duration = (datetime.now() - start_time).total_seconds()
            
            with LogContext(duration=duration, function=func.__name__):
                logger.info(f"Function {func.__name__} completed successfully")
                
            return result
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            
            with LogContext(duration=duration, function=func.__name__, error=str(e)):
                logger.error(f"Function {func.__name__} failed: {e}")
                
            raise
            
    return wrapper