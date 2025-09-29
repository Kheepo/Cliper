#!/usr/bin/env python3
"""Test SMTP connection for email service."""

import asyncio
from dotenv import load_dotenv
from api.services.email_service import EmailService

async def test_smtp_connection():
    """Test SMTP connection."""
    # Load environment variables
    load_dotenv()
    
    # Initialize email service
    service = EmailService()
    
    print("=== Email Service SMTP Connection Test ===")
    print(f"Email service configured: {service.configured}")
    
    # Get configuration status
    status = service.get_configuration_status()
    print(f"Configuration status: {status}")
    
    if service.configured:
        print("\nTesting SMTP connection...")
        try:
            result = await service.test_smtp_connection()
            print(f"SMTP connection test result: {result}")
            
            if result.get('success'):
                print("✅ SMTP connection successful!")
            else:
                print(f"❌ SMTP connection failed: {result.get('error')}")
                
        except Exception as e:
            print(f"❌ SMTP connection test failed with exception: {e}")
    else:
        print("❌ Email service is not properly configured")

if __name__ == '__main__':
    asyncio.run(test_smtp_connection())