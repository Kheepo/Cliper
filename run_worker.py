#!/usr/bin/env python3
"""
Startup script for Virality Clipper Celery worker
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the current directory to Python path
sys.path.insert(0, os.getcwd())

if __name__ == "__main__":
    from api.celery_app import celery_app
    
    print("Starting Virality Clipper Celery worker...")
    print(f"Broker URL: {os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')}")
    print(f"Result Backend: {os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')}")
    
    # Start the worker
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=2',
        '--queues=video_processing',
        '--hostname=worker@%h'
    ])