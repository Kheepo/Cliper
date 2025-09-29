"""Comprehensive monitoring dashboard system.

Provides:
- Real-time metrics collection and aggregation
- Performance monitoring and alerting
- System health dashboards
- Custom metric tracking
- Historical data analysis
- Alert management
- Export capabilities
"""

import asyncio
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from statistics import mean, median, stdev

import psutil
from pydantic import BaseModel

from api.utils.enhanced_logging import get_logger
from api.config.production import get_settings
from api.utils.resource_monitor import get_resource_monitor
from api.utils.health_checker import get_health_checker
from api.utils.load_balancer import get_load_balancing_service
from api.utils.queue_manager import get_queue_manager
from api.utils.caching import get_cache


logger = get_logger(__name__)
settings = get_settings()


class MetricType(str, Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    TIMER = "timer"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatus(str, Enum):
    """Alert status."""
    ACTIVE = "active"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SUPPRESSED = "suppressed"


class DashboardType(str, Enum):
    """Dashboard types."""
    SYSTEM = "system"
    APPLICATION = "application"
    BUSINESS = "business"
    CUSTOM = "custom"


@dataclass
class MetricPoint:
    """A single metric data point."""
    timestamp: datetime
    value: float
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricSeries:
    """A series of metric data points."""
    name: str
    metric_type: MetricType
    unit: str = ""
    description: str = ""
    points: deque = field(default_factory=lambda: deque(maxlen=1000))
    tags: Dict[str, str] = field(default_factory=dict)
    
    def add_point(self, value: float, timestamp: Optional[datetime] = None, tags: Optional[Dict[str, str]] = None):
        """Add a data point to the series."""
        point = MetricPoint(
            timestamp=timestamp or datetime.utcnow(),
            value=value,
            tags=tags or {},
        )
        self.points.append(point)
    
    def get_latest_value(self) -> Optional[float]:
        """Get the latest value."""
        return self.points[-1].value if self.points else None
    
    def get_values_in_range(self, start: datetime, end: datetime) -> List[float]:
        """Get values within a time range."""
        return [
            point.value for point in self.points
            if start <= point.timestamp <= end
        ]
    
    def get_statistics(self, duration: Optional[timedelta] = None) -> Dict[str, float]:
        """Get statistical summary of the metric."""
        if not self.points:
            return {}
        
        values = []
        if duration:
            cutoff = datetime.utcnow() - duration
            values = [point.value for point in self.points if point.timestamp >= cutoff]
        else:
            values = [point.value for point in self.points]
        
        if not values:
            return {}
        
        stats = {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'mean': mean(values),
            'median': median(values),
            'latest': values[-1] if values else 0
        }
        
        if len(values) > 1:
            stats['stddev'] = stdev(values)
        
        return stats


@dataclass
class AlertRule:
    """Alert rule configuration."""
    id: str
    name: str
    metric_name: str
    condition: str  # e.g., "> 80", "< 10", "== 0"
    threshold: float
    severity: AlertSeverity
    duration: timedelta = timedelta(minutes=5)  # How long condition must be true
    cooldown: timedelta = timedelta(minutes=15)  # Cooldown between alerts
    
    # Notification settings
    enabled: bool = True
    notification_channels: List[str] = field(default_factory=list)
    
    # State tracking
    last_triggered: Optional[datetime] = None
    last_resolved: Optional[datetime] = None
    consecutive_violations: int = 0
    
    def evaluate(self, value: float) -> bool:
        """Evaluate if the alert condition is met."""
        try:
            if self.condition.startswith('>'):
                return value > self.threshold
            elif self.condition.startswith('<'):
                return value < self.threshold
            elif self.condition.startswith('>='):
                return value >= self.threshold
            elif self.condition.startswith('<='):
                return value <= self.threshold
            elif self.condition.startswith('=='):
                return value == self.threshold
            elif self.condition.startswith('!='):
                return value != self.threshold
            else:
                return False
        except Exception:
            return False


class Alert(BaseModel):
    """Active alert."""
    id: str
    rule_id: str
    metric_name: str
    severity: AlertSeverity
    status: AlertStatus
    message: str
    value: float
    threshold: float
    
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    
    tags: Dict[str, str] = {}
    metadata: Dict[str, Any] = {}


@dataclass
class DashboardWidget:
    """Dashboard widget configuration."""
    id: str
    title: str
    widget_type: str  # chart, gauge, table, text, etc.
    metrics: List[str]
    config: Dict[str, Any] = field(default_factory=dict)
    position: Dict[str, int] = field(default_factory=dict)  # x, y, width, height
    refresh_interval: int = 30  # seconds


@dataclass
class Dashboard:
    """Dashboard configuration."""
    id: str
    name: str
    description: str
    dashboard_type: DashboardType
    widgets: List[DashboardWidget] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None


class MetricsCollector:
    """Collects and manages metrics."""
    
    def __init__(self):
        self.metrics: Dict[str, MetricSeries] = {}
        self.collection_tasks: Dict[str, asyncio.Task] = {}
        self.custom_collectors: Dict[str, Callable] = {}
        
        logger.info("Metrics collector initialized")
    
    def register_metric(self, name: str, metric_type: MetricType, unit: str = "", description: str = "", tags: Optional[Dict[str, str]] = None):
        """Register a new metric."""
        self.metrics[name] = MetricSeries(
            name=name,
            metric_type=metric_type,
            unit=unit,
            description=description,
            tags=tags or {}
        )
        
        logger.info(f"Registered metric: {name} ({metric_type.value})")
    
    def record_metric(self, name: str, value: float, timestamp: Optional[datetime] = None, tags: Optional[Dict[str, str]] = None):
        """Record a metric value."""
        if name not in self.metrics:
            # Auto-register as gauge
            self.register_metric(name, MetricType.GAUGE)
        
        self.metrics[name].add_point(value, timestamp, tags)
    
    def increment_counter(self, name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None):
        """Increment a counter metric."""
        if name not in self.metrics:
            self.register_metric(name, MetricType.COUNTER)
        
        current_value = self.metrics[name].get_latest_value() or 0
        self.record_metric(name, current_value + value, tags=tags)
    
    def set_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Set a gauge metric value."""
        if name not in self.metrics:
            self.register_metric(name, MetricType.GAUGE)
        
        self.record_metric(name, value, tags=tags)
    
    def record_timer(self, name: str, duration: float, tags: Optional[Dict[str, str]] = None):
        """Record a timer metric (duration in seconds)."""
        if name not in self.metrics:
            self.register_metric(name, MetricType.TIMER, unit="seconds")
        
        self.record_metric(name, duration, tags=tags)
    
    def register_custom_collector(self, name: str, collector_func: Callable):
        """Register a custom metric collector function."""
        self.custom_collectors[name] = collector_func
        logger.info(f"Registered custom collector: {name}")
    
    async def start_collection(self, metric_name: str, interval: float = 60.0):
        """Start automatic collection for a metric."""
        if metric_name in self.collection_tasks:
            return
        
        if metric_name in self.custom_collectors:
            task = asyncio.create_task(
                self._collection_loop(metric_name, self.custom_collectors[metric_name], interval)
            )
            self.collection_tasks[metric_name] = task
            logger.info(f"Started collection for {metric_name} (interval: {interval}s)")
    
    async def stop_collection(self, metric_name: str):
        """Stop automatic collection for a metric."""
        if metric_name in self.collection_tasks:
            self.collection_tasks[metric_name].cancel()
            try:
                await self.collection_tasks[metric_name]
            except asyncio.CancelledError:
                pass
            del self.collection_tasks[metric_name]
            logger.info(f"Stopped collection for {metric_name}")
    
    async def _collection_loop(self, metric_name: str, collector_func: Callable, interval: float):
        """Background collection loop."""
        while True:
            try:
                await asyncio.sleep(interval)
                
                # Call collector function
                if asyncio.iscoroutinefunction(collector_func):
                    value = await collector_func()
                else:
                    value = collector_func()
                
                if value is not None:
                    self.record_metric(metric_name, value)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in collection loop for {metric_name}: {e}")
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a metric series."""
        return self.metrics.get(name)
    
    def get_all_metrics(self) -> Dict[str, MetricSeries]:
        """Get all metrics."""
        return self.metrics.copy()
    
    def get_metric_names(self) -> List[str]:
        """Get list of all metric names."""
        return list(self.metrics.keys())
    
    async def stop_all_collection(self):
        """Stop all collection tasks."""
        tasks = list(self.collection_tasks.keys())
        for metric_name in tasks:
            await self.stop_collection(metric_name)


class AlertManager:
    """Manages alerts and notifications."""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.alert_rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        
        # Notification callbacks
        self.notification_handlers: Dict[str, Callable] = {}
        
        # Evaluation task
        self.evaluation_task: Optional[asyncio.Task] = None
        self.evaluation_interval = 30.0  # seconds
        
        logger.info("Alert manager initialized")
    
    def add_alert_rule(self, rule: AlertRule):
        """Add an alert rule."""
        self.alert_rules[rule.id] = rule
        logger.info(f"Added alert rule: {rule.name}")
    
    def remove_alert_rule(self, rule_id: str):
        """Remove an alert rule."""
        if rule_id in self.alert_rules:
            del self.alert_rules[rule_id]
            logger.info(f"Removed alert rule: {rule_id}")
    
    def register_notification_handler(self, channel: str, handler: Callable):
        """Register a notification handler."""
        self.notification_handlers[channel] = handler
        logger.info(f"Registered notification handler: {channel}")
    
    async def start_evaluation(self):
        """Start alert evaluation loop."""
        if self.evaluation_task:
            return
        
        self.evaluation_task = asyncio.create_task(self._evaluation_loop())
        logger.info("Started alert evaluation")
    
    async def stop_evaluation(self):
        """Stop alert evaluation loop."""
        if self.evaluation_task:
            self.evaluation_task.cancel()
            try:
                await self.evaluation_task
            except asyncio.CancelledError:
                pass
            self.evaluation_task = None
            logger.info("Stopped alert evaluation")
    
    async def _evaluation_loop(self):
        """Background alert evaluation loop."""
        while True:
            try:
                await asyncio.sleep(self.evaluation_interval)
                await self._evaluate_alerts()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in alert evaluation: {e}")
    
    async def _evaluate_alerts(self):
        """Evaluate all alert rules."""
        for rule in self.alert_rules.values():
            if not rule.enabled:
                continue
            
            try:
                await self._evaluate_rule(rule)
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.id}: {e}")
    
    async def _evaluate_rule(self, rule: AlertRule):
        """Evaluate a single alert rule."""
        metric = self.metrics_collector.get_metric(rule.metric_name)
        if not metric:
            return
        
        current_value = metric.get_latest_value()
        if current_value is None:
            return
        
        # Check if condition is met
        condition_met = rule.evaluate(current_value)
        
        if condition_met:
            rule.consecutive_violations += 1
            
            # Check if we should trigger an alert
            if (rule.consecutive_violations >= 1 and  # Immediate for now, could be configurable
                (not rule.last_triggered or 
                 datetime.utcnow() - rule.last_triggered > rule.cooldown)):
                
                await self._trigger_alert(rule, current_value)
        else:
            # Reset consecutive violations
            if rule.consecutive_violations > 0:
                rule.consecutive_violations = 0
                
                # Resolve any active alerts for this rule
                await self._resolve_alerts_for_rule(rule.id)
    
    async def _trigger_alert(self, rule: AlertRule, value: float):
        """Trigger an alert."""
        alert_id = f"{rule.id}_{int(time.time())}"
        
        alert = Alert(
            id=alert_id,
            rule_id=rule.id,
            metric_name=rule.metric_name,
            severity=rule.severity,
            status=AlertStatus.ACTIVE,
            message=f"{rule.name}: {rule.metric_name} is {value} (threshold: {rule.threshold})",
            value=value,
            threshold=rule.threshold,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        
        rule.last_triggered = datetime.utcnow()
        
        # Send notifications
        await self._send_notifications(alert, rule)
        
        logger.warning(f"Alert triggered: {alert.message}")
    
    async def _resolve_alerts_for_rule(self, rule_id: str):
        """Resolve all active alerts for a rule."""
        alerts_to_resolve = [
            alert for alert in self.active_alerts.values()
            if alert.rule_id == rule_id and alert.status == AlertStatus.ACTIVE
        ]
        
        for alert in alerts_to_resolve:
            await self.resolve_alert(alert.id)
    
    async def resolve_alert(self, alert_id: str):
        """Resolve an alert."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.utcnow()
            alert.updated_at = datetime.utcnow()
            
            del self.active_alerts[alert_id]
            
            logger.info(f"Alert resolved: {alert.message}")
    
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str):
        """Acknowledge an alert."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.utcnow()
            alert.acknowledged_by = acknowledged_by
            alert.updated_at = datetime.utcnow()
            
            logger.info(f"Alert acknowledged by {acknowledged_by}: {alert.message}")
    
    async def _send_notifications(self, alert: Alert, rule: AlertRule):
        """Send notifications for an alert."""
        for channel in rule.notification_channels:
            if channel in self.notification_handlers:
                try:
                    handler = self.notification_handlers[channel]
                    if asyncio.iscoroutinefunction(handler):
                        await handler(alert)
                    else:
                        handler(alert)
                except Exception as e:
                    logger.error(f"Error sending notification to {channel}: {e}")
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return list(self.active_alerts.values())
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get alert history."""
        return self.alert_history[-limit:]
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert statistics."""
        total_alerts = len(self.alert_history)
        active_alerts = len(self.active_alerts)
        
        severity_counts = defaultdict(int)
        for alert in self.alert_history:
            severity_counts[alert.severity.value] += 1
        
        return {
            'total_alerts': total_alerts,
            'active_alerts': active_alerts,
            'severity_distribution': dict(severity_counts),
            'alert_rules': len(self.alert_rules)
        }


class DashboardManager:
    """Manages dashboards and widgets."""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.dashboards: Dict[str, Dashboard] = {}
        
        # Create default dashboards
        self._create_default_dashboards()
        
        logger.info("Dashboard manager initialized")
    
    def _create_default_dashboards(self):
        """Create default system dashboards."""
        # System dashboard
        system_dashboard = Dashboard(
            id="system",
            name="System Metrics",
            description="System performance and resource metrics",
            dashboard_type=DashboardType.SYSTEM
        )
        
        # Add system widgets
        system_dashboard.widgets = [
            DashboardWidget(
                id="cpu_usage",
                title="CPU Usage",
                widget_type="gauge",
                metrics=["system.cpu.usage"],
                config={"min": 0, "max": 100, "unit": "%"},
                position={"x": 0, "y": 0, "width": 6, "height": 4}
            ),
            DashboardWidget(
                id="memory_usage",
                title="Memory Usage",
                widget_type="gauge",
                metrics=["system.memory.usage"],
                config={"min": 0, "max": 100, "unit": "%"},
                position={"x": 6, "y": 0, "width": 6, "height": 4}
            ),
            DashboardWidget(
                id="disk_usage",
                title="Disk Usage",
                widget_type="gauge",
                metrics=["system.disk.usage"],
                config={"min": 0, "max": 100, "unit": "%"},
                position={"x": 0, "y": 4, "width": 6, "height": 4}
            ),
            DashboardWidget(
                id="network_io",
                title="Network I/O",
                widget_type="chart",
                metrics=["system.network.bytes_sent", "system.network.bytes_recv"],
                config={"chart_type": "line", "time_range": "1h"},
                position={"x": 6, "y": 4, "width": 6, "height": 4}
            )
        ]
        
        self.dashboards[system_dashboard.id] = system_dashboard
        
        # Application dashboard
        app_dashboard = Dashboard(
            id="application",
            name="Application Metrics",
            description="Application performance and business metrics",
            dashboard_type=DashboardType.APPLICATION
        )
        
        app_dashboard.widgets = [
            DashboardWidget(
                id="request_rate",
                title="Request Rate",
                widget_type="chart",
                metrics=["app.requests.rate"],
                config={"chart_type": "line", "time_range": "1h"},
                position={"x": 0, "y": 0, "width": 6, "height": 4}
            ),
            DashboardWidget(
                id="response_time",
                title="Response Time",
                widget_type="chart",
                metrics=["app.response.time"],
                config={"chart_type": "line", "time_range": "1h"},
                position={"x": 6, "y": 0, "width": 6, "height": 4}
            ),
            DashboardWidget(
                id="error_rate",
                title="Error Rate",
                widget_type="gauge",
                metrics=["app.errors.rate"],
                config={"min": 0, "max": 10, "unit": "%"},
                position={"x": 0, "y": 4, "width": 6, "height": 4}
            ),
            DashboardWidget(
                id="active_users",
                title="Active Users",
                widget_type="number",
                metrics=["app.users.active"],
                config={"format": "integer"},
                position={"x": 6, "y": 4, "width": 6, "height": 4}
            )
        ]
        
        self.dashboards[app_dashboard.id] = app_dashboard
    
    def create_dashboard(self, dashboard: Dashboard):
        """Create a new dashboard."""
        self.dashboards[dashboard.id] = dashboard
        logger.info(f"Created dashboard: {dashboard.name}")
    
    def get_dashboard(self, dashboard_id: str) -> Optional[Dashboard]:
        """Get a dashboard by ID."""
        return self.dashboards.get(dashboard_id)
    
    def get_all_dashboards(self) -> List[Dashboard]:
        """Get all dashboards."""
        return list(self.dashboards.values())
    
    def update_dashboard(self, dashboard_id: str, updates: Dict[str, Any]):
        """Update a dashboard."""
        if dashboard_id in self.dashboards:
            dashboard = self.dashboards[dashboard_id]
            
            for key, value in updates.items():
                if hasattr(dashboard, key):
                    setattr(dashboard, key, value)
            
            dashboard.updated_at = datetime.utcnow()
            logger.info(f"Updated dashboard: {dashboard_id}")
    
    def delete_dashboard(self, dashboard_id: str):
        """Delete a dashboard."""
        if dashboard_id in self.dashboards:
            del self.dashboards[dashboard_id]
            logger.info(f"Deleted dashboard: {dashboard_id}")
    
    def get_widget_data(self, dashboard_id: str, widget_id: str, time_range: Optional[str] = None) -> Dict[str, Any]:
        """Get data for a specific widget."""
        dashboard = self.get_dashboard(dashboard_id)
        if not dashboard:
            return {}
        
        widget = next((w for w in dashboard.widgets if w.id == widget_id), None)
        if not widget:
            return {}
        
        # Calculate time range
        end_time = datetime.utcnow()
        if time_range == "1h":
            start_time = end_time - timedelta(hours=1)
        elif time_range == "6h":
            start_time = end_time - timedelta(hours=6)
        elif time_range == "24h":
            start_time = end_time - timedelta(hours=24)
        elif time_range == "7d":
            start_time = end_time - timedelta(days=7)
        else:
            start_time = end_time - timedelta(hours=1)  # Default
        
        # Collect data for each metric
        data = {}
        for metric_name in widget.metrics:
            metric = self.metrics_collector.get_metric(metric_name)
            if metric:
                if widget.widget_type in ["gauge", "number"]:
                    # For gauges and numbers, return latest value and statistics
                    data[metric_name] = {
                        'latest': metric.get_latest_value(),
                        'statistics': metric.get_statistics(timedelta(hours=1))
                    }
                else:
                    # For charts, return time series data
                    points = [
                        {
                            'timestamp': point.timestamp.isoformat(),
                            'value': point.value
                        }
                        for point in metric.points
                        if start_time <= point.timestamp <= end_time
                    ]
                    data[metric_name] = {
                        'points': points,
                        'statistics': metric.get_statistics(end_time - start_time)
                    }
        
        return {
            'widget': {
                'id': widget.id,
                'title': widget.title,
                'type': widget.widget_type,
                'config': widget.config
            },
            'data': data,
            'time_range': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat()
            }
        }


