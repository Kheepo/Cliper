#!/usr/bin/env python3
"""
Comprehensive Test Suite for Cliper Application
Tests end-to-end clip generation with various scenarios
"""

import asyncio
import json
import time
import requests
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
import subprocess
from pathlib import Path

console = Console()

class ComprehensiveTestSuite:
    def __init__(self):
        self.api_url = "http://localhost:8001"
        self.test_results = {}
        self.test_video_id = "test-video-123"
        self.test_user_id = "test-user-456"
        
        # Test scenarios
        self.test_scenarios = [
            {
                "name": "YouTube Short",
                "platform": "youtube",
                "duration": 60,
                "aspect_ratio": "9:16",
                "description": "Test YouTube Shorts generation"
            },
            {
                "name": "TikTok Video",
                "platform": "tiktok", 
                "duration": 30,
                "aspect_ratio": "9:16",
                "description": "Test TikTok video generation"
            },
            {
                "name": "Instagram Reel",
                "platform": "instagram",
                "duration": 45,
                "aspect_ratio": "9:16", 
                "description": "Test Instagram Reel generation"
            },
            {
                "name": "Custom Format",
                "platform": "custom",
                "duration": 90,
                "aspect_ratio": "16:9",
                "description": "Test custom format generation"
            }
        ]
    
    def setup_test_environment(self) -> bool:
        """Setup test environment and verify prerequisites"""
        console.print("\n[bold blue]🔧 Setting up test environment...[/bold blue]")
        
        try:
            # Check if system status checker exists and run it
            if os.path.exists("system_status_checker.py"):
                result = subprocess.run([sys.executable, "system_status_checker.py"], 
                                      capture_output=True, text=True)
                if result.returncode != 0:
                    console.print("[red]❌ System status check failed. Please ensure all services are running.[/red]")
                    return False
            
            # Verify API is accessible
            try:
                response = requests.get(f"{self.api_url}/health", timeout=5)
                if response.status_code != 200:
                    console.print(f"[red]❌ API health check failed: {response.status_code}[/red]")
                    return False
            except Exception as e:
                console.print(f"[red]❌ Cannot connect to API: {e}[/red]")
                return False
            
            # Create test directories
            os.makedirs("test_results", exist_ok=True)
            os.makedirs("test_clips", exist_ok=True)
            
            console.print("[green]✅ Test environment setup complete[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]❌ Setup failed: {e}[/red]")
            return False
    
    def test_api_endpoints(self) -> Dict[str, Any]:
        """Test basic API endpoint functionality"""
        console.print("\n[bold cyan]🔍 Testing API Endpoints...[/bold cyan]")
        
        results = {}
        endpoints_to_test = [
            {"method": "GET", "path": "/health", "expected_status": 200},
            {"method": "GET", "path": "/api/videos/", "expected_status": [200, 401]},
            {"method": "GET", "path": f"/api/videos/{self.test_video_id}", "expected_status": [200, 404]},
        ]
        
        for endpoint in endpoints_to_test:
            try:
                method = endpoint["method"]
                path = endpoint["path"]
                expected = endpoint["expected_status"]
                
                if method == "GET":
                    response = requests.get(f"{self.api_url}{path}", timeout=10)
                
                status_ok = (response.status_code in expected if isinstance(expected, list) 
                           else response.status_code == expected)
                
                results[path] = {
                    "status_code": response.status_code,
                    "success": status_ok,
                    "response_time": response.elapsed.total_seconds(),
                    "error": None if status_ok else f"Unexpected status: {response.status_code}"
                }
                
                status_emoji = "✅" if status_ok else "❌"
                console.print(f"  {status_emoji} {method} {path}: {response.status_code}")
                
            except Exception as e:
                results[path] = {
                    "status_code": None,
                    "success": False,
                    "response_time": None,
                    "error": str(e)
                }
                console.print(f"  ❌ {method} {path}: {e}")
        
        return results
    
    def test_clip_generation_scenario(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """Test a specific clip generation scenario"""
        console.print(f"\n[bold yellow]🎬 Testing: {scenario['name']}[/bold yellow]")
        
        start_time = time.time()
        
        # Prepare request data
        request_data = {
            "platform": scenario["platform"],
            "max_duration": scenario["duration"],
            "aspect_ratio": scenario["aspect_ratio"],
            "user_preferences": {
                "style": "engaging",
                "include_captions": True,
                "music": False
            }
        }
        
        try:
            # Send clip generation request
            response = requests.post(
                f"{self.api_url}/api/videos/{self.test_video_id}/clips",
                json=request_data,
                timeout=30
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "duration": time.time() - start_time
                }
            
            clip_data = response.json()
            clip_id = clip_data.get("clip_id")
            
            if not clip_id:
                return {
                    "success": False,
                    "error": "No clip_id returned",
                    "duration": time.time() - start_time
                }
            
            # Monitor clip generation progress
            max_wait_time = 300  # 5 minutes
            check_interval = 5   # 5 seconds
            elapsed = 0
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(f"Generating {scenario['name']}...", total=max_wait_time)
                
                while elapsed < max_wait_time:
                    try:
                        status_response = requests.get(
                            f"{self.api_url}/api/clips/{clip_id}/status",
                            timeout=10
                        )
                        
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            status = status_data.get("status", "unknown")
                            
                            if status == "completed":
                                progress.update(task, completed=max_wait_time)
                                return {
                                    "success": True,
                                    "clip_id": clip_id,
                                    "status": status,
                                    "duration": time.time() - start_time,
                                    "file_info": self._check_clip_file(clip_id),
                                    "error": None
                                }
                            elif status == "failed":
                                error_msg = status_data.get("error", "Unknown error")
                                return {
                                    "success": False,
                                    "clip_id": clip_id,
                                    "status": status,
                                    "duration": time.time() - start_time,
                                    "error": error_msg
                                }
                        
                        time.sleep(check_interval)
                        elapsed += check_interval
                        progress.update(task, advance=check_interval)
                        
                    except Exception as e:
                        console.print(f"[yellow]Warning: Status check failed: {e}[/yellow]")
                        time.sleep(check_interval)
                        elapsed += check_interval
            
            # Timeout reached
            return {
                "success": False,
                "clip_id": clip_id,
                "status": "timeout",
                "duration": time.time() - start_time,
                "error": f"Generation timed out after {max_wait_time} seconds"
            }
            
        except Exception as e:
            return {
                "success": False,
                "duration": time.time() - start_time,
                "error": str(e)
            }
    
    def _check_clip_file(self, clip_id: str) -> Dict[str, Any]:
        """Check if clip file was actually generated and get file info"""
        possible_paths = [
            f"uploads/clips/{clip_id}.mp4",
            f"api/uploads/clips/{clip_id}.mp4",
            f"test_clips/{clip_id}.mp4"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                file_size = os.path.getsize(path)
                return {
                    "exists": True,
                    "path": path,
                    "size_bytes": file_size,
                    "size_mb": round(file_size / (1024 * 1024), 2),
                    "is_empty": file_size == 0
                }
        
        return {
            "exists": False,
            "path": None,
            "size_bytes": 0,
            "size_mb": 0,
            "is_empty": True
        }
    
    def test_performance_metrics(self) -> Dict[str, Any]:
        """Test performance and resource usage"""
        console.print("\n[bold magenta]📊 Testing Performance Metrics...[/bold magenta]")
        
        try:
            import psutil
            
            # Get initial system state
            initial_memory = psutil.virtual_memory().percent
            initial_cpu = psutil.cpu_percent(interval=1)
            
            # Run a quick test scenario
            test_scenario = self.test_scenarios[0]  # Use first scenario
            start_time = time.time()
            
            result = self.test_clip_generation_scenario(test_scenario)
            
            # Get final system state
            final_memory = psutil.virtual_memory().percent
            final_cpu = psutil.cpu_percent(interval=1)
            
            return {
                "test_duration": time.time() - start_time,
                "memory_usage": {
                    "initial": initial_memory,
                    "final": final_memory,
                    "delta": final_memory - initial_memory
                },
                "cpu_usage": {
                    "initial": initial_cpu,
                    "final": final_cpu,
                    "delta": final_cpu - initial_cpu
                },
                "generation_result": result
            }
            
        except ImportError:
            return {
                "error": "psutil not available for performance monitoring"
            }
        except Exception as e:
            return {
                "error": str(e)
            }
    
    def run_comprehensive_tests(self) -> Dict[str, Any]:
        """Run all comprehensive tests"""
        console.print("\n[bold green]🚀 Starting Comprehensive Test Suite[/bold green]")
        
        if not self.setup_test_environment():
            return {"error": "Test environment setup failed"}
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "api_tests": {},
            "clip_generation_tests": {},
            "performance_tests": {},
            "summary": {}
        }
        
        # Test API endpoints
        results["api_tests"] = self.test_api_endpoints()
        
        # Test clip generation scenarios
        for scenario in self.test_scenarios:
            scenario_result = self.test_clip_generation_scenario(scenario)
            results["clip_generation_tests"][scenario["name"]] = scenario_result
            
            # Small delay between tests
            time.sleep(2)
        
        # Test performance
        results["performance_tests"] = self.test_performance_metrics()
        
        # Generate summary
        results["summary"] = self._generate_summary(results)
        
        return results
    
    def _generate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate test summary"""
        api_success_count = sum(1 for test in results["api_tests"].values() if test.get("success", False))
        api_total = len(results["api_tests"])
        
        clip_success_count = sum(1 for test in results["clip_generation_tests"].values() if test.get("success", False))
        clip_total = len(results["clip_generation_tests"])
        
        return {
            "api_tests": {
                "passed": api_success_count,
                "total": api_total,
                "success_rate": (api_success_count / api_total * 100) if api_total > 0 else 0
            },
            "clip_generation": {
                "passed": clip_success_count,
                "total": clip_total,
                "success_rate": (clip_success_count / clip_total * 100) if clip_total > 0 else 0
            },
            "overall_success": api_success_count == api_total and clip_success_count == clip_total
        }
    
    def display_results(self, results: Dict[str, Any]):
        """Display test results in formatted tables"""
        
        # Summary table
        summary = results.get("summary", {})
        
        summary_table = Table(title="🎯 Test Summary")
        summary_table.add_column("Test Category", style="cyan")
        summary_table.add_column("Passed", style="green")
        summary_table.add_column("Total", style="blue")
        summary_table.add_column("Success Rate", style="magenta")
        
        api_summary = summary.get("api_tests", {})
        summary_table.add_row(
            "API Endpoints",
            str(api_summary.get("passed", 0)),
            str(api_summary.get("total", 0)),
            f"{api_summary.get('success_rate', 0):.1f}%"
        )
        
        clip_summary = summary.get("clip_generation", {})
        summary_table.add_row(
            "Clip Generation",
            str(clip_summary.get("passed", 0)),
            str(clip_summary.get("total", 0)),
            f"{clip_summary.get('success_rate', 0):.1f}%"
        )
        
        console.print(summary_table)
        
        # Detailed clip generation results
        clip_table = Table(title="🎬 Clip Generation Test Results")
        clip_table.add_column("Scenario", style="cyan")
        clip_table.add_column("Status", style="magenta")
        clip_table.add_column("Duration", style="green")
        clip_table.add_column("File Size", style="blue")
        clip_table.add_column("Notes", style="yellow")
        
        for scenario_name, result in results.get("clip_generation_tests", {}).items():
            status_emoji = "✅" if result.get("success", False) else "❌"
            status = f"{status_emoji} {result.get('status', 'unknown')}"
            
            duration = f"{result.get('duration', 0):.1f}s"
            
            file_info = result.get("file_info", {})
            file_size = f"{file_info.get('size_mb', 0):.1f} MB" if file_info.get("exists", False) else "No file"
            
            notes = result.get("error", "Success") if not result.get("success", False) else "Success"
            if file_info.get("is_empty", True) and file_info.get("exists", False):
                notes = "File exists but is empty"
            
            clip_table.add_row(scenario_name, status, duration, file_size, notes)
        
        console.print(clip_table)
        
        # Overall status
        overall_success = summary.get("overall_success", False)
        if overall_success:
            console.print("\n[bold green]🎉 All tests passed successfully![/bold green]")
        else:
            console.print("\n[bold yellow]⚠️ Some tests failed. Please review the results above.[/bold yellow]")
    
    def save_results(self, results: Dict[str, Any], filename: str = None):
        """Save test results to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_results/comprehensive_test_report_{timestamp}.json"
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        console.print(f"\n📄 Test report saved to: [cyan]{filename}[/cyan]")
        return filename

def main():
    """Main function to run comprehensive tests"""
    test_suite = ComprehensiveTestSuite()
    
    try:
        results = test_suite.run_comprehensive_tests()
        
        if "error" in results:
            console.print(f"[red]❌ Test suite failed: {results['error']}[/red]")
            sys.exit(1)
        
        test_suite.display_results(results)
        report_file = test_suite.save_results(results)
        
        # Return exit code based on test results
        overall_success = results.get("summary", {}).get("overall_success", False)
        sys.exit(0 if overall_success else 1)
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Tests interrupted by user[/yellow]")
        sys.exit(1)