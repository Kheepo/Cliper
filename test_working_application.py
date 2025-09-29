#!/usr/bin/env python3
"""
Focused Application Test
Tests the working application with both frontend and backend running
"""

import requests
import json
import time
from typing import Dict, List, Any

# Configuration
BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3001"

class WorkingApplicationTester:
    def __init__(self):
        self.session = requests.Session()
        self.results = {}
        
    def test_basic_connectivity(self):
        """Test basic server connectivity"""
        print("\n=== TESTING BASIC CONNECTIVITY ===")
        
        # Test backend health
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            backend_status = "WORKING" if response.status_code == 200 else "ISSUES"
            print(f"✓ Backend Health: {response.status_code} - {backend_status}")
            self.results["backend_health"] = {"status": backend_status, "code": response.status_code}
        except Exception as e:
            print(f"✗ Backend Health: ERROR - {e}")
            self.results["backend_health"] = {"status": "ERROR", "error": str(e)}
        
        # Test frontend accessibility
        try:
            response = requests.get(FRONTEND_URL, timeout=10)
            frontend_status = "WORKING" if response.status_code == 200 else "ISSUES"
            print(f"✓ Frontend Access: {response.status_code} - {frontend_status}")
            self.results["frontend_access"] = {"status": frontend_status, "code": response.status_code}
            
            # Check if it's a React app
            if response.status_code == 200:
                content = response.text
                has_react_root = "root" in content
                has_vite = "vite" in content.lower()
                print(f"✓ React App Structure: Root element = {has_react_root}, Vite = {has_vite}")
                self.results["frontend_structure"] = {"react_root": has_react_root, "vite": has_vite}
                
        except Exception as e:
            print(f"✗ Frontend Access: ERROR - {e}")
            self.results["frontend_access"] = {"status": "ERROR", "error": str(e)}
    
    def test_api_availability(self):
        """Test key API endpoints availability"""
        print("\n=== TESTING API AVAILABILITY ===")
        
        key_endpoints = {
            "Health Check": "/health",
            "Detailed Health": "/health/detailed", 
            "User Settings": "/api/user/settings",
            "Video Upload": "/api/videos/upload",
            "Jobs List": "/api/jobs",
            "Results List": "/api/results",
            "Analysis Start": "/api/analysis/start",
            "Clips Generate": "/api/clips/generate"
        }
        
        available_endpoints = 0
        total_endpoints = len(key_endpoints)
        
        for name, endpoint in key_endpoints.items():
            try:
                if endpoint in ["/api/analysis/start", "/api/clips/generate"]:
                    response = self.session.post(f"{BASE_URL}{endpoint}", json={})
                else:
                    response = self.session.get(f"{BASE_URL}{endpoint}")
                
                if response.status_code != 404:
                    available_endpoints += 1
                    status = "AVAILABLE"
                    if response.status_code == 401:
                        status += " (Auth Required)"
                    elif response.status_code == 405:
                        status += " (Method Check)"
                else:
                    status = "NOT_FOUND"
                
                icon = "✓" if response.status_code != 404 else "✗"
                print(f"{icon} {name}: {response.status_code} - {status}")
                
            except Exception as e:
                print(f"✗ {name}: ERROR - {e}")
        
        availability_rate = (available_endpoints / total_endpoints) * 100
        print(f"\n📊 API Availability: {available_endpoints}/{total_endpoints} ({availability_rate:.1f}%)")
        self.results["api_availability"] = {
            "available": available_endpoints,
            "total": total_endpoints,
            "rate": availability_rate
        }
    
    def test_authentication_endpoints(self):
        """Test authentication system"""
        print("\n=== TESTING AUTHENTICATION SYSTEM ===")
        
        auth_endpoints = {
            "Register": "/auth/register",
            "Login": "/auth/login", 
            "Google OAuth": "/auth/google",
            "OAuth Callback": "/auth/google/callback",
            "Logout": "/auth/logout"
        }
        
        auth_available = 0
        total_auth = len(auth_endpoints)
        
        for name, endpoint in auth_endpoints.items():
            try:
                if endpoint == "/auth/register":
                    response = requests.post(f"{BASE_URL}{endpoint}", json={
                        "email": "test@example.com",
                        "password": "testpass"
                    })
                elif endpoint == "/auth/login":
                    response = requests.post(f"{BASE_URL}{endpoint}", json={
                        "email": "test@example.com", 
                        "password": "testpass"
                    })
                else:
                    response = requests.get(f"{BASE_URL}{endpoint}")
                
                if response.status_code != 404:
                    auth_available += 1
                    status = "AVAILABLE"
                else:
                    status = "NOT_IMPLEMENTED"
                
                icon = "✓" if response.status_code != 404 else "✗"
                print(f"{icon} {name}: {response.status_code} - {status}")
                
            except Exception as e:
                print(f"✗ {name}: ERROR - {e}")
        
        auth_rate = (auth_available / total_auth) * 100
        print(f"\n📊 Authentication: {auth_available}/{total_auth} ({auth_rate:.1f}%)")
        self.results["authentication"] = {
            "available": auth_available,
            "total": total_auth,
            "rate": auth_rate
        }
    
    def test_database_connectivity(self):
        """Test database connectivity"""
        print("\n=== TESTING DATABASE CONNECTIVITY ===")
        
        try:
            response = requests.get(f"{BASE_URL}/health/detailed")
            if response.status_code == 200:
                data = response.json()
                db_info = data.get("database", {})
                db_status = db_info.get("status", "unknown")
                
                if db_status == "healthy":
                    print(f"✓ Database Status: {db_status}")
                    print(f"✓ Connection Pool: {db_info.get('connection_pool', 'N/A')}")
                    self.results["database"] = {"status": "HEALTHY", "details": db_info}
                else:
                    print(f"⚠️  Database Status: {db_status}")
                    self.results["database"] = {"status": "ISSUES", "details": db_info}
            else:
                print(f"✗ Database Check: HTTP {response.status_code}")
                self.results["database"] = {"status": "ERROR", "code": response.status_code}
        except Exception as e:
            print(f"✗ Database Check: ERROR - {e}")
            self.results["database"] = {"status": "ERROR", "error": str(e)}
    
    def test_file_upload_capability(self):
        """Test file upload functionality"""
        print("\n=== TESTING FILE UPLOAD CAPABILITY ===")
        
        try:
            # Test with a small mock file
            test_content = b"Mock video file content for testing"
            files = {"file": ("test_video.mp4", test_content, "video/mp4")}
            
            response = self.session.post(f"{BASE_URL}/api/videos/upload", files=files)
            
            if response.status_code == 401:
                print("✓ Upload Endpoint: Available (Authentication Required)")
                self.results["file_upload"] = {"status": "AVAILABLE", "requires_auth": True}
            elif response.status_code in [200, 201]:
                print("✓ Upload Endpoint: Working (No Auth Required)")
                self.results["file_upload"] = {"status": "WORKING", "requires_auth": False}
            elif response.status_code == 404:
                print("✗ Upload Endpoint: Not Found")
                self.results["file_upload"] = {"status": "NOT_FOUND"}
            else:
                print(f"⚠️  Upload Endpoint: Status {response.status_code}")
                self.results["file_upload"] = {"status": "ISSUES", "code": response.status_code}
                
        except Exception as e:
            print(f"✗ Upload Test: ERROR - {e}")
            self.results["file_upload"] = {"status": "ERROR", "error": str(e)}
    
    def generate_summary(self):
        """Generate test summary"""
        print("\n" + "="*60)
        print("APPLICATION STATUS SUMMARY")
        print("="*60)
        
        # Overall status
        backend_ok = self.results.get("backend_health", {}).get("status") == "WORKING"
        frontend_ok = self.results.get("frontend_access", {}).get("status") == "WORKING"
        
        if backend_ok and frontend_ok:
            print("🟢 OVERALL STATUS: APPLICATION IS RUNNING")
        elif backend_ok or frontend_ok:
            print("🟡 OVERALL STATUS: PARTIAL FUNCTIONALITY")
        else:
            print("🔴 OVERALL STATUS: MAJOR ISSUES")
        
        # Component status
        print(f"\nCOMPONENT STATUS:")
        print(f"  Backend Server: {'✓ Running' if backend_ok else '✗ Issues'}")
        print(f"  Frontend App: {'✓ Running' if frontend_ok else '✗ Issues'}")
        
        # API availability
        api_info = self.results.get("api_availability", {})
        if api_info:
            print(f"  API Endpoints: {api_info.get('available', 0)}/{api_info.get('total', 0)} available ({api_info.get('rate', 0):.1f}%)")
        
        # Authentication
        auth_info = self.results.get("authentication", {})
        if auth_info:
            print(f"  Authentication: {auth_info.get('available', 0)}/{auth_info.get('total', 0)} endpoints ({auth_info.get('rate', 0):.1f}%)")
        
        # Database
        db_status = self.results.get("database", {}).get("status", "UNKNOWN")
        print(f"  Database: {db_status}")
        
        # File upload
        upload_status = self.results.get("file_upload", {}).get("status", "UNKNOWN")
        print(f"  File Upload: {upload_status}")
        
        # Key findings
        print(f"\nKEY FINDINGS:")
        findings = []
        
        if backend_ok and frontend_ok:
            findings.append("✅ Both frontend and backend servers are running successfully")
        
        if api_info.get("rate", 0) > 70:
            findings.append("✅ Most API endpoints are available and responding")
        
        if auth_info.get("rate", 0) == 0:
            findings.append("⚠️  Authentication system is not implemented")
        
        if db_status == "HEALTHY":
            findings.append("✅ Database connectivity is working")
        elif db_status in ["ISSUES", "ERROR"]:
            findings.append("⚠️  Database connectivity has issues")
        
        if upload_status in ["AVAILABLE", "WORKING"]:
            findings.append("✅ File upload functionality is available")
        
        for finding in findings:
            print(f"  {finding}")
        
        # Next steps
        print(f"\nRECOMMENDED NEXT STEPS:")
        next_steps = []
        
        if not backend_ok:
            next_steps.append("🔧 Fix backend server issues")
        
        if not frontend_ok:
            next_steps.append("🔧 Fix frontend accessibility issues")
        
        if auth_info.get("rate", 0) == 0:
            next_steps.append("🔧 Implement authentication endpoints")
        
        if db_status != "HEALTHY":
            next_steps.append("🔧 Check database configuration and connectivity")
        
        if api_info.get("rate", 0) < 70:
            next_steps.append("🔧 Implement missing API endpoints")
        
        if not next_steps:
            next_steps.append("✅ Application is ready for user testing")
            next_steps.append("🧪 Perform end-to-end user workflow testing")
            next_steps.append("🔍 Test authentication flow with real users")
        
        for step in next_steps:
            print(f"  {step}")
        
        return self.results
    
    def run_focused_test(self):
        """Run focused application test"""
        print("Starting Focused Application Test...")
        print(f"Frontend: {FRONTEND_URL}")
        print(f"Backend: {BASE_URL}")
        
        self.test_basic_connectivity()
        self.test_api_availability()
        self.test_authentication_endpoints()
        self.test_database_connectivity()
        self.test_file_upload_capability()
        
        return self.generate_summary()

def main():
    tester = WorkingApplicationTester()
    results = tester.run_focused_test()
    
    # Save results
    with open("working_app_test.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDetailed results saved to: working_app_test.json")

if __name__ == "__main__":
    main()