import requests
import os

# Get token
access_token = os.environ.get('ACCESS_TOKEN')
if not access_token:
    print("No access token found")
    exit(1)

print("Testing simple upload...")

# Create a simple test file
with open('simple_test.mp4', 'wb') as f:
    # Write minimal MP4 header
    f.write(b'\x00\x00\x00\x20ftypiso\x00\x00\x02\x00isomiso2avc1mp41')
    # Add some dummy data
    f.write(b'\x00' * 1000)

print("Created simple test file")

# Upload with requests
url = "http://localhost:8000/api/jobs/upload"
headers = {"Authorization": f"Bearer {access_token}"}

with open('simple_test.mp4', 'rb') as f:
    files = {'file': ('simple_test.mp4', f, 'video/mp4')}
    data = {
        'title': 'Simple Test Upload',
        'description': 'Testing upload with minimal file'
    }
    
    try:
        response = requests.post(url, headers=headers, files=files, data=data)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code in [200, 201]:
            result = response.json()
            job_id = result.get('id')
            print(f"SUCCESS! Job ID: {job_id}")
            
            # Save job ID
            with open('test_job_id.txt', 'w') as job_file:
                job_file.write(str(job_id))
            
            os.environ['TEST_JOB_ID'] = str(job_id)
            print(f"Job ID saved: {job_id}")
            
    except Exception as e:
        print(f"Error: {e}")
