#!/usr/bin/env python3
"""
Startup script for Virality Clipper FastAPI server
"""

import uvicorn
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add FFmpeg to PATH if not already present
ffmpeg_paths = [
    "C:\\ffmpeg\\bin",
    "C:\\Program Files\\ffmpeg\\bin",
    "C:\\Program Files (x86)\\ffmpeg\\bin"
]

for ffmpeg_path in ffmpeg_paths:
    if os.path.exists(ffmpeg_path) and ffmpeg_path not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ.get("PATH", "")
        print(f"Added FFmpeg path to environment: {ffmpeg_path}")
        break

if __name__ == "__main__":
    # Get configuration from environment
    host = os.getenv("FASTAPI_HOST", "0.0.0.0")
    port = int(os.getenv("FASTAPI_PORT", 8000))
    debug = os.getenv("FASTAPI_DEBUG", "True").lower() == "true"
    
    print(f"Starting Virality Clipper API server on {host}:{port}")
    print(f"Debug mode: {debug}")
    
    # Run the server with enhanced timeout configurations for large file uploads
    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info" if debug else "warning",
        timeout_keep_alive=300,  # 5 minutes keep-alive for long uploads
        timeout_graceful_shutdown=30,  # 30 seconds for graceful shutdown
        limit_max_requests=10000,  # Increase max requests
        limit_concurrency=1000,  # Allow more concurrent connections
        backlog=2048  # Increase connection backlog
    )