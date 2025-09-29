#!/usr/bin/env python3
"""
Performance Monitor for Cliper Application
Monitors processing times, resource usage, and system performance during clip generation
"""

import asyncio
import json
import time
import psutil
import requests
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
import subprocess
import sys
import os
from collections import deque
import statistics

console = Console()

class PerformanceMonitor:
    def __init__(self):
        self.api_url = "http://localhost:8001"
        self.monitoring = False
        self.metrics_history = deque(maxlen=100)  # Keep last 100 measurements
        self.active_tasks = {}
        self.performance_data = {
            "start_time": None,
            "end_time": None,
            "total_duration": 0,
            "system_metrics": [],
            "task_metrics": [],
            "api_response_times": [],
            "resource_usage": {
                "peak_memory": 0,
                "peak_cpu": 0,
                "avg_memory": 0,
                "avg_cpu": 0
            }
        }
    
    def start_monitoring(self):
        """Start performance monitoring"""
        self.monitoring = True
        self.performance_data["start_time"] = datetime.now()
        console.print("[bold green]🚀 Performance monitoring started[/bold green]")
        
        # Start background monitoring thread
        self.monitor_thread = threading.Thread(target=self._monitor_system_resources)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop performance monitoring"""
        self.monitoring = False
        self.performance_data["end_time"] = datetime.now()
        if self.performance_data["start_time"]:
            self.performance_data["total_duration"] = (
                self.performance_data["end_time"] - self.performance_data["start_time"]
            ).total_seconds()
        
        console.print("[bold red]⏹️ Performance monitoring stopped[/bold red]")
        self._calculate_summary_metrics()
    
    def _monitor_system_resources(self):
        """Background thread to monitor system resources"""
        while self.monitoring:
            try:
                # Get current system metrics
                memory = psutil.virtual_memory()
                cpu_percent = psutil.cpu_percent(interval=1)
                disk_io = psutil.disk_io_counters()
                net_io = psutil.net_io_counters()
                
                # Get process-specific metrics for Python processes
                python_processes = []
                for proc in psutil.process_iter(['pid', 'name', 'memory_percent', 'cpu_percent']):
                    try:
                        if 'python' in proc.info['name'].lower():
                            python_processes.append({
                                'pid': proc.info['pid'],
                                'name': proc.info['name'],
                                'memory_percent': proc.info['memory_percent'],
                                'cpu_percent': proc.info['cpu_percent']
                            })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                metrics = {
                    "timestamp": datetime.now().isoformat(),
                    "memory": {
                        "total": memory.total,
                        "available": memory.available,
                        "percent": memory.percent,
                        "used": memory.used
                    },
                    "cpu_percent": cpu_percent,
                    "disk_io": {
                        "read_bytes": disk_io.read_bytes if disk_io else 0,
                        "write_bytes": disk_io.write_bytes if disk_io else 0
                    },
                    "network_io": {
                        "bytes_sent": net_io.bytes_sent if net_io else 0,
                        "bytes_recv": net_io.bytes_recv if net_io else 0
                    },
                    "python_processes": python_processes
                }
                
                self.metrics_history.append(metrics)
                self.performance_data["system_metrics"].append(metrics)
                
                # Update peak values
                if memory.percent > self.performance_data["resource_usage"]["peak_memory"]:
                    self.performance_data["resource_usage"]["peak_memory"] = memory.percent
                
                if cpu_percent > self.performance_data["resource_usage"]["peak_cpu"]:
                    self.performance_data["resource_usage"]["peak_cpu"] = cpu_percent
                
            except Exception as e:
                console.print(f"[yellow]Warning: Error collecting metrics: {e}[/yellow]")
            
            time.sleep(2)  # Collect metrics every 2 seconds
    
    def track_api_request(self, method: str, endpoint: str, duration: float, status_code: int):
        """Track API request performance"""
        request_data = {
            "timestamp": datetime.now().isoformat(),
            "method": method,
            "endpoint": endpoint,
            "duration": duration,
            "status_code": status_code
        }
        
        self.performance_data["api_response_times"].append(request_data)
    
    def track_task_start(self, task_id: str, task_type: str, parameters: Dict[str, Any]):
        """Track when a task starts"""
        self.active_tasks[task_id] = {
            "task_id": task_id,
            "task_type": task_type,
            "parameters": parameters,
            "start_time": datetime.now(),
            "end_time": None,
            "duration": None,
            "status": "running",
            "error": None
        }
    
    def track_task_end(self, task_id: str, status: str, error: str = None):
        """Track when a task ends"""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            task["end_time"] = datetime.now()
            task["duration"] = (task["end_time"] - task["start_time"]).total_seconds()
            task["status"] = status
            task["error"] = error
            
            # Move to completed tasks
            self.performance_data["task_metrics"].append(task.copy())
            del self.active_tasks[task_id]
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        if not self.metrics_history:
            return {}
        
        latest = self.metrics_history[-1]
        
        # Calculate recent averages (last 10 measurements)
        recent_metrics = list(self.metrics_history)[-10:]
        
        avg_memory = statistics.mean([m["memory"]["percent"] for m in recent_metrics])
        avg_cpu = statistics.mean([m["cpu_percent"] for m in recent_metrics])
        
        return {
            "current": latest,
            "recent_averages": {
                "memory_percent": avg_memory,
                "cpu_percent": avg_cpu
            },
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.performance_data["task_metrics"])
        }
    
    def _calculate_summary_metrics(self):
        """Calculate summary performance metrics"""
        if not self.performance_data["system_metrics"]:
            return
        
        memory_values = [m["memory"]["percent"] for m in self.performance_data["system_metrics"]]
        cpu_values = [m["cpu_percent"] for m in self.performance_data["system_metrics"]]
        
        self.performance_data["resource_usage"]["avg_memory"] = statistics.mean(memory_values)
        self.performance_data["resource_usage"]["avg_cpu"] = statistics.mean(cpu_values)
    
    def test_clip_generation_performance(self, video_id: str = "test-video-123") -> Dict[str, Any]:
        """Test clip generation performance with monitoring"""
        console.print("\n[bold cyan]🎬 Testing Clip Generation Performance...[/bold cyan]")
        
        test_scenarios = [
            {"platform": "youtube", "duration": 60, "name": "YouTube Short"},
            {"platform": "tiktok", "duration": 30, "name": "TikTok Video"},
            {"platform": "instagram", "duration": 45, "name": "Instagram Reel"}
        ]
        
        results = []
        
        for scenario in test_scenarios:
            console.print(f"\n[yellow]Testing: {scenario['name']}[/yellow]")
            
            # Prepare request
            request_data = {
                "platform": scenario["platform"],
                "max_duration": scenario["duration"],
                "aspect_ratio": "9:16"
            }
            
            # Track API request timing
            start_time = time.time()
            
            try:
                response = requests.post(
                    f"{self.api_url}/api/videos/{video_id}/clips",
                    json=request_data,
                    timeout=30
                )
                
                api_duration = time.time() - start_time
                self.track_api_request("POST", f"/api/videos/{video_id}/clips", 
                                     api_duration, response.status_code)
                
                if response.status_code == 200:
                    clip_data = response.json()
                    clip_id = clip_data.get("clip_id")
                    
                    if clip_id:
                        # Track task
                        self.track_task_start(clip_id, "clip_generation", scenario)
                        
                        # Monitor task progress
                        task_result = self._monitor_task_progress(clip_id, scenario["name"])
                        
                        # Track task completion
                        self.track_task_end(clip_id, task_result.get("status", "unknown"), 
                                          task_result.get("error"))
                        
                        results.append({
                            "scenario": scenario["name"],
                            "clip_id": clip_id,
                            "api_response_time": api_duration,
                            "task_result": task_result,
                            "success": task_result.get("success", False)
                        })
                    else:
                        results.append({
                            "scenario": scenario["name"],
                            "error": "No clip_id returned",
                            "api_response_time": api_duration,
                            "success": False
                        })
                else:
                    results.append({
                        "scenario": scenario["name"],
                        "error": f"HTTP {response.status_code}: {response.text}",
                        "api_response_time": api_duration,
                        "success": False
                    })
                    
            except Exception as e:
                results.append({
                    "scenario": scenario["name"],
                    "error": str(e),
                    "success": False
                })
            
            # Small delay between tests
            time.sleep(3)
        
        return results
    
    def _monitor_task_progress(self, clip_id: str, scenario_name: str) -> Dict[str, Any]:
        """Monitor individual task progress"""
        max_wait_time = 300  # 5 minutes
        check_interval = 5   # 5 seconds
        elapsed = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"Monitoring {scenario_name}...", total=max_wait_time)
            
            while elapsed < max_wait_time:
                try:
                    start_time = time.time()
                    status_response = requests.get(
                        f"{self.api_url}/api/clips/{clip_id}/status",
                        timeout=10
                    )
                    api_duration = time.time() - start_time
                    
                    self.track_api_request("GET", f"/api/clips/{clip_id}/status", 
                                         api_duration, status_response.status_code)
                    
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        status = status_data.get("status", "unknown")
                        
                        if status == "completed":
                            return {
                                "success": True,
                                "status": status,
                                "duration": elapsed,
                                "final_check_time": api_duration
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
                    progress.update(task, advance=check_interval)
                    
                except Exception as e:
                    console.print(f"[yellow]Warning: Status check failed: {e}[/yellow]")
                    time.sleep(check_interval)
                    elapsed += check_interval
            
            return {
                "success": False,
                "status": "timeout",
                "duration": elapsed,
                "error": f"Task timed out after {max_wait_time} seconds"
            }
    
    def display_live_metrics(self, duration: int = 60):
        """Display live performance metrics"""
        console.print(f"\n[bold blue]📊 Live Performance Monitoring ({duration}s)[/bold blue]")
        
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        
        def generate_display():
            current_metrics = self.get_current_metrics()
            
            if not current_metrics:
                return Panel("No metrics available yet...", title="Performance Monitor")
            
            current = current_metrics.get("current", {})
            recent = current_metrics.get("recent_averages", {})
            
            # Create metrics table
            table = Table(title="System Performance Metrics")
            table.add_column("Metric", style="cyan")
            table.add_column("Current", style="green")
            table.add_column("Recent Avg", style="yellow")
            table.add_column("Peak", style="red")
            
            # Memory metrics
            memory_current = current.get("memory", {}).get("percent", 0)
            memory_avg = recent.get("memory_percent", 0)
            memory_peak = self.performance_data["resource_usage"]["peak_memory"]
            
            table.add_row(
                "Memory Usage",
                f"{memory_current:.1f}%",
                f"{memory_avg:.1f}%",
                f"{memory_peak:.1f}%"
            )
            
            # CPU metrics
            cpu_current = current.get("cpu_percent", 0)
            cpu_avg = recent.get("cpu_percent", 0)
            cpu_peak = self.performance_data["resource_usage"]["peak_cpu"]
            
            table.add_row(
                "CPU Usage",
                f"{cpu_current:.1f}%",
                f"{cpu_avg:.1f}%",
                f"{cpu_peak:.1f}%"
            )
            
            # Task metrics
            active_tasks = current_metrics.get("active_tasks", 0)
            completed_tasks = current_metrics.get("completed_tasks", 0)
            
            table.add_row(
                "Active Tasks",
                str(active_tasks),
                "-",
                "-"
            )
            
            table.add_row(
                "Completed Tasks",
                str(completed_tasks),
                "-",
                "-"
            )
            
            return table
        
        with Live(generate_display(), refresh_per_second=1, console=console) as live:
            for i in range(duration):
                time.sleep(1)
                live.update(generate_display())
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        if not self.performance_data["start_time"]:
            return {"error": "No monitoring data available"}
        
        # Calculate API performance metrics
        api_times = [req["duration"] for req in self.performance_data["api_response_times"]]
        api_metrics = {}
        
        if api_times:
            api_metrics = {
                "total_requests": len(api_times),
                "avg_response_time": statistics.mean(api_times),
                "min_response_time": min(api_times),
                "max_response_time": max(api_times),
                "median_response_time": statistics.median(api_times)
            }
        
        # Calculate task performance metrics
        completed_tasks = [task for task in self.performance_data["task_metrics"] if task["duration"]]
        task_metrics = {}
        
        if completed_tasks:
            task_durations = [task["duration"] for task in completed_tasks]
            successful_tasks = [task for task in completed_tasks if task["status"] == "completed"]
            
            task_metrics = {
                "total_tasks": len(completed_tasks),
                "successful_tasks": len(successful_tasks),
                "success_rate": (len(successful_tasks) / len(completed_tasks)) * 100,
                "avg_duration": statistics.mean(task_durations),
                "min_duration": min(task_durations),
                "max_duration": max(task_durations),
                "median_duration": statistics.median(task_durations)
            }
        
        return {
            "monitoring_period": {
                "start_time": self.performance_data["start_time"].isoformat(),
                "end_time": self.performance_data["end_time"].isoformat() if self.performance_data["end_time"] else None,
                "total_duration": self.performance_data["total_duration"]
            },
            "resource_usage": self.performance_data["resource_usage"],
            "api_performance": api_metrics,
            "task_performance": task_metrics,
            "system_metrics_count": len(self.performance_data["system_metrics"])
        }
    
    def save_performance_data(self, filename: str = None):
        """Save performance data to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_report_{timestamp}.json"
        
        report = self.generate_performance_report()
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        console.print(f"\n📄 Performance report saved to: [cyan]{filename}[/cyan]")
        return filename

