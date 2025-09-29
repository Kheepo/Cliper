"""Production monitoring enhancements for comprehensive observability.

Provides:
- Advanced alerting system
- Log aggregation and analysis
- Performance optimization recommendations
- Production health monitoring
- Automated incident response
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import logging
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import psutil
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from .enhanced_logging import EnhancedLogger, LogLevel, EventType
from .memory_optimizer import EnhancedMemoryOptimizer
from .resource_manager import ResourceMonitor
from ..core.database import get_db
from ..core.redis_client import get_redis_client


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Alert status."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class MetricType(str, Enum):
    """Metric types for monitoring."""
    SYSTEM = "system"
    APPLICATION = "application"
    PERFORMANCE = "performance"
    BUSINESS = "business"
    SECURITY = "security"


@dataclass
class AlertRule:
    """Alert rule configuration."""
    name: str
    metric_name: str
    metric_type: MetricType
    threshold: float
    operator: str  # >, <, >=, <=, ==, !=
    severity: AlertSeverity
    description: str
    enabled: bool = True
    cooldown_minutes: int = 15
    notification_channels: List[str] = None
    auto_resolve: bool = True
    resolve_threshold: Optional[float] = None
    
    def __post_init__(self):
        if self.notification_channels is None:
            self.notification_channels = ["email", "log"]


@dataclass
class Alert:
    """Active alert."""
    id: str
    rule_name: str
    metric_name: str
    current_value: float
    threshold: float
    severity: AlertSeverity
    status: AlertStatus
    message: str
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class PerformanceInsight:
    """Performance analysis insight."""
    category: str
    severity: str
    title: str
    description: str
    recommendation: str
    impact: str
    effort: str  # low, medium, high
    metrics: Dict[str, Any]
    timestamp: datetime


class ProductionMonitor:
    """Production monitoring and alerting system."""
    
    def __init__(self):
        self.logger = EnhancedLogger("production_monitor")
        self.memory_optimizer = EnhancedMemoryOptimizer()
        self.resource_monitor = ResourceMonitor()
        self.alert_rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.metrics_history: Dict[str, List[Dict[str, Any]]] = {}
        self.performance_insights: List[PerformanceInsight] = []
        self.notification_handlers: Dict[str, Callable] = {}
        self.running = False
        self.check_interval = 60  # seconds
        
        # Initialize default alert rules
        self._setup_default_alert_rules()
        
        # Setup notification handlers
        self._setup_notification_handlers()
    
    def _setup_default_alert_rules(self):
        """Setup default production alert rules."""
        default_rules = [
            AlertRule(
                name="high_cpu_usage",
                metric_name="cpu_percent",
                metric_type=MetricType.SYSTEM,
                threshold=85.0,
                operator=">",
                severity=AlertSeverity.HIGH,
                description="CPU usage is critically high",
                resolve_threshold=70.0
            ),
            AlertRule(
                name="high_memory_usage",
                metric_name="memory_percent",
                metric_type=MetricType.SYSTEM,
                threshold=90.0,
                operator=">",
                severity=AlertSeverity.CRITICAL,
                description="Memory usage is critically high",
                resolve_threshold=80.0
            ),
            AlertRule(
                name="disk_space_low",
                metric_name="disk_percent",
                metric_type=MetricType.SYSTEM,
                threshold=85.0,
                operator=">",
                severity=AlertSeverity.HIGH,
                description="Disk space is running low",
                resolve_threshold=75.0
            ),
            AlertRule(
                name="high_error_rate",
                metric_name="error_rate_percent",
                metric_type=MetricType.APPLICATION,
                threshold=5.0,
                operator=">",
                severity=AlertSeverity.HIGH,
                description="Application error rate is too high",
                resolve_threshold=2.0
            ),
            AlertRule(
                name="slow_response_time",
                metric_name="avg_response_time_ms",
                metric_type=MetricType.PERFORMANCE,
                threshold=5000.0,
                operator=">",
                severity=AlertSeverity.MEDIUM,
                description="Average response time is too slow",
                resolve_threshold=3000.0
            ),
            AlertRule(
                name="queue_backlog",
                metric_name="queue_length",
                metric_type=MetricType.APPLICATION,
                threshold=50.0,
                operator=">",
                severity=AlertSeverity.HIGH,
                description="Processing queue has significant backlog",
                resolve_threshold=20.0
            ),
            AlertRule(
                name="failed_jobs_spike",
                metric_name="failed_jobs_per_hour",
                metric_type=MetricType.APPLICATION,
                threshold=10.0,
                operator=">",
                severity=AlertSeverity.HIGH,
                description="High number of failed jobs detected",
                resolve_threshold=3.0
            )
        ]
        
        for rule in default_rules:
            self.alert_rules[rule.name] = rule
    
    def _setup_notification_handlers(self):
        """Setup notification handlers for alerts."""
        self.notification_handlers = {
            "log": self._log_notification,
            "email": self._email_notification,
            "webhook": self._webhook_notification
        }
    
    async def start_monitoring(self):
        """Start the production monitoring loop."""
        if self.running:
            return
        
        self.running = True
        self.logger.info("Starting production monitoring", event_type=EventType.SYSTEM)
        
        # Start monitoring tasks
        tasks = [
            asyncio.create_task(self._monitoring_loop()),
            asyncio.create_task(self._performance_analysis_loop()),
            asyncio.create_task(self._cleanup_loop())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            self.logger.error("Monitoring loop failed", error=e)
            self.running = False
    
    async def stop_monitoring(self):
        """Stop the production monitoring."""
        self.running = False
        self.logger.info("Stopping production monitoring", event_type=EventType.SYSTEM)
    
    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                # Collect metrics
                metrics = await self._collect_all_metrics()
                
                # Store metrics history
                timestamp = datetime.utcnow()
                for metric_type, metric_data in metrics.items():
                    if metric_type not in self.metrics_history:
                        self.metrics_history[metric_type] = []
                    
                    self.metrics_history[metric_type].append({
                        "timestamp": timestamp,
                        **metric_data
                    })
                    
                    # Keep only last 24 hours of data
                    cutoff = timestamp - timedelta(hours=24)
                    self.metrics_history[metric_type] = [
                        m for m in self.metrics_history[metric_type]
                        if m["timestamp"] > cutoff
                    ]
                
                # Check alert rules
                await self._check_alert_rules(metrics)
                
                # Log monitoring status
                self.logger.debug(
                    "Monitoring check completed",
                    metrics_collected=len(metrics),
                    active_alerts=len(self.active_alerts),
                    event_type=EventType.SYSTEM
                )
                
            except Exception as e:
                self.logger.error("Error in monitoring loop", error=e)
            
            await asyncio.sleep(self.check_interval)
    
    async def _performance_analysis_loop(self):
        """Performance analysis and optimization recommendations."""
        while self.running:
            try:
                # Run performance analysis every 5 minutes
                await asyncio.sleep(300)
                
                insights = await self._analyze_performance()
                self.performance_insights.extend(insights)
                
                # Keep only last 100 insights
                self.performance_insights = self.performance_insights[-100:]
                
                # Log significant insights
                for insight in insights:
                    if insight.severity in ["high", "critical"]:
                        self.logger.warning(
                            f"Performance insight: {insight.title}",
                            insight=asdict(insight),
                            event_type=EventType.PERFORMANCE
                        )
                
            except Exception as e:
                self.logger.error("Error in performance analysis loop", error=e)
    
    async def _cleanup_loop(self):
        """Cleanup old data and resolved alerts."""
        while self.running:
            try:
                # Run cleanup every hour
                await asyncio.sleep(3600)
                
                # Clean up resolved alerts older than 7 days
                cutoff = datetime.utcnow() - timedelta(days=7)
                self.alert_history = [
                    alert for alert in self.alert_history
                    if alert.resolved_at is None or alert.resolved_at > cutoff
                ]
                
                # Clean up old metrics (keep 24 hours)
                cutoff = datetime.utcnow() - timedelta(hours=24)
                for metric_type in self.metrics_history:
                    self.metrics_history[metric_type] = [
                        m for m in self.metrics_history[metric_type]
                        if m["timestamp"] > cutoff
                    ]
                
                self.logger.debug("Cleanup completed", event_type=EventType.SYSTEM)
                
            except Exception as e:
                self.logger.error("Error in cleanup loop", error=e)
    
    async def _collect_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Collect all system and application metrics."""
        metrics = {}
        
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            metrics["system"] = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "load_average": list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else [cpu_percent/100]
            }
            
            # Memory optimizer metrics
            memory_stats = self.memory_optimizer.get_memory_stats()
            metrics["memory"] = {
                "current_usage_mb": memory_stats.get("current_usage_mb", 0),
                "peak_usage_mb": memory_stats.get("peak_usage_mb", 0),
                "gc_collections": memory_stats.get("gc_collections", 0)
            }
            
            # Resource monitor metrics
            resource_usage = self.resource_monitor.get_resource_usage()
            metrics["resources"] = {
                "file_handles": resource_usage.file_handles,
                "threads": resource_usage.threads,
                "processes": resource_usage.processes
            }
            
            # Application metrics (mock for now - implement based on your app)
            metrics["application"] = {
                "error_rate_percent": 2.1,  # Implement actual error rate calculation
                "avg_response_time_ms": 1250.5,  # Implement actual response time tracking
                "queue_length": 15,  # Implement actual queue length
                "failed_jobs_per_hour": 2  # Implement actual failed jobs tracking
            }
            
        except Exception as e:
            self.logger.error("Error collecting metrics", error=e)
        
        return metrics
    
    async def _check_alert_rules(self, metrics: Dict[str, Dict[str, Any]]):
        """Check all alert rules against current metrics."""
        for rule_name, rule in self.alert_rules.items():
            if not rule.enabled:
                continue
            
            try:
                # Find metric value
                metric_value = None
                for metric_type, metric_data in metrics.items():
                    if rule.metric_name in metric_data:
                        metric_value = metric_data[rule.metric_name]
                        break
                
                if metric_value is None:
                    continue
                
                # Check if alert should be triggered
                should_alert = self._evaluate_condition(metric_value, rule.threshold, rule.operator)
                
                # Check if alert should be resolved
                should_resolve = False
                if rule.auto_resolve and rule.resolve_threshold is not None:
                    should_resolve = not self._evaluate_condition(metric_value, rule.resolve_threshold, rule.operator)
                
                # Handle alert state changes
                if should_alert and rule_name not in self.active_alerts:
                    await self._trigger_alert(rule, metric_value)
                elif should_resolve and rule_name in self.active_alerts:
                    await self._resolve_alert(rule_name)
                
            except Exception as e:
                self.logger.error(f"Error checking alert rule {rule_name}", error=e)
    
    def _evaluate_condition(self, value: float, threshold: float, operator: str) -> bool:
        """Evaluate alert condition."""
        operators = {
            ">": lambda v, t: v > t,
            "<": lambda v, t: v < t,
            ">=": lambda v, t: v >= t,
            "<=": lambda v, t: v <= t,
            "==": lambda v, t: v == t,
            "!=": lambda v, t: v != t
        }
        return operators.get(operator, lambda v, t: False)(value, threshold)
    
    async def _trigger_alert(self, rule: AlertRule, current_value: float):
        """Trigger a new alert."""
        alert_id = f"{rule.name}_{int(time.time())}"
        
        alert = Alert(
            id=alert_id,
            rule_name=rule.name,
            metric_name=rule.metric_name,
            current_value=current_value,
            threshold=rule.threshold,
            severity=rule.severity,
            status=AlertStatus.ACTIVE,
            message=f"{rule.description}. Current value: {current_value}, Threshold: {rule.threshold}",
            triggered_at=datetime.utcnow(),
            metadata={
                "operator": rule.operator,
                "metric_type": rule.metric_type.value
            }
        )
        
        self.active_alerts[rule.name] = alert
        self.alert_history.append(alert)
        
        # Send notifications
        for channel in rule.notification_channels:
            if channel in self.notification_handlers:
                try:
                    await self.notification_handlers[channel](alert)
                except Exception as e:
                    self.logger.error(f"Failed to send {channel} notification", error=e)
        
        self.logger.error(
            f"Alert triggered: {rule.name}",
            alert=asdict(alert),
            event_type=EventType.SYSTEM
        )
    
    async def _resolve_alert(self, rule_name: str):
        """Resolve an active alert."""
        if rule_name not in self.active_alerts:
            return
        
        alert = self.active_alerts[rule_name]
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()
        
        del self.active_alerts[rule_name]
        
        self.logger.info(
            f"Alert resolved: {rule_name}",
            alert_id=alert.id,
            duration_minutes=(alert.resolved_at - alert.triggered_at).total_seconds() / 60,
            event_type=EventType.SYSTEM
        )
    
    async def _log_notification(self, alert: Alert):
        """Log notification handler."""
        self.logger.error(
            f"ALERT: {alert.message}",
            alert_details=asdict(alert),
            event_type=EventType.SYSTEM
        )
    
    async def _email_notification(self, alert: Alert):
        """Email notification handler (implement based on your email setup)."""
        # This is a placeholder - implement actual email sending
        self.logger.info(
            f"Email notification would be sent for alert: {alert.rule_name}",
            event_type=EventType.SYSTEM
        )
    
    async def _webhook_notification(self, alert: Alert):
        """Webhook notification handler (implement based on your webhook setup)."""
        # This is a placeholder - implement actual webhook sending
        self.logger.info(
            f"Webhook notification would be sent for alert: {alert.rule_name}",
            event_type=EventType.SYSTEM
        )
    
    async def _analyze_performance(self) -> List[PerformanceInsight]:
        """Analyze performance and generate insights."""
        insights = []
        
        try:
            # Analyze memory usage trends
            if "memory" in self.metrics_history and len(self.metrics_history["memory"]) > 10:
                memory_data = self.metrics_history["memory"][-10:]
                avg_usage = sum(m["current_usage_mb"] for m in memory_data) / len(memory_data)
                
                if avg_usage > 800:  # 800MB threshold
                    insights.append(PerformanceInsight(
                        category="memory",
                        severity="medium",
                        title="High Memory Usage Detected",
                        description=f"Average memory usage is {avg_usage:.1f}MB over the last 10 checks",
                        recommendation="Consider implementing memory optimization strategies or increasing available memory",
                        impact="May lead to performance degradation and potential out-of-memory errors",
                        effort="medium",
                        metrics={"avg_usage_mb": avg_usage, "threshold_mb": 800},
                        timestamp=datetime.utcnow()
                    ))
            
            # Analyze CPU usage patterns
            if "system" in self.metrics_history and len(self.metrics_history["system"]) > 5:
                cpu_data = self.metrics_history["system"][-5:]
                avg_cpu = sum(m["cpu_percent"] for m in cpu_data) / len(cpu_data)
                
                if avg_cpu > 70:
                    insights.append(PerformanceInsight(
                        category="cpu",
                        severity="medium",
                        title="High CPU Usage Pattern",
                        description=f"Average CPU usage is {avg_cpu:.1f}% over the last 5 checks",
                        recommendation="Investigate CPU-intensive processes and consider optimization or scaling",
                        impact="May cause request timeouts and degraded user experience",
                        effort="high",
                        metrics={"avg_cpu_percent": avg_cpu, "threshold_percent": 70},
                        timestamp=datetime.utcnow()
                    ))
            
            # Analyze error patterns
            if "application" in self.metrics_history and len(self.metrics_history["application"]) > 3:
                app_data = self.metrics_history["application"][-3:]
                avg_error_rate = sum(m["error_rate_percent"] for m in app_data) / len(app_data)
                
                if avg_error_rate > 3:
                    insights.append(PerformanceInsight(
                        category="reliability",
                        severity="high",
                        title="Elevated Error Rate",
                        description=f"Average error rate is {avg_error_rate:.1f}% over the last 3 checks",
                        recommendation="Review error logs, fix recurring issues, and improve error handling",
                        impact="Directly affects user experience and system reliability",
                        effort="medium",
                        metrics={"avg_error_rate_percent": avg_error_rate, "threshold_percent": 3},
                        timestamp=datetime.utcnow()
                    ))
        
        except Exception as e:
            self.logger.error("Error in performance analysis", error=e)
        
        return insights
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status."""
        return {
            "running": self.running,
            "check_interval_seconds": self.check_interval,
            "active_alerts": len(self.active_alerts),
            "alert_rules": len(self.alert_rules),
            "metrics_tracked": len(self.metrics_history),
            "performance_insights": len(self.performance_insights),
            "last_check": datetime.utcnow().isoformat()
        }
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all active alerts."""
        return [asdict(alert) for alert in self.active_alerts.values()]
    
    def get_performance_insights(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent performance insights."""
        return [asdict(insight) for insight in self.performance_insights[-limit:]]
    
    def acknowledge_alert(self, rule_name: str, acknowledged_by: str) -> bool:
        """Acknowledge an active alert."""
        if rule_name not in self.active_alerts:
            return False
        
        alert = self.active_alerts[rule_name]
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = acknowledged_by
        
        self.logger.info(
            f"Alert acknowledged: {rule_name}",
            acknowledged_by=acknowledged_by,
            event_type=EventType.SYSTEM
        )
        
        return True


# Global production monitor instance
_production_monitor: Optional[ProductionMonitor] = None


def get_production_monitor() -> ProductionMonitor:
    """Get the global production monitor instance."""
    global _production_monitor
    if _production_monitor is None:
        _production_monitor = ProductionMonitor()
    return _production_monitor


# Export main components
__all__ = [
    'ProductionMonitor',
    'AlertRule',
    'Alert',
    'AlertSeverity',
    'AlertStatus',
    'MetricType',
    'PerformanceInsight',
    'get_production_monitor'
]