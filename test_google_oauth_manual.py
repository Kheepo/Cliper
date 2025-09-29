#!/usr/bin/env python3
"""
Manual Google OAuth Flow Test for Cliper

This script provides step-by-step instructions for manually testing
the Google OAuth functionality and validates the setup.
"""

import requests
import webbrowser
import time
import sys
from urllib.parse import urlparse

class ManualGoogleOAuthTester:
    def __init__(self):
        self.frontend_url = "http://localhost:3000"
        self.backend_url = "http://localhost:8001"
        
    def check_servers_running(self):
        """Check if both frontend and backend servers are running"""
        print("🔍 Checking server status...")
        
        try:
            frontend_response = requests.get(self.frontend_url, timeout=5)
            if frontend_response.status_code == 200:
                print("✅ Frontend server is running at http://localhost:3000")
            else:
                print(f"❌ Frontend server returned status {frontend_response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Frontend server is not accessible: {e}")
            print("💡 Please run: npm run client:dev")
            return False
        
        try:
            backend_response = requests.get(f"{self.backend_url}/health", timeout=5)
            if backend_response.status_code == 200:
                print("✅ Backend server is running at http://localhost:8001")
            else:
                print(f"❌ Backend server returned status {backend_response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Backend server is not accessible: {e}")
            print("💡 Please run: python -m uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload")
            return False
        
        return True
    
    def check_supabase_config(self):
        """Check Supabase configuration"""
        print("\n⚙️ Checking Supabase configuration...")
        
        try:
            with open('.env', 'r') as f:
                env_content = f.read()
                if 'VITE_SUPABASE_URL' in env_content and 'VITE_SUPABASE_ANON_KEY' in env_content:
                    print("✅ Supabase environment variables found")
                    return True
                else:
                    print("❌ Supabase environment variables missing")
                    return False
        except FileNotFoundError:
            try:
                with open('.env.local', 'r') as f:
                    env_content = f.read()
                    if 'VITE_SUPABASE_URL' in env_content and 'VITE_SUPABASE_ANON_KEY' in env_content:
                        print("✅ Supabase environment variables found in .env.local")
                        return True
                    else:
                        print("❌ Supabase environment variables missing in .env.local")
                        return False
            except FileNotFoundError:
                print("❌ No Supabase environment file found")
                print("💡 Please create .env file with VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY")
                return False
    
    def open_login_page(self):
        """Open the login page in the default browser"""
        print("\n🌐 Opening login page in your default browser...")
        login_url = f"{self.frontend_url}/login"
        
        try:
            webbrowser.open(login_url)
            print(f"✅ Opened {login_url}")
            return True
        except Exception as e:
            print(f"❌ Failed to open browser: {e}")
            print(f"💡 Please manually open: {login_url}")
            return False
    
    def provide_manual_test_instructions(self):
        """Provide step-by-step manual testing instructions"""
        print("\n" + "="*60)
        print("📋 MANUAL GOOGLE OAUTH TEST INSTRUCTIONS")
        print("="*60)
        
        print("\n🔍 STEP 1: Verify Login Page")
        print("• Look for the 'Continue with Google' button on the login page")
        print("• The button should be visible and clickable")
        print("• Check that the page loads without any console errors")
        
        print("\n🖱️ STEP 2: Test Google OAuth Button")
        print("• Click the 'Continue with Google' button")
        print("• You should be redirected to Google's OAuth consent screen")
        print("• If you see an error, note the exact error message")
        
        print("\n🔐 STEP 3: Complete Google Authentication")
        print("• Sign in with your Google account")
        print("• Grant the requested permissions")
        print("• You should be redirected back to the application")
        
        print("\n✅ STEP 4: Verify Successful Login")
        print("• Check that you're logged in (user profile/avatar visible)")
        print("• Verify you're redirected to the dashboard or home page")
        print("• Check browser console for any errors")
        
        print("\n🧪 STEP 5: Test Registration Flow")
        print("• Log out and go to the registration page")
        print("• Click 'Continue with Google' on the register page")
        print("• Verify the same OAuth flow works for registration")
        
        print("\n" + "-"*60)
        print("🚨 COMMON ISSUES AND SOLUTIONS")
        print("-"*60)
        
        print("\n❌ 'Provider not enabled' error:")
        print("• Go to Supabase Dashboard > Auth > Providers")
        print("• Enable the Google provider")
        print("• Add your Google OAuth Client ID and Secret")
        
        print("\n❌ 'Redirect URI mismatch' error:")
        print("• Go to Google Cloud Console > APIs & Services > Credentials")
        print("• Add http://localhost:3000/auth/callback to authorized redirect URIs")
        print("• Also add your production domain when deploying")
        
        print("\n❌ 'OAuth consent screen' error:")
        print("• Go to Google Cloud Console > APIs & Services > OAuth consent screen")
        print("• Configure the consent screen with required information")
        print("• Add test users if in testing mode")
        
        print("\n❌ 'Invalid client' error:")
        print("• Verify Client ID and Secret are correctly set in Supabase")
        print("• Check that the Google Cloud project is active")
        print("• Ensure Google+ API is enabled (if required)")
        
        print("\n💡 DEBUGGING TIPS:")
        print("• Open browser developer tools (F12) to check console errors")
        print("• Check Supabase Auth logs in the dashboard")
        print("• Verify network requests in the Network tab")
        print("• Test with an incognito/private browser window")
        
    def run_manual_test(self):
        """Run the complete manual test flow"""
        print("🚀 Starting Manual Google OAuth Test for Cliper\n")
        
        # Check prerequisites
        if not self.check_servers_running():
            print("\n❌ Servers not running. Please start both frontend and backend servers.")
            return False
        
        if not self.check_supabase_config():
            print("\n❌ Supabase configuration incomplete.")
            return False
        
        # Open login page
        self.open_login_page()
        
        # Wait a moment for the page to load
        time.sleep(2)
        
        # Provide instructions
        self.provide_manual_test_instructions()
        
        print("\n" + "="*60)
        print("🎯 READY FOR MANUAL TESTING!")
        print("="*60)
        print("\nThe login page should now be open in your browser.")
        print("Follow the step-by-step instructions above to test Google OAuth.")
        print("\nPress Ctrl+C to exit this script when you're done testing.")
        
        # Keep the script running so user can refer to instructions
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n👋 Manual testing session ended. Thank you!")
            return True

if __name__ == "__main__":
    tester = ManualGoogleOAuthTester()
    try:
        tester.run_manual_test()
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)