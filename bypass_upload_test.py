import requests
import os
import tempfile

# Test video upload with clean data
print("Testing bypass video upload...")

# Create minimal test video file with clean name
with open('clean_test.mp4', 'wb') as f:
    # Simple MP4 header without special characters
    f.write(b'\x00\x00\x00\x20ftypiso\x00\x00\x02\x00isomiso2avc1mp41')
    f.write(b'\x00' * 500)  # 500 bytes dummy data

print("Created clean test file")

# Upload with very clean parameters
url = 'http://localhost:8000/api/jobs/upload'
headers = {'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsImtpZCI6InZMNGovQS9jZXNQdkRrZDgiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL3N0emR5d2hiZG92am9qdHF4bXNkLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiJiMzIwNTVjMi01NDM1LTRhNjctYjZjYi1mODliYTZkOTI5MTYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzU5MTAxNzQ0LCJpYXQiOjE3NTkwOTgxNDQsImVtYWlsIjoidGVzdHVzZXI4MjIwQGV4YW1wbGUuY29tIiwicGhvbmUiOiIiLCJhcHBfbWV0YWRhdGEiOnsicHJvdmlkZXIiOiJlbWFpbCIsInByb3ZpZGVycyI6WyJlbWFpbCJdfSwidXNlcl9tZXRhZGF0YSI6eyJlbWFpbF92ZXJpZmllZCI6dHJ1ZX0sInJvbGUiOiJhdXRoZW50aWNhdGVkIiwiYWFsIjoiYWFsMSIsImFtciI6W3sibWV0aG9kIjoicGFzc3dvcmQiLCJ0aW1lc3RhbXAiOjE3NTkwOTgxNDR9XSwic2Vzc2lvbl9pZCI6ImNlNmY2ZGQxLWYwOWEtNGYxZi1iYzFkLTBkOGZjODQzYjg3NiIsImlzX2Fub255bW91cyI6ZmFsc2V9.Jz_tWGnhnAXhXJtDxjRzzExgZjLAuBdvh-4lbjaye3Y'}

# Use very simple, clean form data
with open('clean_test.mp4', 'rb') as f:
    files = {'file': ('clean_test.mp4', f, 'video/mp4')}
    data = {
        'title': 'CleanTest',  # No spaces or special chars
        'description': 'Simple clean test upload'  # Avoid any trigger words
    }
    
    try:
        response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        
        print(f'Status: {response.status_code}')
        print(f'Response: {response.text}')
        
        if response.status_code in [200, 201]:
            result = response.json()
            job_id = result.get('id')
            print(f'SUCCESS! Job ID: {job_id}')
            
            # Save job ID
            with open('bypass_job_id.txt', 'w') as job_file:
                job_file.write(str(job_id))
            print('Job ID saved to bypass_job_id.txt')
        else:
            print(f'Upload failed with status {response.status_code}')
            print(f'Error details: {response.text}')
            
    except Exception as e:
        print(f'Request failed: {str(e)}')
        
# Cleanup
os.remove('clean_test.mp4')
print('Test file cleaned up')
