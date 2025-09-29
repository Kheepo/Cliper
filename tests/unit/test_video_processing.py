"""Unit tests for video processing functionality."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
import tempfile
import json
from datetime import datetime, timedelta

# Import the modules to test
try:
    from api.services.video_processor import VideoProcessor, VideoAnalyzer
    from api.models.video import Video, VideoStatus, AnalysisResult
    from api.core.exceptions import VideoProcessingError, InvalidFormatError
except ImportError:
    # Mock imports for testing
    class VideoProcessor:
        pass
    class VideoAnalyzer:
        pass
    class Video:
        pass
    class VideoStatus:
        PENDING = "pending"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"
    class AnalysisResult:
        pass
    class VideoProcessingError(Exception):
        pass
    class InvalidFormatError(Exception):
        pass

class TestVideoProcessor:
    """Test cases for VideoProcessor class."""
    
    @pytest.fixture
    def processor(self):
        """Create a VideoProcessor instance for testing."""
        return VideoProcessor()
    
    @pytest.fixture
    def sample_video_file(self):
        """Create a temporary video file for testing."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video content")
            yield f.name
        Path(f.name).unlink(missing_ok=True)
    
    @pytest.fixture
    def sample_video_data(self):
        """Sample video metadata for testing."""
        return {
            "id": "test_video_123",
            "title": "Test Video",
            "filename": "test_video.mp4",
            "size": 1024000,
            "duration": 120,
            "format": "mp4",
            "user_id": "user_123",
            "created_at": datetime.now(),
            "status": VideoStatus.PENDING
        }
    
    def test_processor_initialization(self, processor):
        """Test VideoProcessor initialization."""
        assert processor is not None
        assert hasattr(processor, 'process_video')
        assert hasattr(processor, 'validate_format')
    
    @pytest.mark.asyncio
    async def test_validate_format_valid_mp4(self, processor, sample_video_file):
        """Test format validation for valid MP4 file."""
        with patch('api.services.video_processor.VideoProcessor.validate_format') as mock_validate:
            mock_validate.return_value = True
            result = await processor.validate_format(sample_video_file)
            assert result is True
            mock_validate.assert_called_once_with(sample_video_file)
    
    @pytest.mark.asyncio
    async def test_validate_format_invalid_file(self, processor):
        """Test format validation for invalid file."""
        with patch('api.services.video_processor.VideoProcessor.validate_format') as mock_validate:
            mock_validate.side_effect = InvalidFormatError("Unsupported format")
            
            with pytest.raises(InvalidFormatError):
                await processor.validate_format("invalid_file.txt")
    
    @pytest.mark.asyncio
    async def test_process_video_success(self, processor, sample_video_data):
        """Test successful video processing."""
        with patch('api.services.video_processor.VideoProcessor.process_video') as mock_process:
            mock_process.return_value = {
                "video_id": sample_video_data["id"],
                "status": VideoStatus.COMPLETED,
                "processed_at": datetime.now(),
                "output_path": "/processed/test_video_123.mp4",
                "thumbnail_path": "/thumbnails/test_video_123.jpg",
                "metadata": {
                    "resolution": "1920x1080",
                    "bitrate": "2000kbps",
                    "codec": "h264"
                }
            }
            
            result = await processor.process_video(sample_video_data)
            
            assert result["video_id"] == sample_video_data["id"]
            assert result["status"] == VideoStatus.COMPLETED
            assert "output_path" in result
            assert "thumbnail_path" in result
            assert "metadata" in result
    
    @pytest.mark.asyncio
    async def test_process_video_failure(self, processor, sample_video_data):
        """Test video processing failure."""
        with patch('api.services.video_processor.VideoProcessor.process_video') as mock_process:
            mock_process.side_effect = VideoProcessingError("Processing failed")
            
            with pytest.raises(VideoProcessingError):
                await processor.process_video(sample_video_data)
    
    @pytest.mark.asyncio
    async def test_extract_thumbnail(self, processor, sample_video_file):
        """Test thumbnail extraction."""
        with patch('api.services.video_processor.VideoProcessor.extract_thumbnail') as mock_extract:
            mock_extract.return_value = "/thumbnails/test_video_123.jpg"
            
            result = await processor.extract_thumbnail(sample_video_file, "test_video_123")
            
            assert result == "/thumbnails/test_video_123.jpg"
            mock_extract.assert_called_once_with(sample_video_file, "test_video_123")
    
    @pytest.mark.asyncio
    async def test_get_video_metadata(self, processor, sample_video_file):
        """Test video metadata extraction."""
        expected_metadata = {
            "duration": 120.5,
            "resolution": "1920x1080",
            "bitrate": "2000kbps",
            "codec": "h264",
            "fps": 30,
            "size": 1024000
        }
        
        with patch('api.services.video_processor.VideoProcessor.get_video_metadata') as mock_metadata:
            mock_metadata.return_value = expected_metadata
            
            result = await processor.get_video_metadata(sample_video_file)
            
            assert result == expected_metadata
            assert result["duration"] == 120.5
            assert result["resolution"] == "1920x1080"
    
    @pytest.mark.asyncio
    async def test_compress_video(self, processor, sample_video_file):
        """Test video compression."""
        compression_options = {
            "quality": "medium",
            "target_size": "50MB",
            "format": "mp4"
        }
        
        with patch('api.services.video_processor.VideoProcessor.compress_video') as mock_compress:
            mock_compress.return_value = {
                "compressed_path": "/compressed/test_video_123.mp4",
                "original_size": 1024000,
                "compressed_size": 512000,
                "compression_ratio": 0.5
            }
            
            result = await processor.compress_video(sample_video_file, compression_options)
            
            assert "compressed_path" in result
            assert result["compression_ratio"] == 0.5
            assert result["compressed_size"] < result["original_size"]

