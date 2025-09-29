#!/usr/bin/env python3
"""
Cliper Application - Standalone Runner for Port 3000
A completely self-contained FastAPI application that runs on localhost:3000
"""

import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import json
import uuid
from datetime import datetime
import shutil

# Load configuration from config.env file
def load_config():
    """Load configuration from config.env file"""
    config = {}
    config_path = Path("config.env")
    
    if config_path.exists():
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
    
    # Set defaults
    config.setdefault('APP_PORT', '3000')
    config.setdefault('HOST', '0.0.0.0')
    config.setdefault('ENVIRONMENT', 'development')
    config.setdefault('DEBUG', 'true')
    config.setdefault('LOG_LEVEL', 'DEBUG')
    config.setdefault('FRONTEND_URL', 'http://localhost:3000')
    config.setdefault('VITE_API_URL', 'http://localhost:3000')
    
    return config

# Load configuration
config = load_config()

# Create FastAPI app
app = FastAPI(
    title="Cliper API",
    description="AI-Powered Video Clip Generation Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    environment: str

class PlatformConfig(BaseModel):
    name: str
    max_duration: int
    aspect_ratio: str
    resolution: str
    formats: List[str]
    optimization: Dict[str, Any]

class VideoUploadResponse(BaseModel):
    job_id: str
    status: str
    message: str
    file_info: Dict[str, Any]

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    clips_generated: int
    total_clips: int
    results: Optional[Dict[str, Any]] = None

# Demo data
DEMO_PLATFORMS = {
    "tiktok": {
        "name": "TikTok",
        "max_duration": 60,
        "aspect_ratio": "9:16",
        "resolution": "1080x1920",
        "formats": ["mp4"],
        "optimization": {
            "fps": 30,
            "bitrate": "2000k",
            "audio_bitrate": "128k",
            "optimize_for_mobile": True
        }
    },
    "youtube": {
        "name": "YouTube Shorts",
        "max_duration": 60,
        "aspect_ratio": "9:16",
        "resolution": "1080x1920",
        "formats": ["mp4"],
        "optimization": {
            "fps": 30,
            "bitrate": "4000k",
            "audio_bitrate": "128k",
            "optimize_for_streaming": True
        }
    },
    "instagram": {
        "name": "Instagram Reels",
        "max_duration": 90,
        "aspect_ratio": "9:16",
        "resolution": "1080x1920",
        "formats": ["mp4"],
        "optimization": {
            "fps": 30,
            "bitrate": "3000k",
            "audio_bitrate": "128k",
            "optimize_for_mobile": True
        }
    },
    "twitter": {
        "name": "Twitter/X",
        "max_duration": 140,
        "aspect_ratio": "16:9",
        "resolution": "1920x1080",
        "formats": ["mp4"],
        "optimization": {
            "fps": 30,
            "bitrate": "2500k",
            "audio_bitrate": "128k",
            "optimize_for_streaming": True
        }
    }
}

# In-memory storage for demo
jobs_db = {}
uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)

# Routes
@app.get("/", response_class=JSONResponse)
async def root():
    """Root endpoint with basic info"""
    return {
        "message": "🎬 Cliper API - AI-Powered Video Clip Generation",
        "version": "1.0.0",
        "status": "running",
        "port": config['APP_PORT'],
        "docs": "/docs",
        "demo": "/demo"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="1.0.0",
        environment=config['ENVIRONMENT']
    )

@app.get("/demo")
async def demo_info():
    """Demo information and capabilities"""
    return {
        "message": "🎬 Cliper Demo Mode",
        "description": "AI-Powered Video Clip Generation Platform",
        "features": [
            "📹 Video Upload & Processing",
            "🤖 AI-Powered Content Analysis", 
            "✂️ Intelligent Clip Generation",
            "📱 Multi-Platform Optimization",
            "🎯 Virality Scoring",
            "⚡ Real-time Processing"
        ],
        "platforms": list(DEMO_PLATFORMS.keys()),
        "endpoints": {
            "upload": "/api/v1/videos/upload",
            "status": "/api/v1/jobs/{job_id}/status",
            "platforms": "/api/v1/config/platforms",
            "health": "/health",
            "docs": "/docs"
        },
        "note": "This is demo mode. Add OpenAI API key and FFmpeg for full functionality."
    }

