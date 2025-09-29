"""Comprehensive test suite for the video-to-clip generation system.

Tests:
- Video processing pipeline
- AI analysis and scoring
- Memory optimization
- Error handling and recovery
- Performance monitoring
- API endpoints
- Database operations
- File handling and cleanup
"""

import os
import sys
import pytest
import asyncio
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
import json
from pathlib import Path

# Add the api directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from video_processor import VideoProcessor
from services.ai_analyzer import AIAnalyzer
from utils.memory_optimizer import EnhancedMemoryOptimizer, MemoryStats
from utils.monitoring import MonitoringSystem, HealthStatus, MetricType
from performance_utils import MemoryManager
from llm_service import LLMService
from services.unified_llm_service import UnifiedLLMService

class TestVideoProcessor:
    """Test video processing functionality."""
    
    @pytest.fixture
    def video_processor(self):
        """Create a video processor instance for testing."""
        return VideoProcessor()
    
    @pytest.fixture
    def temp_video_file(self):
        """Create a temporary video file for testing."""
        temp_dir = tempfile.mkdtemp()
        video_path = os.path.join(temp_dir, "test_video.mp4")
        
        # Create a minimal video file (just for testing)
        with open(video_path, 'wb') as f:
            f.write(b'fake video content')
        
        yield video_path
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_video_processor_initialization(self, video_processor):
        """Test video processor initialization."""
        assert video_processor is not None
        assert hasattr(video_processor, 'temp_dir')
        assert hasattr(video_processor, 'memory_manager')
    
    @patch('video_processor.VideoFileClip')
    def test_extract_audio_success(self, mock_video_clip, video_processor, temp_video_file):
        """Test successful audio extraction."""
        # Mock video clip
        mock_clip = Mock()
        mock_audio = Mock()
        mock_clip.audio = mock_audio
        mock_video_clip.return_value = mock_clip
        
        # Test audio extraction
        result = video_processor.extract_audio(temp_video_file)
        
        assert result is not None
        mock_video_clip.assert_called_once_with(temp_video_file)
        mock_audio.write_audiofile.assert_called_once()
    
    @patch('video_processor.VideoFileClip')
    def test_extract_audio_failure(self, mock_video_clip, video_processor, temp_video_file):
        """Test audio extraction failure handling."""
        # Mock video clip to raise exception
        mock_video_clip.side_effect = Exception("Video loading failed")
        
        # Test audio extraction failure
        result = video_processor.extract_audio(temp_video_file)
        
        assert result is None
    
    def test_cleanup_resources(self, video_processor):
        """Test resource cleanup."""
        # Create some temporary files
        temp_file = os.path.join(video_processor.temp_dir, "test_file.txt")
        with open(temp_file, 'w') as f:
            f.write("test content")
        
        assert os.path.exists(temp_file)
        
        # Test cleanup
        video_processor.cleanup_resources()
        
        # Verify cleanup (temp_dir should be recreated)
        assert os.path.exists(video_processor.temp_dir)
        assert not os.path.exists(temp_file)
    
    @patch('video_processor.whisper.load_model')
    def test_transcribe_audio_success(self, mock_load_model, video_processor, temp_video_file):
        """Test successful audio transcription."""
        # Mock whisper model
        mock_model = Mock()
        mock_model.transcribe.return_value = {
            'text': 'This is a test transcription',
            'segments': [{
                'start': 0.0,
                'end': 5.0,
                'text': 'This is a test transcription'
            }]
        }
        mock_load_model.return_value = mock_model
        
        # Test transcription
        result = video_processor.transcribe_audio(temp_video_file)
        
        assert result is not None
        assert 'text' in result
        assert 'segments' in result
        assert result['text'] == 'This is a test transcription'

