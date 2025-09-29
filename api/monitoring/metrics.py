"""Comprehensive monitoring and metrics collection for the Cliper application."""

import time
import psutil
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict, deque

from prometheus_client import (
    Counter, Histogram, Gauge, Summary, Info,
    CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
)
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.types import ASGIApp
import redis
# SQLAlchemy imports disabled for Firebase migration
# from sqlalchemy import text
# from sqlalchemy.orm import Session

# from ..core.database import get_db_pool
from ..core.config import settings

# Create custom registry for application metrics
registry = CollectorRegistry()

# HTTP Metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code'],
    registry=registry
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=registry
)

http_request_size_bytes = Histogram(
    'http_request_size_bytes',
    'HTTP request size in bytes',
    ['method', 'endpoint'],
    registry=registry
)

http_response_size_bytes = Histogram(
    'http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'endpoint'],
    registry=registry
)

# Application Metrics
active_users = Gauge(
    'active_users_total',
    'Number of active users',
    registry=registry
)

video_processing_duration = Histogram(
    'video_processing_duration_seconds',
    'Video processing duration in seconds',
    ['processing_type'],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600],
    registry=registry
)

video_processing_total = Counter(
    'video_processing_total',
    'Total video processing requests',
    ['processing_type', 'status'],
    registry=registry
)

video_queue_size = Gauge(
    'video_processing_queue_size',
    'Number of videos in processing queue',
    registry=registry
)

file_uploads_total = Counter(
    'file_uploads_total',
    'Total file uploads',
    ['file_type', 'status'],
    registry=registry
)

file_upload_size_bytes = Histogram(
    'file_upload_size_bytes',
    'File upload size in bytes',
    ['file_type'],
    registry=registry
)

# Database Metrics
db_connections_active = Gauge(
    'database_connections_active',
    'Active database connections',
    registry=registry
)

