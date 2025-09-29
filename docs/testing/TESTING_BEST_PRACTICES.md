# Testing Best Practices for Clip Generation Feature

This document outlines best practices for writing, maintaining, and executing tests for the clip generation feature.

## Table of Contents

1. [Test Writing Guidelines](#test-writing-guidelines)
2. [Test Structure and Organization](#test-structure-and-organization)
3. [Mocking and Test Doubles](#mocking-and-test-doubles)
4. [Performance Testing Guidelines](#performance-testing-guidelines)
5. [Security Testing Guidelines](#security-testing-guidelines)
6. [Database Testing Guidelines](#database-testing-guidelines)
7. [Error Testing Guidelines](#error-testing-guidelines)
8. [Test Maintenance](#test-maintenance)
9. [Common Pitfalls](#common-pitfalls)
10. [Code Examples](#code-examples)

## Test Writing Guidelines

### 1. Test Naming Conventions

**Follow the pattern**: `test_[what]_[when]_[expected_result]`

```python
# Good examples
def test_create_clip_with_valid_data_returns_success():
    pass

def test_create_clip_with_insufficient_credits_raises_error():
    pass

def test_get_clip_with_invalid_id_returns_404():
    pass

# Bad examples
def test_clip():
    pass

def test_create():
    pass

def test_error_case():
    pass
```

### 2. Test Documentation

**Always include docstrings** for complex test scenarios:

```python
def test_concurrent_clip_generation_maintains_credit_consistency():
    """
    Test that concurrent clip generation requests maintain credit consistency.
    
    This test verifies that when multiple clip generation requests are made
    simultaneously for the same user, the credit deduction is atomic and
    prevents race conditions that could lead to negative credits.
    
    Scenario:
    1. User has 50 credits
    2. 10 concurrent requests for clips (each costs 10 credits)
    3. Only 5 requests should succeed
    4. User should have 0 credits remaining
    5. 5 requests should fail with insufficient credits error
    """
    # Test implementation
```

### 3. Test Structure (AAA Pattern)

**Arrange, Act, Assert** - Structure all tests consistently:

```python
def test_create_clip_with_valid_data_returns_success():
    # Arrange
    user = UserFactory(credits=100)
    video = VideoFactory(user_id=user.id, duration=120.0)
    clip_data = {
        "video_id": video.id,
        "start_time": 10.0,
        "duration": 30.0,
        "platform": "youtube"
    }
    
    # Act
    response = client.post(
        "/api/clips",
        json=clip_data,
        headers=auth_headers(user)
    )
    
    # Assert
    assert response.status_code == 201
    assert "clip_id" in response.json()
    assert response.json()["status"] == "processing"
```

### 4. Single Responsibility Principle

**Each test should verify one specific behavior**:

```python
# Good: Single responsibility
def test_create_clip_deducts_credits():
    user = UserFactory(credits=100)
    video = VideoFactory(user_id=user.id)
    
    client.post("/api/clips", json=clip_data, headers=auth_headers(user))
    
    db_session.refresh(user)
    assert user.credits == 90  # Assuming clip costs 10 credits

def test_create_clip_creates_database_record():
    user = UserFactory(credits=100)
    video = VideoFactory(user_id=user.id)
    
    response = client.post("/api/clips", json=clip_data, headers=auth_headers(user))
    
    clip_id = response.json()["clip_id"]
    clip = db_session.query(Clip).filter_by(id=clip_id).first()
    assert clip is not None
    assert clip.user_id == user.id

# Bad: Multiple responsibilities
def test_create_clip_does_everything():
    # Tests credit deduction, database creation, response format, etc.
    pass
```

## Test Structure and Organization

### 1. File Organization

```python
# tests/test_auth/test_clip_authentication.py

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from api.main import app
from api.models import User, Video, Clip
from tests.factories import UserFactory, VideoFactory
from tests.utils import auth_headers, create_test_video


class TestClipAuthentication:
    """Test suite for clip generation authentication."""
    
    @pytest.fixture(autouse=True)
    def setup(self, db_session, client):
        """Setup for each test method."""
        self.db = db_session
        self.client = client
    
    def test_valid_jwt_token_allows_access(self):
        """Test that valid JWT tokens allow clip generation."""
        pass
    
    def test_invalid_jwt_token_denies_access(self):
        """Test that invalid JWT tokens deny clip generation."""
        pass
```

### 2. Fixture Organization

**Create reusable fixtures** in `conftest.py`:

```python
# tests/conftest.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.main import app
from api.database import get_db, Base
from api.config import settings


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine."""
    engine = create_engine(
        settings.TEST_DATABASE_URL,
        echo=settings.DEBUG
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(test_engine):
    """Create database session for each test."""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(db_session):
    """Create test client with database session override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_user(db_session):
    """Create a mock user for testing."""
    return UserFactory(
        id="user123",
        email="test@example.com",
        credits=100
    )


@pytest.fixture
def mock_video(db_session, mock_user):
    """Create a mock video for testing."""
    return VideoFactory(
        id="video123",
        user_id=mock_user.id,
        filename="test_video.mp4",
        duration=120.0
    )
```

## Mocking and Test Doubles

### 1. External Service Mocking

**Mock external dependencies** to ensure test isolation:

```python
# Good: Mock external FFmpeg service
@patch('api.services.ffmpeg_service.extract_clip')
def test_clip_generation_calls_ffmpeg(mock_extract, mock_user, mock_video):
    mock_extract.return_value = "/tmp/clip_123.mp4"
    
    clip_data = {
        "video_id": mock_video.id,
        "start_time": 10.0,
        "duration": 30.0
    }
    
    response = client.post("/api/clips", json=clip_data, headers=auth_headers(mock_user))
    
    assert response.status_code == 201
    mock_extract.assert_called_once_with(
        video_path=mock_video.file_path,
        start_time=10.0,
        duration=30.0,
        output_path=mock.ANY
    )

# Good: Mock AI service with realistic responses
@patch('api.services.ai_service.detect_highlights')
def test_ai_highlight_detection(mock_detect, mock_user, mock_video):
    mock_detect.return_value = [
        {"start": 10.0, "end": 40.0, "score": 0.95, "type": "action"},
        {"start": 60.0, "end": 90.0, "score": 0.87, "type": "goal"}
    ]
    
    response = client.post(f"/api/videos/{mock_video.id}/highlights")
    
    assert response.status_code == 200
    highlights = response.json()["highlights"]
    assert len(highlights) == 2
    assert highlights[0]["score"] == 0.95
```

### 2. Database Mocking

**Use transactions for database test isolation**:

```python
@pytest.fixture
def isolated_db_session(test_engine):
    """Create isolated database session with automatic rollback."""
    connection = test_engine.connect()
    transaction = connection.begin()
    
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=connection
    )
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
```

### 3. Time Mocking

**Mock time-dependent functionality**:

```python
from freezegun import freeze_time
from datetime import datetime, timedelta

@freeze_time("2024-01-15 12:00:00")
def test_clip_expiration():
    """Test that clips expire after the configured time."""
    # Create clip at frozen time
    clip = create_test_clip()
    
    # Move time forward past expiration
    with freeze_time("2024-01-22 12:00:00"):  # 7 days later
        response = client.get(f"/api/clips/{clip.id}")
        assert response.status_code == 410  # Gone
        assert "expired" in response.json()["detail"].lower()
```

## Performance Testing Guidelines

### 1. Load Testing Structure

```python
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

class TestClipPerformance:
    """Performance tests for clip generation."""
    
    def test_concurrent_clip_generation_performance(self):
        """Test performance under concurrent load."""
        num_concurrent_requests = 50
        max_response_time = 5.0  # seconds
        
        users = [UserFactory(credits=1000) for _ in range(10)]
        videos = [VideoFactory(user_id=user.id) for user in users]
        
        def create_clip_request(user, video):
            start_time = time.time()
            response = client.post(
                "/api/clips",
                json={
                    "video_id": video.id,
                    "start_time": 10.0,
                    "duration": 30.0
                },
                headers=auth_headers(user)
            )
            end_time = time.time()
            return {
                "response": response,
                "duration": end_time - start_time,
                "user_id": user.id
            }
        
        # Execute concurrent requests
        with ThreadPoolExecutor(max_workers=num_concurrent_requests) as executor:
            futures = []
            for i in range(num_concurrent_requests):
                user = users[i % len(users)]
                video = videos[i % len(videos)]
                future = executor.submit(create_clip_request, user, video)
                futures.append(future)
            
            results = [future.result() for future in as_completed(futures)]
        
        # Analyze results
        response_times = [result["duration"] for result in results]
        success_count = sum(1 for result in results if result["response"].status_code == 201)
        
        # Assertions
        assert success_count >= num_concurrent_requests * 0.95  # 95% success rate
        assert max(response_times) <= max_response_time
        assert sum(response_times) / len(response_times) <= max_response_time / 2  # Avg < 2.5s
```

### 2. Memory Usage Testing

```python
import psutil
import os

def test_memory_usage_during_bulk_processing():
    """Test memory usage doesn't exceed limits during bulk processing."""
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    # Create bulk clip generation request
    user = UserFactory(credits=10000)
    videos = [VideoFactory(user_id=user.id) for _ in range(100)]
    
    clip_requests = [
        {
            "video_id": video.id,
            "start_time": 10.0,
            "duration": 30.0
        }
        for video in videos
    ]
    
    response = client.post(
        "/api/clips/bulk",
        json={"clips": clip_requests},
        headers=auth_headers(user)
    )
    
    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = final_memory - initial_memory
    
    assert response.status_code == 202
    assert memory_increase < 500  # Less than 500MB increase
```

## Security Testing Guidelines

### 1. Authentication Testing

```python
def test_jwt_token_validation():
    """Test comprehensive JWT token validation."""
    user = UserFactory()
    video = VideoFactory(user_id=user.id)
    
    test_cases = [
        {
            "name": "valid_token",
            "token": create_valid_jwt(user.id),
            "expected_status": 201
        },
        {
            "name": "expired_token",
            "token": create_expired_jwt(user.id),
            "expected_status": 401
        },
        {
            "name": "invalid_signature",
            "token": create_jwt_with_wrong_signature(user.id),
            "expected_status": 401
        },
        {
            "name": "malformed_token",
            "token": "invalid.jwt.token",
            "expected_status": 401
        },
        {
            "name": "missing_claims",
            "token": create_jwt_missing_claims(),
            "expected_status": 401
        }
    ]
    
    for case in test_cases:
        response = client.post(
            "/api/clips",
            json={
                "video_id": video.id,
                "start_time": 10.0,
                "duration": 30.0
            },
            headers={"Authorization": f"Bearer {case['token']}"}
        )
        
        assert response.status_code == case["expected_status"], \
            f"Failed for case: {case['name']}"
```

### 2. Input Validation Testing

```python
def test_sql_injection_prevention():
    """Test that SQL injection attempts are prevented."""
    user = UserFactory()
    
    malicious_inputs = [
        "'; DROP TABLE clips; --",
        "1' OR '1'='1",
        "1; DELETE FROM users WHERE id=1; --",
        "UNION SELECT * FROM users"
    ]
    
    for malicious_input in malicious_inputs:
        response = client.post(
            "/api/clips",
            json={
                "video_id": malicious_input,
                "start_time": 10.0,
                "duration": 30.0
            },
            headers=auth_headers(user)
        )
        
        # Should return validation error, not execute SQL
        assert response.status_code in [400, 422]
        assert "validation" in response.json().get("detail", "").lower()

def test_xss_prevention():
    """Test that XSS attempts are prevented."""
    user = UserFactory()
    video = VideoFactory(user_id=user.id)
    
    xss_payloads = [
        "<script>alert('xss')</script>",
        "javascript:alert('xss')",
        "<img src=x onerror=alert('xss')>",
        "<svg onload=alert('xss')>"
    ]
    
    for payload in xss_payloads:
        response = client.post(
            "/api/clips",
            json={
                "video_id": video.id,
                "start_time": 10.0,
                "duration": 30.0,
                "title": payload
            },
            headers=auth_headers(user)
        )
        
        if response.status_code == 201:
            # If creation succeeds, ensure payload is sanitized
            clip_id = response.json()["clip_id"]
            clip_response = client.get(f"/api/clips/{clip_id}", headers=auth_headers(user))
            title = clip_response.json()["title"]
            
            # Should not contain script tags or javascript
            assert "<script>" not in title
            assert "javascript:" not in title
            assert "onerror=" not in title
```

## Database Testing Guidelines

### 1. Transaction Testing

```python
def test_transaction_rollback_on_error():
    """Test that database transactions rollback properly on errors."""
    user = UserFactory(credits=100)
    video = VideoFactory(user_id=user.id)
    
    initial_credits = user.credits
    initial_clip_count = db_session.query(Clip).count()
    
    # Mock external service to fail after credit deduction
    with patch('api.services.ffmpeg_service.extract_clip') as mock_ffmpeg:
        mock_ffmpeg.side_effect = Exception("FFmpeg processing failed")
        
        with pytest.raises(Exception):
            clip_service.create_clip(
                user_id=user.id,
                clip_data={
                    "video_id": video.id,
                    "start_time": 10.0,
                    "duration": 30.0
                }
            )
    
    # Verify rollback occurred
    db_session.refresh(user)
    final_clip_count = db_session.query(Clip).count()
    
    assert user.credits == initial_credits  # Credits not deducted
    assert final_clip_count == initial_clip_count  # No clip created
```

### 2. Concurrent Access Testing

```python
def test_concurrent_credit_deduction_consistency():
    """Test that concurrent credit deductions maintain consistency."""
    user = UserFactory(credits=50)
    video = VideoFactory(user_id=user.id)
    
    def attempt_clip_creation():
        try:
            return clip_service.create_clip(
                user_id=user.id,
                clip_data={
                    "video_id": video.id,
                    "start_time": 10.0,
                    "duration": 30.0  # Costs 10 credits
                }
            )
        except InsufficientCreditsError:
            return None
    
    # Attempt 10 concurrent clip creations (should only allow 5)
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(attempt_clip_creation) for _ in range(10)]
        results = [future.result() for future in as_completed(futures)]
    
    successful_clips = [r for r in results if r is not None]
    failed_attempts = [r for r in results if r is None]
    
    assert len(successful_clips) == 5  # Only 5 should succeed
    assert len(failed_attempts) == 5   # 5 should fail
    
    db_session.refresh(user)
    assert user.credits == 0  # All credits used
```

## Error Testing Guidelines

### 1. Exception Handling

```python
def test_specific_exception_types():
    """Test that specific exceptions are raised for different error conditions."""
    user = UserFactory(credits=5)  # Insufficient for clip creation
    video = VideoFactory(user_id=user.id)
    
    # Test insufficient credits
    with pytest.raises(InsufficientCreditsError) as exc_info:
        clip_service.create_clip(user.id, {
            "video_id": video.id,
            "start_time": 10.0,
            "duration": 30.0
        })
    
    assert "not enough credits" in str(exc_info.value).lower()
    assert exc_info.value.required_credits == 10
    assert exc_info.value.available_credits == 5
    
    # Test nonexistent video
    user.credits = 100
    db_session.commit()
    
    with pytest.raises(VideoNotFoundError) as exc_info:
        clip_service.create_clip(user.id, {
            "video_id": "nonexistent",
            "start_time": 10.0,
            "duration": 30.0
        })
    
    assert "video not found" in str(exc_info.value).lower()
```

### 2. Error Recovery Testing

```python
def test_retry_mechanism_with_exponential_backoff():
    """Test that retry mechanisms work with exponential backoff."""
    user = UserFactory(credits=100)
    video = VideoFactory(user_id=user.id)
    
    call_times = []
    
    def mock_failing_service(*args, **kwargs):
        call_times.append(time.time())
        if len(call_times) < 3:
            raise ConnectionError("Service temporarily unavailable")
        return "/path/to/clip.mp4"
    
    with patch('api.services.ffmpeg_service.extract_clip', side_effect=mock_failing_service):
        start_time = time.time()
        result = clip_service.create_clip_with_retry(user.id, {
            "video_id": video.id,
            "start_time": 10.0,
            "duration": 30.0
        })
        end_time = time.time()
    
    assert result is not None
    assert len(call_times) == 3  # Failed twice, succeeded on third
    
    # Verify exponential backoff timing
    assert call_times[1] - call_times[0] >= 1.0  # First retry after 1s
    assert call_times[2] - call_times[1] >= 2.0  # Second retry after 2s
    assert end_time - start_time >= 3.0  # Total time at least 3s
```

## Test Maintenance

### 1. Test Data Factories

**Use factories for consistent test data**:

```python
# tests/factories.py

import factory
from factory.alchemy import SQLAlchemyModelFactory
from api.models import User, Video, Clip
from api.database import SessionLocal

class BaseFactory(SQLAlchemyModelFactory):
    class Meta:
        sqlalchemy_session = SessionLocal
        sqlalchemy_session_persistence = "commit"

class UserFactory(BaseFactory):
    class Meta:
        model = User
    
    id = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.id}@example.com")
    credits = 100
    subscription_tier = "basic"
    created_at = factory.Faker('date_time_this_year')

class VideoFactory(BaseFactory):
    class Meta:
        model = Video
    
    id = factory.Sequence(lambda n: f"video_{n}")
    user_id = factory.SubFactory(UserFactory)
    filename = factory.Faker('file_name', extension='mp4')
    duration = factory.Faker('pyfloat', min_value=30.0, max_value=3600.0)
    file_path = factory.LazyAttribute(lambda obj: f"/uploads/{obj.filename}")
    created_at = factory.Faker('date_time_this_year')

class ClipFactory(BaseFactory):
    class Meta:
        model = Clip
    
    id = factory.Sequence(lambda n: f"clip_{n}")
    user_id = factory.SubFactory(UserFactory)
    video_id = factory.SubFactory(VideoFactory)
    start_time = factory.Faker('pyfloat', min_value=0.0, max_value=100.0)
    duration = factory.Faker('pyfloat', min_value=5.0, max_value=60.0)
    platform = factory.Faker('random_element', elements=['youtube', 'tiktok', 'instagram'])
    status = "completed"
    created_at = factory.Faker('date_time_this_year')
```

### 2. Test Utilities

**Create reusable test utilities**:

```python
# tests/utils.py

import jwt
from datetime import datetime, timedelta
from api.config import settings

def auth_headers(user):
    """Create authentication headers for a user."""
    token = create_valid_jwt(user.id)
    return {"Authorization": f"Bearer {token}"}

def create_valid_jwt(user_id, expires_delta=None):
    """Create a valid JWT token for testing."""
    if expires_delta is None:
        expires_delta = timedelta(hours=1)
    
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + expires_delta,
        "iat": datetime.utcnow(),
        "type": "access"
    }
    
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")

def create_expired_jwt(user_id):
    """Create an expired JWT token for testing."""
    return create_valid_jwt(user_id, expires_delta=timedelta(hours=-1))

def create_jwt_with_wrong_signature(user_id):
    """Create a JWT token with wrong signature for testing."""
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow(),
        "type": "access"
    }
    
    return jwt.encode(payload, "wrong_secret_key", algorithm="HS256")

def assert_response_format(response, expected_fields):
    """Assert that response contains expected fields."""
    response_data = response.json()
    for field in expected_fields:
        assert field in response_data, f"Missing field: {field}"

def assert_error_response(response, expected_status, expected_message=None):
    """Assert error response format."""
    assert response.status_code == expected_status
    
    if expected_message:
        error_detail = response.json().get("detail", "")
        assert expected_message.lower() in error_detail.lower()
```

## Common Pitfalls

### 1. Test Isolation Issues

```python
# Bad: Tests affect each other
class TestClipGeneration:
    def test_create_clip(self):
        user = User(id="user1", credits=100)
        db_session.add(user)
        db_session.commit()
        # Test logic...
    
    def test_another_clip_operation(self):
        # This test might fail if previous test data exists
        user = db_session.query(User).filter_by(id="user1").first()
        # Assumes user exists from previous test

# Good: Isolated tests
class TestClipGeneration:
    def test_create_clip(self, db_session):
        user = UserFactory()  # Fresh user for each test
        # Test logic...
    
    def test_another_clip_operation(self, db_session):
        user = UserFactory()  # Independent user
        # Test logic...
```

### 2. Over-Mocking

```python
# Bad: Mocking too much
@patch('api.services.clip_service.validate_user')
@patch('api.services.clip_service.validate_video')
@patch('api.services.clip_service.deduct_credits')
@patch('api.services.clip_service.create_clip_record')
@patch('api.services.ffmpeg_service.extract_clip')
def test_clip_creation(mock_extract, mock_create, mock_deduct, mock_validate_video, mock_validate_user):
    # Too many mocks - not testing real integration
    pass

# Good: Mock only external dependencies
@patch('api.services.ffmpeg_service.extract_clip')
def test_clip_creation(mock_extract, mock_user, mock_video):
    mock_extract.return_value = "/path/to/clip.mp4"
    # Test real business logic with mocked external service
    pass
```

### 3. Brittle Assertions

```python
# Bad: Brittle assertion
def test_clip_response():
    response = client.post("/api/clips", json=clip_data)
    assert response.json() == {
        "clip_id": "clip_123",
        "status": "processing",
        "created_at": "2024-01-15T12:00:00Z",
        "estimated_completion": "2024-01-15T12:05:00Z"
    }

# Good: Flexible assertion
def test_clip_response():
    response = client.post("/api/clips", json=clip_data)
    data = response.json()
    
    assert "clip_id" in data
    assert data["status"] == "processing"
    assert "created_at" in data
    assert "estimated_completion" in data
    
    # Validate data types and formats
    assert isinstance(data["clip_id"], str)
    assert len(data["clip_id"]) > 0
```

### 4. Ignoring Test Performance

```python
# Bad: Slow test that creates too much data
def test_bulk_processing():
    users = [UserFactory() for _ in range(1000)]  # Too many
    videos = [VideoFactory(user_id=user.id) for user in users]
    # Test takes too long

# Good: Efficient test with minimal data
def test_bulk_processing():
    users = [UserFactory() for _ in range(5)]  # Sufficient for testing
    videos = [VideoFactory(user_id=user.id) for user in users]
    # Test is fast and focused
```

## Code Examples

### Complete Test Class Example

```python
# tests/test_auth/test_clip_security.py

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from api.main import app
from api.models import User, Video, Clip
from api.exceptions import InsufficientCreditsError, VideoNotFoundError
from tests.factories import UserFactory, VideoFactory
from tests.utils import auth_headers, assert_error_response


class TestClipSecurity:
    """Comprehensive security tests for clip generation endpoints."""
    
    @pytest.fixture(autouse=True)
    def setup(self, db_session, client):
        """Setup for each test method."""
        self.db = db_session
        self.client = client
    
    def test_unauthenticated_request_denied(self):
        """Test that unauthenticated requests are denied."""
        response = self.client.post("/api/clips", json={
            "video_id": "video123",
            "start_time": 10.0,
            "duration": 30.0
        })
        
        assert_error_response(response, 401, "authentication required")
    
    def test_invalid_jwt_token_denied(self):
        """Test that invalid JWT tokens are denied."""
        response = self.client.post(
            "/api/clips",
            json={
                "video_id": "video123",
                "start_time": 10.0,
                "duration": 30.0
            },
            headers={"Authorization": "Bearer invalid.jwt.token"}
        )
        
        assert_error_response(response, 401, "invalid token")
    
    def test_user_can_only_access_own_videos(self):
        """Test that users can only create clips for their own videos."""
        user1 = UserFactory()
        user2 = UserFactory()
        video = VideoFactory(user_id=user2.id)  # Video belongs to user2
        
        response = self.client.post(
            "/api/clips",
            json={
                "video_id": video.id,
                "start_time": 10.0,
                "duration": 30.0
            },
            headers=auth_headers(user1)  # user1 trying to access user2's video
        )
        
        assert_error_response(response, 403, "access denied")
    
    @pytest.mark.parametrize("malicious_input", [
        "'; DROP TABLE clips; --",
        "1' OR '1'='1",
        "<script>alert('xss')</script>",
        "javascript:alert('xss')"
    ])
    def test_malicious_input_sanitization(self, malicious_input):
        """Test that malicious inputs are properly sanitized."""
        user = UserFactory()
        video = VideoFactory(user_id=user.id)
        
        response = self.client.post(
            "/api/clips",
            json={
                "video_id": video.id,
                "start_time": 10.0,
                "duration": 30.0,
                "title": malicious_input
            },
            headers=auth_headers(user)
        )
        
        # Should either reject input or sanitize it
        if response.status_code == 201:
            clip_id = response.json()["clip_id"]
            clip_response = self.client.get(
                f"/api/clips/{clip_id}",
                headers=auth_headers(user)
            )
            title = clip_response.json()["title"]
            
            # Verify sanitization
            assert "<script>" not in title
            assert "javascript:" not in title
            assert "DROP TABLE" not in title
        else:
            # Should be validation error
            assert response.status_code in [400, 422]
    
    def test_rate_limiting_enforced(self):
        """Test that rate limiting is enforced."""
        user = UserFactory(credits=1000)
        video = VideoFactory(user_id=user.id)
        
        # Make requests rapidly
        responses = []
        for _ in range(20):  # Assuming rate limit is 10 requests per minute
            response = self.client.post(
                "/api/clips",
                json={
                    "video_id": video.id,
                    "start_time": 10.0,
                    "duration": 30.0
                },
                headers=auth_headers(user)
            )
            responses.append(response)
        
        # Some requests should be rate limited
        rate_limited_responses = [r for r in responses if r.status_code == 429]
        assert len(rate_limited_responses) > 0
    
    @patch('api.services.ffmpeg_service.extract_clip')
    def test_successful_clip_creation_with_valid_auth(self, mock_extract):
        """Test successful clip creation with valid authentication."""
        mock_extract.return_value = "/tmp/clip_123.mp4"
        
        user = UserFactory(credits=100)
        video = VideoFactory(user_id=user.id)
        
        response = self.client.post(
            "/api/clips",
            json={
                "video_id": video.id,
                "start_time": 10.0,
                "duration": 30.0,
                "platform": "youtube",
                "title": "Test Clip"
            },
            headers=auth_headers(user)
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "clip_id" in data
        assert data["status"] == "processing"
        assert data["user_id"] == user.id
        
        # Verify clip was created in database
        clip = self.db.query(Clip).filter_by(id=data["clip_id"]).first()
        assert clip is not None
        assert clip.user_id == user.id
        assert clip.video_id == video.id
```

This comprehensive testing guide provides the foundation for maintaining high-quality, reliable tests for the clip generation feature. Following these practices ensures that the testing infrastructure remains maintainable, efficient, and effective at catching issues before they reach production.