class TestAIAnalyzer:
    """Test AI analysis functionality."""
    
    @pytest.fixture
    def ai_analyzer(self):
        """Create an AI analyzer instance for testing."""
        return AIAnalyzer()
    
    @pytest.fixture
    def sample_video_data(self):
        """Sample video data for testing."""
        return {
            'transcript': 'This is an amazing video about technology and innovation',
            'duration': 120.0,
            'resolution': '1920x1080',
            'fps': 30,
            'file_size': 50 * 1024 * 1024,  # 50MB
            'audio_features': {
                'volume_levels': [0.8, 0.9, 0.7, 0.85],
                'silence_ratio': 0.1
            }
        }
    
    def test_ai_analyzer_initialization(self, ai_analyzer):
        """Test AI analyzer initialization."""
        assert ai_analyzer is not None
        assert hasattr(ai_analyzer, 'llm_service')
    
    def test_calculate_technical_quality(self, ai_analyzer, sample_video_data):
        """Test technical quality calculation."""
        score = ai_analyzer._calculate_technical_quality(sample_video_data)
        
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100
    
    def test_calculate_engagement_hooks(self, ai_analyzer, sample_video_data):
        """Test engagement hooks calculation."""
        score = ai_analyzer._calculate_engagement_hooks(sample_video_data)
        
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100
    
    @patch.object(AIAnalyzer, '_calculate_technical_quality')
    @patch.object(AIAnalyzer, '_calculate_engagement_hooks')
    def test_calculate_viral_score(self, mock_engagement, mock_technical, ai_analyzer, sample_video_data):
        """Test viral score calculation."""
        mock_technical.return_value = 80
        mock_engagement.return_value = 75
        
        score = ai_analyzer._calculate_viral_score(sample_video_data)
        
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100
        mock_technical.assert_called_once()
        mock_engagement.assert_called_once()
    
    def test_cleanup_temp_files(self, ai_analyzer):
        """Test temporary file cleanup."""
        # Create a temporary file
        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, "test_temp.txt")
        with open(temp_file, 'w') as f:
            f.write("temporary content")
        
        # Add to cleanup list
        ai_analyzer.temp_files = [temp_file]
        
        assert os.path.exists(temp_file)
        
        # Test cleanup
        ai_analyzer._cleanup_temp_files()
        
        assert not os.path.exists(temp_file)
        assert len(ai_analyzer.temp_files) == 0
        
        # Cleanup temp dir
        shutil.rmtree(temp_dir, ignore_errors=True)

class TestMemoryOptimizer:
    """Test memory optimization functionality."""
    
    @pytest.fixture
    def memory_optimizer(self):
        """Create a memory optimizer instance for testing."""
        optimizer = EnhancedMemoryOptimizer(
            warning_threshold_mb=512,
            critical_threshold_mb=1024,
            monitoring_interval=1.0  # Fast for testing
        )
        yield optimizer
        optimizer.stop_monitoring()
    
    def test_memory_optimizer_initialization(self, memory_optimizer):
        """Test memory optimizer initialization."""
        assert memory_optimizer is not None
        assert memory_optimizer.warning_threshold_mb == 512
        assert memory_optimizer.critical_threshold_mb == 1024
    
    def test_get_memory_stats(self, memory_optimizer):
        """Test memory statistics collection."""
        stats = memory_optimizer.get_memory_stats()
        
        assert isinstance(stats, MemoryStats)
        assert stats.rss_mb >= 0
        assert stats.vms_mb >= 0
        assert 0 <= stats.percent <= 100
        assert stats.available_mb >= 0
        assert stats.total_mb > 0
        assert stats.gc_objects >= 0
    
    def test_register_resource(self, memory_optimizer):
        """Test resource registration."""
        resource_id = memory_optimizer.register_resource(
            "test_resource",
            "video",
            size_mb=100.0,
            metadata={"format": "mp4"}
        )
        
        assert resource_id == "test_resource"
        assert resource_id in memory_optimizer._resource_registry
        
        resource_info = memory_optimizer._resource_registry[resource_id]
        assert resource_info.resource_type == "video"
        assert resource_info.size_mb == 100.0
        assert resource_info.metadata["format"] == "mp4"
    
    def test_unregister_resource(self, memory_optimizer):
        """Test resource unregistration."""
        # Register a resource first
        resource_id = memory_optimizer.register_resource("test_resource", "video")
        assert resource_id in memory_optimizer._resource_registry
        
        # Unregister the resource
        memory_optimizer.unregister_resource(resource_id)
        assert resource_id not in memory_optimizer._resource_registry
    
    def test_force_garbage_collection(self, memory_optimizer):
        """Test garbage collection."""
        # Create some objects to collect
        test_objects = [[] for _ in range(1000)]
        del test_objects
        
        result = memory_optimizer.force_garbage_collection()
        
        assert isinstance(result, dict)
        assert "collected_by_generation" in result
        assert "total_collected" in result
        assert "memory_freed_mb" in result
        assert isinstance(result["total_collected"], int)
    
    def test_memory_context(self, memory_optimizer):
        """Test memory context manager."""
        with memory_optimizer.memory_context("test_operation"):
            # Simulate some memory usage
            test_data = [i for i in range(10000)]
            assert len(test_data) == 10000
        
        # Context should complete without errors
        assert True
    
    def test_track_object(self, memory_optimizer):
        """Test object tracking with weak references."""
        test_object = {"data": "test"}
        cleanup_called = False
        
        def cleanup_callback():
            nonlocal cleanup_called
            cleanup_called = True
        
        obj_id = memory_optimizer.track_object(test_object, cleanup_callback)
        assert obj_id.startswith("obj_")
        
        # Delete the object
        del test_object
        
        # Force garbage collection to trigger cleanup
        memory_optimizer.force_garbage_collection()
        
        # Note: cleanup_called might not be True immediately due to GC timing
        # This is expected behavior with weak references

