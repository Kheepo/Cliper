import requests
import json
import os

def test_auth_and_upload():
    # Test login
    print("Testing login...")
    login_response = requests.post('http://localhost:8000/api/auth/login', 
                                 json={'email': 'test@example.com', 'password': 'password123'})
    
    print(f"Login response: {login_response.status_code}")
    print(f"Login response body: {login_response.text[:500]}")
    
    if login_response.status_code != 200:
        print("Login failed, cannot proceed with upload test")
        return
    
    # Extract token
    login_data = login_response.json()
    if 'session' not in login_data or 'access_token' not in login_data['session']:
        print("No access token in login response")
        print(f"Available keys: {list(login_data.keys())}")
        return
    
    token = login_data['session']['access_token']
    print(f"Token obtained: {token[:50]}...")
    
    # Test upload
    print("\nTesting video upload...")
    if not os.path.exists('test_video.mp4'):
        print("test_video.mp4 not found, cannot test upload")
        return
    
    with open('test_video.mp4', 'rb') as f:
        files = {'file': f}
        data = {'title': 'Test Upload', 'description': 'Testing job creation'}
        headers = {'Authorization': f'Bearer {token}'}
        
        upload_response = requests.post('http://localhost:8000/api/videos/upload', 
                                      files=files, data=data, headers=headers)
    
    print(f"Upload response: {upload_response.status_code}")
    print(f"Upload response body: {upload_response.text}")
    
    if upload_response.status_code == 200:
        print("\n✅ Upload successful!")
    else:
        print("\n❌ Upload failed")

if __name__ == "__main__":
    test_auth_and_upload()