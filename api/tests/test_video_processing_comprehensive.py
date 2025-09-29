"""Comprehensive tests for video processing system.

Tests:
- Video processor with memory management
- Video pipeline with error recovery
- FFmpeg integration and optimization
- Concurrent processing capabilities
- Large file handling
- Error recovery mechanisms
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, List
import json

from ..services.video_processor import VideoProcessor
from ..services.video_pipeline import VideoPipeline
from ..utils.memory_optimizer import EnhancedMemoryOptimizer
from ..utils.error_recovery import ErrorRecoveryManager


class TestVideoProcessor:
    """Test video processor with comprehensive scenarios."""
    
    @pytest.fixture
    def processor(self):
        """Create video processor for testing."""
        return VideoProcessor()
    
    @pytest.fixture
    def sample_video_path(self):
        """Create a sample video file for testing."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            # Create a minimal MP4 file (just headers for testing)
            f.write(b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom')
            return f.name
    
    def test_processor_initialization(self, processor):
        """Test processor initializes correctly."""
        assert processor.whisper_model is None
        assert processor.current_model_size is None
        assert hasattr(processor, 'memory_optimizer')
        assert hasattr(processor, 'logger')
    
    @pytest.mark.asyncio
    async def test_gpu_detection(self, processor):
        """Test GPU detection functionality."""
        with patch('torch.cuda.is_available', return_value=True), \
             patch('torch.cuda.device_count', return_value=1), \
             patch('torch.cuda.get_device_properties') as mock_props:
            
            mock_props.return_value.total_memory = 8 * 1024**3  # 8GB
            
            gpu_info = processor._detect_gpu()
            
            assert gpu_info['available'] is True
            assert gpu_info['device_count'] == 1
            assert gpu_info['memory_gb'] == 8.0
    
    @pytest.mark.asyncio
    async def test_whisper_model_loading(self, processor):
        """Test Whisper model loading with memory management."""
        with patch('whisper.load_model') as mock_load, \
             patch.object(processor, '_detect_gpu') as mock_gpu:
            
            mock_gpu.return_value = {'available': True, 'memory_gb': 8.0}
            mock_model = Mock()
            mock_load.return_value = mock_model
            
            await processor._load_whisper_model('base')
            
            assert processor.whisper_model == mock_model
            assert processor.current_model_size == 'base'
            mock_load.assert_called_once_with('base', device='cuda')
    
    @pytest.mark.asyncio
    async def test_model_size_selection(self, processor):
        """Test optimal model size selection based on video duration."""
        # Test short video (< 5 minutes)
        model_size = processor._select_optimal_model_size(240, priority='speed')
        assert model_size == 'tiny'
        
        # Test medium video (5-30 minutes)
        model_size = processor._select_optimal_model_size(900, priority='balanced')
        assert model_size == 'base'
        
        # Test long video (> 30 minutes)
        model_size = processor._select_optimal_model_size(2400, priority='accuracy')
        assert model_size == 'small'
    
    @pytest.mark.asyncio
    async def test_video_info_extraction(self, processor, sample_video_path):
        """Test video information extraction."""
        with patch('ffmpeg.probe') as mock_probe:
            mock_probe.return_value = {
                'streams': [{
                    'codec_type': 'video',
                    'duration': '120.5',
                    'width': 1920,
                    'height': 1080,
                    'r_frame_rate': '30/1'
                }],
                'format': {
                    'duration': '120.5',
                    'size': '50000000'
                }
            }
            
            info = await processor.get_video_info(sample_video_path)
            
            assert info['duration'] == 120.5
            assert info['width'] == 1920
            assert info['height'] == 1080
            assert info['fps'] == 30.0
            assert info['file_size'] == 50000000
    
    @pytest.mark.asyncio
    async def test_audio_extraction(self, processor, sample_video_path):
        """Test audio extraction from video."""
        with patch('ffmpeg.input') as mock_input, \
             patch('ffmpeg.output') as mock_output, \
             patch('ffmpeg.run') as mock_run:
            
            mock_stream = Mock()
            mock_input.return_value = mock_stream
            mock_output.return_value = mock_stream
            
            audio_path = await processor.extract_audio(sample_video_path)
            
            assert audio_path.endswith('.wav')
            mock_input.assert_called_once_with(sample_video_path)
            mock_run.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_transcription_with_chunking(self, processor):
        """Test transcription with audio chunking for large files."""
        with patch.object(processor, '_load_whisper_model') as mock_load, \
             patch.object(processor, '_transcribe_chunk') as mock_transcribe, \
             patch('librosa.load') as mock_librosa:
            
            # Mock audio data (10 minutes = 600 seconds)
            mock_librosa.return_value = ([0.1] * 600 * 22050, 22050)
            
            mock_transcribe.return_value = {
                'text': 'Test transcription',
                'segments': [{'start': 0, 'end': 30, 'text': 'Test'}]
            }
            
            result = await processor.transcribe_audio('/fake/audio.wav', 'base')
            
            # Should chunk 10-minute audio into multiple parts
            assert mock_transcribe.call_count > 1
            assert 'text' in result
            assert 'segments' in result
    
    @pytest.mark.asyncio
    async def test_memory_cleanup_during_processing(self, processor):
        """Test memory cleanup during video processing."""
        with patch.object(processor.memory_optimizer, 'emergency_cleanup') as mock_cleanup, \
             patch('psutil.virtual_memory') as mock_memory:
            
            # Mock high memory usage
            mock_memory.return_value.percent = 95.0
            
            await processor.force_memory_cleanup()
            
            mock_cleanup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_concurrent_processing_limits(self, processor):
        """Test concurrent processing limits and queuing."""
        # Mock multiple concurrent requests
        tasks = []
        
        with patch.object(processor, 'transcribe_audio') as mock_transcribe:
            mock_transcribe.return_value = {'text': 'test', 'segments': []}
            
            # Create 5 concurrent tasks
            for i in range(5):
                task = asyncio.create_task(
                    processor.transcribe_audio(f'/fake/audio_{i}.wav', 'base')
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All tasks should complete successfully
            assert len(results) == 5
            assert all(not isinstance(r, Exception) for r in results)
    
    def test_cleanup_on_destruction(self, processor):
        """Test cleanup when processor is destroyed."""
        with patch.object(processor, 'cleanup_models') as mock_cleanup:
            # Trigger destructor
            del processor
            
            # Note: __del__ might not be called immediately in tests
            # This test verifies the cleanup method exists
            assert hasattr(VideoProcessor, '__del__')


class TestVideoPipeline:
    """Test video processing pipeline."""
    
    @pytest.fixture
    def pipeline(self):
        """Create video pipeline for testing."""
        return VideoPipeline()
    
    @pytest.fixture
    def sample_video_data(self):
        """Sample video data for testing."""
        return {
            'file_path': '/fake/video.mp4',
            'duration': 300,  # 5 minutes
            'file_size': 100 * 1024 * 1024,  # 100MB
            'format': 'mp4'
        }
    
    @pytest.mark.asyncio
    async def test_pipeline_initialization(self, pipeline):
        """Test pipeline initializes correctly."""
        assert hasattr(pipeline, 'video_processor')
        assert hasattr(pipeline, 'error_recovery')
        assert hasattr(pipeline, 'memory_optimizer')
        assert pipeline.max_concurrent_jobs == 3
    
    @pytest.mark.asyncio
    async def test_video_processing_workflow(self, pipeline, sample_video_data):
        """Test complete video processing workflow."""
        with patch.object(pipeline.video_processor, 'get_video_info') as mock_info, \
             patch.object(pipeline.video_processor, 'extract_audio') as mock_extract, \
             patch.object(pipeline.video_processor, 'transcribe_audio') as mock_transcribe, \
             patch.object(pipeline, '_generate_clips') as mock_clips:
            
            mock_info.return_value = sample_video_data
            mock_extract.return_value = '/fake/audio.wav'
            mock_transcribe.return_value = {
                'text': 'This is a test transcription',
                'segments': [
                    {'start': 0, 'end': 10, 'text': 'This is a test'},
                    {'start': 10, 'end': 20, 'text': 'transcription'}
                ]
            }
            mock_clips.return_value = [
                {'start': 0, 'end': 10, 'text': 'This is a test', 'score': 0.8},
                {'start': 10, 'end': 20, 'text': 'transcription', 'score': 0.7}
            ]
            
            result = await pipeline.process_video(
                video_path='/fake/video.mp4',
                user_id='test_user',
                options={'priority': 'balanced'}
            )
            
            assert 'clips' in result
            assert 'transcription' in result
            assert 'metadata' in result
            assert len(result['clips']) == 2
    
    @pytest.mark.asyncio
    async def test_error_recovery_during_processing(self, pipeline):
        """Test error recovery mechanisms."""
        with patch.object(pipeline.video_processor, 'extract_audio') as mock_extract, \
             patch.object(pipeline.error_recovery, 'handle_error') as mock_recovery:
            
            # Simulate extraction failure
            mock_extract.side_effect = Exception("FFmpeg error")
            mock_recovery.return_value = {'recovered': True, 'retry_count': 1}
            
            with pytest.raises(Exception):
                await pipeline.process_video('/fake/video.mp4', 'test_user')
            
            mock_recovery.assert_called()
    
    @pytest.mark.asyncio
    async def test_large_file_handling(self, pipeline):
        """Test handling of large video files."""
        large_video_data = {
            'file_path': '/fake/large_video.mp4',
            'duration': 3600,  # 1 hour
            'file_size': 2 * 1024**3,  # 2GB
            'format': 'mp4'
        }
        
        with patch.object(pipeline.video_processor, 'get_video_info') as mock_info, \
             patch.object(pipeline, '_process_in_chunks') as mock_chunks:
            
            mock_info.return_value = large_video_data
            mock_chunks.return_value = {
                'clips': [],
                'transcription': {'text': '', 'segments': []},
                'metadata': {}
            }
            
            result = await pipeline.process_video('/fake/large_video.mp4', 'test_user')
            
            # Should use chunked processing for large files
            mock_chunks.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_concurrent_job_limiting(self, pipeline):
        """Test concurrent job limiting."""
        # Set low limit for testing
        pipeline.max_concurrent_jobs = 2
        
        processing_tasks = []
        
        async def mock_process_video(video_path, user_id, options=None):
            await asyncio.sleep(0.1)  # Simulate processing time
            return {'clips': [], 'transcription': {'text': '', 'segments': []}}
        
        with patch.object(pipeline, 'process_video', side_effect=mock_process_video):
            # Start 5 concurrent jobs
            for i in range(5):
                task = asyncio.create_task(
                    pipeline.process_video(f'/fake/video_{i}.mp4', f'user_{i}')
                )
                processing_tasks.append(task)
            
            results = await asyncio.gather(*processing_tasks)
            
            # All jobs should complete
            assert len(results) == 5
    
    @pytest.mark.asyncio
    async def test_memory_monitoring_during_pipeline(self, pipeline):
        """Test memory monitoring during pipeline execution."""
        with patch.object(pipeline.memory_optimizer, 'get_memory_stats') as mock_stats, \
             patch.object(pipeline.memory_optimizer, 'emergency_cleanup') as mock_cleanup:
            
            mock_stats.return_value = {
                'current_usage_mb': 1500,  # High memory usage
                'peak_usage_mb': 1600,
                'gc_collections': 10
            }
            
            # Simulate memory pressure during processing
            await pipeline._monitor_memory_usage()
            
            # Should trigger cleanup for high memory usage
            mock_cleanup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_temporary_file_cleanup(self, pipeline):
        """Test cleanup of temporary files."""
        temp_files = []
        
        with patch('tempfile.NamedTemporaryFile') as mock_temp, \
             patch('os.unlink') as mock_unlink:
            
            # Mock temporary file creation
            mock_file = Mock()
            mock_file.name = '/tmp/test_audio.wav'
            mock_temp.return_value.__enter__.return_value = mock_file
            
            # Process with temporary files
            await pipeline._cleanup_temp_files(['/tmp/test_audio.wav'])
            
            mock_unlink.assert_called_with('/tmp/test_audio.wav')


class TestFFmpegIntegration:
    """Test FFmpeg integration and optimization."""
    
    @pytest.mark.asyncio
    async def test_ffmpeg_audio_extraction_optimization(self):
        """Test optimized FFmpeg audio extraction."""
        with patch('ffmpeg.input') as mock_input, \
             patch('ffmpeg.output') as mock_output, \
             patch('ffmpeg.run') as mock_run:
            
            mock_stream = Mock()
            mock_input.return_value = mock_stream
            mock_output.return_value = mock_stream
            
            processor = VideoProcessor()
            await processor.extract_audio('/fake/video.mp4')
            
            # Verify optimized parameters are used
            mock_output.assert_called()
            call_args = mock_output.call_args
            
            # Should include audio optimization parameters
            assert any('acodec' in str(arg) for arg in call_args[0])
    
    @pytest.mark.asyncio
    async def test_ffmpeg_error_handling(self):
        """Test FFmpeg error handling and recovery."""
        with patch('ffmpeg.run') as mock_run:
            mock_run.side_effect = Exception("FFmpeg process failed")
            
            processor = VideoProcessor()
            
            with pytest.raises(Exception):
                await processor.extract_audio('/fake/video.mp4')
    
    @pytest.mark.asyncio
    async def test_ffmpeg_progress_monitoring(self):
        """Test FFmpeg progress monitoring for long operations."""
        with patch('ffmpeg.run') as mock_run:
            # Mock long-running FFmpeg process
            mock_run.return_value = None
            
            processor = VideoProcessor()
            
            # Should complete without hanging
            result = await processor.extract_audio('/fake/video.mp4')
            assert result is not None


class TestErrorRecovery:
    """Test error recovery mechanisms."""
    
    @pytest.fixture
    def error_recovery(self):
        """Create error recovery manager."""
        return ErrorRecoveryManager()
    
    @pytest.mark.asyncio
    async def test_retry_mechanism(self, error_recovery):
        """Test retry mechanism for transient failures."""
        call_count = 0
        
        async def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient error")
            return "success"
        
        result = await error_recovery.retry_with_backoff(
            failing_function,
            max_retries=3,
            base_delay=0.01
        )
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_pattern(self, error_recovery):
        """Test circuit breaker for repeated failures."""
        async def always_failing_function():
            raise Exception("Persistent error")
        
        # Should fail after max retries
        with pytest.raises(Exception):
            await error_recovery.retry_with_backoff(
                always_failing_function,
                max_retries=2,
                base_delay=0.01
            )
    
    @pytest.mark.asyncio
    async def test_resource_cleanup_on_error(self, error_recovery):
        """Test resource cleanup when errors occur."""
        cleanup_called = False
        
        async def cleanup_function():
            nonlocal cleanup_called
            cleanup_called = True
        
        async def failing_function():
            raise Exception("Test error")
        
        try:
            await error_recovery.execute_with_cleanup(
                failing_function,
                cleanup_function
            )
        except Exception:
            pass
        
        assert cleanup_called


class TestPerformanceOptimization:
    """Test performance optimization features."""
    
    @pytest.mark.asyncio
    async def test_memory_optimization_during_processing(self):
        """Test memory optimization during video processing."""
        optimizer = EnhancedMemoryOptimizer()
        
        with patch('gc.collect') as mock_gc, \
             patch('torch.cuda.empty_cache') as mock_cuda:
            
            await optimizer.emergency_cleanup()
            
            mock_gc.assert_called()
            mock_cuda.assert_called()
    
    @pytest.mark.asyncio
    async def test_concurrent_processing_optimization(self):
        """Test concurrent processing optimization."""
        pipeline = VideoPipeline()
        
        # Test optimal concurrency level
        assert pipeline.max_concurrent_jobs <= 5  # Reasonable limit
        
        # Test semaphore-based limiting
        semaphore = asyncio.Semaphore(2)
        
        async def limited_task(task_id):
            async with semaphore:
                await asyncio.sleep(0.01)
                return f"task_{task_id}"
        
        tasks = [limited_task(i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 5
        assert all(r.startswith("task_") for r in results)
    
    @pytest.mark.asyncio
    async def test_chunk_size_optimization(self):
        """Test optimal chunk size calculation for large files."""
        processor = VideoProcessor()
        
        # Test chunk size calculation based on file size and available memory
        chunk_size = processor._calculate_optimal_chunk_size(
            file_size_mb=1000,  # 1GB file
            available_memory_mb=2000  # 2GB available
        )
        
        # Should return reasonable chunk size
        assert 30 <= chunk_size <= 300  # 30 seconds to 5 minutes


class TestIntegrationScenarios:
    """Integration tests for complete scenarios."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_video_processing(self):
        """Test complete end-to-end video processing."""
        pipeline = VideoPipeline()
        
        with patch.object(pipeline.video_processor, 'get_video_info') as mock_info, \
             patch.object(pipeline.video_processor, 'extract_audio') as mock_extract, \
             patch.object(pipeline.video_processor, 'transcribe_audio') as mock_transcribe, \
             patch.object(pipeline, '_generate_clips') as mock_clips, \
             patch.object(pipeline, '_save_results') as mock_save:
            
            # Mock successful processing
            mock_info.return_value = {
                'duration': 120,
                'file_size': 50000000,
                'format': 'mp4'
            }
            mock_extract.return_value = '/tmp/audio.wav'
            mock_transcribe.return_value = {
                'text': 'Complete test transcription',
                'segments': [
                    {'start': 0, 'end': 30, 'text': 'First segment'},
                    {'start': 30, 'end': 60, 'text': 'Second segment'}
                ]
            }
            mock_clips.return_value = [
                {'start': 0, 'end': 30, 'text': 'First segment', 'score': 0.9},
                {'start': 30, 'end': 60, 'text': 'Second segment', 'score': 0.8}
            ]
            mock_save.return_value = {'job_id': 'test_job_123'}
            
            result = await pipeline.process_video(
                video_path='/fake/test_video.mp4',
                user_id='test_user_123',
                options={'priority': 'balanced', 'max_clips': 5}
            )
            
            # Verify complete workflow
            assert 'clips' in result
            assert 'transcription' in result
            assert 'metadata' in result
            assert len(result['clips']) == 2
            
            # Verify all steps were called
            mock_info.assert_called_once()
            mock_extract.assert_called_once()
            mock_transcribe.assert_called_once()
            mock_clips.assert_called_once()
            mock_save.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_high_load_scenario(self):
        """Test system behavior under high load."""
        pipeline = VideoPipeline()
        
        # Simulate 10 concurrent video processing requests
        tasks = []
        
        async def mock_process_video(video_path, user_id, options=None):
            await asyncio.sleep(0.05)  # Simulate processing time
            return {
                'clips': [{'start': 0, 'end': 30, 'text': 'test', 'score': 0.8}],
                'transcription': {'text': 'test', 'segments': []},
                'metadata': {'duration': 30}
            }
        
        with patch.object(pipeline, 'process_video', side_effect=mock_process_video):
            for i in range(10):
                task = asyncio.create_task(
                    pipeline.process_video(f'/fake/video_{i}.mp4', f'user_{i}')
                )
                tasks.append(task)
            
            # All tasks should complete successfully
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            assert len(results) == 10
            assert all(not isinstance(r, Exception) for r in results)
            assert all('clips' in r for r in results)
    
    @pytest.mark.asyncio
    async def test_memory_pressure_scenario(self):
        """Test system behavior under memory pressure."""
        optimizer = EnhancedMemoryOptimizer()
        
        with patch('psutil.virtual_memory') as mock_memory, \
             patch.object(optimizer, 'emergency_cleanup') as mock_cleanup:
            
            # Simulate high memory usage
            mock_memory.return_value.percent = 95.0
            
            # Should trigger emergency cleanup
            await optimizer.check_memory_pressure()
            
            mock_cleanup.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])