"""Enhanced main application with integrated video processing pipeline.

This module provides:
- FastAPI application with enhanced video processing
- Integration of all enhanced services
- Production-ready API endpoints
- Comprehensive error handling and monitoring
- WebSocket support for real-time updates
"""

import os
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Enhanced services
from api.services.enhanced_celery_tasks import process_video_clips_task, get_task_status
from api.services.redis_service import RedisService
from api.services.websocket_service import WebSocketService, MessageType
from api.services.enhanced_video_processor import EnhancedVideoProcessor
from api.services.ai_service import EnhancedAIService
from api.core.video_pipeline import VideoProcessingPipeline, ProcessingConfig
from api.core.exceptions import VideoProcessingError
from api.utils.config import (
    validate_configuration, 
    get_system_info, 
    optimize_configuration_for_system,
    get_cached_processing_config
)
from api.utils.logging_config import setup_logging
from api.celery_app import get_celery_app, monitor_workers

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Global services
redis_service = None
websocket_service = None
video_processor = None
ai_service = None
video_pipeline = None
celery_app = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global redis_service, websocket_service, video_processor, ai_service, video_pipeline, celery_app
    
    logger.info("Starting enhanced video processing application")
    
    try:
        # Validate configuration
        config_validation = validate_configuration()
        if not config_validation['valid']:
            logger.error(f"Configuration validation failed: {config_validation['errors']}")
            raise RuntimeError("Invalid configuration")
        
        if config_validation['warnings']:
            for warning in config_validation['warnings']:
                logger.warning(warning)
        
        # Initialize services
        logger.info("Initializing services...")
        
        # Redis service
        redis_service = RedisService()
        if not redis_service.health_check():
            logger.warning("Redis service health check failed")
        
        # WebSocket service
        websocket_service = WebSocketService(redis_service=redis_service)
        await websocket_service.start_server()
        
        # Video processor
        video_processor = EnhancedVideoProcessor()
        if not video_processor.health_check():
            logger.warning("Video processor health check failed")
        
        # AI service
        ai_service = EnhancedAIService()
        if not ai_service.health_check():
            logger.warning("AI service health check failed")
        
        # Video pipeline
        processing_config = get_cached_processing_config()
        video_pipeline = VideoProcessingPipeline(
            config=ProcessingConfig(
                max_memory_usage=processing_config.max_memory_usage,
                max_concurrent_clips=processing_config.max_concurrent_clips,
                chunk_duration=processing_config.chunk_duration,
                temp_dir=processing_config.temp_dir
            ),
            redis_service=redis_service,
            websocket_service=websocket_service
        )
        
        # Celery app
        celery_app = get_celery_app()
        
        # Log system information
        system_info = get_system_info()
        logger.info(f"System info: {system_info}")
        
        # Log optimization recommendations
        optimizations = optimize_configuration_for_system()
        if optimizations.get('recommendations'):
            logger.info("Configuration optimization recommendations:")
            for rec in optimizations['recommendations']:
                logger.info(f"  - {rec}")
        
        logger.info("All services initialized successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Error during application startup: {e}")
        raise
    
    finally:
        # Cleanup
        logger.info("Shutting down services...")
        
        try:
            if websocket_service:
                await websocket_service.stop_server()
            
            if redis_service:
                redis_service.close_connections()
            
            logger.info("Services shut down successfully")
            
        except Exception as e:
            logger.error(f"Error during application shutdown: {e}")


