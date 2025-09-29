"""Comprehensive monitoring and health check system.

Provides:
- Application health monitoring
- Performance metrics collection
- Error tracking and alerting
- Resource usage monitoring
- API endpoint monitoring
- Database health checks
- Service dependency monitoring
"""

import os
import time
import psutil
import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import json
import threading
from contextlib import asynccontextmanager
from functools import wraps

logger = logging.getLogger(__name__)

class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DOWN = "down"

class MetricType(Enum):
    """Metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"

@dataclass
class HealthCheck:
    """Health check definition."""
    name: str
    check_func: Callable
    interval: float = 60.0  # seconds
    timeout: float = 30.0   # seconds
    critical: bool = False
    last_check: Optional[datetime] = None
    last_status: HealthStatus = HealthStatus.HEALTHY
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    max_failures: int = 3

@dataclass
class Metric:
    """Metric data structure."""
    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)
    description: str = ""

@dataclass
class Alert:
    """Alert definition."""
    id: str
    title: str
    description: str
    severity: str
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class MonitoringSystem:
    """Comprehensive monitoring system."""
    
    def __init__(self):
        self.health_checks: Dict[str, HealthCheck] = {}
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.alerts: Dict[str, Alert] = {}
        self.performance_data: deque = deque(maxlen=1000)
        
        # Monitoring state
        self._monitoring_active = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._alert_handlers: List[Callable] = []
        
        # Performance tracking
        self._request_times: deque = deque(maxlen=1000)
        self._error_counts = defaultdict(int)
        self._endpoint_stats = defaultdict(lambda: {
            'count': 0,
            'total_time': 0,
            'errors': 0,
            'last_access': None
        })
        
        # System metrics
        self._system_metrics_interval = 30.0
        
        # Register default health checks
        self._register_default_health_checks()
    
    def start_monitoring(self):
        """Start the monitoring system."""
        if not self._monitoring_active:
            self._monitoring_active = True
            self._monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True
            )
            self._monitor_thread.start()
            logger.info("Monitoring system started")
    
    def stop_monitoring(self):
        """Stop the monitoring system."""
        self._monitoring_active = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        logger.info("Monitoring system stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        last_system_metrics = time.time()
        
        while self._monitoring_active:
            try:
                current_time = time.time()
                
                # Run health checks
                self._run_health_checks()
                
                # Collect system metrics
                if current_time - last_system_metrics >= self._system_metrics_interval:
                    self._collect_system_metrics()
                    last_system_metrics = current_time
                
                # Process alerts
                self._process_alerts()
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(10)
    
    def register_health_check(self, health_check: HealthCheck):
        """Register a health check."""
        self.health_checks[health_check.name] = health_check
        logger.info(f"Registered health check: {health_check.name}")
    
    def _register_default_health_checks(self):
        """Register default health checks."""
        # Memory health check
        self.register_health_check(HealthCheck(
            name="memory",
            check_func=self._check_memory_health,
            interval=30.0,
            critical=True
        ))
        
        # Disk space health check
        self.register_health_check(HealthCheck(
            name="disk_space",
            check_func=self._check_disk_health,
            interval=60.0,
            critical=True
        ))
        
        # CPU health check
        self.register_health_check(HealthCheck(
            name="cpu",
            check_func=self._check_cpu_health,
            interval=30.0,
            critical=False
        ))
    
    def _run_health_checks(self):
        """Run all health checks."""
        current_time = datetime.utcnow()
        
        for name, check in self.health_checks.items():
            # Check if it's time to run this health check
            if (check.last_check is None or 
                (current_time - check.last_check).total_seconds() >= check.interval):
                
                try:
                    # Run the health check with timeout
                    start_time = time.time()
                    result = check.check_func()
                    duration = time.time() - start_time
                    
                    if duration > check.timeout:
                        raise TimeoutError(f"Health check {name} timed out after {duration:.2f}s")
                    
                    # Update check status
                    check.last_check = current_time
                    check.last_status = result.get('status', HealthStatus.HEALTHY)
                    check.last_error = result.get('error')
                    
                    if check.last_status == HealthStatus.HEALTHY:
                        check.consecutive_failures = 0
                    else:
                        check.consecutive_failures += 1
                    
                    # Record metric
                    self.record_metric(
                        f"health_check_{name}",
                        1 if check.last_status == HealthStatus.HEALTHY else 0,
                        MetricType.GAUGE,
                        tags={"status": check.last_status.value}
                    )
                    
                    # Generate alert if needed
                    if (check.consecutive_failures >= check.max_failures and 
                        check.critical):
                        self._generate_alert(
                            f"health_check_{name}_failed",
                            f"Health check {name} failed {check.consecutive_failures} times",
                            f"Health check {name} has failed consecutively. Last error: {check.last_error}",
                            "critical" if check.critical else "warning"
                        )
                    
                except Exception as e:
                    logger.error(f"Health check {name} failed: {e}")
                    check.last_check = current_time
                    check.last_status = HealthStatus.CRITICAL
                    check.last_error = str(e)
                    check.consecutive_failures += 1
    
    def _check_memory_health(self) -> Dict[str, Any]:
        """Check memory health."""
        try:
            memory = psutil.virtual_memory()
            process = psutil.Process()
            process_memory = process.memory_info()
            
            # Check system memory
            if memory.percent > 95:
                return {
                    "status": HealthStatus.CRITICAL,
                    "error": f"System memory usage critical: {memory.percent:.1f}%"
                }
            elif memory.percent > 85:
                return {
                    "status": HealthStatus.WARNING,
                    "error": f"System memory usage high: {memory.percent:.1f}%"
                }
            
            # Check process memory
            process_mb = process_memory.rss / 1024 / 1024
            if process_mb > 2048:  # 2GB
                return {
                    "status": HealthStatus.WARNING,
                    "error": f"Process memory usage high: {process_mb:.1f}MB"
                }
            
            return {"status": HealthStatus.HEALTHY}
            
        except Exception as e:
            return {
                "status": HealthStatus.CRITICAL,
                "error": f"Memory health check failed: {e}"
            }
    
    def _check_disk_health(self) -> Dict[str, Any]:
        """Check disk space health."""
        try:
            disk_usage = psutil.disk_usage('/')
            percent_used = (disk_usage.used / disk_usage.total) * 100
            
            if percent_used > 95:
                return {
                    "status": HealthStatus.CRITICAL,
                    "error": f"Disk space critical: {percent_used:.1f}% used"
                }
            elif percent_used > 85:
                return {
                    "status": HealthStatus.WARNING,
                    "error": f"Disk space high: {percent_used:.1f}% used"
                }
            
            return {"status": HealthStatus.HEALTHY}
            
        except Exception as e:
            return {
                "status": HealthStatus.CRITICAL,
                "error": f"Disk health check failed: {e}"
            }
    
    def _check_cpu_health(self) -> Dict[str, Any]:
        """Check CPU health."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            
            if cpu_percent > 95:
                return {
                    "status": HealthStatus.WARNING,
                    "error": f"CPU usage very high: {cpu_percent:.1f}%"
                }
            elif cpu_percent > 85:
                return {
                    "status": HealthStatus.WARNING,
                    "error": f"CPU usage high: {cpu_percent:.1f}%"
                }
            
            return {"status": HealthStatus.HEALTHY}
            
        except Exception as e:
            return {
                "status": HealthStatus.CRITICAL,
                "error": f"CPU health check failed: {e}"
            }
    
    def _collect_system_metrics(self):
        """Collect system performance metrics."""
        try:
            # Memory metrics
            memory = psutil.virtual_memory()
            process = psutil.Process()
            process_memory = process.memory_info()
            
            self.record_metric("system_memory_percent", memory.percent, MetricType.GAUGE)
            self.record_metric("system_memory_available_mb", memory.available / 1024 / 1024, MetricType.GAUGE)
            self.record_metric("process_memory_rss_mb", process_memory.rss / 1024 / 1024, MetricType.GAUGE)
            
            # CPU metrics
            cpu_percent = psutil.cpu_percent()
            self.record_metric("system_cpu_percent", cpu_percent, MetricType.GAUGE)
            
            # Disk metrics
            disk_usage = psutil.disk_usage('/')
            disk_percent = (disk_usage.used / disk_usage.total) * 100
            self.record_metric("system_disk_percent", disk_percent, MetricType.GAUGE)
            self.record_metric("system_disk_free_gb", disk_usage.free / 1024 / 1024 / 1024, MetricType.GAUGE)
            
            # Network metrics (if available)
            try:
                net_io = psutil.net_io_counters()
                self.record_metric("network_bytes_sent", net_io.bytes_sent, MetricType.COUNTER)
                self.record_metric("network_bytes_recv", net_io.bytes_recv, MetricType.COUNTER)
            except Exception:
                pass  # Network metrics not available
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    def record_metric(self, name: str, value: float, metric_type: MetricType, 
                     tags: Dict[str, str] = None, description: str = ""):
        """Record a metric."""
        metric = Metric(
            name=name,
            value=value,
            metric_type=metric_type,
            tags=tags or {},
            description=description
        )
        
        self.metrics[name].append(metric)
        
        # Log significant metrics
        if metric_type == MetricType.COUNTER or "error" in name.lower():
            logger.debug(f"Metric recorded: {name}={value} ({metric_type.value})")
    
    def track_request(self, endpoint: str, method: str, duration: float, 
                     status_code: int, error: Optional[str] = None):
        """Track API request metrics."""
        # Record request duration
        self._request_times.append(duration)
        
        # Update endpoint statistics
        endpoint_key = f"{method}:{endpoint}"
        stats = self._endpoint_stats[endpoint_key]
        stats['count'] += 1
        stats['total_time'] += duration
        stats['last_access'] = datetime.utcnow()
        
        if status_code >= 400 or error:
            stats['errors'] += 1
            self._error_counts[f"{status_code}"] += 1
        
        # Record metrics
        self.record_metric(
            "api_request_duration",
            duration,
            MetricType.HISTOGRAM,
            tags={
                "endpoint": endpoint,
                "method": method,
                "status_code": str(status_code)
            }
        )
        
        self.record_metric(
            "api_requests_total",
            1,
            MetricType.COUNTER,
            tags={
                "endpoint": endpoint,
                "method": method,
                "status_code": str(status_code)
            }
        )
        
        if error:
            self.record_metric(
                "api_errors_total",
                1,
                MetricType.COUNTER,
                tags={
                    "endpoint": endpoint,
                    "method": method,
                    "error_type": type(error).__name__ if isinstance(error, Exception) else "unknown"
                }
            )
    
    def _generate_alert(self, alert_id: str, title: str, description: str, severity: str):
        """Generate an alert."""
        if alert_id not in self.alerts or self.alerts[alert_id].resolved:
            alert = Alert(
                id=alert_id,
                title=title,
                description=description,
                severity=severity,
                timestamp=datetime.utcnow()
            )
            
            self.alerts[alert_id] = alert
            
            # Notify alert handlers
            for handler in self._alert_handlers:
                try:
                    handler(alert)
                except Exception as e:
                    logger.error(f"Alert handler failed: {e}")
            
            logger.warning(f"Alert generated: {title} - {description}")
    
    def resolve_alert(self, alert_id: str):
        """Resolve an alert."""
        if alert_id in self.alerts and not self.alerts[alert_id].resolved:
            self.alerts[alert_id].resolved = True
            self.alerts[alert_id].resolved_at = datetime.utcnow()
            logger.info(f"Alert resolved: {alert_id}")
    
    def register_alert_handler(self, handler: Callable[[Alert], None]):
        """Register an alert handler."""
        self._alert_handlers.append(handler)
    
    def _process_alerts(self):
        """Process and auto-resolve alerts."""
        current_time = datetime.utcnow()
        
        for alert_id, alert in self.alerts.items():
            if not alert.resolved:
                # Auto-resolve alerts older than 1 hour if conditions are met
                if (current_time - alert.timestamp).total_seconds() > 3600:
                    # Check if the underlying issue is resolved
                    if self._is_alert_condition_resolved(alert):
                        self.resolve_alert(alert_id)
    
    def _is_alert_condition_resolved(self, alert: Alert) -> bool:
        """Check if alert condition is resolved."""
        # Simple heuristic: if it's a health check alert, check current status
        if "health_check" in alert.id:
            check_name = alert.id.replace("health_check_", "").replace("_failed", "")
            if check_name in self.health_checks:
                return self.health_checks[check_name].last_status == HealthStatus.HEALTHY
        
        return False
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status."""
        overall_status = HealthStatus.HEALTHY
        checks_summary = {}
        
        for name, check in self.health_checks.items():
            checks_summary[name] = {
                "status": check.last_status.value,
                "last_check": check.last_check.isoformat() if check.last_check else None,
                "error": check.last_error,
                "consecutive_failures": check.consecutive_failures
            }
            
            # Determine overall status
            if check.critical and check.last_status == HealthStatus.CRITICAL:
                overall_status = HealthStatus.CRITICAL
            elif (check.last_status in [HealthStatus.WARNING, HealthStatus.CRITICAL] and 
                  overall_status == HealthStatus.HEALTHY):
                overall_status = HealthStatus.WARNING
        
        return {
            "status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks_summary
        }
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        summary = {}
        
        for name, metric_deque in self.metrics.items():
            if metric_deque:
                recent_metrics = list(metric_deque)[-10:]  # Last 10 values
                values = [m.value for m in recent_metrics]
                
                summary[name] = {
                    "current": values[-1] if values else 0,
                    "average": sum(values) / len(values) if values else 0,
                    "min": min(values) if values else 0,
                    "max": max(values) if values else 0,
                    "count": len(metric_deque)
                }
        
        return summary
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        if not self._request_times:
            return {"message": "No request data available"}
        
        times = list(self._request_times)
        
        # Calculate percentiles
        sorted_times = sorted(times)
        n = len(sorted_times)
        
        p50 = sorted_times[int(n * 0.5)] if n > 0 else 0
        p95 = sorted_times[int(n * 0.95)] if n > 0 else 0
        p99 = sorted_times[int(n * 0.99)] if n > 0 else 0
        
        # Endpoint statistics
        endpoint_summary = {}
        for endpoint, stats in self._endpoint_stats.items():
            if stats['count'] > 0:
                endpoint_summary[endpoint] = {
                    "requests": stats['count'],
                    "avg_duration": stats['total_time'] / stats['count'],
                    "errors": stats['errors'],
                    "error_rate": stats['errors'] / stats['count'],
                    "last_access": stats['last_access'].isoformat() if stats['last_access'] else None
                }
        
        return {
            "request_count": len(times),
            "avg_duration": sum(times) / len(times),
            "min_duration": min(times),
            "max_duration": max(times),
            "p50_duration": p50,
            "p95_duration": p95,
            "p99_duration": p99,
            "error_counts": dict(self._error_counts),
            "endpoints": endpoint_summary
        }
    
    def get_alerts_summary(self) -> Dict[str, Any]:
        """Get alerts summary."""
        active_alerts = [alert for alert in self.alerts.values() if not alert.resolved]
        resolved_alerts = [alert for alert in self.alerts.values() if alert.resolved]
        
        return {
            "active_count": len(active_alerts),
            "resolved_count": len(resolved_alerts),
            "total_count": len(self.alerts),
            "active_alerts": [
                {
                    "id": alert.id,
                    "title": alert.title,
                    "severity": alert.severity,
                    "timestamp": alert.timestamp.isoformat()
                }
                for alert in active_alerts
            ]
        }
    
    @asynccontextmanager
    async def request_context(self, endpoint: str, method: str):
        """Context manager for tracking requests."""
        start_time = time.time()
        error = None
        status_code = 200
        
        try:
            yield
        except Exception as e:
            error = str(e)
            status_code = 500
            raise
        finally:
            duration = time.time() - start_time
            self.track_request(endpoint, method, duration, status_code, error)
    
    def monitoring_decorator(self, endpoint: str = None, method: str = "GET"):
        """Decorator for monitoring function calls."""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                func_endpoint = endpoint or func.__name__
                start_time = time.time()
                error = None
                status_code = 200
                
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    error = str(e)
                    status_code = 500
                    raise
                finally:
                    duration = time.time() - start_time
                    self.track_request(func_endpoint, method, duration, status_code, error)
            
            return wrapper
        return decorator

# Global monitoring instance
monitoring_system = MonitoringSystem()

# Convenience functions
def start_monitoring():
    """Start the monitoring system."""
    monitoring_system.start_monitoring()

def stop_monitoring():
    """Stop the monitoring system."""
    monitoring_system.stop_monitoring()

def get_health_status():
    """Get health status."""
    return monitoring_system.get_health_status()

def record_metric(name: str, value: float, metric_type: MetricType = MetricType.GAUGE, 
                 tags: Dict[str, str] = None):
    """Record a metric."""
    monitoring_system.record_metric(name, value, metric_type, tags)

def monitor_request(endpoint: str = None, method: str = "GET"):
    """Decorator for monitoring requests."""
    return monitoring_system.monitoring_decorator(endpoint, method)