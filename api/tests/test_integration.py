"""Integration tests for the enhanced video processing system.

This module provides:
- End-to-end workflow testing
- API endpoint integration tests
- Celery task integration tests
- Performance and stress testing
- Error scenario validation
"""

import os
import pytest
import asyncio
import tempfile
import shutil
import json
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
from typing import Dict, Any
from fastapi.testclient import TestClient
from celery import Celery

# Set test environment variable
os.environ['TESTING'] = 'true'

# Apply patches at module level before any imports
patch_detect = patch('api.utils.config.detect_ffmpeg_path')
patch_video_processor = patch('api.services.enhanced_video_processor.EnhancedVideoProcessor')
patch_module_instance = patch('api.services.enhanced_video_processor.enhanced_video_processor')
patch_subprocess = patch('subprocess.run')

# Start all patches
mock_detect = patch_detect.start()
mock_video_processor_class = patch_video_processor.start()
mock_module_instance = patch_module_instance.start()
mock_subprocess = patch_subprocess.start()

# Configure mocks
mock_detect.return_value = Mock(
    ffmpeg_path='ffmpeg',
    ffprobe_path='ffprobe', 
    available=True,
    version='8.0'
)

# Create a mock video processor instance
mock_video_processor_instance = Mock()
mock_video_processor_instance.health_check.return_value = True
mock_video_processor_instance.ffmpeg_path = 'ffmpeg'
mock_video_processor_instance.ffprobe_path = 'ffprobe'
mock_video_processor_instance.gpu_acceleration = Mock(value='none')
mock_video_processor_class.return_value = mock_video_processor_instance

# Configure the module-level instance mock
mock_module_instance.health_check.return_value = True
mock_module_instance.ffmpeg_path = 'ffmpeg'
mock_module_instance.ffprobe_path = 'ffprobe'
mock_module_instance.gpu_acceleration = Mock(value='none')

mock_subprocess.return_value = Mock(returncode=0, stdout='ffmpeg version 4.4.0')

# Now safe to import
from api.enhanced_main import app
from api.services.enhanced_celery_tasks import (
    process_video_clips_task, process_single_clip_task, health_check_task
)
from api.celery_app import celery_app
from api.core.video_pipeline import VideoProcessingPipeline, ProcessingConfig
from api.core.exceptions import VideoProcessingError, ResourceExhaustionError
from api.utils.config import validate_configuration


