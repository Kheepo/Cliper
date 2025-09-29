"""Comprehensive health check system for the Cliper application."""

import asyncio
import time
import psutil
import aioredis
import asyncpg
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

import aiohttp
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from ..core.config import settings
# from ..core.database import get_db_pool  # Disabled for Firebase migration
from .metrics import metrics_collector

class HealthStatus(Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

@dataclass
class HealthCheckResult:
    """Health check result."""
    name: str
    status: HealthStatus
    message: str
    duration_ms: float
    timestamp: datetime
    details: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp.isoformat(),
            "details": self.details or {}
        }

class HealthCheck:
    """Base health check class."""
    
    def __init__(self, name: str, timeout: float = 5.0):
        self.name = name
        self.timeout = timeout
    
    async def check(self) -> HealthCheckResult:
        """Perform health check."""
        start_time = time.time()
        timestamp = datetime.utcnow()
        
        try:
            # Run the actual check with timeout
            result = await asyncio.wait_for(
                self._perform_check(),
                timeout=self.timeout
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                name=self.name,
                status=result.get("status", HealthStatus.UNKNOWN),
                message=result.get("message", "Check completed"),
                duration_ms=duration_ms,
                timestamp=timestamp,
                details=result.get("details", {})
            )
            
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check timed out after {self.timeout}s",
                duration_ms=duration_ms,
                timestamp=timestamp
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                duration_ms=duration_ms,
                timestamp=timestamp
            )
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Override this method to implement the actual check."""
        raise NotImplementedError

class DatabaseHealthCheck(HealthCheck):
    """Database connectivity health check."""
    
    def __init__(self, timeout: float = 5.0):
        super().__init__("database", timeout)
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Check database connectivity and performance."""
        try:
            pool = await get_db_pool()
            
            # Test basic connectivity
            async with pool.acquire() as conn:
                # Simple query to test connectivity
                result = await conn.fetchval("SELECT 1")
                
                if result != 1:
                    return {
                        "status": HealthStatus.UNHEALTHY,
                        "message": "Database query returned unexpected result"
                    }
                
                # Check connection pool status
                pool_size = pool.get_size()
                pool_free = pool.get_idle_size()
                pool_used = pool_size - pool_free
                
                # Get database stats
                stats_query = """
                SELECT 
                    count(*) as active_connections,
                    (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') as active_queries
                FROM pg_stat_activity
                """
                
                stats = await conn.fetchrow(stats_query)
                
                details = {
                    "pool_size": pool_size,
                    "pool_used": pool_used,
                    "pool_free": pool_free,
                    "active_connections": stats["active_connections"],
                    "active_queries": stats["active_queries"]
                }
                
                # Determine status based on pool usage
                pool_usage_percent = (pool_used / pool_size) * 100 if pool_size > 0 else 0
                
                if pool_usage_percent > 90:
                    status = HealthStatus.DEGRADED
                    message = f"Database pool usage high: {pool_usage_percent:.1f}%"
                elif pool_usage_percent > 95:
                    status = HealthStatus.UNHEALTHY
                    message = f"Database pool usage critical: {pool_usage_percent:.1f}%"
                else:
                    status = HealthStatus.HEALTHY
                    message = "Database is healthy"
                
                return {
                    "status": status,
                    "message": message,
                    "details": details
                }
                
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"Database connection failed: {str(e)}"
            }

