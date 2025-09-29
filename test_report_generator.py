#!/usr/bin/env python3
"""
Test Report Generator for Cliper Application
Generates comprehensive reports from test results and system status
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
import requests
import subprocess

class TestReportGenerator:
    def __init__(self):
        self.api_url = "http://localhost:8001"
        self.report_data = {
            "timestamp": datetime.now().isoformat(),
            "system_status": {},
            "api_tests": {},
            "clip_generation_tests": {},
            "performance_metrics": {},
            "file_verification": {},
            "summary": {}
        }
    
    def collect_system_status(self):
        """Collect current system status"""
        print("📊 Collecting system status...")
        
        try:
            # Check Redis
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0)
            redis_status = {"healthy": r.ping(), "service": "Redis"}
        except Exception as e:
            redis_status = {"healthy": False, "service": "Redis", "error": str(e)}
        
        # Check API
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            api_status = {"healthy": response.status_code == 200, "service": "API", "status_code": response.status_code}
        except Exception as e:
            api_status = {"healthy": False, "service": "API", "error": str(e)}
        
        # Check Celery
        try:
            result = subprocess.run(
                ["celery", "-A", "api.celery_app", "inspect", "ping"],
                capture_output=True, text=True, timeout=10
            )
            celery_status = {"healthy": result.returncode == 0, "service": "Celery"}
        except Exception as e:
            celery_status = {"healthy": False, "service": "Celery", "error": str(e)}
        
        self.report_data["system_status"] = {
            "redis": redis_status,
            "api": api_status,
            "celery": celery_status,
            "overall_healthy": all([redis_status["healthy"], api_status["healthy"], celery_status["healthy"]])
        }
    
    def test_api_endpoints(self):
        """Test basic API endpoints"""
        print("🔍 Testing API endpoints...")
        
        endpoints = [
            {"path": "/health", "method": "GET", "expected": [200]},
            {"path": "/api/videos/", "method": "GET", "expected": [200, 401, 422]},
        ]
        
        results = {}
        
        for endpoint in endpoints:
            try:
                if endpoint["method"] == "GET":
                    response = requests.get(f"{self.api_url}{endpoint['path']}", timeout=10)
                
                success = response.status_code in endpoint["expected"]
                results[endpoint["path"]] = {
                    "status_code": response.status_code,
                    "success": success,
                    "response_time": response.elapsed.total_seconds()
                }
                
                print(f"  {'✅' if success else '❌'} {endpoint['method']} {endpoint['path']}: {response.status_code}")
                
            except Exception as e:
                results[endpoint["path"]] = {"success": False, "error": str(e)}
                print(f"  ❌ {endpoint['method']} {endpoint['path']}: {e}")
        
        self.report_data["api_tests"] = results
    
    def test_clip_generation(self):
        """Test clip generation for different platforms"""
        print("🎬 Testing clip generation...")
        
        platforms = [
            {"platform": "youtube", "duration": 60, "name": "YouTube Short"},
            {"platform": "tiktok", "duration": 30, "name": "TikTok Video"},
            {"platform": "instagram", "duration": 45, "name": "Instagram Reel"}
        ]
        
        results = {}
        video_id = "test-video-123"
        
        for platform_config in platforms:
            platform = platform_config["platform"]
            print(f"  Testing {platform_config['name']}...")
            
            request_data = {
                "platform": platform,
                "max_duration": platform_config["duration"],
                "aspect_ratio": "9:16"
            }
            
            try:
                # Send clip generation request
                response = requests.post(
                    f"{self.api_url}/api/videos/{video_id}/clips",
                    json=request_data,
                    timeout=30
                )
                
                if response.status_code == 200:
                    clip_data = response.json()
                    clip_id = clip_data.get("clip_id")
                    
                    if clip_id:
                        # Check status once
                        status_response = requests.get(
                            f"{self.api_url}/api/clips/{clip_id}/status",
                            timeout=10
                        )
                        
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            status = status_data.get("status", "unknown")
                        else:
                            status = "status_check_failed"
                        
                        results[platform] = {
                            "success": True,
                            "clip_id": clip_id,
                            "initial_status": status,
                            "api_response_time": response.elapsed.total_seconds()
                        }
                        print(f"    ✅ Request successful, Clip ID: {clip_id}, Status: {status}")
                    else:
                        results[platform] = {
                            "success": False,
                            "error": "No clip_id returned"
                        }
                        print(f"    ❌ No clip_id returned")
                else:
                    results[platform] = {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text[:100]}"
                    }
                    print(f"    ❌ HTTP {response.status_code}")
                    
            except Exception as e:
                results[platform] = {
                    "success": False,
                    "error": str(e)
                }
                print(f"    ❌ Exception: {e}")
        
        self.report_data["clip_generation_tests"] = results
    
    def check_clip_files(self):
        """Check for generated clip files"""
        print("📁 Checking clip files...")
        
        clip_directories = [
            "uploads/clips",
            "api/uploads/clips",
            "test_clips",
            "clips"
        ]
        
        found_files = []
        
        for directory in clip_directories:
            if os.path.exists(directory):
                for file in os.listdir(directory):
                    if file.endswith(('.mp4', '.avi', '.mov', '.mkv')):
                        file_path = os.path.join(directory, file)
                        file_size = os.path.getsize(file_path)
                        
                        found_files.append({
                            "name": file,
                            "path": file_path,
                            "size_bytes": file_size,
                            "size_mb": round(file_size / (1024 * 1024), 2),
                            "is_empty": file_size == 0
                        })
        
        empty_files = [f for f in found_files if f["is_empty"]]
        valid_files = [f for f in found_files if not f["is_empty"]]
        
        print(f"  Found {len(found_files)} total files, {len(valid_files)} valid, {len(empty_files)} empty")
        
        self.report_data["file_verification"] = {
            "total_files": len(found_files),
            "valid_files": len(valid_files),
            "empty_files": len(empty_files),
            "files": found_files,
            "directories_checked": clip_directories
        }
    
    def collect_performance_metrics(self):
        """Collect basic performance metrics"""
        print("⚡ Collecting performance metrics...")
        
        try:
            import psutil
            
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            disk_usage = psutil.disk_usage('C:\\' if os.name == 'nt' else '/')
            
            self.report_data["performance_metrics"] = {
                "memory_percent": memory.percent,
                "cpu_percent": cpu_percent,
                "disk_percent": (disk_usage.used / disk_usage.total) * 100,
                "available_memory_gb": round(memory.available / (1024**3), 2),
                "total_memory_gb": round(memory.total / (1024**3), 2)
            }
            
            print(f"  Memory: {memory.percent:.1f}%, CPU: {cpu_percent:.1f}%")
            
        except ImportError:
            self.report_data["performance_metrics"] = {"error": "psutil not available"}
            print("  ⚠️ psutil not available for performance monitoring")
        except Exception as e:
            self.report_data["performance_metrics"] = {"error": str(e)}
            print(f"  ❌ Error collecting metrics: {e}")
    
    def generate_summary(self):
        """Generate test summary"""
        print("📋 Generating summary...")
        
        # System status summary
        system_healthy = self.report_data["system_status"].get("overall_healthy", False)
        
        # API tests summary
        api_tests = self.report_data["api_tests"]
        api_passed = sum(1 for test in api_tests.values() if test.get("success", False))
        api_total = len(api_tests)
        
        # Clip generation summary
        clip_tests = self.report_data["clip_generation_tests"]
        clip_passed = sum(1 for test in clip_tests.values() if test.get("success", False))
        clip_total = len(clip_tests)
        
        # File verification summary
        file_data = self.report_data["file_verification"]
        valid_files = file_data.get("valid_files", 0)
        total_files = file_data.get("total_files", 0)
        
        self.report_data["summary"] = {
            "system_status": {
                "healthy": system_healthy,
                "status": "All services running" if system_healthy else "Some services have issues"
            },
            "api_tests": {
                "passed": api_passed,
                "total": api_total,
                "success_rate": (api_passed / api_total * 100) if api_total > 0 else 0
            },
            "clip_generation": {
                "passed": clip_passed,
                "total": clip_total,
                "success_rate": (clip_passed / clip_total * 100) if clip_total > 0 else 0
            },
            "file_verification": {
                "valid_files": valid_files,
                "total_files": total_files,
                "has_valid_files": valid_files > 0
            },
            "overall_assessment": self._get_overall_assessment(system_healthy, api_passed, api_total, clip_passed, clip_total, valid_files)
        }
    
    def _get_overall_assessment(self, system_healthy, api_passed, api_total, clip_passed, clip_total, valid_files):
        """Get overall system assessment"""
        if not system_healthy:
            return "CRITICAL: System services not healthy"
        
        if api_passed < api_total:
            return "WARNING: API endpoints have issues"
        
        if clip_passed == 0:
            return "CRITICAL: Clip generation completely failing"
        
        if clip_passed < clip_total:
            return "WARNING: Some clip generation tests failing"
        
        if valid_files == 0:
            return "CRITICAL: No valid clip files generated"
        
        return "GOOD: System functioning normally"
    
    def display_report(self):
        """Display the test report"""
        print("\n" + "="*60)
        print("🎯 COMPREHENSIVE TEST REPORT")
        print("="*60)
        
        # System Status
        print("\n📊 SYSTEM STATUS")
        print("-" * 30)
        system_status = self.report_data["system_status"]
        for service, data in system_status.items():
            if service != "overall_healthy" and isinstance(data, dict):
                status = "✅ Healthy" if data.get("healthy", False) else "❌ Unhealthy"
                print(f"  {data.get('service', service)}: {status}")
        
        # API Tests
        print("\n🔍 API ENDPOINT TESTS")
        print("-" * 30)
        api_summary = self.report_data["summary"]["api_tests"]
        print(f"  Passed: {api_summary['passed']}/{api_summary['total']} ({api_summary['success_rate']:.1f}%)")
        
        # Clip Generation Tests
        print("\n🎬 CLIP GENERATION TESTS")
        print("-" * 30)
        clip_summary = self.report_data["summary"]["clip_generation"]
        print(f"  Passed: {clip_summary['passed']}/{clip_summary['total']} ({clip_summary['success_rate']:.1f}%)")
        
        for platform, result in self.report_data["clip_generation_tests"].items():
            status = "✅" if result.get("success", False) else "❌"
            print(f"    {status} {platform.title()}: {result.get('initial_status', 'failed')}")
        
        # File Verification
        print("\n📁 FILE VERIFICATION")
        print("-" * 30)
        file_summary = self.report_data["summary"]["file_verification"]
        print(f"  Valid files: {file_summary['valid_files']}/{file_summary['total_files']}")
        
        # Performance
        print("\n⚡ PERFORMANCE METRICS")
        print("-" * 30)
        perf = self.report_data["performance_metrics"]
        if "error" not in perf:
            print(f"  Memory: {perf.get('memory_percent', 0):.1f}%")
            print(f"  CPU: {perf.get('cpu_percent', 0):.1f}%")
            print(f"  Available Memory: {perf.get('available_memory_gb', 0):.1f} GB")
        else:
            print(f"  ❌ {perf['error']}")
        
        # Overall Assessment
        print("\n🎯 OVERALL ASSESSMENT")
        print("-" * 30)
        assessment = self.report_data["summary"]["overall_assessment"]
        if "CRITICAL" in assessment:
            print(f"  🚨 {assessment}")
        elif "WARNING" in assessment:
            print(f"  ⚠️ {assessment}")
        else:
            print(f"  ✅ {assessment}")
        
        print("\n" + "="*60)
    
    def save_report(self, filename=None):
        """Save report to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_report_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.report_data, f, indent=2, default=str)
        
        print(f"\n📄 Report saved to: {filename}")
        return filename
    
    def run_comprehensive_report(self):
        """Run all tests and generate comprehensive report"""
        print("🚀 Starting Comprehensive Test Report Generation")
        print("="*60)
        
        try:
            self.collect_system_status()
            self.test_api_endpoints()
            self.test_clip_generation()
            self.check_clip_files()
            self.collect_performance_metrics()
            self.generate_summary()
            
            self.display_report()
            report_file = self.save_report()
            
            # Return success based on overall assessment
            assessment = self.report_data["summary"]["overall_assessment"]
            return "GOOD" in assessment
            
        except Exception as e:
            print(f"\n❌ Error generating report: {e}")
            return False

def main():
    """Main function"""
    generator = TestReportGenerator()
    
    try:
        success = generator.run_comprehensive_report()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Report generation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()