db_query_duration_seconds = Histogram(
    'database_query_duration_seconds',
    'Database query duration in seconds',
    ['query_type'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    registry=registry
)

db_queries_total = Counter(
    'database_queries_total',
    'Total database queries',
    ['query_type', 'status'],
    registry=registry
)

# Redis Metrics
redis_operations_total = Counter(
    'redis_operations_total',
    'Total Redis operations',
    ['operation', 'status'],
    registry=registry
)

redis_operation_duration_seconds = Histogram(
    'redis_operation_duration_seconds',
    'Redis operation duration in seconds',
    ['operation'],
    registry=registry
)

redis_memory_usage_bytes = Gauge(
    'redis_memory_usage_bytes',
    'Redis memory usage in bytes',
    registry=registry
)

# System Metrics
system_cpu_usage_percent = Gauge(
    'system_cpu_usage_percent',
    'System CPU usage percentage',
    registry=registry
)

system_memory_usage_bytes = Gauge(
    'system_memory_usage_bytes',
    'System memory usage in bytes',
    ['type'],
    registry=registry
)

system_disk_usage_bytes = Gauge(
    'system_disk_usage_bytes',
    'System disk usage in bytes',
    ['device', 'type'],
    registry=registry
)

system_network_bytes = Counter(
    'system_network_bytes_total',
    'System network bytes',
    ['interface', 'direction'],
    registry=registry
)

# Error Metrics
errors_total = Counter(
    'errors_total',
    'Total application errors',
    ['error_type', 'severity'],
    registry=registry
)

# Business Metrics
user_registrations_total = Counter(
    'user_registrations_total',
    'Total user registrations',
    ['source'],
    registry=registry
)

user_logins_total = Counter(
    'user_logins_total',
    'Total user logins',
    ['status'],
    registry=registry
)

video_views_total = Counter(
    'video_views_total',
    'Total video views',
    registry=registry
)

video_downloads_total = Counter(
    'video_downloads_total',
    'Total video downloads',
    registry=registry
)

# Application Info
app_info = Info(
    'cliper_app_info',
    'Cliper application information',
    registry=registry
)

class MetricsCollector:
    """Centralized metrics collection and management."""
    
    def __init__(self):
        self.redis_client = redis.Redis.from_url(settings.redis_url)
        self.start_time = time.time()
        self.request_times = deque(maxlen=1000)  # Keep last 1000 request times
        self.error_counts = defaultdict(int)
        
        # Set application info
        app_info.info({
            'version': getattr(settings, 'VERSION', '1.0.0'),
            'environment': getattr(settings, 'ENVIRONMENT', 'production'),
            'start_time': str(datetime.utcnow())
        })
    
    def record_http_request(self, method: str, endpoint: str, status_code: int, 
                          duration: float, request_size: int, response_size: int):
        """Record HTTP request metrics."""
        http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code
        ).inc()
        
        http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
        
        http_request_size_bytes.labels(
            method=method,
            endpoint=endpoint
        ).observe(request_size)
        
        http_response_size_bytes.labels(
            method=method,
            endpoint=endpoint
        ).observe(response_size)
        
        # Track request times for rate calculation
        self.request_times.append(time.time())
    
    def record_video_processing(self, processing_type: str, duration: float, status: str):
        """Record video processing metrics."""
        video_processing_duration.labels(
            processing_type=processing_type
        ).observe(duration)
        
        video_processing_total.labels(
            processing_type=processing_type,
            status=status
        ).inc()
    
    def record_file_upload(self, file_type: str, size: int, status: str):
        """Record file upload metrics."""
        file_uploads_total.labels(
            file_type=file_type,
            status=status
        ).inc()
        
        if status == 'success':
            file_upload_size_bytes.labels(
                file_type=file_type
            ).observe(size)
    
    def record_database_query(self, query_type: str, duration: float, status: str):
        """Record database query metrics."""
        db_query_duration_seconds.labels(
            query_type=query_type
        ).observe(duration)
        
        db_queries_total.labels(
            query_type=query_type,
            status=status
        ).inc()
    
    def record_redis_operation(self, operation: str, duration: float, status: str):
        """Record Redis operation metrics."""
        redis_operations_total.labels(
            operation=operation,
            status=status
        ).inc()
        
        redis_operation_duration_seconds.labels(
            operation=operation
        ).observe(duration)
    
    def record_error(self, error_type: str, severity: str):
        """Record application error."""
        errors_total.labels(
            error_type=error_type,
            severity=severity
        ).inc()
        
        self.error_counts[f"{error_type}:{severity}"] += 1
    
    def record_business_metric(self, metric_type: str, labels: Dict[str, str] = None):
        """Record business metrics."""
        if metric_type == 'user_registration':
            source = labels.get('source', 'web') if labels else 'web'
            user_registrations_total.labels(source=source).inc()
        
        elif metric_type == 'user_login':
            status = labels.get('status', 'success') if labels else 'success'
            user_logins_total.labels(status=status).inc()
        
        elif metric_type == 'video_view':
            video_views_total.inc()
        
        elif metric_type == 'video_download':
            video_downloads_total.inc()
    
    def update_system_metrics(self):
        """Update system resource metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            system_cpu_usage_percent.set(cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            system_memory_usage_bytes.labels(type='used').set(memory.used)
            system_memory_usage_bytes.labels(type='available').set(memory.available)
            system_memory_usage_bytes.labels(type='total').set(memory.total)
            
            # Disk usage
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    device = partition.device.replace('\\', '_').replace(':', '')
                    system_disk_usage_bytes.labels(device=device, type='used').set(usage.used)
                    system_disk_usage_bytes.labels(device=device, type='free').set(usage.free)
                    system_disk_usage_bytes.labels(device=device, type='total').set(usage.total)
                except (PermissionError, OSError):
                    continue
            
            # Network I/O
            network = psutil.net_io_counters(pernic=True)
            for interface, stats in network.items():
                system_network_bytes.labels(interface=interface, direction='sent').inc(stats.bytes_sent)
                system_network_bytes.labels(interface=interface, direction='recv').inc(stats.bytes_recv)
            
        except Exception as e:
            self.record_error('system_metrics_collection', 'warning')
            print(f"Error collecting system metrics: {e}")
    
    def update_application_metrics(self):
        """Update application-specific metrics."""
        try:
            # Active users (users active in last 5 minutes)
            active_count = self.redis_client.zcount(
                'active_users',
                int(time.time()) - 300,  # 5 minutes ago
                int(time.time())
            )
            active_users.set(active_count)
            
            # Video processing queue size
            queue_size = self.redis_client.llen('video_processing_queue')
            video_queue_size.set(queue_size)
            
            # Redis memory usage
            redis_info = self.redis_client.info('memory')
            redis_memory_usage_bytes.set(redis_info.get('used_memory', 0))
            
        except Exception as e:
            self.record_error('application_metrics_collection', 'warning')
            print(f"Error collecting application metrics: {e}")
    
    def update_database_metrics(self):
        """Update database metrics."""
        try:
            with engine.connect() as conn:
                # Active connections
                result = conn.execute(text(
                    "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
                ))
                active_connections = result.scalar()
                db_connections_active.set(active_connections)
                
        except Exception as e:
            self.record_error('database_metrics_collection', 'warning')
            print(f"Error collecting database metrics: {e}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status."""
        health = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'uptime_seconds': time.time() - self.start_time,
            'checks': {}
        }
        
        # Database health
        try:
            with engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            health['checks']['database'] = {'status': 'healthy'}
        except Exception as e:
            health['checks']['database'] = {'status': 'unhealthy', 'error': str(e)}
            health['status'] = 'unhealthy'
        
        # Redis health
        try:
            self.redis_client.ping()
            health['checks']['redis'] = {'status': 'healthy'}
        except Exception as e:
            health['checks']['redis'] = {'status': 'unhealthy', 'error': str(e)}
            health['status'] = 'unhealthy'
        
        # System resources
        try:
            cpu_percent = psutil.cpu_percent()
            memory_percent = psutil.virtual_memory().percent
            
            health['checks']['system'] = {
                'status': 'healthy' if cpu_percent < 90 and memory_percent < 90 else 'degraded',
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent
            }
            
            if cpu_percent > 95 or memory_percent > 95:
                health['status'] = 'unhealthy'
            elif cpu_percent > 80 or memory_percent > 80:
                health['status'] = 'degraded'
                
        except Exception as e:
            health['checks']['system'] = {'status': 'unknown', 'error': str(e)}
        
        # Error rate check
        recent_errors = sum(
            count for error_type, count in self.error_counts.items()
            if 'critical' in error_type or 'error' in error_type
        )
        
        if recent_errors > 10:  # More than 10 critical errors
            health['status'] = 'unhealthy'
        elif recent_errors > 5:
            health['status'] = 'degraded'
        
        health['checks']['errors'] = {
            'status': 'healthy' if recent_errors <= 5 else 'degraded',
            'recent_error_count': recent_errors
        }
        
        return health
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary for dashboard."""
        current_time = time.time()
        
        # Calculate request rate (requests per minute)
        recent_requests = [t for t in self.request_times if current_time - t < 60]
        request_rate = len(recent_requests)
        
        return {
            'uptime_seconds': current_time - self.start_time,
            'request_rate_per_minute': request_rate,
            'total_requests': len(self.request_times),
            'error_counts': dict(self.error_counts),
            'active_users': active_users._value._value,
            'queue_size': video_queue_size._value._value,
            'system': {
                'cpu_percent': system_cpu_usage_percent._value._value,
                'memory_used_bytes': system_memory_usage_bytes.labels(type='used')._value._value
            }
        }

class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP metrics."""
    
    def __init__(self, app: ASGIApp, metrics_collector: MetricsCollector):
        super().__init__(app)
        self.metrics = metrics_collector
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        start_time = time.time()
        
        # Get request size
        request_size = 0
        if hasattr(request, 'body'):
            try:
                body = await request.body()
                request_size = len(body)
            except Exception:
                pass
        
        # Process request
        response = await call_next(request)
        
        # Calculate metrics
        duration = time.time() - start_time
        method = request.method
        endpoint = self._get_endpoint_name(request)
        status_code = response.status_code
        
        # Get response size
        response_size = 0
        if hasattr(response, 'body'):
            try:
                response_size = len(response.body)
            except Exception:
                pass
        
        # Record metrics
        self.metrics.record_http_request(
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            duration=duration,
            request_size=request_size,
            response_size=response_size
        )
        
        # Record errors
        if status_code >= 500:
            self.metrics.record_error('http_5xx', 'error')
        elif status_code >= 400:
            self.metrics.record_error('http_4xx', 'warning')
        
        return response
    
    def _get_endpoint_name(self, request: Request) -> str:
        """Extract endpoint name from request."""
        path = request.url.path
        
        # Normalize paths with IDs
        import re
        path = re.sub(r'/\d+', '/{id}', path)
        path = re.sub(r'/[a-f0-9-]{36}', '/{uuid}', path)
        
        return path

