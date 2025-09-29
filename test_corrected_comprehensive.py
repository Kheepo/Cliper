#!/usr/bin/env python3
"""
Corrected Comprehensive End-to-End Application Test
Tests all critical functionality with correct URLs
"""

import requests
import json
import time
import os
from datetime import datetime

# Configuration - Updated with correct ports
BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3001"  # Corrected frontend port
TEST_EMAIL = f"test_{int(time.time())}@example.com"
TEST_PASSWORD = "TestPassword123!"

class CorrectedComprehensiveTest:
    def __init__(self):
        self.results = {
            "backend_connectivity": {},
            "authentication": {},
            "user_management": {},
            "video_processing": {},
            "database_operations": {},
            "frontend_connectivity": {},
            "api_endpoints": {},
            "error_handling": {},
            "critical_issues": [],
            "working_features": [],
            "broken_features": [],
            "recommendations": []
        }
        self.access_token = None
        self.user_id = None

    def test_backend_connectivity(self):
        """Test backend connectivity with proper timeout handling"""
        print("\n🔗 Testing Backend Connectivity...")
        
        # Test health endpoint with longer timeout
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=15)
            self.results["backend_connectivity"]["health"] = {
                "status": response.status_code,
                "working": response.status_code == 200,
                "response_time": response.elapsed.total_seconds()
            }
            if response.status_code == 200:
                print(f"  ✓ Health endpoint working (response time: {response.elapsed.total_seconds():.2f}s)")
                self.results["working_features"].append("Backend health endpoint")
            else:
                print(f"  ✗ Health endpoint failed: {response.status_code}")
                self.results["broken_features"].append("Backend health endpoint")
        except requests.exceptions.Timeout:
            print("  ⚠ Health endpoint timeout (>15s) - server may be overloaded")
            self.results["backend_connectivity"]["health"] = {"error": "Timeout", "working": False}
            self.results["broken_features"].append("Backend health endpoint (timeout)")
        except Exception as e:
            print(f"  ✗ Backend connectivity failed: {e}")
            self.results["backend_connectivity"]["health"] = {"error": str(e), "working": False}
            self.results["critical_issues"].append("Backend server not accessible")
            self.results["broken_features"].append("Backend connectivity")

        # Test API documentation
        try:
            response = requests.get(f"{BASE_URL}/docs", timeout=10)
            self.results["backend_connectivity"]["docs"] = {
                "status": response.status_code,
                "working": response.status_code == 200
            }
            if response.status_code == 200:
                print("  ✓ API documentation accessible")
                self.results["working_features"].append("API documentation")
            else:
                print(f"  ✗ API documentation failed: {response.status_code}")
        except Exception as e:
            print(f"  ✗ API documentation error: {e}")
            self.results["backend_connectivity"]["docs"] = {"error": str(e), "working": False}

    def test_frontend_connectivity(self):
        """Test frontend connectivity with correct port"""
        print("\n🌐 Testing Frontend Connectivity...")
        
        try:
            response = requests.get(FRONTEND_URL, timeout=10)
            self.results["frontend_connectivity"]["main"] = {
                "status": response.status_code,
                "working": response.status_code == 200,
                "content_length": len(response.content)
            }
            if response.status_code == 200:
                print(f"  ✓ Frontend server accessible (content: {len(response.content)} bytes)")
                self.results["working_features"].append("Frontend server")
                
                # Check if it's actually serving the React app
                if "react" in response.text.lower() or "vite" in response.text.lower():
                    print("  ✓ React/Vite application detected")
                    self.results["working_features"].append("React application")
                else:
                    print("  ⚠ Frontend serving content but may not be React app")
            else:
                print(f"  ✗ Frontend server failed: {response.status_code}")
                self.results["broken_features"].append("Frontend server")
        except Exception as e:
            print(f"  ✗ Frontend connectivity failed: {e}")
            self.results["frontend_connectivity"]["main"] = {"error": str(e), "working": False}
            self.results["critical_issues"].append("Frontend server not accessible")
            self.results["broken_features"].append("Frontend connectivity")

    def test_authentication_flow(self):
        """Test complete authentication flow with detailed analysis"""
        print("\n🔐 Testing Authentication Flow...")
        
        # Test registration
        try:
            register_data = {
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
                "display_name": "Test User"
            }
            response = requests.post(f"{BASE_URL}/api/auth/register", json=register_data, timeout=15)
            self.results["authentication"]["registration"] = {
                "status": response.status_code,
                "working": response.status_code == 200,
                "response_data": response.json() if response.status_code == 200 else response.text
            }
            
            if response.status_code == 200:
                print("  ✓ User registration working")
                self.results["working_features"].append("User registration")
                data = response.json()
                print(f"    - User ID: {data.get('user', {}).get('id', 'N/A')}")
                print(f"    - Email: {data.get('user', {}).get('email', 'N/A')}")
            else:
                print(f"  ✗ Registration failed: {response.status_code} - {response.text}")
                self.results["broken_features"].append("User registration")
                return False
                
        except Exception as e:
            print(f"  ✗ Registration error: {e}")
            self.results["authentication"]["registration"] = {"error": str(e), "working": False}
            self.results["broken_features"].append("User registration")
            return False

        # Test login
        try:
            login_data = {
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            }
            response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data, timeout=15)
            self.results["authentication"]["login"] = {
                "status": response.status_code,
                "working": response.status_code == 200
            }
            
            if response.status_code == 200:
                print("  ✓ User login working")
                data = response.json()
                self.access_token = data.get("access_token")
                self.user_id = data.get("user", {}).get("id")
                print(f"    - Access token received: {bool(self.access_token)}")
                print(f"    - Token length: {len(self.access_token) if self.access_token else 0}")
                self.results["working_features"].append("User login")
                return True
            else:
                print(f"  ✗ Login failed: {response.status_code} - {response.text}")
                self.results["broken_features"].append("User login")
                return False
                
        except Exception as e:
            print(f"  ✗ Login error: {e}")
            self.results["authentication"]["login"] = {"error": str(e), "working": False}
            self.results["broken_features"].append("User login")
            return False

    def test_user_management(self):
        """Test user profile and settings management"""
        print("\n👤 Testing User Management...")
        
        if not self.access_token:
            print("  ⚠ Skipping user management tests - no access token")
            self.results["critical_issues"].append("Cannot test user management - authentication failed")
            return

        headers = {"Authorization": f"Bearer {self.access_token}"}

        # Test profile retrieval
        try:
            response = requests.get(f"{BASE_URL}/api/auth/profile", headers=headers, timeout=10)
            self.results["user_management"]["profile_get"] = {
                "status": response.status_code,
                "working": response.status_code == 200
            }
            
            if response.status_code == 200:
                print("  ✓ Profile retrieval working")
                profile_data = response.json()
                print(f"    - Profile ID: {profile_data.get('id', 'N/A')}")
                print(f"    - Display name: {profile_data.get('display_name', 'N/A')}")
                self.results["working_features"].append("Profile retrieval")
            else:
                print(f"  ✗ Profile retrieval failed: {response.status_code} - {response.text}")
                self.results["broken_features"].append("Profile retrieval")
                if response.status_code == 500:
                    self.results["critical_issues"].append("Profile endpoint returns 500 error")
                
        except Exception as e:
            print(f"  ✗ Profile retrieval error: {e}")
            self.results["user_management"]["profile_get"] = {"error": str(e), "working": False}
            self.results["broken_features"].append("Profile retrieval")

        # Test user settings
        try:
            response = requests.get(f"{BASE_URL}/api/user/settings", headers=headers, timeout=10)
            self.results["user_management"]["settings_get"] = {
                "status": response.status_code,
                "working": response.status_code == 200
            }
            
            if response.status_code == 200:
                print("  ✓ User settings retrieval working")
                self.results["working_features"].append("User settings")
            else:
                print(f"  ✗ User settings failed: {response.status_code}")
                self.results["broken_features"].append("User settings")
                
        except Exception as e:
            print(f"  ✗ User settings error: {e}")
            self.results["user_management"]["settings_get"] = {"error": str(e), "working": False}

    def test_api_endpoints(self):
        """Test various API endpoints"""
        print("\n🔌 Testing API Endpoints...")
        
        if not self.access_token:
            print("  ⚠ Skipping API endpoint tests - no access token")
            return

        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        endpoints_to_test = [
            ("/api/jobs", "GET", "Jobs listing"),
            ("/api/user/videos", "GET", "User videos"),
            ("/api/user/clips", "GET", "User clips"),
            ("/api/analytics/overview", "GET", "Analytics overview")
        ]
        
        for endpoint, method, description in endpoints_to_test:
            try:
                if method == "GET":
                    response = requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=10)
                
                self.results["api_endpoints"][endpoint] = {
                    "status": response.status_code,
                    "working": response.status_code in [200, 201, 204]
                }
                
                if response.status_code in [200, 201, 204]:
                    print(f"  ✓ {description} working")
                    self.results["working_features"].append(description)
                else:
                    print(f"  ✗ {description} failed: {response.status_code}")
                    self.results["broken_features"].append(description)
                    
            except Exception as e:
                print(f"  ✗ {description} error: {e}")
                self.results["api_endpoints"][endpoint] = {"error": str(e), "working": False}
                self.results["broken_features"].append(description)

    def test_video_processing(self):
        """Test video processing functionality"""
        print("\n🎥 Testing Video Processing...")
        
        if not self.access_token:
            print("  ⚠ Skipping video processing tests - no access token")
            return

        headers = {"Authorization": f"Bearer {self.access_token}"}

        # Test job creation endpoint
        try:
            job_data = {
                "job_type": "url",
                "title": "Test Video Job",
                "description": "Test video processing",
                "video_url": "https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4"
            }
            response = requests.post(f"{BASE_URL}/api/jobs", json=job_data, headers=headers, timeout=15)
            self.results["video_processing"]["job_creation"] = {
                "status": response.status_code,
                "working": response.status_code in [200, 201]
            }
            
            if response.status_code in [200, 201]:
                print("  ✓ Job creation working")
                job_response = response.json()
                print(f"    - Job ID: {job_response.get('id', 'N/A')}")
                print(f"    - Status: {job_response.get('status', 'N/A')}")
                self.results["working_features"].append("Video job creation")
            else:
                print(f"  ✗ Job creation failed: {response.status_code} - {response.text}")
                self.results["broken_features"].append("Video job creation")
                
        except Exception as e:
            print(f"  ✗ Job creation error: {e}")
            self.results["video_processing"]["job_creation"] = {"error": str(e), "working": False}
            self.results["broken_features"].append("Video job creation")

    def test_error_handling(self):
        """Test error handling and edge cases"""
        print("\n⚠️ Testing Error Handling...")
        
        # Test invalid endpoint
        try:
            response = requests.get(f"{BASE_URL}/api/nonexistent", timeout=5)
            self.results["error_handling"]["invalid_endpoint"] = {
                "status": response.status_code,
                "working": response.status_code == 404
            }
            
            if response.status_code == 404:
                print("  ✓ 404 error handling working")
                self.results["working_features"].append("404 error handling")
            else:
                print(f"  ✗ Invalid endpoint handling unexpected: {response.status_code}")
                
        except Exception as e:
            print(f"  ✗ Error handling test failed: {e}")
            self.results["error_handling"]["invalid_endpoint"] = {"error": str(e), "working": False}

        # Test unauthorized access
        try:
            response = requests.get(f"{BASE_URL}/api/auth/profile", timeout=5)
            self.results["error_handling"]["unauthorized"] = {
                "status": response.status_code,
                "working": response.status_code in [401, 403]
            }
            
            if response.status_code in [401, 403]:
                print(f"  ✓ Unauthorized access handling working ({response.status_code})")
                self.results["working_features"].append("Unauthorized access handling")
            else:
                print(f"  ✗ Unauthorized handling unexpected: {response.status_code}")
                
        except Exception as e:
            print(f"  ✗ Unauthorized test failed: {e}")
            self.results["error_handling"]["unauthorized"] = {"error": str(e), "working": False}

    def analyze_results(self):
        """Analyze test results and generate recommendations"""
        print("\n🔍 Analyzing Results...")
        
        # Check for critical authentication issues
        if not self.results["authentication"].get("registration", {}).get("working", False):
            self.results["critical_issues"].append("User registration not working")
            self.results["recommendations"].append("Fix user registration endpoint and Supabase integration")
        
        if not self.results["authentication"].get("login", {}).get("working", False):
            self.results["critical_issues"].append("User login not working")
            self.results["recommendations"].append("Fix user login endpoint and authentication flow")
        
        # Check profile endpoint specifically
        if not self.results["user_management"].get("profile_get", {}).get("working", False):
            self.results["critical_issues"].append("User profile endpoint not working")
            self.results["recommendations"].append("Fix profile endpoint - likely Supabase user lookup issue")
        
        # Check server connectivity
        if not self.results["backend_connectivity"].get("health", {}).get("working", False):
            if "Timeout" in str(self.results["backend_connectivity"].get("health", {})):
                self.results["recommendations"].append("Backend health endpoint is slow - optimize performance")
            else:
                self.results["recommendations"].append("Check backend server status and configuration")
        
        if not self.results["frontend_connectivity"].get("main", {}).get("working", False):
            self.results["recommendations"].append("Check frontend server status and build")
        
        # Analyze working vs broken ratio
        working_count = len(self.results["working_features"])
        broken_count = len(self.results["broken_features"])
        
        if broken_count > working_count:
            self.results["recommendations"].append("More features are broken than working - prioritize core functionality")
        
        # Check for missing core functionality
        core_features = ["User registration", "User login", "Profile retrieval"]
        missing_core = [f for f in core_features if f not in self.results["working_features"]]
        if missing_core:
            self.results["critical_issues"].append(f"Missing core features: {', '.join(missing_core)}")

    def generate_report(self):
        """Generate comprehensive audit report"""
        print("\n" + "="*80)
        print("📋 COMPREHENSIVE APPLICATION AUDIT REPORT (CORRECTED)")
        print("="*80)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Backend URL: {BASE_URL}")
        print(f"Frontend URL: {FRONTEND_URL}")
        print(f"Test Email: {TEST_EMAIL}")
        
        print("\n🟢 WORKING FEATURES:")
        if self.results["working_features"]:
            for feature in sorted(set(self.results["working_features"])):
                print(f"  ✓ {feature}")
        else:
            print("  ⚠ No working features detected")
        
        print("\n🔴 BROKEN/MISSING FEATURES:")
        if self.results["broken_features"]:
            for feature in sorted(set(self.results["broken_features"])):
                print(f"  ✗ {feature}")
        else:
            print("  ✓ No broken features detected")
        
        print("\n🚨 CRITICAL ISSUES:")
        if self.results["critical_issues"]:
            for issue in self.results["critical_issues"]:
                print(f"  🚨 {issue}")
        else:
            print("  ✓ No critical issues detected")
        
        print("\n💡 RECOMMENDATIONS:")
        if self.results["recommendations"]:
            for rec in self.results["recommendations"]:
                print(f"  💡 {rec}")
        else:
            print("  ✓ No specific recommendations")
        
        # Summary statistics
        working_count = len(set(self.results["working_features"]))
        broken_count = len(set(self.results["broken_features"]))
        critical_count = len(self.results["critical_issues"])
        
        print("\n📊 SUMMARY STATISTICS:")
        print(f"  Working Features: {working_count}")
        print(f"  Broken Features: {broken_count}")
        print(f"  Critical Issues: {critical_count}")
        if (working_count + broken_count) > 0:
            health_percentage = working_count / (working_count + broken_count) * 100
            print(f"  Overall Health: {health_percentage:.1f}%")
        else:
            print("  Overall Health: 0%")
        
        # Detailed analysis
        print("\n🔍 DETAILED ANALYSIS:")
        if self.access_token:
            print("  ✓ Authentication system functional")
            print("  ✓ JWT token generation working")
        else:
            print("  ✗ Authentication system failed")
        
        if self.results["backend_connectivity"].get("docs", {}).get("working"):
            print("  ✓ Backend API documentation accessible")
        
        if self.results["frontend_connectivity"].get("main", {}).get("working"):
            print("  ✓ Frontend application accessible")
        
        # Priority actions
        print("\n🎯 PRIORITY ACTIONS:")
        if critical_count > 0:
            print("  1. 🚨 Fix critical issues immediately:")
            for issue in self.results["critical_issues"][:3]:  # Top 3 critical issues
                print(f"     - {issue}")
            print("  2. 🔧 Restore broken core functionality")
            print("  3. ✅ Test and validate fixes")
        elif broken_count > working_count:
            print("  1. 🔧 Focus on core functionality restoration")
            print("  2. 🚀 Implement missing features")
            print("  3. 🛡️ Improve error handling")
        else:
            print("  1. 🚀 Continue development of missing features")
            print("  2. 🎨 Improve user experience")
            print("  3. 🧪 Add comprehensive testing")
        
        print("\n" + "="*80)
        
        # Save detailed results to file
        with open("corrected_audit_report.json", "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        print("📄 Detailed results saved to corrected_audit_report.json")

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Corrected Comprehensive Application Test...")
        print(f"Backend: {BASE_URL}")
        print(f"Frontend: {FRONTEND_URL}")
        
        self.test_backend_connectivity()
        self.test_frontend_connectivity()
        
        auth_success = self.test_authentication_flow()
        
        if auth_success:
            self.test_user_management()
            self.test_api_endpoints()
            self.test_video_processing()
        
        self.test_error_handling()
        
        self.analyze_results()
        self.generate_report()

if __name__ == "__main__":
    tester = CorrectedComprehensiveTest()
    tester.run_all_tests()