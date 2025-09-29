"""Comprehensive alerting system for the Cliper application."""

import asyncio
import smtplib
import json
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass, asdict
from enum import Enum

import aiohttp
import redis
from jinja2 import Template

from ..core.config import settings
from .metrics import metrics_collector

class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AlertStatus(Enum):
    """Alert status."""
    FIRING = "firing"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SILENCED = "silenced"

@dataclass
class Alert:
    """Alert data structure."""
    id: str
    name: str
    description: str
    severity: AlertSeverity
    status: AlertStatus
    labels: Dict[str, str]
    annotations: Dict[str, str]
    starts_at: datetime
    ends_at: Optional[datetime] = None
    generator_url: Optional[str] = None
    fingerprint: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        data = asdict(self)
        data['severity'] = self.severity.value
        data['status'] = self.status.value
        data['starts_at'] = self.starts_at.isoformat()
        if self.ends_at:
            data['ends_at'] = self.ends_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Alert':
        """Create alert from dictionary."""
        data['severity'] = AlertSeverity(data['severity'])
        data['status'] = AlertStatus(data['status'])
        data['starts_at'] = datetime.fromisoformat(data['starts_at'])
        if data.get('ends_at'):
            data['ends_at'] = datetime.fromisoformat(data['ends_at'])
        return cls(**data)

class AlertRule:
    """Alert rule definition."""
    
    def __init__(self, name: str, condition: Callable[[], bool], 
                 severity: AlertSeverity, description: str,
                 labels: Dict[str, str] = None, 
                 annotations: Dict[str, str] = None,
                 for_duration: int = 0):
        self.name = name
        self.condition = condition
        self.severity = severity
        self.description = description
        self.labels = labels or {}
        self.annotations = annotations or {}
        self.for_duration = for_duration  # seconds
        self.last_triggered = None
        self.consecutive_triggers = 0
    
    def evaluate(self) -> Optional[Alert]:
        """Evaluate rule and return alert if triggered."""
        try:
            if self.condition():
                current_time = datetime.utcnow()
                
                if self.last_triggered is None:
                    self.last_triggered = current_time
                    self.consecutive_triggers = 1
                else:
                    self.consecutive_triggers += 1
                
                # Check if alert should fire based on duration
                if (current_time - self.last_triggered).total_seconds() >= self.for_duration:
                    alert_id = f"{self.name}_{int(time.time())}"
                    
                    return Alert(
                        id=alert_id,
                        name=self.name,
                        description=self.description,
                        severity=self.severity,
                        status=AlertStatus.FIRING,
                        labels=self.labels.copy(),
                        annotations=self.annotations.copy(),
                        starts_at=self.last_triggered,
                        fingerprint=self._generate_fingerprint()
                    )
            else:
                # Reset trigger state
                self.last_triggered = None
                self.consecutive_triggers = 0
                
        except Exception as e:
            print(f"Error evaluating alert rule {self.name}: {e}")
        
        return None
    
    def _generate_fingerprint(self) -> str:
        """Generate unique fingerprint for alert."""
        import hashlib
        content = f"{self.name}:{self.labels}:{self.annotations}"
        return hashlib.md5(content.encode()).hexdigest()

class NotificationChannel:
    """Base class for notification channels."""
    
    async def send(self, alert: Alert) -> bool:
        """Send alert notification."""
        raise NotImplementedError

