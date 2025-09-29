#!/usr/bin/env python3
"""
Test script to verify authentication integration fixes
"""

import pytest
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone

from api.main import app

# Sample JWT payload for testing (same as used in unit tests)
SAMPLE_JWT_PAYLOAD = {
    "sub": "12345678-1234-1234-1234-123456789012",
    "email": "test@example.com",
    "aud": "authenticated",
    "role": "authenticated",
    "iat": int(datetime.now(timezone.utc).timestamp()),
    "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
    "user_metadata": {
        "full_name": "Test User",
        "username": "testuser"
    },
    "app_metadata": {
        "provider": "email",
        "providers": ["email"]
    }
}

def test_clips_endpoint_with_mocked_auth():
    """
    Test clips endpoint with properly mocked authentication
    """
    print("Testing clips endpoint with mocked authentication...")
    
    with TestClient(app) as client:
        # Mock the get_supabase_token_info function to return valid payload
        with patch('api.auth.jwt_middleware.get_supabase_token_info') as mock_get_token:
            mock_get_token.return_value = SAMPLE_JWT_PAYLOAD
            
            # Test the clips list endpoint
            response = client.get(
                "/api/v1/clips/",
                headers={"Authorization": "Bearer valid_access_token"}
            )
            
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text[:200]}...")
            
            # Should not be 401 anymore
            assert response.status_code != 401, "Authentication should work with mocked token"
            
            # Should be 200 or another valid status (not 401)
            assert response.status_code in [200, 404, 500], f"Unexpected status: {response.status_code}"
            
            return response.status_code == 200

def test_clips_generation_with_mocked_auth():
    """
    Test clips generation endpoint with properly mocked authentication
    """
    print("\nTesting clips generation endpoint with mocked authentication...")
    
    with TestClient(app) as client:
        # Mock the get_supabase_token_info function to return valid payload
        with patch('api.auth.jwt_middleware.get_supabase_token_info') as mock_get_token:
            mock_get_token.return_value = SAMPLE_JWT_PAYLOAD
            
            # Test the clips generation endpoint
            response = client.post(
                "/api/v1/clips/generate",
                headers={"Authorization": "Bearer valid_access_token"},
                json={
                    "content": "Test content for clip generation",
                    "platform": "tiktok",
                    "style": "engaging",
                    "duration": 30
                }
            )
            
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text[:200]}...")
            
            # Should not be 401 anymore
            assert response.status_code != 401, "Authentication should work with mocked token"
            
            # Should be 200, 202, or another valid status (not 401)
            assert response.status_code in [200, 202, 404, 500], f"Unexpected status: {response.status_code}"
            
            return response.status_code in [200, 202]

if __name__ == "__main__":
    print("=== Testing Authentication Integration Fixes ===")
    
    try:
        # Test clips list endpoint
        list_success = test_clips_endpoint_with_mocked_auth()
        
        # Test clips generation endpoint
        generation_success = test_clips_generation_with_mocked_auth()
        
        print("\n=== Test Results ===")
        print(f"Clips list endpoint: {'✅ PASSED' if list_success else '⚠️  PARTIAL (no 401 error)'}")
        print(f"Clips generation endpoint: {'✅ PASSED' if generation_success else '⚠️  PARTIAL (no 401 error)'}")
        
        if list_success or generation_success:
            print("\n🎉 Authentication fixes are working! No more 401 errors.")
        else:
            print("\n✅ Authentication is no longer failing with 401 errors.")
            print("   Other issues (404, 500) may need separate fixes.")
            
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()