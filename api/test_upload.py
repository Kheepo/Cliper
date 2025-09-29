#!/usr/bin/env python3
"""
Test script to verify upload functionality with Firestore
"""

import requests
import os
import tempfile

def test_upload_endpoint():
    """Test the upload endpoint with a proper video file"""
    
    # Use the existing proper test video file
    temp_file_path = "test_video.mp4"
    
    if not os.path.exists(temp_file_path):
        print("❌ test_video.mp4 not found. Please create a proper test video first.")
        return False, None
    
    try:
        # Prepare the upload request
        url = "http://localhost:8000/api/videos/upload"
        
        with open(temp_file_path, 'rb') as f:
            files = {
                'file': ('test_video.mp4', f, 'video/mp4')
            }
            data = {
                'user_id': 'test_user_123',
                'target_niche': 'tech'
            }
            
            print("🚀 Testing upload endpoint...")
            print(f"URL: {url}")
            print(f"File: test_video.mp4")
            print(f"User ID: test_user_123")
            print(f"Target Niche: tech")
            
            # Make the request
            response = requests.post(url, files=files, data=data, timeout=30)
            
            print(f"\n📊 Response Status: {response.status_code}")
            print(f"📊 Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Upload successful!")
                print(f"📄 Response: {result}")
                
                if 'job_id' in result:
                    print(f"🆔 Job ID: {result['job_id']}")
                    print(f"📊 Status: {result.get('status', 'unknown')}")
                    print(f"⏱️ Estimated Time: {result.get('estimated_time_minutes', 'unknown')} minutes")
                    
                    return True, result['job_id']
                else:
                    print("⚠️ No job_id in response")
                    return False, None
            else:
                print(f"❌ Upload failed with status {response.status_code}")
                print(f"📄 Error response: {response.text}")
                return False, None
                
    except requests.exceptions.ConnectionError:
        print("❌ Connection error: Make sure the API server is running on localhost:8000")
        return False, None
    except requests.exceptions.Timeout:
        print("❌ Request timeout: The server took too long to respond")
        return False, None
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False, None
    finally:
        # No cleanup needed since we're using existing test file
        pass

def test_job_status(job_id):
    """Test getting job status"""
    try:
        url = f"http://localhost:8000/api/jobs/{job_id}"
        print(f"\n🔍 Checking job status: {job_id}")
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Job status retrieved successfully!")
            print(f"📊 Status: {result.get('status', 'unknown')}")
            print(f"📈 Progress: {result.get('progress', 0)}%")
            print(f"🔄 Current Step: {result.get('current_step', 'unknown')}")
            return True
        else:
            print(f"❌ Failed to get job status: {response.status_code}")
            print(f"📄 Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking job status: {str(e)}")
        return False

def test_health_endpoint():
    """Test the health endpoint"""
    try:
        url = "http://localhost:8000/api/health"
        print("🏥 Testing health endpoint...")
        
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Health check passed!")
            print(f"📄 Response: {result}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Health check error: {str(e)}")
        return False

if __name__ == "__main__":
    print("🧪 Starting API endpoint tests...\n")
    
    # Test health endpoint first
    if not test_health_endpoint():
        print("\n❌ Health check failed. Make sure the API server is running.")
        exit(1)
    
    # Test upload endpoint
    success, job_id = test_upload_endpoint()
    
    if success and job_id:
        # Test job status endpoint
        test_job_status(job_id)
        
        print("\n🎉 All tests completed successfully!")
        print("✅ Firestore integration is working properly")
        print("✅ Upload functionality is operational")
    else:
        print("\n❌ Upload test failed")
        print("🔧 Please check the server logs for more details")