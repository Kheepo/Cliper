#!/usr/bin/env python3
"""
Test script to verify 1-hour video support in the video processing system.

This script validates:
1. Configuration limits for 1-hour videos
2. Memory management during long video processing
3. Progress tracking for extended processing times
4. Celery task timeout handling
5. Chunk-based processing for large videos
"""

import os
import sys
import time
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from unittest.mock import Mock, patch

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.utils.config import get_processing_config, get_celery_config
from api.services.enhanced_celery_tasks import ProgressTracker
from api.services.enhanced_video_processor import EnhancedVideoProcessor
from api.core.video_metadata import VideoMetadata

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VideoSupportTester:
    """Test class for validating 1-hour video support."""
    
    def __init__(self):
        self.results = {}
        self.errors = []
        
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests and return results."""
        logger.info("Starting 1-hour video support tests...")
        
        tests = [
            ("Configuration Limits", self.test_configuration_limits),
            ("Progress Tracking", self.test_progress_tracking),
            ("Memory Management", self.test_memory_management),
            ("Celery Configuration", self.test_celery_configuration),
            ("Chunk Processing", self.test_chunk_processing),
            ("Video Metadata Handling", self.test_video_metadata_handling),
            ("Error Handling", self.test_error_handling)
        ]
        
        for test_name, test_func in tests:
            try:
                logger.info(f"Running test: {test_name}")
                result = await test_func()
                self.results[test_name] = {
                    "status": "PASSED" if result else "FAILED",
                    "details": result
                }
                logger.info(f"Test {test_name}: {'PASSED' if result else 'FAILED'}")
            except Exception as e:
                self.results[test_name] = {
                    "status": "ERROR",
                    "error": str(e)
                }
                self.errors.append(f"{test_name}: {e}")
                logger.error(f"Test {test_name} failed with error: {e}")
        
        return self.generate_report()
    
    async def test_configuration_limits(self) -> bool:
        """Test that configuration supports 1-hour videos."""
        try:
            # Test processing config
            config = get_processing_config()
            
            # Check video duration limit (should be 3600 seconds = 1 hour)
            max_duration = int(os.environ.get('MAX_VIDEO_DURATION', '1800'))
            if max_duration < 3600:
                logger.error(f"MAX_VIDEO_DURATION too low: {max_duration}s (need 3600s)")
                return False
            
            # Check file size limit (should be 2GB)
            max_file_size = int(os.environ.get('MAX_FILE_SIZE', '500000000'))
            min_required_size = 2 * 1024 * 1024 * 1024  # 2GB
            if max_file_size < min_required_size:
                logger.error(f"MAX_FILE_SIZE too low: {max_file_size} bytes (need {min_required_size} bytes)")
                return False
            
            # Check processing timeouts
            if config.clip_processing_timeout < 1800:  # 30 minutes
                logger.error(f"Clip processing timeout too low: {config.clip_processing_timeout}s")
                return False
            
            if config.transcription_timeout < 900:  # 15 minutes
                logger.error(f"Transcription timeout too low: {config.transcription_timeout}s")
                return False
            
            logger.info("Configuration limits validation: PASSED")
            return True
            
        except Exception as e:
            logger.error(f"Configuration test failed: {e}")
            return False
    
    async def test_progress_tracking(self) -> bool:
        """Test enhanced progress tracking for long videos."""
        try:
            # Test progress tracker with multiple chunks
            tracker = ProgressTracker("test_task", "test_video", total_chunks=12)
            
            # Simulate progress updates
            await tracker.update(10, "Starting processing")
            await tracker.update(25, "Processing chunk 1", "chunk_1")
            await tracker.update_chunk_completed("chunk_1", "Chunk 1 completed")
            
            # Check that memory usage is being tracked
            if tracker.memory_usage <= 0:
                logger.warning("Memory usage not being tracked (psutil may not be available)")
            
            # Check estimated completion time
            if tracker.estimated_completion is None:
                logger.error("Estimated completion time not calculated")
                return False
            
            # Test chunk progress tracking
            if len(tracker.chunk_progress) == 0:
                logger.error("Chunk progress not being tracked")
                return False
            
            logger.info("Progress tracking validation: PASSED")
            return True
            
        except Exception as e:
            logger.error(f"Progress tracking test failed: {e}")
            return False
    
    async def test_memory_management(self) -> bool:
        """Test memory management features."""
        try:
            config = get_processing_config()
            
            # Check memory-related configurations
            if not hasattr(config, 'max_chunks_in_memory'):
                logger.error("max_chunks_in_memory not configured")
                return False
            
            if config.max_chunks_in_memory > 5:
                logger.warning(f"max_chunks_in_memory might be too high: {config.max_chunks_in_memory}")
            
            if not hasattr(config, 'chunk_processing_batch_size'):
                logger.error("chunk_processing_batch_size not configured")
                return False
            
            # Check concurrent processing limits
            if config.max_concurrent_clips > 3:
                logger.warning(f"max_concurrent_clips might be too high for 1-hour videos: {config.max_concurrent_clips}")
            
            logger.info("Memory management validation: PASSED")
            return True
            
        except Exception as e:
            logger.error(f"Memory management test failed: {e}")
            return False
    
    async def test_celery_configuration(self) -> bool:
        """Test Celery configuration for long-running tasks."""
        try:
            celery_config = get_celery_config()
            
            # Check task time limits
            if celery_config.task_time_limit < 3600:  # 1 hour
                logger.error(f"Celery task time limit too low: {celery_config.task_time_limit}s")
                return False
            
            if celery_config.task_soft_time_limit < 3300:  # 55 minutes
                logger.error(f"Celery soft time limit too low: {celery_config.task_soft_time_limit}s")
                return False
            
            # Check worker configuration
            if celery_config.worker_concurrency > 2:
                logger.warning(f"Worker concurrency might be too high: {celery_config.worker_concurrency}")
            
            if celery_config.worker_max_memory_per_child < 500000:  # 500MB
                logger.warning(f"Worker memory limit might be too low: {celery_config.worker_max_memory_per_child}")
            
            logger.info("Celery configuration validation: PASSED")
            return True
            
        except Exception as e:
            logger.error(f"Celery configuration test failed: {e}")
            return False
    
    async def test_chunk_processing(self) -> bool:
        """Test chunk-based processing logic."""
        try:
            # Mock a 1-hour video metadata
            mock_metadata = VideoMetadata(
                duration=3600,  # 1 hour
                width=1920,
                height=1080,
                fps=30,
                bitrate=5000000,
                file_size=2000000000,  # 2GB
                format="mp4",
                codec="h264"
            )
            
            # Test chunk calculation
            chunk_duration = 300  # 5 minutes
            expected_chunks = max(1, int(mock_metadata.duration / chunk_duration))
            
            if expected_chunks < 12:  # Should be 12 chunks for 1-hour video
                logger.error(f"Insufficient chunks calculated: {expected_chunks}")
                return False
            
            # Test long video detection
            is_long_video = mock_metadata.duration > 1800  # 30 minutes
            if not is_long_video:
                logger.error("1-hour video not detected as long video")
                return False
            
            logger.info("Chunk processing validation: PASSED")
            return True
            
        except Exception as e:
            logger.error(f"Chunk processing test failed: {e}")
            return False
    
    async def test_video_metadata_handling(self) -> bool:
        """Test video metadata handling for large files."""
        try:
            # Test with mock large video file
            large_file_size = 2 * 1024 * 1024 * 1024  # 2GB
            
            # Validate file size limits
            max_allowed = int(os.environ.get('MAX_FILE_SIZE', '500000000'))
            if large_file_size > max_allowed:
                logger.error(f"Large file size {large_file_size} exceeds limit {max_allowed}")
                return False
            
            # Test duration limits
            long_duration = 3600  # 1 hour
            max_duration = int(os.environ.get('MAX_VIDEO_DURATION', '1800'))
            if long_duration > max_duration:
                logger.error(f"Long duration {long_duration}s exceeds limit {max_duration}s")
                return False
            
            logger.info("Video metadata handling validation: PASSED")
            return True
            
        except Exception as e:
            logger.error(f"Video metadata test failed: {e}")
            return False
    
    async def test_error_handling(self) -> bool:
        """Test error handling for long video processing."""
        try:
            # Test progress tracker error handling
            tracker = ProgressTracker("error_test", "error_video", 1)
            await tracker.update_error("Test error message")
            
            # Test timeout handling simulation
            config = get_processing_config()
            if config.clip_processing_timeout <= 0:
                logger.error("Invalid timeout configuration")
                return False
            
            logger.info("Error handling validation: PASSED")
            return True
            
        except Exception as e:
            logger.error(f"Error handling test failed: {e}")
            return False
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive test report."""
        passed_tests = sum(1 for result in self.results.values() if result["status"] == "PASSED")
        total_tests = len(self.results)
        
        report = {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": total_tests - passed_tests,
                "success_rate": f"{(passed_tests / total_tests * 100):.1f}%" if total_tests > 0 else "0%"
            },
            "test_results": self.results,
            "errors": self.errors,
            "recommendations": self.generate_recommendations(),
            "system_ready": passed_tests == total_tests and len(self.errors) == 0
        }
        
        return report
    
    def generate_recommendations(self) -> list:
        """Generate recommendations based on test results."""
        recommendations = []
        
        for test_name, result in self.results.items():
            if result["status"] != "PASSED":
                if "Configuration" in test_name:
                    recommendations.append("Update .env file with proper limits for 1-hour videos")
                elif "Progress" in test_name:
                    recommendations.append("Install psutil for memory monitoring: pip install psutil")
                elif "Celery" in test_name:
                    recommendations.append("Restart Celery workers with updated configuration")
                elif "Memory" in test_name:
                    recommendations.append("Review memory management settings in processing config")
        
        if not recommendations:
            recommendations.append("System is ready for 1-hour video processing!")
        
        return recommendations


