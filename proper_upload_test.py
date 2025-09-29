import requests
import sys

def test_upload():
    try:
        # Read the MP4 file
        with open('proper_test_video.mp4', 'rb') as f:
            file_content = f.read()
        
        print(f"File size: {len(file_content)} bytes")
        print(f"File header: {file_content[:16].hex()}")
        
        # Prepare the upload
        url = 'http://localhost:8000/api/jobs/upload'
        
        # Get access token from environment
        import os
        access_token = os.environ.get('ACCESS_TOKEN')
        if not access_token:
            print("ERROR: No access token found")
            return False
            
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        # Prepare form data
        files = {
            'file': ('test_video.mp4', file_content, 'video/mp4')
        }
        
        data = {
            'title': 'Test Upload',
            'description': 'Testing video upload functionality'
        }
        
        print("Sending upload request...")
        response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"SUCCESS! Job created with ID: {result.get('id')}")
            print(f"Job details: {result}")
            
            # Save job ID for status checking
            with open('successful_job_id.txt', 'w') as f:
                f.write(str(result.get('id')))
            
            return True
        else:
            print(f"FAILED: {response.status_code}")
            try:
                error_detail = response.json()
                print(f"Error details: {error_detail}")
            except:
                print(f"Error text: {response.text}")
            return False
            
    except Exception as e:
        print(f"Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_upload()
    sys.exit(0 if success else 1)
