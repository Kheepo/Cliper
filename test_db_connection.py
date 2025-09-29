#!/usr/bin/env python3
"""Test database connection with different approaches."""

import os
import psycopg2
from sqlalchemy import create_engine
from dotenv import load_dotenv
import urllib.parse

# Load environment variables
load_dotenv()

def test_direct_psycopg2():
    """Test direct psycopg2 connection."""
    print("Testing direct psycopg2 connection...")
    try:
        # Get credentials from environment
        supabase_url = os.getenv("SUPABASE_URL")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        # Extract project ref from URL
        project_ref = supabase_url.split("//")[1].split(".")[0]
        
        # Try different connection approaches
        connection_configs = [
            {
                "name": "Original DATABASE_URL",
                "conn_str": os.getenv("DATABASE_URL")
            },
            {
                "name": "URL-encoded password",
                "conn_str": f"postgresql://postgres.{project_ref}:{urllib.parse.quote('Cliper2025!', safe='')}@aws-0-us-west-1.pooler.supabase.com:6543/postgres"
            },
            {
                "name": "Direct connection params",
                "params": {
                    "host": "aws-0-us-west-1.pooler.supabase.com",
                    "port": 6543,
                    "database": "postgres",
                    "user": f"postgres.{project_ref}",
                    "password": "Cliper2025!"
                }
            }
        ]
        
        for config in connection_configs:
            print(f"\nTrying {config['name']}...")
            try:
                if 'conn_str' in config:
                    conn = psycopg2.connect(config['conn_str'])
                else:
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

def test_sqlalchemy():
    """Test SQLAlchemy connection."""
    print("\nTesting SQLAlchemy connection...")
    try:
        database_url = os.getenv("DATABASE_URL")
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_timeout=10,
            connect_args={"connect_timeout": 10}
        )
        
        with engine.connect() as connection:
            result = connection.execute("SELECT 1")
            print(f"✓ SQLAlchemy connection successful! Result: {result.fetchone()}")
            return True
            
    except Exception as e:
        print(f"✗ SQLAlchemy connection failed: {e}")
    
    return False

if __name__ == "__main__":
    print("Database Connection Test")
    print("=" * 50)
    
    # Show current environment
    print(f"SUPABASE_URL: {os.getenv('SUPABASE_URL')}")
    print(f"DATABASE_URL: {os.getenv('DATABASE_URL')}")
    print("=" * 50)
    
    success = test_direct_psycopg2()
    if success:
        test_sqlalchemy()
    else:
        print("\nSkipping SQLAlchemy test due to psycopg2 failures.")
    
    print("\nTest completed.")