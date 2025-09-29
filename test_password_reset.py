#!/usr/bin/env python3
"""
Password Reset Functionality Test
Tests password reset flow and email functionality
"""

import requests
import json
import time
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpassword123"
NEW_PASSWORD = "newpassword456"

def test_server_connectivity() -> bool:
    """Test if the server is running"""
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def test_password_reset_request() -> Dict[str, Any]:
    """Test password reset request endpoint"""
    print("\n=== Testing Password Reset Request ===")
    
    endpoints_to_test = [
        "/api/auth/reset-password",
        "/api/auth/password-reset", 
        "/api/auth/forgot-password",
        "/api/users/reset-password",
        "/api/password-reset"
    ]
    
    results = {}
    
    for endpoint in endpoints_to_test:
        try:
            # Test POST request
            response = requests.post(
                f"{BASE_URL}{endpoint}",
                json={"email": TEST_EMAIL},
                timeout=10
            )
            
            status = response.status_code
            print(f"{endpoint}: {status}")
            
            if status == 200:
                print(f"  ✓ Password reset request successful")
                results[endpoint] = {"status": "success", "code": status}
            elif status == 404:
                print(f"  ✗ Endpoint not found")
                results[endpoint] = {"status": "not_found", "code": status}
            elif status == 422:
                print(f"  ⚠ Validation error (expected for invalid email)")
                results[endpoint] = {"status": "validation_error", "code": status}
            else:
                print(f"  ? Unexpected status: {status}")
                results[endpoint] = {"status": "unexpected", "code": status}
                
        except Exception as e:
            print(f"{endpoint}: Error - {str(e)}")
            results[endpoint] = {"status": "error", "error": str(e)}
    
    return results

def test_password_reset_confirm() -> Dict[str, Any]:
    """Test password reset confirmation endpoint"""
    print("\n=== Testing Password Reset Confirmation ===")
    
    endpoints_to_test = [
        "/api/auth/reset-password/confirm",
        "/api/auth/password-reset/confirm",
        "/api/auth/confirm-reset",
        "/api/users/reset-password/confirm"
    ]
    
    results = {}
    test_token = "test-reset-token-123"
    
    for endpoint in endpoints_to_test:
        try:
            # Test POST request with token and new password
            response = requests.post(
                f"{BASE_URL}{endpoint}",
                json={
                    "token": test_token,
                    "password": NEW_PASSWORD,
                    "confirm_password": NEW_PASSWORD
                },
                timeout=10
            )
            
            status = response.status_code
            print(f"{endpoint}: {status}")
            
            if status == 200:
                print(f"  ✓ Password reset confirmation successful")
                results[endpoint] = {"status": "success", "code": status}
            elif status == 404:
                print(f"  ✗ Endpoint not found")
                results[endpoint] = {"status": "not_found", "code": status}
            elif status == 400 or status == 422:
                print(f"  ⚠ Invalid token/validation error (expected)")
                results[endpoint] = {"status": "validation_error", "code": status}
            else:
                print(f"  ? Unexpected status: {status}")
                results[endpoint] = {"status": "unexpected", "code": status}
                
        except Exception as e:
            print(f"{endpoint}: Error - {str(e)}")
            results[endpoint] = {"status": "error", "error": str(e)}
    
    return results

def test_auth_endpoints() -> Dict[str, Any]:
    """Test general auth endpoints"""
    print("\n=== Testing Auth Endpoints ===")
    
    endpoints_to_test = [
        ("/api/auth/signup", "POST"),
        ("/api/auth/login", "POST"),
        ("/api/auth/logout", "POST"),
        ("/api/auth/me", "GET"),
        ("/api/auth/refresh", "POST")
    ]
    
    results = {}
    
    for endpoint, method in endpoints_to_test:
        try:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            else:
                response = requests.post(
                    f"{BASE_URL}{endpoint}",
                    json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
                    timeout=10
                )
            
            status = response.status_code
            print(f"{endpoint} ({method}): {status}")
            
            if status in [200, 401, 422]:  # Expected responses
                print(f"  ✓ Endpoint available")
                results[endpoint] = {"status": "available", "code": status}
            elif status == 404:
                print(f"  ✗ Endpoint not found")
                results[endpoint] = {"status": "not_found", "code": status}
            else:
                print(f"  ? Unexpected status: {status}")
                results[endpoint] = {"status": "unexpected", "code": status}
                
        except Exception as e:
            print(f"{endpoint}: Error - {str(e)}")
            results[endpoint] = {"status": "error", "error": str(e)}
    
    return results