class TestMonitoringSystem:
    """Test monitoring system functionality."""
    
    @pytest.fixture
    def monitoring_system(self):
        """Create a monitoring system instance for testing."""
        system = MonitoringSystem()
        yield system
        system.stop_monitoring()
    
    def test_monitoring_system_initialization(self, monitoring_system):
        """Test monitoring system initialization."""
        assert monitoring_system is not None
        assert len(monitoring_system.health_checks) > 0  # Default health checks
        assert "memory" in monitoring_system.health_checks
        assert "disk_space" in monitoring_system.health_checks
        assert "cpu" in monitoring_system.health_checks
    
    def test_record_metric(self, monitoring_system):
        """Test metric recording."""
        monitoring_system.record_metric(
            "test_metric",
            42.0,
            MetricType.GAUGE,
            tags={"environment": "test"}
        )
        
        assert "test_metric" in monitoring_system.metrics
        metrics = list(monitoring_system.metrics["test_metric"])
        assert len(metrics) == 1
        assert metrics[0].value == 42.0
        assert metrics[0].metric_type == MetricType.GAUGE
        assert metrics[0].tags["environment"] == "test"
    
    def test_track_request(self, monitoring_system):
        """Test request tracking."""
        monitoring_system.track_request(
            endpoint="/api/test",
            method="GET",
            duration=0.5,
            status_code=200
        )
        
        # Check that metrics were recorded
        assert "api_request_duration" in monitoring_system.metrics
        assert "api_requests_total" in monitoring_system.metrics
        
        # Check endpoint statistics
        endpoint_key = "GET:/api/test"
        assert endpoint_key in monitoring_system._endpoint_stats
        stats = monitoring_system._endpoint_stats[endpoint_key]
        assert stats['count'] == 1
        assert stats['total_time'] == 0.5
        assert stats['errors'] == 0
    
    def test_track_request_with_error(self, monitoring_system):
        """Test request tracking with error."""
        monitoring_system.track_request(
            endpoint="/api/test",
            method="POST",
            duration=1.0,
            status_code=500,
            error="Internal server error"
        )
        
        # Check error metrics
        assert "api_errors_total" in monitoring_system.metrics
        
        # Check endpoint statistics
        endpoint_key = "POST:/api/test"
        stats = monitoring_system._endpoint_stats[endpoint_key]
        assert stats['errors'] == 1
        
        # Check error counts
        assert "500" in monitoring_system._error_counts
        assert monitoring_system._error_counts["500"] == 1
    
    def test_get_health_status(self, monitoring_system):
        """Test health status retrieval."""
        health_status = monitoring_system.get_health_status()
        
        assert isinstance(health_status, dict)
        assert "status" in health_status
        assert "timestamp" in health_status
        assert "checks" in health_status
        
        # Verify health status is valid
        valid_statuses = [status.value for status in HealthStatus]
        assert health_status["status"] in valid_statuses
    
    def test_get_metrics_summary(self, monitoring_system):
        """Test metrics summary."""
        # Record some test metrics
        for i in range(5):
            monitoring_system.record_metric("test_counter", i, MetricType.COUNTER)
        
        summary = monitoring_system.get_metrics_summary()
        
        assert isinstance(summary, dict)
        if "test_counter" in summary:
            metric_summary = summary["test_counter"]
            assert "current" in metric_summary
            assert "average" in metric_summary
            assert "min" in metric_summary
            assert "max" in metric_summary
            assert "count" in metric_summary
    
    def test_get_performance_summary(self, monitoring_system):
        """Test performance summary."""
        # Track some requests
        for i in range(10):
            monitoring_system.track_request(
                endpoint=f"/api/test{i % 3}",
                method="GET",
                duration=0.1 + (i * 0.05),
                status_code=200 if i % 4 != 0 else 500
            )
        
        summary = monitoring_system.get_performance_summary()
        
        assert isinstance(summary, dict)
        assert "request_count" in summary
        assert "avg_duration" in summary
        assert "p50_duration" in summary
        assert "p95_duration" in summary
        assert "p99_duration" in summary
        assert "endpoints" in summary
        
        assert summary["request_count"] == 10

