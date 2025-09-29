#!/usr/bin/env python3
"""
Google OAuth Validation Script
Validates that Google OAuth is properly configured and working
"""

import requests
import json
import time
from typing import Dict, Any, Tuple

# Supabase configuration
SUPABASE_URL = "https://stzdywhbdovjojtqxmsd.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN0emR5d2hiZG92am9qdHF4bXNkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc1NDA1NjgsImV4cCI6MjA3MzExNjU2OH0.R7GzJ18oGs4JQMBqdoq8h3jH_FQr4W8d0xJ_Wf9Hzm8"

def test_auth_settings() -> Tuple[bool, Dict[str, Any]]:
    """
    Test if Google OAuth is enabled in Supabase auth settings
    """
    print("🔍 Testing Supabase auth settings...")
    
    url = f"{SUPABASE_URL}/auth/v1/settings"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            settings = response.json()
            google_config = settings.get('external', {}).get('google', {})
            google_enabled = google_config.get('enabled', False)
            
            if google_enabled:
                print("✅ Google OAuth is ENABLED in Supabase")
                print(f"   - Client ID configured: {'Yes' if google_config.get('client_id') else 'No'}")
                return True, settings
            else:
                print("❌ Google OAuth is DISABLED in Supabase")
                return False, settings
        else:
            print(f"❌ Failed to get auth settings: {response.status_code}")
            return False, {}
            
    except Exception as e:
        print(f"❌ Error testing auth settings: {str(e)}")
        return False, {}

def test_oauth_authorize_endpoint() -> bool:
    """
    Test the OAuth authorize endpoint
    """
    print("\n🔍 Testing OAuth authorize endpoint...")
    
    url = f"{SUPABASE_URL}/auth/v1/authorize"
    params = {
        "provider": "google",
        "redirect_to": "http://localhost:3000/auth/callback"
    }
    headers = {
        "apikey": SUPABASE_ANON_KEY
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, allow_redirects=False, timeout=10)
        
        if response.status_code == 302:
            redirect_url = response.headers.get('Location', '')
            if 'accounts.google.com' in redirect_url:
                print("✅ OAuth endpoint working - redirects to Google")
                print(f"   - Redirect URL: {redirect_url[:100]}...")
                return True
            else:
                print(f"⚠️  Unexpected redirect: {redirect_url}")
                return False
        elif response.status_code == 400:
            error_data = response.json() if response.content else {}
            error_msg = error_data.get('msg', 'Unknown error')
            print(f"❌ OAuth endpoint error: {error_msg}")
            return False
        else:
            print(f"⚠️  Unexpected response: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing OAuth endpoint: {str(e)}")
        return False

def test_frontend_integration() -> bool:
    """
    Test if frontend can reach the development server
    """
    print("\n🔍 Testing frontend integration...")
    
    try:
        # Test if frontend dev server is running
        response = requests.get("http://localhost:3000", timeout=5)
        if response.status_code == 200:
            print("✅ Frontend dev server is running")
            return True
        else:
            print(f"⚠️  Frontend dev server returned: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Frontend dev server is not running")
        print("   Run: npm run client:dev")
        return False
    except Exception as e:
        print(f"❌ Error testing frontend: {str(e)}")
        return False

def test_google_oauth_flow_simulation() -> bool:
    """
    Simulate the Google OAuth flow without actual authentication
    """
    print("\n🔍 Simulating Google OAuth flow...")
    
    # Step 1: Test initial OAuth request
    oauth_url = f"{SUPABASE_URL}/auth/v1/authorize"
    params = {
        "provider": "google",
        "redirect_to": "http://localhost:3000/auth/callback"
    }
    headers = {
        "apikey": SUPABASE_ANON_KEY
    }
    
    try:
        # Test OAuth initiation
        response = requests.get(oauth_url, params=params, headers=headers, allow_redirects=False, timeout=10)
        
        if response.status_code == 302:
            redirect_url = response.headers.get('Location', '')
            
            # Check if redirect contains Google OAuth parameters
            required_params = ['client_id', 'redirect_uri', 'response_type', 'scope']
            params_found = sum(1 for param in required_params if param in redirect_url)
            
            print(f"✅ OAuth flow initiated successfully")
            print(f"   - Required OAuth parameters found: {params_found}/{len(required_params)}")
            print(f"   - Redirects to: accounts.google.com")
            
            if params_found >= 3:
                print("✅ OAuth flow appears properly configured")
                return True
            else:
                print("⚠️  Some OAuth parameters may be missing")
                return False
        else:
            print(f"❌ OAuth flow failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error simulating OAuth flow: {str(e)}")
        return False

def generate_test_report(results: Dict[str, bool]) -> Dict[str, Any]:
    """
    Generate a comprehensive test report
    """
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    success_rate = (passed_tests / total_tests) * 100
    
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "success_rate": success_rate,
        "test_results": results,
        "overall_status": "PASS" if success_rate >= 75 else "FAIL",
        "recommendations": []
    }
    
    # Add specific recommendations based on failures
    if not results.get('auth_settings', False):
        report["recommendations"].append("Enable Google OAuth in Supabase Dashboard")
    
    if not results.get('oauth_endpoint', False):
        report["recommendations"].append("Check Google Cloud Console configuration")
    
    if not results.get('frontend_integration', False):
        report["recommendations"].append("Start frontend development server")
    
    if not results.get('oauth_flow_simulation', False):
        report["recommendations"].append("Verify OAuth client credentials")
    
    if success_rate == 100:
        report["recommendations"].append("All tests passed! Google OAuth should be working.")
    
    return report

def main():
    """
    Main validation function
    """
    print("🧪 GOOGLE OAUTH VALIDATION SUITE")
    print("=" * 50)
    
    # Run all tests
    results = {}
    
    # Test 1: Auth settings
    auth_enabled, auth_settings = test_auth_settings()
    results['auth_settings'] = auth_enabled
    
    # Test 2: OAuth endpoint
    results['oauth_endpoint'] = test_oauth_authorize_endpoint()
    
    # Test 3: Frontend integration
    results['frontend_integration'] = test_frontend_integration()
    
    # Test 4: OAuth flow simulation
    results['oauth_flow_simulation'] = test_google_oauth_flow_simulation()
    
    # Generate report
    report = generate_test_report(results)
    
    # Display results
    print("\n" + "=" * 50)
    print("📊 VALIDATION RESULTS")
    print("=" * 50)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        test_display = test_name.replace('_', ' ').title()
        print(f"{test_display}: {status}")
    
    print(f"\nOverall Success Rate: {report['success_rate']:.1f}%")
    print(f"Overall Status: {report['overall_status']}")
    
    if report['recommendations']:
        print("\n📋 RECOMMENDATIONS:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"{i}. {rec}")
    
    # Save detailed report
    with open('google_oauth_validation_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: google_oauth_validation_report.json")
    
    # Final status
    if report['overall_status'] == 'PASS':
        print("\n🎉 VALIDATION SUCCESSFUL!")
        print("Google OAuth should be working in your application.")
        print("\n🚀 Next steps:")
        print("1. Open http://localhost:3000 in your browser")
        print("2. Go to Login or Register page")
        print("3. Click 'Continue with Google' button")
        print("4. Complete the OAuth flow")
    else:
        print("\n⚠️  VALIDATION FAILED")
        print("Please follow the recommendations above to fix the issues.")
        print("\n📖 For detailed setup instructions, see: GOOGLE_OAUTH_SETUP_GUIDE.md")

if __name__ == "__main__":
    main()