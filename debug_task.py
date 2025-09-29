#!/usr/bin/env python3
"""
Debug script to check the generate_clips_task object
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.tasks import generate_clips_task
import inspect

def debug_task():
    """Debug the generate_clips_task object"""
    
    print("=== Task Object Debug ===")
    print(f"Task object: {generate_clips_task}")
    print(f"Task type: {type(generate_clips_task)}")
    print(f"Task name: {getattr(generate_clips_task, 'name', 'No name')}")
    print(f"Task bind: {getattr(generate_clips_task, 'bind', 'No bind')}")
    
    print("\n=== Task Signature ===")
    try:
        sig = inspect.signature(generate_clips_task)
        print(f"Signature: {sig}")
        print(f"Parameters: {list(sig.parameters.keys())}")
    except Exception as e:
        print(f"Error getting signature: {e}")
    
    print("\n=== Task Attributes ===")
    for attr in dir(generate_clips_task):
        if not attr.startswith('_'):
            try:
                value = getattr(generate_clips_task, attr)
                print(f"{attr}: {value}")
            except Exception as e:
                print(f"{attr}: Error - {e}")
    
    print("\n=== Testing Task Call ===")
    try:
        # Test the delay method signature
        delay_method = getattr(generate_clips_task, 'delay', None)
        if delay_method:
            print(f"Delay method: {delay_method}")
            delay_sig = inspect.signature(delay_method)
            print(f"Delay signature: {delay_sig}")
        else:
            print("No delay method found")
    except Exception as e:
        print(f"Error checking delay method: {e}")

if __name__ == "__main__":
    debug_task()