class RedisHealthCheck(HealthCheck):
    """Redis connectivity health check."""
    
    def __init__(self, timeout: float = 5.0):
        super().__init__("redis", timeout)
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Check Redis connectivity and performance."""
        try:
            redis = aioredis.from_url(settings.REDIS_URL)
            
            # Test basic connectivity
            pong = await redis.ping()
            if not pong:
                return {
                    "status": HealthStatus.UNHEALTHY,
                    "message": "Redis ping failed"
                }
            
            # Get Redis info
            info = await redis.info()
            
            # Test read/write operations
            test_key = "health_check_test"
            test_value = str(time.time())
            
            await redis.set(test_key, test_value, ex=60)
            retrieved_value = await redis.get(test_key)
            
            if retrieved_value.decode() != test_value:
                return {
                    "status": HealthStatus.UNHEALTHY,
                    "message": "Redis read/write test failed"
                }
            
            # Clean up test key
            await redis.delete(test_key)
            
            # Analyze Redis health
            memory_usage = info.get('used_memory', 0)
            max_memory = info.get('maxmemory', 0)
            connected_clients = info.get('connected_clients', 0)
            
            details = {
                "version": info.get('redis_version', 'unknown'),
                "uptime_seconds": info.get('uptime_in_seconds', 0),
                "connected_clients": connected_clients,
                "used_memory_mb": round(memory_usage / 1024 / 1024, 2),
                "memory_fragmentation_ratio": info.get('mem_fragmentation_ratio', 0),
                "keyspace_hits": info.get('keyspace_hits', 0),
                "keyspace_misses": info.get('keyspace_misses', 0)
            }
            
            if max_memory > 0:
                memory_usage_percent = (memory_usage / max_memory) * 100
                details["memory_usage_percent"] = round(memory_usage_percent, 2)
                
                if memory_usage_percent > 90:
                    status = HealthStatus.DEGRADED
                    message = f"Redis memory usage high: {memory_usage_percent:.1f}%"
                elif memory_usage_percent > 95:
                    status = HealthStatus.UNHEALTHY
                    message = f"Redis memory usage critical: {memory_usage_percent:.1f}%"
                else:
                    status = HealthStatus.HEALTHY
                    message = "Redis is healthy"
            else:
                status = HealthStatus.HEALTHY
                message = "Redis is healthy"
            
            await redis.close()
            
            return {
                "status": status,
                "message": message,
                "details": details
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"Redis connection failed: {str(e)}"
            }

class SystemHealthCheck(HealthCheck):
    """System resources health check."""
    
    def __init__(self, timeout: float = 5.0):
        super().__init__("system", timeout)
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Check system resources."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # Load average (Unix-like systems)
            try:
                load_avg = psutil.getloadavg()
                load_avg_1min = load_avg[0]
            except (AttributeError, OSError):
                load_avg_1min = None
            
            # Network I/O
            net_io = psutil.net_io_counters()
            
            details = {
                "cpu_percent": round(cpu_percent, 2),
                "memory_percent": round(memory_percent, 2),
                "memory_available_gb": round(memory.available / 1024 / 1024 / 1024, 2),
                "disk_percent": round(disk_percent, 2),
                "disk_free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "network_bytes_sent": net_io.bytes_sent,
                "network_bytes_recv": net_io.bytes_recv
            }
            
            if load_avg_1min is not None:
                details["load_avg_1min"] = round(load_avg_1min, 2)
            
            # Determine overall system health
            issues = []
            
            if cpu_percent > 90:
                issues.append(f"High CPU usage: {cpu_percent:.1f}%")
            elif cpu_percent > 80:
                issues.append(f"Elevated CPU usage: {cpu_percent:.1f}%")
            
            if memory_percent > 90:
                issues.append(f"High memory usage: {memory_percent:.1f}%")
            elif memory_percent > 80:
                issues.append(f"Elevated memory usage: {memory_percent:.1f}%")
            
            if disk_percent > 90:
                issues.append(f"Low disk space: {disk_percent:.1f}% used")
            elif disk_percent > 80:
                issues.append(f"Disk space warning: {disk_percent:.1f}% used")
            
            if load_avg_1min is not None and load_avg_1min > psutil.cpu_count() * 2:
                issues.append(f"High load average: {load_avg_1min:.2f}")
            
            if len(issues) == 0:
                status = HealthStatus.HEALTHY
                message = "System resources are healthy"
            elif any("High" in issue for issue in issues):
                status = HealthStatus.UNHEALTHY
                message = f"System issues: {', '.join(issues)}"
            else:
                status = HealthStatus.DEGRADED
                message = f"System warnings: {', '.join(issues)}"
            
            return {
                "status": status,
                "message": message,
                "details": details
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"System check failed: {str(e)}"
            }

class ExternalServiceHealthCheck(HealthCheck):
    """External service health check."""
    
    def __init__(self, name: str, url: str, timeout: float = 10.0, 
                 expected_status: int = 200, headers: Dict[str, str] = None):
        super().__init__(f"external_{name}", timeout)
        self.url = url
        self.expected_status = expected_status
        self.headers = headers or {}
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Check external service availability."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.url, 
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    
                    details = {
                        "url": self.url,
                        "status_code": response.status,
                        "expected_status": self.expected_status,
                        "response_headers": dict(response.headers)
                    }
                    
                    if response.status == self.expected_status:
                        status = HealthStatus.HEALTHY
                        message = f"External service is healthy (HTTP {response.status})"
                    else:
                        status = HealthStatus.UNHEALTHY
                        message = f"External service returned HTTP {response.status}, expected {self.expected_status}"
                    
                    return {
                        "status": status,
                        "message": message,
                        "details": details
                    }
                    
        except asyncio.TimeoutError:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"External service timeout after {self.timeout}s"
            }
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"External service check failed: {str(e)}"
            }

class CeleryHealthCheck(HealthCheck):
    """Celery task queue health check."""
    
    def __init__(self, timeout: float = 5.0):
        super().__init__("celery", timeout)
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Check Celery worker status and connectivity."""
        try:
            from api.celery_app import celery_app
            
            # Check if Celery is available
            inspect = celery_app.control.inspect()
            
            # Get worker stats
            stats = inspect.stats()
            active_tasks = inspect.active()
            scheduled_tasks = inspect.scheduled()
            
            if not stats:
                return {
                    "status": HealthStatus.DEGRADED,
                    "message": "No Celery workers available",
                    "workers": 0,
                    "active_tasks": 0,
                    "scheduled_tasks": 0
                }
            
            worker_count = len(stats)
            total_active = sum(len(tasks) for tasks in active_tasks.values()) if active_tasks else 0
            total_scheduled = sum(len(tasks) for tasks in scheduled_tasks.values()) if scheduled_tasks else 0
            
            return {
                "status": HealthStatus.HEALTHY,
                "message": f"{worker_count} worker(s) available",
                "workers": worker_count,
                "active_tasks": total_active,
                "scheduled_tasks": total_scheduled,
                "worker_stats": stats
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"Celery check failed: {str(e)}",
                "workers": 0,
                "active_tasks": 0,
                "scheduled_tasks": 0,
                "error": str(e)
            }