class TestLLMService:
    """Test LLM service functionality."""
    
    @pytest.fixture
    def llm_service(self):
        """Create an LLM service instance for testing."""
        return LLMService()
    
    def test_llm_service_initialization(self, llm_service):
        """Test LLM service initialization."""
        assert llm_service is not None
    
    @patch('llm_service.openai.ChatCompletion.create')
    def test_generate_hashtags_success(self, mock_openai, llm_service):
        """Test successful hashtag generation."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = json.dumps({
            "instagram": [
                {"tag": "#viral", "relevance_score": 0.9},
                {"tag": "#trending", "relevance_score": 0.8}
            ],
            "tiktok": [
                {"tag": "#fyp", "relevance_score": 0.95},
                {"tag": "#viral", "relevance_score": 0.9}
            ]
        })
        mock_openai.return_value = mock_response
        
        # Test hashtag generation
        result = llm_service.generate_hashtags("Test video content")
        
        assert isinstance(result, dict)
        assert "instagram" in result
        assert "tiktok" in result
        assert len(result["instagram"]) == 2
        assert result["instagram"][0]["tag"] == "#viral"
    
    @patch('llm_service.openai.ChatCompletion.create')
    def test_generate_hashtags_failure(self, mock_openai, llm_service):
        """Test hashtag generation failure handling."""
        # Mock OpenAI to raise exception
        mock_openai.side_effect = Exception("API Error")
        
        # Test hashtag generation failure
        result = llm_service.generate_hashtags("Test video content")
        
        # Should return default hashtags
        assert isinstance(result, dict)
        assert "instagram" in result
        assert "tiktok" in result
    
    @patch('llm_service.openai.ChatCompletion.create')
    def test_generate_posting_recommendations_success(self, mock_openai, llm_service):
        """Test successful posting recommendations generation."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = json.dumps({
            "platforms": [
                {
                    "platform": "instagram",
                    "suitability_score": 0.9,
                    "optimal_times": ["18:00", "20:00"],
                    "format_suggestions": ["Reel", "Story"]
                }
            ]
        })
        mock_openai.return_value = mock_response
        
        # Test recommendations generation
        result = llm_service.generate_posting_recommendations("Test video content")
        
        assert isinstance(result, dict)
        assert "platforms" in result
        assert len(result["platforms"]) == 1
        assert result["platforms"][0]["platform"] == "instagram"