class TestFastAPIIntegration:
    """Test FastAPI application integration."""
    
    @pytest.fixture
    def client(self):
        """Test client for FastAPI app."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_services(self):
        """Mock all external services."""
        with patch('api.enhanced_main.redis_service') as mock_redis, \
             patch('api.enhanced_main.websocket_service') as mock_ws, \
             patch('api.enhanced_main.video_processor') as mock_processor, \
             patch('api.enhanced_main.ai_service') as mock_ai:
            
            # Setup health checks
            mock_redis.health_check.return_value = True
            mock_ws.health_check.return_value = True
            mock_processor.health_check.return_value = True
            mock_ai.health_check.return_value = True
            
            yield {
                'redis': mock_redis,
                'websocket': mock_ws,
                'processor': mock_processor,
                'ai': mock_ai
            }
    
    def test_health_check_endpoint(self, client, mock_services):
        """Test health check endpoint."""
        response = client.get('/api/v2/health')
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert 'services' in data
        assert 'system' in data
        assert 'timestamp' in data
    
    def test_health_check_with_service_failure(self, client, mock_services):
        """Test health check with service failure."""
        # Make Redis fail
        mock_services['redis'].health_check.return_value = False
        
        response = client.get('/api/v2/health')
        
        assert response.status_code == 503
        data = response.json()
        assert data['status'] == 'unhealthy'
        assert data['services']['redis'] is False
    
    def test_process_video_endpoint_success(self, client, mock_services):
        """Test successful video processing request."""
        with patch('api.enhanced_main.process_video_clips_task.delay') as mock_task, \
             patch('api.enhanced_main.get_task_status') as mock_get_status:
            mock_task.return_value.id = 'test_task_id'
            mock_get_status.return_value = {'state': 'PENDING', 'result': None}
            
            request_data = {
                'video_path': '/path/to/video.mp4',
                'platform': 'tiktok',
                'clip_count': 3,
                'clip_duration': 30,
                'user_preferences': {
                    'content_type': 'highlight',
                    'style': 'energetic'
                }
            }
            
            response = client.post('/api/v2/process-video', json=request_data)
            
            assert response.status_code == 202
            data = response.json()
            assert data['task_id'] == 'test_task_id'
            assert data['status'] == 'accepted'
            assert 'estimated_completion_time' in data
    
    def test_process_video_endpoint_validation_error(self, client, mock_services):
        """Test video processing with validation error."""
        request_data = {
            'video_path': '',  # Invalid empty path
            'platform': 'invalid_platform',
            'clip_count': 0  # Invalid count
        }
        
        response = client.post('/api/v2/process-video', json=request_data)
        
        assert response.status_code == 422
        data = response.json()
        assert 'detail' in data
    
    def test_task_status_endpoint(self, client, mock_services):
        """Test task status endpoint."""
        with patch('api.enhanced_main.get_task_status') as mock_get_status:
            mock_get_status.return_value = {
                'state': 'PROGRESS',
                'result': None,
                'successful': False,
                'failed': False
            }
            
            response = client.get('/api/v2/task/test_task_id')
            
            assert response.status_code == 200
            data = response.json()
            assert data['task_id'] == 'test_task_id'
            assert data['status'] == 'PROGRESS'
            assert data['progress'] == 50.0
    
    def test_cancel_task_endpoint(self, client, mock_services):
        """Test task cancellation endpoint."""
        with patch('api.enhanced_main.celery_app') as mock_celery:
            mock_celery.control.revoke = Mock()
            
            response = client.post('/api/v2/cancel-task/test_task_id')
            
            assert response.status_code == 200
            data = response.json()
            assert data['message'] == 'Task cancelled successfully'
            mock_celery.control.revoke.assert_called_once_with('test_task_id', terminate=True)
    
    def test_metrics_endpoint(self, client, mock_services):
        """Test metrics endpoint."""
        mock_services['redis'].get_stats.return_value = {
            'total_videos_processed': 100,
            'total_clips_generated': 300,
            'average_processing_time': 45.2,
            'success_rate': 0.95
        }
        
        response = client.get('/api/v2/metrics')
        
        assert response.status_code == 200
        data = response.json()
        assert 'processing' in data
        assert 'system' in data
        assert 'timestamp' in data
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self, client, mock_services):
        """Test WebSocket connection for progress updates."""
        with client.websocket_connect('/ws/progress/test_video_id') as websocket:
            # Send test message
            test_message = {
                'type': 'progress_update',
                'data': {
                    'progress': 25.0,
                    'status': 'processing',
                    'current_step': 'transcription'
                }
            }
            
            # Mock WebSocket service to send message
            mock_services['websocket'].broadcast_progress_update = AsyncMock()
            
            # Simulate receiving message
            data = websocket.receive_json()
            assert 'type' in data
            assert 'data' in data


class TestCeleryTaskIntegration:
    """Test Celery task integration."""
    
    @pytest.fixture
    def mock_services(self):
        """Mock all services for Celery tasks."""
        with patch('api.services.enhanced_celery_tasks.redis_service') as mock_redis, \
             patch('api.services.enhanced_celery_tasks.websocket_service') as mock_ws, \
             patch('api.services.enhanced_celery_tasks.video_processor') as mock_processor, \
             patch('api.services.enhanced_celery_tasks.ai_service') as mock_ai:
            
            # Setup mocks
            mock_redis.health_check.return_value = True
            mock_processor.extract_metadata = AsyncMock(return_value=Mock(
                duration=120.0, width=1920, height=1080, fps=30.0, file_size=1000000
            ))
            mock_processor.extract_audio = AsyncMock(return_value='/tmp/audio.wav')
            mock_ai.transcribe_audio = AsyncMock(return_value=[])
            mock_ai.analyze_content_moments = AsyncMock(return_value=[])
            
            yield {
                'redis': mock_redis,
                'websocket': mock_ws,
                'processor': mock_processor,
                'ai': mock_ai
            }
    
    def test_health_check_task(self):
        """Test health check task."""
        with patch('api.services.enhanced_celery_tasks.redis_service') as mock_redis:
            mock_redis.health_check.return_value = True
            
            result = health_check_task.apply()
            
            assert result.successful()
            assert result.result['status'] == 'healthy'
    
    def test_process_video_clips_task_success(self, mock_services):
        """Test successful video processing task."""
        task_data = {
            'video_path': '/path/to/video.mp4',
            'platform': 'tiktok',
            'clip_count': 2,
            'clip_duration': 30,
            'user_preferences': {'content_type': 'highlight'}
        }
        
        # Mock successful processing
        mock_services['processor'].process_video_chunk = AsyncMock(return_value=True)
        
        with patch('os.path.exists', return_value=True), \
             patch('tempfile.mkdtemp', return_value='/tmp/test'), \
             patch('shutil.rmtree'):
            
            result = process_video_clips_task.apply(args=[task_data])
            
            assert result.successful()
            assert 'clips' in result.result
            assert 'metadata' in result.result
    
    def test_process_video_clips_task_file_not_found(self, mock_services):
        """Test video processing task with missing file."""
        task_data = {
            'video_path': '/nonexistent/video.mp4',
            'platform': 'tiktok',
            'clip_count': 2,
            'clip_duration': 30
        }
        
        with patch('os.path.exists', return_value=False):
            result = process_video_clips_task.apply(args=[task_data])
            
            assert result.failed()
            assert 'not found' in str(result.result)
    
    def test_process_single_clip_task_success(self, mock_services):
        """Test successful single clip processing."""
        clip_data = {
            'input_path': '/path/to/video.mp4',
            'output_path': '/path/to/clip.mp4',
            'start_time': 10.0,
            'duration': 30.0,
            'platform': 'tiktok'
        }
        
        mock_services['processor'].process_video_chunk = AsyncMock(return_value=True)
        
        with patch('os.path.exists', return_value=True):
            result = process_single_clip_task.apply(args=[clip_data])
            
            assert result.successful()
            assert result.result['success'] is True
    
    def test_process_single_clip_task_failure(self, mock_services):
        """Test single clip processing failure."""
        clip_data = {
            'input_path': '/path/to/video.mp4',
            'output_path': '/path/to/clip.mp4',
            'start_time': 10.0,
            'duration': 30.0,
            'platform': 'tiktok'
        }
        
        mock_services['processor'].process_video_chunk = AsyncMock(
            side_effect=Exception("Processing failed")
        )
        
        with patch('os.path.exists', return_value=True):
            result = process_single_clip_task.apply(args=[clip_data])
            
            assert result.failed()
            assert 'Processing failed' in str(result.result)


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""
    
    @pytest.fixture
    def temp_dir(self):
        """Temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def test_video_file(self, temp_dir):
        """Create a test video file."""
        video_path = os.path.join(temp_dir, 'test_video.mp4')
        with open(video_path, 'wb') as f:
            f.write(b'fake video data' * 1000)  # Create a larger fake file
        return video_path
    
    @pytest.mark.asyncio
    async def test_complete_video_processing_workflow(self, test_video_file, temp_dir):
        """Test complete video processing from start to finish."""
        # Mock all external dependencies
        with patch('api.services.redis_service.RedisService') as mock_redis_class, \
             patch('api.services.enhanced_video_processor.EnhancedVideoProcessor') as mock_processor_class, \
             patch('api.services.ai_service.EnhancedAIService') as mock_ai_class, \
             patch('api.services.websocket_service.WebSocketService') as mock_ws_class:
            
            # Setup service mocks
            mock_redis = Mock()
            mock_redis_class.return_value = mock_redis
            mock_redis.health_check.return_value = True
            mock_redis.cache_video_metadata.return_value = True
            mock_redis.cache_transcription.return_value = True
            
            mock_processor = Mock()
            mock_processor_class.return_value = mock_processor
            mock_processor.health_check.return_value = True
            mock_processor.extract_metadata = AsyncMock(return_value=Mock(
                duration=120.0, width=1920, height=1080, fps=30.0, file_size=15000
            ))
            mock_processor.extract_audio = AsyncMock(return_value=os.path.join(temp_dir, 'audio.wav'))
            mock_processor.process_video_chunk = AsyncMock(return_value=True)
            
            mock_ai = Mock()
            mock_ai_class.return_value = mock_ai
            mock_ai.health_check.return_value = True
            mock_ai.transcribe_audio = AsyncMock(return_value=[
                Mock(text='Hello world', start_time=0.0, end_time=2.0),
                Mock(text='This is a test', start_time=2.0, end_time=4.0)
            ])
            mock_ai.analyze_content_moments = AsyncMock(return_value=[
                Mock(
                    start_time=10.0, end_time=40.0, content_type='highlight',
                    virality_score=Mock(overall=0.85), description='Exciting moment'
                )
            ])
            
            mock_ws = Mock()
            mock_ws_class.return_value = mock_ws
            mock_ws.broadcast_progress_update = AsyncMock()
            
            # Create pipeline
            config = ProcessingConfig(
                max_memory_usage=0.8,
                max_concurrent_clips=2,
                chunk_duration=60,
                temp_dir=temp_dir
            )
            
            pipeline = VideoProcessingPipeline(
                config=config,
                redis_service=mock_redis,
                websocket_service=mock_ws
            )
            
            # Test the workflow
            with patch('psutil.virtual_memory') as mock_memory:
                mock_memory.return_value.percent = 50.0
                
                # Check system resources
                resource_check = await pipeline.check_system_resources()
                assert resource_check is True
                
                # Verify all services are healthy
                assert mock_redis.health_check() is True
                assert mock_processor.health_check() is True
                assert mock_ai.health_check() is True
    
    def test_error_handling_workflow(self, test_video_file):
        """Test error handling throughout the workflow."""
        with patch('api.services.enhanced_video_processor.EnhancedVideoProcessor') as mock_processor_class:
            mock_processor = Mock()
            mock_processor_class.return_value = mock_processor
            
            # Simulate metadata extraction failure
            mock_processor.extract_metadata = AsyncMock(
                side_effect=Exception("Failed to extract metadata")
            )
            
            # Test that error is properly handled
            with pytest.raises(Exception, match="Failed to extract metadata"):
                asyncio.run(mock_processor.extract_metadata(test_video_file))
    
    @pytest.mark.asyncio
    async def test_resource_exhaustion_handling(self, test_video_file):
        """Test handling of resource exhaustion scenarios."""
        config = ProcessingConfig(
            max_memory_usage=0.8,
            max_concurrent_clips=2,
            chunk_duration=60,
            temp_dir=tempfile.mkdtemp()
        )
        
        pipeline = VideoProcessingPipeline(
            config=config,
            redis_service=Mock(),
            websocket_service=Mock()
        )
        
        # Simulate high memory usage
        with patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value.percent = 95.0  # Very high memory usage
            
            with pytest.raises(ResourceExhaustionError):
                await pipeline.check_system_resources()


