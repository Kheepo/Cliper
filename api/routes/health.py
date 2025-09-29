"""Health check API endpoints for production monitoring.

This module provides:
- Liveness probe endpoint
- Readiness probe endpoint
- Startup probe endpoint
- Detailed health status endpoint
- Component-specific health checks
- System metrics endpoint
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from typing import Optional, List
import asyncio
from datetime import datetime, timedelta

from ..utils.health_checks import (
    get_health_manager,
    HealthStatus,
    SystemHealth,
    ComponentType
)
from ..utils.logging_config import get_logger

logger = get_logger('health_api')

router = APIRouter(prefix="/health", tags=["Health Checks"])


@router.get("/live", 
           summary="Liveness Probe",
           description="Check if the application is alive and running. Used by orchestrators like Kubernetes.")
async def liveness_probe():
    """Liveness probe endpoint.
    
    Returns 200 if the application is alive, 503 if it's not.
    This endpoint should be lightweight and fast.
    """
    try:
        # Simple check - if we can respond, we're alive
        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": "clip-generation-api"
        }
    except Exception as e:
        logger.error(f"Liveness probe failed: {e}")
        raise HTTPException(status_code=503, detail="Service not alive")


@router.get("/ready",
           summary="Readiness Probe", 
           description="Check if the application is ready to serve traffic. Includes dependency checks.")
async def readiness_probe():
    """Readiness probe endpoint.
    
    Returns 200 if the application is ready to serve traffic, 503 if not.
    This checks critical dependencies like database and cache.
    """
    try:
        manager = get_health_manager()
        health = await manager.check_all()
        
        # Consider ready if no components are unhealthy
        # Degraded components are acceptable for readiness
        if health.status == HealthStatus.UNHEALTHY:
            logger.warning(f"Readiness check failed: {health.summary}")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "reason": "Critical dependencies unhealthy",
                    "failed_components": health.summary.get('failed_components', [])
                }
            )
        
        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "health_status": health.status.value,
            "components_checked": health.summary.get('total_components', 0)
        }
    
    except Exception as e:
        logger.error(f"Readiness probe failed: {e}")
        raise HTTPException(status_code=503, detail="Readiness check failed")


@router.get("/startup",
           summary="Startup Probe",
           description="Check if the application has finished starting up. Used during application initialization.")
async def startup_probe():
    """Startup probe endpoint.
    
    Returns 200 if the application has finished starting up, 503 if still starting.
    This is more lenient than readiness and allows for longer initialization times.
    """
    try:
        manager = get_health_manager()
        
        # Check if we have any health checkers configured
        if not manager.checkers:
            return {
                "status": "starting",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "reason": "Health checkers not yet configured"
            }
        
        # Perform a quick health check
        health = await manager.check_all()
        
        # For startup, we're more lenient - only fail if critical components are down
        critical_failures = [
            component for component in health.components
            if component.status == HealthStatus.UNHEALTHY and 
            component.component_type in [ComponentType.DATABASE, ComponentType.FILESYSTEM]
        ]
        
        if critical_failures:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "starting",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "reason": "Critical components still initializing",
                    "critical_failures": [c.component for c in critical_failures]
                }
            )
        
        return {
            "status": "started",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "health_status": health.status.value,
            "components_checked": len(health.components)
        }
    
    except Exception as e:
        logger.error(f"Startup probe failed: {e}")
        raise HTTPException(status_code=503, detail="Startup check failed")


@router.get("/status",
           summary="Detailed Health Status",
           description="Get comprehensive health status of all system components.")
async def health_status(
    include_details: bool = Query(True, description="Include detailed component information"),
    component_filter: Optional[List[str]] = Query(None, description="Filter by component names")
):
    """Get detailed health status of all system components.
    
    Returns comprehensive health information including:
    - Overall system health status
    - Individual component health
    - Performance metrics
    - Error details
    """
    try:
        manager = get_health_manager()
        health = await manager.check_all()
        
        # Filter components if requested
        if component_filter:
            health.components = [
                component for component in health.components
                if component.component in component_filter
            ]
            # Recalculate summary for filtered components
            health.summary = manager._generate_summary(health.components)
            health.status = manager._determine_overall_status(health.components)
        
        response_data = health.to_dict()
        
        # Remove detailed component info if not requested
        if not include_details:
            for component in response_data['components']:
                component.pop('details', None)
                component.pop('error', None)
        
        return response_data
    
    except Exception as e:
        logger.error(f"Health status check failed: {e}")
        raise HTTPException(status_code=500, detail="Health status check failed")


@router.get("/components/{component_name}",
           summary="Component Health Status",
           description="Get health status of a specific component.")
async def component_health(component_name: str):
    """Get health status of a specific component."""
    try:
        manager = get_health_manager()
        
        # Find the specific checker
        checker = None
        for c in manager.checkers:
            if c.name == component_name:
                checker = c
                break
        
        if not checker:
            raise HTTPException(
                status_code=404, 
                detail=f"Component '{component_name}' not found"
            )
        
        # Perform health check for this component
        result = await checker.check()
        
        return result.to_dict()
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Component health check failed for {component_name}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Component health check failed: {str(e)}"
        )


@router.get("/metrics",
           summary="System Metrics",
           description="Get system performance and health metrics.")
async def system_metrics():
    """Get system performance and health metrics."""
    try:
        manager = get_health_manager()
        
        # Get current health status
        health = await manager.check_all()
        
        # Calculate additional metrics
        current_time = datetime.utcnow()
        
        # Component response times
        response_times = {
            component.component: component.response_time_ms
            for component in health.components
        }
        
        # Health check history (if available)
        last_results = manager.get_last_results()
        uptime_info = {
            "last_check": health.timestamp.isoformat() + "Z",
            "check_interval_seconds": manager.check_interval,
            "background_checks_running": manager.running
        }
        
        # Circuit breaker stats (if available)
        circuit_breaker_stats = {}
        for checker in manager.checkers:
            if hasattr(checker, 'circuit_breaker'):
                cb = checker.circuit_breaker
                circuit_breaker_stats[checker.name] = {
                    "state": cb.state.value,
                    "failure_count": cb.failure_count,
                    "success_count": cb.success_count,
                    "last_failure_time": cb.last_failure_time.isoformat() + "Z" if cb.last_failure_time else None
                }
        
        return {
            "timestamp": current_time.isoformat() + "Z",
            "overall_health": health.status.value,
            "component_count": len(health.components),
            "response_times_ms": response_times,
            "average_response_time_ms": health.summary.get('avg_response_time_ms', 0),
            "status_distribution": health.summary.get('status_counts', {}),
            "uptime_info": uptime_info,
            "circuit_breaker_stats": circuit_breaker_stats,
            "failed_components": health.summary.get('failed_components', []),
            "degraded_components": health.summary.get('degraded_components', [])
        }
    
    except Exception as e:
        logger.error(f"System metrics collection failed: {e}")
        raise HTTPException(status_code=500, detail="Metrics collection failed")


@router.get("/history",
           summary="Health Check History",
           description="Get historical health check results.")
async def health_history(
    hours: int = Query(24, ge=1, le=168, description="Hours of history to retrieve (max 7 days)")
):
    """Get historical health check results.
    
    Note: This is a basic implementation. In production, you would typically
    store health check results in a time-series database for proper historical tracking.
    """
    try:
        manager = get_health_manager()
        
        # For now, just return the last known results
        # In production, implement proper historical storage
        last_results = manager.get_last_results()
        
        if not last_results:
            return {
                "message": "No historical data available",
                "note": "Historical tracking requires persistent storage implementation"
            }
        
        return {
            "requested_hours": hours,
            "available_data": "last_check_only",
            "last_check": last_results.to_dict(),
            "note": "Full historical tracking requires time-series database integration"
        }
    
    except Exception as e:
        logger.error(f"Health history retrieval failed: {e}")
        raise HTTPException(status_code=500, detail="Health history retrieval failed")


@router.post("/check",
            summary="Trigger Health Check",
            description="Manually trigger a health check of all components.")
async def trigger_health_check():
    """Manually trigger a health check of all components."""
    try:
        manager = get_health_manager()
        health = await manager.check_all()
        
        return {
            "message": "Health check completed",
            "triggered_at": datetime.utcnow().isoformat() + "Z",
            "result": health.to_dict()
        }
    
    except Exception as e:
        logger.error(f"Manual health check failed: {e}")
        raise HTTPException(status_code=500, detail="Manual health check failed")


@router.get("/checkers",
           summary="List Health Checkers",
           description="Get list of configured health checkers.")
async def list_health_checkers():
    """Get list of configured health checkers."""
    try:
        manager = get_health_manager()
        
        checkers_info = []
        for checker in manager.checkers:
            checker_info = {
                "name": checker.name,
                "component_type": checker.component_type.value,
                "timeout": checker.timeout
            }
            
            # Add circuit breaker info if available
            if hasattr(checker, 'circuit_breaker'):
                cb = checker.circuit_breaker
                checker_info["circuit_breaker"] = {
                    "state": cb.state.value,
                    "failure_threshold": cb.config.failure_threshold,
                    "recovery_timeout": cb.config.recovery_timeout
                }
            
            checkers_info.append(checker_info)
        
        return {
            "total_checkers": len(checkers_info),
            "checkers": checkers_info,
            "background_checks_enabled": manager.running,
            "check_interval_seconds": manager.check_interval
        }
    
    except Exception as e:
        logger.error(f"Failed to list health checkers: {e}")
        raise HTTPException(status_code=500, detail="Failed to list health checkers")