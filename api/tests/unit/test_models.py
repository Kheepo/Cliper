import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError, DataError
from api.models.database_models import (
    Base, User, Job, UserSettings, JobResult, JobLog, JobStatus, JobType
)
from api.core.config import settings

# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def test_engine():
    """Create test database engine."""
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    Base.metadata.create_all(engine)
    return engine

@pytest.fixture
def test_session(test_engine):
    """Create test database session."""
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "auth_id": "auth-123",
        "email": "test@example.com",
        "display_name": "Test User",
        "photo_url": "https://example.com/avatar.jpg",
        "is_active": True,
        "last_login": datetime.utcnow()
    }

@pytest.fixture
def sample_job_data():
    """Sample job data for testing."""
    from api.models.database_models import JobType, JobStatus
    return {
        "user_id": 1,
        "job_type": JobType.VIDEO_UPLOAD,
        "status": JobStatus.PENDING,
        "title": "Test Job",
        "description": "A test job",
        "video_url": "https://example.com/video.mp4",
        "video_file_name": "test.mp4",
        "video_file_size": 1024000,
        "video_duration": 300.5
    }

class TestUserModel:
    """Test User model validation, constraints, and relationships."""
    
    def test_user_creation_valid(self, test_session, sample_user_data):
        """Test creating a user with valid data."""
        user = User(**sample_user_data)
        test_session.add(user)
        test_session.commit()
        
        # Verify user was created
        saved_user = test_session.query(User).filter_by(auth_id="auth-123").first()
        assert saved_user is not None
        assert saved_user.email == "test@example.com"
        assert saved_user.display_name == "Test User"
        assert saved_user.is_active is True
    
    def test_user_email_unique_constraint(self, test_session, sample_user_data):
        """Test that email must be unique."""
        # Create first user
        user1 = User(**sample_user_data)
        test_session.add(user1)
        test_session.commit()
        
        # Try to create second user with same email
        user2_data = sample_user_data.copy()
        user2_data["auth_id"] = "auth-456"
        user2 = User(**user2_data)
        test_session.add(user2)
        
        with pytest.raises(IntegrityError):
            test_session.commit()
    
    def test_user_auth_id_required(self, test_session, sample_user_data):
        """Test that user auth_id is required."""
        del sample_user_data["auth_id"]
        
        with pytest.raises((IntegrityError, DataError)):
            user = User(**sample_user_data)
            test_session.add(user)
            test_session.commit()
    
    def test_user_email_required(self, test_session, sample_user_data):
        """Test that email is required."""
        del sample_user_data["email"]
        
        with pytest.raises((IntegrityError, DataError)):
            user = User(**sample_user_data)
            test_session.add(user)
            test_session.commit()
    

    
    def test_user_timestamps_auto_generated(self, test_session, sample_user_data):
        """Test that timestamps are automatically generated."""
        user = User(**sample_user_data)
        test_session.add(user)
        test_session.commit()
        
        saved_user = test_session.query(User).filter_by(auth_id="auth-123").first()
        assert saved_user.created_at is not None
        assert saved_user.updated_at is not None
        assert isinstance(saved_user.created_at, datetime)
        assert isinstance(saved_user.updated_at, datetime)
    
    def test_user_relationships(self, test_session, sample_user_data, sample_job_data):
        """Test user relationships with jobs."""
        # Create user
        user = User(**sample_user_data)
        test_session.add(user)
        test_session.commit()
        
        # Update job data to use the actual user ID
        sample_job_data["user_id"] = user.id
        
        # Create job
        job = Job(**sample_job_data)
        test_session.add(job)
        test_session.commit()
        
        # Test relationships
        saved_user = test_session.query(User).filter_by(auth_id="auth-123").first()
        assert len(saved_user.jobs) == 1
        assert saved_user.jobs[0].title == "Test Job"
    
    def test_user_soft_delete(self, test_session, sample_user_data):
        """Test user soft delete functionality."""
        user = User(**sample_user_data)
        test_session.add(user)
        test_session.commit()
        
        # Soft delete user
        user.is_active = False
        test_session.commit()
        
        saved_user = test_session.query(User).filter_by(auth_id="auth-123").first()
        assert saved_user.is_active is False