class MonitoringDashboard:
    """Main monitoring dashboard system."""
    
    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.alert_manager = AlertManager(self.metrics_collector)
        self.dashboard_manager = DashboardManager(self.metrics_collector)
        
        # System monitoring task
        self.system_monitoring_task: Optional[asyncio.Task] = None
        
        # Setup default metrics and alerts
        self._setup_default_metrics()
        self._setup_default_alerts()
        
        logger.info("Monitoring dashboard initialized")
    
    def _setup_default_metrics(self):
        """Setup default system metrics."""
        # System metrics
        self.metrics_collector.register_metric("system.cpu.usage", MetricType.GAUGE, "%", "CPU usage percentage")
        self.metrics_collector.register_metric("system.memory.usage", MetricType.GAUGE, "%", "Memory usage percentage")
        self.metrics_collector.register_metric("system.disk.usage", MetricType.GAUGE, "%", "Disk usage percentage")
        self.metrics_collector.register_metric("system.network.bytes_sent", MetricType.COUNTER, "bytes", "Network bytes sent")
        self.metrics_collector.register_metric("system.network.bytes_recv", MetricType.COUNTER, "bytes", "Network bytes received")
        
        # Application metrics
        self.metrics_collector.register_metric("app.requests.total", MetricType.COUNTER, "requests", "Total requests")
        self.metrics_collector.register_metric("app.requests.rate", MetricType.GAUGE, "req/s", "Request rate")
        self.metrics_collector.register_metric("app.response.time", MetricType.TIMER, "seconds", "Response time")
        self.metrics_collector.register_metric("app.errors.total", MetricType.COUNTER, "errors", "Total errors")
        self.metrics_collector.register_metric("app.errors.rate", MetricType.GAUGE, "%", "Error rate")
        self.metrics_collector.register_metric("app.users.active", MetricType.GAUGE, "users", "Active users")
        
        # Register custom collectors
        self.metrics_collector.register_custom_collector("system.cpu.usage", self._collect_cpu_usage)
        self.metrics_collector.register_custom_collector("system.memory.usage", self._collect_memory_usage)
        self.metrics_collector.register_custom_collector("system.disk.usage", self._collect_disk_usage)
    
    def _setup_default_alerts(self):
        """Setup default alert rules."""
        # High CPU usage
        self.alert_manager.add_alert_rule(AlertRule(
            id="high_cpu_usage",
            name="High CPU Usage",
            metric_name="system.cpu.usage",
            condition=">",
            threshold=80.0,
            severity=AlertSeverity.HIGH,
            duration=timedelta(minutes=5)
        ))
        
        # High memory usage
        self.alert_manager.add_alert_rule(AlertRule(
            id="high_memory_usage",
            name="High Memory Usage",
            metric_name="system.memory.usage",
            condition=">",
            threshold=85.0,
            severity=AlertSeverity.HIGH,
            duration=timedelta(minutes=5)
        ))
        
        # High disk usage
        self.alert_manager.add_alert_rule(AlertRule(
            id="high_disk_usage",
            name="High Disk Usage",
            metric_name="system.disk.usage",
            condition=">",
            threshold=90.0,
            severity=AlertSeverity.CRITICAL,
            duration=timedelta(minutes=2)
        ))
        
        # High error rate
        self.alert_manager.add_alert_rule(AlertRule(
            id="high_error_rate",
            name="High Error Rate",
            metric_name="app.errors.rate",
            condition=">",
            threshold=5.0,
            severity=AlertSeverity.HIGH,
            duration=timedelta(minutes=3)
        ))
    
    def _collect_cpu_usage(self) -> float:
        """Collect CPU usage percentage."""
        return psutil.cpu_percent(interval=1)
    
    def _collect_memory_usage(self) -> float:
        """Collect memory usage percentage."""
        return psutil.virtual_memory().percent
    
    def _collect_disk_usage(self) -> float:
        """Collect disk usage percentage."""
        return psutil.disk_usage('/').percent
    
    async def start(self):
        """Start the monitoring dashboard."""
        # Start metrics collection
        await self.metrics_collector.start_collection("system.cpu.usage", 30.0)
        await self.metrics_collector.start_collection("system.memory.usage", 30.0)
        await self.metrics_collector.start_collection("system.disk.usage", 60.0)
        
        # Start alert evaluation
        await self.alert_manager.start_evaluation()
        
        # Start system monitoring
        self.system_monitoring_task = asyncio.create_task(self._system_monitoring_loop())
        
        logger.info("Monitoring dashboard started")
    
    async def stop(self):
        """Stop the monitoring dashboard."""
        # Stop metrics collection
        await self.metrics_collector.stop_all_collection()
        
        # Stop alert evaluation
        await self.alert_manager.stop_evaluation()
        
        # Stop system monitoring
        if self.system_monitoring_task:
            self.system_monitoring_task.cancel()
            try:
                await self.system_monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Monitoring dashboard stopped")
    
    async def _system_monitoring_loop(self):
        """Background system monitoring loop."""
        while True:
            try:
                await asyncio.sleep(60.0)  # Monitor every minute
                
                # Collect additional system metrics
                await self._collect_system_metrics()
                
                # Collect application metrics
                await self._collect_application_metrics()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in system monitoring loop: {e}")
    
    async def _collect_system_metrics(self):
        """Collect additional system metrics."""
        try:
            # Network I/O
            net_io = psutil.net_io_counters()
            self.metrics_collector.set_gauge("system.network.bytes_sent", net_io.bytes_sent)
            self.metrics_collector.set_gauge("system.network.bytes_recv", net_io.bytes_recv)
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    async def _collect_application_metrics(self):
        """Collect application-specific metrics."""
        try:
            # Get metrics from other services
            
            # Load balancer metrics
            lb_service = get_load_balancing_service()
            if lb_service:
                lb_metrics = lb_service.get_metrics()
                if 'load_balancer' in lb_metrics:
                    lb_data = lb_metrics['load_balancer']
                    if 'request_metrics' in lb_data:
                        req_metrics = lb_data['request_metrics']
                        self.metrics_collector.set_gauge("app.requests.rate", req_metrics.get('requests_per_second', 0))
                        self.metrics_collector.set_gauge("app.response.time", req_metrics.get('average_response_time', 0))
                        
                        # Calculate error rate
                        total_requests = req_metrics.get('total_requests', 0)
                        failed_requests = req_metrics.get('failed_requests', 0)
                        if total_requests > 0:
                            error_rate = (failed_requests / total_requests) * 100
                            self.metrics_collector.set_gauge("app.errors.rate", error_rate)
            
            # Queue metrics
            queue_manager = get_queue_manager()
            if queue_manager:
                queue_stats = queue_manager.get_stats()
                # Add queue-related metrics here
            
            # Health check metrics
            health_checker = get_health_checker()
            if health_checker:
                overall_status = health_checker.get_overall_status()
                # Convert health status to numeric for monitoring
                health_score = 100 if overall_status.status == "healthy" else 0
                self.metrics_collector.set_gauge("app.health.score", health_score)
            
        except Exception as e:
            logger.error(f"Error collecting application metrics: {e}")
    
    # Public API methods
    def record_request(self, response_time: float, success: bool = True):
        """Record a request metric."""
        self.metrics_collector.increment_counter("app.requests.total")
        self.metrics_collector.record_timer("app.response.time", response_time)
        
        if not success:
            self.metrics_collector.increment_counter("app.errors.total")
    
    def record_user_activity(self, active_users: int):
        """Record user activity metrics."""
        self.metrics_collector.set_gauge("app.users.active", active_users)
    
    def record_custom_metric(self, name: str, value: float, metric_type: MetricType = MetricType.GAUGE, tags: Optional[Dict[str, str]] = None):
        """Record a custom metric."""
        if name not in self.metrics_collector.metrics:
            self.metrics_collector.register_metric(name, metric_type)
        
        self.metrics_collector.record_metric(name, value, tags=tags)
    
    def get_dashboard_data(self, dashboard_id: str) -> Dict[str, Any]:
        """Get complete dashboard data."""
        dashboard = self.dashboard_manager.get_dashboard(dashboard_id)
        if not dashboard:
            return {}
        
        # Get data for all widgets
        widgets_data = []
        for widget in dashboard.widgets:
            widget_data = self.dashboard_manager.get_widget_data(dashboard_id, widget.id)
            widgets_data.append(widget_data)
        
        return {
            'dashboard': {
                'id': dashboard.id,
                'name': dashboard.name,
                'description': dashboard.description,
                'type': dashboard.dashboard_type.value,
                'updated_at': dashboard.updated_at.isoformat()
            },
            'widgets': widgets_data,
            'alerts': {
                'active': len(self.alert_manager.get_active_alerts()),
                'total': len(self.alert_manager.get_alert_history())
            }
        }
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics."""
        metrics_data = {}
        
        for name, metric in self.metrics_collector.get_all_metrics().items():
            latest_value = metric.get_latest_value()
            stats = metric.get_statistics(timedelta(hours=1))
            
            metrics_data[name] = {
                'type': metric.metric_type.value,
                'unit': metric.unit,
                'description': metric.description,
                'latest_value': latest_value,
                'statistics': stats,
                'data_points': len(metric.points)
            }
        
        return {
            'metrics': metrics_data,
            'total_metrics': len(metrics_data),
            'collection_status': 'active' if self.system_monitoring_task else 'stopped'
        }
    
    def export_metrics(self, format: str = "json", time_range: Optional[timedelta] = None) -> str:
        """Export metrics data."""
        end_time = datetime.utcnow()
        start_time = end_time - (time_range or timedelta(hours=24))
        
        export_data = {
            'export_time': end_time.isoformat(),
            'time_range': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat()
            },
            'metrics': {}
        }
        
        for name, metric in self.metrics_collector.get_all_metrics().items():
            points = [
                {
                    'timestamp': point.timestamp.isoformat(),
                    'value': point.value,
                    'tags': point.tags
                }
                for point in metric.points
                if start_time <= point.timestamp <= end_time
            ]
            
            export_data['metrics'][name] = {
                'type': metric.metric_type.value,
                'unit': metric.unit,
                'description': metric.description,
                'points': points
            }
        
        if format.lower() == "json":
            return json.dumps(export_data, indent=2)
        else:
            # Could add other formats like CSV, Prometheus, etc.
            return json.dumps(export_data, indent=2)


# Global monitoring dashboard
monitoring_dashboard: Optional[MonitoringDashboard] = None


def get_monitoring_dashboard() -> Optional[MonitoringDashboard]:
    """Get the global monitoring dashboard."""
    return monitoring_dashboard


def initialize_monitoring_dashboard() -> MonitoringDashboard:
    """Initialize the global monitoring dashboard."""
    global monitoring_dashboard
    
    monitoring_dashboard = MonitoringDashboard()
    
    logger.info("Global monitoring dashboard initialized")
    return monitoring_dashboard


# Utility decorators
def monitor_performance(metric_name: str):
    """Decorator to monitor function performance."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start_time
                dashboard = get_monitoring_dashboard()
                if dashboard:
                    dashboard.metrics_collector.record_timer(f"{metric_name}.duration", duration)
                    dashboard.metrics_collector.increment_counter(f"{metric_name}.calls")
                    if not success:
                        dashboard.metrics_collector.increment_counter(f"{metric_name}.errors")
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start_time
                dashboard = get_monitoring_dashboard()
                if dashboard:
                    dashboard.metrics_collector.record_timer(f"{metric_name}.duration", duration)
                    dashboard.metrics_collector.increment_counter(f"{metric_name}.calls")
                    if not success:
                        dashboard.metrics_collector.increment_counter(f"{metric_name}.errors")
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def track_metric(metric_name: str, metric_type: MetricType = MetricType.COUNTER):
    """Decorator to track custom metrics."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            dashboard = get_monitoring_dashboard()
            if dashboard:
                if metric_type == MetricType.COUNTER:
                    dashboard.metrics_collector.increment_counter(metric_name)
                elif metric_type == MetricType.GAUGE and isinstance(result, (int, float)):
                    dashboard.metrics_collector.set_gauge(metric_name, result)
            
            return result
        
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            dashboard = get_monitoring_dashboard()
            if dashboard:
                if metric_type == MetricType.COUNTER:
                    dashboard.metrics_collector.increment_counter(metric_name)
                elif metric_type == MetricType.GAUGE and isinstance(result, (int, float)):
                    dashboard.metrics_collector.set_gauge(metric_name, result)
            
            return result
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator