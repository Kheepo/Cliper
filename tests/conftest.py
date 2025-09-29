import pytest
import asyncio
import os
import tempfile
from unittest.mock import Mock, patch
from pathlib import Path

# Add the project root to Python path
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_directory():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def sample_video_data():
    """Sample video data for testing."""
    return {
        'id': 'video_123',
        'title': 'Test Video',
        'description': 'A test video for clip generation',
        'duration': 300.0,
        'file_path': '/path/to/test_video.mp4',
        'file_size': 50000000,  # 50MB
        'resolution': '1920x1080',
        'fps': 30,
        'format': 'mp4',
        'status': 'processed',
        'user_id': 'user_456',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z'
    }


@pytest.fixture
def sample_job_data():
    """Sample job data for testing."""
    return {
        'id': 'job_123',
        'user_id': 'user_456',
        'video_id': 'video_123',
        'job_type': 'clip_generation',
        'status': 'pending',
        'parameters': {
            'clip_type': 'highlight',
            'platform': 'youtube',
            'max_clips': 3,
            'duration_range': [20, 60]
        },
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
        'started_at': None,
        'completed_at': None,
        'error_message': None,
        'progress': 0
    }


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        'id': 'user_456',
        'email': 'test@example.com',
        'username': 'testuser',
        'full_name': 'Test User',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
        'is_active': True,
        'subscription_tier': 'premium'
    }


@pytest.fixture
def sample_analysis_data():
    """Sample video analysis data for testing."""
    return {
        'video_id': 'video_123',
        'transcript': 'This is a sample video transcript with exciting content and amazing moments.',
        'summary': 'A video showcasing exciting content with multiple amazing moments throughout.',
        'keywords': ['exciting', 'content', 'amazing', 'moments', 'showcase'],
        'sentiment': 'positive',
        'topics': ['entertainment', 'education', 'tutorial'],
        'language': 'en',
        'confidence': 0.95,
        'processing_time': 45.2,
        'created_at': '2024-01-01T00:00:00Z'
    }


@pytest.fixture
def sample_virality_scores():
    """Sample virality scores for testing."""
    return [
        {
            'video_id': 'video_123',
            'start_time': 0.0,
            'end_time': 30.0,
            'score': 0.8,
            'factors': {
                'engagement': 0.9,
                'emotion': 0.7,
                'novelty': 0.8,
                'clarity': 0.9
            },
            'reasoning': 'Strong opening hook with high engagement potential'
        },
        {
            'video_id': 'video_123',
            'start_time': 30.0,
            'end_time': 60.0,
            'score': 0.6,
            'factors': {
                'engagement': 0.6,
                'emotion': 0.5,
                'novelty': 0.7,
                'clarity': 0.8
            },
            'reasoning': 'Moderate content with steady engagement'
        },
        {
            'video_id': 'video_123',
            'start_time': 60.0,
            'end_time': 90.0,
            'score': 0.9,
            'factors': {
                'engagement': 0.95,
                'emotion': 0.9,
                'novelty': 0.85,
                'clarity': 0.9
            },
            'reasoning': 'Climax moment with surprise element and high emotional impact'
        }
    ]


@pytest.fixture
def mock_environment_variables():
    """Mock environment variables for testing."""
    env_vars = {
        'SUPABASE_URL': 'https://test.supabase.co',
        'SUPABASE_ANON_KEY': 'test_anon_key',
        'SUPABASE_SERVICE_ROLE_KEY': 'test_service_role_key',
        'OPENAI_API_KEY': 'test_openai_key',
        'REDIS_URL': 'redis://localhost:6379',
        'CELERY_BROKER_URL': 'redis://localhost:6379/0',
        'CELERY_RESULT_BACKEND': 'redis://localhost:6379/0',
        'UPLOAD_FOLDER': '/tmp/uploads',
        'CLIPS_FOLDER': '/tmp/clips',
        'THUMBNAILS_FOLDER': '/tmp/thumbnails'
    }
    
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def mock_ffmpeg_available():
    """Mock FFmpeg availability check."""
    with patch('shutil.which') as mock_which:
        mock_which.return_value = '/usr/bin/ffmpeg'
        yield mock_which