class TestPerformanceAndStress:
    """Performance and stress testing."""
    
    @pytest.mark.asyncio
    async def test_concurrent_processing_performance(self):
        """Test performance under concurrent processing load."""
        import time
        
        # Mock services for performance testing
        with patch('api.services.enhanced_video_processor.EnhancedVideoProcessor') as mock_processor_class:
            mock_processor = Mock()
            mock_processor_class.return_value = mock_processor
            mock_processor.process_video_chunk = AsyncMock(return_value=True)
            
            # Simulate processing multiple clips concurrently
            async def process_clip(clip_id):
                await mock_processor.process_video_chunk(
                    input_path=f'input_{clip_id}.mp4',
                    output_path=f'output_{clip_id}.mp4',
                    start_time=0.0,
                    duration=30.0,
                    platform='tiktok'
                )
                return f'clip_{clip_id}'
            
            start_time = time.time()
            
            # Process 10 clips concurrently
            tasks = [process_clip(i) for i in range(10)]
            results = await asyncio.gather(*tasks)
            
            end_time = time.time()
            duration = end_time - start_time
            
            assert len(results) == 10
            assert all(result.startswith('clip_') for result in results)
            # Should complete quickly with mocked operations
            assert duration < 1.0
    
    def test_memory_usage_monitoring(self):
        """Test memory usage monitoring and limits."""
        config = ProcessingConfig(
            max_memory_usage=0.7,  # 70% limit
            max_concurrent_clips=4,
            chunk_duration=60,
            temp_dir=tempfile.mkdtemp()
        )
        
        pipeline = VideoProcessingPipeline(
            config=config,
            redis_service=Mock(),
            websocket_service=Mock()
        )
        
        # Test memory monitoring
        with patch('psutil.virtual_memory') as mock_memory:
            # Test normal memory usage
            mock_memory.return_value.percent = 60.0
            result = asyncio.run(pipeline.check_system_resources())
            assert result is True
            
            # Test high memory usage
            mock_memory.return_value.percent = 80.0
            with pytest.raises(ResourceExhaustionError):
                asyncio.run(pipeline.check_system_resources())
    
    def test_large_file_handling(self):
        """Test handling of large video files."""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            # Create a large fake file (100MB)
            temp_file.write(b'0' * (100 * 1024 * 1024))
            temp_path = temp_file.name
        
        try:
            with patch('api.services.enhanced_video_processor.EnhancedVideoProcessor') as mock_processor_class:
                mock_processor = Mock()
                mock_processor_class.return_value = mock_processor
                mock_processor.extract_metadata = AsyncMock(return_value=Mock(
                    duration=3600.0,  # 1 hour video
                    width=1920,
                    height=1080,
                    fps=30.0,
                    file_size=100 * 1024 * 1024
                ))
                
                # Test metadata extraction for large file
                result = asyncio.run(mock_processor.extract_metadata(temp_path))
                assert result.duration == 3600.0
                assert result.file_size == 100 * 1024 * 1024
                
        finally:
            os.unlink(temp_path)


