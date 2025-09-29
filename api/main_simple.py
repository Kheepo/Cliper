"""
Simplified FastAPI application for testing
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

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

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Cliper API",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "API is running"
    }

@app.get("/api/v1/health")
async def health_check_v1():
    """V1 health check endpoint"""
    return {
        "status": "healthy",
        "message": "API v1 is running",
        "services": {
            "api": "healthy",
            "database": "not_configured",
            "ai_service": "not_configured",
            "video_processor": "not_configured"
        }
    }

@app.get("/api/v1/status")
async def system_status():
    """System status endpoint"""
    return {
        "status": "running",
        "timestamp": "2024-01-01T00:00:00Z",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development")
    }

@app.get("/api/v1/config/platforms")
async def get_supported_platforms():
    """Get supported platforms"""
    return {
        "platforms": {
            'tiktok': {
                'name': 'TikTok',
                'max_duration': 60,
                'min_duration': 15,
                'aspect_ratio': '9:16',
                'resolution': '1080x1920',
                'optimal_duration': 30
            },
            'youtube': {
                'name': 'YouTube Shorts',
                'max_duration': 60,
                'min_duration': 15,
                'aspect_ratio': '9:16',
                'resolution': '1080x1920',
                'optimal_duration': 45
            },
            'instagram': {
                'name': 'Instagram Reels',
                'max_duration': 90,
                'min_duration': 15,
                'aspect_ratio': '9:16',
                'resolution': '1080x1920',
                'optimal_duration': 30
            }
        }
    }

@app.post("/api/v1/videos/upload")
async def upload_video():
    """Upload video endpoint (placeholder)"""
    return {
        "message": "Video upload endpoint - requires full setup",
        "status": "not_implemented",
        "note": "This is a simplified version. Full implementation requires FFmpeg and AI services."
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