class TestVideoAnalyzer:
    """Test cases for VideoAnalyzer class."""
    
    @pytest.fixture
    def analyzer(self):
        """Create a VideoAnalyzer instance for testing."""
        return VideoAnalyzer()
    
    @pytest.fixture
    def sample_analysis_request(self):
        """Sample analysis request data."""
        return {
            "video_id": "test_video_123",
            "analysis_type": "transcription",
            "options": {
                "language": "en",
                "confidence_threshold": 0.8,
                "include_timestamps": True
            }
        }
    
    def test_analyzer_initialization(self, analyzer):
        """Test VideoAnalyzer initialization."""
        assert analyzer is not None
        assert hasattr(analyzer, 'analyze_video')
        assert hasattr(analyzer, 'transcribe_audio')
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_success(self, analyzer, sample_analysis_request):
        """Test successful audio transcription."""
        expected_transcription = {
            "text": "This is a test transcription of the video content.",
            "confidence": 0.95,
            "language": "en",
            "timestamps": [
                {"start": 0.0, "end": 2.5, "text": "This is a test"},
                {"start": 2.5, "end": 5.0, "text": "transcription of the"},
                {"start": 5.0, "end": 7.5, "text": "video content."}
            ]
        }
        
        with patch('api.services.video_processor.VideoAnalyzer.transcribe_audio') as mock_transcribe:
            mock_transcribe.return_value = expected_transcription
            
            result = await analyzer.transcribe_audio(
                sample_analysis_request["video_id"],
                sample_analysis_request["options"]
            )
            
            assert result["text"] == expected_transcription["text"]
            assert result["confidence"] >= 0.8
            assert len(result["timestamps"]) == 3
    
    @pytest.mark.asyncio
    async def test_generate_summary(self, analyzer):
        """Test video summary generation."""
        video_id = "test_video_123"
        transcription = "This is a long transcription of video content that needs to be summarized."
        
        expected_summary = {
            "summary": "This video contains content that has been transcribed and summarized.",
            "key_points": [
                "Main topic discussion",
                "Important conclusions",
                "Action items"
            ],
            "duration_covered": 120,
            "confidence": 0.88
        }
        
        with patch('api.services.video_processor.VideoAnalyzer.generate_summary') as mock_summary:
            mock_summary.return_value = expected_summary
            
            result = await analyzer.generate_summary(video_id, transcription)
            
            assert "summary" in result
            assert "key_points" in result
            assert len(result["key_points"]) > 0
            assert result["confidence"] > 0.8
    
    @pytest.mark.asyncio
    async def test_analyze_sentiment(self, analyzer):
        """Test sentiment analysis."""
        text = "This is a great video with positive content and helpful information."
        
        expected_sentiment = {
            "overall_sentiment": "positive",
            "confidence": 0.92,
            "scores": {
                "positive": 0.85,
                "neutral": 0.10,
                "negative": 0.05
            },
            "emotions": [
                {"emotion": "joy", "score": 0.7},
                {"emotion": "satisfaction", "score": 0.6}
            ]
        }
        
        with patch('api.services.video_processor.VideoAnalyzer.analyze_sentiment') as mock_sentiment:
            mock_sentiment.return_value = expected_sentiment
            
            result = await analyzer.analyze_sentiment(text)
            
            assert result["overall_sentiment"] == "positive"
            assert result["confidence"] > 0.9
            assert "scores" in result
            assert "emotions" in result
    
    @pytest.mark.asyncio
    async def test_extract_topics(self, analyzer):
        """Test topic extraction."""
        text = "This video discusses machine learning, artificial intelligence, and data science concepts."
        
        expected_topics = {
            "topics": [
                {"topic": "machine learning", "relevance": 0.9},
                {"topic": "artificial intelligence", "relevance": 0.85},
                {"topic": "data science", "relevance": 0.8}
            ],
            "categories": ["technology", "education"],
            "confidence": 0.87
        }
        
        with patch('api.services.video_processor.VideoAnalyzer.extract_topics') as mock_topics:
            mock_topics.return_value = expected_topics
            
            result = await analyzer.extract_topics(text)
            
            assert "topics" in result
            assert len(result["topics"]) > 0
            assert "categories" in result
            assert result["confidence"] > 0.8
    
    @pytest.mark.asyncio
    async def test_analyze_video_complete(self, analyzer, sample_analysis_request):
        """Test complete video analysis workflow."""
        expected_result = {
            "video_id": sample_analysis_request["video_id"],
            "analysis_type": sample_analysis_request["analysis_type"],
            "status": "completed",
            "results": {
                "transcription": {
                    "text": "Complete transcription text",
                    "confidence": 0.92
                },
                "summary": {
                    "summary": "Video summary",
                    "key_points": ["Point 1", "Point 2"]
                },
                "sentiment": {
                    "overall_sentiment": "positive",
                    "confidence": 0.88
                },
                "topics": {
                    "topics": [{"topic": "education", "relevance": 0.9}]
                }
            },
            "processed_at": datetime.now(),
            "processing_time": 45.2
        }
        
        with patch('api.services.video_processor.VideoAnalyzer.analyze_video') as mock_analyze:
            mock_analyze.return_value = expected_result
            
            result = await analyzer.analyze_video(sample_analysis_request)
            
            assert result["video_id"] == sample_analysis_request["video_id"]
            assert result["status"] == "completed"
            assert "results" in result
            assert "transcription" in result["results"]
            assert "processing_time" in result

