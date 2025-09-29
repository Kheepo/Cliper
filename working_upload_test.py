import requests
import os
import tempfile

def test_video_upload():
    # Get access token
    access_token = os.environ.get('ACCESS_TOKEN')
    if not access_token:
        print(" No access token found")
        return False
    
    print(" Testing video upload with proper multipart encoding...")
    
    # Create a minimal valid video file
    test_file_path = 'working_test.mp4'
    with open(test_file_path, 'wb') as f:
        # Write minimal MP4 header (ftyp box)
        f.write(b'\x00\x00\x00\x20ftypiso\x00\x00\x02\x00isomiso2avc1mp41')
        # Add some dummy video data
        f.write(b'\x00' * 2000)  # 2KB of dummy data
    
    print(f" Created test file: {test_file_path} ({os.path.getsize(test_file_path)} bytes)")
    
    # Prepare upload
    url = "http://localhost:8000/api/jobs/upload"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    # Use proper multipart form data
    with open(test_file_path, 'rb') as video_file:
        files = {
            'file': ('working_test.mp4', video_file, 'video/mp4')
        }
        data = {
            'title': 'Working Upload Test',
            'description': 'Testing proper multipart form encoding for video upload'
        }
        
        try:
            print(" Sending upload request...")
            response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
            
            print(f"📊 Response Status: {response.status_code}")
            print(f" Response Headers: {dict(response.headers)}")
            print(f" Response Body: {response.text}")
            
            if response.status_code in [200, 201]:
                result = response.json()
                job_id = result.get('id')
                print(f" SUCCESS! Job created with ID: {job_id}")
                
                # Save job ID for further testing
                with open('working_job_id.txt', 'w') as f:
                    f.write(str(job_id))
                
                # Set environment variable
                os.environ['TEST_JOB_ID'] = str(job_id)
                
                return True
            else:
                print(f" Upload failed with status {response.status_code}")
                print(f"Error details: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f" Request failed: {e}")
            return False
        except Exception as e:
            print(f" Unexpected error: {e}")
            return False
        finally:
            # Clean up test file
            if os.path.exists(test_file_path):
                os.remove(test_file_path)
                print(f" Cleaned up test file: {test_file_path}")

if __name__ == '__main__':
    success = test_video_upload()
    if success:
        print("\n Video upload test PASSED!")
        exit(0)
    else:
        print("\n Video upload test FAILED!")
        exit(1)
