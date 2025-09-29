#!/usr/bin/env python3
"""
Test script to verify job processing system
"""

import asyncio
import aiohttp
import json
import os
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

API_BASE_URL = "http://localhost:8001"

async def test_job_processing_directly():
    """Test job processing by creating jobs directly in the database"""
    print("🧪 Testing job processing system directly...")
    
    try:
        # Import after adding to path
        from api.utils.supabase_client import get_supabase_admin_client
        from api.services.job_processor import job_processor
        
        supabase = get_supabase_admin_client()
        
        # Create a test job directly in the database
        print("\n📝 Creating test job in database...")
        job_data = {
            "user_id": "test-user-123",
            "job_type": "test",
            "status": "pending",
            "title": "Test Job Processing",
            "description": "Testing job processing system",
            "video_url": "https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4"
        }
        
        result = supabase.table("jobs").insert(job_data).execute()
        if not result.data:
            print("❌ Failed to create test job")
            return
        
        job_id = result.data[0]["id"]
        print(f"✅ Test job created with ID: {job_id}")
        
        # Test adding job to queue
        print(f"\n🔄 Adding job {job_id} to processing queue...")
        await job_processor.add_job_to_queue(job_id)
        print(f"✅ Job added to queue successfully")
        
        # Monitor job status
        print(f"\n👀 Monitoring job status...")
        for attempt in range(10):  # Check 10 times
            try:
                result = supabase.table("jobs").select("*").eq("id", job_id).execute()
                if result.data:
                    job = result.data[0]
                    status = job.get('status', 'unknown')
                    print(f"📊 Job status (attempt {attempt + 1}): {status}")
                    
                    if status in ['completed', 'failed']:
                        print(f"🏁 Job finished with status: {status}")
                        if status == 'completed':
                            print(f"✅ Job completed successfully!")
                            print(f"📄 Job details: {json.dumps(job, indent=2, default=str)}")
                        else:
                            error_msg = job.get('error_message', 'Unknown error')
                            print(f"❌ Job failed: {error_msg}")
                        break
                    elif status == 'processing':
                        print(f"⏳ Job is being processed...")
                    elif status == 'pending':
                        print(f"⏸️ Job is pending...")
                else:
                    print(f"❌ Could not find job {job_id}")
                    
            except Exception as e:
                print(f"❌ Error checking job status: {e}")
            
            if attempt < 9:  # Don't wait after the last attempt
                await asyncio.sleep(3)  # Wait 3 seconds between checks
        
        # Cleanup test job
        print(f"\n🧹 Cleaning up test job...")
        try:
            supabase.table("jobs").delete().eq("id", job_id).execute()
            print(f"✅ Test job cleaned up")
        except Exception as e:
            print(f"⚠️ Could not cleanup test job: {e}")
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

async def test_health_endpoints():
    """Test health and status endpoints"""
    print("\n🏥 Testing health endpoints...")
    
    endpoints = [
        "/health",
        "/api/health",
        "/api/status"
    ]
    
    async with aiohttp.ClientSession() as session:
        for endpoint in endpoints:
            try:
                async with session.get(f"{API_BASE_URL}{endpoint}") as resp:
                    print(f"📡 {endpoint}: {resp.status}")
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"   Response: {json.dumps(data, indent=2)}")
            except Exception as e:
                print(f"❌ Error testing {endpoint}: {e}")

async def test_job_queue_functionality():
    """Test the job queue functionality directly"""
    print("\n🔧 Testing job queue functionality...")
    
    try:
        from api.services.job_processor import job_processor
        
        # Test queue operations
        print("📥 Testing queue operations...")
        
        # Add some test job IDs to the queue
        test_job_ids = ["test-job-1", "test-job-2", "test-job-3"]
        
        for job_id in test_job_ids:
            await job_processor.add_job_to_queue(job_id)
            print(f"✅ Added {job_id} to queue")
        
        print(f"📊 Queue size: {job_processor.job_queue.qsize()}")
        print(f"🔄 Queue processing active: {job_processor.queue_processing}")
        
        # Wait a bit to see if queue processing works
        await asyncio.sleep(5)
        
        print(f"📊 Queue size after processing: {job_processor.job_queue.qsize()}")
        
    except Exception as e:
        print(f"❌ Queue test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Starting job processing tests...")
    print(f"🎯 Target API: {API_BASE_URL}")
    
    asyncio.run(test_health_endpoints())
    asyncio.run(test_job_queue_functionality())
    asyncio.run(test_job_processing_directly())
    
    print("\n🎉 Test completed!")