#!/usr/bin/env python3
"""
Google OAuth Solution Implementation and Testing Script

This script implements and tests the complete solution for Google OAuth issues.
It verifies the configuration and provides step-by-step guidance.
"""

import os
import sys
import json
import requests
from datetime import datetime
from typing import Dict, List, Tuple

class GoogleOAuthSolutionImplementer:
    def __init__(self):
        # Load environment variables from .env file
        from dotenv import load_dotenv
        load_dotenv()
        
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_anon_key = os.getenv('SUPABASE_ANON_KEY')
        self.google_client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'environment_check': {},
            'supabase_config': {},
            'google_config': {},
            'solution_status': {},
            'next_steps': []
        }
    
    def check_environment_variables(self) -> bool:
        """Verify all required environment variables are present."""
        print("\n🔍 CHECKING ENVIRONMENT VARIABLES...")
        print("=" * 50)
        
        required_vars = {
            'SUPABASE_URL': self.supabase_url,
            'SUPABASE_ANON_KEY': self.supabase_anon_key,
            'GOOGLE_CLIENT_ID': self.google_client_id,
            'GOOGLE_CLIENT_SECRET': self.google_client_secret
        }
        
        all_present = True
        for var_name, var_value in required_vars.items():
            status = "✅ Present" if var_value else "❌ Missing"
            print(f"{var_name}: {status}")
            if var_value:
                # Show partial value for security
                if 'SECRET' in var_name or 'KEY' in var_name:
                    display_value = f"{var_value[:10]}...{var_value[-4:]}" if len(var_value) > 14 else "[HIDDEN]"
                else:
                    display_value = var_value
                print(f"  Value: {display_value}")
            else:
                all_present = False
        
        self.results['environment_check'] = {
            'all_variables_present': all_present,
            'missing_variables': [k for k, v in required_vars.items() if not v]
        }
        
        return all_present
    
    def test_supabase_auth_config(self) -> Dict:
        """Test Supabase authentication configuration."""
        print("\n🔧 TESTING SUPABASE AUTH CONFIGURATION...")
        print("=" * 50)
        
        if not self.supabase_url or not self.supabase_anon_key:
            print("❌ Missing Supabase configuration")
            return {'status': 'error', 'message': 'Missing Supabase credentials'}
        
        try:
            # Test Supabase auth endpoint
            auth_url = f"{self.supabase_url}/auth/v1/settings"
            headers = {
                'apikey': self.supabase_anon_key,
                'Authorization': f'Bearer {self.supabase_anon_key}'
            }
            
            response = requests.get(auth_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                settings = response.json()
                
                # Check if Google provider is enabled
                external_providers = settings.get('external', {})
                google_config = external_providers.get('google', {})
                google_enabled = google_config.get('enabled', False) if isinstance(google_config, dict) else False
                
                print(f"Supabase Auth Status: ✅ Connected")
                print(f"Google Provider Enabled: {'✅ Yes' if google_enabled else '❌ No'}")
                
                if google_enabled:
                    print("✅ Google OAuth is properly configured in Supabase!")
                else:
                    print("❌ CRITICAL: Google provider is NOT enabled in Supabase dashboard")
                    print("   👉 Go to Supabase Dashboard > Authentication > Providers")
                    print("   👉 Enable Google provider and add your credentials")
                
                self.results['supabase_config'] = {
                    'status': 'success',
                    'google_enabled': google_enabled,
                    'auth_endpoint_accessible': True
                }
                
                return {
                    'status': 'success',
                    'google_enabled': google_enabled,
                    'settings': settings
                }
            else:
                print(f"❌ Supabase Auth Error: {response.status_code}")
                return {'status': 'error', 'code': response.status_code}
                
        except Exception as e:
            print(f"❌ Supabase Connection Error: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def verify_google_oauth_config(self) -> Dict:
        """Verify Google OAuth configuration."""
        print("\n🔍 VERIFYING GOOGLE OAUTH CONFIGURATION...")
        print("=" * 50)
        
        if not self.google_client_id:
            print("❌ Missing Google Client ID")
            return {'status': 'error', 'message': 'Missing Google Client ID'}
        
        try:
            # Test Google OAuth discovery endpoint
            discovery_url = "https://accounts.google.com/.well-known/openid-configuration"
            response = requests.get(discovery_url, timeout=10)
            
            if response.status_code == 200:
                config = response.json()
                print("✅ Google OAuth Discovery: Accessible")
                print(f"   Authorization Endpoint: {config.get('authorization_endpoint')}")
                print(f"   Token Endpoint: {config.get('token_endpoint')}")
                
                # Verify client ID format
                if self.google_client_id.endswith('.apps.googleusercontent.com'):
                    print("✅ Google Client ID: Valid format")
                else:
                    print("❌ Google Client ID: Invalid format")
                
                self.results['google_config'] = {
                    'status': 'success',
                    'discovery_accessible': True,
                    'client_id_format_valid': self.google_client_id.endswith('.apps.googleusercontent.com')
                }
                
                return {'status': 'success', 'config': config}
            else:
                print(f"❌ Google OAuth Discovery Error: {response.status_code}")
                return {'status': 'error', 'code': response.status_code}
                
        except Exception as e:
            print(f"❌ Google OAuth Error: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def generate_solution_steps(self, supabase_result: Dict, google_result: Dict) -> List[str]:
        """Generate specific solution steps based on test results."""
        steps = []
        
        # Check Supabase Google provider status
        if supabase_result.get('status') == 'success':
            if not supabase_result.get('google_enabled', False):
                steps.extend([
                    "🚨 CRITICAL: Enable Google Provider in Supabase Dashboard",
                    "   1. Go to https://app.supabase.com/project/stzdywhbdovjojtqxmsd",
                    "   2. Navigate to Authentication > Providers",
                    "   3. Find 'Google' and toggle it to 'Enabled'",
                    "   4. Enter Client ID: 608018819675-9jc4kkgire3la6eqi0lq3321e55o13g1.apps.googleusercontent.com",
                    "   5. Enter Client Secret: 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",
                    "   6. Click 'Save'"
                ])
            else:
                steps.append("✅ Supabase Google provider is properly enabled")
        else:
            steps.append("❌ Fix Supabase connection issues first")
        
        # Check Google OAuth configuration
        if google_result.get('status') == 'success':
            steps.extend([
                "✅ Google OAuth endpoints are accessible",
                "🔧 Verify Google Cloud Console settings:",
                "   1. Go to https://console.cloud.google.com/",
                "   2. Navigate to APIs & Services > Credentials",
                "   3. Verify redirect URIs include:",
                "      - https://stzdywhbdovjojtqxmsd.supabase.co/auth/v1/callback",
                "      - http://localhost:3001/auth/callback",
                "   4. Verify JavaScript origins include:",
                "      - http://localhost:3001",
                "      - http://localhost:3000"
            ])
        else:
            steps.append("❌ Fix Google OAuth configuration issues")
        
        # Final testing steps
        steps.extend([
            "🧪 Test the complete OAuth flow:",
            "   1. Wait 5-10 minutes for changes to propagate",
            "   2. Clear browser cache and cookies",
            "   3. Test Google login in your application",
            "   4. Check browser console for any errors"
        ])
        
        return steps
    
    def run_complete_solution(self) -> Dict:
        """Run the complete solution implementation and testing."""
        print("\n🚀 GOOGLE OAUTH SOLUTION IMPLEMENTATION")
        print("=" * 60)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Step 1: Check environment
        env_ok = self.check_environment_variables()
        if not env_ok:
            print("\n❌ Environment variables are missing. Please check your .env file.")
            return self.results
        
        # Step 2: Test Supabase configuration
        supabase_result = self.test_supabase_auth_config()
        
        # Step 3: Verify Google OAuth configuration
        google_result = self.verify_google_oauth_config()
        
        # Step 4: Generate solution steps
        solution_steps = self.generate_solution_steps(supabase_result, google_result)
        
        # Step 5: Display results and next steps
        print("\n📋 SOLUTION IMPLEMENTATION STEPS")
        print("=" * 50)
        for i, step in enumerate(solution_steps, 1):
            print(f"{i}. {step}")
        
        # Update results
        self.results['solution_status'] = {
            'environment_ready': env_ok,
            'supabase_status': supabase_result.get('status'),
            'google_status': google_result.get('status'),
            'google_enabled_in_supabase': supabase_result.get('google_enabled', False)
        }
        self.results['next_steps'] = solution_steps
        
        # Final assessment
        print("\n🎯 FINAL ASSESSMENT")
        print("=" * 50)
        
        if (supabase_result.get('google_enabled', False) and 
            google_result.get('status') == 'success' and env_ok):
            print("✅ ALL SYSTEMS READY: Google OAuth should work correctly!")
            print("   Test your application's Google login functionality.")
        else:
            print("⚠️  CONFIGURATION INCOMPLETE: Follow the steps above to complete setup.")
            if not supabase_result.get('google_enabled', False):
                print("   🚨 PRIORITY: Enable Google provider in Supabase dashboard")
        
        return self.results
    
    def save_results(self, filename: str = "oauth_solution_results.json"):
        """Save results to a JSON file."""
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\n💾 Results saved to: {filename}")

def main():
    """Main execution function."""
    implementer = GoogleOAuthSolutionImplementer()
    
    try:
        results = implementer.run_complete_solution()
        implementer.save_results()
        
        # Return appropriate exit code
        if results['solution_status'].get('google_enabled_in_supabase', False):
            print("\n🎉 SUCCESS: Solution implementation complete!")
            sys.exit(0)
        else:
            print("\n⚠️  INCOMPLETE: Manual steps required in Supabase dashboard.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Operation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()