class TestConfigurationValidation:
    """Test configuration validation and system compatibility."""
    
    def test_configuration_validation_success(self):
        """Test successful configuration validation."""
        with patch('api.utils.config.detect_ffmpeg_path') as mock_detect, \
             patch.dict(os.environ, {
                 'REDIS_HOST': 'localhost',
                 'REDIS_PORT': '6379',
                 'CELERY_BROKER_URL': 'redis://localhost:6379/0'
             }):
            
            mock_detect.return_value = Mock(
                ffmpeg_path='ffmpeg',
                ffprobe_path='ffprobe',
                available=True,
                version='4.4.0'
            )
            
            result = validate_configuration()
            
            assert result['valid'] is True
            assert len(result['errors']) == 0
    
    def test_configuration_validation_missing_ffmpeg(self):
        """Test configuration validation with missing FFmpeg."""
        with patch('api.utils.config.detect_ffmpeg_path') as mock_detect:
            mock_detect.return_value = Mock(
                ffmpeg_path=None,
                ffprobe_path=None,
                available=False,
                version=None
            )
            
            result = validate_configuration()
            
            assert result['valid'] is False
            assert any('FFmpeg' in error for error in result['errors'])
    
    def test_system_requirements_check(self):
        """Test system requirements validation."""
        with patch('psutil.cpu_count') as mock_cpu, \
             patch('psutil.virtual_memory') as mock_memory:
            
            # Test sufficient resources
            mock_cpu.return_value = 8
            mock_memory.return_value.total = 16 * 1024**3  # 16GB
            
            from api.utils.config import get_system_info
            system_info = get_system_info()
            
            assert system_info['cpu_count_logical'] == 8
            assert system_info['memory_total_gb'] == 16.0
            
            # Test insufficient resources
            mock_cpu.return_value = 2
            mock_memory.return_value.total = 2 * 1024**3  # 2GB
            
            system_info = get_system_info()
            
            assert system_info['cpu_count_logical'] == 2
            assert system_info['memory_total_gb'] == 2.0


if __name__ == '__main__':
    # Run integration tests
    pytest.main([__file__, '-v', '--tb=short', '-x'])