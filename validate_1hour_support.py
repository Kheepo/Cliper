#!/usr/bin/env python3
"""
Quick validation script to check if the system supports 1-hour video processing.

Usage: python validate_1hour_support.py
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_env_variables():
    """Check environment variables for 1-hour video support."""
    print("Checking environment variables...")
    
    checks = []
    
    # Check MAX_VIDEO_DURATION
    max_duration = int(os.environ.get('MAX_VIDEO_DURATION', '1800'))
    duration_ok = max_duration >= 3600
    checks.append(("MAX_VIDEO_DURATION", f"{max_duration}s", "≥3600s", duration_ok))
    
    # Check MAX_FILE_SIZE
    max_file_size = int(os.environ.get('MAX_FILE_SIZE', '500000000'))
    size_gb = max_file_size / (1024 * 1024 * 1024)
    size_ok = max_file_size >= 2 * 1024 * 1024 * 1024  # 2GB
    checks.append(("MAX_FILE_SIZE", f"{size_gb:.1f}GB", "≥2GB", size_ok))
    
    # Check processing timeouts
    clip_timeout = int(os.environ.get('CLIP_PROCESSING_TIMEOUT', '600'))
    clip_ok = clip_timeout >= 1800
    checks.append(("CLIP_PROCESSING_TIMEOUT", f"{clip_timeout}s", "≥1800s", clip_ok))
    
    transcription_timeout = int(os.environ.get('TRANSCRIPTION_TIMEOUT', '300'))
    trans_ok = transcription_timeout >= 900
    checks.append(("TRANSCRIPTION_TIMEOUT", f"{transcription_timeout}s", "≥900s", trans_ok))
    
    # Check Celery timeouts
    celery_time_limit = int(os.environ.get('CELERY_TIME_LIMIT', '900'))
    celery_ok = celery_time_limit >= 3600
    checks.append(("CELERY_TIME_LIMIT", f"{celery_time_limit}s", "≥3600s", celery_ok))
    
    return checks

def print_results(checks):
    """Print validation results."""
    print("\n" + "=" * 70)
    print("1-HOUR VIDEO SUPPORT VALIDATION")
    print("=" * 70)
    
    print(f"{'Setting':<25} {'Current':<15} {'Required':<15} {'Status':<10}")
    print("-" * 70)
    
    all_passed = True
    for setting, current, required, passed in checks:
        status = "✓ PASS" if passed else "✗ FAIL"
        if not passed:
            all_passed = False
        print(f"{setting:<25} {current:<15} {required:<15} {status:<10}")
    
    print("-" * 70)
    
    if all_passed:
        print("🎉 SYSTEM READY: Your system supports 1-hour video processing!")
        print("\nNext steps:")
        print("• Upload a 1-hour video to test the system")
        print("• Monitor memory usage during processing")
        print("• Check progress tracking in the UI")
    else:
        print("❌ SYSTEM NOT READY: Some settings need to be updated")
        print("\nTo fix:")
        print("• Update your .env file with the required values")
        print("• Restart the API server and Celery workers")
        print("• Run this script again to verify")
    
    print("\n" + "=" * 70)
    return all_passed

def main():
    """Main validation function."""
    try:
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        # Run checks
        checks = check_env_variables()
        success = print_results(checks)
        
        return 0 if success else 1
        
    except ImportError as e:
        print(f"Error: Missing dependency - {e}")
        print("Please install required packages: pip install python-dotenv")
        return 1
    except Exception as e:
        print(f"Error during validation: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())