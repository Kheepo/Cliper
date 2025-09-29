#!/usr/bin/env python3
"""
Custom Video Processing Metrics Exporter

Collects and exposes custom metrics for the video processing system including:
- Video processing queue metrics
- AI service performance
- FFmpeg operation metrics
- WebSocket connection metrics
- Custom business metrics
"""

import asyncio
import logging
import os
import signal
import sys
import time
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

import psutil
import structlog
from fastapi import FastAPI, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    start_http_server,
)
from pydantic import BaseSettings

from .collectors import (
    AIServiceCollector,
    CeleryCollector,
    DatabaseCollector,
    FFmpegCollector,
    RedisCollector,
    SystemCollector,
    VideoProcessingCollector,
    WebSocketCollector,
)
from .utils import setup_logging


class ExporterSettings(BaseSettings):
    """Configuration settings for the metrics exporter."""
    
    # Server configuration
    exporter_port: int = 9200
    exporter_host: str = "0.0.0.0"
    exporter_interval: int = 30
    
    # Database configuration
    database_url: str = "postgresql://user:password@localhost:5432/video_processing"
    redis_url: str = "redis://localhost:6379"
    
    # API configuration
    api_base_url: str = "http://localhost:8000"
    
    # Monitoring configuration
    metrics_enabled: bool = True
    health_check_enabled: bool = True
    
    # Logging configuration
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Cache configuration
    cache_ttl: int = 300
    
    # Collection intervals (seconds)
    system_metrics_interval: int = 30
    database_metrics_interval: int = 60
    redis_metrics_interval: int = 30
    celery_metrics_interval: int = 30
    video_processing_interval: int = 15
    ai_service_interval: int = 60
    ffmpeg_interval: int = 30
    websocket_interval: int = 30
    
    class Config:
        env_file = ".env"
        env_prefix = "EXPORTER_"


class VideoProcessingExporter:
    """Main exporter class that orchestrates metric collection."""
    
    def __init__(self, settings: ExporterSettings):
        self.settings = settings
        self.logger = structlog.get_logger()
        self.running = False
        self.collectors = {}
        self.tasks = []
        
        # Initialize Prometheus metrics
        self._init_metrics()
        
        # Initialize collectors
        self._init_collectors()
    
    def _init_metrics(self):
        """Initialize Prometheus metrics."""
        # Exporter info
        self.exporter_info = Info(
            'video_processing_exporter_info',
            'Information about the video processing exporter'
        )
        self.exporter_info.info({
            'version': '1.0.0',
            'python_version': sys.version,
            'host': self.settings.exporter_host,
            'port': str(self.settings.exporter_port)
        })
        
        # Collection metrics
        self.collection_duration = Histogram(
            'video_processing_collection_duration_seconds',
            'Time spent collecting metrics',
            ['collector']
        )
        
        self.collection_errors = Counter(
            'video_processing_collection_errors_total',
            'Total number of collection errors',
            ['collector', 'error_type']
        )
        
        self.last_collection_timestamp = Gauge(
            'video_processing_last_collection_timestamp',
            'Timestamp of last successful collection',
            ['collector']
        )
        
        # Exporter health
        self.exporter_up = Gauge(
            'video_processing_exporter_up',
            'Whether the exporter is running'
        )
        self.exporter_up.set(1)
        
        # System resource usage
        self.exporter_memory_usage = Gauge(
            'video_processing_exporter_memory_usage_bytes',
            'Memory usage of the exporter process'
        )
        
        self.exporter_cpu_usage = Gauge(
            'video_processing_exporter_cpu_usage_percent',
            'CPU usage of the exporter process'
        )
    
    def _init_collectors(self):
        """Initialize metric collectors."""
        try:
            self.collectors = {
                'system': SystemCollector(self.settings),
                'database': DatabaseCollector(self.settings),
                'redis': RedisCollector(self.settings),
                'celery': CeleryCollector(self.settings),
                'video_processing': VideoProcessingCollector(self.settings),
                'ai_service': AIServiceCollector(self.settings),
                'ffmpeg': FFmpegCollector(self.settings),
                'websocket': WebSocketCollector(self.settings),
            }
            
            self.logger.info(
                "Initialized collectors",
                collectors=list(self.collectors.keys())
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to initialize collectors",
                error=str(e),
                exc_info=True
            )
            raise
    
    async def _collect_metrics(self, collector_name: str, collector):
        """Collect metrics from a specific collector."""
        start_time = time.time()
        
        try:
            await collector.collect()
            
            # Update collection timestamp
            self.last_collection_timestamp.labels(
                collector=collector_name
            ).set(time.time())
            
            self.logger.debug(
                "Metrics collected successfully",
                collector=collector_name,
                duration=time.time() - start_time
            )
            
        except Exception as e:
            self.collection_errors.labels(
                collector=collector_name,
                error_type=type(e).__name__
            ).inc()
            
            self.logger.error(
                "Failed to collect metrics",
                collector=collector_name,
                error=str(e),
                exc_info=True
            )
        
        finally:
            # Record collection duration
            self.collection_duration.labels(
                collector=collector_name
            ).observe(time.time() - start_time)
    
    async def _collection_loop(self, collector_name: str, collector, interval: int):
        """Run collection loop for a specific collector."""
        self.logger.info(
            "Starting collection loop",
            collector=collector_name,
            interval=interval
        )
        
        while self.running:
            try:
                await self._collect_metrics(collector_name, collector)
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                self.logger.info(
                    "Collection loop cancelled",
                    collector=collector_name
                )
                break
                
            except Exception as e:
                self.logger.error(
                    "Unexpected error in collection loop",
                    collector=collector_name,
                    error=str(e),
                    exc_info=True
                )
                await asyncio.sleep(interval)
    
    async def _update_exporter_metrics(self):
        """Update exporter's own metrics."""
        while self.running:
            try:
                # Get current process
                process = psutil.Process()
                
                # Update memory usage
                memory_info = process.memory_info()
                self.exporter_memory_usage.set(memory_info.rss)
                
                # Update CPU usage
                cpu_percent = process.cpu_percent()
                self.exporter_cpu_usage.set(cpu_percent)
                
                await asyncio.sleep(30)  # Update every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(
                    "Failed to update exporter metrics",
                    error=str(e)
                )
                await asyncio.sleep(30)
    
    async def start(self):
        """Start the metrics exporter."""
        self.logger.info(
            "Starting video processing metrics exporter",
            port=self.settings.exporter_port,
            interval=self.settings.exporter_interval
        )
        
        self.running = True
        
        # Start collection tasks
        intervals = {
            'system': self.settings.system_metrics_interval,
            'database': self.settings.database_metrics_interval,
            'redis': self.settings.redis_metrics_interval,
            'celery': self.settings.celery_metrics_interval,
            'video_processing': self.settings.video_processing_interval,
            'ai_service': self.settings.ai_service_interval,
            'ffmpeg': self.settings.ffmpeg_interval,
            'websocket': self.settings.websocket_interval,
        }
        
        for collector_name, collector in self.collectors.items():
            interval = intervals.get(collector_name, self.settings.exporter_interval)
            task = asyncio.create_task(
                self._collection_loop(collector_name, collector, interval)
            )
            self.tasks.append(task)
        
        # Start exporter metrics update task
        exporter_task = asyncio.create_task(self._update_exporter_metrics())
        self.tasks.append(exporter_task)
        
        self.logger.info(
            "Metrics collection started",
            collectors=len(self.collectors),
            tasks=len(self.tasks)
        )
    
    async def stop(self):
        """Stop the metrics exporter."""
        self.logger.info("Stopping video processing metrics exporter")
        
        self.running = False
        self.exporter_up.set(0)
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Close collectors
        for collector in self.collectors.values():
            if hasattr(collector, 'close'):
                await collector.close()
        
        self.logger.info("Metrics exporter stopped")


