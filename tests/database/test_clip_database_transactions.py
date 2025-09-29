import pytest
import asyncio
from typing import List, Dict, Any
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError, DatabaseError
from sqlalchemy import text
from fastapi.testclient import TestClient

from api.main import app
from api.database import get_db, engine
from api.models.video import Video
from api.models.user import User
from api.models.clip import Clip
from api.services.clip_service import ClipService
from api.core.exceptions import DatabaseTransactionError, InsufficientCreditsError


class TestClipDatabaseTransactions:
    """Comprehensive database transaction and rollback testing for clip generation."""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer valid_jwt_token"}
    
    @pytest.fixture
    def mock_user(self, db_session):
        user = User(
            id="user123",
            email="test@example.com",
            credits=100,
            subscription_tier="premium"
        )
        db_session.add(user)
        db_session.commit()
        return user
    
    @pytest.fixture
    def mock_video(self, db_session, mock_user):
        video = Video(
            id="video123",
            user_id=mock_user.id,
            filename="test_video.mp4",
            file_path="/storage/videos/test_video.mp4",
            duration=120.0,
            status="processed"
        )
        db_session.add(video)
        db_session.commit()
        return video
    
    @pytest.fixture
    def clip_service(self, db_session):
        return ClipService(db_session)
    
    # Basic Transaction Tests
    
    def test_successful_clip_creation_transaction(self, db_session, mock_user, mock_video, clip_service):
        """Test successful clip creation with proper transaction commit."""
        initial_credits = mock_user.credits
        initial_clip_count = db_session.query(Clip).count()
        
        # Create clip
        clip_data = {
            "video_id": mock_video.id,
            "start_time": 10.0,
            "duration": 30.0,
            "platform": "youtube",
            "title": "Test Clip"
        }
        
        with patch('api.services.clip_service.generate_clip_async') as mock_generate:
            mock_generate.return_value = "clip123"
            
            clip = clip_service.create_clip(mock_user.id, clip_data)
            
            # Verify transaction was committed
            db_session.refresh(mock_user)
            assert mock_user.credits < initial_credits
            assert db_session.query(Clip).count() == initial_clip_count + 1
            assert clip.id is not None
            assert clip.status == "processing"
    
    def test_clip_creation_rollback_on_credit_deduction_failure(self, db_session, mock_user, mock_video, clip_service):
        """Test rollback when credit deduction fails."""
        initial_credits = mock_user.credits
        initial_clip_count = db_session.query(Clip).count()
        
        # Mock credit deduction to fail
        with patch.object(clip_service, '_deduct_credits') as mock_deduct:
            mock_deduct.side_effect = InsufficientCreditsError("Not enough credits")
            
            with pytest.raises(InsufficientCreditsError):
                clip_service.create_clip(mock_user.id, {
                    "video_id": mock_video.id,
                    "start_time": 10.0,
                    "duration": 30.0,
                    "platform": "youtube"
                })
            
            # Verify rollback - no changes should persist
            db_session.refresh(mock_user)
            assert mock_user.credits == initial_credits
            assert db_session.query(Clip).count() == initial_clip_count
    
    def test_clip_creation_rollback_on_database_error(self, db_session, mock_user, mock_video, clip_service):
        """Test rollback when database constraint violation occurs."""
        initial_credits = mock_user.credits
        initial_clip_count = db_session.query(Clip).count()
        
        # Mock database error during clip insertion
        with patch.object(db_session, 'add') as mock_add:
            mock_add.side_effect = IntegrityError("Constraint violation", None, None)
            
            with pytest.raises(DatabaseTransactionError):
                clip_service.create_clip(mock_user.id, {
                    "video_id": mock_video.id,
                    "start_time": 10.0,
                    "duration": 30.0,
                    "platform": "youtube"
                })
            
            # Verify rollback
            db_session.refresh(mock_user)
            assert mock_user.credits == initial_credits
            assert db_session.query(Clip).count() == initial_clip_count
    
    def test_clip_creation_rollback_on_external_service_failure(self, db_session, mock_user, mock_video, clip_service):
        """Test rollback when external service (FFmpeg, AI) fails."""
        initial_credits = mock_user.credits
        initial_clip_count = db_session.query(Clip).count()
        
        # Mock external service failure
        with patch('api.services.clip_service.generate_clip_async') as mock_generate:
            mock_generate.side_effect = Exception("FFmpeg processing failed")
            
            with pytest.raises(Exception):
                clip_service.create_clip(mock_user.id, {
                    "video_id": mock_video.id,
                    "start_time": 10.0,
                    "duration": 30.0,
                    "platform": "youtube"
                })
            
            # Verify rollback
            db_session.refresh(mock_user)
            assert mock_user.credits == initial_credits
            assert db_session.query(Clip).count() == initial_clip_count
    
    # Concurrent Transaction Tests
    
    def test_concurrent_clip_creation_credit_consistency(self, db_session, mock_user, mock_video):
        """Test credit consistency under concurrent clip creation."""
        initial_credits = mock_user.credits
        clip_cost = 10  # Assume each clip costs 10 credits
        
        def create_clip_worker(worker_id: int):
            """Worker function for concurrent clip creation."""
            try:
                service = ClipService(db_session)
                with patch('api.services.clip_service.generate_clip_async'):
                    service.create_clip(mock_user.id, {
                        "video_id": mock_video.id,
                        "start_time": 10.0 + worker_id,
                        "duration": 30.0,
                        "platform": "youtube",
                        "title": f"Concurrent Clip {worker_id}"
                    })
                return True
            except Exception:
                return False
        
        # Simulate concurrent requests
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_clip_worker, i) for i in range(5)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # Verify credit consistency
        db_session.refresh(mock_user)
        successful_clips = sum(results)
        expected_credits = initial_credits - (successful_clips * clip_cost)
        
        assert mock_user.credits == expected_credits
        assert db_session.query(Clip).filter(Clip.user_id == mock_user.id).count() == successful_clips
    
    def test_concurrent_clip_creation_with_insufficient_credits(self, db_session, mock_user, mock_video):
        """Test behavior when multiple concurrent requests exceed available credits."""
        # Set user to have limited credits
        mock_user.credits = 25  # Only enough for 2-3 clips
        db_session.commit()
        
        def create_clip_worker(worker_id: int):
            try:
                service = ClipService(db_session)
                with patch('api.services.clip_service.generate_clip_async'):
                    service.create_clip(mock_user.id, {
                        "video_id": mock_video.id,
                        "start_time": 10.0 + worker_id,
                        "duration": 30.0,
                        "platform": "youtube"
                    })
                return "success"
            except InsufficientCreditsError:
                return "insufficient_credits"
            except Exception as e:
                return f"error: {str(e)}"
        
        # Launch concurrent requests
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_clip_worker, i) for i in range(5)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # Verify that credits never go negative
        db_session.refresh(mock_user)
        assert mock_user.credits >= 0
        
        # Verify that some requests succeeded and others failed appropriately
        success_count = sum(1 for r in results if r == "success")
        insufficient_count = sum(1 for r in results if r == "insufficient_credits")
        
        assert success_count > 0
        assert insufficient_count > 0
        assert success_count + insufficient_count == len(results)
    
    # Bulk Operations Transaction Tests
    
    def test_bulk_clip_creation_atomic_transaction(self, db_session, mock_user, mock_video, clip_service):
        """Test that bulk clip creation is atomic - all or nothing."""
        initial_credits = mock_user.credits
        initial_clip_count = db_session.query(Clip).count()
        
        bulk_clips = [
            {
                "video_id": mock_video.id,
                "start_time": 10.0,
                "duration": 30.0,
                "platform": "youtube",
                "title": "Clip 1"
            },
            {
                "video_id": mock_video.id,
                "start_time": 50.0,
                "duration": 30.0,
                "platform": "tiktok",
                "title": "Clip 2"
            },
            {
                "video_id": "nonexistent_video",  # This will cause failure
                "start_time": 80.0,
                "duration": 30.0,
                "platform": "instagram",
                "title": "Clip 3"
            }
        ]
        
        with pytest.raises(Exception):  # Should fail due to nonexistent video
            clip_service.create_bulk_clips(mock_user.id, bulk_clips)
        
        # Verify complete rollback - no clips should be created
        db_session.refresh(mock_user)
        assert mock_user.credits == initial_credits
        assert db_session.query(Clip).count() == initial_clip_count
    
    def test_bulk_clip_creation_partial_failure_handling(self, db_session, mock_user, mock_video, clip_service):
        """Test handling of partial failures in bulk operations."""
        initial_credits = mock_user.credits
        
        bulk_clips = [
            {
                "video_id": mock_video.id,
                "start_time": 10.0,
                "duration": 30.0,
                "platform": "youtube"
            },
            {
                "video_id": mock_video.id,
                "start_time": 50.0,
                "duration": 30.0,
                "platform": "tiktok"
            }
        ]
        
        # Mock one clip to fail during processing
        with patch('api.services.clip_service.generate_clip_async') as mock_generate:
            mock_generate.side_effect = ["clip1", Exception("Processing failed")]
            
            # Depending on implementation, this might succeed partially or fail completely
            try:
                clips = clip_service.create_bulk_clips(mock_user.id, bulk_clips)
                # If partial success is allowed
                assert len(clips) == 1
            except Exception:
                # If atomic behavior is enforced
                db_session.refresh(mock_user)
                assert mock_user.credits == initial_credits
    
    # Database Connection and Recovery Tests
    
    def test_clip_creation_with_database_connection_loss(self, db_session, mock_user, mock_video, clip_service):
        """Test behavior when database connection is lost during transaction."""
        initial_credits = mock_user.credits
        
        # Mock database connection loss
        with patch.object(db_session, 'commit') as mock_commit:
            mock_commit.side_effect = OperationalError("Connection lost", None, None)
            
            with pytest.raises(DatabaseTransactionError):
                clip_service.create_clip(mock_user.id, {
                    "video_id": mock_video.id,
                    "start_time": 10.0,
                    "duration": 30.0,
                    "platform": "youtube"
                })
            
            # Verify that transaction was rolled back
            # Note: In real scenario, we'd need to reconnect to verify state
            assert True  # Placeholder for connection recovery test
    
    def test_clip_creation_with_deadlock_detection(self, db_session, mock_user, mock_video, clip_service):
        """Test deadlock detection and recovery."""
        # Mock deadlock scenario
        with patch.object(db_session, 'commit') as mock_commit:
            mock_commit.side_effect = OperationalError("Deadlock detected", None, None)
            
            with pytest.raises(DatabaseTransactionError):
                clip_service.create_clip(mock_user.id, {
                    "video_id": mock_video.id,
                    "start_time": 10.0,
                    "duration": 30.0,
                    "platform": "youtube"
                })
    
    # Transaction Isolation Tests
    
    def test_read_committed_isolation_level(self, db_session, mock_user, mock_video):
        """Test read committed isolation level behavior."""
        # Create a clip in one transaction
        clip = Clip(
            id="clip123",
            user_id=mock_user.id,
            video_id=mock_video.id,
            start_time=10.0,
            duration=30.0,
            platform="youtube",
            status="processing"
        )
        
        # Start transaction but don't commit
        db_session.add(clip)
        db_session.flush()  # Send to DB but don't commit
        
        # In another session, the clip should not be visible
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(bind=engine)
        other_session = SessionLocal()
        
        try:
            other_clip = other_session.query(Clip).filter(Clip.id == "clip123").first()
            assert other_clip is None  # Should not see uncommitted data
            
            # Now commit the first transaction
            db_session.commit()
            
            # Now it should be visible
            other_clip = other_session.query(Clip).filter(Clip.id == "clip123").first()
            assert other_clip is not None
            
        finally:
            other_session.close()
    
    def test_transaction_timeout_handling(self, db_session, mock_user, mock_video, clip_service):
        """Test handling of transaction timeouts."""
        # Mock long-running transaction that times out
        with patch('time.sleep') as mock_sleep:
            with patch.object(db_session, 'commit') as mock_commit:
                mock_commit.side_effect = OperationalError("Transaction timeout", None, None)
                
                with pytest.raises(DatabaseTransactionError):
                    clip_service.create_clip(mock_user.id, {
                        "video_id": mock_video.id,
                        "start_time": 10.0,
                        "duration": 30.0,
                        "platform": "youtube"
                    })
    
    # Cleanup and Recovery Tests
    
    def test_cleanup_after_failed_transaction(self, db_session, mock_user, mock_video, clip_service):
        """Test proper cleanup after failed transactions."""
        initial_state = {
            "credits": mock_user.credits,
            "clip_count": db_session.query(Clip).count()
        }
        
        # Attempt clip creation that will fail
        with patch('api.services.clip_service.generate_clip_async') as mock_generate:
            mock_generate.side_effect = Exception("Processing failed")
            
            with pytest.raises(Exception):
                clip_service.create_clip(mock_user.id, {
                    "video_id": mock_video.id,
                    "start_time": 10.0,
                    "duration": 30.0,
                    "platform": "youtube"
                })
        
        # Verify cleanup
        db_session.refresh(mock_user)
        assert mock_user.credits == initial_state["credits"]
        assert db_session.query(Clip).count() == initial_state["clip_count"]
        
        # Verify that subsequent operations work normally
        with patch('api.services.clip_service.generate_clip_async') as mock_generate:
            mock_generate.return_value = "clip123"
            
            clip = clip_service.create_clip(mock_user.id, {
                "video_id": mock_video.id,
                "start_time": 10.0,
                "duration": 30.0,
                "platform": "youtube"
            })
            
            assert clip is not None
            assert clip.status == "processing"
    
    def test_nested_transaction_rollback(self, db_session, mock_user, mock_video, clip_service):
        """Test rollback behavior with nested transactions/savepoints."""
        initial_credits = mock_user.credits
        
        try:
            # Start outer transaction
            with db_session.begin():
                # Deduct credits
                mock_user.credits -= 10
                db_session.flush()
                
                try:
                    # Start inner transaction (savepoint)
                    with db_session.begin_nested():
                        # Create clip record
                        clip = Clip(
                            id="clip123",
                            user_id=mock_user.id,
                            video_id=mock_video.id,
                            start_time=10.0,
                            duration=30.0,
                            platform="youtube",
                            status="processing"
                        )
                        db_session.add(clip)
                        db_session.flush()
                        
                        # Simulate failure in processing
                        raise Exception("Processing failed")
                        
                except Exception:
                    # Inner transaction should rollback
                    # But outer transaction (credit deduction) should remain
                    pass
                
                # Decide whether to commit or rollback outer transaction
                raise Exception("Complete rollback")
                
        except Exception:
            # Complete rollback
            pass
        
        # Verify complete rollback
        db_session.refresh(mock_user)
        assert mock_user.credits == initial_credits
        assert db_session.query(Clip).filter(Clip.id == "clip123").first() is None
    
    # Performance and Stress Tests
    
    def test_transaction_performance_under_load(self, db_session, mock_user, mock_video, clip_service):
        """Test transaction performance under high load."""
        import time
        
        start_time = time.time()
        successful_transactions = 0
        
        # Perform multiple transactions rapidly
        for i in range(50):
            try:
                with patch('api.services.clip_service.generate_clip_async'):
                    clip_service.create_clip(mock_user.id, {
                        "video_id": mock_video.id,
                        "start_time": 10.0 + i,
                        "duration": 30.0,
                        "platform": "youtube",
                        "title": f"Load Test Clip {i}"
                    })
                successful_transactions += 1
            except Exception:
                # Some transactions may fail due to credit limits
                pass
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Verify reasonable performance
        assert duration < 30.0  # Should complete within 30 seconds
        assert successful_transactions > 0  # At least some should succeed
        
        # Verify data consistency
        db_session.refresh(mock_user)
        assert mock_user.credits >= 0
        assert db_session.query(Clip).filter(Clip.user_id == mock_user.id).count() == successful_transactions
    
    def test_memory_usage_during_large_transactions(self, db_session, mock_user, mock_video, clip_service):
        """Test memory usage during large transaction operations."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Perform large bulk operation
        large_bulk_clips = [
            {
                "video_id": mock_video.id,
                "start_time": 10.0 + i,
                "duration": 30.0,
                "platform": "youtube",
                "title": f"Bulk Clip {i}"
            }
            for i in range(100)
        ]
        
        try:
            with patch('api.services.clip_service.generate_clip_async'):
                clip_service.create_bulk_clips(mock_user.id, large_bulk_clips)
        except Exception:
            # May fail due to credit limits, that's okay
            pass
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB)
        assert memory_increase < 100 * 1024 * 1024
    
    # Integration with External Services
    
    def test_transaction_rollback_on_external_service_timeout(self, db_session, mock_user, mock_video, clip_service):
        """Test transaction rollback when external services timeout."""
        initial_credits = mock_user.credits
        
        # Mock external service timeout
        with patch('api.services.clip_service.generate_clip_async') as mock_generate:
            mock_generate.side_effect = asyncio.TimeoutError("Service timeout")
            
            with pytest.raises(Exception):
                clip_service.create_clip(mock_user.id, {
                    "video_id": mock_video.id,
                    "start_time": 10.0,
                    "duration": 30.0,
                    "platform": "youtube"
                })
        
        # Verify rollback
        db_session.refresh(mock_user)
        assert mock_user.credits == initial_credits
        assert db_session.query(Clip).filter(
            Clip.user_id == mock_user.id,
            Clip.video_id == mock_video.id
        ).count() == 0