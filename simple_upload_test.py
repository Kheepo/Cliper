import requests
import os

# Test video upload
print("Testing video upload...")

# Create minimal test video file
with open('test_upload.mp4', 'wb') as f:
    # MP4 file signature
    f.write(b'\x00\x00\x00\x20ftypiso\x00\x00\x02\x00isomiso2avc1mp41')
    f.write(b'\x00' * 1000)  # 1KB dummy data

print("Created test file")

# Upload parameters
url = 'http://localhost:8000/api/jobs/upload'
headers = {'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsImtpZCI6InZMNGovQS9jZXNQdkRrZDgiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL3N0emR5d2hiZG92am9qdHF4bXNkLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI2ZWJkOTMyZi01ZmY1LTQwMWQtOTBmNy05Y2M3ZjgxZjdjNzkiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzU5MTAxNjA4LCJpYXQiOjE3NTkwOTgwMDgsImVtYWlsIjoidGVzdHVzZXIyODY4QGV4YW1wbGUuY29tIiwicGhvbmUiOiIiLCJhcHBfbWV0YWRhdGEiOnsicHJvdmlkZXIiOiJlbWFpbCIsInByb3ZpZGVycyI6WyJlbWFpbCJdfSwidXNlcl9tZXRhZGF0YSI6eyJlbWFpbF92ZXJpZmllZCI6dHJ1ZX0sInJvbGUiOiJhdXRoZW50aWNhdGVkIiwiYWFsIjoiYWFsMSIsImFtciI6W3sibWV0aG9kIjoicGFzc3dvcmQiLCJ0aW1lc3RhbXAiOjE3NTkwOTgwMDh9XSwic2Vzc2lvbl9pZCI6IjNkYjFjZWVhLTA1NDQtNDdkNi1iY2Y1LWJiMWFhOGIyMzlkOCIsImlzX2Fub255bW91cyI6ZmFsc2V9.CvbWzbXqzcF1harIenHUw2TyXmejz9dAS_4BRvU_yu8'}

with open('test_upload.mp4', 'rb') as f:
    files = {'file': ('test_upload.mp4', f, 'video/mp4')}
    data = {'title': 'Test Upload', 'description': 'Simple test'}
    
    response = requests.post(url, headers=headers, files=files, data=data)
    
    print(f'Status: {response.status_code}')
    print(f'Response: {response.text}')
    
    if response.status_code in [200, 201]:
        result = response.json()
        job_id = result.get('id')
        print(f'SUCCESS! Job ID: {job_id}')
        
        # Save job ID
        with open('test_job_id.txt', 'w') as job_file:
            job_file.write(str(job_id))
        print('Job ID saved')
    else:
        print('Upload failed')
        
# Cleanup
os.remove('test_upload.mp4')
print('Test file cleaned up')
