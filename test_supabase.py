#!/usr/bin/env python3
"""Test Supabase connection and basic operations."""

import sys
import os
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from api.utils.supabase_client import get_supabase_client, get_supabase_admin_client
except ImportError as e:
    print(f"Import error: {e}")
    print("Current working directory:", os.getcwd())
    print("Python path:", sys.path)
    sys.exit(1)

import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_supabase_connection():
    """Test basic Supabase connection."""
    print("Testing Supabase connection...")
    
    # Test anon client
    print("\n1. Testing anon client...")
    client = get_supabase_client()
    if client:
        print("✓ Anon client created successfully")
        try:
            # Test a simple query
            response = client.table('users').select('id').limit(1).execute()
            print(f"✓ Anon client query successful: {len(response.data)} rows")
        except Exception as e:
            print(f"✗ Anon client query failed: {e}")
    else:
        print("✗ Failed to create anon client")
    
    # Test admin client
    print("\n2. Testing admin client...")
    admin_client = get_supabase_admin_client()
    if admin_client:
        print("✓ Admin client created successfully")
        try:
            # Test admin operations
            response = admin_client.table('users').select('id').limit(1).execute()
            print(f"✓ Admin client query successful: {len(response.data)} rows")
            
            # Test auth admin operations
            auth_response = admin_client.auth.admin.list_users()
            if hasattr(auth_response, 'users'):
                print(f"✓ Auth admin query successful: {len(auth_response.users)} users")
            elif isinstance(auth_response, list):
                print(f"✓ Auth admin query successful: {len(auth_response)} users")
            else:
                print(f"✓ Auth admin query successful: {type(auth_response)}")
        except Exception as e:
            print(f"✗ Admin client query failed: {e}")
    else:
        print("✗ Failed to create admin client")

def test_user_registration():
    """Test user registration process."""
    print("\n3. Testing user registration process...")
    
    admin_client = get_supabase_admin_client()
    if not admin_client:
        print("✗ Cannot test registration without admin client")
        return
    
    test_email = "test_connection@example.com"
    
    try:
        # Check if test user already exists
        print(f"Checking if {test_email} already exists...")
        auth_users_response = admin_client.auth.admin.list_users()
        
        # Handle different response formats
        if hasattr(auth_users_response, 'users'):
            auth_users = auth_users_response.users
        elif isinstance(auth_users_response, list):
            auth_users = auth_users_response
        else:
            print(f"Unexpected auth users response format: {type(auth_users_response)}")
            return
        
        existing_user = None
        for user in auth_users:
            if hasattr(user, 'email') and user.email == test_email:
                existing_user = user
                break
        
        if existing_user:
            print(f"Test user already exists: {existing_user.id}")
            # Clean up existing test user
            admin_client.auth.admin.delete_user(existing_user.id)
            print("Cleaned up existing test user")
        
        # Try to create a test user
        print(f"Creating test user: {test_email}")
        auth_response = admin_client.auth.admin.create_user({
            "email": test_email,
            "password": "TestPassword123!",
            "email_confirm": True
        })
        
        if auth_response.user:
            print(f"✓ Test user created successfully: {auth_response.user.id}")
            
            # Clean up test user
            admin_client.auth.admin.delete_user(auth_response.user.id)
            print("✓ Test user cleaned up")
        else:
            print("✗ Failed to create test user")
            
    except Exception as e:
        print(f"✗ Registration test failed: {e}")

if __name__ == "__main__":
    test_supabase_connection()
    test_user_registration()
    print("\nTest completed.")