@pytest.fixture
def mock_file_system():
    """Mock file system operations."""
    mocks = {
        'exists': patch('os.path.exists'),
        'getsize': patch('os.path.getsize'),
        'makedirs': patch('os.makedirs'),
        'remove': patch('os.remove'),
        'disk_usage': patch('shutil.disk_usage')
    }
    
    started_mocks = {}
    for name, mock_patch in mocks.items():
        started_mocks[name] = mock_patch.start()
    
    # Set default return values
    started_mocks['exists'].return_value = True
    started_mocks['getsize'].return_value = 1000000  # 1MB
    started_mocks['disk_usage'].return_value = (1000000000, 500000000, 500000000)  # 1GB total, 500MB free
    
    yield started_mocks
    
    for mock_patch in mocks.values():
        mock_patch.stop()


@pytest.fixture
def mock_system_resources():
    """Mock system resource monitoring."""
    with patch('psutil.virtual_memory') as mock_memory, \
         patch('psutil.cpu_percent') as mock_cpu:
        
        # Mock memory usage (50% used)
        mock_memory_obj = Mock()
        mock_memory_obj.percent = 50.0
        mock_memory_obj.available = 4000000000  # 4GB available
        mock_memory.return_value = mock_memory_obj
        
        # Mock CPU usage (30%)
        mock_cpu.return_value = 30.0
        
        yield {
            'memory': mock_memory,
            'cpu': mock_cpu
        }


@pytest.fixture
def mock_websocket_manager():
    """Mock WebSocket manager for testing."""
    mock_manager = Mock()
    mock_manager.broadcast_to_user = Mock()
    mock_manager.broadcast_to_room = Mock()
    mock_manager.send_to_user = Mock()
    return mock_manager


@pytest.fixture
def mock_celery_task():
    """Mock Celery task for testing."""
    mock_task = Mock()
    mock_task.update_state = Mock()
    mock_task.retry = Mock()
    mock_task.request = Mock()
    mock_task.request.id = 'test_task_id'
    mock_task.request.retries = 0
    return mock_task


@pytest.fixture(autouse=True)
def setup_test_logging():
    """Setup logging for tests."""
    import logging
    
    # Set logging level to WARNING to reduce noise during tests
    logging.getLogger().setLevel(logging.WARNING)
    
    # Disable specific loggers that are too verbose
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('requests').setLevel(logging.ERROR)
    logging.getLogger('celery').setLevel(logging.ERROR)
    
    yield
    
    # Reset logging after tests
    logging.getLogger().setLevel(logging.INFO)


@pytest.fixture
def mock_database_transaction():
    """Mock database transaction for testing."""
    class MockTransaction:
        def __enter__(self):
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type:
                # Simulate rollback on exception
                pass
            else:
                # Simulate commit on success
                pass
    
    return MockTransaction()


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_ffmpeg: mark test as requiring FFmpeg"
    )
    config.addinivalue_line(
        "markers", "requires_redis: mark test as requiring Redis"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names."""
    for item in items:
        # Add integration marker to integration tests
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        
        # Add unit marker to unit tests
        elif "test_" in item.name and "integration" not in item.nodeid:
            item.add_marker(pytest.mark.unit)
        
        # Add slow marker to tests that might be slow
        if any(keyword in item.name.lower() for keyword in ['generate', 'process', 'upload']):
            item.add_marker(pytest.mark.slow)


# Custom pytest fixtures for async testing
@pytest.fixture
def async_mock():
    """Create an async mock for testing async functions."""
    from unittest.mock import AsyncMock
    return AsyncMock


@pytest.fixture
def mock_async_context_manager():
    """Create a mock async context manager."""
    class MockAsyncContextManager:
        def __init__(self, return_value=None):
            self.return_value = return_value
        
        async def __aenter__(self):
            return self.return_value
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    
    return MockAsyncContextManager