class ApplicationHealthCheck(HealthCheck):
    """Application-specific health check."""
    
    def __init__(self, timeout: float = 5.0):
        super().__init__("application", timeout)
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Check application-specific health indicators."""
        try:
            # Check if critical services are running
            issues = []
            details = {}
            
            # Check video processing queue
            try:
                redis = aioredis.from_url(settings.REDIS_URL)
                queue_size = await redis.llen('video_processing_queue')
                details["video_queue_size"] = queue_size
                
                if queue_size > 1000:
                    issues.append(f"Video queue backed up: {queue_size} items")
                
                await redis.close()
            except Exception as e:
                issues.append(f"Cannot check video queue: {str(e)}")
            
            # Check recent error rates
            try:
                # This would integrate with your metrics system
                error_rate = 0.0  # Placeholder
                details["error_rate_5min"] = error_rate
                
                if error_rate > 0.1:  # 10% error rate
                    issues.append(f"High error rate: {error_rate:.1%}")
            except Exception as e:
                issues.append(f"Cannot check error rate: {str(e)}")
            
            # Check disk space for uploads
            try:
                upload_disk = psutil.disk_usage(settings.UPLOAD_DIR)
                upload_disk_percent = (upload_disk.used / upload_disk.total) * 100
                details["upload_disk_percent"] = round(upload_disk_percent, 2)
                
                if upload_disk_percent > 90:
                    issues.append(f"Upload disk space low: {upload_disk_percent:.1f}%")
            except Exception as e:
                issues.append(f"Cannot check upload disk: {str(e)}")
            
            # Determine status
            if len(issues) == 0:
                status = HealthStatus.HEALTHY
                message = "Application is healthy"
            elif any("backed up" in issue or "low" in issue for issue in issues):
                status = HealthStatus.DEGRADED
                message = f"Application warnings: {', '.join(issues)}"
            else:
                status = HealthStatus.UNHEALTHY
                message = f"Application issues: {', '.join(issues)}"
            
            return {
                "status": status,
                "message": message,
                "details": details
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"Application check failed: {str(e)}"
            }

class SupabaseHealthCheck(HealthCheck):
    """Supabase connectivity health check."""
    
    def __init__(self, timeout: float = 5.0):
        super().__init__("supabase", timeout)
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Check Supabase connectivity."""
        try:
            from api.services.supabase_service import SupabaseService
            
            supabase_service = SupabaseService()
            
            # Check if Supabase service is available
            if not supabase_service.supabase_available:
                return {
                    "status": HealthStatus.DEGRADED,
                    "message": "Supabase service not available (fallback mode)"
                }
            
            # Test Supabase connection with a simple query
            client = supabase_service.client
            if client is None:
                return {
                    "status": HealthStatus.DEGRADED,
                    "message": "Supabase client not initialized (fallback mode)"
                }
            
            # Simple test - try to access a table (lightweight operation)
            # This will fail if Supabase is not accessible
            result = client.table('users').select('id').limit(1).execute()
            
            return {
                "status": HealthStatus.HEALTHY,
                "message": "Supabase is healthy"
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.DEGRADED,
                "message": f"Supabase not available: {str(e)}"
            }

