#!/usr/bin/env python3
"""Simple test to check imports."""

try:
    print("Testing api.services.email_service import...")
    from api.services.email_service import EmailService
    print("✓ EmailService imported successfully")
except ImportError as e:
    print(f"✗ Failed to import EmailService: {e}")

try:
    print("Testing api.core.config import...")
    from api.core.config import get_settings
    print("✓ get_settings imported successfully")
except ImportError as e:
    print(f"✗ Failed to import get_settings: {e}")

try:
    print("Testing api.core.exceptions import...")
    from api.core.exceptions import EmailError
    print("✓ EmailError imported successfully")
except ImportError as e:
    print(f"✗ Failed to import EmailError: {e}")

print("Import test completed.")