class EmailNotificationChannel(NotificationChannel):
    """Email notification channel."""
    
    def __init__(self, smtp_host: str, smtp_port: int, username: str, 
                 password: str, from_email: str, to_emails: List[str],
                 use_tls: bool = True):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.to_emails = to_emails
        self.use_tls = use_tls
    
    async def send(self, alert: Alert) -> bool:
        """Send email notification."""
        try:
            # Create email content
            subject = f"[{alert.severity.value.upper()}] {alert.name}"
            
            # HTML template for email
            html_template = Template("""
            <html>
            <body>
                <h2 style="color: {{ color }};">{{ alert.name }}</h2>
                <p><strong>Severity:</strong> {{ alert.severity.value.title() }}</p>
                <p><strong>Status:</strong> {{ alert.status.value.title() }}</p>
                <p><strong>Description:</strong> {{ alert.description }}</p>
                <p><strong>Started At:</strong> {{ alert.starts_at.strftime('%Y-%m-%d %H:%M:%S UTC') }}</p>
                
                {% if alert.labels %}
                <h3>Labels:</h3>
                <ul>
                {% for key, value in alert.labels.items() %}
                    <li><strong>{{ key }}:</strong> {{ value }}</li>
                {% endfor %}
                </ul>
                {% endif %}
                
                {% if alert.annotations %}
                <h3>Annotations:</h3>
                <ul>
                {% for key, value in alert.annotations.items() %}
                    <li><strong>{{ key }}:</strong> {{ value }}</li>
                {% endfor %}
                </ul>
                {% endif %}
                
                {% if alert.generator_url %}
                <p><a href="{{ alert.generator_url }}">View in Dashboard</a></p>
                {% endif %}
            </body>
            </html>
            """)
            
            # Determine color based on severity
            color_map = {
                AlertSeverity.INFO: "#17a2b8",
                AlertSeverity.WARNING: "#ffc107",
                AlertSeverity.ERROR: "#fd7e14",
                AlertSeverity.CRITICAL: "#dc3545"
            }
            
            html_content = html_template.render(
                alert=alert,
                color=color_map.get(alert.severity, "#6c757d")
            )
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = ', '.join(self.to_emails)
            
            # Add HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            print(f"Failed to send email notification: {e}")
            return False

class SlackNotificationChannel(NotificationChannel):
    """Slack notification channel."""
    
    def __init__(self, webhook_url: str, channel: str = None, username: str = "Cliper Alerts"):
        self.webhook_url = webhook_url
        self.channel = channel
        self.username = username
    
    async def send(self, alert: Alert) -> bool:
        """Send Slack notification."""
        try:
            # Color based on severity
            color_map = {
                AlertSeverity.INFO: "#36a64f",
                AlertSeverity.WARNING: "#ffcc00",
                AlertSeverity.ERROR: "#ff6600",
                AlertSeverity.CRITICAL: "#ff0000"
            }
            
            # Create Slack message
            payload = {
                "username": self.username,
                "attachments": [{
                    "color": color_map.get(alert.severity, "#cccccc"),
                    "title": alert.name,
                    "text": alert.description,
                    "fields": [
                        {
                            "title": "Severity",
                            "value": alert.severity.value.title(),
                            "short": True
                        },
                        {
                            "title": "Status",
                            "value": alert.status.value.title(),
                            "short": True
                        },
                        {
                            "title": "Started At",
                            "value": alert.starts_at.strftime('%Y-%m-%d %H:%M:%S UTC'),
                            "short": False
                        }
                    ],
                    "footer": "Cliper Monitoring",
                    "ts": int(alert.starts_at.timestamp())
                }]
            }
            
            if self.channel:
                payload["channel"] = self.channel
            
            # Add labels and annotations as fields
            if alert.labels:
                for key, value in alert.labels.items():
                    payload["attachments"][0]["fields"].append({
                        "title": f"Label: {key}",
                        "value": value,
                        "short": True
                    })
            
            # Send to Slack
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    return response.status == 200
                    
        except Exception as e:
            print(f"Failed to send Slack notification: {e}")
            return False

class WebhookNotificationChannel(NotificationChannel):
    """Generic webhook notification channel."""
    
    def __init__(self, webhook_url: str, headers: Dict[str, str] = None):
        self.webhook_url = webhook_url
        self.headers = headers or {"Content-Type": "application/json"}
    
    async def send(self, alert: Alert) -> bool:
        """Send webhook notification."""
        try:
            payload = alert.to_dict()
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url, 
                    json=payload, 
                    headers=self.headers
                ) as response:
                    return response.status < 400
                    
        except Exception as e:
            print(f"Failed to send webhook notification: {e}")
            return False