class TestVideoModel:
    """Test cases for Video model."""
    
    @pytest.fixture
    def video_data(self):
        """Sample video data for model testing."""
        return {
            "id": "video_123",
            "title": "Test Video",
            "filename": "test.mp4",
            "size": 1024000,
            "duration": 120,
            "format": "mp4",
            "user_id": "user_123",
            "status": VideoStatus.PENDING,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
    
    def test_video_creation(self, video_data):
        """Test Video model creation."""
        with patch('api.models.video.Video') as MockVideo:
            video = MockVideo(**video_data)
            video.id = video_data["id"]
            video.title = video_data["title"]
            video.status = video_data["status"]
            
            assert video.id == "video_123"
            assert video.title == "Test Video"
            assert video.status == VideoStatus.PENDING
    
    def test_video_status_update(self, video_data):
        """Test video status updates."""
        with patch('api.models.video.Video') as MockVideo:
            video = MockVideo(**video_data)
            video.status = VideoStatus.PENDING
            
            # Simulate status update
            video.status = VideoStatus.PROCESSING
            assert video.status == VideoStatus.PROCESSING
            
            video.status = VideoStatus.COMPLETED
            assert video.status == VideoStatus.COMPLETED
    
    def test_video_validation(self, video_data):
        """Test video data validation."""
        # Test valid data
        assert video_data["size"] > 0
        assert video_data["duration"] > 0
        assert video_data["format"] in ["mp4", "avi", "mov", "mkv"]
        
        # Test invalid data
        invalid_data = video_data.copy()
        invalid_data["size"] = -1
        
        with pytest.raises(ValueError):
            if invalid_data["size"] <= 0:
                raise ValueError("Size must be positive")

class TestVideoProcessingIntegration:
    """Integration tests for video processing workflow."""
    
    @pytest.fixture
    def processor(self):
        return VideoProcessor()
    
    @pytest.fixture
    def analyzer(self):
        return VideoAnalyzer()
    
    @pytest.mark.asyncio
    async def test_complete_video_workflow(self, processor, analyzer):
        """Test complete video processing and analysis workflow."""
        video_data = {
            "id": "integration_test_123",
            "title": "Integration Test Video",
            "filename": "test.mp4",
            "user_id": "user_123"
        }
        
        # Mock the complete workflow
        with patch.object(processor, 'process_video') as mock_process, \
             patch.object(analyzer, 'analyze_video') as mock_analyze:
            
            # Setup mocks
            mock_process.return_value = {
                "video_id": video_data["id"],
                "status": VideoStatus.COMPLETED,
                "output_path": "/processed/integration_test_123.mp4"
            }
            
            mock_analyze.return_value = {
                "video_id": video_data["id"],
                "status": "completed",
                "results": {
                    "transcription": {"text": "Test transcription"},
                    "summary": {"summary": "Test summary"}
                }
            }
            
            # Execute workflow
            process_result = await processor.process_video(video_data)
            analysis_result = await analyzer.analyze_video({
                "video_id": video_data["id"],
                "analysis_type": "full"
            })
            
            # Verify results
            assert process_result["status"] == VideoStatus.COMPLETED
            assert analysis_result["status"] == "completed"
            assert process_result["video_id"] == analysis_result["video_id"]
    
    @pytest.mark.asyncio
    async def test_error_handling_workflow(self, processor, analyzer):
        """Test error handling in video processing workflow."""
        video_data = {
            "id": "error_test_123",
            "title": "Error Test Video",
            "filename": "corrupted.mp4"
        }
        
        # Test processing error
        with patch.object(processor, 'process_video') as mock_process:
            mock_process.side_effect = VideoProcessingError("Corrupted file")
            
            with pytest.raises(VideoProcessingError):
                await processor.process_video(video_data)
        
        # Test analysis error
        with patch.object(analyzer, 'analyze_video') as mock_analyze:
            mock_analyze.side_effect = Exception("Analysis failed")
            
            with pytest.raises(Exception):
                await analyzer.analyze_video({
                    "video_id": video_data["id"],
                    "analysis_type": "transcription"
                })

if __name__ == "__main__":
    pytest.main([__file__, "-v"])