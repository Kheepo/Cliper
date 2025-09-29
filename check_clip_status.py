#!/usr/bin/env python3
"""
Quick script to check clip processing status
Usage: python check_clip_status.py [clip_id]
"""

import requests
import json
import sys
import time
import os
from datetime import datetime

API_BASE = "http://localhost:8001"

def check_clip_status(clip_id):
    """Check the status of a specific clip"""
    try:
        # Since the current API doesn't have a dedicated clips endpoint,
        # we'll show the clip ID and suggest checking the processing logs
        print(f"\n🎬 Clip Status Report")
        print(f"{'='*50}")
        print(f"Clip ID: {clip_id}")
        print(f"Status: PROCESSING (simulated)")
        print(f"⏳ The current API implementation uses simple clip generation.")
        print(f"📋 Check the API server logs for processing details.")
        print(f"📁 Generated clips should appear in the uploads/clips/ directory.")
        
        # Check if there are any files in the clips directory
        clips_dir = "uploads/clips"
        if os.path.exists(clips_dir):
            files = os.listdir(clips_dir)
            if files:
                print(f"\n📁 Found {len(files)} files in clips directory:")
                for file in files[:5]:  # Show first 5 files
                    print(f"   - {file}")
                if len(files) > 5:
                    print(f"   ... and {len(files) - 5} more files")
            else:
                print(f"\n📁 No files found in clips directory yet.")
        else:
            print(f"\n📁 Clips directory not found: {clips_dir}")
        
        return {"id": clip_id, "status": "processing", "message": "Check logs for details"}
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API server. Make sure it's running on port 8001.")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def list_all_clips():
    """List all clips in the system"""
    try:
        # Check the uploads/clips directory for generated files
        clips_dir = "uploads/clips"
        print(f"\n📋 Generated Clips Directory: {clips_dir}")
        print(f"{'='*80}")
        
        if os.path.exists(clips_dir):
            files = os.listdir(clips_dir)
            if files:
                print(f"Found {len(files)} clip files:")
                for i, file in enumerate(files, 1):
                    file_path = os.path.join(clips_dir, file)
                    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                    file_size_mb = file_size / (1024 * 1024)
                    
                    print(f"{i}. 📹 {file}")
                    print(f"   Size: {file_size_mb:.2f} MB")
                    if os.path.exists(file_path):
                        mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                        print(f"   Modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    print()
                
                return [{"file": f, "path": os.path.join(clips_dir, f)} for f in files]
            else:
                print("No clip files found yet.")
                print("💡 Generate some clips using the test interface!")
                return []
        else:
            print(f"Clips directory not found: {clips_dir}")
            print("💡 Directory will be created when first clips are generated.")
            return []
            
    except Exception as e:
        print(f"❌ Error listing clips: {e}")
        return None

def monitor_clip(clip_id, interval=5):
    """Monitor a clip with auto-refresh"""
    print(f"🔄 Monitoring clip {clip_id} (refreshing every {interval}s)")
    print("Press Ctrl+C to stop monitoring")
    
    try:
        while True:
            clip = check_clip_status(clip_id)
            
            if clip and clip['status'] in ['completed', 'failed']:
                print(f"\n🏁 Final status: {clip['status'].upper()}")
                break
            
            print(f"\n⏰ Next check in {interval} seconds...")
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped.")

def check_api_health():
    """Check if the API server is running"""
    try:
        response = requests.get(f"{API_BASE}/health")
        if response.status_code == 200:
            print("✅ API server is running")
            return True
        else:
            print(f"⚠️ API server responded with status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ API server is not running or not accessible")
        return False
    except Exception as e:
        print(f"❌ Error checking API health: {e}")
        return False

def main():
    print("🎬 Clip Status Checker")
    print(f"API Base: {API_BASE}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check API health first
    if not check_api_health():
        print("\n💡 Make sure your API server is running:")
        print("   python api/main.py --port 8001")
        return
    
    if len(sys.argv) > 1:
        clip_id = sys.argv[1]
        
        if clip_id == "all":
            list_all_clips()
        elif clip_id == "monitor":
            if len(sys.argv) > 2:
                monitor_clip(sys.argv[2])
            else:
                print("Usage: python check_clip_status.py monitor <clip_id>")
        else:
            check_clip_status(clip_id)
    else:
        # Default: check the current clip and list all
        current_clip_id = "eb1beb4b-ad4a-45a9-85d2-cfa5ff571ac7"
        print(f"\n🎯 Checking current clip: {current_clip_id}")
        check_clip_status(current_clip_id)
        
        print(f"\n" + "="*50)
        list_all_clips()
        
        print(f"\n💡 Usage examples:")
        print(f"   python check_clip_status.py <clip_id>")
        print(f"   python check_clip_status.py all")
        print(f"   python check_clip_status.py monitor <clip_id>")

if __name__ == "__main__":
    main()