def main():
    """Main function for performance monitoring"""
    monitor = PerformanceMonitor()
    
    try:
        # Start monitoring
        monitor.start_monitoring()
        
        # Run performance tests
        console.print("\n[bold green]🚀 Starting Performance Testing[/bold green]")
        
        # Test clip generation performance
        test_results = monitor.test_clip_generation_performance()
        
        # Display live metrics for a short period
        monitor.display_live_metrics(30)
        
        # Stop monitoring
        monitor.stop_monitoring()
        
        # Generate and save report
        report_file = monitor.save_performance_data()
        
        # Display summary
        console.print("\n[bold blue]📊 Performance Test Summary[/bold blue]")
        
        summary_table = Table(title="Test Results Summary")
        summary_table.add_column("Scenario", style="cyan")
        summary_table.add_column("Status", style="magenta")
        summary_table.add_column("API Response", style="green")
        summary_table.add_column("Notes", style="yellow")
        
        for result in test_results:
            status_emoji = "✅" if result.get("success", False) else "❌"
            status = f"{status_emoji} {'Success' if result.get('success', False) else 'Failed'}"
            
            api_time = result.get("api_response_time", 0)
            api_response = f"{api_time:.3f}s" if api_time else "N/A"
            
            notes = result.get("error", "Success") if not result.get("success", False) else "Success"
            
            summary_table.add_row(
                result.get("scenario", "Unknown"),
                status,
                api_response,
                notes
            )
        
        console.print(summary_table)
        
        # Overall success
        successful_tests = sum(1 for r in test_results if r.get("success", False))
        total_tests = len(test_results)
        
        if successful_tests == total_tests:
            console.print(f"\n[bold green]🎉 All {total_tests} performance tests passed![/bold green]")
        else:
            console.print(f"\n[bold yellow]⚠️ {successful_tests}/{total_tests} tests passed[/bold yellow]")
        
        sys.exit(0 if successful_tests == total_tests else 1)
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Performance monitoring interrupted by user[/yellow]")
        monitor.stop_monitoring()
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Error during performance monitoring: {e}[/red]")
        monitor.stop_monitoring()
        sys.exit(1)

if __name__ == "__main__":
    main()