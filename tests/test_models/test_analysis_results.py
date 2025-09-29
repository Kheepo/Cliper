import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.models.database_models import Base, User, AnalysisResult, AnalysisSegment, Job, JobType, JobStatus, AnalysisType
import uuid

# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_analysis.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing."""
    user = User(
        auth_id=str(uuid.uuid4()),
        email="test@example.com",
        display_name="Test User"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def sample_job(db_session, sample_user):
    """Create a sample job for testing."""
    job = Job(
        user_id=sample_user.id,
        job_type=JobType.URL_ANALYSIS,
        status=JobStatus.PENDING,
        title="Test Video",
        description="A test video for analysis",
        video_url="https://example.com/test-video.mp4"
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job

@pytest.fixture
def sample_analysis_result(db_session, sample_job):
    """Create a sample analysis result for testing."""
    analysis = AnalysisResult(
        job_id=sample_job.id,
        analysis_type=AnalysisType.EMOTION,
        analysis_data={"emotion": "positive", "score": 0.85},
        confidence_score=0.85,
        processing_time_ms=1500
    )
    db_session.add(analysis)
    db_session.commit()
    db_session.refresh(analysis)
    return analysis

class TestAnalysisResult:
    """Test cases for AnalysisResult model."""
    
    def test_create_analysis_result(self, db_session, sample_job):
        """Test creating a new analysis result."""
        analysis = AnalysisResult(
            job_id=sample_job.id,
            analysis_type=AnalysisType.EMOTION,
            analysis_data={"emotion": "happy", "intensity": 0.8},
            confidence_score=0.9,
            processing_time_ms=2000
        )
        
        db_session.add(analysis)
        db_session.commit()
        db_session.refresh(analysis)
        
        assert analysis.id is not None
        assert analysis.job_id == sample_job.id
        assert analysis.analysis_type == AnalysisType.EMOTION
        assert analysis.analysis_data["emotion"] == "happy"
        assert analysis.confidence_score == 0.9
        assert analysis.processing_time_ms == 2000
        assert analysis.created_at is not None
        assert analysis.updated_at is not None
    
    def test_analysis_result_relationships(self, db_session, sample_analysis_result):
        """Test relationships between AnalysisResult and other models."""
        # Test job relationship
        assert sample_analysis_result.job is not None
        assert sample_analysis_result.job.title == "Test Video"
        
        # Test segments relationship (should be empty initially)
        assert len(sample_analysis_result.segments) == 0
    
    def test_analysis_result_validation(self, db_session, sample_job):
        """Test validation of analysis result fields."""
        # Test with missing required fields
        with pytest.raises(Exception):  # Should raise validation error
            analysis = AnalysisResult(
                job_id=sample_job.id,
                # Missing analysis_type and analysis_data
            )
            db_session.add(analysis)
            db_session.commit()
    
    def test_analysis_result_update(self, db_session, sample_analysis_result):
        """Test updating analysis result."""
        original_updated_at = sample_analysis_result.updated_at
        
        # Add a small delay to ensure timestamp difference
        import time
        time.sleep(0.01)
        
        # Update the analysis
        sample_analysis_result.confidence_score = 0.95
        sample_analysis_result.analysis_data = {"emotion": "very_positive", "score": 0.95}
        sample_analysis_result.processing_time_ms = 2500
        
        db_session.commit()
        db_session.refresh(sample_analysis_result)
        
        assert sample_analysis_result.confidence_score == 0.95
        assert sample_analysis_result.analysis_data["emotion"] == "very_positive"
        assert sample_analysis_result.processing_time_ms == 2500
        assert sample_analysis_result.updated_at >= original_updated_at
    
    def test_analysis_result_to_dict(self, sample_analysis_result):
        """Test converting analysis result to dictionary."""
        # Since the model doesn't have a to_dict method, test basic attributes
        assert sample_analysis_result.id is not None
        assert sample_analysis_result.job_id is not None
        assert sample_analysis_result.analysis_type == AnalysisType.EMOTION
        assert sample_analysis_result.analysis_data is not None
        assert sample_analysis_result.confidence_score == 0.85
        assert sample_analysis_result.created_at is not None
        assert sample_analysis_result.updated_at is not None
    
    def test_analysis_result_repr(self, sample_analysis_result):
        """Test string representation of analysis result."""
        repr_str = repr(sample_analysis_result)
        assert "AnalysisResult" in repr_str
        assert str(sample_analysis_result.id) in repr_str
        assert sample_analysis_result.analysis_type.value in repr_str

class TestAnalysisSegment:
    """Test cases for AnalysisSegment model."""
    
    def test_create_analysis_segment(self, db_session, sample_analysis_result):
        """Test creating a new analysis segment."""
        segment = AnalysisSegment(
            analysis_id=sample_analysis_result.id,
            start_time=10.0,
            end_time=20.0,
            segment_data={"type": "highlight", "content": "This is a highlight segment", "emotion": "happy"},
            confidence_score=0.9
        )
        
        db_session.add(segment)
        db_session.commit()
        db_session.refresh(segment)
        
        assert segment.id is not None
        assert segment.analysis_id == sample_analysis_result.id
        assert segment.start_time == 10.0
        assert segment.end_time == 20.0
        assert segment.segment_data["type"] == "highlight"
        assert segment.segment_data["content"] == "This is a highlight segment"
        assert segment.confidence_score == 0.9
        assert segment.segment_data["emotion"] == "happy"
        assert segment.created_at is not None
    
    def test_segment_relationships(self, db_session, sample_analysis_result):
        """Test relationships between AnalysisSegment and AnalysisResult."""
        segment = AnalysisSegment(
            analysis_id=sample_analysis_result.id,
            start_time=0.0,
            end_time=10.0,
            segment_data={"type": "intro", "content": "Introduction segment"}
        )
        
        db_session.add(segment)
        db_session.commit()
        db_session.refresh(segment)
        
        # Test analysis relationship
        assert segment.analysis is not None
        assert segment.analysis.id == sample_analysis_result.id
        
        # Test reverse relationship
        db_session.refresh(sample_analysis_result)
        assert len(sample_analysis_result.segments) == 1
        assert sample_analysis_result.segments[0].id == segment.id
    
    def test_segment_duration_calculation(self, db_session, sample_analysis_result):
        """Test calculating duration from start and end times."""
        segment = AnalysisSegment(
            analysis_id=sample_analysis_result.id,
            start_time=15.5,
            end_time=45.2,
            segment_data={"type": "content", "content": "Main content"}
        )
        
        db_session.add(segment)
        db_session.commit()
        
        expected_duration = 45.2 - 15.5
        actual_duration = segment.end_time - segment.start_time
        assert abs(actual_duration - expected_duration) < 0.001
    
    def test_segment_validation(self, db_session, sample_analysis_result):
        """Test validation of segment fields."""
        # Test with missing required fields
        with pytest.raises(Exception):
            segment = AnalysisSegment(
                analysis_id=sample_analysis_result.id,
                start_time=20.0,
                end_time=10.0,  # Invalid: end_time < start_time
                # Missing segment_data
            )
            db_session.add(segment)
            db_session.commit()
    
    def test_segment_to_dict(self, db_session, sample_analysis_result):
        """Test converting segment to dictionary."""
        segment = AnalysisSegment(
            analysis_id=sample_analysis_result.id,
            start_time=5.0,
            end_time=15.0,
            segment_data={"type": "summary", "content": "Summary segment"},
            confidence_score=0.8
        )
        
        db_session.add(segment)
        db_session.commit()
        
        # Since the model doesn't have a to_dict method, test basic attributes
        assert segment.id is not None
        assert segment.analysis_id == sample_analysis_result.id
        assert segment.start_time == 5.0
        assert segment.end_time == 15.0
        assert segment.segment_data["type"] == "summary"
        assert segment.segment_data["content"] == "Summary segment"
        assert segment.confidence_score == 0.8
        assert segment.created_at is not None
    
    def test_multiple_segments_ordering(self, db_session, sample_analysis_result):
        """Test that segments can be ordered by start_time."""
        # Create segments in random order
        segments_data = [
            (30.0, 40.0, "segment3"),
            (10.0, 20.0, "segment2"),
            (0.0, 10.0, "segment1"),
            (40.0, 50.0, "segment4")
        ]
        
        for start, end, content in segments_data:
            segment = AnalysisSegment(
                analysis_id=sample_analysis_result.id,
                start_time=start,
                end_time=end,
                segment_data={"type": "content", "content": content}
            )
            db_session.add(segment)
        
        db_session.commit()
        
        # Query segments ordered by start_time
        from sqlalchemy import asc
        segments = db_session.query(AnalysisSegment).filter(
            AnalysisSegment.analysis_id == sample_analysis_result.id
        ).order_by(asc(AnalysisSegment.start_time)).all()
        
        assert len(segments) == 4
        
        # Check that segments are ordered by start_time
        for i in range(len(segments) - 1):
            assert segments[i].start_time <= segments[i + 1].start_time
        
        # Verify the correct order
        expected_start_times = [0.0, 10.0, 30.0, 40.0]
        actual_start_times = [seg.start_time for seg in segments]
        assert actual_start_times == expected_start_times

if __name__ == "__main__":
    pytest.main([__file__])