def test_email_configuration() -> Dict[str, Any]:
    """Test email configuration endpoints"""
    print("\n=== Testing Email Configuration ===")
    
    endpoints_to_test = [
        "/api/config/email",
        "/api/email/config",
        "/api/settings/email"
    ]
    
    results = {}
    
    for endpoint in endpoints_to_test:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            status = response.status_code
            print(f"{endpoint}: {status}")
            
            if status == 200:
                print(f"  ✓ Email config available")
                results[endpoint] = {"status": "available", "code": status}
            elif status == 404:
                print(f"  ✗ Endpoint not found")
                results[endpoint] = {"status": "not_found", "code": status}
            else:
                print(f"  ? Status: {status}")
                results[endpoint] = {"status": "other", "code": status}
                
        except Exception as e:
            print(f"{endpoint}: Error - {str(e)}")
            results[endpoint] = {"status": "error", "error": str(e)}
    
    return results

def main():
    print("🔐 PASSWORD RESET FUNCTIONALITY TEST")
    print("=" * 50)
    
    # Test server connectivity
    if not test_server_connectivity():
        print("❌ Server not accessible at", BASE_URL)
        print("\n💡 Common issues:")
        print("   • Server not running (try: python run_server.py)")
        print("   • Wrong port or URL")
        print("   • Firewall blocking connection")
        return
    
    print("✅ Server is running")
    
    # Run tests
    reset_request_results = test_password_reset_request()
    reset_confirm_results = test_password_reset_confirm()
    auth_results = test_auth_endpoints()
    email_results = test_email_configuration()
    
    # Summary
    print("\n" + "=" * 55)
    print("📊 PASSWORD RESET TEST SUMMARY")
    print("=" * 55)
    
    # Count available endpoints
    total_reset_endpoints = len(reset_request_results)
    available_reset_endpoints = sum(1 for r in reset_request_results.values() 
                                  if r.get('status') in ['success', 'validation_error'])
    
    total_confirm_endpoints = len(reset_confirm_results)
    available_confirm_endpoints = sum(1 for r in reset_confirm_results.values() 
                                    if r.get('status') in ['success', 'validation_error'])
    
    total_auth_endpoints = len(auth_results)
    available_auth_endpoints = sum(1 for r in auth_results.values() 
                                 if r.get('status') == 'available')
    
    total_email_endpoints = len(email_results)
    available_email_endpoints = sum(1 for r in email_results.values() 
                                  if r.get('status') == 'available')
    
    print(f"Password Reset Request: {available_reset_endpoints}/{total_reset_endpoints} endpoints available")
    print(f"Password Reset Confirm: {available_confirm_endpoints}/{total_confirm_endpoints} endpoints available")
    print(f"Auth Endpoints: {available_auth_endpoints}/{total_auth_endpoints} endpoints available")
    print(f"Email Config: {available_email_endpoints}/{total_email_endpoints} endpoints available")
    
    print("\n📋 IMPLEMENTATION STATUS:")
    if available_reset_endpoints > 0:
        print("- Password reset request: ✓ Available")
    else:
        print("- Password reset request: ✗ Not implemented")
        
    if available_confirm_endpoints > 0:
        print("- Password reset confirm: ✓ Available")
    else:
        print("- Password reset confirm: ✗ Not implemented")
        
    if available_auth_endpoints >= 3:
        print("- Basic auth endpoints: ✓ Available")
    else:
        print("- Basic auth endpoints: ⚠ Partially available")
        
    if available_email_endpoints > 0:
        print("- Email configuration: ✓ Available")
    else:
        print("- Email configuration: ✗ Not available")
    
    print("\n💡 Common issues:")
    print("   • Password reset endpoints may need implementation")
    print("   • Email service configuration required")
    print("   • SMTP settings may need setup")
    print("   • Frontend integration may be needed")

if __name__ == "__main__":
    main()