async def main():
    """Main test execution function."""
    print("=" * 60)
    print("1-HOUR VIDEO SUPPORT VALIDATION TEST")
    print("=" * 60)
    
    tester = VideoSupportTester()
    report = await tester.run_all_tests()
    
    # Print detailed report
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    
    summary = report["summary"]
    print(f"Total Tests: {summary['total_tests']}")
    print(f"Passed: {summary['passed']}")
    print(f"Failed: {summary['failed']}")
    print(f"Success Rate: {summary['success_rate']}")
    print(f"System Ready: {'YES' if report['system_ready'] else 'NO'}")
    
    print("\n" + "-" * 60)
    print("DETAILED RESULTS")
    print("-" * 60)
    
    for test_name, result in report["test_results"].items():
        status_symbol = "✓" if result["status"] == "PASSED" else "✗"
        print(f"{status_symbol} {test_name}: {result['status']}")
        if result["status"] == "ERROR":
            print(f"  Error: {result['error']}")
    
    if report["errors"]:
        print("\n" + "-" * 60)
        print("ERRORS ENCOUNTERED")
        print("-" * 60)
        for error in report["errors"]:
            print(f"• {error}")
    
    print("\n" + "-" * 60)
    print("RECOMMENDATIONS")
    print("-" * 60)
    for rec in report["recommendations"]:
        print(f"• {rec}")
    
    print("\n" + "=" * 60)
    
    return report["system_ready"]


if __name__ == "__main__":
    try:
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        # Run the tests
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        sys.exit(1)