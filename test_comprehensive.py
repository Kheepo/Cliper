#!/usr/bin/env python3
"""
Comprehensive End-to-End Application Test
Tests all critical functionality and generates audit report
"""

import requests
import json
import time
import os
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:5173"
TEST_EMAIL = f"test_{int(time.time())}@example.com"
TEST_PASSWORD = "TestPassword123!"

class ComprehensiveTest:
    def __init__(self):
        self.results = {
            "backend_connectivity": {},
            "authentication": {},
            "user_management": {},
            "video_processing": {},
            "database_operations": {},
            "frontend_connectivity": {},
            "error_handling": {},
            "critical_issues": [],
            "working_features": [],
            "broken_features": [],
            "recommendations": []
        }
        self.access_token = None
        self.user_id = None

    def test_backend_connectivity(self):
        """Test basic backend connectivity"""
        print("\n🔗 Testing Backend Connectivity...")
        
        try:
            # Test health endpoint
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            self.results["backend_connectivity"]["health"] = {
                "status": response.status_code,
                "working": response.status_code == 200
            }
            if response.status_code == 200:
                print("  ✓ Health endpoint working")
                self.results["working_features"].append("Backend health endpoint")
            else:
                print(f"  ✗ Health endpoint failed: {response.status_code}")
                self.results["broken_features"].append("Backend health endpoint")
        except Exception as e:
            print(f"  ✗ Backend connectivity failed: {e}")
            self.results["backend_connectivity"]["health"] = {"error": str(e), "working": False}
            self.results["critical_issues"].append("Backend server not accessible")
            self.results["broken_features"].append("Backend connectivity")

        # Test API documentation
        try:
            response = requests.get(f"{BASE_URL}/docs", timeout=5)
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
        """Test frontend connectivity"""
        print("\n🌐 Testing Frontend Connectivity...")
        
        try:
            response = requests.get(FRONTEND_URL, timeout=5)
            self.results["frontend_connectivity"]["main"] = {
                "status": response.status_code,
                "working": response.status_code == 200
            }
            if response.status_code == 200:
                print("  ✓ Frontend server accessible")
                self.results["working_features"].append("Frontend server")
            else:
                print(f"  ✗ Frontend server failed: {response.status_code}")
                self.results["broken_features"].append("Frontend server")
        except Exception as e:
            print(f"  ✗ Frontend connectivity failed: {e}")
            self.results["frontend_connectivity"]["main"] = {"error": str(e), "working": False}
            self.results["critical_issues"].append("Frontend server not accessible")
            self.results["broken_features"].append("Frontend connectivity")

    def test_authentication_flow(self):
        """Test complete authentication flow"""
        print("\n🔐 Testing Authentication Flow...")
        
        # Test registration
        try:
            register_data = {
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
                "display_name": "Test User"
            }
            response = requests.post(f"{BASE_URL}/api/auth/register", json=register_data, timeout=10)
            self.results["authentication"]["registration"] = {
                "status": response.status_code,
                "working": response.status_code == 200
            }
            
            if response.status_code == 200:
                print("  ✓ User registration working")
                self.results["working_features"].append("User registration")
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
            response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data, timeout=10)
            self.results["authentication"]["login"] = {
                "status": response.status_code,
                "working": response.status_code == 200
            }
            
            if response.status_code == 200:
                print("  ✓ User login working")
                data = response.json()
                self.access_token = data.get("access_token")
                self.user_id = data.get("user", {}).get("id")
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
            return

        headers = {"Authorization": f"Bearer {self.access_token}"}

        # Test profile retrieval
        try:
            response = requests.get(f"{BASE_URL}/api/auth/profile", headers=headers, timeout=5)
            self.results["user_management"]["profile_get"] = {
                "status": response.status_code,
                "working": response.status_code == 200
            }
            
            if response.status_code == 200:
                print("  ✓ Profile retrieval working")
                self.results["working_features"].append("Profile retrieval")
            else:
                print(f"  ✗ Profile retrieval failed: {response.status_code}")
                self.results["broken_features"].append("Profile retrieval")
                
        except Exception as e:
            print(f"  ✗ Profile retrieval error: {e}")
            self.results["user_management"]["profile_get"] = {"error": str(e), "working": False}
            self.results["broken_features"].append("Profile retrieval")

        # Test profile update
        try:
            update_data = {"display_name": "Updated Test User"}
            response = requests.put(f"{BASE_URL}/api/auth/profile", json=update_data, headers=headers, timeout=5)
            self.results["user_management"]["profile_update"] = {
                "status": response.status_code,
                "working": response.status_code == 200
            }
            
            if response.status_code == 200:
                print("  ✓ Profile update working")
                self.results["working_features"].append("Profile update")
            else:
                print(f"  ✗ Profile update failed: {response.status_code}")
                self.results["broken_features"].append("Profile update")
                
        except Exception as e:
            print(f"  ✗ Profile update error: {e}")
            self.results["user_management"]["profile_update"] = {"error": str(e), "working": False}
            self.results["broken_features"].append("Profile update")

    def test_video_processing(self):
        """Test video upload and processing endpoints"""
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
                "video_url": "https://example.com/test.mp4"
            }
            response = requests.post(f"{BASE_URL}/api/jobs", json=job_data, headers=headers, timeout=10)
            self.results["video_processing"]["job_creation"] = {
                "status": response.status_code,
                "working": response.status_code in [200, 201]
            }
            
            if response.status_code in [200, 201]:
                print("  ✓ Job creation working")
                self.results["working_features"].append("Video job creation")
            else:
                print(f"  ✗ Job creation failed: {response.status_code}")
                self.results["broken_features"].append("Video job creation")
                
        except Exception as e:
            print(f"  ✗ Job creation error: {e}")
            self.results["video_processing"]["job_creation"] = {"error": str(e), "working": False}
            self.results["broken_features"].append("Video job creation")

        # Test jobs listing
        try:
            response = requests.get(f"{BASE_URL}/api/jobs", headers=headers, timeout=5)
            self.results["video_processing"]["jobs_list"] = {
                "status": response.status_code,
                "working": response.status_code == 200
            }
            
            if response.status_code == 200:
                print("  ✓ Jobs listing working")
                self.results["working_features"].append("Jobs listing")
            else:
                print(f"  ✗ Jobs listing failed: {response.status_code}")
                self.results["broken_features"].append("Jobs listing")
                
        except Exception as e:
            print(f"  ✗ Jobs listing error: {e}")
            self.results["video_processing"]["jobs_list"] = {"error": str(e), "working": False}
            self.results["broken_features"].append("Jobs listing")

    def test_database_operations(self):
        """Test database connectivity and operations"""
        print("\n🗄️ Testing Database Operations...")
        
        if not self.access_token:
            print("  ⚠ Skipping database tests - no access token")
            return

        headers = {"Authorization": f"Bearer {self.access_token}"}

        # Test user settings (database read/write)
        try:
            response = requests.get(f"{BASE_URL}/api/user/settings", headers=headers, timeout=5)
            self.results["database_operations"]["settings_read"] = {
                "status": response.status_code,
                "working": response.status_code == 200
            }
            
            if response.status_code == 200:
                print("  ✓ Database read operations working")
                self.results["working_features"].append("Database read operations")
            else:
                print(f"  ✗ Database read failed: {response.status_code}")
                self.results["broken_features"].append("Database read operations")
                
        except Exception as e:
            print(f"  ✗ Database read error: {e}")
            self.results["database_operations"]["settings_read"] = {"error": str(e), "working": False}
            self.results["broken_features"].append("Database read operations")

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
                print(f"  ✗ Invalid endpoint handling failed: {response.status_code}")
                
        except Exception as e:
            print(f"  ✗ Error handling test failed: {e}")
            self.results["error_handling"]["invalid_endpoint"] = {"error": str(e), "working": False}

        # Test unauthorized access
        try:
            response = requests.get(f"{BASE_URL}/api/auth/profile", timeout=5)
            self.results["error_handling"]["unauthorized"] = {
                "status": response.status_code,
                "working": response.status_code == 401
            }
            
            if response.status_code == 401:
                print("  ✓ Unauthorized access handling working")
                self.results["working_features"].append("Unauthorized access handling")
            else:
                print(f"  ✗ Unauthorized handling failed: {response.status_code}")
                
        except Exception as e:
            print(f"  ✗ Unauthorized test failed: {e}")
            self.results["error_handling"]["unauthorized"] = {"error": str(e), "working": False}

    def analyze_results(self):
        """Analyze test results and generate recommendations"""
        print("\n🔍 Analyzing Results...")
        
        # Check for critical issues
        if not self.results["backend_connectivity"].get("health", {}).get("working", False):
            self.results["critical_issues"].append("Backend server not responding")
            self.results["recommendations"].append("Check backend server status and configuration")
        
        if not self.results["frontend_connectivity"].get("main", {}).get("working", False):
            self.results["critical_issues"].append("Frontend server not responding")
            self.results["recommendations"].append("Check frontend server status and build")
        
        if not self.results["authentication"].get("registration", {}).get("working", False):
            self.results["critical_issues"].append("User registration not working")
            self.results["recommendations"].append("Fix user registration endpoint and Supabase integration")
        
        if not self.results["authentication"].get("login", {}).get("working", False):
            self.results["critical_issues"].append("User login not working")
            self.results["recommendations"].append("Fix user login endpoint and authentication flow")
        
        # Check for missing features
        if len(self.results["broken_features"]) > len(self.results["working_features"]):
            self.results["recommendations"].append("More features are broken than working - prioritize core functionality")
        
        # Database connectivity
        if not any("Database" in feature for feature in self.results["working_features"]):
            self.results["critical_issues"].append("Database operations not working")
            self.results["recommendations"].append("Check database connectivity and Supabase configuration")

    def generate_report(self):
        """Generate comprehensive audit report"""
        print("\n" + "="*80)
        print("📋 COMPREHENSIVE APPLICATION AUDIT REPORT")
        print("="*80)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Test Email: {TEST_EMAIL}")
        
        print("\n🟢 WORKING FEATURES:")
        if self.results["working_features"]:
            for feature in self.results["working_features"]:
                print(f"  ✓ {feature}")
        else:
            print("  ⚠ No working features detected")
        
        print("\n🔴 BROKEN/MISSING FEATURES:")
        if self.results["broken_features"]:
            for feature in self.results["broken_features"]:
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
        working_count = len(self.results["working_features"])
        broken_count = len(self.results["broken_features"])
        critical_count = len(self.results["critical_issues"])
        
        print("\n📊 SUMMARY STATISTICS:")
        print(f"  Working Features: {working_count}")
        print(f"  Broken Features: {broken_count}")
        print(f"  Critical Issues: {critical_count}")
        print(f"  Overall Health: {working_count/(working_count+broken_count)*100:.1f}%" if (working_count+broken_count) > 0 else "  Overall Health: 0%")
        
        # Priority actions
        print("\n🎯 PRIORITY ACTIONS:")
        if critical_count > 0:
            print("  1. Fix critical issues immediately")
            print("  2. Restore broken core functionality")
            print("  3. Test and validate fixes")
        elif broken_count > working_count:
            print("  1. Focus on core functionality restoration")
            print("  2. Implement missing features")
            print("  3. Improve error handling")
        else:
            print("  1. Continue development of missing features")
            print("  2. Improve user experience")
            print("  3. Add comprehensive testing")
        
        print("\n" + "="*80)
        
        # Save detailed results to file
        with open("audit_report.json", "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        print("📄 Detailed results saved to audit_report.json")

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Comprehensive Application Test...")
        
        self.test_backend_connectivity()
        self.test_frontend_connectivity()
        
        auth_success = self.test_authentication_flow()
        
        self.test_user_management()
        self.test_video_processing()
        self.test_database_operations()
        self.test_error_handling()
        
        self.analyze_results()
        self.generate_report()

if __name__ == "__main__":
    tester = ComprehensiveTest()
    tester.run_all_tests()