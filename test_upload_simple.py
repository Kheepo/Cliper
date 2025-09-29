import requests
import io

# Create a simple test file
test_content = b"This is a test video file content"
test_file = io.BytesIO(test_content)
test_file.name = "test_video.mp4"

# Prepare the upload
files = {'file': ('test_video.mp4', test_file, 'video/mp4')}
data = {'user_id': 'test-user-123'}

try:
    print("Testing video upload endpoint...")
    response = requests.post(
        'http://localhost:8001/api/videos/upload',
        files=files,
        data=data,
        timeout=30
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("✅ Upload endpoint is working!")
    else:
        print("❌ Upload endpoint returned an error")
        
except requests.exceptions.RequestException as e:
    print(f"❌ Request failed: {e}")
except Exception as e:
    print(f"❌ Unexpected error: {e}")