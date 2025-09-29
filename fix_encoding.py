#!/usr/bin/env python3

import codecs

# Read the file with problematic encoding
with open('tests/integration/test_production_scenarios.py', 'rb') as f:
    data = f.read()

# Write it back with proper UTF-8 encoding, replacing problematic characters
with open('tests/integration/test_production_scenarios.py', 'w', encoding='utf-8') as f:
    f.write(data.decode('utf-8', errors='replace'))

print("Fixed encoding issues in test_production_scenarios.py")