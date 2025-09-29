import requests
import time

def test_video_upload_workflow():
    """Test complete video upload and processing workflow"""
    
    # Upload a new video
    url = 'http://localhost:8001/api/videos/upload'
    files = {'file': ('test_video.mp4', open('test_video.mp4', 'rb'), 'video/mp4')}
    data = {'user_id': '12345678-1234-1234-1234-123456789012'}
    
    print('🚀 Uploading video...')
    response = requests.post(url, files=files, data=data)
    print(f'Upload Status: {response.status_code}')
    print(f'Upload Response: {response.text}')
    
    if response.status_code == 200:
        job_data = response.json()
        job_id = job_data['job_id']
        print(f'\n📋 Job ID: {job_id}')
        
        # Check job status multiple times
        for i in range(5):
            time.sleep(2)
            status_url = f'http://localhost:8001/api/jobs/{job_id}/status'
            status_response = requests.get(status_url)
            if status_response.status_code == 200:
                status_data = status_response.json()
                print(f'\n⏱️  Check {i+1}: Status={status_data["status"]}, Progress={status_data["progress"]}%, Step={status_data["current_step"]}')
                if status_data['status'] in ['complete', 'failed']:
                    break
            else:
                print(f'\n❌ Status check failed: {status_response.status_code}')
                
        # Test job results endpoint
        results_url = f'http://localhost:8001/api/jobs/{job_id}/results'
        results_response = requests.get(results_url)
        print(f'\n📊 Results Status: {results_response.status_code}')
        if results_response.status_code == 200:
            print(f'Results: {results_response.text}')
        else:
            print(f'Results Error: {results_response.text}')
    else:
        print(f'❌ Upload failed: {response.text}')

if __name__ == '__main__':
    test_video_upload_workflow()