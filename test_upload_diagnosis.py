#!/usr/bin/env python3
"""
Comprehensive Upload Diagnosis Tool
Diagnoses video upload failures and identifies bottlenecks
"""

import asyncio
import aiohttp
import json
import time
import os
import tempfile
from datetime import datetime
from typing import Dict, List, Any
import websockets
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class UploadDiagnostics:
    def __init__(self):
        self.base_url = "http://localhost:8001"
        self.ws_url = "ws://localhost:8001"
        self.results = []
        
    async def run_all_diagnostics(self):
        """Run comprehensive upload diagnostics"""
        print("🔍 Starting Upload Diagnostics...")
        print("=" * 50)
        
        # Test 1: Basic connectivity
        await self.test_basic_connectivity()
        
        # Test 2: File upload endpoint structure
        await self.test_upload_endpoint_structure()
        
        # Test 3: WebSocket connectivity
        await self.test_websocket_connectivity()
        
        # Test 4: Job processing pipeline
        await self.test_job_processing_pipeline()
        
        # Test 5: Progress tracking
        await self.test_progress_tracking()
        
        # Test 6: Resource monitoring
        await self.test_resource_monitoring()
        
        # Test 7: Error handling
        await self.test_error_handling()
        
        # Test 8: Timeout scenarios
        await self.test_timeout_scenarios()
        
        # Generate report
        self.generate_report()
        
    async def test_basic_connectivity(self):
        """Test basic API connectivity"""
        print("\n📡 Testing Basic Connectivity...")
        
        try:
            async with aiohttp.ClientSession() as session:
                # Test health endpoint
                async with session.get(f"{self.base_url}/health") as response:
                    if response.status == 200:
                        self.log_success("Health endpoint", "✅ Responsive")
                    else:
                        self.log_error("Health endpoint", f"❌ Status {response.status}")
                
                # Test detailed health
                async with session.get(f"{self.base_url}/health/detailed") as response:
                    if response.status == 200:
                        data = await response.json()
                        self.log_success("Detailed health", f"✅ Status: {data.get('status', 'unknown')}")
                    else:
                        self.log_error("Detailed health", f"❌ Status {response.status}")
                
                # Test API info
                async with session.get(f"{self.base_url}/api/info") as response:
                    if response.status == 200:
                        data = await response.json()
                        features = data.get('features', {})
                        self.log_success("API info", f"✅ Video upload: {features.get('video_upload', False)}")
                    else:
                        self.log_error("API info", f"❌ Status {response.status}")
                        
        except Exception as e:
            self.log_error("Basic connectivity", f"❌ Connection failed: {str(e)}")
    
    async def test_upload_endpoint_structure(self):
        """Test upload endpoint structure and requirements"""
        print("\n📤 Testing Upload Endpoint Structure...")
        
        try:
            async with aiohttp.ClientSession() as session:
                # Test upload endpoint without auth (should get 403)
                test_data = aiohttp.FormData()
                test_data.add_field('user_id', 'test_user')
                
                async with session.post(f"{self.base_url}/api/videos/upload", data=test_data) as response:
                    if response.status == 403:
                        self.log_success("Upload auth", "✅ Properly requires authentication")
                    elif response.status == 422:
                        self.log_warning("Upload auth", "⚠️ Validation error (expected for test)")
                    else:
                        self.log_error("Upload auth", f"❌ Unexpected status {response.status}")
                
                # Test process URL endpoint
                async with session.post(f"{self.base_url}/api/videos/process-url", 
                                       json={"url": "https://example.com/test.mp4"}) as response:
                    if response.status == 403:
                        self.log_success("Process URL auth", "✅ Properly requires authentication")
                    elif response.status == 405:
                        self.log_warning("Process URL auth", "⚠️ Method not allowed (check endpoint)")
                    else:
                        self.log_error("Process URL auth", f"❌ Unexpected status {response.status}")
                        
        except Exception as e:
            self.log_error("Upload endpoint structure", f"❌ Test failed: {str(e)}")
    
    async def test_websocket_connectivity(self):
        """Test WebSocket connectivity and job subscription"""
        print("\n🔌 Testing WebSocket Connectivity...")
        
        try:
            # Test general WebSocket endpoint
            uri = f"{self.ws_url}/ws/test_client_123"
            
            async with websockets.connect(uri) as websocket:
                self.log_success("WebSocket connection", "✅ Connected successfully")
                
                # Test ping/pong
                ping_msg = json.dumps({"type": "ping"})
                await websocket.send(ping_msg)
                
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(response)
                    if data.get("type") == "pong":
                        self.log_success("WebSocket ping/pong", "✅ Ping/pong working")
                    else:
                        self.log_warning("WebSocket ping/pong", f"⚠️ Unexpected response: {data}")
                except asyncio.TimeoutError:
                    self.log_error("WebSocket ping/pong", "❌ Ping/pong timeout")
                
                # Test job subscription
                subscribe_msg = json.dumps({
                    "type": "subscribe_job",
                    "job_id": "test_job_123"
                })
                await websocket.send(subscribe_msg)
                
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(response)
                    if "subscribed" in data.get("message", "").lower():
                        self.log_success("Job subscription", "✅ Job subscription working")
                    else:
                        self.log_warning("Job subscription", f"⚠️ Unexpected response: {data}")
                except asyncio.TimeoutError:
                    self.log_error("Job subscription", "❌ Subscription timeout")
                    
        except Exception as e:
            self.log_error("WebSocket connectivity", f"❌ Connection failed: {str(e)}")
    
    async def test_job_processing_pipeline(self):
        """Test job processing pipeline components"""
        print("\n⚙️ Testing Job Processing Pipeline...")
        
        try:
            # Test Supabase connection
            from api.utils.supabase_client import get_supabase_admin_client
            
            supabase = get_supabase_admin_client()
            if supabase:
                self.log_success("Supabase connection", "✅ Admin client created")
                
                # Test database connectivity
                try:
                    result = supabase.table('jobs').select('id').limit(1).execute()
                    self.log_success("Database connectivity", "✅ Can query jobs table")
                except Exception as db_error:
                    self.log_error("Database connectivity", f"❌ Query failed: {str(db_error)}")
            else:
                self.log_error("Supabase connection", "❌ Failed to create admin client")
            
            # Test job processor
            try:
                from api.services.job_processor import JobProcessor
                processor = JobProcessor()
                self.log_success("Job processor", "✅ Job processor initialized")
                
                # Check processing queue
                queue_size = processor.job_queue.qsize()
                self.log_info("Processing queue", f"📊 Queue size: {queue_size}")
                
            except Exception as proc_error:
                self.log_error("Job processor", f"❌ Initialization failed: {str(proc_error)}")
            
            # Test AI analyzer
            try:
                from api.services.ai_analyzer import ai_analyzer
                self.log_success("AI analyzer", "✅ AI analyzer available")
                
                # Check OpenAI API key
                if os.getenv('OPENAI_API_KEY'):
                    self.log_success("OpenAI API key", "✅ API key configured")
                else:
                    self.log_warning("OpenAI API key", "⚠️ API key not found")
                    
            except Exception as ai_error:
                self.log_error("AI analyzer", f"❌ Import failed: {str(ai_error)}")
                
        except Exception as e:
            self.log_error("Job processing pipeline", f"❌ Test failed: {str(e)}")
    
    async def test_progress_tracking(self):
        """Test progress tracking mechanisms"""
        print("\n📊 Testing Progress Tracking...")
        
        try:
            # Test broadcast function
            from api.main import broadcast_job_update
            
            test_job_id = "test_progress_123"
            
            # Test progress update broadcast
            await broadcast_job_update(test_job_id, "processing", 50, "Testing progress")
            self.log_success("Progress broadcast", "✅ Broadcast function works")
            
            # Test WebSocket manager
            from api.main import manager
            
            active_connections = len(manager.active_connections)
            job_subscribers = len(manager.job_subscribers)
            
            self.log_info("WebSocket manager", f"📊 Active connections: {active_connections}")
            self.log_info("WebSocket manager", f"📊 Job subscribers: {job_subscribers}")
            
        except Exception as e:
            self.log_error("Progress tracking", f"❌ Test failed: {str(e)}")
    
    async def test_resource_monitoring(self):
        """Test resource monitoring and limits"""
        print("\n💾 Testing Resource Monitoring...")
        
        try:
            # Test system metrics
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/metrics") as response:
                    if response.status == 200:
                        data = await response.json()
                        self.log_success("System metrics", "✅ Metrics endpoint available")
                        
                        # Check for key metrics
                        if 'memory_usage' in str(data):
                            self.log_info("Memory monitoring", "📊 Memory usage tracked")
                        if 'cpu_usage' in str(data):
                            self.log_info("CPU monitoring", "📊 CPU usage tracked")
                    else:
                        self.log_warning("System metrics", f"⚠️ Status {response.status}")
            
            # Test file size limits
            max_file_size = os.getenv('MAX_FILE_SIZE_MB', '100')
            self.log_info("File size limit", f"📊 Max file size: {max_file_size}MB")
            
            # Test upload directory
            upload_dir = "uploads"
            if os.path.exists(upload_dir):
                self.log_success("Upload directory", "✅ Upload directory exists")
                
                # Check disk space
                import shutil
                total, used, free = shutil.disk_usage(upload_dir)
                free_gb = free // (1024**3)
                self.log_info("Disk space", f"📊 Free space: {free_gb}GB")
            else:
                self.log_warning("Upload directory", "⚠️ Upload directory not found")
                
        except Exception as e:
            self.log_error("Resource monitoring", f"❌ Test failed: {str(e)}")
    
    async def test_error_handling(self):
        """Test error handling mechanisms"""
        print("\n🚨 Testing Error Handling...")
        
        try:
            # Test invalid file upload
            async with aiohttp.ClientSession() as session:
                # Test with invalid file type
                test_data = aiohttp.FormData()
                test_data.add_field('file', b'invalid content', filename='test.txt', content_type='text/plain')
                test_data.add_field('user_id', 'test_user')
                
                async with session.post(f"{self.base_url}/api/videos/upload", data=test_data) as response:
                    if response.status in [400, 403, 422]:
                        self.log_success("Invalid file handling", "✅ Properly rejects invalid files")
                    else:
                        self.log_warning("Invalid file handling", f"⚠️ Unexpected status {response.status}")
            
            # Test invalid URL processing
            async with aiohttp.ClientSession() as session:
                invalid_data = aiohttp.FormData()
                invalid_data.add_field('url', 'not-a-valid-url')
                
                async with session.post(f"{self.base_url}/api/videos/process-url", data=invalid_data) as response:
                    if response.status in [400, 403, 405, 422]:
                        self.log_success("Invalid URL handling", "✅ Properly rejects invalid URLs")
                    else:
                        self.log_warning("Invalid URL handling", f"⚠️ Unexpected status {response.status}")
                        
        except Exception as e:
            self.log_error("Error handling", f"❌ Test failed: {str(e)}")
    
    async def test_timeout_scenarios(self):
        """Test timeout scenarios and recovery"""
        print("\n⏱️ Testing Timeout Scenarios...")
        
        try:
            # Test connection timeout
            timeout = aiohttp.ClientTimeout(total=1.0)  # Very short timeout
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    async with session.get(f"{self.base_url}/health") as response:
                        if response.status == 200:
                            self.log_success("Fast response", "✅ Server responds quickly")
                        else:
                            self.log_warning("Fast response", f"⚠️ Status {response.status}")
                except asyncio.TimeoutError:
                    self.log_error("Fast response", "❌ Server too slow (>1s)")
                except Exception as e:
                    self.log_error("Fast response", f"❌ Error: {str(e)}")
            
            # Test WebSocket timeout
            try:
                uri = f"{self.ws_url}/ws/timeout_test"
                async with websockets.connect(uri) as websocket:
                    # Send message and wait for response with timeout
                    await websocket.send(json.dumps({"type": "ping"}))
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    self.log_success("WebSocket timeout", "✅ WebSocket responds within timeout")
            except asyncio.TimeoutError:
                self.log_error("WebSocket timeout", "❌ WebSocket response timeout")
            except Exception as e:
                self.log_error("WebSocket timeout", f"❌ WebSocket error: {str(e)}")
                
        except Exception as e:
            self.log_error("Timeout scenarios", f"❌ Test failed: {str(e)}")
    
    def log_success(self, test: str, message: str):
        """Log successful test result"""
        result = {"test": test, "status": "SUCCESS", "message": message, "timestamp": datetime.now().isoformat()}
        self.results.append(result)
        print(f"  {message}")
    
    def log_error(self, test: str, message: str):
        """Log error test result"""
        result = {"test": test, "status": "ERROR", "message": message, "timestamp": datetime.now().isoformat()}
        self.results.append(result)
        print(f"  {message}")
    
    def log_warning(self, test: str, message: str):
        """Log warning test result"""
        result = {"test": test, "status": "WARNING", "message": message, "timestamp": datetime.now().isoformat()}
        self.results.append(result)
        print(f"  {message}")
    
    def log_info(self, test: str, message: str):
        """Log info test result"""
        result = {"test": test, "status": "INFO", "message": message, "timestamp": datetime.now().isoformat()}
        self.results.append(result)
        print(f"  {message}")
    
    def generate_report(self):
        """Generate comprehensive diagnostic report"""
        print("\n" + "=" * 50)
        print("📋 DIAGNOSTIC REPORT")
        print("=" * 50)
        
        # Count results by status
        success_count = len([r for r in self.results if r["status"] == "SUCCESS"])
        error_count = len([r for r in self.results if r["status"] == "ERROR"])
        warning_count = len([r for r in self.results if r["status"] == "WARNING"])
        info_count = len([r for r in self.results if r["status"] == "INFO"])
        
        print(f"\n📊 SUMMARY:")
        print(f"  ✅ Successful tests: {success_count}")
        print(f"  ❌ Failed tests: {error_count}")
        print(f"  ⚠️ Warnings: {warning_count}")
        print(f"  📊 Info: {info_count}")
        
        # Show critical errors
        errors = [r for r in self.results if r["status"] == "ERROR"]
        if errors:
            print(f"\n🚨 CRITICAL ISSUES:")
            for error in errors:
                print(f"  • {error['test']}: {error['message']}")
        
        # Show warnings
        warnings = [r for r in self.results if r["status"] == "WARNING"]
        if warnings:
            print(f"\n⚠️ WARNINGS:")
            for warning in warnings:
                print(f"  • {warning['test']}: {warning['message']}")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        
        if error_count > 0:
            print("  🔧 Fix critical errors first - these are blocking upload functionality")
        
        if any("timeout" in r["message"].lower() for r in errors):
            print("  ⏱️ Implement timeout handling and retry mechanisms")
        
        if any("websocket" in r["test"].lower() for r in errors):
            print("  🔌 Fix WebSocket connectivity for real-time progress updates")
        
        if any("supabase" in r["message"].lower() for r in errors):
            print("  🗄️ Fix database connectivity issues")
        
        if any("auth" in r["test"].lower() for r in warnings):
            print("  🔐 Review authentication requirements and error handling")
        
        print("  📈 Implement comprehensive monitoring and alerting")
        print("  🔄 Add upload resumption capability for large files")
        print("  💾 Monitor resource usage and implement limits")
        
        # Save detailed report
        report_file = f"upload_diagnosis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                "summary": {
                    "total_tests": len(self.results),
                    "success_count": success_count,
                    "error_count": error_count,
                    "warning_count": warning_count,
                    "info_count": info_count
                },
                "results": self.results,
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_file}")
        print("=" * 50)

async def main():
    """Run upload diagnostics"""
    diagnostics = UploadDiagnostics()
    await diagnostics.run_all_diagnostics()

if __name__ == "__main__":
    asyncio.run(main())