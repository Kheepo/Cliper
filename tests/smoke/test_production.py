#!/usr/bin/env python3
"""
Smoke tests for production environment.
These tests verify critical functionality in production with minimal impact.
"""

import os
import sys
import time
import requests
import json
import ssl
import socket
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class TestResult:
    """Test result container."""
    name: str
    passed: bool
    message: str
    duration: float
    severity: str = "medium"  # low, medium, high, critical
    details: Optional[Dict[str, Any]] = None


class ProductionSmokeTests:
    """Smoke tests for production environment."""
    
    def __init__(self):
        self.base_url = os.getenv("PRODUCTION_URL", "https://api.example.com")
        self.api_key = os.getenv("PRODUCTION_API_KEY", "")
        self.timeout = 10  # Shorter timeout for production
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ProductionSmokeTest/1.0"
        }
        self.results = []
        self.critical_failures = []
    
    def run_test(self, test_name: str, test_func, severity: str = "medium"):
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
                    severity=severity,
                    details=result.get("details")
                ))
            else:
                print("✗ FAIL")
                test_result = TestResult(
                    name=test_name,
                    passed=False,
                    message=result.get("message", "Test failed"),
                    duration=duration,
                    severity=severity,
                    details=result.get("details")
                )
                self.results.append(test_result)
                
                if severity in ["high", "critical"]:
                    self.critical_failures.append(test_result)
                    
        except Exception as e:
            duration = time.time() - start_time
            print(f"✗ ERROR: {str(e)}")
            test_result = TestResult(
                name=test_name,
                passed=False,
                message=f"Exception: {str(e)}",
                duration=duration,
                severity=severity
            )
            self.results.append(test_result)
            
            if severity in ["high", "critical"]:
                self.critical_failures.append(test_result)
    
    def test_health_check(self) -> Dict[str, Any]:
        """Test basic health endpoint - CRITICAL."""
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                
                if status == "healthy":
                    return {
                        "success": True,
                        "message": f"Service healthy (response time: {response.elapsed.total_seconds():.3f}s)",
                        "details": {
                            "status": status,
                            "response_time": response.elapsed.total_seconds(),
                            "timestamp": data.get("timestamp")
                        }
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Service unhealthy: {status}",
                        "details": data
                    }
            else:
                return {
                    "success": False,
                    "message": f"Health endpoint returned {response.status_code}",
                    "details": {"status_code": response.status_code, "response": response.text[:200]}
                }
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "message": f"Health check timed out after {self.timeout}s"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Health check failed: {str(e)}"
            }
    
    def test_ssl_security(self) -> Dict[str, Any]:
        """Test SSL/TLS security configuration - HIGH."""
        try:
            if not self.base_url.startswith("https://"):
                return {
                    "success": False,
                    "message": "Production API must use HTTPS"
                }
            
            parsed_url = urlparse(self.base_url)
            hostname = parsed_url.hostname
            port = parsed_url.port or 443
            
            # Check SSL certificate
            context = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=self.timeout) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    
                    # Check certificate expiry
                    not_after = cert.get('notAfter')
                    if not_after:
                        expiry_time = time.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
                        expiry_timestamp = time.mktime(expiry_time)
                        days_until_expiry = (expiry_timestamp - time.time()) / (24 * 3600)
                        
                        if days_until_expiry < 30:
                            return {
                                "success": False,
                                "message": f"SSL certificate expires in {days_until_expiry:.1f} days",
                                "details": {"expiry_date": not_after, "days_remaining": days_until_expiry}
                            }
                    
                    return {
                        "success": True,
                        "message": "SSL certificate is valid and secure",
                        "details": {
                            "subject": dict(x[0] for x in cert['subject']),
                            "issuer": dict(x[0] for x in cert['issuer']),
                            "version": cert.get('version'),
                            "expires": not_after
                        }
                    }
        except Exception as e:
            return {
                "success": False,
                "message": f"SSL security check failed: {str(e)}"
            }
    
    def test_api_authentication(self) -> Dict[str, Any]:
        """Test API authentication - HIGH."""
        try:
            if not self.api_key:
                return {
                    "success": False,
                    "message": "No API key provided for production testing"
                }
            
            # Test with valid API key
            response = requests.get(
                f"{self.base_url}/api/v1/clips",
                headers=self.headers,
                params={"limit": 1},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                # Test without API key to ensure auth is enforced
                response_no_auth = requests.get(
                    f"{self.base_url}/api/v1/clips",
                    timeout=self.timeout
                )
                
                if response_no_auth.status_code == 401:
                    return {
                        "success": True,
                        "message": "Authentication working correctly",
                        "details": {
                            "authenticated_status": response.status_code,
                            "unauthenticated_status": response_no_auth.status_code
                        }
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Authentication not enforced (got {response_no_auth.status_code} without auth)",
                        "details": {"unauthenticated_status": response_no_auth.status_code}
                    }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "message": "API key appears to be invalid",
                    "details": {"status_code": response.status_code}
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
                "message": f"Authentication test failed: {str(e)}"
            }
    
    def test_response_times(self) -> Dict[str, Any]:
        """Test API response times - MEDIUM."""
        try:
            endpoints = [
                "/health",
                "/api/v1/clips"
            ]
            
            response_times = {}
            slow_endpoints = []
            
            for endpoint in endpoints:
                start_time = time.time()
                response = requests.get(
                    f"{self.base_url}{endpoint}",
                    headers=self.headers if endpoint.startswith("/api") else {},
                    timeout=self.timeout
                )
                response_time = time.time() - start_time
                
                response_times[endpoint] = {
                    "time": response_time,
                    "status": response.status_code
                }
                
                # Flag slow responses (>2 seconds)
                if response_time > 2.0:
                    slow_endpoints.append(endpoint)
            
            avg_response_time = sum(rt["time"] for rt in response_times.values()) / len(response_times)
            
            if slow_endpoints:
                return {
                    "success": False,
                    "message": f"Slow response times detected: {slow_endpoints}",
                    "details": {
                        "response_times": response_times,
                        "average": avg_response_time,
                        "slow_endpoints": slow_endpoints
                    }
                }
            else:
                return {
                    "success": True,
                    "message": f"Response times acceptable (avg: {avg_response_time:.3f}s)",
                    "details": {
                        "response_times": response_times,
                        "average": avg_response_time
                    }
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Response time test failed: {str(e)}"
            }
    
    def test_database_connectivity(self) -> Dict[str, Any]:
        """Test database connectivity - CRITICAL."""
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
                        "message": "Database connectivity confirmed",
                        "details": {
                            "total_clips": data.get("total"),
                            "response_time": response.elapsed.total_seconds()
                        }
                    }
                else:
                    return {
                        "success": False,
                        "message": "Invalid database response format",
                        "details": data
                    }
            elif response.status_code == 503:
                return {
                    "success": False,
                    "message": "Database appears to be unavailable (503)",
                    "details": {"status_code": response.status_code}
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
                "message": f"Database connectivity test failed: {str(e)}"
            }
    
    def test_rate_limiting(self) -> Dict[str, Any]:
        """Test rate limiting - MEDIUM."""
        try:
            # Send requests to test rate limiting
            responses = []
            for i in range(5):  # Fewer requests for production
                response = requests.get(
                    f"{self.base_url}/api/v1/clips",
                    headers=self.headers,
                    params={"limit": 1},
                    timeout=self.timeout
                )
                responses.append({
                    "status_code": response.status_code,
                    "headers": dict(response.headers)
                })
                time.sleep(0.2)  # Small delay
            
            # Check for rate limit headers
            rate_limit_headers = []
            for resp in responses:
                headers = resp["headers"]
                if any(header.lower().startswith("x-ratelimit") for header in headers):
                    rate_limit_headers.append(headers)
            
            if rate_limit_headers:
                return {
                    "success": True,
                    "message": "Rate limiting headers detected",
                    "details": {
                        "responses": [r["status_code"] for r in responses],
                        "rate_limit_headers": rate_limit_headers[0] if rate_limit_headers else None
                    }
                }
            else:
                return {
                    "success": True,
                    "message": "No rate limiting detected (may be configured at higher thresholds)",
                    "details": {"responses": [r["status_code"] for r in responses]}
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Rate limiting test failed: {str(e)}"
            }
    
    def test_monitoring_endpoints(self) -> Dict[str, Any]:
        """Test monitoring endpoints - HIGH."""
        try:
            endpoints = [
                "/api/v1/monitoring/health",
                "/api/v1/monitoring/metrics"
            ]
            
            results = {}
            all_passed = True
            
            for endpoint in endpoints:
                try:
                    response = requests.get(
                        f"{self.base_url}{endpoint}",
                        headers=self.headers,
                        timeout=self.timeout
                    )
                    
                    results[endpoint] = {
                        "status_code": response.status_code,
                        "response_time": response.elapsed.total_seconds(),
                        "success": response.status_code == 200
                    }
                    
                    if response.status_code != 200:
                        all_passed = False
                        
                except Exception as e:
                    results[endpoint] = {
                        "error": str(e),
                        "success": False
                    }
                    all_passed = False
            
            return {
                "success": all_passed,
                "message": "All monitoring endpoints working" if all_passed else "Some monitoring endpoints failed",
                "details": results
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Monitoring endpoints test failed: {str(e)}"
            }
    
    def test_error_handling(self) -> Dict[str, Any]:
        """Test error handling - MEDIUM."""
        try:
            # Test invalid endpoint
            response = requests.get(
                f"{self.base_url}/api/v1/invalid-endpoint",
                headers=self.headers,
                timeout=self.timeout
            )
            
            if response.status_code == 404:
                try:
                    error_data = response.json()
                    if "error" in error_data or "message" in error_data:
                        return {
                            "success": True,
                            "message": "Error handling working correctly",
                            "details": {
                                "status_code": response.status_code,
                                "error_format": error_data
                            }
                        }
                    else:
                        return {
                            "success": False,
                            "message": "Error response missing proper error format",
                            "details": {"response": error_data}
                        }
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "message": "Error response is not valid JSON",
                        "details": {"response": response.text[:200]}
                    }
            else:
                return {
                    "success": False,
                    "message": f"Expected 404 for invalid endpoint, got {response.status_code}",
                    "details": {"status_code": response.status_code}
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error handling test failed: {str(e)}"
            }
    
    def run_all_tests(self):
        """Run all production smoke tests."""
        print(f"Running production smoke tests against: {self.base_url}")
        print("=" * 70)
        
        tests = [
            ("Health Check", self.test_health_check, "critical"),
            ("SSL Security", self.test_ssl_security, "high"),
            ("API Authentication", self.test_api_authentication, "high"),
            ("Database Connectivity", self.test_database_connectivity, "critical"),
            ("Monitoring Endpoints", self.test_monitoring_endpoints, "high"),
            ("Response Times", self.test_response_times, "medium"),
            ("Rate Limiting", self.test_rate_limiting, "medium"),
            ("Error Handling", self.test_error_handling, "medium"),
        ]
        
        for test_name, test_func, severity in tests:
            self.run_test(test_name, test_func, severity)
        
        self.print_summary()
        return self.get_exit_code()
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 70)
        print("PRODUCTION SMOKE TEST SUMMARY")
        print("=" * 70)
        
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        critical_failed = len(self.critical_failures)
        
        print(f"Tests passed: {passed}/{total}")
        print(f"Success rate: {(passed/total)*100:.1f}%")
        print(f"Critical failures: {critical_failed}")
        
        if critical_failed > 0:
            print("\n🚨 CRITICAL FAILURES:")
            for result in self.critical_failures:
                print(f"  ✗ {result.name}: {result.message}")
        
        if passed < total:
            print("\nALL FAILED TESTS:")
            for result in self.results:
                if not result.passed:
                    severity_icon = "🚨" if result.severity == "critical" else "⚠️" if result.severity == "high" else "ℹ️"
                    print(f"  {severity_icon} {result.name} ({result.severity}): {result.message}")
        
        print("\nTEST DETAILS:")
        for result in self.results:
            status = "✓" if result.passed else "✗"
            severity_icon = "🚨" if result.severity == "critical" else "⚠️" if result.severity == "high" else "ℹ️"
            print(f"  {status} {result.name} ({result.duration:.2f}s) {severity_icon}: {result.message}")
    
    def get_exit_code(self) -> int:
        """Get exit code based on test results."""
        # Exit with error code if any critical tests failed
        if self.critical_failures:
            return 2  # Critical failure
        
        # Exit with warning code if any high severity tests failed
        high_failures = sum(1 for r in self.results if not r.passed and r.severity == "high")
        if high_failures > 0:
            return 1  # High severity failure
        
        # Exit with success if only medium/low severity failures
        failed_tests = sum(1 for r in self.results if not r.passed)
        return 0 if failed_tests == 0 else 1


def main():
    """Main function."""
    tester = ProductionSmokeTests()
    exit_code = tester.run_all_tests()
    
    # Print final status
    if exit_code == 0:
        print("\n✅ All production smoke tests passed!")
    elif exit_code == 1:
        print("\n⚠️ Some tests failed, but no critical issues detected.")
    elif exit_code == 2:
        print("\n🚨 CRITICAL FAILURES DETECTED! Immediate attention required.")
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()