import asyncio
import aiohttp
import json
import os
import tempfile
from datetime import datetime
from typing import Dict, Any, Optional

# Test configuration
API_BASE_URL = "http://localhost:8001/api"
TEST_EMAIL_PREFIX = "test_"
TEST_PASSWORD = "TestPassword123!"

class AuthenticatedUploadTester:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.test_email: Optional[str] = None
        self.results = []
        
    async def setup_session(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
            
    def log_result(self, test_name: str, success: bool, message: str, details: Dict[str, Any] = None):
        """Log test result"""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        self.results.append(result)
        status = "✅" if success else "❌"
        print(f"{status} {test_name}: {message}")
        if details:
            print(f"   Details: {details}")
            
    async def create_test_video_file(self, size_mb: int) -> str:
        """Create a test video file with realistic content pattern"""
        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        
        # Generate realistic video-like binary data
        # MP4 files start with specific headers
        mp4_header = b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom'
        temp_file.write(mp4_header)
        
        # Fill with pseudo-random data to reach target size
        target_size = size_mb * 1024 * 1024
        remaining_size = target_size - len(mp4_header)
        
        # Write in chunks to avoid memory issues
        chunk_size = 8192
        pattern = b'\x00\x01\x02\x03\x04\x05\x06\x07' * (chunk_size // 8)
        
        while remaining_size > 0:
            write_size = min(chunk_size, remaining_size)
            temp_file.write(pattern[:write_size])
            remaining_size -= write_size
            
        temp_file.close()
        return temp_file.name
        
    async def test_user_registration(self):
        """Test user registration"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        self.test_email = f"{TEST_EMAIL_PREFIX}{unique_id}@example.com"
        
        registration_data = {
            "email": self.test_email,
            "password": TEST_PASSWORD,
            "display_name": "Test User"
        }
        
        try:
            async with self.session.post(
                f"{API_BASE_URL}/auth/register",
                json=registration_data
            ) as response:
                response_text = await response.text()
                
                # Registration can return 200 (success) or 201 (created)
                if response.status in [200, 201]:
                    try:
                        response_data = json.loads(response_text)
                        if "user" in response_data and "tokens" in response_data:
                            self.user_id = response_data["user"]["id"]
                            self.access_token = response_data["tokens"]["access_token"]
                            self.refresh_token = response_data["tokens"]["refresh_token"]
                            self.log_result(
                                "user_registration", 
                                True, 
                                "User registered successfully",
                                {"user_id": self.user_id, "has_tokens": bool(self.access_token)}
                            )
                            return True
                        else:
                            self.log_result(
                                "user_registration", 
                                False, 
                                f"Invalid response structure: {response_text[:200]}"
                            )
                            return False
                    except json.JSONDecodeError:
                        self.log_result(
                            "user_registration", 
                            False, 
                            f"Invalid JSON response: {response_text[:200]}"
                        )
                        return False
                else:
                    self.log_result(
                        "user_registration", 
                        False, 
                        f"Registration failed: {response.status}",
                        {"error": response_text}
                    )
                    return False
                    
        except Exception as e:
            self.log_result(
                "user_registration", 
                False, 
                f"Registration exception: {str(e)}"
            )
            return False
            
    async def test_user_login(self):
        """Test user login if registration failed"""
        if self.access_token:  # Already have token from registration
            self.log_result(
                "user_login", 
                True, 
                "User logged in successfully",
                {"user_id": self.user_id, "has_tokens": True}
            )
            return True
            
        if not self.test_email:
            self.log_result(
                "user_login", 
                False, 
                "No test email available for login"
            )
            return False
            
        login_data = {
            "email": self.test_email,
            "password": TEST_PASSWORD
        }
        
        try:
            async with self.session.post(
                f"{API_BASE_URL}/auth/login",
                json=login_data
            ) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    try:
                        response_data = json.loads(response_text)
                        if "user" in response_data and "tokens" in response_data:
                            self.user_id = response_data["user"]["id"]
                            self.access_token = response_data["tokens"]["access_token"]
                            self.refresh_token = response_data["tokens"]["refresh_token"]
                            self.log_result(
                                "user_login", 
                                True, 
                                "User logged in successfully",
                                {"user_id": self.user_id, "has_tokens": bool(self.access_token)}
                            )
                            return True
                        else:
                            self.log_result(
                                "user_login", 
                                False, 
                                f"Invalid login response structure: {response_text[:200]}"
                            )
                            return False
                    except json.JSONDecodeError:
                        self.log_result(
                            "user_login", 
                            False, 
                            f"Invalid JSON in login response: {response_text[:200]}"
                        )
                        return False
                else:
                    self.log_result(
                        "user_login", 
                        False, 
                        f"Login failed: {response.status}",
                        {"error": response_text}
                    )
                    return False
                    
        except Exception as e:
            self.log_result(
                "user_login", 
                False, 
                f"Login exception: {str(e)}"
            )
            return False
            
    async def test_authenticated_health_check(self):
        """Test authenticated health check"""
        if not self.access_token:
            self.log_result(
                "authenticated_health_check", 
                False, 
                "No access token available"
            )
            return False
            
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            async with self.session.get(
                f"{API_BASE_URL}/health",
                headers=headers
            ) as response:
                if response.status == 200:
                    self.log_result(
                        "authenticated_health_check", 
                        True, 
                        "Authenticated health check passed",
                        {"status": await response.text()}
                    )
                    return True
                else:
                    self.log_result(
                        "authenticated_health_check", 
                        False, 
                        f"Health check failed: {response.status}",
                        {"error": await response.text()}
                    )
                    return False
                    
        except Exception as e:
            self.log_result(
                "authenticated_health_check", 
                False, 
                f"Health check exception: {str(e)}"
            )
            return False
            
    async def test_video_upload(self, file_size_mb: int):
        """Test video upload with authentication"""
        if not self.access_token:
            self.log_result(
                f"video_upload_{file_size_mb}mb", 
                False, 
                "No access token available"
            )
            return False
            
        test_file = None
        try:
            # Create test file
            test_file = await self.create_test_video_file(file_size_mb)
            
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            # Prepare multipart form data - NO title field, only file and optional target_niche
            with open(test_file, 'rb') as f:
                form_data = aiohttp.FormData()
                form_data.add_field('file', f, filename=f'test_video_{file_size_mb}mb.mp4', content_type='video/mp4')
                form_data.add_field('target_niche', 'general')  # Optional field
                
                async with self.session.post(
                    f"{API_BASE_URL}/videos/upload",
                    headers=headers,
                    data=form_data
                ) as response:
                    response_text = await response.text()
                    
                    if response.status in [200, 201]:
                        try:
                            response_data = json.loads(response_text)
                            # Check for expected fields in response
                            if "video_id" in response_data or "job_id" in response_data:
                                self.log_result(
                                    f"video_upload_{file_size_mb}mb", 
                                    True, 
                                    "Video uploaded successfully",
                                    {
                                        "file_size_mb": file_size_mb,
                                        "response_keys": list(response_data.keys()),
                                        "status": response_data.get("status", "unknown")
                                    }
                                )
                                return True
                            else:
                                self.log_result(
                                    f"video_upload_{file_size_mb}mb", 
                                    False, 
                                    "Upload response missing expected fields",
                                    {
                                        "file_size_mb": file_size_mb,
                                        "response": response_text[:500]
                                    }
                                )
                                return False
                        except json.JSONDecodeError:
                            self.log_result(
                                f"video_upload_{file_size_mb}mb", 
                                False, 
                                "Invalid JSON in upload response",
                                {
                                    "file_size_mb": file_size_mb,
                                    "response": response_text[:500]
                                }
                            )
                            return False
                    else:
                        self.log_result(
                            f"video_upload_{file_size_mb}mb", 
                            False, 
                            f"Upload failed: {response.status}",
                            {
                                "error": response_text,
                                "file_size_mb": file_size_mb
                            }
                        )
                        return False
                        
        except Exception as e:
            self.log_result(
                f"video_upload_{file_size_mb}mb", 
                False, 
                f"Upload exception: {str(e)}",
                {"file_size_mb": file_size_mb}
            )
            return False
        finally:
            # Cleanup test file
            if test_file and os.path.exists(test_file):
                try:
                    os.unlink(test_file)
                except:
                    pass
                    
    async def test_url_processing(self):
        """Test URL processing endpoint"""
        if not self.access_token:
            self.log_result(
                "url_processing", 
                False, 
                "No access token available"
            )
            return False
            
        headers = {"Authorization": f"Bearer {self.access_token}"}
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll for testing
        
        try:
            # Use form data for URL processing
            form_data = aiohttp.FormData()
            form_data.add_field('url', test_url)
            form_data.add_field('target_niche', 'general')
            
            async with self.session.post(
                f"{API_BASE_URL}/videos/process-url",
                headers=headers,
                data=form_data
            ) as response:
                response_text = await response.text()
                
                if response.status in [200, 201]:
                    try:
                        response_data = json.loads(response_text)
                        self.log_result(
                            "url_processing", 
                            True, 
                            "URL processing initiated successfully",
                            {
                                "url": test_url,
                                "response_keys": list(response_data.keys())
                            }
                        )
                        return True
                    except json.JSONDecodeError:
                        self.log_result(
                            "url_processing", 
                            False, 
                            "Invalid JSON in URL processing response",
                            {"response": response_text[:500]}
                        )
                        return False
                else:
                    self.log_result(
                        "url_processing", 
                        False, 
                        f"URL processing failed: {response.status}",
                        {"error": response_text}
                    )
                    return False
                    
        except Exception as e:
            self.log_result(
                "url_processing", 
                False, 
                f"URL processing exception: {str(e)}"
            )
            return False
            
    async def test_job_status_monitoring(self, job_id: str):
        """Test job status monitoring"""
        if not self.access_token or not job_id:
            self.log_result(
                "job_status_monitoring", 
                False, 
                "No access token or job ID available"
            )
            return False
            
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            async with self.session.get(
                f"{API_BASE_URL}/jobs/{job_id}",
                headers=headers
            ) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    try:
                        response_data = json.loads(response_text)
                        self.log_result(
                            "job_status_monitoring", 
                            True, 
                            "Job status retrieved successfully",
                            {
                                "job_id": job_id,
                                "status": response_data.get("status", "unknown")
                            }
                        )
                        return True
                    except json.JSONDecodeError:
                        self.log_result(
                            "job_status_monitoring", 
                            False, 
                            "Invalid JSON in job status response",
                            {"response": response_text[:500]}
                        )
                        return False
                else:
                    self.log_result(
                        "job_status_monitoring", 
                        False, 
                        f"Job status check failed: {response.status}",
                        {"error": response_text}
                    )
                    return False
                    
        except Exception as e:
            self.log_result(
                "job_status_monitoring", 
                False, 
                f"Job status exception: {str(e)}"
            )
            return False
            
    async def run_all_tests(self):
        """Run all authentication and upload tests"""
        print("🚀 Starting Authenticated Upload Flow Tests...\n")
        
        await self.setup_session()
        
        try:
            # Test authentication flow
            await self.test_user_registration()
            await self.test_user_login()
            await self.test_authenticated_health_check()
            
            # Test upload functionality
            await self.test_video_upload(1)  # 1MB test
            await self.test_video_upload(5)  # 5MB test
            
            # Test URL processing
            await self.test_url_processing()
            
            # Cleanup
            self.log_result(
                "cleanup", 
                True, 
                f"Test completed for user: {self.test_email}",
                {"user_id": self.user_id}
            )
            
        finally:
            await self.cleanup_session()
            
    def generate_report(self):
        """Generate test report"""
        successful = sum(1 for r in self.results if r["success"])
        total = len(self.results)
        success_rate = (successful / total * 100) if total > 0 else 0
        
        report = {
            "summary": {
                "total_tests": total,
                "successful": successful,
                "failed": total - successful,
                "success_rate": success_rate
            },
            "results": self.results,
            "timestamp": datetime.now().isoformat()
        }
        
        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"auth_upload_test_report_{timestamp}.json"
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        print(f"\n📊 Test Summary:")
        print(f"   Total Tests: {total}")
        print(f"   Successful: {successful}")
        print(f"   Failed: {total - successful}")
        print(f"   Success Rate: {success_rate:.1f}%")
        print(f"   Report saved: {report_file}")
        
        # Print key findings
        print(f"\n🔍 Key Findings:")
        auth_tests = [r for r in self.results if 'login' in r['test'] or 'registration' in r['test'] or 'health' in r['test']]
        upload_tests = [r for r in self.results if 'upload' in r['test'] or 'url' in r['test']]
        
        auth_success = sum(1 for r in auth_tests if r['success'])
        upload_success = sum(1 for r in upload_tests if r['success'])
        
        print(f"   Authentication: {auth_success}/{len(auth_tests)} tests passed")
        print(f"   Upload/Processing: {upload_success}/{len(upload_tests)} tests passed")
        
        if upload_success < len(upload_tests):
            failed_uploads = [r for r in upload_tests if not r['success']]
            print(f"   Upload Issues: {[r['test'] + ': ' + r['message'] for r in failed_uploads]}")
            
        return report

async def main():
    """Main test execution"""
    tester = AuthenticatedUploadTester()
    await tester.run_all_tests()
    tester.generate_report()

if __name__ == "__main__":
    asyncio.run(main())