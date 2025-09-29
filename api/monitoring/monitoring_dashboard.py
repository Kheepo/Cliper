"""Comprehensive monitoring dashboard with real-time metrics and alerting."""

import os
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse
import redis
import psutil
import logging
from collections import defaultdict, deque
import time
from .logging_config import log_aggregator, LogContext
from .health import health_manager
from .performance_monitor import PerformanceMonitor
from .alerting import AlertManager

logger = logging.getLogger(__name__)

@dataclass
class MetricPoint:
    """Single metric data point."""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = None
    
@dataclass
class AlertRule:
    """Alert rule configuration."""
    name: str
    metric: str
    condition: str  # gt, lt, eq
    threshold: float
    duration: int  # seconds
    severity: str  # critical, warning, info
    enabled: bool = True
    
class MetricsCollector:
    """Collects and stores metrics for monitoring."""
    
    def __init__(self):
        self.redis_available = False
        self.redis_client = None
        try:
            self.redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))
            # Test connection
            self.redis_client.ping()
            self.redis_available = True
            logger.info("Redis connection established for monitoring")
        except Exception as e:
            logger.warning(f"Redis connection failed for monitoring: {e}. Using memory-only storage.")
            self.redis_client = None
            
        self.metrics_buffer = defaultdict(lambda: deque(maxlen=1000))
        self.alert_rules = []
        self.load_alert_rules()
        
    def load_alert_rules(self):
        """Load alert rules from configuration."""
        default_rules = [
            AlertRule("High CPU Usage", "cpu_percent", "gt", 80.0, 300, "warning"),
            AlertRule("Critical CPU Usage", "cpu_percent", "gt", 95.0, 60, "critical"),
            AlertRule("High Memory Usage", "memory_percent", "gt", 85.0, 300, "warning"),
            AlertRule("Critical Memory Usage", "memory_percent", "gt", 95.0, 60, "critical"),
            AlertRule("High Disk Usage", "disk_percent", "gt", 90.0, 600, "warning"),
            AlertRule("Critical Disk Usage", "disk_percent", "gt", 95.0, 300, "critical"),
            AlertRule("High Error Rate", "error_rate", "gt", 5.0, 300, "warning"),
            AlertRule("Critical Error Rate", "error_rate", "gt", 10.0, 60, "critical"),
            AlertRule("Slow Response Time", "avg_response_time", "gt", 2.0, 300, "warning"),
            AlertRule("Very Slow Response Time", "avg_response_time", "gt", 5.0, 60, "critical"),
        ]
        self.alert_rules = default_rules
        
    async def collect_system_metrics(self) -> Dict[str, float]:
        """Collect system-level metrics."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            
            # Network metrics
            network = psutil.net_io_counters()
            
            # Process metrics
            process = psutil.Process()
            process_memory = process.memory_info()
            
            metrics = {
                "cpu_percent": cpu_percent,
                "cpu_count": cpu_count,
                "memory_total": memory.total,
                "memory_available": memory.available,
                "memory_percent": memory.percent,
                "memory_used": memory.used,
                "disk_total": disk.total,
                "disk_used": disk.used,
                "disk_free": disk.free,
                "disk_percent": (disk.used / disk.total) * 100,
                "network_bytes_sent": network.bytes_sent,
                "network_bytes_recv": network.bytes_recv,
                "process_memory_rss": process_memory.rss,
                "process_memory_vms": process_memory.vms,
                "process_cpu_percent": process.cpu_percent(),
                "timestamp": time.time()
            }
            
            # Store metrics in Redis and buffer
            await self.store_metrics("system", metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return {}
            
    async def collect_application_metrics(self) -> Dict[str, float]:
        """Collect application-specific metrics."""
        try:
            metrics = {}
            
            # Redis metrics
            if self.redis_available and self.redis_client:
                try:
                    redis_info = self.redis_client.info()
                    metrics.update({
                        "redis_connected_clients": redis_info.get('connected_clients', 0),
                        "redis_used_memory": redis_info.get('used_memory', 0),
                        "redis_keyspace_hits": redis_info.get('keyspace_hits', 0),
                        "redis_keyspace_misses": redis_info.get('keyspace_misses', 0),
                    })
                except Exception as e:
                    logger.warning(f"Failed to collect Redis metrics: {e}")
            else:
                # Set Redis metrics to 0 when not available
                metrics.update({
                    "redis_connected_clients": 0,
                    "redis_used_memory": 0,
                    "redis_keyspace_hits": 0,
                    "redis_keyspace_misses": 0,
                })
                
            # API metrics from performance monitor
            try:
                if hasattr(self, 'performance_monitor'):
                    perf_metrics = self.performance_monitor.get_current_metrics()
                    metrics.update(perf_metrics)
            except Exception as e:
                logger.warning(f"Failed to collect performance metrics: {e}")
                
            # Health check metrics
            try:
                health_status = await health_manager.run_all_checks()
                metrics.update({
                    "health_overall": 1 if health_status['status'] == 'healthy' else 0,
                    "health_redis": 1 if health_status['checks']['redis']['status'] == 'healthy' else 0,
                    "health_celery": 1 if health_status['checks']['celery']['status'] == 'healthy' else 0,
                    "health_firestore": 1 if health_status['checks']['firestore']['status'] == 'healthy' else 0,
                })
            except Exception as e:
                logger.warning(f"Failed to collect health metrics: {e}")
                
            metrics["timestamp"] = time.time()
            
            # Store metrics
            await self.store_metrics("application", metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect application metrics: {e}")
            return {}
            
    async def store_metrics(self, category: str, metrics: Dict[str, Any]):
        """Store metrics in Redis and local buffer."""
        try:
            # Store in Redis if available
            if self.redis_available and self.redis_client:
                try:
                    # Store in Redis with timestamp
                    key = f"cliper:metrics:{category}:{int(time.time())}"
                    self.redis_client.setex(key, 3600, json.dumps(metrics))  # 1 hour TTL
                    
                    # Store in time-series format
                    for metric_name, value in metrics.items():
                        if isinstance(value, (int, float)):
                            ts_key = f"cliper:timeseries:{category}:{metric_name}"
                            self.redis_client.zadd(ts_key, {str(time.time()): value})
                            
                            # Keep only last 24 hours of data
                            cutoff = time.time() - 86400
                            self.redis_client.zremrangebyscore(ts_key, 0, cutoff)
                except Exception as e:
                    logger.warning(f"Failed to store metrics in Redis: {e}")
                    
            # Always store in local buffer for real-time access
            self.metrics_buffer[category].append({
                "timestamp": datetime.now(),
                "metrics": metrics
            })
            
        except Exception as e:
            logger.error(f"Failed to store metrics: {e}")
            
    async def get_metrics_history(self, category: str, metric: str, hours: int = 1) -> List[MetricPoint]:
        """Get historical metrics data."""
        try:
            # Try Redis first if available
            if self.redis_available and self.redis_client:
                try:
                    key = f"cliper:timeseries:{category}:{metric}"
                    start_time = time.time() - (hours * 3600)
                    
                    data = self.redis_client.zrangebyscore(key, start_time, time.time(), withscores=True)
                    
                    return [
                        MetricPoint(
                            timestamp=datetime.fromtimestamp(float(timestamp)),
                            value=float(value)
                        )
                        for value, timestamp in data
                    ]
                except Exception as e:
                    logger.warning(f"Failed to get metrics history from Redis: {e}")
            
            # Fallback to local buffer
            cutoff_time = datetime.now() - timedelta(hours=hours)
            buffer_data = self.metrics_buffer.get(category, [])
            
            result = []
            for entry in buffer_data:
                if entry["timestamp"] >= cutoff_time and metric in entry["metrics"]:
                    value = entry["metrics"][metric]
                    if isinstance(value, (int, float)):
                        result.append(MetricPoint(
                            timestamp=entry["timestamp"],
                            value=float(value)
                        ))
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get metrics history: {e}")
            return []
            
    async def check_alert_rules(self, metrics: Dict[str, float]):
        """Check metrics against alert rules."""
        for rule in self.alert_rules:
            if not rule.enabled or rule.metric not in metrics:
                continue
                
            value = metrics[rule.metric]
            triggered = False
            
            if rule.condition == "gt" and value > rule.threshold:
                triggered = True
            elif rule.condition == "lt" and value < rule.threshold:
                triggered = True
            elif rule.condition == "eq" and value == rule.threshold:
                triggered = True
                
            if triggered:
                await self.trigger_alert(rule, value, metrics)
                
    async def trigger_alert(self, rule: AlertRule, value: float, context: Dict[str, Any]):
        """Trigger an alert."""
        alert_data = {
            "rule_name": rule.name,
            "metric": rule.metric,
            "value": value,
            "threshold": rule.threshold,
            "severity": rule.severity,
            "timestamp": datetime.now().isoformat(),
            "context": context
        }
        
        # Store alert in Redis if available
        if self.redis_available and self.redis_client:
            try:
                alert_key = f"cliper:alerts:{int(time.time())}"
                self.redis_client.setex(alert_key, 86400, json.dumps(alert_data))  # 24 hour TTL
            except Exception as e:
                logger.warning(f"Failed to store alert in Redis: {e}")
        
        # Log alert
        with LogContext(alert=alert_data):
            logger.warning(f"Alert triggered: {rule.name} - {rule.metric}={value} (threshold: {rule.threshold})")
            
class MonitoringDashboard:
    """Real-time monitoring dashboard."""
    
    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.connected_clients = set()
        self.monitoring_active = False
        
    async def start_monitoring(self):
        """Start the monitoring loop."""
        self.monitoring_active = True
        
        while self.monitoring_active:
            try:
                # Collect metrics
                system_metrics = await self.metrics_collector.collect_system_metrics()
                app_metrics = await self.metrics_collector.collect_application_metrics()
                
                # Check alerts
                all_metrics = {**system_metrics, **app_metrics}
                await self.metrics_collector.check_alert_rules(all_metrics)
                
                # Broadcast to connected clients
                if self.connected_clients:
                    await self.broadcast_metrics({
                        "type": "metrics_update",
                        "system": system_metrics,
                        "application": app_metrics,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                await asyncio.sleep(10)  # Collect every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)
                
    def stop_monitoring(self):
        """Stop the monitoring loop."""
        self.monitoring_active = False
        
    async def add_client(self, websocket: WebSocket):
        """Add a WebSocket client."""
        self.connected_clients.add(websocket)
        
    async def remove_client(self, websocket: WebSocket):
        """Remove a WebSocket client."""
        self.connected_clients.discard(websocket)
        
    async def broadcast_metrics(self, data: Dict[str, Any]):
        """Broadcast metrics to all connected clients."""
        disconnected = set()
        
        for client in self.connected_clients:
            try:
                await client.send_text(json.dumps(data))
            except Exception:
                disconnected.add(client)
                
        # Remove disconnected clients
        self.connected_clients -= disconnected
        
# Global monitoring dashboard instance
monitoring_dashboard = MonitoringDashboard()

# Router for monitoring endpoints
router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

@router.get("/dashboard")
async def get_dashboard():
    """Get monitoring dashboard HTML."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Cliper Monitoring Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
            .metric-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .metric-value { font-size: 2em; font-weight: bold; color: #333; }
            .metric-label { color: #666; margin-bottom: 10px; }
            .status-healthy { color: #28a745; }
            .status-warning { color: #ffc107; }
            .status-critical { color: #dc3545; }
            .chart-container { height: 300px; margin-top: 20px; }
            .alerts { background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0; }
            .alert-item { margin: 10px 0; padding: 10px; border-left: 4px solid #ffc107; background: #fff; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Cliper Monitoring Dashboard</h1>
            
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">CPU Usage</div>
                    <div class="metric-value" id="cpu-usage">--</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Memory Usage</div>
                    <div class="metric-value" id="memory-usage">--</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Disk Usage</div>
                    <div class="metric-value" id="disk-usage">--</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">System Health</div>
                    <div class="metric-value" id="system-health">--</div>
                </div>
            </div>
            
            <div class="chart-container">
                <canvas id="metricsChart"></canvas>
            </div>
            
            <div class="alerts" id="alerts-container" style="display: none;">
                <h3>Active Alerts</h3>
                <div id="alerts-list"></div>
            </div>
        </div>
        
        <script>
            const ws = new WebSocket(`ws://${window.location.host}/api/monitoring/ws`);
            
            const ctx = document.getElementById('metricsChart').getContext('2d');
            const chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'CPU %',
                        data: [],
                        borderColor: 'rgb(75, 192, 192)',
                        tension: 0.1
                    }, {
                        label: 'Memory %',
                        data: [],
                        borderColor: 'rgb(255, 99, 132)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100
                        }
                    }
                }
            });
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                
                if (data.type === 'metrics_update') {
                    updateMetrics(data);
                    updateChart(data);
                }
            };
            
            function updateMetrics(data) {
                document.getElementById('cpu-usage').textContent = data.system.cpu_percent.toFixed(1) + '%';
                document.getElementById('memory-usage').textContent = data.system.memory_percent.toFixed(1) + '%';
                document.getElementById('disk-usage').textContent = data.system.disk_percent.toFixed(1) + '%';
                
                const healthStatus = data.application.health_overall ? 'Healthy' : 'Unhealthy';
                const healthElement = document.getElementById('system-health');
                healthElement.textContent = healthStatus;
                healthElement.className = data.application.health_overall ? 'status-healthy' : 'status-critical';
            }
            
            function updateChart(data) {
                const now = new Date().toLocaleTimeString();
                
                chart.data.labels.push(now);
                chart.data.datasets[0].data.push(data.system.cpu_percent);
                chart.data.datasets[1].data.push(data.system.memory_percent);
                
                if (chart.data.labels.length > 20) {
                    chart.data.labels.shift();
                    chart.data.datasets[0].data.shift();
                    chart.data.datasets[1].data.shift();
                }
                
                chart.update('none');
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time metrics."""
    await websocket.accept()
    await monitoring_dashboard.add_client(websocket)
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        await monitoring_dashboard.remove_client(websocket)
        
@router.get("/metrics")
async def get_current_metrics():
    """Get current system and application metrics."""
    system_metrics = await monitoring_dashboard.metrics_collector.collect_system_metrics()
    app_metrics = await monitoring_dashboard.metrics_collector.collect_application_metrics()
    
    return {
        "system": system_metrics,
        "application": app_metrics,
        "timestamp": datetime.now().isoformat()
    }
    
@router.get("/metrics/history")
async def get_metrics_history(
    category: str = Query(..., description="Metric category (system/application)"),
    metric: str = Query(..., description="Metric name"),
    hours: int = Query(1, description="Hours of history to retrieve")
):
    """Get historical metrics data."""
    history = await monitoring_dashboard.metrics_collector.get_metrics_history(category, metric, hours)
    return {
        "category": category,
        "metric": metric,
        "data": [asdict(point) for point in history]
    }
    
@router.get("/logs")
async def get_recent_logs(
    level: str = Query("all", description="Log level filter"),
    limit: int = Query(100, description="Number of logs to retrieve")
):
    """Get recent logs."""
    logs = await log_aggregator.get_recent_logs(level, limit)
    return {
        "logs": logs,
        "count": len(logs)
    }
    
@router.get("/logs/stats")
async def get_log_stats():
    """Get logging statistics."""
    return log_aggregator.get_log_stats()
    
@router.get("/alerts")
async def get_active_alerts():
    """Get active alerts."""
    try:
        redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))
        
        # Get all alert keys from last 24 hours
        current_time = int(time.time())
        start_time = current_time - 86400
        
        alerts = []
        for key in redis_client.scan_iter(match="cliper:alerts:*"):
            try:
                timestamp = int(key.decode().split(':')[-1])
                if timestamp >= start_time:
                    alert_data = redis_client.get(key)
                    if alert_data:
                        alerts.append(json.loads(alert_data))
            except (ValueError, json.JSONDecodeError):
                continue
                
        # Sort by timestamp (newest first)
        alerts.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return {
            "alerts": alerts,
            "count": len(alerts)
        }
        
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve alerts")
        
# Start monitoring when module is imported
async def start_background_monitoring():
    """Start background monitoring task."""
    asyncio.create_task(monitoring_dashboard.start_monitoring())
    
# Initialize monitoring on startup
try:
    asyncio.create_task(start_background_monitoring())
except RuntimeError:
    # Event loop not running yet, will be started later
    pass