# FastAPI app for health checks and metrics endpoint
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
    settings = ExporterSettings()
    exporter = VideoProcessingExporter(settings)
    
    # Store exporter in app state
    app.state.exporter = exporter
    
    # Start exporter
    await exporter.start()
    
    yield
    
    # Shutdown
    await exporter.stop()


app = FastAPI(
    title="Video Processing Metrics Exporter",
    description="Custom metrics exporter for video processing system",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    exporter = app.state.exporter
    
    if not exporter.running:
        return Response(
            content="Exporter not running",
            status_code=503
        )
    
    # Check collector health
    unhealthy_collectors = []
    for name, collector in exporter.collectors.items():
        if hasattr(collector, 'is_healthy') and not await collector.is_healthy():
            unhealthy_collectors.append(name)
    
    if unhealthy_collectors:
        return Response(
            content=f"Unhealthy collectors: {', '.join(unhealthy_collectors)}",
            status_code=503
        )
    
    return {"status": "healthy", "collectors": len(exporter.collectors)}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.get("/info")
async def info():
    """Exporter information endpoint."""
    exporter = app.state.exporter
    
    return {
        "version": "1.0.0",
        "running": exporter.running,
        "collectors": list(exporter.collectors.keys()),
        "settings": {
            "port": exporter.settings.exporter_port,
            "interval": exporter.settings.exporter_interval,
            "log_level": exporter.settings.log_level,
        }
    }


def setup_signal_handlers(exporter: VideoProcessingExporter):
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logging.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(exporter.stop())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main entry point."""
    # Setup logging
    setup_logging()
    
    # Load settings
    settings = ExporterSettings()
    
    # Create and start exporter
    exporter = VideoProcessingExporter(settings)
    
    # Setup signal handlers
    setup_signal_handlers(exporter)
    
    try:
        # Start exporter
        await exporter.start()
        
        # Start FastAPI server
        import uvicorn
        config = uvicorn.Config(
            app,
            host=settings.exporter_host,
            port=settings.exporter_port,
            log_level=settings.log_level.lower(),
            access_log=False
        )
        server = uvicorn.Server(config)
        await server.serve()
        
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt")
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        await exporter.stop()


if __name__ == "__main__":
    asyncio.run(main())