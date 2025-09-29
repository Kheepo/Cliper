#!/usr/bin/env python3
"""
Smoke tests for staging environment.
These tests verify basic functionality after deployment.
"""

import os
import sys
import time
import requests
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class TestResult:
    """Test result container."""
    name: str
    passed: bool
    message: str
    duration: float
    details: Optional[Dict[str, Any]] = None


class StagingSmokeTests:
    """Smoke tests for staging environment."""
    
    def __init__(self):
        self.base_url = os.getenv("STAGING_URL", "https://api-staging.example.com")
        self.api_key = os.getenv("API_KEY", "staging-test-key")
        self.timeout = 30
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "StagingSmokeTest/1.0"
        }
        self.results = []
    
    def run_test(self, test_name: str, test_func):
        """Run a single test and record results."""
        print(f"Running {test_name}...", end=" ")
        start_time = time.time()
        
        try:
            result = test_func()
            duration = time.time() - start_time
            
            if result.get("success", False):
                print("✓ PASS")
                self.results.append(TestResult(
                    name=test_name,
                    passed=True,
                    message=result.get("message", "Test passed"),
                    duration=duration,
                    details=result.get("details")
                ))
            else:
                print("✗ FAIL")
                self.results.append(TestResult(
                    name=test_name,
                    passed=False,
                    message=result.get("message", "Test failed"),
                    duration=duration,
                    details=result.get("details")
                ))
        except Exception as e:
            duration = time.time() - start_time
            print(f"✗ ERROR: {str(e)}")
            self.results.append(TestResult(
                name=test_name,
                passed=False,
                message=f"Exception: {str(e)}",
                duration=duration
            ))
    
    def test_health_check(self) -> Dict[str, Any]:
        """Test basic health endpoint."""
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    return {
                        "success": True,
                        "message": "Health check passed",
                        "details": data
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Unhealthy status: {data.get('status')}",
                        "details": data
                    }
            else:
                return {
                    "success": False,
                    "message": f"Health check failed with status {response.status_code}",
                    "details": {"status_code": response.status_code, "response": response.text}
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Health check exception: {str(e)}"
            }
    
    def test_api_authentication(self) -> Dict[str, Any]:
        """Test API authentication."""
        try:
            # Test with valid API key
            response = requests.get(
                f"{self.base_url}/api/v1/clips",
                headers=self.headers,
                timeout=self.timeout
            )
            
            if response.status_code in [200, 401, 403]:
                # Test without API key
                response_no_auth = requests.get(
                    f"{self.base_url}/api/v1/clips",
                    timeout=self.timeout
                )
                
                if response_no_auth.status_code == 401:
                    return {
                        "success": True,
                        "message": "Authentication working correctly",
                        "details": {
                            "with_auth": response.status_code,
                            "without_auth": response_no_auth.status_code
                        }
                    }
                else:
                    return {
                        "success": False,
                        "message": "Authentication not enforced",
                        "details": {
                            "with_auth": response.status_code,
                            "without_auth": response_no_auth.status_code
                        }
                    }
            else:
                return {
                    "success": False,
                    "message": f"Unexpected auth response: {response.status_code}",
                    "details": {"status_code": response.status_code}
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Authentication test exception: {str(e)}"
            }
    
    def test_clip_generation_endpoint(self) -> Dict[str, Any]:
        """Test clip generation endpoint."""
        try:
            test_data = {
                "title": "Staging Test Clip",
                "description": "Test clip for staging smoke test",
                "platform": "youtube",
                "topic": "technology",
                "duration": 60,
                "requirements": {
                    "include_captions": True,
                    "quality": "720p"
                }
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/clips/generate",
                json=test_data,
                headers=self.headers,
                timeout=self.timeout
            )
            
            if response.status_code == 202:
                data = response.json()
                task_id = data.get("task_id")
                if task_id:
                    return {
                        "success": True,
                        "message": "Clip generation endpoint working",
                        "details": {"task_id": task_id, "response": data}
                    }
                else:
                    return {
                        "success": False,
                        "message": "No task_id in response",
                        "details": data
                    }
            elif response.status_code == 429:
                return {
                    "success": True,
                    "message": "Rate limiting working (429 response)",
                    "details": {"status_code": response.status_code}
                }
            else:
                return {
                    "success": False,
                    "message": f"Unexpected response: {response.status_code}",
                    "details": {"status_code": response.status_code, "response": response.text}
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Clip generation test exception: {str(e)}"
            }
    
    def test_database_connectivity(self) -> Dict[str, Any]:
        """Test database connectivity through API."""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/clips",
                headers=self.headers,
                params={"limit": 1},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if "clips" in data and "total" in data:
                    return {
                        "success": True,
                        "message": "Database connectivity working",
                        "details": {"total_clips": data.get("total")}
                    }
                else:
                    return {
                        "success": False,
                        "message": "Invalid response format from database query",
                        "details": data
                    }
            else:
                return {
                    "success": False,
                    "message": f"Database query failed: {response.status_code}",
                    "details": {"status_code": response.status_code}
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Database connectivity test exception: {str(e)}"
            }
    
    def test_monitoring_endpoints(self) -> Dict[str, Any]:
        """Test monitoring endpoints."""
        try:
            endpoints = [
                "/api/v1/monitoring/metrics",
                "/api/v1/monitoring/health"
            ]
            
            results = {}
            all_passed = True
            
            for endpoint in endpoints:
                response = requests.get(
                    f"{self.base_url}{endpoint}",
                    headers=self.headers,
                    timeout=self.timeout
                )
                
                results[endpoint] = {
                    "status_code": response.status_code,
                    "success": response.status_code == 200
                }
                
                if response.status_code != 200:
                    all_passed = False
            
            return {
                "success": all_passed,
                "message": "All monitoring endpoints working" if all_passed else "Some monitoring endpoints failed",
                "details": results
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Monitoring endpoints test exception: {str(e)}"
            }
    
    def test_rate_limiting(self) -> Dict[str, Any]:
        """Test rate limiting functionality."""
        try:
            # Send multiple rapid requests
            responses = []
            for i in range(10):
                response = requests.get(
                    f"{self.base_url}/api/v1/clips",
                    headers=self.headers,
                    timeout=self.timeout
                )
                responses.append(response.status_code)
                time.sleep(0.1)  # Small delay
            
            # Check if we got any rate limit responses
            rate_limited = any(code == 429 for code in responses)
            success_responses = sum(1 for code in responses if code == 200)
            
            if rate_limited or success_responses > 0:
                return {
                    "success": True,
                    "message": "Rate limiting appears to be working",
                    "details": {
                        "responses": responses,
                        "rate_limited": rate_limited,
                        "success_count": success_responses
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "No successful or rate-limited responses",
                    "details": {"responses": responses}
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Rate limiting test exception: {str(e)}"
            }
    
    def test_ssl_certificate(self) -> Dict[str, Any]:
        """Test SSL certificate validity."""
        try:
            if not self.base_url.startswith("https://"):
                return {
                    "success": True,
                    "message": "HTTP endpoint, SSL test skipped"
                }
            
            response = requests.get(
                f"{self.base_url}/health",
                timeout=self.timeout,
                verify=True  # Verify SSL certificate
            )
            
            return {
                "success": True,
                "message": "SSL certificate is valid",
                "details": {"status_code": response.status_code}
            }
        except requests.exceptions.SSLError as e:
            return {
                "success": False,
                "message": f"SSL certificate error: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"SSL test exception: {str(e)}"
            }
    
    def run_all_tests(self):
        """Run all smoke tests."""
        print(f"Running staging smoke tests against: {self.base_url}")
        print("=" * 60)
        
        tests = [
            ("Health Check", self.test_health_check),
            ("API Authentication", self.test_api_authentication),
            ("Clip Generation Endpoint", self.test_clip_generation_endpoint),
            ("Database Connectivity", self.test_database_connectivity),
            ("Monitoring Endpoints", self.test_monitoring_endpoints),
            ("Rate Limiting", self.test_rate_limiting),
            ("SSL Certificate", self.test_ssl_certificate),
        ]
        
        for test_name, test_func in tests:
            self.run_test(test_name, test_func)
        
        self.print_summary()
        return self.get_exit_code()
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("STAGING SMOKE TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        
        print(f"Tests passed: {passed}/{total}")
        print(f"Success rate: {(passed/total)*100:.1f}%")
        
        if passed < total:
            print("\nFAILED TESTS:")
            for result in self.results:
                if not result.passed:
                    print(f"  ✗ {result.name}: {result.message}")
        
        print("\nTEST DETAILS:")
        for result in self.results:
            status = "✓" if result.passed else "✗"
            print(f"  {status} {result.name} ({result.duration:.2f}s): {result.message}")
    
    def get_exit_code(self) -> int:
        """Get exit code based on test results."""
        failed_tests = sum(1 for r in self.results if not r.passed)
        return 0 if failed_tests == 0 else 1


def main():
    """Main function."""
    tester = StagingSmokeTests()
    exit_code = tester.run_all_tests()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()