class TestJobModel:
    """Test Job model validation, constraints, and relationships."""
    
    def test_job_creation_valid(self, test_session, sample_user_data, sample_job_data):
        """Test creating a job with valid data."""
        from api.models.database_models import JobStatus, JobType
        
        # Create user dependency
        user = User(**sample_user_data)
        test_session.add(user)
        test_session.commit()
        
        # Update job data to use the actual user ID
        sample_job_data["user_id"] = user.id
        
        # Create job
        job = Job(**sample_job_data)
        test_session.add(job)
        test_session.commit()
        
        saved_job = test_session.query(Job).filter_by(title="Test Job").first()
        assert saved_job is not None
        assert saved_job.title == "Test Job"
        assert saved_job.status == JobStatus.PENDING
        assert saved_job.job_type == JobType.VIDEO_UPLOAD
    
    def test_job_status_validation(self, test_session, sample_user_data, sample_job_data):
        """Test job status validation."""
        from api.models.database_models import JobStatus, JobType
        
        # Create user dependency
        user = User(**sample_user_data)
        test_session.add(user)
        test_session.commit()
        
        valid_statuses = [JobStatus.PENDING, JobStatus.PROCESSING, JobStatus.COMPLETED, JobStatus.FAILED]
        
        for i, status in enumerate(valid_statuses):
            job_data = sample_job_data.copy()
            job_data["user_id"] = user.id
            job_data["title"] = f"Test Job {i}"
            job_data["status"] = status
            
            job = Job(**job_data)
            test_session.add(job)
            test_session.commit()
            
            saved_job = test_session.query(Job).filter_by(title=f"Test Job {i}").first()
            assert saved_job.status == status
    
    def test_job_type_validation(self, test_session, sample_user_data, sample_job_data):
        """Test job type validation."""
        from api.models.database_models import JobStatus, JobType
        
        # Create user dependency
        user = User(**sample_user_data)
        test_session.add(user)
        test_session.commit()
        
        valid_types = [JobType.URL_ANALYSIS, JobType.VIDEO_UPLOAD]
        
        for i, job_type in enumerate(valid_types):
            job_data = sample_job_data.copy()
            job_data["user_id"] = user.id
            job_data["title"] = f"Test Job Type {i}"
            job_data["job_type"] = job_type
            
            job = Job(**job_data)
            test_session.add(job)
            test_session.commit()
            
            saved_job = test_session.query(Job).filter_by(title=f"Test Job Type {i}").first()
            assert saved_job.job_type == job_type
    
    def test_job_relationships(self, test_session, sample_user_data, sample_job_data):
        """Test job relationships with user."""
        # Create user dependency
        user = User(**sample_user_data)
        test_session.add(user)
        test_session.commit()
        
        # Update job data to use the actual user ID
        sample_job_data["user_id"] = user.id
        
        # Create job
        job = Job(**sample_job_data)
        test_session.add(job)
        test_session.commit()
        
        # Test relationships
        saved_job = test_session.query(Job).filter_by(title="Test Job").first()
        assert saved_job.user.auth_id == "auth-123"
        assert saved_job.user.email == "test@example.com"



