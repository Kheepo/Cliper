#!/usr/bin/env python3
"""Debug import step by step."""

import sys
print(f"Python path: {sys.path}")
print("\n" + "="*50)

try:
    print("Step 1: Import os...")
    import os
    print("✓ os imported")
except Exception as e:
    print(f"✗ os failed: {e}")

try:
    print("Step 2: Import logging...")
    import logging
    print("✓ logging imported")
except Exception as e:
    print(f"✗ logging failed: {e}")

try:
    print("Step 3: Import api.core.config...")
    from api.core.config import get_settings
    print("✓ api.core.config imported")
except Exception as e:
    print(f"✗ api.core.config failed: {e}")

try:
    print("Step 4: Import api.core.exceptions...")
    from api.core.exceptions import EmailError
    print("✓ api.core.exceptions imported")
except Exception as e:
    print(f"✗ api.core.exceptions failed: {e}")

try:
    print("Step 5: Import jinja2...")
    from jinja2 import Environment, FileSystemLoader
    print("✓ jinja2 imported")
except Exception as e:
    print(f"✗ jinja2 failed: {e}")

try:
    print("Step 6: Import pathlib...")
    from pathlib import Path
    print("✓ pathlib imported")
except Exception as e:
    print(f"✗ pathlib failed: {e}")

try:
    print("Step 7: Import dataclasses...")
    from dataclasses import dataclass
    print("✓ dataclasses imported")
except Exception as e:
    print(f"✗ dataclasses failed: {e}")

try:
    print("Step 8: Import typing...")
    from typing import Dict, List, Optional, Any
    print("✓ typing imported")
except Exception as e:
    print(f"✗ typing failed: {e}")

try:
    print("Step 9: Import smtplib...")
    import smtplib
    print("✓ smtplib imported")
except Exception as e:
    print(f"✗ smtplib failed: {e}")

try:
    print("Step 10: Import email modules...")
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email import encoders
    print("✓ email modules imported")
except Exception as e:
    print(f"✗ email modules failed: {e}")

try:
    print("Step 11: Import enum...")
    from enum import Enum
    print("✓ enum imported")
except Exception as e:
    print(f"✗ enum failed: {e}")

print("\nNow trying to import the email service module directly...")
try:
    import api.services.email_service
    print("✓ api.services.email_service module imported successfully")
except Exception as e:
    print(f"✗ api.services.email_service module failed: {e}")
    import traceback
    traceback.print_exc()