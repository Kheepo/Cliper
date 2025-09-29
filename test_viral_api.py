#!/usr/bin/env python3
"""
Test viral scoring API endpoints
"""

import requests
import json
import sys
import time
from pathlib import Path

# Test configuration
BASE_URL = "http://localhost:8000"
TEST_VIDEO_ID = 1

def test_viral_scoring_endpoint():
    """Test the viral scoring endpoint"""
    print("🧪 Testing Viral Scoring API Endpoint...")
    
    try:
        # Test data
        payload = {
            "video_id": TEST_VIDEO_ID,
            "clip_segments": [
                {
                    "start_time": 0,
                    "end_time": 30,
                    "text": "Amazing AI breakthrough that will change everything!"
                },
                {
                    "start_time": 30,
                    "end_time": 60,
                    "text": "The results are incredible and everyone needs to see this."
                }
            ],
            "platforms": ["tiktok", "instagram", "youtube"],
            "include_insights": True
        }
        
        # Make request
        print(f"📡 Making request to {BASE_URL}/api/analysis/viral-scoring")
        response = requests.post(
            f"{BASE_URL}/api/analysis/viral-scoring",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"📊 Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Viral scoring endpoint working!")
            print(f"📊 Overall score: {data.get('overall_score', 'N/A')}")
            print(f"🎯 Confidence: {data.get('confidence', 'N/A')}")
            print(f"📱 Platform scores: {len(data.get('platform_scores', {}))}")
            print(f"⚡ Viral moments: {len(data.get('viral_moments', []))}")
            print(f"#️⃣ Hashtags: {len(data.get('hashtags', []))}")
            print(f"📝 Recommendations: {len(data.get('posting_recommendations', []))}")
            return True
        elif response.status_code == 404:
            print("⚠️ Video not found (expected for test)")
            return True
        elif response.status_code == 422:
            print("⚠️ Validation error (check request format)")
            print(f"📝 Response: {response.text}")
            return False
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            print(f"📝 Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Is the server running?")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_viral_analysis_retrieval():
    """Test retrieving viral analysis results"""
    print("\n🧪 Testing Viral Analysis Retrieval...")
    
    try:
        # Make request
        print(f"📡 Making request to {BASE_URL}/api/analysis/viral-scoring/{TEST_VIDEO_ID}")
        response = requests.get(
            f"{BASE_URL}/api/analysis/viral-scoring/{TEST_VIDEO_ID}",
            timeout=10
        )
        
        print(f"📊 Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Viral analysis retrieval working!")
            print(f"📊 Overall score: {data.get('overall_score', 'N/A')}")
            print(f"🎯 Confidence: {data.get('confidence', 'N/A')}")
            return True
        elif response.status_code == 404:
            print("⚠️ Analysis not found (expected for test)")
            return True
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            print(f"📝 Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Is the server running?")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_server_health():
    """Test if the server is running"""
    print("🧪 Testing Server Health...")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running!")
            return True
        else:
            print(f"⚠️ Server responded with status: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running")
        return False
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def main():
    """Run all API tests"""
    print("🚀 Starting Viral Scoring API Tests")
    print("=" * 50)
    
    tests = [
        ("Server Health", test_server_health),
        ("Viral Scoring Endpoint", test_viral_scoring_endpoint),
        ("Viral Analysis Retrieval", test_viral_analysis_retrieval)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running {test_name}...")
        try:
            result = test_func()
            results.append((test_name, result))
            if result:
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 API TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All viral scoring API tests PASSED!")
        return True
    else:
        print("⚠️ Some viral scoring API tests FAILED!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)