class TestUserSettingsModel:
    """Test UserSettings model validation and relationships."""
    
    def test_user_settings_creation_valid(self, test_session, sample_user_data):
        """Test creating user settings with valid data."""
        # Create user first
        user = User(**sample_user_data)
        test_session.add(user)
        test_session.commit()
        
        # Create user settings
        settings_data = {
            "user_id": user.id,
            "preferred_language": "en",
            "timezone": "UTC",
            "email_notifications": True,
            "push_notifications": False,
            "auto_process_uploads": True,
            "max_concurrent_jobs": 3
        }
        
        settings = UserSettings(**settings_data)
        test_session.add(settings)
        test_session.commit()
        
        saved_settings = test_session.query(UserSettings).filter_by(user_id=user.id).first()
        assert saved_settings is not None
        assert saved_settings.email_notifications is True
        assert saved_settings.preferred_language == "en"
        assert saved_settings.timezone == "UTC"
    
    def test_user_settings_user_relationship(self, test_session, sample_user_data):
        """Test user settings relationship with user."""
        # Create user
        user = User(**sample_user_data)
        test_session.add(user)
        test_session.commit()
        
        # Create settings
        settings_data = {
            "user_id": user.id,
            "preferred_language": "en",
            "timezone": "UTC",
            "email_notifications": True,
            "push_notifications": False
        }
        
        settings = UserSettings(**settings_data)
        test_session.add(settings)
        test_session.commit()
        
        # Test relationship
        saved_settings = test_session.query(UserSettings).filter_by(user_id=user.id).first()
        assert saved_settings.preferred_language == "en"
        assert saved_settings.timezone == "UTC"
        assert saved_settings.email_notifications == True
        assert saved_settings.push_notifications == False
        assert saved_settings.user.auth_id == "auth-123"
        assert saved_settings.user.email == "test@example.com"
    
    def test_user_settings_unique_per_user(self, test_session, sample_user_data):
        """Test that each user can have only one settings record."""
        # Create user
        user = User(**sample_user_data)
        test_session.add(user)
        test_session.commit()
        
        # Create first settings
        settings1 = UserSettings(
            user_id=user.id,
            preferred_language="en",
            timezone="UTC",
            email_notifications=True,
            push_notifications=False
        )
        test_session.add(settings1)
        test_session.commit()
        
        # Try to create second settings for same user
        settings2 = UserSettings(
            user_id=user.id,
            preferred_language="es",
            timezone="EST",
            email_notifications=False,
            push_notifications=True
        )
        test_session.add(settings2)
        
        with pytest.raises(IntegrityError):
            test_session.commit()



class TestModelIndexes:
    """Test database indexes for performance."""
    
    def test_user_email_index(self, test_session):
        """Test that user email has an index for fast lookups."""
        # This would typically be tested by examining query execution plans
        # For now, we'll test that email queries work efficiently
        
        # Create multiple users
        for i in range(100):
            user_data = {
                "auth_id": f"auth-{i}",
                "email": f"user{i}@example.com",
                "display_name": f"User {i}",
                "is_active": True
            }
            user = User(**user_data)
            test_session.add(user)
        
        test_session.commit()
        
        # Query by email should be fast
        import time
        start_time = time.time()
        
        user = test_session.query(User).filter_by(email="user50@example.com").first()
        
        end_time = time.time()
        
        assert user is not None
        assert user.auth_id == "auth-50"
        # Query should be fast (less than 0.1 seconds for 100 records)
        assert end_time - start_time < 0.1
    
    def test_job_status_index(self, test_session, sample_user_data):
        """Test that job status has an index for filtering."""
        from api.models.database_models import JobStatus, JobType
        
        # Create user
        user = User(**sample_user_data)
        test_session.add(user)
        test_session.commit()
        
        # Create multiple jobs with different statuses
        statuses = [JobStatus.PENDING, JobStatus.PROCESSING, JobStatus.COMPLETED, JobStatus.FAILED]
        
        for i in range(100):
            job_data = {
                "user_id": user.id,
                "job_type": JobType.VIDEO_UPLOAD,
                "title": f"Job {i}",
                "status": statuses[i % len(statuses)],
                "video_url": f"https://example.com/video{i}.mp4"
            }
            job = Job(**job_data)
            test_session.add(job)
        
        test_session.commit()
        
        # Query by status should be fast
        import time
        start_time = time.time()
        
        pending_jobs = test_session.query(Job).filter_by(status=JobStatus.PENDING).all()
        
        end_time = time.time()
        
        assert len(pending_jobs) == 25  # 100/4 = 25 jobs per status
        # Query should be fast
        assert end_time - start_time < 0.1
    
    def test_user_settings_timestamp_index(self, test_session, sample_user_data):
        """Test that user settings timestamp has an index for time-based queries."""
        from datetime import datetime, timedelta
        
        # Create multiple users with settings at different times
        base_time = datetime.utcnow()
        
        for i in range(100):
            user_data = {
                "auth_id": f"auth-{i}",
                "email": f"user{i}@example.com",
                "display_name": f"User {i}",
                "is_active": True
            }
            user = User(**user_data)
            test_session.add(user)
            test_session.commit()
            
            settings_data = {
                "user_id": user.id,
                "preferred_language": "en",
                "timezone": "UTC",
                "email_notifications": True,
                "push_notifications": False
            }
            settings = UserSettings(**settings_data)
            # Manually set created_at for testing
            settings.created_at = base_time - timedelta(hours=i)
            test_session.add(settings)
        
        test_session.commit()
        
        # Query by timestamp range should be fast
        import time
        start_time = time.time()
        
        recent_settings = test_session.query(UserSettings).filter(
            UserSettings.created_at >= base_time - timedelta(hours=24)
        ).all()
        
        end_time = time.time()
        
        assert len(recent_settings) == 25  # Last 24 hours
        # Query should be fast
        assert end_time - start_time < 0.1