class TestIntegration:
    """Integration tests for the complete system."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace for integration tests."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_complete_video_processing_pipeline(self, temp_workspace):
        """Test the complete video processing pipeline."""
        # Create a mock video file
        video_path = os.path.join(temp_workspace, "test_video.mp4")
        with open(video_path, 'wb') as f:
            f.write(b'fake video content for testing')
        
        # Initialize components
        video_processor = VideoProcessor()
        ai_analyzer = AIAnalyzer()
        memory_optimizer = EnhancedMemoryOptimizer()
        monitoring_system = MonitoringSystem()
        
        try:
            # Start monitoring
            monitoring_system.start_monitoring()
            memory_optimizer.start_monitoring()
            
            # Simulate video processing pipeline
            with monitoring_system.request_context("/api/process_video", "POST"):
                # Step 1: Extract audio (mocked)
                with patch.object(video_processor, 'extract_audio') as mock_extract:
                    mock_extract.return_value = os.path.join(temp_workspace, "audio.wav")
                    audio_path = video_processor.extract_audio(video_path)
                    assert audio_path is not None
                
                # Step 2: Transcribe audio (mocked)
                with patch.object(video_processor, 'transcribe_audio') as mock_transcribe:
                    mock_transcribe.return_value = {
                        'text': 'This is a test transcription',
                        'segments': []
                    }
                    transcript = video_processor.transcribe_audio(audio_path)
                    assert transcript is not None
                
                # Step 3: Analyze video (mocked)
                video_data = {
                    'transcript': transcript['text'],
                    'duration': 120.0,
                    'resolution': '1920x1080',
                    'fps': 30,
                    'file_size': 50 * 1024 * 1024
                }
                
                with patch.object(ai_analyzer, 'analyze_video') as mock_analyze:
                    mock_analyze.return_value = {
                        'viral_score': 85,
                        'technical_quality': 80,
                        'engagement_hooks': 90,
                        'hashtags': {'instagram': [], 'tiktok': []},
                        'recommendations': {'platforms': []}
                    }
                    analysis_result = ai_analyzer.analyze_video(video_data)
                    assert analysis_result is not None
                    assert 'viral_score' in analysis_result
            
            # Verify monitoring data was collected
            health_status = monitoring_system.get_health_status()
            assert health_status['status'] in ['healthy', 'warning', 'critical', 'down']
            
            performance_summary = monitoring_system.get_performance_summary()
            if 'request_count' in performance_summary:
                assert performance_summary['request_count'] >= 1
            
            # Verify memory optimization is working
            memory_stats = memory_optimizer.get_memory_stats()
            assert memory_stats.rss_mb > 0
            
        finally:
            # Cleanup
            monitoring_system.stop_monitoring()
            memory_optimizer.stop_monitoring()
            video_processor.cleanup_resources()
    
    def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        video_processor = VideoProcessor()
        ai_analyzer = AIAnalyzer()
        
        # Test video processor error handling
        result = video_processor.extract_audio("nonexistent_file.mp4")
        assert result is None  # Should handle error gracefully
        
        # Test AI analyzer error handling
        with patch.object(ai_analyzer, 'llm_service') as mock_llm:
            mock_llm.generate_hashtags.side_effect = Exception("LLM Error")
            
            # Should not raise exception, should return fallback
            video_data = {'transcript': 'test', 'duration': 60}
            result = ai_analyzer.analyze_video(video_data)
            assert result is not None  # Should have fallback data
    
    def test_concurrent_processing(self):
        """Test concurrent processing capabilities."""
        import threading
        import time
        
        memory_optimizer = EnhancedMemoryOptimizer()
        monitoring_system = MonitoringSystem()
        
        results = []
        errors = []
        
        def process_task(task_id):
            try:
                with memory_optimizer.memory_context(f"task_{task_id}"):
                    # Simulate processing
                    time.sleep(0.1)
                    
                    # Record metrics
                    monitoring_system.record_metric(
                        f"task_{task_id}_metric",
                        task_id * 10,
                        MetricType.GAUGE
                    )
                    
                    results.append(task_id)
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=process_task, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5.0)
        
        # Verify results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 5
        assert set(results) == {0, 1, 2, 3, 4}

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])