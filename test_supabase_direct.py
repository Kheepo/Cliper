#!/usr/bin/env python3
"""Test Supabase connection using direct connection and REST API."""

import os
import requests
from dotenv import load_dotenv
from supabase import create_client, Client
import psycopg2

# Load environment variables
load_dotenv()

def test_supabase_rest_api():
    """Test Supabase REST API connection."""
    print("Testing Supabase REST API connection...")
    try:
        url = os.getenv("SUPABASE_URL")
        anon_key = os.getenv("SUPABASE_ANON_KEY")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        # Test with anon key
        headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(f"{url}/rest/v1/users?select=count", headers=headers)
        print(f"✓ REST API (anon) response: {response.status_code}")
        
        # Test with service role key
        headers["apikey"] = service_role_key
        headers["Authorization"] = f"Bearer {service_role_key}"
        
        response = requests.get(f"{url}/rest/v1/users?select=count", headers=headers)
        print(f"✓ REST API (service_role) response: {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"✗ REST API test failed: {e}")
        return False

def test_supabase_python_client():
    """Test Supabase Python client."""
    print("\nTesting Supabase Python client...")
    try:
        url = os.getenv("SUPABASE_URL")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        supabase: Client = create_client(url, service_role_key)
        
        # Test a simple query
        result = supabase.table("users").select("count").execute()
        print(f"✓ Supabase client connection successful! Users count query executed.")
        print(f"  Response: {result}")
        
        return True
        
    except Exception as e:
        print(f"✗ Supabase client test failed: {e}")
        return False

def test_direct_postgres_connection():
    """Test direct PostgreSQL connection (non-pooler)."""
    print("\nTesting direct PostgreSQL connection...")
    try:
        # Extract project ref from Supabase URL
        supabase_url = os.getenv("SUPABASE_URL")
        project_ref = supabase_url.split("//")[1].split(".")[0]
        
        # Try direct connection to PostgreSQL (port 5432)
        direct_configs = [
            {
                "name": "Direct PostgreSQL (port 5432)",
                "params": {
                    "host": f"db.{project_ref}.supabase.co",
                    "port": 5432,
                    "database": "postgres",
                    "user": "postgres",
                    "password": "Cliper2025!"
                }
            },
            {
                "name": "Alternative direct connection",
                "params": {
                    "host": f"{project_ref}.supabase.co",
                    "port": 5432,
                    "database": "postgres",
                    "user": "postgres",
                    "password": "Cliper2025!"
                }
            }
        ]
        
        for config in direct_configs:
            print(f"\nTrying {config['name']}...")
            print(f"  Host: {config['params']['host']}")
            try:
                conn = psycopg2.connect(**config['params'])
                cursor = conn.cursor()
                cursor.execute("SELECT version();")
                version = cursor.fetchone()
                print(f"✓ Success! PostgreSQL version: {version[0][:50]}...")
                
                cursor.close()
                conn.close()
                return True
                
            except Exception as e:
                print(f"✗ Failed: {e}")
                
    except Exception as e:
        print(f"✗ Configuration error: {e}")
    
    return False

def show_environment_info():
    """Show current environment configuration."""
    print("Environment Configuration:")
    print("=" * 50)
    
    supabase_url = os.getenv("SUPABASE_URL")
    if supabase_url:
        project_ref = supabase_url.split("//")[1].split(".")[0]
        print(f"SUPABASE_URL: {supabase_url}")
        print(f"Project Reference: {project_ref}")
    
    print(f"DATABASE_URL: {os.getenv('DATABASE_URL')}")
    print(f"SUPABASE_ANON_KEY: {os.getenv('SUPABASE_ANON_KEY')[:20]}...")
    print(f"SUPABASE_SERVICE_ROLE_KEY: {os.getenv('SUPABASE_SERVICE_ROLE_KEY')[:20]}...")
    print("=" * 50)

if __name__ == "__main__":
    print("Comprehensive Supabase Connection Test")
    print("=" * 50)
    
    show_environment_info()
    
    # Run all tests
    rest_success = test_supabase_rest_api()
    client_success = test_supabase_python_client()
    direct_success = test_direct_postgres_connection()
    
    print("\n" + "=" * 50)
    print("Test Summary:")
    print(f"REST API: {'✓ PASS' if rest_success else '✗ FAIL'}")
    print(f"Python Client: {'✓ PASS' if client_success else '✗ FAIL'}")
    print(f"Direct PostgreSQL: {'✓ PASS' if direct_success else '✗ FAIL'}")
    print("=" * 50)