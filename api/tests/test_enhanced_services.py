"""Comprehensive unit tests for enhanced video processing services.

This module provides:
- Unit tests for all enhanced services
- Integration tests for the video processing pipeline
- Performance benchmarks
- Error handling validation
- Mock data and fixtures
"""

import os
import pytest
import asyncio
import tempfile
import shutil
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
from typing import Dict, Any

# Test imports
from api.services.redis_service import RedisService
from api.services.ai_service import EnhancedAIService, TranscriptionSegment, ViralityScore
from api.services.enhanced_video_processor import EnhancedVideoProcessor, VideoMetadata
from api.services.websocket_service import WebSocketService, MessageType
from api.core.video_pipeline import VideoProcessingPipeline, ProcessingConfig
from api.core.exceptions import (
    VideoProcessingError, ResourceExhaustionError, TranscriptionError,
    SegmentationError, EncodingError, ValidationError
)
from api.utils.retry import exponential_backoff_retry, CircuitBreaker
from api.utils.config import (
    FFmpegConfig, CeleryConfig, RedisConfig, ProcessingConfig as UtilsProcessingConfig,
    validate_configuration, get_system_info
)


class TestRedisService:
    """Test Redis service functionality."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        with patch('redis.Redis') as mock_redis:
            mock_client = Mock()
            mock_redis.return_value = mock_client
            yield mock_client
    
    @pytest.fixture
    def redis_service(self, mock_redis):
        """Redis service with mocked client."""
        return RedisService()
    
    def test_redis_service_initialization(self, redis_service):
        """Test Redis service initialization."""
        assert redis_service is not None
        assert hasattr(redis_service, 'client')
        assert hasattr(redis_service, 'async_client')
    
    def test_set_and_get(self, redis_service, mock_redis):
        """Test basic set and get operations."""
        mock_redis.get.return_value = b'test_value'
        mock_redis.set.return_value = True
        
        # Test set
        result = redis_service.set('test_key', 'test_value')
        assert result is True
        mock_redis.set.assert_called_once()
        
        # Test get
        result = redis_service.get('test_key')
        assert result == 'test_value'
        mock_redis.get.assert_called_once_with('test_key')
    
    @pytest.mark.asyncio
    async def test_async_operations(self, redis_service):
        """Test async Redis operations."""
        with patch.object(redis_service, 'async_client') as mock_async_client:
            mock_async_client.set = AsyncMock(return_value=True)
            mock_async_client.get = AsyncMock(return_value=b'async_value')
            
            # Test async set
            result = await redis_service.aset('async_key', 'async_value')
            assert result is True
            
            # Test async get
            result = await redis_service.aget('async_key')
            assert result == 'async_value'
    
    def test_caching_methods(self, redis_service, mock_redis):
        """Test specialized caching methods."""
        mock_redis.set.return_value = True
        mock_redis.get.return_value = b'{"duration": 120.5}'
        
        # Test video metadata caching
        metadata = {'duration': 120.5, 'fps': 30}
        result = redis_service.cache_video_metadata('video123', metadata)
        assert result is True
        
        # Test transcription caching
        transcription = [{'text': 'Hello world', 'start': 0.0, 'end': 2.0}]
        result = redis_service.cache_transcription('video123', transcription)
        assert result is True
    
    def test_health_check(self, redis_service, mock_redis):
        """Test Redis health check."""
        mock_redis.ping.return_value = True
        
        result = redis_service.health_check()
        assert result is True
        mock_redis.ping.assert_called_once()
    
    def test_health_check_failure(self, redis_service, mock_redis):
        """Test Redis health check failure."""
        mock_redis.ping.side_effect = Exception("Connection failed")
        
        result = redis_service.health_check()
        assert result is False


class TestEnhancedAIService:
    """Test Enhanced AI service functionality."""
    
    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client."""
        with patch('openai.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            yield mock_client
    
    @pytest.fixture
    def ai_service(self, mock_openai_client):
        """AI service with mocked OpenAI client."""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            return EnhancedAIService()
    
    def test_ai_service_initialization(self, ai_service):
        """Test AI service initialization."""
        assert ai_service is not None
        assert hasattr(ai_service, 'client')
        assert ai_service.model_whisper == 'whisper-1'
        assert ai_service.model_gpt == 'gpt-4-1106-preview'
    
    @pytest.mark.asyncio
    async def test_transcribe_audio(self, ai_service, mock_openai_client):
        """Test audio transcription."""
        # Mock transcription response
        mock_response = Mock()
        mock_response.segments = [
            Mock(text='Hello world', start=0.0, end=2.0),
            Mock(text='This is a test', start=2.0, end=4.0)
        ]
        mock_openai_client.audio.transcriptions.create.return_value = mock_response
        
        # Create temporary audio file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_file.write(b'fake audio data')
            temp_path = temp_file.name
        
        try:
            result = await ai_service.transcribe_audio(temp_path)
            
            assert isinstance(result, list)
            assert len(result) == 2
            assert all(isinstance(segment, TranscriptionSegment) for segment in result)
            assert result[0].text == 'Hello world'
            assert result[0].start_time == 0.0
            assert result[0].end_time == 2.0
            
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_analyze_content_moments(self, ai_service, mock_openai_client):
        """Test content moment analysis."""
        # Mock GPT response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
        {
            "moments": [
                {
                    "start_time": 10.0,
                    "end_time": 40.0,
                    "content_type": "highlight",
                    "description": "Exciting moment",
                    "virality_score": {
                        "overall": 0.85,
                        "engagement": 0.9,
                        "shareability": 0.8,
                        "retention": 0.85
                    },
                    "keywords": ["exciting", "moment"]
                }
            ]
        }
        '''
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        # Test data
        transcription = [
            TranscriptionSegment(text='This is an exciting moment', start_time=10.0, end_time=40.0)
        ]
        
        result = await ai_service.analyze_content_moments(
            transcription=transcription,
            platform='tiktok',
            duration=60.0
        )
        
        assert isinstance(result, list)
        assert len(result) == 1
        moment = result[0]
        assert moment.start_time == 10.0
        assert moment.end_time == 40.0
        assert moment.content_type == 'highlight'
        assert isinstance(moment.virality_score, ViralityScore)
        assert moment.virality_score.overall == 0.85
    
    def test_health_check(self, ai_service):
        """Test AI service health check."""
        result = ai_service.health_check()
        assert isinstance(result, bool)


class TestEnhancedVideoProcessor:
    """Test Enhanced Video Processor functionality."""
    
    @pytest.fixture
    def video_processor(self):
        """Video processor instance."""
        return EnhancedVideoProcessor()
    
    def test_video_processor_initialization(self, video_processor):
        """Test video processor initialization."""
        assert video_processor is not None
        assert hasattr(video_processor, 'ffmpeg_path')
        assert hasattr(video_processor, 'ffprobe_path')
        assert hasattr(video_processor, 'gpu_acceleration')
    
    @pytest.mark.asyncio
    async def test_extract_metadata(self, video_processor):
        """Test video metadata extraction."""
        # Mock ffprobe output
        mock_output = '''
        {
            "streams": [
                {
                    "codec_type": "video",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "30/1",
                    "duration": "120.5"
                },
                {
                    "codec_type": "audio",
                    "sample_rate": "44100",
                    "channels": 2
                }
            ],
            "format": {
                "duration": "120.5",
                "size": "52428800"
            }
        }
        '''
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = Mock()
            mock_process.communicate.return_value = (mock_output.encode(), b'')
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await video_processor.extract_metadata('test_video.mp4')
            
            assert isinstance(result, VideoMetadata)
            assert result.duration == 120.5
            assert result.width == 1920
            assert result.height == 1080
            assert result.fps == 30.0
            assert result.file_size == 52428800
    
    @pytest.mark.asyncio
    async def test_process_video_chunk(self, video_processor):
        """Test video chunk processing."""
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = Mock()
            mock_process.communicate.return_value = (b'', b'')
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await video_processor.process_video_chunk(
                input_path='input.mp4',
                output_path='output.mp4',
                start_time=10.0,
                duration=30.0,
                platform='tiktok'
            )
            
            assert result is True
            mock_subprocess.assert_called_once()
    
    def test_health_check(self, video_processor):
        """Test video processor health check."""
        result = video_processor.health_check()
        assert isinstance(result, bool)


class TestWebSocketService:
    """Test WebSocket service functionality."""
    
    @pytest.fixture
    def mock_redis_service(self):
        """Mock Redis service."""
        mock_redis = Mock(spec=RedisService)
        mock_redis.health_check.return_value = True
        return mock_redis
    
    @pytest.fixture
    def websocket_service(self, mock_redis_service):
        """WebSocket service with mocked Redis."""
        return WebSocketService(redis_service=mock_redis_service)
    
    @pytest.mark.asyncio
    async def test_websocket_service_initialization(self, websocket_service):
        """Test WebSocket service initialization."""
        assert websocket_service is not None
        assert hasattr(websocket_service, 'clients')
        assert hasattr(websocket_service, 'redis_service')
    
    @pytest.mark.asyncio
    async def test_add_remove_client(self, websocket_service):
        """Test client management."""
        mock_websocket = Mock()
        
        # Add client
        client_id = await websocket_service.add_client(mock_websocket, 'video123')
        assert client_id is not None
        assert len(websocket_service.clients) == 1
        
        # Remove client
        await websocket_service.remove_client(client_id)
        assert len(websocket_service.clients) == 0
    
    @pytest.mark.asyncio
    async def test_broadcast_message(self, websocket_service):
        """Test message broadcasting."""
        mock_websocket = Mock()
        mock_websocket.send_text = AsyncMock()
        
        # Add client
        client_id = await websocket_service.add_client(mock_websocket, 'video123')
        
        # Broadcast message
        await websocket_service.broadcast_progress_update(
            'video123',
            {'progress': 50.0, 'status': 'processing'}
        )
        
        # Verify message was sent
        mock_websocket.send_text.assert_called_once()


class TestVideoProcessingPipeline:
    """Test Video Processing Pipeline functionality."""
    
    @pytest.fixture
    def processing_config(self):
        """Processing configuration."""
        return ProcessingConfig(
            max_memory_usage=0.8,
            max_concurrent_clips=2,
            chunk_duration=60,
            temp_dir=tempfile.mkdtemp()
        )
    
    @pytest.fixture
    def mock_services(self):
        """Mock services."""
        redis_service = Mock(spec=RedisService)
        websocket_service = Mock(spec=WebSocketService)
        return redis_service, websocket_service
    
    @pytest.fixture
    def video_pipeline(self, processing_config, mock_services):
        """Video processing pipeline."""
        redis_service, websocket_service = mock_services
        return VideoProcessingPipeline(
            config=processing_config,
            redis_service=redis_service,
            websocket_service=websocket_service
        )
    
    def test_pipeline_initialization(self, video_pipeline):
        """Test pipeline initialization."""
        assert video_pipeline is not None
        assert hasattr(video_pipeline, 'config')
        assert hasattr(video_pipeline, 'redis_service')
        assert hasattr(video_pipeline, 'websocket_service')
    
    @pytest.mark.asyncio
    async def test_resource_monitoring(self, video_pipeline):
        """Test resource monitoring."""
        with patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value.percent = 70.0
            
            result = await video_pipeline.check_system_resources()
            assert result is True
            
            # Test memory exhaustion
            mock_memory.return_value.percent = 90.0
            
            with pytest.raises(ResourceExhaustionError):
                await video_pipeline.check_system_resources()


class TestExceptions:
    """Test custom exceptions."""
    
    def test_video_processing_error(self):
        """Test VideoProcessingError."""
        error = VideoProcessingError("Test error", error_code="TEST_001")
        assert str(error) == "Test error"
        assert error.error_code == "TEST_001"
        
        error_dict = error.to_dict()
        assert error_dict['error'] == "Test error"
        assert error_dict['error_code'] == "TEST_001"
    
    def test_resource_exhaustion_error(self):
        """Test ResourceExhaustionError."""
        error = ResourceExhaustionError("Memory exhausted", resource_type="memory", current_usage=90.0)
        assert error.resource_type == "memory"
        assert error.current_usage == 90.0
    
    def test_transcription_error(self):
        """Test TranscriptionError."""
        error = TranscriptionError("Transcription failed", audio_path="/path/to/audio.wav")
        assert error.audio_path == "/path/to/audio.wav"


class TestRetryUtilities:
    """Test retry utilities."""
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_retry_success(self):
        """Test successful retry."""
        call_count = 0
        
        async def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = await exponential_backoff_retry(
            test_function,
            max_retries=5,
            base_delay=0.01
        )
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_retry_failure(self):
        """Test retry exhaustion."""
        async def test_function():
            raise Exception("Persistent failure")
        
        with pytest.raises(Exception, match="Persistent failure"):
            await exponential_backoff_retry(
                test_function,
                max_retries=3,
                base_delay=0.01
            )
    
    def test_circuit_breaker(self):
        """Test circuit breaker functionality."""
        circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=1.0,
            expected_exception=Exception
        )
        
        # Test closed state
        assert circuit_breaker.state == 'closed'
        
        # Trigger failures
        for _ in range(3):
            circuit_breaker.record_failure()
        
        # Should be open now
        assert circuit_breaker.state == 'open'
        
        # Test call blocking
        with pytest.raises(Exception, match="Circuit breaker is open"):
            circuit_breaker.call(lambda: "test")


class TestConfiguration:
    """Test configuration utilities."""
    
    def test_ffmpeg_config(self):
        """Test FFmpeg configuration."""
        config = FFmpegConfig(
            ffmpeg_path='/usr/bin/ffmpeg',
            ffprobe_path='/usr/bin/ffprobe',
            available=True,
            version='4.4.0'
        )
        
        assert config.ffmpeg_path == '/usr/bin/ffmpeg'
        assert config.available is True
        
        config_dict = config.to_dict()
        assert config_dict['ffmpeg_path'] == '/usr/bin/ffmpeg'
        assert config_dict['available'] is True
    
    def test_celery_config(self):
        """Test Celery configuration."""
        config = CeleryConfig(
            broker_url='redis://localhost:6379/0',
            result_backend='redis://localhost:6379/0'
        )
        
        assert config.broker_url == 'redis://localhost:6379/0'
        assert config.worker_concurrency == 4
        assert config.task_routes is not None
    
    def test_redis_config(self):
        """Test Redis configuration."""
        config = RedisConfig(
            host='localhost',
            port=6379,
            password='secret'
        )
        
        assert config.get_url() == 'redis://:secret@localhost:6379/0'
    
    def test_validate_configuration(self):
        """Test configuration validation."""
        with patch('api.utils.config.detect_ffmpeg_path') as mock_detect:
            mock_detect.return_value = FFmpegConfig(
                ffmpeg_path='ffmpeg',
                ffprobe_path='ffprobe',
                available=True
            )
            
            result = validate_configuration()
            assert isinstance(result, dict)
            assert 'valid' in result
            assert 'errors' in result
            assert 'warnings' in result
    
    def test_get_system_info(self):
        """Test system information gathering."""
        with patch('psutil.cpu_count') as mock_cpu, \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            mock_cpu.return_value = 8
            mock_memory.return_value.total = 16 * 1024**3  # 16GB
            mock_memory.return_value.percent = 60.0
            mock_disk.return_value.total = 1024 * 1024**3  # 1TB
            mock_disk.return_value.percent = 50.0
            
            result = get_system_info()
            assert isinstance(result, dict)
            assert 'cpu_count_logical' in result
            assert 'memory_total_gb' in result
            assert 'disk_total_gb' in result


class TestPerformanceBenchmarks:
    """Performance benchmark tests."""
    
    @pytest.mark.asyncio
    async def test_redis_performance(self):
        """Test Redis operation performance."""
        with patch('redis.Redis') as mock_redis:
            mock_client = Mock()
            mock_redis.return_value = mock_client
            mock_client.set.return_value = True
            mock_client.get.return_value = b'test_value'
            
            redis_service = RedisService()
            
            import time
            start_time = time.time()
            
            # Perform 100 operations
            for i in range(100):
                redis_service.set(f'key_{i}', f'value_{i}')
                redis_service.get(f'key_{i}')
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Should complete in reasonable time
            assert duration < 1.0  # Less than 1 second for 100 operations
    
    @pytest.mark.asyncio
    async def test_ai_service_performance(self):
        """Test AI service performance."""
        with patch('openai.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            
            # Mock fast response
            mock_response = Mock()
            mock_response.segments = []
            mock_client.audio.transcriptions.create.return_value = mock_response
            
            ai_service = EnhancedAIService()
            
            # Create temporary audio file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(b'fake audio data')
                temp_path = temp_file.name
            
            try:
                import time
                start_time = time.time()
                
                await ai_service.transcribe_audio(temp_path)
                
                end_time = time.time()
                duration = end_time - start_time
                
                # Should complete quickly with mocked response
                assert duration < 0.1  # Less than 100ms
                
            finally:
                os.unlink(temp_path)


class TestIntegration:
    """Integration tests for the complete system."""
    
    @pytest.fixture
    def temp_dir(self):
        """Temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.mark.asyncio
    async def test_end_to_end_processing(self, temp_dir):
        """Test end-to-end video processing workflow."""
        # Create mock video file
        video_path = os.path.join(temp_dir, 'test_video.mp4')
        with open(video_path, 'wb') as f:
            f.write(b'fake video data')
        
        # Mock all services
        with patch('api.services.redis_service.RedisService') as mock_redis, \
             patch('api.services.enhanced_video_processor.EnhancedVideoProcessor') as mock_processor, \
             patch('api.services.ai_service.EnhancedAIService') as mock_ai:
            
            # Setup mocks
            mock_redis_instance = Mock()
            mock_redis.return_value = mock_redis_instance
            mock_redis_instance.health_check.return_value = True
            
            mock_processor_instance = Mock()
            mock_processor.return_value = mock_processor_instance
            mock_processor_instance.health_check.return_value = True
            mock_processor_instance.extract_metadata = AsyncMock(return_value=VideoMetadata(
                duration=120.0, width=1920, height=1080, fps=30.0, file_size=1000000
            ))
            
            mock_ai_instance = Mock()
            mock_ai.return_value = mock_ai_instance
            mock_ai_instance.health_check.return_value = True
            mock_ai_instance.transcribe_audio = AsyncMock(return_value=[])
            mock_ai_instance.analyze_content_moments = AsyncMock(return_value=[])
            
            # Create pipeline
            config = ProcessingConfig(
                max_memory_usage=0.8,
                max_concurrent_clips=2,
                chunk_duration=60,
                temp_dir=temp_dir
            )
            
            pipeline = VideoProcessingPipeline(
                config=config,
                redis_service=mock_redis_instance,
                websocket_service=None
            )
            
            # Test pipeline health
            assert pipeline is not None
            
            # Test resource check
            with patch('psutil.virtual_memory') as mock_memory:
                mock_memory.return_value.percent = 50.0
                result = await pipeline.check_system_resources()
                assert result is True


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v', '--tb=short'])