@app.get("/api/v1/config/platforms", response_model=Dict[str, PlatformConfig])
async def get_platform_configs():
    """Get platform-specific configuration"""
    return {platform: PlatformConfig(**config) for platform, config in DEMO_PLATFORMS.items()}

@app.post("/api/v1/videos/upload", response_model=VideoUploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    platforms: str = Form("tiktok,youtube"),
    duration_limit: int = Form(60)
):
    """Upload video for processing"""
    
    # Validate file
    if not file.content_type or not file.content_type.startswith('video/'):
        raise HTTPException(status_code=400, detail="File must be a video")
    
    # Generate job ID
    job_id = str(uuid.uuid4())
    
    # Save file
    file_path = uploads_dir / f"{job_id}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Create job record
    jobs_db[job_id] = {
        "id": job_id,
        "filename": file.filename,
        "file_path": str(file_path),
        "platforms": platforms.split(','),
        "duration_limit": duration_limit,
        "status": "uploaded",
        "progress": 0.0,
        "clips_generated": 0,
        "total_clips": 0,
        "created_at": datetime.now().isoformat(),
        "results": None
    }
    
    return VideoUploadResponse(
        job_id=job_id,
        status="uploaded",
        message="Video uploaded successfully",
        file_info={
            "filename": file.filename,
            "size": file_path.stat().st_size,
            "platforms": platforms.split(','),
            "duration_limit": duration_limit
        }
    )

@app.get("/api/v1/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get job processing status"""
    
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs_db[job_id]
    
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        clips_generated=job["clips_generated"],
        total_clips=job["total_clips"],
        results=job["results"]
    )

@app.post("/api/v1/jobs/{job_id}/process")
async def process_job(job_id: str):
    """Start processing a job (demo mode)"""
    
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs_db[job_id]
    
    # Demo processing simulation
    job["status"] = "processing"
    job["progress"] = 25.0
    job["total_clips"] = 3
    
    # Simulate clip generation
    job["clips_generated"] = 1
    job["progress"] = 50.0
    
    # Add demo results
    job["results"] = {
        "clips": [
            {
                "id": f"{job_id}_clip_1",
                "platform": "tiktok",
                "start_time": 5.2,
                "duration": 15.0,
                "virality_score": 8.5,
                "description": "High-energy moment with great engagement potential"
            },
            {
                "id": f"{job_id}_clip_2", 
                "platform": "youtube",
                "start_time": 23.1,
                "duration": 30.0,
                "virality_score": 7.8,
                "description": "Educational content perfect for YouTube Shorts"
            },
            {
                "id": f"{job_id}_clip_3",
                "platform": "instagram",
                "start_time": 45.7,
                "duration": 20.0,
                "virality_score": 9.1,
                "description": "Visual storytelling moment ideal for Instagram Reels"
            }
        ],
        "analysis": {
            "total_segments": 12,
            "viral_moments": 5,
            "avg_virality_score": 8.1,
            "recommended_platforms": ["tiktok", "instagram"]
        }
    }
    
    job["status"] = "completed"
    job["progress"] = 100.0
    job["clips_generated"] = 3
    
    return {"message": "Job processing completed", "job_id": job_id}

@app.get("/api/v1/jobs")
async def list_jobs():
    """List all jobs"""
    return {"jobs": list(jobs_db.values())}

if __name__ == "__main__":
    port = int(config['APP_PORT'])
    host = config['HOST']
    
    print(f"🚀 Starting Cliper API on Port {port}...")
    print(f"📖 API Documentation: http://localhost:{port}/docs")
    print(f"🔍 Demo Info: http://localhost:{port}/demo")
    print(f"❤️ Health Check: http://localhost:{port}/health")
    print(f"🌐 Frontend URL: {config['FRONTEND_URL']}")
    
    uvicorn.run(
        "run_cliper_3000:app",
        host=host,
        port=port,
        log_level=config['LOG_LEVEL'].lower(),
        reload=False
    )
