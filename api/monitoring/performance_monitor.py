import time
import psutil
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import deque, defaultdict
import json
import redis
from fastapi import HTTPException

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MetricPoint:
    """Represents a single metric data point."""
    timestamp: float
    value: float
    tags: Dict[str, str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}

@dataclass
class SystemMetrics:
    """System-level performance metrics."""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_used_percent: float
    disk_free_gb: float
    process_cpu_percent: float
    process_memory_mb: float
    active_connections: int
    request_count: int
    error_count: int
    avg_response_time: float

@dataclass
class ApplicationMetrics:
    """Application-specific performance metrics."""
    timestamp: float
    active_jobs: int
    completed_jobs: int
    failed_jobs: int
    queue_size: int
    avg_processing_time: float
    video_upload_count: int
    url_processing_count: int
    websocket_connections: int
    cache_hit_rate: float
    database_connections: int

@dataclass
class Alert:
    """Performance alert definition."""
    id: str
    metric_name: str
    threshold: float
    operator: str  # 'gt', 'lt', 'eq'
    severity: str  # 'critical', 'warning', 'info'
    message: str
    enabled: bool = True
    cooldown_minutes: int = 5
    last_triggered: Optional[float] = None

class MetricsCollector:
    """Collects and stores performance metrics."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client or redis.Redis(host='localhost', port=6379, db=0)
        self.metrics_buffer = deque(maxlen=1000)  # Keep last 1000 metrics in memory
        self.request_times = deque(maxlen=100)  # Track last 100 request times
        self.error_count = 0
        self.request_count = 0
        self.start_time = time.time()
        
        # Application-specific counters
        self.job_counters = {
            'active': 0,
            'completed': 0,
            'failed': 0
        }
        self.upload_counters = {
            'video': 0,
            'url': 0
        }
        self.websocket_connections = 0
        
    def collect_system_metrics(self) -> SystemMetrics:
        """Collect current system performance metrics."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_used_mb = memory.used / (1024 * 1024)
            memory_available_mb = memory.available / (1024 * 1024)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_used_percent = (disk.used / disk.total) * 100
            disk_free_gb = disk.free / (1024 * 1024 * 1024)
            
            # Process metrics
            process = psutil.Process()
            process_cpu = process.cpu_percent()
            process_memory = process.memory_info().rss / (1024 * 1024)
            
            # Network/connection metrics
            active_connections = len(psutil.net_connections())
            
            # Application metrics
            avg_response_time = self._calculate_avg_response_time()
            
            metrics = SystemMetrics(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory_used_mb,
                memory_available_mb=memory_available_mb,
                disk_used_percent=disk_used_percent,
                disk_free_gb=disk_free_gb,
                process_cpu_percent=process_cpu,
                process_memory_mb=process_memory,
                active_connections=active_connections,
                request_count=self.request_count,
                error_count=self.error_count,
                avg_response_time=avg_response_time
            )
            
            # Store in buffer and Redis
            self.metrics_buffer.append(metrics)
            self._store_metrics_in_redis('system', asdict(metrics))
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            raise
    
    def collect_application_metrics(self) -> ApplicationMetrics:
        """Collect application-specific metrics."""
        try:
            # Get queue size from Redis
            queue_size = self._get_queue_size()
            
            # Calculate cache hit rate
            cache_hit_rate = self._calculate_cache_hit_rate()
            
            # Get database connection count
            db_connections = self._get_database_connections()
            
            # Calculate average processing time
            avg_processing_time = self._calculate_avg_processing_time()
            
            metrics = ApplicationMetrics(
                timestamp=time.time(),
                active_jobs=self.job_counters['active'],
                completed_jobs=self.job_counters['completed'],
                failed_jobs=self.job_counters['failed'],
                queue_size=queue_size,
                avg_processing_time=avg_processing_time,
                video_upload_count=self.upload_counters['video'],
                url_processing_count=self.upload_counters['url'],
                websocket_connections=self.websocket_connections,
                cache_hit_rate=cache_hit_rate,
                database_connections=db_connections
            )
            
            # Store in Redis
            self._store_metrics_in_redis('application', asdict(metrics))
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting application metrics: {e}")
            raise
    
    def record_request(self, duration: float, status_code: int):
        """Record a request with its duration and status code."""
        self.request_count += 1
        self.request_times.append(duration)
        
        if status_code >= 400:
            self.error_count += 1
        
        # Store request metric
        metric = {
            'timestamp': time.time(),
            'duration': duration,
            'status_code': status_code
        }
        self._store_metrics_in_redis('requests', metric)
    
    def record_job_event(self, event_type: str, job_id: str, processing_time: Optional[float] = None):
        """Record job-related events."""
        if event_type in ['started', 'active']:
            self.job_counters['active'] += 1
        elif event_type == 'completed':
            self.job_counters['active'] = max(0, self.job_counters['active'] - 1)
            self.job_counters['completed'] += 1
        elif event_type == 'failed':
            self.job_counters['active'] = max(0, self.job_counters['active'] - 1)
            self.job_counters['failed'] += 1
        
        # Store job event
        event = {
            'timestamp': time.time(),
            'event_type': event_type,
            'job_id': job_id,
            'processing_time': processing_time
        }
        self._store_metrics_in_redis('job_events', event)
    
    def record_upload_event(self, upload_type: str, file_size: Optional[int] = None):
        """Record upload events."""
        if upload_type in self.upload_counters:
            self.upload_counters[upload_type] += 1
        
        event = {
            'timestamp': time.time(),
            'upload_type': upload_type,
            'file_size': file_size
        }
        self._store_metrics_in_redis('upload_events', event)
    
    def update_websocket_connections(self, count: int):
        """Update WebSocket connection count."""
        self.websocket_connections = count
    
    def get_metrics_history(self, metric_type: str, hours: int = 24) -> List[Dict]:
        """Get historical metrics from Redis."""
        try:
            end_time = time.time()
            start_time = end_time - (hours * 3600)
            
            # Get metrics from Redis sorted set
            key = f"metrics:{metric_type}"
            raw_metrics = self.redis_client.zrangebyscore(
                key, start_time, end_time, withscores=True
            )
            
            metrics = []
            for data, timestamp in raw_metrics:
                try:
                    metric = json.loads(data)
                    metric['timestamp'] = timestamp
                    metrics.append(metric)
                except json.JSONDecodeError:
                    continue
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting metrics history: {e}")
            return []
    
    def _calculate_avg_response_time(self) -> float:
        """Calculate average response time from recent requests."""
        if not self.request_times:
            return 0.0
        return sum(self.request_times) / len(self.request_times)
    
    def _get_queue_size(self) -> int:
        """Get current queue size from Redis."""
        try:
            return self.redis_client.llen('celery') or 0
        except:
            return 0
    
    def _calculate_cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        try:
            info = self.redis_client.info('stats')
            hits = info.get('keyspace_hits', 0)
            misses = info.get('keyspace_misses', 0)
            total = hits + misses
            return (hits / total * 100) if total > 0 else 0.0
        except:
            return 0.0
    
    def _get_database_connections(self) -> int:
        """Get current database connection count."""
        # This would need to be implemented based on your database
        # For now, return a placeholder
        return 0
    
    def _calculate_avg_processing_time(self) -> float:
        """Calculate average job processing time."""
        try:
            # Get recent job events with processing times
            recent_events = self.get_metrics_history('job_events', hours=1)
            processing_times = [
                event['processing_time'] for event in recent_events 
                if event.get('processing_time') and event.get('event_type') == 'completed'
            ]
            
            if not processing_times:
                return 0.0
            
            return sum(processing_times) / len(processing_times)
            
        except Exception as e:
            logger.error(f"Error calculating avg processing time: {e}")
            return 0.0
    
    def _store_metrics_in_redis(self, metric_type: str, data: Dict):
        """Store metrics in Redis with timestamp-based sorting."""
        try:
            key = f"metrics:{metric_type}"
            timestamp = data.get('timestamp', time.time())
            
            # Store as JSON in sorted set with timestamp as score
            self.redis_client.zadd(key, {json.dumps(data): timestamp})
            
            # Keep only last 7 days of data
            cutoff = time.time() - (7 * 24 * 3600)
            self.redis_client.zremrangebyscore(key, 0, cutoff)
            
        except Exception as e:
            logger.error(f"Error storing metrics in Redis: {e}")