# Monitoring decorators
def monitor_function(metric_name: str, labels: Dict[str, str] = None):
    """Decorator to monitor function execution."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            status = 'success'
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = 'error'
                metrics_collector.record_error(metric_name, 'error')
                raise
            finally:
                duration = time.time() - start_time
                
                if metric_name == 'video_processing':
                    processing_type = labels.get('type', 'unknown') if labels else 'unknown'
                    metrics_collector.record_video_processing(processing_type, duration, status)
                elif metric_name == 'database_query':
                    query_type = labels.get('type', 'unknown') if labels else 'unknown'
                    metrics_collector.record_database_query(query_type, duration, status)
                elif metric_name == 'redis_operation':
                    operation = labels.get('operation', 'unknown') if labels else 'unknown'
                    metrics_collector.record_redis_operation(operation, duration, status)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            status = 'success'
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status = 'error'
                metrics_collector.record_error(metric_name, 'error')
                raise
            finally:
                duration = time.time() - start_time
                
                if metric_name == 'video_processing':
                    processing_type = labels.get('type', 'unknown') if labels else 'unknown'
                    metrics_collector.record_video_processing(processing_type, duration, status)
                elif metric_name == 'database_query':
                    query_type = labels.get('type', 'unknown') if labels else 'unknown'
                    metrics_collector.record_database_query(query_type, duration, status)
                elif metric_name == 'redis_operation':
                    operation = labels.get('operation', 'unknown') if labels else 'unknown'
                    metrics_collector.record_redis_operation(operation, duration, status)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

# Global metrics collector instance
metrics_collector = MetricsCollector()

# Background task to update metrics
async def update_metrics_task():
    """Background task to periodically update metrics."""
    while True:
        try:
            metrics_collector.update_system_metrics()
            metrics_collector.update_application_metrics()
            metrics_collector.update_database_metrics()
        except Exception as e:
            print(f"Error updating metrics: {e}")
        
        await asyncio.sleep(30)  # Update every 30 seconds

def get_metrics_response() -> Response:
    """Get Prometheus metrics response."""
    metrics_data = generate_latest(registry)
    return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)

def get_health_response() -> Dict[str, Any]:
    """Get health check response."""
    return metrics_collector.get_health_status()

def get_metrics_summary_response() -> Dict[str, Any]:
    """Get metrics summary response."""
    return metrics_collector.get_metrics_summary()