import requests
import os

# Get token from environment
access_token = os.environ.get('ACCESS_TOKEN')
if not access_token:
    print("No access token found in environment")
    exit(1)

print(f"Using token (first 20 chars): {access_token[:20]}...")

# Test video upload with correct form structure
url = "http://localhost:8000/api/jobs/upload"
headers = {
    "Authorization": f"Bearer {access_token}"
}

# Open file and prepare form data
with open("test_video.mp4", "rb") as f:
    files = {
        "file": ("test_video.mp4", f, "video/mp4")
    }
    
    data = {
        "title": "Test Video Upload for Clip Generation",
        "description": "Testing video upload functionality for comprehensive verification"
    }
    
    try:
        print("Uploading video to /api/jobs/upload...")
        response = requests.post(url, headers=headers, files=files, data=data)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200 or response.status_code == 201:
            result = response.json()
            print(f" Upload successful!")
            print(f"Job ID: {result.get('id')}")
            print(f"Status: {result.get('status')}")
            print(f"Title: {result.get('title')}")
            
            # Save job ID for later use
            with open("test_job_id.txt", "w") as job_file:
                job_file.write(str(result.get('id', '')))
            print("Job ID saved to test_job_id.txt")
            
            # Also save as environment variable for immediate use
            os.environ['TEST_JOB_ID'] = str(result.get('id', ''))
            print(f"Job ID set in environment: {result.get('id')}")
            
        else:
            print(f"Upload failed with status {response.status_code}")
            print(f"Error details: {response.text}")
                
    except Exception as e:
        print(f"Error: {e}")