class HealthCheckManager:
    """Manages all health checks."""
    
    def __init__(self):
        self.checks: List[HealthCheck] = []
        self.last_results: Dict[str, HealthCheckResult] = {}
        self.check_history: List[Dict[str, Any]] = []
        
        # Initialize default checks
        self._initialize_default_checks()
    
    def _initialize_default_checks(self):
        """Initialize default health checks."""
        # self.add_check(DatabaseHealthCheck())  # Commented out for Firebase migration
        self.add_check(RedisHealthCheck())
        self.add_check(CeleryHealthCheck())
        self.add_check(SystemHealthCheck())
        self.add_check(ApplicationHealthCheck())
        self.add_check(SupabaseHealthCheck())
        
        # Add external service checks if configured
        if hasattr(settings, 'EXTERNAL_SERVICES'):
            for service_name, service_config in settings.EXTERNAL_SERVICES.items():
                self.add_check(ExternalServiceHealthCheck(
                    name=service_name,
                    url=service_config['url'],
                    timeout=service_config.get('timeout', 10.0),
                    expected_status=service_config.get('expected_status', 200),
                    headers=service_config.get('headers', {})
                ))
    
    def add_check(self, check: HealthCheck):
        """Add a health check."""
        self.checks.append(check)
    
    async def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks."""
        start_time = time.time()
        timestamp = datetime.utcnow()
        
        # Run all checks concurrently
        tasks = [check.check() for check in self.checks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        check_results = {}
        overall_status = HealthStatus.HEALTHY
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Handle exceptions
                check_name = self.checks[i].name
                result = HealthCheckResult(
                    name=check_name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check failed with exception: {str(result)}",
                    duration_ms=0,
                    timestamp=timestamp
                )
            
            check_results[result.name] = result.to_dict()
            self.last_results[result.name] = result
            
            # Update overall status
            if result.status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
            elif result.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                overall_status = HealthStatus.DEGRADED
        
        total_duration = (time.time() - start_time) * 1000
        
        # Create summary
        summary = {
            "status": overall_status.value,
            "timestamp": timestamp.isoformat(),
            "duration_ms": round(total_duration, 2),
            "checks": check_results,
            "summary": {
                "total_checks": len(self.checks),
                "healthy": sum(1 for r in check_results.values() if r["status"] == "healthy"),
                "degraded": sum(1 for r in check_results.values() if r["status"] == "degraded"),
                "unhealthy": sum(1 for r in check_results.values() if r["status"] == "unhealthy")
            }
        }
        
        # Store in history
        self.check_history.append({
            "timestamp": timestamp.isoformat(),
            "overall_status": overall_status.value,
            "duration_ms": total_duration,
            "check_count": len(self.checks)
        })
        
        # Keep only last 100 entries
        if len(self.check_history) > 100:
            self.check_history = self.check_history[-100:]
        
        return summary
    
    async def run_check(self, check_name: str) -> Optional[HealthCheckResult]:
        """Run a specific health check."""
        for check in self.checks:
            if check.name == check_name:
                result = await check.check()
                self.last_results[check_name] = result
                return result
        return None
    
    def get_check_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get health check history."""
        return self.check_history[-limit:]
    
    def get_last_results(self) -> Dict[str, Dict[str, Any]]:
        """Get last results for all checks."""
        return {name: result.to_dict() for name, result in self.last_results.items()}

# Global health check manager
health_manager = HealthCheckManager()

class SystemMetrics:
    """System metrics collection for health monitoring."""
    
    @staticmethod
    def get_cpu_usage() -> float:
        """Get current CPU usage percentage."""
        return psutil.cpu_percent(interval=1)
    
    @staticmethod
    def get_memory_usage() -> Dict[str, Any]:
        """Get current memory usage information."""
        memory = psutil.virtual_memory()
        return {
            "total": memory.total,
            "available": memory.available,
            "used": memory.used,
            "percentage": memory.percent
        }
    
    @staticmethod
    def get_disk_usage() -> Dict[str, Any]:
        """Get current disk usage information."""
        disk = psutil.disk_usage('/')
        return {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percentage": (disk.used / disk.total) * 100
        }
    
    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """Get comprehensive system information."""
        return {
            "cpu_usage": SystemMetrics.get_cpu_usage(),
            "memory": SystemMetrics.get_memory_usage(),
            "disk": SystemMetrics.get_disk_usage(),
            "timestamp": datetime.utcnow().isoformat()
        }

