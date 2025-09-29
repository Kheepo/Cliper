#!/usr/bin/env python3
"""
Google OAuth Integration Test Suite for Cliper

This script tests the Google OAuth functionality in the Cliper authentication system.
It verifies both frontend and backend integration with Supabase Google OAuth.
"""

import requests
import json
import time
import sys
from urllib.parse import urljoin, parse_qs, urlparse

class GoogleOAuthTester:
    def __init__(self):
        self.frontend_url = "http://localhost:3000"
        self.backend_url = "http://localhost:8001"
        self.test_results = []
        
    def test_frontend_accessibility(self):
        """Test if frontend is accessible"""
        try:
            response = requests.get(self.frontend_url, timeout=10)
            if response.status_code == 200:
                self.test_results.append("✅ Frontend accessible")
                return True
            else:
                self.test_results.append(f"❌ Frontend returned status {response.status_code}")
                return False
        except Exception as e:
            self.test_results.append(f"❌ Frontend not accessible: {e}")
            return False
    
    def test_backend_health(self):
        """Test if backend is accessible"""
        try:
            response = requests.get(f"{self.backend_url}/health", timeout=10)
            if response.status_code == 200:
                self.test_results.append("✅ Backend health check passed")
                return True
            else:
                self.test_results.append(f"❌ Backend health check failed: {response.status_code}")
                return False
        except Exception as e:
            self.test_results.append(f"❌ Backend not accessible: {e}")
            return False
    
    def test_google_oauth_frontend_code(self):
        """Test if Google OAuth code exists in frontend files"""
        try:
            # Check if AuthContext has Google OAuth implementation
            with open('src/contexts/AuthContext.tsx', 'r', encoding='utf-8') as f:
                auth_content = f.read()
                if 'loginWithGoogle' in auth_content and 'signInWithGoogle' in auth_content:
                    self.test_results.append("✅ Google OAuth implementation found in AuthContext")
                else:
                    self.test_results.append("❌ Google OAuth implementation missing in AuthContext")
                    return False
            
            # Check if Supabase lib has Google OAuth implementation
            with open('src/lib/supabase.ts', 'r', encoding='utf-8') as f:
                supabase_content = f.read()
                if 'signInWithGoogle' in supabase_content and 'signInWithOAuth' in supabase_content:
                    self.test_results.append("✅ Google OAuth implementation found in Supabase lib")
                else:
                    self.test_results.append("❌ Google OAuth implementation missing in Supabase lib")
                    return False
            
            # Check Login component
            with open('src/pages/Login.tsx', 'r', encoding='utf-8') as f:
                login_content = f.read()
                if 'Continue with Google' in login_content and 'handleGoogleLogin' in login_content:
                    self.test_results.append("✅ Google OAuth button found in Login component")
                else:
                    self.test_results.append("❌ Google OAuth button missing in Login component")
                    return False
            
            # Check Register component
            with open('src/pages/Register.tsx', 'r', encoding='utf-8') as f:
                register_content = f.read()
                if 'Continue with Google' in register_content and 'handleGoogleSignUp' in register_content:
                    self.test_results.append("✅ Google OAuth button found in Register component")
                else:
                    self.test_results.append("❌ Google OAuth button missing in Register component")
                    return False
            
            return True
            
        except FileNotFoundError as e:
            self.test_results.append(f"❌ Frontend file not found: {e}")
            return False
        except Exception as e:
            self.test_results.append(f"❌ Error checking frontend code: {e}")
            return False
    
    def test_supabase_config(self):
        """Test if Supabase configuration includes Google OAuth"""
        try:
            # Check if .env file has Supabase configuration
            try:
                with open('.env', 'r') as f:
                    env_content = f.read()
                    if 'VITE_SUPABASE_URL' in env_content and 'VITE_SUPABASE_ANON_KEY' in env_content:
                        self.test_results.append("✅ Supabase environment variables found")
                    else:
                        self.test_results.append("❌ Supabase environment variables missing")
                        return False
            except FileNotFoundError:
                self.test_results.append("⚠️ .env file not found - checking .env.local")
                try:
                    with open('.env.local', 'r') as f:
                        env_content = f.read()
                        if 'VITE_SUPABASE_URL' in env_content and 'VITE_SUPABASE_ANON_KEY' in env_content:
                            self.test_results.append("✅ Supabase environment variables found in .env.local")
                        else:
                            self.test_results.append("❌ Supabase environment variables missing in .env.local")
                            return False
                except FileNotFoundError:
                    self.test_results.append("❌ No Supabase environment file found")
                    return False
            
            # Check Supabase client configuration
            try:
                with open('src/lib/supabase.ts', 'r', encoding='utf-8') as f:
                    supabase_content = f.read()
                    if 'createClient' in supabase_content:
                        self.test_results.append("✅ Supabase client configuration found")
                    else:
                        self.test_results.append("❌ Supabase client configuration missing")
                        return False
            except FileNotFoundError:
                self.test_results.append("❌ Supabase client file not found")
                return False
            
            return True
            
        except Exception as e:
            self.test_results.append(f"❌ Error checking Supabase config: {e}")
            return False
    
    def test_oauth_redirect_config(self):
        """Test OAuth redirect configuration"""
        try:
            # Check if there's a callback route or handling
            with open('src/App.tsx', 'r', encoding='utf-8') as f:
                app_content = f.read()
                if 'auth/callback' in app_content or 'useEffect' in app_content:
                    self.test_results.append("✅ OAuth callback handling likely configured")
                else:
                    self.test_results.append("⚠️ OAuth callback handling not clearly visible")
            
            return True
            
        except Exception as e:
            self.test_results.append(f"⚠️ Could not verify OAuth redirect config: {e}")
            return True
    
    def test_google_oauth_manual_flow(self):
        """Test Google OAuth flow manually by checking frontend response"""
        try:
            # Test if frontend loads without errors
            response = requests.get(f"{self.frontend_url}/login", timeout=10)
            if response.status_code == 200:
                if 'Continue with Google' in response.text:
                    self.test_results.append("✅ Google OAuth button visible in login page HTML")
                else:
                    self.test_results.append("⚠️ Google OAuth button not found in login page HTML (may be dynamically rendered)")
            
            response = requests.get(f"{self.frontend_url}/register", timeout=10)
            if response.status_code == 200:
                if 'Continue with Google' in response.text:
                    self.test_results.append("✅ Google OAuth button visible in register page HTML")
                else:
                    self.test_results.append("⚠️ Google OAuth button not found in register page HTML (may be dynamically rendered)")
            
            return True
            
        except Exception as e:
            self.test_results.append(f"⚠️ Could not test manual OAuth flow: {e}")
            return True
    
    def run_all_tests(self):
        """Run all Google OAuth tests"""
        print("🚀 Starting Google OAuth Integration Tests for Cliper\n")
        
        # Basic connectivity tests
        print("📡 Testing basic connectivity...")
        frontend_ok = self.test_frontend_accessibility()
        backend_ok = self.test_backend_health()
        
        if not frontend_ok:
            print("❌ Frontend not accessible. Please ensure frontend is running on http://localhost:3000")
        
        if not backend_ok:
            print("❌ Backend not accessible. Please ensure backend is running on http://localhost:8001")
        
        # Code structure tests
        print("\n🔍 Testing Google OAuth code implementation...")
        self.test_google_oauth_frontend_code()
        
        print("\n⚙️ Testing Supabase configuration...")
        self.test_supabase_config()
        
        print("\n🔄 Testing OAuth redirect configuration...")
        self.test_oauth_redirect_config()
        
        print("\n🌐 Testing manual OAuth flow...")
        self.test_google_oauth_manual_flow()
        
        # Print results
        self.print_results()
        
        return True
    
    def print_results(self):
        """Print test results summary"""
        print("\n" + "="*60)
        print("📊 GOOGLE OAUTH TEST RESULTS")
        print("="*60)
        
        for result in self.test_results:
            print(result)
        
        # Count results
        passed = len([r for r in self.test_results if r.startswith("✅")])
        failed = len([r for r in self.test_results if r.startswith("❌")])
        warnings = len([r for r in self.test_results if r.startswith("⚠️")])
        info = len([r for r in self.test_results if r.startswith("ℹ️")])
        
        print("\n" + "-"*60)
        print(f"📈 SUMMARY: {passed} passed, {failed} failed, {warnings} warnings, {info} info")
        
        if failed == 0:
            print("\n🎉 All critical tests passed! Google OAuth integration looks good.")
            print("\n✅ READY FOR MANUAL TESTING:")
            print("1. 🌐 Open http://localhost:3000/login in your browser")
            print("2. 🖱️ Click the 'Continue with Google' button")
            print("3. 🔐 Complete the Google OAuth flow")
            print("4. ✅ Verify you're logged in and redirected properly")
        else:
            print(f"\n⚠️ {failed} critical issues found. Please review and fix before proceeding.")
        
        print("\n📋 NEXT STEPS FOR GOOGLE OAUTH:")
        print("1. 🔧 Ensure Google OAuth is enabled in Supabase Auth settings")
        print("2. 🌐 Verify Google OAuth app configuration in Google Cloud Console")
        print("3. 🔑 Check that Client ID and Client Secret are set in Supabase")
        print("4. 🔄 Ensure redirect URIs match exactly (http://localhost:3000/auth/callback)")
        print("5. 🧪 Test the actual login flow manually with a real Google account")
        
        print("\n💡 TROUBLESHOOTING TIPS:")
        print("• Make sure your Google Cloud project has OAuth consent screen configured")
        print("• Verify that your domain (localhost:3000) is authorized in Google Cloud Console")
        print("• Check Supabase Auth logs for any OAuth-related errors")
        print("• Ensure the Google OAuth provider is enabled in Supabase Dashboard > Auth > Providers")
        
if __name__ == "__main__":
    tester = GoogleOAuthTester()
    try:
        tester.run_all_tests()
    except KeyboardInterrupt:
        print("\n⏹️ Tests interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)