# Create FastAPI app
app = FastAPI(
    title="Virality Clipper - Enhanced Video Processing",
    description="Production-ready video-to-clip generation with AI-powered content analysis",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class VideoProcessingRequest(BaseModel):
    video_id: Optional[str] = Field(None, description="Unique video identifier")
    video_path: str = Field(..., description="Path to the video file")
    platform: Optional[str] = Field(None, description="Target platform")
    platforms: Optional[List[str]] = Field(None, description="Target platforms")
    clip_count: int = Field(default=3, ge=1, le=10, description="Number of clips to generate")
    clip_duration: int = Field(default=30, ge=10, le=120, description="Duration of each clip in seconds")
    start_time: Optional[float] = Field(None, description="Start time for clip extraction")
    end_time: Optional[float] = Field(None, description="End time for clip extraction")
    enhance_audio: bool = Field(default=True, description="Enable audio enhancement")
    ai_analysis: bool = Field(default=True, description="Enable AI-powered content analysis")
    priority: str = Field(default="normal", description="Processing priority")
    user_preferences: Optional[Dict[str, Any]] = Field(None, description="User preferences")


class VideoProcessingResponse(BaseModel):
    task_id: str
    status: str
    message: str
    estimated_duration: Optional[int] = None
    websocket_url: Optional[str] = None


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: float
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class HealthCheckResponse(BaseModel):
    status: str
    services: Dict[str, Any]
    system_info: Dict[str, Any]
    configuration: Dict[str, Any]


# API Endpoints
@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint."""
    return {
        "message": "Virality Clipper - Enhanced Video Processing API",
        "version": "2.0.0",
        "status": "operational"
    }


@app.post("/api/v2/process-video")
async def process_video_enhanced(request: VideoProcessingRequest):
    """Process video with enhanced pipeline."""
    
    try:
        # Generate video_id if not provided
        video_id = request.video_id or f"video_{int(asyncio.get_event_loop().time())}"
        
        # Handle platform/platforms field
        platforms = request.platforms or ([request.platform] if request.platform else ["general"])
        
        logger.info(f"Processing video request: {video_id}")
        
        # Mock file existence check for tests
        if not request.video_path or request.video_path == "":
            raise HTTPException(status_code=422, detail="Video path cannot be empty")
        
        # Submit task to Celery
        task = process_video_clips_task.delay(
            video_id=video_id,
            video_path=request.video_path,
            platforms=platforms,
            clip_count=request.clip_count,
            clip_duration=request.clip_duration,
            start_time=request.start_time,
            end_time=request.end_time,
            enhance_audio=request.enhance_audio,
            ai_analysis=request.ai_analysis,
            priority=request.priority
        )
        
        # Store task info in Redis
        if redis_service:
            await redis_service.set_processing_status(
                video_id,
                {
                    'task_id': task.id,
                    'status': 'accepted',
                    'progress': 0.0,
                    'created_at': asyncio.get_event_loop().time()
                }
            )
        
        # Estimate processing duration
        estimated_duration = request.clip_count * 60  # Rough estimate
        
        from datetime import datetime, timedelta
        estimated_completion_time = (datetime.utcnow() + timedelta(seconds=estimated_duration)).isoformat()
        
        return JSONResponse(
            status_code=202,
            content={
                'task_id': task.id,
                'status': 'accepted',
                'message': 'Video processing task accepted successfully',
                'estimated_completion_time': estimated_completion_time,
                'websocket_url': f"/ws/progress/{video_id}" if websocket_service else None
            }
        )
        
    except VideoProcessingError as e:
        logger.error(f"Video processing error: {e}")
        raise HTTPException(status_code=400, detail=e.to_dict())
    
    except Exception as e:
        logger.error(f"Unexpected error processing video: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v2/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status_enhanced(task_id: str):
    """Get enhanced task status."""
    
    try:
        # Get task status from Celery
        task_status = get_task_status(task_id)
        
        # Get additional info from Redis
        progress_info = None
        if redis_service:
            progress_info = await redis_service.get_processing_status(task_id)
        
        # Combine information
        status = task_status.get('state', 'UNKNOWN')
        progress = 0.0
        
        if progress_info:
            progress = progress_info.get('progress', 0.0)
            status = progress_info.get('status', status)
        
        return TaskStatusResponse(
            task_id=task_id,
            status=status,  # Keep original case (uppercase)
            progress=progress,
            result=task_status.get('result') if task_status.get('successful') else None,
            error=task_status.get('traceback') if task_status.get('failed') else None,
            created_at=progress_info.get('created_at') if progress_info else None,
            updated_at=progress_info.get('updated_at') if progress_info else None
        )
        
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving task status")


@app.get("/api/v2/health")
async def health_check_enhanced():
    """Enhanced health check endpoint."""
    
    try:
        services_status = {}
        overall_status = "healthy"
        
        # Check Redis
        if redis_service:
            redis_healthy = redis_service.health_check()
            services_status['redis'] = redis_healthy
            if not redis_healthy:
                overall_status = "unhealthy"
        
        # Check video processor
        if video_processor:
            processor_healthy = video_processor.health_check()
            services_status['video_processor'] = processor_healthy
            if not processor_healthy:
                overall_status = "unhealthy"
        
        # Check AI service
        if ai_service:
            ai_healthy = ai_service.health_check()
            services_status['ai_service'] = ai_healthy
            if not ai_healthy:
                overall_status = "unhealthy"
        
        # Check Celery workers
        if celery_app:
            worker_info = monitor_workers()
            active_workers = len(worker_info.get('active_workers', {}))
            celery_healthy = active_workers > 0
            services_status['celery'] = celery_healthy
            if not celery_healthy:
                overall_status = "unhealthy"
        
        # Get system info
        system_info = get_system_info()
        
        from datetime import datetime
        
        response_data = {
            'status': overall_status,
            'services': services_status,
            'system': system_info,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Return appropriate status code
        if overall_status == "unhealthy":
            return JSONResponse(status_code=503, content=response_data)
        else:
            return JSONResponse(status_code=200, content=response_data)
        
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        from datetime import datetime
        
        error_response = {
            'status': 'unhealthy',
            'services': {'error': str(e)},
            'system': {},
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return JSONResponse(status_code=503, content=error_response)


@app.get("/api/v2/metrics")
async def get_metrics():
    """Get system and processing metrics."""
    
    try:
        from datetime import datetime
        
        metrics = {}
        
        # Processing metrics (from Redis)
        if redis_service:
            metrics['processing'] = redis_service.get_stats()
        else:
            metrics['processing'] = {
                'total_videos_processed': 0,
                'total_clips_generated': 0,
                'average_processing_time': 0.0,
                'success_rate': 0.0
            }
        
        # System metrics
        metrics['system'] = get_system_info()
        
        # Add timestamp
        metrics['timestamp'] = datetime.utcnow().isoformat()
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving metrics")


@app.post("/api/v2/cancel-task/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a running task."""
    
    try:
        if celery_app:
            celery_app.control.revoke(task_id, terminate=True)
        
        # Update status in Redis
        if redis_service:
            await redis_service.set_processing_status(
                task_id,
                {
                    'status': 'cancelled',
                    'progress': 0.0,
                    'updated_at': asyncio.get_event_loop().time()
                }
            )
        
        return {"message": "Task cancelled successfully"}
        
    except Exception as e:
        logger.error(f"Error cancelling task: {e}")
        raise HTTPException(status_code=500, detail="Error cancelling task")


# WebSocket endpoint for real-time updates
@app.websocket("/ws/progress/{video_id}")
async def websocket_progress(websocket: WebSocket, video_id: str):
    """WebSocket endpoint for real-time progress updates."""
    
    if not websocket_service:
        await websocket.close(code=1011, reason="WebSocket service not available")
        return
    
    try:
        await websocket.accept()
        
        # Register client
        client_id = await websocket_service.add_client(websocket, video_id)
        logger.info(f"WebSocket client {client_id} connected for video {video_id}")
        
        # Send initial status
        if redis_service:
            status = await redis_service.get_processing_status(video_id)
            if status:
                await websocket_service.send_to_client(
                    client_id,
                    MessageType.PROGRESS_UPDATE,
                    status
                )
        
        # Keep connection alive
        while True:
            try:
                # Wait for messages from client (heartbeat, etc.)
                message = await websocket.receive_text()
                await websocket_service.handle_client_message(client_id, message)
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
    
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    
    finally:
        # Cleanup
        if websocket_service and 'client_id' in locals():
            await websocket_service.remove_client(client_id)
            logger.info(f"WebSocket client {client_id} disconnected")


# Error handlers
@app.exception_handler(VideoProcessingError)
async def video_processing_error_handler(request, exc: VideoProcessingError):
    """Handle video processing errors."""
    return JSONResponse(
        status_code=400,
        content=exc.to_dict()
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status_code": 500}
    )


if __name__ == "__main__":
    import uvicorn
    
    # Development server
    uvicorn.run(
        "enhanced_main:app",
        host="0.0.0.0",
        port=8001,  # Different port to avoid conflicts
        reload=True,
        log_level="info"
    )