from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
import asyncio
import time
from datetime import datetime, timedelta
import logging
from .health import health_manager, HealthStatus
from .service_discovery import (
    service_registry, load_balancer, ServiceStatus, ServiceType,
    ServiceInfo, initialize_service_discovery, ServiceDiscoveryConfig
)
from ..versioning.models import HealthCheck, SystemMetrics
from ..core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])

# Health check cache
health_cache: Dict[str, Any] = {}
health_cache_ttl = 30  # seconds
last_health_check = 0

async def get_service_registry_dependency():
    """Dependency to get service registry."""
    if not service_registry:
        await initialize_service_discovery()
    return service_registry

@router.get("/", summary="Basic Health Check")
async def basic_health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "cliper-api",
        "version": "1.0.0"
    }

@router.get("/detailed", summary="Detailed Health Check")
async def detailed_health_check(
    background_tasks: BackgroundTasks,
    registry = Depends(get_service_registry_dependency)
):
    """Detailed health check with all system components."""
    global health_cache, last_health_check
    
    current_time = time.time()
    
    # Use cache if available and not expired
    if health_cache and (current_time - last_health_check) < health_cache_ttl:
        return health_cache
    
    try:
        # Run all health checks
        health_results = await health_manager.run_all_checks()
        
        # Get service discovery info
        services = await registry.discover_services() if registry else []
        healthy_services = [s for s in services if s.status == ServiceStatus.HEALTHY]
        
        # Prepare response
        response = {
            "overall_status": health_results["status"],
            "timestamp": datetime.utcnow().isoformat(),
            "service_info": {
                "name": "cliper-api",
                "version": "1.0.0",
                "uptime_seconds": time.time() - getattr(detailed_health_check, 'start_time', time.time())
            },
            "health_checks": health_results["checks"],
            "system_metrics": health_results.get("system_metrics", {}),
            "metrics_summary": health_results.get("metrics_summary", {}),
            "service_discovery": {
                "total_services": len(services),
                "healthy_services": len(healthy_services),
                "services_by_type": {}
            }
        }
        
        # Group services by type
        for service in services:
            service_type = service.type.value
            if service_type not in response["service_discovery"]["services_by_type"]:
                response["service_discovery"]["services_by_type"][service_type] = {
                    "total": 0,
                    "healthy": 0
                }
            
            response["service_discovery"]["services_by_type"][service_type]["total"] += 1
            if service.status == ServiceStatus.HEALTHY:
                response["service_discovery"]["services_by_type"][service_type]["healthy"] += 1
        
        # Cache the result
        health_cache = response
        last_health_check = current_time
        
        # Update service status in background
        if registry and hasattr(registry, '_local_service') and registry._local_service:
            background_tasks.add_task(
                update_local_service_status,
                registry,
                health_results["status"]
            )
        
        return response
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "overall_status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
        )

@router.get("/live", summary="Liveness Probe")
async def liveness_probe():
    """Kubernetes liveness probe endpoint."""
    try:
        # Basic application liveness check
        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Liveness probe failed: {e}")
        raise HTTPException(status_code=503, detail="Service not alive")

