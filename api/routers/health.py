from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from datetime import datetime
import psutil
import os

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ..utils.supabase_client import get_supabase_client, verify_supabase_connection as test_connection

router = APIRouter(tags=["health"])

# Pydantic models
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    uptime: float
    
class DetailedHealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    uptime: float
    database: dict
    system: dict
    services: dict

class DatabaseHealthResponse(BaseModel):
    status: str
    connection_pool: dict
    query_performance: dict
    
# Global start time for uptime calculation
start_time = datetime.utcnow()

@router.get("/", response_model=HealthResponse)
async def health_check():
    """Basic health check endpoint"""
    try:
        uptime = (datetime.utcnow() - start_time).total_seconds()
        
        return HealthResponse(
            status="healthy",
            timestamp=datetime.utcnow().isoformat(),
            version="1.0.0",
            uptime=uptime
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {str(e)}"
        )

@router.get("/simple")
async def simple_health_check():
    """Simple health check without database dependency"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Server is running"
    }

@router.get("/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check():
    """Detailed health check with system and database information"""
    try:
        uptime = (datetime.utcnow() - start_time).total_seconds()
        
        # Database health
        db_connected = test_connection()
        db_health = {
            "status": "connected" if db_connected else "disconnected",
            "type": "supabase"
        }
        
        # System information
        system_info = {
            "cpu_usage": psutil.cpu_percent(interval=1),
            "memory_usage": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "percent": psutil.virtual_memory().percent
            },
            "disk_usage": {
                "total": psutil.disk_usage('/').total if os.name != 'nt' else psutil.disk_usage('C:').total,
                "free": psutil.disk_usage('/').free if os.name != 'nt' else psutil.disk_usage('C:').free,
                "percent": psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:').percent
            },
            "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else None
        }
        
        # Service status
        services_status = {
            "api": "healthy",
            "database": "healthy" if db_health["status"] == "connected" else "unhealthy",
            "file_storage": "healthy" if os.path.exists("uploads") else "warning"
        }
        
        # Overall status
        overall_status = "healthy"
        if any(status == "unhealthy" for status in services_status.values()):
            overall_status = "unhealthy"
        elif any(status == "warning" for status in services_status.values()):
            overall_status = "warning"
        
        return DetailedHealthResponse(
            status=overall_status,
            timestamp=datetime.utcnow().isoformat(),
            version="1.0.0",
            uptime=uptime,
            database=db_health,
            system=system_info,
            services=services_status
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Detailed health check failed: {str(e)}"
        )

@router.get("/database", response_model=DatabaseHealthResponse)
async def database_health_check():
    """Database-specific health check"""
    try:
        # Test Supabase connection
        db_connected = test_connection()
        
        # Connection pool information (simplified for Supabase)
        pool_info = {
            "type": "supabase_client",
            "status": "connected" if db_connected else "disconnected"
        }
        
        # Simple query performance test
        start_time_query = datetime.utcnow()
        try:
            client = get_supabase_client()
            client.table('users').select('id').limit(1).execute()
            query_time = (datetime.utcnow() - start_time_query).total_seconds() * 1000
            query_status = "good" if query_time < 100 else "slow" if query_time < 1000 else "poor"
        except Exception:
            query_time = 0
            query_status = "failed"
        
        query_performance = {
            "simple_query_ms": query_time,
            "status": query_status
        }
        
        return DatabaseHealthResponse(
            status="connected" if db_connected else "disconnected",
            connection_pool=pool_info,
            query_performance=query_performance
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database health check failed: {str(e)}"
        )

@router.get("/readiness")
async def readiness_check():
    """Kubernetes readiness probe endpoint"""
    try:
        # Check database connectivity
        if not test_connection():
            raise Exception("Database connection failed")
        
        # Check critical directories
        if not os.path.exists("uploads"):
            os.makedirs("uploads", exist_ok=True)
        
        return {"status": "ready"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service not ready: {str(e)}"
        )

@router.get("/liveness")
async def liveness_check():
    """Kubernetes liveness probe endpoint"""
    try:
        # Basic application liveness check
        uptime = (datetime.utcnow() - start_time).total_seconds()
        
        # Check if the application has been running for a reasonable time
        if uptime < 0:
            raise Exception("Invalid uptime calculation")
        
        return {
            "status": "alive",
            "uptime": uptime
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Liveness check failed: {str(e)}"
        )

@router.get("/metrics")
async def get_metrics():
    """Get application metrics for monitoring"""
    try:
        client = get_supabase_client()
        
        # Database metrics using Supabase
        users_response = client.table('users').select('id', count='exact').execute()
        total_users = users_response.count or 0
        
        jobs_response = client.table('jobs').select('id', count='exact').execute()
        total_jobs = jobs_response.count or 0
        
        completed_jobs_response = client.table('jobs').select('id', count='exact').eq('status', 'completed').execute()
        completed_jobs = completed_jobs_response.count or 0
        
        failed_jobs_response = client.table('jobs').select('id', count='exact').eq('status', 'failed').execute()
        failed_jobs = failed_jobs_response.count or 0
        
        pending_jobs_response = client.table('jobs').select('id', count='exact').eq('status', 'pending').execute()
        pending_jobs = pending_jobs_response.count or 0
        
        processing_jobs_response = client.table('jobs').select('id', count='exact').eq('status', 'processing').execute()
        processing_jobs = processing_jobs_response.count or 0
        
        # Performance metrics (simplified for Supabase)
        try:
            results_response = client.table('job_results').select('processing_time_seconds', 'virality_score').execute()
            results_data = results_response.data or []
            
            if results_data:
                processing_times = [r.get('processing_time_seconds', 0) for r in results_data if r.get('processing_time_seconds')]
                virality_scores = [r.get('virality_score', 0) for r in results_data if r.get('virality_score')]
                
                avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
                avg_virality_score = sum(virality_scores) / len(virality_scores) if virality_scores else 0
            else:
                avg_processing_time = 0
                avg_virality_score = 0
        except Exception:
            avg_processing_time = 0
            avg_virality_score = 0
        
        # System metrics
        uptime = (datetime.utcnow() - start_time).total_seconds()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": uptime,
            "database_metrics": {
                "total_users": total_users,
                "total_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "failed_jobs": failed_jobs,
                "pending_jobs": pending_jobs,
                "processing_jobs": processing_jobs
            },
            "performance_metrics": {
                "average_processing_time_seconds": float(avg_processing_time),
                "average_virality_score": float(avg_virality_score) if avg_virality_score else None,
                "success_rate": (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
            },
            "system_metrics": {
                "cpu_usage_percent": psutil.cpu_percent(),
                "memory_usage_percent": psutil.virtual_memory().percent,
                "disk_usage_percent": psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:').percent
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving metrics: {str(e)}"
        )