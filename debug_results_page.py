#!/usr/bin/env python3
"""
Debug script to examine the Results page content in detail
"""

import requests
import re

def debug_results_page():
    """Debug the Results page to see what content is being returned"""
    print("🔍 Debugging Results Page Content")
    print("=" * 50)
    
    try:
        # Get the Results page content
        response = requests.get("http://localhost:3000/results", timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type', 'N/A')}")
        print(f"Content-Length: {len(response.text)} characters")
        
        content = response.text
        
        # Check if it's HTML
        if "<!DOCTYPE html>" in content or "<html" in content:
            print("✅ Response is HTML")
            
            # Look for key elements
            if "<title>" in content:
                title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
                if title_match:
                    print(f"   Page Title: {title_match.group(1)}")
            
            # Check for React app mounting
            if 'id="root"' in content:
                print("✅ React root element found")
            
            # Check for script tags (React bundles)
            script_count = content.count('<script')
            print(f"   Script tags: {script_count}")
            
            # Check for specific content
            if "results" in content.lower():
                print("✅ 'Results' text found in content")
            
            if "error" in content.lower():
                print("⚠️  'Error' text found in content")
            
            if "loading" in content.lower():
                print("⚠️  'Loading' text found in content")
            
            # Check for authentication-related content
            if "login" in content.lower():
                print("⚠️  'Login' text found - might be redirecting")
            
            if "auth" in content.lower():
                print("⚠️  'Auth' text found")
            
            # Look for React Router or navigation
            if "react-router" in content.lower() or "router" in content.lower():
                print("✅ Router-related content found")
            
            # Check for empty body or minimal content
            body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
            if body_match:
                body_content = body_match.group(1).strip()
                # Remove script and style tags for analysis
                clean_body = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
                clean_body = re.sub(r'<[^>]+>', '', clean_body).strip()
                
                if len(clean_body) < 50:
                    print(f"⚠️  Body has minimal text content: '{clean_body[:100]}...'")
                else:
                    print(f"✅ Body has substantial content ({len(clean_body)} chars)")
            
            # Show first 500 characters for inspection
            print("\n📄 First 500 characters of content:")
            print("-" * 50)
            print(content[:500])
            print("-" * 50)
            
            # Show last 200 characters
            print("\n📄 Last 200 characters of content:")
            print("-" * 50)
            print(content[-200:])
            print("-" * 50)
            
        else:
            print("❌ Response is not HTML")
            print(f"Content preview: {content[:200]}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to get Results page: {e}")
        return False

def test_other_pages_for_comparison():
    """Test other pages to compare their content structure"""
    print("\n🔍 Testing Other Pages for Comparison")
    print("=" * 50)
    
    pages = [
        ("/", "Home"),
        ("/login", "Login"),
        ("/register", "Register")
    ]
    
    for path, name in pages:
        try:
            response = requests.get(f"http://localhost:3000{path}", timeout=5)
            content = response.text
            
            # Check title
            title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
            title = title_match.group(1) if title_match else "No title"
            
            # Check body content length
            body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
            body_length = len(body_match.group(1)) if body_match else 0
            
            print(f"   {name} page: Title='{title}', Body={body_length} chars")
            
        except requests.exceptions.RequestException as e:
            print(f"   {name} page: Failed - {e}")

if __name__ == "__main__":
    debug_results_page()
    test_other_pages_for_comparison()
    
    print("\n💡 Analysis Complete")
    print("   If the Results page shows minimal content or redirects,")
    print("   it might be due to authentication state not being properly")
    print("   maintained in the frontend React application.")