# Alias for backward compatibility
HealthChecker = HealthCheckManager

# FastAPI router for health endpoints
router = APIRouter(prefix="/health", tags=["health"])

@router.get("/")
async def health_check():
    """Comprehensive health check endpoint."""
    try:
        results = await health_manager.run_all_checks()
        
        # Return appropriate HTTP status based on health
        if results["status"] == "healthy":
            return JSONResponse(content=results, status_code=200)
        elif results["status"] == "degraded":
            return JSONResponse(content=results, status_code=200)  # Still OK but with warnings
        else:
            return JSONResponse(content=results, status_code=503)  # Service Unavailable
            
    except Exception as e:
        error_response = {
            "status": "unhealthy",
            "message": f"Health check failed: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }
        return JSONResponse(content=error_response, status_code=503)

@router.get("/live")
async def liveness_probe():
    """Kubernetes liveness probe - basic application availability."""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}

@router.get("/ready")
async def readiness_probe():
    """Kubernetes readiness probe - check if app is ready to serve traffic."""
    try:
        # Check critical dependencies only
        redis_check = RedisHealthCheck(timeout=2.0)
        firestore_check = FirestoreHealthCheck(timeout=2.0)
        
        redis_result = await redis_check.check()
        firestore_result = await firestore_check.check()
        
        # Consider degraded Firestore as acceptable for readiness (fallback mode)
        firestore_ready = firestore_result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
        
        if (redis_result.status == HealthStatus.HEALTHY and firestore_ready):
            return JSONResponse(
                content={
                    "status": "ready",
                    "timestamp": datetime.utcnow().isoformat(),
                    "checks": {
                        "redis": redis_result.to_dict(),
                        "firestore": firestore_result.to_dict()
                    }
                },
                status_code=200
            )
        else:
            return JSONResponse(
                content={
                    "status": "not_ready",
                    "timestamp": datetime.utcnow().isoformat(),
                    "checks": {
                        "redis": redis_result.to_dict(),
                        "firestore": firestore_result.to_dict()
                    }
                },
                status_code=503
            )
            
    except Exception as e:
        return JSONResponse(
            content={
                "status": "not_ready",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            },
            status_code=503
        )

@router.get("/check/{check_name}")
async def individual_health_check(check_name: str):
    """Run individual health check."""
    result = await health_manager.run_check(check_name)
    
    if result is None:
        raise HTTPException(status_code=404, detail=f"Health check '{check_name}' not found")
    
    status_code = 200 if result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED] else 503
    return JSONResponse(content=result.to_dict(), status_code=status_code)

@router.get("/history")
async def health_check_history(limit: int = 50):
    """Get health check history."""
    history = health_manager.get_check_history(limit)
    return {"history": history}

@router.get("/summary")
async def health_summary():
    """Get health check summary."""
    last_results = health_manager.get_last_results()
    
    if not last_results:
        return {"message": "No health checks have been run yet"}
    
    # Calculate summary statistics
    total_checks = len(last_results)
    healthy_count = sum(1 for r in last_results.values() if r["status"] == "healthy")
    degraded_count = sum(1 for r in last_results.values() if r["status"] == "degraded")
    unhealthy_count = sum(1 for r in last_results.values() if r["status"] == "unhealthy")
    
    # Determine overall status
    if unhealthy_count > 0:
        overall_status = "unhealthy"
    elif degraded_count > 0:
        overall_status = "degraded"
    else:
        overall_status = "healthy"
    
    return {
        "overall_status": overall_status,
        "total_checks": total_checks,
        "healthy": healthy_count,
        "degraded": degraded_count,
        "unhealthy": unhealthy_count,
        "last_check_time": max(
            (r["timestamp"] for r in last_results.values()),
            default=None
        ),
        "checks": last_results
    }

# Background task for periodic health checks
async def periodic_health_check_task():
    """Background task to run periodic health checks."""
    while True:
        try:
            await health_manager.run_all_checks()
        except Exception as e:
            print(f"Error in periodic health check: {e}")
        
        # Wait 60 seconds between checks
        await asyncio.sleep(60)