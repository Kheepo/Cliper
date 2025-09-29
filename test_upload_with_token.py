import requests
import os

# Get token from environment
access_token = os.environ.get('ACCESS_TOKEN')
if not access_token:
    print("No access token found in environment")
    exit(1)

print(f"Using token (first 20 chars): {access_token[:20]}...")

# Test video upload
url = "http://localhost:8000/api/jobs/upload"
headers = {
    "Authorization": f"Bearer {access_token}"
}

files = {
    "file": ("test_video.mp4", open("test_video.mp4", "rb"), "video/mp4")
}

data = {
    "target_platforms": "tiktok,youtube,instagram",
    "max_clips": "3",
    "min_virality_score": "70.0",
    "generate_thumbnails": "true",
    "generate_hashtags": "true"
}

try:
    print("Uploading video to /api/jobs/upload...")
    response = requests.post(url, headers=headers, files=files, data=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200 or response.status_code == 201:
        result = response.json()
        print(f" Upload successful!")
        print(f"Job ID: {result.get('job_id')}")
        print(f"Status: {result.get('status')}")
        
        # Save job ID for later use
        with open("test_job_id.txt", "w") as f:
            f.write(result.get('job_id', ''))
        print("Job ID saved to test_job_id.txt")
    else:
        print(f"Upload failed with status {response.status_code}")
        print(f"Error details: {response.text}")
            
except Exception as e:
    print(f"Error: {e}")
