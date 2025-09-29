"""Monitoring and metrics endpoints for system observability.

Provides comprehensive monitoring capabilities including:
- System metrics and performance data
- Real-time statistics and dashboards
- Resource utilization monitoring
- Application health metrics
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
import psutil
import asyncio
import time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, func
import redis.asyncio as redis
import logging
from ..core.database import get_db_pool
from ..middleware.auth import get_current_user
from ..utils.redis_client import get_redis_client
from ..models import User
from ..models import GeneratedClip as Clip

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/monitoring", tags=["monitoring"])


class SystemMetrics(BaseModel):
    """System resource metrics."""
    timestamp: datetime
    cpu_percent: float = Field(..., description="CPU usage percentage")
    memory_percent: float = Field(..., description="Memory usage percentage")
    memory_used_gb: float = Field(..., description="Memory used in GB")
    memory_total_gb: float = Field(..., description="Total memory in GB")
    disk_percent: float = Field(..., description="Disk usage percentage")
    disk_used_gb: float = Field(..., description="Disk used in GB")
    disk_total_gb: float = Field(..., description="Total disk space in GB")
    network_bytes_sent: int = Field(..., description="Network bytes sent")
    network_bytes_recv: int = Field(..., description="Network bytes received")
    load_average: List[float] = Field(..., description="System load average (1, 5, 15 min)")
    process_count: int = Field(..., description="Number of running processes")
    uptime_seconds: int = Field(..., description="System uptime in seconds")


class ApplicationMetrics(BaseModel):
    """Application-specific metrics."""
    timestamp: datetime
    total_clips: int = Field(..., description="Total clips in system")
    clips_processing: int = Field(..., description="Clips currently processing")
    clips_completed_today: int = Field(..., description="Clips completed today")
    clips_failed_today: int = Field(..., description="Clips failed today")
    active_users: int = Field(..., description="Active users in last 24h")
    total_users: int = Field(..., description="Total registered users")
    storage_used_gb: float = Field(..., description="Storage used by clips in GB")
    average_processing_time: float = Field(..., description="Average processing time in seconds")
    queue_length: int = Field(..., description="Current processing queue length")
    cache_hit_rate: float = Field(..., description="Cache hit rate percentage")
    error_rate: float = Field(..., description="Error rate percentage (last hour)")


class PerformanceMetrics(BaseModel):
    """Performance and timing metrics."""
    timestamp: datetime
    response_times: Dict[str, float] = Field(..., description="Average response times by endpoint")
    throughput: Dict[str, int] = Field(..., description="Requests per minute by endpoint")
    concurrent_connections: int = Field(..., description="Current concurrent connections")
    websocket_connections: int = Field(..., description="Active WebSocket connections")
    database_connections: int = Field(..., description="Active database connections")
    redis_connections: int = Field(..., description="Active Redis connections")
    ffmpeg_processes: int = Field(..., description="Active FFmpeg processes")


class MetricsHistory(BaseModel):
    """Historical metrics data."""
    timeframe: str = Field(..., description="Time frame (1h, 24h, 7d, 30d)")
    data_points: List[Dict[str, Any]] = Field(..., description="Historical data points")
    summary: Dict[str, Any] = Field(..., description="Summary statistics")


class AlertRule(BaseModel):
    """Monitoring alert rule."""
    name: str = Field(..., description="Alert rule name")
    metric: str = Field(..., description="Metric to monitor")
    threshold: float = Field(..., description="Alert threshold")
    operator: str = Field(..., description="Comparison operator (>, <, >=, <=, ==)")
    enabled: bool = Field(True, description="Whether alert is enabled")
    severity: str = Field(..., description="Alert severity (low, medium, high, critical)")
    description: str = Field(..., description="Alert description")


class Alert(BaseModel):
    """Active alert."""
    id: str = Field(..., description="Alert ID")
    rule_name: str = Field(..., description="Alert rule name")
    metric: str = Field(..., description="Metric that triggered alert")
    current_value: float = Field(..., description="Current metric value")
    threshold: float = Field(..., description="Alert threshold")
    severity: str = Field(..., description="Alert severity")
    message: str = Field(..., description="Alert message")
    triggered_at: datetime = Field(..., description="When alert was triggered")
    acknowledged: bool = Field(False, description="Whether alert is acknowledged")


class DashboardData(BaseModel):
    """Complete dashboard data."""
    system_metrics: SystemMetrics
    application_metrics: ApplicationMetrics
    performance_metrics: PerformanceMetrics
    active_alerts: List[Alert]
    recent_activity: List[Dict[str, Any]]
    health_status: str = Field(..., description="Overall health status")


# In-memory storage for metrics (in production, use proper time-series DB)
metrics_store = {
    "system": [],
    "application": [],
    "performance": [],
    "alerts": [],
    "alert_rules": []
}


async def collect_system_metrics() -> SystemMetrics:
    """Collect current system metrics."""
    try:
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory metrics
        memory = psutil.virtual_memory()
        memory_used_gb = memory.used / (1024**3)
        memory_total_gb = memory.total / (1024**3)
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        disk_used_gb = disk.used / (1024**3)
        disk_total_gb = disk.total / (1024**3)
        
        # Network metrics
        network = psutil.net_io_counters()
        
        # Load average (Unix-like systems)
        try:
            load_avg = list(psutil.getloadavg())
        except AttributeError:
            # Windows doesn't have load average
            load_avg = [cpu_percent / 100, cpu_percent / 100, cpu_percent / 100]
        
        # Process count
        process_count = len(psutil.pids())
        
        # Uptime
        uptime_seconds = int(time.time() - psutil.boot_time())
        
        return SystemMetrics(
            timestamp=datetime.utcnow(),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used_gb=memory_used_gb,
            memory_total_gb=memory_total_gb,
            disk_percent=disk.percent,
            disk_used_gb=disk_used_gb,
            disk_total_gb=disk_total_gb,
            network_bytes_sent=network.bytes_sent,
            network_bytes_recv=network.bytes_recv,
            load_average=load_avg,
            process_count=process_count,
            uptime_seconds=uptime_seconds
        )
    except Exception as e:
        logger.error(f"Error collecting system metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to collect system metrics")


async def collect_application_metrics(db: AsyncSession, redis_client: redis.Redis) -> ApplicationMetrics:
    """Collect application-specific metrics."""
    try:
        # Database queries
        total_clips_result = await db.execute(text("SELECT COUNT(*) FROM clips"))
        total_clips = total_clips_result.scalar() or 0
        
        processing_clips_result = await db.execute(
            text("SELECT COUNT(*) FROM clips WHERE status = 'processing'")
        )
        clips_processing = processing_clips_result.scalar() or 0
        
        today = datetime.utcnow().date()
        completed_today_result = await db.execute(
            text("SELECT COUNT(*) FROM clips WHERE status = 'completed' AND DATE(created_at) = :today"),
            {"today": today}
        )
        clips_completed_today = completed_today_result.scalar() or 0
        
        failed_today_result = await db.execute(
            text("SELECT COUNT(*) FROM clips WHERE status = 'failed' AND DATE(created_at) = :today"),
            {"today": today}
        )
        clips_failed_today = failed_today_result.scalar() or 0
        
        # User metrics
        total_users_result = await db.execute(text("SELECT COUNT(*) FROM users"))
        total_users = total_users_result.scalar() or 0
        
        yesterday = datetime.utcnow() - timedelta(days=1)
        active_users_result = await db.execute(
            text("SELECT COUNT(DISTINCT user_id) FROM clips WHERE created_at >= :yesterday"),
            {"yesterday": yesterday}
        )
        active_users = active_users_result.scalar() or 0
        
        # Storage metrics
        storage_result = await db.execute(
            text("SELECT COALESCE(SUM(file_size), 0) FROM clips WHERE file_size IS NOT NULL")
        )
        storage_bytes = storage_result.scalar() or 0
        storage_used_gb = storage_bytes / (1024**3)
        
        # Performance metrics
        avg_time_result = await db.execute(
            text("""
                SELECT AVG(EXTRACT(EPOCH FROM (completed_at - created_at)))
                FROM clips 
                WHERE status = 'completed' AND completed_at IS NOT NULL
                AND created_at >= :since
            """),
            {"since": datetime.utcnow() - timedelta(hours=24)}
        )
        average_processing_time = avg_time_result.scalar() or 0
        
        # Queue length from Redis
        queue_length = await redis_client.llen("clip_processing_queue") or 0
        
        # Cache hit rate (mock data - implement based on your caching strategy)
        cache_hit_rate = 85.5  # This should come from actual cache metrics
        
        # Error rate (mock data - implement based on your error tracking)
        error_rate = 2.1  # This should come from actual error metrics
        
        return ApplicationMetrics(
            timestamp=datetime.utcnow(),
            total_clips=total_clips,
            clips_processing=clips_processing,
            clips_completed_today=clips_completed_today,
            clips_failed_today=clips_failed_today,
            active_users=active_users,
            total_users=total_users,
            storage_used_gb=storage_used_gb,
            average_processing_time=average_processing_time,
            queue_length=queue_length,
            cache_hit_rate=cache_hit_rate,
            error_rate=error_rate
        )
    except Exception as e:
        logger.error(f"Error collecting application metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to collect application metrics")


async def collect_performance_metrics() -> PerformanceMetrics:
    """Collect performance metrics."""
    try:
        # Mock performance data - implement based on your monitoring setup
        response_times = {
            "/clips/generate": 1250.5,
            "/clips/upload": 890.2,
            "/auth/login": 145.8,
            "/health": 12.3
        }
        
        throughput = {
            "/clips/generate": 45,
            "/clips/upload": 78,
            "/auth/login": 23,
            "/health": 120
        }
        
        # Connection counts (mock data)
        concurrent_connections = 156
        websocket_connections = 23
        database_connections = 8
        redis_connections = 4
        ffmpeg_processes = 3
        
        return PerformanceMetrics(
            timestamp=datetime.utcnow(),
            response_times=response_times,
            throughput=throughput,
            concurrent_connections=concurrent_connections,
            websocket_connections=websocket_connections,
            database_connections=database_connections,
            redis_connections=redis_connections,
            ffmpeg_processes=ffmpeg_processes
        )
    except Exception as e:
        logger.error(f"Error collecting performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to collect performance metrics")


@router.get("/metrics/system", response_model=SystemMetrics)
async def get_system_metrics(
    current_user: User = Depends(get_current_user)
):
    """Get current system resource metrics.
    
    Returns real-time system metrics including CPU, memory, disk usage,
    network statistics, and system load information.
    """
    return await collect_system_metrics()


@router.get("/metrics/application", response_model=ApplicationMetrics)
async def get_application_metrics(
    db: AsyncSession = Depends(get_db_pool),
    redis_client: redis.Redis = Depends(get_redis_client),
    current_user: User = Depends(get_current_user)
):
    """Get current application metrics.
    
    Returns application-specific metrics including clip statistics,
    user activity, storage usage, and performance indicators.
    """
    return await collect_application_metrics(db, redis_client)


@router.get("/metrics/performance", response_model=PerformanceMetrics)
async def get_performance_metrics(
    current_user: User = Depends(get_current_user)
):
    """Get current performance metrics.
    
    Returns performance metrics including response times, throughput,
    connection counts, and resource utilization.
    """
    return await collect_performance_metrics()


@router.get("/dashboard", response_model=DashboardData)
async def get_dashboard_data(
    db: AsyncSession = Depends(get_db_pool),
    redis_client: redis.Redis = Depends(get_redis_client),
    current_user: User = Depends(get_current_user)
):
    """Get complete dashboard data.
    
    Returns comprehensive monitoring data for dashboard display,
    including all metrics, alerts, and recent activity.
    """
    try:
        # Collect all metrics concurrently
        system_metrics, app_metrics, perf_metrics = await asyncio.gather(
            collect_system_metrics(),
            collect_application_metrics(db, redis_client),
            collect_performance_metrics()
        )
        
        # Get active alerts
        active_alerts = metrics_store.get("alerts", [])
        
        # Get recent activity (mock data)
        recent_activity = [
            {
                "timestamp": datetime.utcnow() - timedelta(minutes=5),
                "event": "clip_completed",
                "description": "Clip processing completed successfully",
                "user_id": "user_123"
            },
            {
                "timestamp": datetime.utcnow() - timedelta(minutes=12),
                "event": "user_login",
                "description": "User logged in",
                "user_id": "user_456"
            }
        ]
        
        # Determine overall health status
        health_status = "healthy"
        if system_metrics.cpu_percent > 90 or system_metrics.memory_percent > 90:
            health_status = "degraded"
        if active_alerts:
            critical_alerts = [a for a in active_alerts if a.get("severity") == "critical"]
            if critical_alerts:
                health_status = "unhealthy"
        
        return DashboardData(
            system_metrics=system_metrics,
            application_metrics=app_metrics,
            performance_metrics=perf_metrics,
            active_alerts=active_alerts,
            recent_activity=recent_activity,
            health_status=health_status
        )
    except Exception as e:
        logger.error(f"Error collecting dashboard data: {e}")
        raise HTTPException(status_code=500, detail="Failed to collect dashboard data")


@router.get("/metrics/history", response_model=MetricsHistory)
async def get_metrics_history(
    metric_type: str = Query(..., description="Metric type (system, application, performance)"),
    timeframe: str = Query("24h", description="Time frame (1h, 24h, 7d, 30d)"),
    current_user: User = Depends(get_current_user)
):
    """Get historical metrics data.
    
    Returns historical metrics data for the specified timeframe,
    useful for trend analysis and capacity planning.
    """
    if metric_type not in ["system", "application", "performance"]:
        raise HTTPException(status_code=400, detail="Invalid metric type")
    
    if timeframe not in ["1h", "24h", "7d", "30d"]:
        raise HTTPException(status_code=400, detail="Invalid timeframe")
    
    # Mock historical data - implement based on your time-series storage
    data_points = []
    now = datetime.utcnow()
    
    # Generate sample data points
    if timeframe == "1h":
        for i in range(60):
            timestamp = now - timedelta(minutes=i)
            data_points.append({
                "timestamp": timestamp,
                "cpu_percent": 45 + (i % 20),
                "memory_percent": 60 + (i % 15),
                "clips_processing": 5 + (i % 10)
            })
    
    summary = {
        "avg_cpu": 55.2,
        "max_cpu": 78.5,
        "avg_memory": 67.8,
        "max_memory": 82.1,
        "total_clips_processed": 145
    }
    
    return MetricsHistory(
        timeframe=timeframe,
        data_points=data_points,
        summary=summary
    )


@router.get("/alerts", response_model=List[Alert])
async def get_active_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    current_user: User = Depends(get_current_user)
):
    """Get active monitoring alerts.
    
    Returns list of active alerts, optionally filtered by severity level.
    """
    alerts = metrics_store.get("alerts", [])
    
    if severity:
        alerts = [a for a in alerts if a.get("severity") == severity]
    
    return alerts


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user)
):
    """Acknowledge an active alert.
    
    Marks an alert as acknowledged to prevent further notifications.
    """
    alerts = metrics_store.get("alerts", [])
    
    for alert in alerts:
        if alert.get("id") == alert_id:
            alert["acknowledged"] = True
            alert["acknowledged_by"] = current_user.id
            alert["acknowledged_at"] = datetime.utcnow()
            return {"message": "Alert acknowledged successfully"}
    
    raise HTTPException(status_code=404, detail="Alert not found")


@router.get("/alerts/rules", response_model=List[AlertRule])
async def get_alert_rules(
    current_user: User = Depends(get_current_user)
):
    """Get monitoring alert rules.
    
    Returns list of configured alert rules for system monitoring.
    """
    return metrics_store.get("alert_rules", [])


@router.post("/alerts/rules", response_model=AlertRule)
async def create_alert_rule(
    rule: AlertRule,
    current_user: User = Depends(get_current_user)
):
    """Create a new alert rule.
    
    Creates a new monitoring alert rule with specified conditions.
    """
    # Validate operator
    valid_operators = [">", "<", ">=", "<=", "==", "!="]
    if rule.operator not in valid_operators:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid operator. Must be one of: {valid_operators}"
        )
    
    # Validate severity
    valid_severities = ["low", "medium", "high", "critical"]
    if rule.severity not in valid_severities:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid severity. Must be one of: {valid_severities}"
        )
    
    # Add to storage
    metrics_store.setdefault("alert_rules", []).append(rule.dict())
    
    return rule


@router.get("/stats/summary")
async def get_stats_summary(
    db: AsyncSession = Depends(get_db_pool),
    current_user: User = Depends(get_current_user)
):
    """Get high-level statistics summary.
    
    Returns key performance indicators and summary statistics
    for quick system overview.
    """
    try:
        # Quick stats queries
        stats = {}
        
        # Clips statistics
        clips_stats = await db.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
                COUNT(CASE WHEN created_at >= NOW() - INTERVAL '24 hours' THEN 1 END) as today
            FROM clips
        """))
        clips_row = clips_stats.fetchone()
        
        stats["clips"] = {
            "total": clips_row[0] if clips_row else 0,
            "completed": clips_row[1] if clips_row else 0,
            "processing": clips_row[2] if clips_row else 0,
            "failed": clips_row[3] if clips_row else 0,
            "today": clips_row[4] if clips_row else 0
        }
        
        # Users statistics
        users_stats = await db.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN created_at >= NOW() - INTERVAL '24 hours' THEN 1 END) as new_today,
                COUNT(CASE WHEN last_login >= NOW() - INTERVAL '24 hours' THEN 1 END) as active_today
            FROM users
        """))
        users_row = users_stats.fetchone()
        
        stats["users"] = {
            "total": users_row[0] if users_row else 0,
            "new_today": users_row[1] if users_row else 0,
            "active_today": users_row[2] if users_row else 0
        }
        
        # System health
        system_metrics = await collect_system_metrics()
        stats["system"] = {
            "cpu_percent": system_metrics.cpu_percent,
            "memory_percent": system_metrics.memory_percent,
            "disk_percent": system_metrics.disk_percent,
            "uptime_hours": system_metrics.uptime_seconds / 3600
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error collecting stats summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to collect statistics")


# Background task to collect metrics periodically
async def metrics_collector_task():
    """Background task to collect and store metrics."""
    while True:
        try:
            # This would run in the background to collect metrics
            # and store them in a time-series database
            await asyncio.sleep(60)  # Collect every minute
        except Exception as e:
            logger.error(f"Error in metrics collector: {e}")
            await asyncio.sleep(60)