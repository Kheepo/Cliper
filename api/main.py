"""
FastAPI application for Cliper - AI-Powered Video Clip Generation System
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import logging
import os
import sys

# Add the parent directory to the path so we can import from api
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Cliper API",
    description="AI-Powered Video Clip Generation System",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
try:
    from api.routers.auth import router as auth_router
    app.include_router(auth_router, prefix="/api/v1")
    logger.info("Auth router loaded successfully")
except ImportError as e:
    logger.warning(f"Could not import auth router: {e}")

try:
    from api.routers.upload import router as upload_router
    app.include_router(upload_router, prefix="/api/v1")
    logger.info("Upload router loaded successfully")
except ImportError as e:
    logger.warning(f"Could not import upload router: {e}")

try:
    from api.routers.jobs import router as jobs_router
    app.include_router(jobs_router, prefix="/api/v1")
    logger.info("Jobs router loaded successfully")
except ImportError as e:
    logger.warning(f"Could not import jobs router: {e}")

try:
    from api.routers.health import router as health_router
    app.include_router(health_router, prefix="/api/v1")
    logger.info("Health router loaded successfully")
except ImportError as e:
    logger.warning(f"Could not import health router: {e}")

try:
    from api.routers.clips import router as clips_router
    app.include_router(clips_router, prefix="/api/v1/clips")
    logger.info("Clips router loaded successfully")
except ImportError as e:
    logger.warning(f"Could not import clips router: {e}")

try:
    from api.routers.analysis import router as analysis_router
    app.include_router(analysis_router, prefix="/api")
    logger.info("Analysis router loaded successfully")
except ImportError as e:
    logger.warning(f"Could not import analysis router: {e}")

try:
    from api.routers.recommendations import router as recommendations_router
    app.include_router(recommendations_router, prefix="/api/v1/recommendations")
    logger.info("Recommendations router loaded successfully")
except ImportError as e:
    logger.warning(f"Could not import recommendations router: {e}")

# Basic health check endpoint
@app.get("/")
async def root():
    return {"message": "Cliper API is running", "status": "healthy"}

# Test endpoint to verify routing works
@app.post("/api/v1/recommendations/test")
async def test_recommendations():
    return {"message": "Test endpoint working", "status": "success"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "cliper-api"}

# Serve the test interface
@app.get("/test_clip_generation.html")
async def serve_test_interface():
    """Serve the test clip generation interface"""
    test_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_clip_generation_direct.html")
    if os.path.exists(test_file_path):
        return FileResponse(test_file_path, media_type="text/html")
    else:
        raise HTTPException(status_code=404, detail="Test interface not found")

# Test auth endpoint
@app.post("/api/v1/auth/test")
async def test_auth():
    return {"message": "Auth endpoint working", "status": "ok"}

# Simple registration endpoint for testing
@app.post("/api/v1/auth/register")
async def register_user(user_data: dict):
    """Simple registration endpoint for testing"""
    return {
        "user": {
            "id": "test-user-123",
            "email": user_data.get("email", "test@example.com"),
            "display_name": user_data.get("full_name", "Test User")
        },
        "tokens": {
            "access_token": "test-access-token-123456789",
            "refresh_token": "test-refresh-token-123456789"
        },
        "message": "User registered successfully"
    }

# Simple login endpoint for testing
@app.post("/api/v1/auth/login")
async def login_user(login_data: dict):
    """Simple login endpoint for testing"""
    return {
        "user": {
            "id": "test-user-123",
            "email": login_data.get("email", "test@example.com"),
            "display_name": "Test User"
        },
        "tokens": {
            "access_token": "test-access-token-123456789",
            "refresh_token": "test-refresh-token-123456789"
        },
        "message": "Login successful"
    }

# Simple in-memory storage for testing
uploaded_videos = {}

# Simple upload endpoint for testing
@app.post("/api/videos/upload")
async def upload_video():
    """Simple upload endpoint for testing"""
    import uuid
    from datetime import datetime
    job_id = str(uuid.uuid4())
    
    # Store the uploaded video
    uploaded_videos[job_id] = {
        "id": job_id,
        "status": "completed",
        "file_url": f"https://example.com/videos/{job_id}.mp4",
        "created_at": datetime.now().isoformat() + "Z",
        "processing_status": "ready_for_clipping"
    }
    
    return {
        "job_id": job_id,
        "file_url": f"https://example.com/videos/{job_id}.mp4",
        "task_id": f"task_{job_id}",
        "status": "processing",
        "message": "Video upload successful"
    }

# Simple videos list endpoint for testing
@app.get("/api/videos/")
async def list_videos():
    """Simple videos list endpoint for testing"""
    return list(uploaded_videos.values())

# Simple clip generation endpoint for testing that actually calls Celery
@app.post("/api/videos/{video_id}/clips")
async def generate_clips(video_id: str, request_data: dict = None):
    """Simple clip generation endpoint for testing that calls actual Celery task"""
    try:
        # Import the actual Celery task
        from api.tasks import generate_clips_task
        from api.celery_app import is_background_tasks_available
        import uuid
        
        clip_id = str(uuid.uuid4())
        
        # Prepare generation options
        generation_options = {
            'clip_type': 'highlight',
            'target_duration': 30.0,
            'platform': 'youtube',
            'custom_parameters': request_data or {}
        }
        
        # Check if background tasks are available
        if is_background_tasks_available():
            try:
                # Call the actual Celery task
                task = generate_clips_task.delay(
                    clip_id=clip_id,
                    video_id=video_id,
                    user_id="test-user-123",  # Test user ID
                    generation_options=generation_options
                )
                
                logger.info(f"Queued clip generation task {task.id} for clip {clip_id}")
                
                return {
                    "clip_id": clip_id,
                    "video_id": video_id,
                    "task_id": task.id,
                    "status": "processing",
                    "message": "Clip generation started successfully"
                }
            except Exception as e:
                logger.error(f"Failed to queue clip generation task: {e}")
                return {
                    "clip_id": clip_id,
                    "video_id": video_id,
                    "status": "failed",
                    "error": str(e),
                    "message": "Failed to start clip generation"
                }
        else:
            return {
                "clip_id": clip_id,
                "video_id": video_id,
                "status": "failed",
                "error": "Background tasks not available",
                "message": "Clip generation service unavailable"
            }
    except Exception as e:
        logger.error(f"Error in generate_clips endpoint: {e}")
        return {
            "clip_id": "error",
            "video_id": video_id,
            "status": "failed",
            "error": str(e),
            "message": "Internal server error"
        }

if __name__ == "__main__":
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()
    
    uvicorn.run(app, host=args.host, port=args.port)