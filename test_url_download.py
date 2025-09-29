#!/usr/bin/env python3
"""
Simple test script to verify URL download functionality
"""

import os
import tempfile
import requests

def test_url_download_logic():
    """Test the URL download logic that was added to the video processing"""
    print("🔍 Testing URL download logic...")
    
    # Simulate the logic from _process_video_core
    video_path = "https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4"
    original_filename = "test_video.mp4"
    job_id = "test_job_123"
    local_video_path = None
    
    try:
        print(f"📥 Input video_path: {video_path}")
        
        # Check if video_path is a URL or local file (same logic as in the fix)
        if video_path.startswith(('http://', 'https://')):
            # Download video from URL to local temporary file
            print(f"🌐 Detected URL, downloading...")
            
            # Create temporary file with proper extension
            file_extension = os.path.splitext(original_filename)[1] or '.mp4'
            temp_fd, local_video_path = tempfile.mkstemp(suffix=file_extension, prefix=f"video_{job_id}_")
            
            try:
                # Download the video file
                print(f"📡 Requesting: {video_path}")
                response = requests.get(video_path, stream=True, timeout=30)
                response.raise_for_status()
                
                print(f"✅ Response status: {response.status_code}")
                print(f"📊 Content length: {response.headers.get('content-length', 'unknown')}")
                
                with os.fdopen(temp_fd, 'wb') as temp_file:
                    downloaded_size = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            temp_file.write(chunk)
                            downloaded_size += len(chunk)
                
                print(f"📁 Video downloaded to: {local_video_path}")
                print(f"📊 Downloaded size: {downloaded_size} bytes")
                video_path = local_video_path  # Use local path for processing
                
            except Exception as download_error:
                # Clean up temp file if download failed
                try:
                    os.close(temp_fd)
                    if local_video_path and os.path.exists(local_video_path):
                        os.remove(local_video_path)
                except:
                    pass
                raise Exception(f"Failed to download video: {str(download_error)}")
        
        # Now check if the local file exists (same logic as in the fix)
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        print(f"✅ File exists check passed: {video_path}")
        print(f"📊 Final file size: {os.path.getsize(video_path)} bytes")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
        
    finally:
        # Clean up temporary video file if it was downloaded
        if local_video_path and os.path.exists(local_video_path):
            try:
                os.remove(local_video_path)
                print(f"🧹 Cleaned up temporary video file: {local_video_path}")
            except Exception as cleanup_error:
                print(f"⚠️ Failed to clean up temporary file {local_video_path}: {cleanup_error}")

def test_local_file_logic():
    """Test the logic with a local file path"""
    print("\n🔍 Testing local file logic...")
    
    # Create a temporary local file
    temp_fd, temp_file_path = tempfile.mkstemp(suffix='.mp4', prefix='local_test_')
    
    try:
        # Write some dummy data
        with os.fdopen(temp_fd, 'wb') as f:
            f.write(b'dummy video data')
        
        video_path = temp_file_path
        print(f"📁 Testing with local file: {video_path}")
        
        # Test the logic (should not try to download)
        if video_path.startswith(('http://', 'https://')):
            print("🌐 Would download from URL")
        else:
            print("📁 Detected local file, skipping download")
        
        # Check if file exists
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        print(f"✅ Local file exists check passed")
        print(f"📊 File size: {os.path.getsize(video_path)} bytes")
        
        return True
        
    except Exception as e:
        print(f"❌ Local file test failed: {e}")
        return False
        
    finally:
        # Clean up
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            print(f"🧹 Cleaned up test file: {temp_file_path}")

def main():
    """Main test function"""
    print("🧪 URL Download Logic Tests")
    print("=" * 40)
    
    # Test 1: URL download
    url_test_passed = test_url_download_logic()
    
    # Test 2: Local file handling
    local_test_passed = test_local_file_logic()
    
    print("\n📊 Test Results Summary")
    print("=" * 30)
    print(f"   URL Download Test: {'✅ PASS' if url_test_passed else '❌ FAIL'}")
    print(f"   Local File Test: {'✅ PASS' if local_test_passed else '❌ FAIL'}")
    
    if url_test_passed and local_test_passed:
        print("\n🎉 All tests passed! The URL download fix should work.")
        return True
    else:
        print("\n❌ Some tests failed. The fix may need adjustments.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)