#!/usr/bin/env python3
"""
Interactive Testing Guide for Cliper Application
Step-by-step manual testing instructions with automated verification
"""

import requests
import json
import time
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
import subprocess

console = Console()

class InteractiveTestingGuide:
    def __init__(self):
        self.api_url = "http://localhost:8001"
        self.test_results = {}
        self.current_step = 0
        self.total_steps = 0
        
        # Test steps configuration
        self.test_steps = [
            {
                "title": "System Status Verification",
                "description": "Verify all services are running",
                "type": "automated",
                "function": self.verify_system_status
            },
            {
                "title": "API Health Check",
                "description": "Test basic API connectivity",
                "type": "automated", 
                "function": self.test_api_health
            },
            {
                "title": "Video Upload Interface",
                "description": "Test video upload functionality",
                "type": "manual",
                "function": self.guide_video_upload
            },
            {
                "title": "Clip Generation - YouTube Format",
                "description": "Generate clips for YouTube platform",
                "type": "interactive",
                "function": self.test_youtube_clip_generation
            },
            {
                "title": "Clip Generation - TikTok Format", 
                "description": "Generate clips for TikTok platform",
                "type": "interactive",
                "function": self.test_tiktok_clip_generation
            },
            {
                "title": "Clip Generation - Instagram Format",
                "description": "Generate clips for Instagram platform", 
                "type": "interactive",
                "function": self.test_instagram_clip_generation
            },
            {
                "title": "Real-time Processing Monitor",
                "description": "Monitor Celery worker processing",
                "type": "manual",
                "function": self.guide_processing_monitor
            },
            {
                "title": "File Verification",
                "description": "Verify generated clip files",
                "type": "automated",
                "function": self.verify_clip_files
            },
            {
                "title": "Performance Assessment",
                "description": "Assess system performance",
                "type": "automated", 
                "function": self.assess_performance
            },
            {
                "title": "Error Handling Test",
                "description": "Test error scenarios",
                "type": "interactive",
                "function": self.test_error_handling
            }
        ]
        
        self.total_steps = len(self.test_steps)
    
    def start_interactive_testing(self):
        """Start the interactive testing process"""
        console.print("\n[bold blue]🚀 Welcome to Cliper Interactive Testing Guide[/bold blue]")
        console.print("\nThis guide will walk you through comprehensive testing of the clip generation system.")
        console.print("You'll test different platforms, monitor processing, and verify functionality.\n")
        
        if not Confirm.ask("Ready to start testing?"):
            console.print("[yellow]Testing cancelled by user[/yellow]")
            return
        
        # Initialize results
        self.test_results = {
            "start_time": datetime.now().isoformat(),
            "steps": {},
            "summary": {}
        }
        
        # Run each test step
        for i, step in enumerate(self.test_steps):
            self.current_step = i + 1
            
            console.print(f"\n[bold cyan]Step {self.current_step}/{self.total_steps}: {step['title']}[/bold cyan]")
            console.print(f"[dim]{step['description']}[/dim]")
            
            try:
                if step["type"] == "automated":
                    result = step["function"]()
                elif step["type"] == "manual":
                    result = step["function"]()
                elif step["type"] == "interactive":
                    result = step["function"]()
                
                self.test_results["steps"][step["title"]] = result
                
                # Show result
                if result.get("success", False):
                    console.print(f"[green]✅ Step {self.current_step} completed successfully[/green]")
                else:
                    console.print(f"[red]❌ Step {self.current_step} failed: {result.get('error', 'Unknown error')}[/red]")
                    
                    if not Confirm.ask("Continue with next step?"):
                        break
                
            except Exception as e:
                error_result = {"success": False, "error": str(e)}
                self.test_results["steps"][step["title"]] = error_result
                console.print(f"[red]❌ Step {self.current_step} failed with exception: {e}[/red]")
                
                if not Confirm.ask("Continue with next step?"):
                    break
        
        # Generate final summary
        self.generate_final_summary()
    
    def verify_system_status(self) -> Dict[str, Any]:
        """Step 1: Verify system status"""
        console.print("\n[yellow]Checking system status...[/yellow]")
        
        try:
            # Check if system status checker exists and run it
            if os.path.exists("system_status_checker.py"):
                result = subprocess.run([sys.executable, "system_status_checker.py"], 
                                      capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    return {
                        "success": True,
                        "message": "All systems healthy",
                        "details": "System status check passed"
                    }
                else:
                    return {
                        "success": False,
                        "error": "System status check failed",
                        "details": result.stderr
                    }
            else:
                # Manual checks
                checks = {
                    "redis": self._check_redis(),
                    "api": self._check_api(),
                    "celery": self._check_celery()
                }
                
                all_healthy = all(check["healthy"] for check in checks.values())
                
                return {
                    "success": all_healthy,
                    "checks": checks,
                    "message": "All services healthy" if all_healthy else "Some services have issues"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _check_redis(self) -> Dict[str, Any]:
        """Check Redis connectivity"""
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0)
            ping_result = r.ping()
            return {"healthy": ping_result, "service": "Redis"}
        except Exception as e:
            return {"healthy": False, "service": "Redis", "error": str(e)}
    
    def _check_api(self) -> Dict[str, Any]:
        """Check API connectivity"""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            return {"healthy": response.status_code == 200, "service": "API", "status_code": response.status_code}
        except Exception as e:
            return {"healthy": False, "service": "API", "error": str(e)}
    
    def _check_celery(self) -> Dict[str, Any]:
        """Check Celery worker"""
        try:
            result = subprocess.run(
                ["celery", "-A", "api.celery_app", "inspect", "ping"],
                capture_output=True, text=True, timeout=10
            )
            return {"healthy": result.returncode == 0, "service": "Celery"}
        except Exception as e:
            return {"healthy": False, "service": "Celery", "error": str(e)}
    
    def test_api_health(self) -> Dict[str, Any]:
        """Step 2: Test API health"""
        console.print("\n[yellow]Testing API endpoints...[/yellow]")
        
        endpoints = [
            {"path": "/health", "method": "GET"},
            {"path": "/api/videos/", "method": "GET"},
        ]
        
        results = {}
        all_success = True
        
        for endpoint in endpoints:
            try:
                if endpoint["method"] == "GET":
                    response = requests.get(f"{self.api_url}{endpoint['path']}", timeout=10)
                
                success = response.status_code in [200, 401, 422]  # 401/422 expected without auth
                results[endpoint["path"]] = {
                    "status_code": response.status_code,
                    "success": success
                }
                
                if not success:
                    all_success = False
                    
                console.print(f"  {'✅' if success else '❌'} {endpoint['method']} {endpoint['path']}: {response.status_code}")
                
            except Exception as e:
                results[endpoint["path"]] = {"success": False, "error": str(e)}
                all_success = False
                console.print(f"  ❌ {endpoint['method']} {endpoint['path']}: {e}")
        
        return {
            "success": all_success,
            "endpoints": results,
            "message": "All endpoints accessible" if all_success else "Some endpoints failed"
        }
    
    def guide_video_upload(self) -> Dict[str, Any]:
        """Step 3: Guide video upload testing"""
        console.print("\n[bold yellow]📹 Video Upload Testing[/bold yellow]")
        console.print("\nThis step tests the video upload functionality.")
        console.print("\n[cyan]Instructions:[/cyan]")
        console.print("1. Open your browser to: http://localhost:8001")
        console.print("2. Navigate to the video upload section")
        console.print("3. Try uploading a test video file")
        console.print("4. Verify the upload completes successfully")
        console.print("5. Note the video ID for later testing")
        
        console.print("\n[dim]Press Enter when you've completed the upload test...[/dim]")
        input()
        
        # Ask for results
        upload_success = Confirm.ask("Did the video upload successfully?")
        
        if upload_success:
            video_id = Prompt.ask("What is the video ID? (or press Enter for default)", default="test-video-123")
            return {
                "success": True,
                "video_id": video_id,
                "message": "Video upload completed successfully"
            }
        else:
            error_details = Prompt.ask("What error occurred?", default="Upload failed")
            return {
                "success": False,
                "error": error_details,
                "message": "Video upload failed"
            }
    
    def test_youtube_clip_generation(self) -> Dict[str, Any]:
        """Step 4: Test YouTube clip generation"""
        return self._test_platform_clip_generation("youtube", "YouTube Short", 60)
    
    def test_tiktok_clip_generation(self) -> Dict[str, Any]:
        """Step 5: Test TikTok clip generation"""
        return self._test_platform_clip_generation("tiktok", "TikTok Video", 30)
    
    def test_instagram_clip_generation(self) -> Dict[str, Any]:
        """Step 6: Test Instagram clip generation"""
        return self._test_platform_clip_generation("instagram", "Instagram Reel", 45)
    
    def _test_platform_clip_generation(self, platform: str, platform_name: str, duration: int) -> Dict[str, Any]:
        """Test clip generation for a specific platform"""
        console.print(f"\n[bold yellow]🎬 {platform_name} Clip Generation[/bold yellow]")
        
        # Get video ID from previous steps or ask user
        video_id = "test-video-123"
        if "Video Upload Interface" in self.test_results.get("steps", {}):
            upload_result = self.test_results["steps"]["Video Upload Interface"]
            if upload_result.get("video_id"):
                video_id = upload_result["video_id"]
        
        console.print(f"Testing {platform_name} clip generation for video: {video_id}")
        
        if not Confirm.ask(f"Proceed with {platform_name} clip generation test?"):
            return {"success": False, "error": "Test skipped by user"}
        
        # Prepare request
        request_data = {
            "platform": platform,
            "max_duration": duration,
            "aspect_ratio": "9:16",
            "user_preferences": {
                "style": "engaging",
                "include_captions": True
            }
        }
        
        console.print(f"\n[cyan]Sending clip generation request...[/cyan]")
        console.print(f"Platform: {platform}")
        console.print(f"Duration: {duration}s")
        console.print(f"Aspect Ratio: 9:16")
        
        try:
            # Send request
            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/api/videos/{video_id}/clips",
                json=request_data,
                timeout=30
            )
            
            api_time = time.time() - start_time
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "api_response_time": api_time
                }
            
            clip_data = response.json()
            clip_id = clip_data.get("clip_id")
            
            if not clip_id:
                return {
                    "success": False,
                    "error": "No clip_id returned",
                    "api_response_time": api_time
                }
            
            console.print(f"[green]✅ Clip generation request sent successfully[/green]")
            console.print(f"Clip ID: {clip_id}")
            console.print(f"API Response Time: {api_time:.3f}s")
            
            # Monitor progress
            console.print(f"\n[cyan]Monitoring clip generation progress...[/cyan]")
            console.print("You can also check the Celery worker logs in your terminal")
            
            progress_result = self._monitor_clip_progress(clip_id, platform_name)
            
            return {
                "success": progress_result.get("success", False),
                "clip_id": clip_id,
                "platform": platform,
                "api_response_time": api_time,
                "generation_time": progress_result.get("duration", 0),
                "status": progress_result.get("status", "unknown"),
                "error": progress_result.get("error"),
                "message": f"{platform_name} clip generation completed" if progress_result.get("success") else f"{platform_name} clip generation failed"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "platform": platform
            }
    
    def _monitor_clip_progress(self, clip_id: str, platform_name: str) -> Dict[str, Any]:
        """Monitor clip generation progress"""
        max_wait_time = 300  # 5 minutes
        check_interval = 10  # 10 seconds
        elapsed = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Generating {platform_name} clip...", total=None)
            
            while elapsed < max_wait_time:
                try:
                    status_response = requests.get(
                        f"{self.api_url}/api/clips/{clip_id}/status",
                        timeout=10
                    )
                    
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        status = status_data.get("status", "unknown")
                        
                        console.print(f"[dim]Status check: {status}[/dim]")
                        
                        if status == "completed":
                            progress.update(task, completed=True)
                            return {
                                "success": True,
                                "status": status,
                                "duration": elapsed
                            }
                        elif status == "failed":
                            return {
                                "success": False,
                                "status": status,
                                "duration": elapsed,
                                "error": status_data.get("error", "Unknown error")
                            }
                    
                    time.sleep(check_interval)
                    elapsed += check_interval
                    
                except Exception as e:
                    console.print(f"[yellow]Warning: Status check failed: {e}[/yellow]")
                    time.sleep(check_interval)
                    elapsed += check_interval
            
            return {
                "success": False,
                "status": "timeout",
                "duration": elapsed,
                "error": f"Generation timed out after {max_wait_time} seconds"
            }
    
    def guide_processing_monitor(self) -> Dict[str, Any]:
        """Step 7: Guide processing monitoring"""
        console.print("\n[bold yellow]📊 Real-time Processing Monitor[/bold yellow]")
        console.print("\nThis step helps you monitor the Celery worker processing.")
        console.print("\n[cyan]Instructions:[/cyan]")
        console.print("1. Check your terminal running the Celery worker")
        console.print("2. Look for task processing logs")
        console.print("3. Monitor for any errors or warnings")
        console.print("4. Check system resource usage (CPU, Memory)")
        
        console.print("\n[dim]Press Enter when you've reviewed the processing logs...[/dim]")
        input()
        
        # Ask about observations
        processing_visible = Confirm.ask("Can you see task processing in the Celery logs?")
        errors_present = Confirm.ask("Are there any errors or warnings in the logs?")
        
        if processing_visible and not errors_present:
            return {
                "success": True,
                "message": "Processing monitoring looks healthy",
                "observations": {
                    "processing_visible": processing_visible,
                    "errors_present": errors_present
                }
            }
        else:
            issues = []
            if not processing_visible:
                issues.append("No task processing visible")
            if errors_present:
                error_details = Prompt.ask("What errors did you observe?", default="Unspecified errors")
                issues.append(f"Errors present: {error_details}")
            
            return {
                "success": False,
                "error": "; ".join(issues),
                "observations": {
                    "processing_visible": processing_visible,
                    "errors_present": errors_present
                }
            }
    
    def verify_clip_files(self) -> Dict[str, Any]:
        """Step 8: Verify generated clip files"""
        console.print("\n[yellow]Verifying generated clip files...[/yellow]")
        
        # Look for clip files in common directories
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
        
        if not found_files:
            return {
                "success": False,
                "error": "No clip files found",
                "searched_directories": clip_directories
            }
        
        # Check for empty files
        empty_files = [f for f in found_files if f["is_empty"]]
        valid_files = [f for f in found_files if not f["is_empty"]]
        
        console.print(f"\n[cyan]Found {len(found_files)} clip files:[/cyan]")
        for file in found_files:
            status = "❌ Empty" if file["is_empty"] else "✅ Valid"
            console.print(f"  {status} {file['name']} ({file['size_mb']} MB)")
        
        return {
            "success": len(valid_files) > 0,
            "total_files": len(found_files),
            "valid_files": len(valid_files),
            "empty_files": len(empty_files),
            "files": found_files,
            "message": f"Found {len(valid_files)} valid clip files" if len(valid_files) > 0 else "All clip files are empty"
        }
    
    def assess_performance(self) -> Dict[str, Any]:
        """Step 9: Assess system performance"""
        console.print("\n[yellow]Assessing system performance...[/yellow]")
        
        try:
            import psutil
            
            # Get current system metrics
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=2)
            disk_usage = psutil.disk_usage('C:\\' if os.name == 'nt' else '/')
            
            # Performance thresholds
            memory_threshold = 80  # 80%
            cpu_threshold = 80     # 80%
            disk_threshold = 90    # 90%
            
            performance_issues = []
            
            if memory.percent > memory_threshold:
                performance_issues.append(f"High memory usage: {memory.percent:.1f}%")
            
            if cpu_percent > cpu_threshold:
                performance_issues.append(f"High CPU usage: {cpu_percent:.1f}%")
            
            disk_percent = (disk_usage.used / disk_usage.total) * 100
            if disk_percent > disk_threshold:
                performance_issues.append(f"High disk usage: {disk_percent:.1f}%")
            
            console.print(f"[cyan]System Performance:[/cyan]")
            console.print(f"  Memory: {memory.percent:.1f}% used")
            console.print(f"  CPU: {cpu_percent:.1f}% used")
            console.print(f"  Disk: {disk_percent:.1f}% used")
            
            return {
                "success": len(performance_issues) == 0,
                "metrics": {
                    "memory_percent": memory.percent,
                    "cpu_percent": cpu_percent,
                    "disk_percent": disk_percent
                },
                "issues": performance_issues,
                "message": "Performance looks good" if len(performance_issues) == 0 else f"Performance issues: {'; '.join(performance_issues)}"
            }
            
        except ImportError:
            return {
                "success": False,
                "error": "psutil not available for performance monitoring"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def test_error_handling(self) -> Dict[str, Any]:
        """Step 10: Test error handling"""
        console.print("\n[bold yellow]🚨 Error Handling Test[/bold yellow]")
        console.print("\nThis step tests how the system handles error scenarios.")
        
        if not Confirm.ask("Proceed with error handling tests?"):
            return {"success": False, "error": "Test skipped by user"}
        
        error_tests = [
            {
                "name": "Invalid Video ID",
                "video_id": "nonexistent-video-999",
                "expected": "404 or error response"
            },
            {
                "name": "Invalid Platform",
                "platform": "invalid-platform",
                "expected": "Validation error"
            }
        ]
        
        results = []
        
        for test in error_tests:
            console.print(f"\n[cyan]Testing: {test['name']}[/cyan]")
            
            try:
                if "Invalid Video ID" in test["name"]:
                    response = requests.post(
                        f"{self.api_url}/api/videos/{test['video_id']}/clips",
                        json={"platform": "youtube", "max_duration": 60},
                        timeout=10
                    )
                elif "Invalid Platform" in test["name"]:
                    response = requests.post(
                        f"{self.api_url}/api/videos/test-video-123/clips",
                        json={"platform": test["platform"], "max_duration": 60},
                        timeout=10
                    )
                
                # Error responses are expected
                error_handled = response.status_code in [400, 404, 422, 500]
                
                results.append({
                    "test": test["name"],
                    "success": error_handled,
                    "status_code": response.status_code,
                    "expected": test["expected"]
                })
                
                console.print(f"  {'✅' if error_handled else '❌'} Status: {response.status_code}")
                
            except Exception as e:
                results.append({
                    "test": test["name"],
                    "success": False,
                    "error": str(e)
                })
                console.print(f"  ❌ Exception: {e}")
        
        successful_tests = sum(1 for r in results if r.get("success", False))
        
        return {
            "success": successful_tests == len(error_tests),
            "tests": results,
            "passed": successful_tests,
            "total": len(error_tests),
            "message": f"Error handling: {successful_tests}/{len(error_tests)} tests passed"
        }
    
    def generate_final_summary(self):
        """Generate and display final test summary"""
        self.test_results["end_time"] = datetime.now().isoformat()
        
        console.print("\n[bold blue]📋 Final Test Summary[/bold blue]")
        
        # Create summary table
        summary_table = Table(title="Test Results Overview")
        summary_table.add_column("Step", style="cyan")
        summary_table.add_column("Status", style="magenta")
        summary_table.add_column("Details", style="green")
        
        passed_steps = 0
        total_steps = len(self.test_results["steps"])
        
        for step_name, result in self.test_results["steps"].items():
            status_emoji = "✅" if result.get("success", False) else "❌"
            status = f"{status_emoji} {'Passed' if result.get('success', False) else 'Failed'}"
            
            details = result.get("message", result.get("error", "No details"))
            
            summary_table.add_row(step_name, status, details)
            
            if result.get("success", False):
                passed_steps += 1
        
        console.print(summary_table)
        
        # Overall results
        success_rate = (passed_steps / total_steps * 100) if total_steps > 0 else 0
        
        console.print(f"\n[bold cyan]Overall Results:[/bold cyan]")
        console.print(f"  Passed: {passed_steps}/{total_steps} ({success_rate:.1f}%)")
        
        if success_rate >= 80:
            console.print("[bold green]🎉 Testing completed successfully! System is ready for use.[/bold green]")
        elif success_rate >= 60:
            console.print("[bold yellow]⚠️ Testing completed with some issues. Review failed steps.[/bold yellow]")
        else:
            console.print("[bold red]❌ Testing revealed significant issues. System needs attention.[/bold red]")
        
        # Save results
        self.save_test_results()
    
    def save_test_results(self):
        """Save test results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"interactive_test_results_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        console.print(f"\n📄 Test results saved to: [cyan]{filename}[/cyan]")

def main():
    """Main function for interactive testing"""
    guide = InteractiveTestingGuide()
    
    try