class AlertManager:
    """Central alert management system."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.rules: List[AlertRule] = []
        self.notification_channels: List[NotificationChannel] = []
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.silenced_alerts: Dict[str, datetime] = {}
        
        # Initialize default alert rules
        self._initialize_default_rules()
    
    def add_rule(self, rule: AlertRule):
        """Add alert rule."""
        self.rules.append(rule)
    
    def add_notification_channel(self, channel: NotificationChannel):
        """Add notification channel."""
        self.notification_channels.append(channel)
    
    def _initialize_default_rules(self):
        """Initialize default alert rules."""
        
        # High CPU usage
        self.add_rule(AlertRule(
            name="HighCPUUsage",
            condition=lambda: self._get_cpu_usage() > 80,
            severity=AlertSeverity.WARNING,
            description="CPU usage is above 80%",
            labels={"component": "system", "resource": "cpu"},
            annotations={"runbook_url": "https://docs.cliper.com/runbooks/high-cpu"},
            for_duration=300  # 5 minutes
        ))
        
        # Critical CPU usage
        self.add_rule(AlertRule(
            name="CriticalCPUUsage",
            condition=lambda: self._get_cpu_usage() > 95,
            severity=AlertSeverity.CRITICAL,
            description="CPU usage is critically high (>95%)",
            labels={"component": "system", "resource": "cpu"},
            annotations={"runbook_url": "https://docs.cliper.com/runbooks/critical-cpu"},
            for_duration=60  # 1 minute
        ))
        
        # High memory usage
        self.add_rule(AlertRule(
            name="HighMemoryUsage",
            condition=lambda: self._get_memory_usage_percent() > 85,
            severity=AlertSeverity.WARNING,
            description="Memory usage is above 85%",
            labels={"component": "system", "resource": "memory"},
            annotations={"runbook_url": "https://docs.cliper.com/runbooks/high-memory"},
            for_duration=300
        ))
        
        # Database connection issues
        self.add_rule(AlertRule(
            name="DatabaseConnectionHigh",
            condition=lambda: self._get_db_connections() > 80,
            severity=AlertSeverity.WARNING,
            description="Database connections are high",
            labels={"component": "database"},
            annotations={"runbook_url": "https://docs.cliper.com/runbooks/db-connections"},
            for_duration=180
        ))
        
        # High error rate
        self.add_rule(AlertRule(
            name="HighErrorRate",
            condition=lambda: self._get_error_rate() > 0.05,  # 5% error rate
            severity=AlertSeverity.ERROR,
            description="HTTP error rate is above 5%",
            labels={"component": "application"},
            annotations={"runbook_url": "https://docs.cliper.com/runbooks/high-error-rate"},
            for_duration=120
        ))
        
        # Video processing queue backup
        self.add_rule(AlertRule(
            name="VideoQueueBackup",
            condition=lambda: self._get_video_queue_size() > 100,
            severity=AlertSeverity.WARNING,
            description="Video processing queue has backed up",
            labels={"component": "video-processing"},
            annotations={"runbook_url": "https://docs.cliper.com/runbooks/video-queue"},
            for_duration=600  # 10 minutes
        ))
        
        # Redis connection issues
        self.add_rule(AlertRule(
            name="RedisConnectionFailed",
            condition=lambda: not self._check_redis_health(),
            severity=AlertSeverity.CRITICAL,
            description="Redis connection failed",
            labels={"component": "redis"},
            annotations={"runbook_url": "https://docs.cliper.com/runbooks/redis-down"},
            for_duration=30
        ))
        
        # Disk space low
        self.add_rule(AlertRule(
            name="DiskSpaceLow",
            condition=lambda: self._get_disk_usage_percent() > 85,
            severity=AlertSeverity.WARNING,
            description="Disk space usage is above 85%",
            labels={"component": "system", "resource": "disk"},
            annotations={"runbook_url": "https://docs.cliper.com/runbooks/disk-space"},
            for_duration=300
        ))
    
    def _get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        try:
            import psutil
            return psutil.cpu_percent(interval=1)
        except Exception:
            return 0
    
    def _get_memory_usage_percent(self) -> float:
        """Get current memory usage percentage."""
        try:
            import psutil
            return psutil.virtual_memory().percent
        except Exception:
            return 0
    
    def _get_disk_usage_percent(self) -> float:
        """Get current disk usage percentage."""
        try:
            import psutil
            return psutil.disk_usage('/').percent
        except Exception:
            return 0
    
    def _get_db_connections(self) -> int:
        """Get current database connections."""
        try:
            # This would be implemented based on your database monitoring
            return 0
        except Exception:
            return 0
    
    def _get_error_rate(self) -> float:
        """Get current error rate."""
        try:
            # Calculate error rate from metrics
            return 0.0
        except Exception:
            return 0.0
    
    def _get_video_queue_size(self) -> int:
        """Get video processing queue size."""
        try:
            return self.redis.llen('video_processing_queue')
        except Exception:
            return 0
    
    def _check_redis_health(self) -> bool:
        """Check Redis health."""
        try:
            self.redis.ping()
            return True
        except Exception:
            return False
    
    async def evaluate_rules(self):
        """Evaluate all alert rules."""
        for rule in self.rules:
            try:
                alert = rule.evaluate()
                if alert:
                    await self._handle_alert(alert)
            except Exception as e:
                print(f"Error evaluating rule {rule.name}: {e}")
    
    async def _handle_alert(self, alert: Alert):
        """Handle a triggered alert."""
        # Check if alert is silenced
        if self._is_alert_silenced(alert):
            return
        
        # Check if this is a new alert or update to existing
        existing_alert = self.active_alerts.get(alert.fingerprint)
        
        if existing_alert:
            # Update existing alert
            existing_alert.status = alert.status
            if alert.status == AlertStatus.RESOLVED:
                existing_alert.ends_at = datetime.utcnow()
                # Move to history
                self.alert_history.append(existing_alert)
                del self.active_alerts[alert.fingerprint]
        else:
            # New alert
            self.active_alerts[alert.fingerprint] = alert
            
            # Send notifications
            await self._send_notifications(alert)
            
            # Store in Redis for persistence
            self._store_alert(alert)
    
    def _is_alert_silenced(self, alert: Alert) -> bool:
        """Check if alert is silenced."""
        silence_key = f"{alert.name}:{alert.fingerprint}"
        silence_until = self.silenced_alerts.get(silence_key)
        
        if silence_until and datetime.utcnow() < silence_until:
            return True
        
        # Clean up expired silences
        if silence_until and datetime.utcnow() >= silence_until:
            del self.silenced_alerts[silence_key]
        
        return False
    
    async def _send_notifications(self, alert: Alert):
        """Send alert notifications through all channels."""
        for channel in self.notification_channels:
            try:
                success = await channel.send(alert)
                if not success:
                    print(f"Failed to send notification through {type(channel).__name__}")
            except Exception as e:
                print(f"Error sending notification through {type(channel).__name__}: {e}")
    
    def _store_alert(self, alert: Alert):
        """Store alert in Redis."""
        try:
            key = f"alert:{alert.id}"
            self.redis.setex(key, timedelta(days=30), json.dumps(alert.to_dict()))
            
            # Add to active alerts list
            self.redis.sadd("active_alerts", alert.id)
            
        except Exception as e:
            print(f"Error storing alert: {e}")
    
    def silence_alert(self, alert_name: str, fingerprint: str, duration_minutes: int):
        """Silence an alert for specified duration."""
        silence_key = f"{alert_name}:{fingerprint}"
        silence_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
        self.silenced_alerts[silence_key] = silence_until
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str):
        """Acknowledge an alert."""
        for alert in self.active_alerts.values():
            if alert.id == alert_id:
                alert.status = AlertStatus.ACKNOWLEDGED
                alert.annotations["acknowledged_by"] = acknowledged_by
                alert.annotations["acknowledged_at"] = datetime.utcnow().isoformat()
                break
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return list(self.active_alerts.values())
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get alert history."""
        return self.alert_history[-limit:]
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert statistics."""
        active_count = len(self.active_alerts)
        
        # Count by severity
        severity_counts = {severity.value: 0 for severity in AlertSeverity}
        for alert in self.active_alerts.values():
            severity_counts[alert.severity.value] += 1
        
        # Recent alerts (last 24 hours)
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_alerts = [
            alert for alert in self.alert_history 
            if alert.starts_at > recent_cutoff
        ]
        
        return {
            "active_alerts": active_count,
            "severity_breakdown": severity_counts,
            "recent_alerts_24h": len(recent_alerts),
            "total_rules": len(self.rules),
            "notification_channels": len(self.notification_channels)
        }

# Background task for alert evaluation
async def alert_evaluation_task(alert_manager: AlertManager):
    """Background task to evaluate alerts."""
    while True:
        try:
            await alert_manager.evaluate_rules()
        except Exception as e:
            print(f"Error in alert evaluation: {e}")
        
        await asyncio.sleep(30)  # Evaluate every 30 seconds

# Initialize alert manager
def get_alert_manager() -> AlertManager:
    """Get alert manager instance."""
    redis_client = redis.Redis.from_url(settings.REDIS_URL)
    return AlertManager(redis_client)

def get_alerting_system() -> AlertManager:
    """Get alerting system instance (alias for get_alert_manager)."""
    return get_alert_manager()

class AlertingSystem:
    """Alerting system class for backward compatibility."""
    
    def __init__(self):
        self.alert_manager = get_alert_manager()
    
    def send_alert(self, alert: Alert):
        """Send an alert through the alert manager."""
        return self.alert_manager.handle_alert(alert)
    
    def add_rule(self, rule: AlertRule):
        """Add an alert rule."""
        return self.alert_manager.add_rule(rule)
    
    def get_active_alerts(self):
        """Get active alerts."""
        return self.alert_manager.get_active_alerts()
    
    def configure_notifications(self, channels):
        """Configure notification channels."""
        return configure_notification_channels(channels)

# Configure notification channels based on settings
def configure_notification_channels(alert_manager: AlertManager):
    """Configure notification channels from settings."""
    
    # Email notifications
    if hasattr(settings, 'SMTP_HOST') and settings.SMTP_HOST:
        email_channel = EmailNotificationChannel(
            smtp_host=settings.SMTP_HOST,
            smtp_port=getattr(settings, 'SMTP_PORT', 587),
            username=getattr(settings, 'SMTP_USERNAME', ''),
            password=getattr(settings, 'SMTP_PASSWORD', ''),
            from_email=getattr(settings, 'ALERT_FROM_EMAIL', 'alerts@cliper.com'),
            to_emails=getattr(settings, 'ALERT_TO_EMAILS', ['admin@cliper.com']),
            use_tls=getattr(settings, 'SMTP_TLS', True)
        )
        alert_manager.add_notification_channel(email_channel)
    
    # Slack notifications
    if hasattr(settings, 'SLACK_WEBHOOK_URL') and settings.SLACK_WEBHOOK_URL:
        slack_channel = SlackNotificationChannel(
            webhook_url=settings.SLACK_WEBHOOK_URL,
            channel=getattr(settings, 'SLACK_CHANNEL', '#alerts'),
            username=getattr(settings, 'SLACK_USERNAME', 'Cliper Alerts')
        )
        alert_manager.add_notification_channel(slack_channel)
    
    # Webhook notifications
    if hasattr(settings, 'ALERT_WEBHOOK_URL') and settings.ALERT_WEBHOOK_URL:
        webhook_channel = WebhookNotificationChannel(
            webhook_url=settings.ALERT_WEBHOOK_URL,
            headers=getattr(settings, 'ALERT_WEBHOOK_HEADERS', {})
        )
        alert_manager.add_notification_channel(webhook_channel)