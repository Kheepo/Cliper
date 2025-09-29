#!/usr/bin/env python3
"""
Comprehensive Application Audit
Tests all critical functionalities to identify issues preventing normal usage
"""

import requests
import json
import time
from typing import Dict, List, Any

# Configuration
BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3001"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpassword123"

class ApplicationAuditor:
    def __init__(self):
        self.session = requests.Session()
        self.results = {
            "server_connectivity": {},
            "authentication": {},
            "api_endpoints": {},
            "file_operations": {},
            "database_operations": {},
            "frontend_connectivity": {},
            "integration_tests": {}
        }
        self.auth_token = None
        
    def test_server_connectivity(self):
        """Test basic server connectivity"""
        print("\n=== TESTING SERVER CONNECTIVITY ===")
        
        tests = {
            "backend_health": f"{BASE_URL}/health",
            "backend_detailed_health": f"{BASE_URL}/health/detailed",
            "backend_readiness": f"{BASE_URL}/health/readiness",
            "frontend_accessibility": FRONTEND_URL
        }
        
        for test_name, url in tests.items():
            try:
                response = requests.get(url, timeout=5)
                self.results["server_connectivity"][test_name] = {
                    "status": "PASS" if response.status_code == 200 else "FAIL",
                    "status_code": response.status_code,
                    "response_time": response.elapsed.total_seconds()
                }
                print(f"✓ {test_name}: {response.status_code} ({response.elapsed.total_seconds():.2f}s)")
            except Exception as e:
                self.results["server_connectivity"][test_name] = {
                    "status": "ERROR",
                    "error": str(e)
                }
                print(f"✗ {test_name}: ERROR - {e}")
    
    def test_authentication_system(self):
        """Test authentication endpoints and flows"""
        print("\n=== TESTING AUTHENTICATION SYSTEM ===")
        
        # Test registration endpoint
        try:
            register_data = {
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
                "full_name": "Test User"
            }
            response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
            self.results["authentication"]["registration"] = {
                "status": "AVAILABLE" if response.status_code in [200, 201, 400, 409] else "NOT_FOUND",
                "status_code": response.status_code
            }
            print(f"✓ Registration endpoint: {response.status_code}")
        except Exception as e:
            self.results["authentication"]["registration"] = {"status": "ERROR", "error": str(e)}
            print(f"✗ Registration endpoint: ERROR - {e}")
        
        # Test login endpoint
        try:
            login_data = {
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            }
            response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
            self.results["authentication"]["login"] = {
                "status": "AVAILABLE" if response.status_code in [200, 401, 422] else "NOT_FOUND",
                "status_code": response.status_code
            }
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "access_token" in data:
                        self.auth_token = data["access_token"]
                        self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
                        print(f"✓ Login successful - Token acquired")
                except:
                    pass
            
            print(f"✓ Login endpoint: {response.status_code}")
        except Exception as e:
            self.results["authentication"]["login"] = {"status": "ERROR", "error": str(e)}
            print(f"✗ Login endpoint: ERROR - {e}")
        
        # Test Google OAuth endpoints
        oauth_endpoints = [
            "/auth/google",
            "/auth/google/callback",
            "/auth/logout"
        ]
        
        for endpoint in oauth_endpoints:
            try:
                response = requests.get(f"{BASE_URL}{endpoint}")
                self.results["authentication"][f"oauth_{endpoint.split('/')[-1]}"] = {
                    "status": "AVAILABLE" if response.status_code != 404 else "NOT_FOUND",
                    "status_code": response.status_code
                }
                print(f"✓ OAuth {endpoint}: {response.status_code}")
            except Exception as e:
                self.results["authentication"][f"oauth_{endpoint.split('/')[-1]}"] = {"status": "ERROR", "error": str(e)}
                print(f"✗ OAuth {endpoint}: ERROR - {e}")
    
    def test_api_endpoints(self):
        """Test all critical API endpoints"""
        print("\n=== TESTING API ENDPOINTS ===")
        
        endpoints = {
            # User endpoints
            "user_profile": ("/api/user/profile", "GET"),
            "user_settings": ("/api/user/settings", "GET"),
            
            # Video endpoints
            "video_upload": ("/api/videos/upload", "POST"),
            "video_list": ("/api/videos", "GET"),
            
            # Analysis endpoints
            "analysis_start": ("/api/analysis/start", "POST"),
            "analysis_status": ("/api/analysis/status", "GET"),
            "analysis_results": ("/api/analysis/results", "GET"),
            
            # Clips endpoints
            "clips_generate": ("/api/clips/generate", "POST"),
            "clips_list": ("/api/clips", "GET"),
            
            # Jobs and results
            "jobs_list": ("/api/jobs", "GET"),
            "results_list": ("/api/results", "GET"),
            
            # Analytics
            "analytics_overview": ("/api/analytics/overview", "GET"),
            "analytics_performance": ("/api/analytics/performance", "GET")
        }
        
        for endpoint_name, (path, method) in endpoints.items():
            try:
                if method == "GET":
                    response = self.session.get(f"{BASE_URL}{path}")
                elif method == "POST":
                    response = self.session.post(f"{BASE_URL}{path}", json={})
                
                self.results["api_endpoints"][endpoint_name] = {
                    "status": "AVAILABLE" if response.status_code != 404 else "NOT_FOUND",
                    "status_code": response.status_code,
                    "requires_auth": response.status_code == 401
                }
                
                status_icon = "✓" if response.status_code != 404 else "✗"
                auth_note = " (requires auth)" if response.status_code == 401 else ""
                print(f"{status_icon} {endpoint_name}: {response.status_code}{auth_note}")
                
            except Exception as e:
                self.results["api_endpoints"][endpoint_name] = {"status": "ERROR", "error": str(e)}
                print(f"✗ {endpoint_name}: ERROR - {e}")
    
    def test_file_operations(self):
        """Test file upload and storage operations"""
        print("\n=== TESTING FILE OPERATIONS ===")
        
        # Test file upload endpoint
        try:
            # Create a small test file
            test_content = b"This is a test video file content"
            files = {"file": ("test_video.mp4", test_content, "video/mp4")}
            
            response = self.session.post(f"{BASE_URL}/api/videos/upload", files=files)
            self.results["file_operations"]["video_upload"] = {
                "status": "AVAILABLE" if response.status_code != 404 else "NOT_FOUND",
                "status_code": response.status_code,
                "requires_auth": response.status_code == 401
            }
            
            status_icon = "✓" if response.status_code != 404 else "✗"
            auth_note = " (requires auth)" if response.status_code == 401 else ""
            print(f"{status_icon} Video upload: {response.status_code}{auth_note}")
            
        except Exception as e:
            self.results["file_operations"]["video_upload"] = {"status": "ERROR", "error": str(e)}
            print(f"✗ Video upload: ERROR - {e}")
        
        # Test storage endpoints
        storage_endpoints = [
            "/api/storage/list",
            "/api/storage/upload",
            "/api/storage/download"
        ]
        
        for endpoint in storage_endpoints:
            try:
                response = self.session.get(f"{BASE_URL}{endpoint}")
                endpoint_name = f"storage_{endpoint.split('/')[-1]}"
                self.results["file_operations"][endpoint_name] = {
                    "status": "AVAILABLE" if response.status_code != 404 else "NOT_FOUND",
                    "status_code": response.status_code
                }
                
                status_icon = "✓" if response.status_code != 404 else "✗"
                print(f"{status_icon} {endpoint_name}: {response.status_code}")
                
            except Exception as e:
                self.results["file_operations"][endpoint_name] = {"status": "ERROR", "error": str(e)}
                print(f"✗ {endpoint_name}: ERROR - {e}")
    
    def test_database_operations(self):
        """Test database connectivity and operations"""
        print("\n=== TESTING DATABASE OPERATIONS ===")
        
        # Test database health
        try:
            response = requests.get(f"{BASE_URL}/health/detailed")
            if response.status_code == 200:
                data = response.json()
                db_status = data.get("database", {}).get("status", "unknown")
                self.results["database_operations"]["connectivity"] = {
                    "status": "PASS" if db_status == "healthy" else "FAIL",
                    "details": data.get("database", {})
                }
                print(f"✓ Database connectivity: {db_status}")
            else:
                self.results["database_operations"]["connectivity"] = {
                    "status": "FAIL",
                    "status_code": response.status_code
                }
                print(f"✗ Database connectivity: HTTP {response.status_code}")
        except Exception as e:
            self.results["database_operations"]["connectivity"] = {"status": "ERROR", "error": str(e)}
            print(f"✗ Database connectivity: ERROR - {e}")
        
        # Test table access
        table_endpoints = [
            "/api/users",
            "/api/jobs",
            "/api/results"
        ]
        
        for endpoint in table_endpoints:
            try:
                response = self.session.get(f"{BASE_URL}{endpoint}")
                table_name = endpoint.split('/')[-1]
                self.results["database_operations"][f"table_{table_name}"] = {
                    "status": "ACCESSIBLE" if response.status_code in [200, 401] else "NOT_FOUND",
                    "status_code": response.status_code
                }
                
                status_icon = "✓" if response.status_code in [200, 401] else "✗"
                print(f"{status_icon} Table {table_name}: {response.status_code}")
                
            except Exception as e:
                self.results["database_operations"][f"table_{table_name}"] = {"status": "ERROR", "error": str(e)}
                print(f"✗ Table {table_name}: ERROR - {e}")
    
    def test_frontend_connectivity(self):
        """Test frontend accessibility and basic functionality"""
        print("\n=== TESTING FRONTEND CONNECTIVITY ===")
        
        try:
            response = requests.get(FRONTEND_URL, timeout=10)
            self.results["frontend_connectivity"]["accessibility"] = {
                "status": "PASS" if response.status_code == 200 else "FAIL",
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds()
            }
            
            if response.status_code == 200:
                # Check if it's a React app
                content = response.text
                has_react = "react" in content.lower() or "root" in content
                self.results["frontend_connectivity"]["react_app"] = {
                    "status": "DETECTED" if has_react else "NOT_DETECTED",
                    "has_root_element": "root" in content
                }
                print(f"✓ Frontend accessible: {response.status_code} ({response.elapsed.total_seconds():.2f}s)")
                print(f"✓ React app detected: {has_react}")
            else:
                print(f"✗ Frontend not accessible: {response.status_code}")
                
        except Exception as e:
            self.results["frontend_connectivity"]["accessibility"] = {"status": "ERROR", "error": str(e)}
            print(f"✗ Frontend accessibility: ERROR - {e}")
    
    def generate_report(self):
        """Generate comprehensive audit report"""
        print("\n" + "="*60)
        print("COMPREHENSIVE APPLICATION AUDIT REPORT")
        print("="*60)
        
        # Summary statistics
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        error_tests = 0
        
        for category, tests in self.results.items():
            for test_name, result in tests.items():
                total_tests += 1
                status = result.get("status", "UNKNOWN")
                if status in ["PASS", "AVAILABLE", "ACCESSIBLE", "DETECTED"]:
                    passed_tests += 1
                elif status in ["FAIL", "NOT_FOUND", "NOT_DETECTED"]:
                    failed_tests += 1
                else:
                    error_tests += 1
        
        print(f"\nOVERALL SUMMARY:")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ({passed_tests/total_tests*100:.1f}%)")
        print(f"Failed: {failed_tests} ({failed_tests/total_tests*100:.1f}%)")
        print(f"Errors: {error_tests} ({error_tests/total_tests*100:.1f}%)")
        
        # Detailed results by category
        for category, tests in self.results.items():
            print(f"\n{category.upper().replace('_', ' ')}:")
            for test_name, result in tests.items():
                status = result.get("status", "UNKNOWN")
                status_code = result.get("status_code", "")
                error = result.get("error", "")
                
                if status in ["PASS", "AVAILABLE", "ACCESSIBLE", "DETECTED"]:
                    icon = "✓"
                elif status in ["FAIL", "NOT_FOUND", "NOT_DETECTED"]:
                    icon = "✗"
                else:
                    icon = "!"
                
                status_info = f" ({status_code})" if status_code else ""
                error_info = f" - {error}" if error else ""
                print(f"  {icon} {test_name}: {status}{status_info}{error_info}")
        
        # Critical issues identification
        print(f"\nCRITICAL ISSUES IDENTIFIED:")
        critical_issues = []
        
        # Check server connectivity
        if self.results["server_connectivity"].get("backend_health", {}).get("status") != "PASS":
            critical_issues.append("Backend server health check failing")
        
        if self.results["frontend_connectivity"].get("accessibility", {}).get("status") != "PASS":
            critical_issues.append("Frontend not accessible")
        
        # Check authentication
        auth_available = any(
            result.get("status") == "AVAILABLE" 
            for result in self.results["authentication"].values()
        )
        if not auth_available:
            critical_issues.append("No authentication endpoints available")
        
        # Check database
        if self.results["database_operations"].get("connectivity", {}).get("status") != "PASS":
            critical_issues.append("Database connectivity issues")
        
        # Check core API endpoints
        core_endpoints = ["video_upload", "analysis_start", "clips_generate"]
        missing_core = [
            endpoint for endpoint in core_endpoints 
            if self.results["api_endpoints"].get(endpoint, {}).get("status") == "NOT_FOUND"
        ]
        if missing_core:
            critical_issues.append(f"Missing core endpoints: {', '.join(missing_core)}")
        
        if critical_issues:
            for issue in critical_issues:
                print(f"  ⚠️  {issue}")
        else:
            print("  ✓ No critical issues detected")
        
        # Recommendations
        print(f"\nRECOMMENDATIONS:")
        recommendations = []
        
        if self.auth_token is None:
            recommendations.append("Implement proper authentication flow for testing")
        
        if any(result.get("status") == "NOT_FOUND" for result in self.results["api_endpoints"].values()):
            recommendations.append("Review and implement missing API endpoints")
        
        if self.results["database_operations"].get("connectivity", {}).get("status") != "PASS":
            recommendations.append("Check database configuration and connectivity")
        
        auth_endpoints = len([r for r in self.results["authentication"].values() if r.get("status") == "AVAILABLE"])
        if auth_endpoints < 3:
            recommendations.append("Complete authentication system implementation")
        
        if recommendations:
            for rec in recommendations:
                print(f"  📋 {rec}")
        else:
            print("  ✓ Application appears to be functioning well")
        
        return {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "errors": error_tests,
                "pass_rate": passed_tests/total_tests*100
            },
            "critical_issues": critical_issues,
            "recommendations": recommendations,
            "detailed_results": self.results
        }
    
    def run_full_audit(self):
        """Run complete application audit"""
        print("Starting Comprehensive Application Audit...")
        print(f"Frontend URL: {FRONTEND_URL}")
        print(f"Backend URL: {BASE_URL}")
        
        self.test_server_connectivity()
        self.test_authentication_system()
        self.test_api_endpoints()
        self.test_file_operations()
        self.test_database_operations()
        self.test_frontend_connectivity()
        
        return self.generate_report()

def main():
    auditor = ApplicationAuditor()
    report = auditor.run_full_audit()
    
    # Save detailed report
    with open("audit_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nDetailed report saved to: audit_report.json")
    print(f"\nAudit completed with {report['summary']['pass_rate']:.1f}% pass rate")

if __name__ == "__main__":
    main()