@router.get("/ready", summary="Readiness Probe")
async def readiness_probe(
    registry = Depends(get_service_registry_dependency)
):
    """Kubernetes readiness probe endpoint."""
    try:
        # Check critical dependencies
        redis_health = await health_manager.run_check("redis")
        
        if redis_health.status != HealthStatus.HEALTHY:
            raise HTTPException(
                status_code=503,
                detail=f"Redis not ready: {redis_health.message}"
            )
        
        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat(),
            "dependencies": {
                "redis": "healthy"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Readiness probe failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")

@router.get("/startup", summary="Startup Probe")
async def startup_probe():
    """Kubernetes startup probe endpoint."""
    try:
        # Check if application has fully started
        # This could include database migrations, cache warming, etc.
        return {
            "status": "started",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Startup probe failed: {e}")
        raise HTTPException(status_code=503, detail="Service not started")

@router.get("/services", summary="Service Discovery Status")
async def service_discovery_status(
    service_type: Optional[str] = None,
    status: Optional[str] = None,
    registry = Depends(get_service_registry_dependency)
):
    """Get service discovery status and registered services."""
    try:
        if not registry:
            return {
                "status": "disabled",
                "message": "Service discovery not initialized"
            }
        
        # Parse filters
        type_filter = ServiceType(service_type) if service_type else None
        status_filter = ServiceStatus(status) if status else None
        
        # Discover services
        services = await registry.discover_services(
            service_type=type_filter,
            status=status_filter
        )
        
        # Prepare response
        response = {
            "status": "active",
            "timestamp": datetime.utcnow().isoformat(),
            "total_services": len(services),
            "services": []
        }
        
        for service in services:
            service_data = {
                "id": service.id,
                "name": service.name,
                "type": service.type.value,
                "host": service.host,
                "port": service.port,
                "status": service.status.value,
                "version": service.version,
                "last_heartbeat": service.last_heartbeat.isoformat() if service.last_heartbeat else None,
                "registered_at": service.registered_at.isoformat() if service.registered_at else None,
                "tags": service.tags,
                "health_check_url": service.health_check_url
            }
            response["services"].append(service_data)
        
        return response
        
    except Exception as e:
        logger.error(f"Service discovery status failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/services/{service_name}/endpoints", summary="Get Service Endpoints")
async def get_service_endpoints(
    service_name: str,
    registry = Depends(get_service_registry_dependency)
):
    """Get all healthy endpoints for a specific service."""
    try:
        if not registry:
            raise HTTPException(status_code=503, detail="Service discovery not available")
        
        endpoints = await registry.get_service_endpoints(service_name)
        
        return {
            "service_name": service_name,
            "endpoints": endpoints,
            "count": len(endpoints),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get service endpoints for {service_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/services/{service_name}/load-balance", summary="Load Balance Service")
async def load_balance_service(
    service_name: str,
    strategy: str = "round_robin",
    registry = Depends(get_service_registry_dependency)
):
    """Get load-balanced endpoint for a service."""
    try:
        if not load_balancer:
            raise HTTPException(status_code=503, detail="Load balancer not available")
        
        endpoint = await load_balancer.get_service_endpoint(service_name, strategy)
        
        if not endpoint:
            raise HTTPException(
                status_code=404,
                detail=f"No healthy instances found for service: {service_name}"
            )
        
        return {
            "service_name": service_name,
            "endpoint": endpoint,
            "strategy": strategy,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Load balancing failed for {service_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/services/register", summary="Register Service")
async def register_service(
    service_data: Dict[str, Any],
    registry = Depends(get_service_registry_dependency)
):
    """Register a new service."""
    try:
        if not registry:
            raise HTTPException(status_code=503, detail="Service registry not available")
        
        # Validate required fields
        required_fields = ['name', 'type', 'host', 'port', 'version']
        for field in required_fields:
            if field not in service_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Create service info
        service = ServiceInfo(
            id=f"{service_data['name']}_{service_data['host']}_{service_data['port']}_{int(time.time())}",
            name=service_data['name'],
            type=ServiceType(service_data['type']),
            host=service_data['host'],
            port=service_data['port'],
            status=ServiceStatus.HEALTHY,
            version=service_data['version'],
            metadata=service_data.get('metadata', {}),
            health_check_url=service_data.get('health_check_url'),
            tags=service_data.get('tags', []),
            dependencies=service_data.get('dependencies', [])
        )
        
        # Register service
        success = await registry.register_service(service)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to register service")
        
        return {
            "status": "registered",
            "service_id": service.id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Service registration failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/services/{service_id}", summary="Deregister Service")
async def deregister_service(
    service_id: str,
    registry = Depends(get_service_registry_dependency)
):
    """Deregister a service."""
    try:
        if not registry:
            raise HTTPException(status_code=503, detail="Service registry not available")
        
        success = await registry.deregister_service(service_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Service not found")
        
        return {
            "status": "deregistered",
            "service_id": service_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Service deregistration failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/services/{service_id}/heartbeat", summary="Service Heartbeat")
async def service_heartbeat(
    service_id: str,
    registry = Depends(get_service_registry_dependency)
):
    """Send heartbeat for a service."""
    try:
        if not registry:
            raise HTTPException(status_code=503, detail="Service registry not available")
        
        success = await registry.heartbeat(service_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Service not found")
        
        return {
            "status": "heartbeat_received",
            "service_id": service_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Service heartbeat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dependencies", summary="Service Dependencies")
async def service_dependencies(
    registry = Depends(get_service_registry_dependency)
):
    """Get service dependency graph."""
    try:
        if not registry:
            raise HTTPException(status_code=503, detail="Service registry not available")
        
        services = await registry.discover_services()
        
        # Build dependency graph
        dependency_graph = {}
        for service in services:
            dependency_graph[service.name] = {
                "id": service.id,
                "status": service.status.value,
                "dependencies": service.dependencies or [],
                "dependents": []
            }
        
        # Find dependents
        for service in services:
            if service.dependencies:
                for dep in service.dependencies:
                    if dep in dependency_graph:
                        dependency_graph[dep]["dependents"].append(service.name)
        
        return {
            "dependency_graph": dependency_graph,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get service dependencies: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def update_local_service_status(registry, overall_status: str):
    """Update local service status based on health check."""
    try:
        if overall_status == "healthy":
            status = ServiceStatus.HEALTHY
        elif overall_status == "degraded":
            status = ServiceStatus.HEALTHY  # Still consider as healthy but with warnings
        else:
            status = ServiceStatus.UNHEALTHY
        
        if registry._local_service:
            await registry.update_service_status(registry._local_service.id, status)
            
    except Exception as e:
        logger.error(f"Failed to update local service status: {e}")

# Initialize startup time
detailed_health_check.start_time = time.time()