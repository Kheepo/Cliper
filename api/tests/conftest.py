"""Pytest configuration and fixtures for the video-to-clip generation system tests.

Provides:
- Common test fixtures
- Test configuration
- Mock setups
- Test utilities
"""

import os
import sys
import pytest
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
import asyncio
from pathlib import Path

# Add the api directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for tests."""
    temp_dir = tempfile.mkdtemp(prefix="cliper_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def mock_video_file(temp_workspace):
    """Create a mock video file for testing."""
    video_path = os.path.join(temp_workspace, "test_video.mp4")
    with open(video_path, 'wb') as f:
        f.write(b'fake video content for testing')
    return video_path

@pytest.fixture
def mock_audio_file(temp_workspace):
    """Create a mock audio file for testing."""
    audio_path = os.path.join(temp_workspace, "test_audio.wav")
    with open(audio_path, 'wb') as f:
        f.write(b'fake audio content for testing')
    return audio_path

@pytest.fixture
def sample_transcript():
    """Sample transcript data for testing."""
    return {
        'text': 'This is an amazing video about technology and innovation. It showcases the latest trends in AI and machine learning.',
        'segments': [
            {
                'start': 0.0,
                'end': 5.0,
                'text': 'This is an amazing video about technology and innovation.'
            },
            {
                'start': 5.0,
                'end': 10.0,
                'text': 'It showcases the latest trends in AI and machine learning.'
            }
        ]
    }

@pytest.fixture
def sample_video_data():
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
        },
        'visual_features': {
            'scene_changes': [10.0, 25.0, 45.0, 70.0],
            'motion_intensity': 0.7,
            'color_variance': 0.6
        }
    }

@pytest.fixture
def sample_analysis_result():
    """Sample analysis result for testing."""
    return {
        'viral_score': 85,
        'technical_quality': 80,
        'engagement_hooks': 90,
        'content_analysis': {
            'sentiment': 'positive',
            'topics': ['technology', 'innovation', 'AI'],
            'keywords': ['amazing', 'latest', 'trends']
        },
        'hashtags': {
            'instagram': [
                {'tag': '#technology', 'relevance_score': 0.9},
                {'tag': '#innovation', 'relevance_score': 0.8},
                {'tag': '#AI', 'relevance_score': 0.85}
            ],
            'tiktok': [
                {'tag': '#tech', 'relevance_score': 0.9},
                {'tag': '#viral', 'relevance_score': 0.7},
                {'tag': '#fyp', 'relevance_score': 0.95}
            ]
        },
        'recommendations': {
            'platforms': [
                {
                    'platform': 'instagram',
                    'suitability_score': 0.9,
                    'optimal_times': ['18:00', '20:00'],
                    'format_suggestions': ['Reel', 'Story']
                },
                {
                    'platform': 'tiktok',
                    'suitability_score': 0.95,
                    'optimal_times': ['19:00', '21:00'],
                    'format_suggestions': ['Short Video']
                }
            ]
        }
    }

@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = '''
    {
        "instagram": [
            {"tag": "#viral", "relevance_score": 0.9},
            {"tag": "#trending", "relevance_score": 0.8}
        ],
        "tiktok": [
            {"tag": "#fyp", "relevance_score": 0.95},
            {"tag": "#viral", "relevance_score": 0.9}
        ]
    }
    '''
    return mock_response

@pytest.fixture
def mock_whisper_model():
    """Mock Whisper model for testing."""
    mock_model = Mock()
    mock_model.transcribe.return_value = {
        'text': 'This is a test transcription from Whisper',
        'segments': [
            {
                'start': 0.0,
                'end': 5.0,
                'text': 'This is a test transcription from Whisper'
            }
        ]
    }
    return mock_model

@pytest.fixture
def mock_video_clip():
    """Mock VideoFileClip for testing."""
    mock_clip = Mock()
    mock_clip.duration = 120.0
    mock_clip.fps = 30
    mock_clip.size = (1920, 1080)
    
    # Mock audio
    mock_audio = Mock()
    mock_clip.audio = mock_audio
    
    return mock_clip

@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Setup test environment variables and configurations."""
    # Set test environment variables
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    
    # Mock external dependencies
    with patch('openai.ChatCompletion.create') as mock_openai:
        mock_openai.return_value = Mock()
        yield

@pytest.fixture
def mock_firebase_service():
    """Mock Firebase service for testing."""
    mock_service = Mock()
    mock_service.save_analysis_result.return_value = True
    mock_service.save_virality_scores.return_value = True
    mock_service.get_analysis_result.return_value = None
    return mock_service

@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for testing."""
    mock_client = Mock()
    mock_table = Mock()
    mock_client.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.execute.return_value = Mock(data=[])
    return mock_client

class TestHelpers:
    """Test helper utilities."""
    
    @staticmethod
    def create_test_video_data(**kwargs):
        """Create test video data with optional overrides."""
        default_data = {
            'transcript': 'Test video transcript',
            'duration': 60.0,
            'resolution': '1280x720',
            'fps': 24,
            'file_size': 25 * 1024 * 1024,  # 25MB
            'audio_features': {
                'volume_levels': [0.5, 0.6, 0.7],
                'silence_ratio': 0.2
            }
        }
        default_data.update(kwargs)
        return default_data
    
    @staticmethod
    def create_test_analysis_result(**kwargs):
        """Create test analysis result with optional overrides."""
        default_result = {
            'viral_score': 75,
            'technical_quality': 70,
            'engagement_hooks': 80,
            'hashtags': {'instagram': [], 'tiktok': []},
            'recommendations': {'platforms': []}
        }
        default_result.update(kwargs)
        return default_result
    
    @staticmethod
    def assert_valid_viral_score(score):
        """Assert that a viral score is valid."""
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100
    
    @staticmethod
    def assert_valid_hashtags(hashtags):
        """Assert that hashtags are in valid format."""
        assert isinstance(hashtags, dict)
        for platform, tags in hashtags.items():
            assert isinstance(platform, str)
            assert isinstance(tags, list)
            for tag_info in tags:
                assert isinstance(tag_info, dict)
                assert 'tag' in tag_info
                assert 'relevance_score' in tag_info
                assert tag_info['tag'].startswith('#')
                assert 0 <= tag_info['relevance_score'] <= 1
    
    @staticmethod
    def assert_valid_recommendations(recommendations):
        """Assert that recommendations are in valid format."""
        assert isinstance(recommendations, dict)
        assert 'platforms' in recommendations
        assert isinstance(recommendations['platforms'], list)
        
        for platform_rec in recommendations['platforms']:
            assert isinstance(platform_rec, dict)
            assert 'platform' in platform_rec
            assert 'suitability_score' in platform_rec
            assert 0 <= platform_rec['suitability_score'] <= 1

# Make test helpers available globally
@pytest.fixture
def test_helpers():
    """Provide test helper utilities."""
    return TestHelpers

# Configure pytest
def pytest_configure(config):
    """Configure pytest settings."""
    # Add custom markers
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )

def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names."""
    for item in items:
        # Add markers based on test file names
        if "test_performance" in item.nodeid:
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)
        elif "test_integration" in item.nodeid or "test_complete" in item.name:
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)

# Test data constants
TEST_VIDEO_FORMATS = ['mp4', 'avi', 'mov', 'mkv']
TEST_AUDIO_FORMATS = ['wav', 'mp3', 'aac']
TEST_PLATFORMS = ['instagram', 'tiktok', 'youtube', 'twitter']
TEST_HASHTAG_PREFIXES = ['#viral', '#trending', '#fyp', '#explore']