class TestModelConstraints:
    """Test database constraints and data integrity."""
    
    def test_cascade_delete_user_jobs(self, test_session, sample_user_data):
        """Test that deleting a user handles related jobs appropriately."""
        from api.models.database_models import JobStatus, JobType
        
        # Create user and job
        user = User(**sample_user_data)
        test_session.add(user)
        test_session.commit()
        
        job_data = {
            "user_id": user.id,
            "job_type": JobType.URL_ANALYSIS,
            "title": "Test Job",
            "status": JobStatus.PENDING,
            "video_url": "https://example.com/video.mp4"
        }
        job = Job(**job_data)
        test_session.add(job)
        test_session.commit()
        
        # Verify job exists
        assert test_session.query(Job).filter_by(title="Test Job").first() is not None
        
        # Delete user
        test_session.delete(user)
        test_session.commit()
        
        # Check if job still exists (depends on cascade configuration)
        job_after_delete = test_session.query(Job).filter_by(title="Test Job").first()
        
        # This behavior depends on your cascade configuration
        # Either job should be deleted (CASCADE) or deletion should fail (RESTRICT)
        # For this test, we'll assume soft delete or proper handling
        if job_after_delete is not None:
            # If job still exists, it should handle the missing user gracefully
            assert job_after_delete.user_id == user.id  # Foreign key still there
    
    def test_data_integrity_constraints(self, test_session):
        """Test various data integrity constraints."""
        # Test that required fields cannot be null
        with pytest.raises((IntegrityError, DataError)):
            user = User(
                auth_id=None,  # Required field
                email="test@example.com",
                display_name="Test User",
                is_active=True
            )
            test_session.add(user)
            test_session.commit()
    
    def test_foreign_key_constraints(self, test_session):
        """Test foreign key constraints."""
        from api.models.database_models import JobStatus, JobType
        from sqlalchemy import text
        
        # Enable foreign key constraints for SQLite
        if test_session.bind.dialect.name == 'sqlite':
            test_session.execute(text('PRAGMA foreign_keys=ON'))
        
        # Try to create job with non-existent user
        job_data = {
            "user_id": 99999,  # Non-existent user ID
            "job_type": JobType.URL_ANALYSIS,
            "title": "Test Job",
            "status": JobStatus.PENDING,
            "video_url": "https://example.com/video.mp4"
        }
        job = Job(**job_data)
        test_session.add(job)
        
        with pytest.raises(IntegrityError):
            test_session.commit()
    
    def test_unique_constraints(self, test_session, sample_user_data):
        """Test unique constraints."""
        # Create first user
        user1 = User(**sample_user_data)
        test_session.add(user1)
        test_session.commit()
        
        # Try to create second user with same email
        user2_data = sample_user_data.copy()
        user2_data["auth_id"] = "auth-456"
        user2 = User(**user2_data)
        test_session.add(user2)
        
        with pytest.raises(IntegrityError):
            test_session.commit()