class AlertManager:
    """Manages performance alerts and notifications."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client or redis.Redis(host='localhost', port=6379, db=0)
        self.alerts = self._load_default_alerts()
        self.notification_handlers = []
    
    def _load_default_alerts(self) -> List[Alert]:
        """Load default alert configurations."""
        return [
            Alert(
                id="high_cpu",
                metric_name="cpu_percent",
                threshold=80.0,
                operator="gt",
                severity="warning",
                message="High CPU usage detected: {value}%"
            ),
            Alert(
                id="critical_cpu",
                metric_name="cpu_percent",
                threshold=95.0,
                operator="gt",
                severity="critical",
                message="Critical CPU usage: {value}%"
            ),
            Alert(
                id="high_memory",
                metric_name="memory_percent",
                threshold=85.0,
                operator="gt",
                severity="warning",
                message="High memory usage: {value}%"
            ),
            Alert(
                id="critical_memory",
                metric_name="memory_percent",
                threshold=95.0,
                operator="gt",
                severity="critical",
                message="Critical memory usage: {value}%"
            ),
            Alert(
                id="high_disk_usage",
                metric_name="disk_used_percent",
                threshold=90.0,
                operator="gt",
                severity="warning",
                message="High disk usage: {value}%"
            ),
            Alert(
                id="slow_response_time",
                metric_name="avg_response_time",
                threshold=5.0,
                operator="gt",
                severity="warning",
                message="Slow response time: {value}s"
            ),
            Alert(
                id="high_error_rate",
                metric_name="error_rate",
                threshold=10.0,
                operator="gt",
                severity="critical",
                message="High error rate: {value}%"
            ),
            Alert(
                id="queue_backlog",
                metric_name="queue_size",
                threshold=100,
                operator="gt",
                severity="warning",
                message="Large queue backlog: {value} jobs"
            )
        ]
    
    def check_alerts(self, system_metrics: SystemMetrics, app_metrics: ApplicationMetrics):
        """Check all alerts against current metrics."""
        current_time = time.time()
        
        # Combine metrics for checking
        all_metrics = {**asdict(system_metrics), **asdict(app_metrics)}
        
        # Calculate error rate
        if system_metrics.request_count > 0:
            all_metrics['error_rate'] = (system_metrics.error_count / system_metrics.request_count) * 100
        else:
            all_metrics['error_rate'] = 0.0
        
        for alert in self.alerts:
            if not alert.enabled:
                continue
            
            # Check cooldown period
            if (alert.last_triggered and 
                current_time - alert.last_triggered < alert.cooldown_minutes * 60):
                continue
            
            metric_value = all_metrics.get(alert.metric_name)
            if metric_value is None:
                continue
            
            # Check if alert condition is met
            triggered = False
            if alert.operator == "gt" and metric_value > alert.threshold:
                triggered = True
            elif alert.operator == "lt" and metric_value < alert.threshold:
                triggered = True
            elif alert.operator == "eq" and metric_value == alert.threshold:
                triggered = True
            
            if triggered:
                self._trigger_alert(alert, metric_value)
                alert.last_triggered = current_time
    
    def _trigger_alert(self, alert: Alert, value: float):
        """Trigger an alert and send notifications."""
        message = alert.message.format(value=value)
        
        alert_data = {
            'id': alert.id,
            'severity': alert.severity,
            'message': message,
            'metric_name': alert.metric_name,
            'threshold': alert.threshold,
            'current_value': value,
            'timestamp': time.time()
        }
        
        # Log the alert
        logger.warning(f"ALERT [{alert.severity.upper()}]: {message}")
        
        # Store alert in Redis
        try:
            key = f"alerts:{alert.severity}"
            self.redis_client.zadd(key, {json.dumps(alert_data): time.time()})
            
            # Keep only last 30 days of alerts
            cutoff = time.time() - (30 * 24 * 3600)
            self.redis_client.zremrangebyscore(key, 0, cutoff)
        except Exception as e:
            logger.error(f"Error storing alert: {e}")
        
        # Send notifications
        for handler in self.notification_handlers:
            try:
                handler(alert_data)
            except Exception as e:
                logger.error(f"Error sending notification: {e}")
    
    def add_notification_handler(self, handler):
        """Add a notification handler function."""
        self.notification_handlers.append(handler)
    
    def get_recent_alerts(self, severity: Optional[str] = None, hours: int = 24) -> List[Dict]:
        """Get recent alerts from Redis."""
        try:
            end_time = time.time()
            start_time = end_time - (hours * 3600)
            
            if severity:
                keys = [f"alerts:{severity}"]
            else:
                keys = [f"alerts:{sev}" for sev in ['critical', 'warning', 'info']]
            
            all_alerts = []
            for key in keys:
                raw_alerts = self.redis_client.zrangebyscore(
                    key, start_time, end_time, withscores=True
                )
                
                for data, timestamp in raw_alerts:
                    try:
                        alert = json.loads(data)
                        alert['timestamp'] = timestamp
                        all_alerts.append(alert)
                    except json.JSONDecodeError:
                        continue
            
            # Sort by timestamp (most recent first)
            all_alerts.sort(key=lambda x: x['timestamp'], reverse=True)
            return all_alerts
            
        except Exception as e:
            logger.error(f"Error getting recent alerts: {e}")
            return []

class PerformanceMonitor:
    """Main performance monitoring class."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client or redis.Redis(host='localhost', port=6379, db=0)
        self.metrics_collector = MetricsCollector(self.redis_client)
        self.alert_manager = AlertManager(self.redis_client)
        self.monitoring_active = False
        self.monitoring_interval = 60  # seconds
    
    async def start_monitoring(self):
        """Start the monitoring loop."""
        self.monitoring_active = True
        logger.info("Performance monitoring started")
        
        while self.monitoring_active:
            try:
                # Collect metrics
                system_metrics = self.metrics_collector.collect_system_metrics()
                app_metrics = self.metrics_collector.collect_application_metrics()
                
                # Check alerts
                self.alert_manager.check_alerts(system_metrics, app_metrics)
                
                # Wait for next collection interval
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.monitoring_interval)
    
    def stop_monitoring(self):
        """Stop the monitoring loop."""
        self.monitoring_active = False
        logger.info("Performance monitoring stopped")
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        try:
            system_metrics = self.metrics_collector.collect_system_metrics()
            app_metrics = self.metrics_collector.collect_application_metrics()
            
            return {
                'system': asdict(system_metrics),
                'application': asdict(app_metrics),
                'timestamp': time.time()
            }
        except Exception as e:
            logger.error(f"Error getting current metrics: {e}")
            raise HTTPException(status_code=500, detail="Failed to collect metrics")
    
    def get_metrics_dashboard_data(self, hours: int = 24) -> Dict[str, Any]:
        """Get comprehensive dashboard data."""
        try:
            # Get historical metrics
            system_history = self.metrics_collector.get_metrics_history('system', hours)
            app_history = self.metrics_collector.get_metrics_history('application', hours)
            request_history = self.metrics_collector.get_metrics_history('requests', hours)
            
            # Get recent alerts
            recent_alerts = self.alert_manager.get_recent_alerts(hours=hours)
            
            # Calculate summary statistics
            summary = self._calculate_summary_stats(system_history, app_history)
            
            return {
                'current_metrics': self.get_current_metrics(),
                'system_history': system_history[-100:],  # Last 100 points
                'application_history': app_history[-100:],
                'request_history': request_history[-100:],
                'recent_alerts': recent_alerts[:50],  # Last 50 alerts
                'summary': summary,
                'monitoring_status': {
                    'active': self.monitoring_active,
                    'interval': self.monitoring_interval,
                    'uptime': time.time() - self.metrics_collector.start_time
                }
            }
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            raise HTTPException(status_code=500, detail="Failed to get dashboard data")
    
    def _calculate_summary_stats(self, system_history: List[Dict], app_history: List[Dict]) -> Dict:
        """Calculate summary statistics from historical data."""
        if not system_history:
            return {}
        
        # Calculate averages and peaks
        cpu_values = [m['cpu_percent'] for m in system_history if 'cpu_percent' in m]
        memory_values = [m['memory_percent'] for m in system_history if 'memory_percent' in m]
        response_times = [m['avg_response_time'] for m in system_history if 'avg_response_time' in m]
        
        summary = {
            'avg_cpu': sum(cpu_values) / len(cpu_values) if cpu_values else 0,
            'peak_cpu': max(cpu_values) if cpu_values else 0,
            'avg_memory': sum(memory_values) / len(memory_values) if memory_values else 0,
            'peak_memory': max(memory_values) if memory_values else 0,
            'avg_response_time': sum(response_times) / len(response_times) if response_times else 0,
            'peak_response_time': max(response_times) if response_times else 0
        }
        
        if app_history:
            completed_jobs = [m['completed_jobs'] for m in app_history if 'completed_jobs' in m]
            failed_jobs = [m['failed_jobs'] for m in app_history if 'failed_jobs' in m]
            
            total_completed = max(completed_jobs) if completed_jobs else 0
            total_failed = max(failed_jobs) if failed_jobs else 0
            total_jobs = total_completed + total_failed
            
            summary.update({
                'total_jobs_processed': total_jobs,
                'job_success_rate': (total_completed / total_jobs * 100) if total_jobs > 0 else 100,
                'total_uploads': sum([m.get('video_upload_count', 0) + m.get('url_processing_count', 0) for m in app_history])
            })
        
        return summary
    
    def measure_time(self, metric_name: str):
        """Context manager to measure execution time."""
        from contextlib import contextmanager
        import time
        
        @contextmanager
        def timer():
            start_time = time.time()
            try:
                yield
            finally:
                duration = time.time() - start_time
                # Log the timing for now, could be extended to store metrics
                logger.info(f"Operation '{metric_name}' took {duration:.3f} seconds")
        
        return timer()

# Global performance monitor instance
performance_monitor = None

def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    global performance_monitor
    if performance_monitor is None:
        performance_monitor = PerformanceMonitor()
    return performance_monitor