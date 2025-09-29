import requests
import time
import traceback
import uuid
import os

def test_health_check():
    """Test if the API is responding"""
    try:
        response = requests.get("http://localhost:8000/", timeout=10)
        print(f"Health check: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_file_upload():
    """Test file upload functionality"""
    try:
        user_id = str(uuid.uuid4())
        print(f"Testing file upload with user_id: {user_id}")
        
        url = "http://localhost:8000/api/videos/upload"
        
        # Create a minimal MP4 header for testing
        mp4_header = b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom\x00\x00\x00\x08free'
        test_content = mp4_header + b'\x00' * 100
        
        files = {
            'file': ('test_video.mp4', test_content, 'video/mp4')
        }
        
        data = {
            'user_id': user_id
        }
        
        print("Sending file upload request...")
        response = requests.post(url, files=files, data=data, timeout=60)
        
        print(f"Upload Status Code: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Upload successful! Job ID: {result.get('job_id')}")
            return True, result.get('job_id')
        else:
            print(f"Upload failed: {response.text}")
            return False, None
            
    except Exception as e:
        print(f"File upload test failed: {e}")
        traceback.print_exc()
        return False, None

def test_url_processing():
    """Test URL processing functionality"""
    try:
        user_id = str(uuid.uuid4())
        print(f"Testing URL processing with user_id: {user_id}")
        
        url = "http://localhost:8000/api/videos/process-url"
        
        data = {
            'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',  # Rick Roll for testing
            'user_id': user_id
        }
        
        print("Sending URL processing request...")
        response = requests.post(url, data=data, timeout=30)
        
        print(f"URL Processing Status Code: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"URL processing initiated! Job ID: {result.get('job_id')}")
            return True, result.get('job_id')
        else:
            print(f"URL processing failed: {response.text}")
            return False, None
            
    except Exception as e:
        print(f"URL processing test failed: {e}")
        traceback.print_exc()
        return False, None

def test_job_status(job_id):
    """Test job status endpoint"""
    try:
        url = f"http://localhost:8000/api/jobs/{job_id}/status"
        response = requests.get(url, timeout=10)
        
        print(f"Job Status Code: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Job status: {result.get('status')} - {result.get('current_step')}")
            return True
        else:
            print(f"Job status check failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"Job status test failed: {e}")
        return False

def main():
    print("=== Complete Upload Flow Test ===")
    
    # Test 1: Health check
    print("\n1. Testing API health...")
    if not test_health_check():
        print("❌ API health check failed")
        return
    print("✅ API is healthy")
    
    # Test 2: File upload
    print("\n2. Testing file upload...")
    upload_success, upload_job_id = test_file_upload()
    if upload_success:
        print("✅ File upload endpoint working")
        if upload_job_id:
            print(f"\n2a. Testing job status for upload job...")
            if test_job_status(upload_job_id):
                print("✅ Job status endpoint working for upload")
            else:
                print("⚠️ Job status endpoint failed for upload")
    else:
        print("❌ File upload failed")
    
    # Test 3: URL processing
    print("\n3. Testing URL processing...")
    url_success, url_job_id = test_url_processing()
    if url_success:
        print("✅ URL processing endpoint working")
        if url_job_id:
            print(f"\n3a. Testing job status for URL job...")
            if test_job_status(url_job_id):
                print("✅ Job status endpoint working for URL")
            else:
                print("⚠️ Job status endpoint failed for URL")
    else:
        print("❌ URL processing failed")
    
    print("\n=== Test Summary ===")
    print(f"✅ API Health: Working")
    print(f"{'✅' if upload_success else '❌'} File Upload: {'Working' if upload_success else 'Failed'}")
    print(f"{'✅' if url_success else '❌'} URL Processing: {'Working' if url_success else 'Failed'}")
    
    if upload_success and url_success:
        print("\n🎉 All upload functionality is working correctly!")
        print("Note: Video processing may fail with test files, but the upload mechanism itself is functional.")
    else:
        print("\n⚠️ Some functionality needs attention.")

if __name__ == "__main__":
    main()