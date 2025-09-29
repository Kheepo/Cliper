#!/usr/bin/env python3
"""
System Status Checker for Cliper Application
Verifies all services (API, Redis, Celery) are running and healthy
"""

import asyncio
import json
import time
import psutil
import requests
import redis
from datetime import datetime
from typing import Dict, List, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
import subprocess
import sys
import os

console = Console()

class SystemStatusChecker:
    def __init__(self):
        self.api_url = "http://localhost:8001"
        self.redis_url = "redis://localhost:6379/0"
        self.status_results = {}
        
    def check_redis_status(self) -> Dict[str, Any]:
        """Check Redis server status"""
        try:
            r = redis.Redis.from_url(self.redis_url)
            ping_result = r.ping()
            info = r.info()
            
            return {
                "status": "healthy" if ping_result else "unhealthy",
                "ping": ping_result,
                "memory_usage": info.get('used_memory_human', 'N/A'),
                "connected_clients": info.get('connected_clients', 0),
                "uptime": info.get('uptime_in_seconds', 0),
                "error": None
            }
        except Exception as e:
            return {
                "status": "error",
                "ping": False,
                "error": str(e)
            }
    
    def check_api_status(self) -> Dict[str, Any]:
        """Check API server status"""
        try:
            # Health check
            response = requests.get(f"{self.api_url}/health", timeout=5)
            health_data = response.json() if response.status_code == 200 else {}
            
            # Check specific endpoints
            endpoints_status = {}
            test_endpoints = [
                "/api/videos/",
                "/api/videos/upload",
            ]
            
            for endpoint in test_endpoints:
                try:
                    resp = requests.get(f"{self.api_url}{endpoint}", timeout=3)
                    endpoints_status[endpoint] = {
                        "status_code": resp.status_code,
                        "accessible": resp.status_code in [200, 401, 422]  # 401/422 are expected without auth
                    }
                except Exception as e:
                    endpoints_status[endpoint] = {
                        "status_code": None,
                        "accessible": False,
                        "error": str(e)
                    }
            
            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "status_code": response.status_code,
                "health_data": health_data,
                "endpoints": endpoints_status,
                "error": None
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def check_celery_status(self) -> Dict[str, Any]:
        """Check Celery worker status"""
        try:
            # Try to connect to Redis and check for Celery workers
            r = redis.Redis.from_url(self.redis_url)
            
            # Check for active workers
            result = subprocess.run(
                ["celery", "-A", "api.celery_app", "inspect", "active"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=os.getcwd()
            )
            
            if result.returncode == 0:
                # Parse the output to check for workers
                output = result.stdout
                workers_active = "celery@" in output
                
                return {
                    "status": "healthy" if workers_active else "no_workers",
                    "workers_active": workers_active,
                    "output": output,
                    "error": None
                }
            else:
                return {
                    "status": "error",
                    "workers_active": False,
                    "error": result.stderr
                }
                
        except Exception as e:
            return {
                "status": "error",
                "workers_active": False,
                "error": str(e)
            }
    
    def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage"""
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('C:\\' if os.name == 'nt' else '/')
            cpu_percent = psutil.cpu_percent(interval=1)
            
            return {
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used
                },
                "disk": {
                    "total": disk.total,
                    "free": disk.free,
                    "percent": (disk.used / disk.total) * 100
                },
                "cpu_percent": cpu_percent,
                "status": "healthy"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def check_video_files(self) -> Dict[str, Any]:
        """Check for test video files and clip output directory"""
        try:
            video_dirs = ["uploads/videos", "api/uploads/videos", "test_files"]
            clip_dirs = ["uploads/clips", "api/uploads/clips"]
            
            video_files = []
            clip_files = []
            
            for dir_path in video_dirs:
                if os.path.exists(dir_path):
                    for file in os.listdir(dir_path):
                        if file.endswith(('.mp4', '.avi', '.mov', '.mkv')):
                            file_path = os.path.join(dir_path, file)
                            video_files.append({
                                "name": file,
                                "path": file_path,
                                "size": os.path.getsize(file_path)
                            })
            
            for dir_path in clip_dirs:
                if os.path.exists(dir_path):
                    for file in os.listdir(dir_path):
                        if file.endswith(('.mp4', '.avi', '.mov', '.mkv')):
                            file_path = os.path.join(dir_path, file)
                            clip_files.append({
                                "name": file,
                                "path": file_path,
                                "size": os.path.getsize(file_path)
                            })
            
            return {
                "status": "healthy",
                "video_files": video_files,
                "clip_files": clip_files,
                "video_count": len(video_files),
                "clip_count": len(clip_files)
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def run_comprehensive_check(self) -> Dict[str, Any]:
        """Run all status checks"""
        console.print("\n[bold blue]🔍 Running Comprehensive System Status Check[/bold blue]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            
            # Redis Check
            task1 = progress.add_task("Checking Redis server...", total=None)
            redis_status = self.check_redis_status()
            progress.update(task1, completed=True)
            
            # API Check
            task2 = progress.add_task("Checking API server...", total=None)
            api_status = self.check_api_status()
            progress.update(task2, completed=True)
            
            # Celery Check
            task3 = progress.add_task("Checking Celery workers...", total=None)
            celery_status = self.check_celery_status()
            progress.update(task3, completed=True)
            
            # System Resources
            task4 = progress.add_task("Checking system resources...", total=None)
            system_status = self.check_system_resources()
            progress.update(task4, completed=True)
            
            # Video Files
            task5 = progress.add_task("Checking video files...", total=None)
            video_status = self.check_video_files()
            progress.update(task5, completed=True)
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "redis": redis_status,
            "api": api_status,
            "celery": celery_status,
            "system": system_status,
            "videos": video_status
        }
        
        self.status_results = results
        return results
    
    def display_results(self, results: Dict[str, Any]):
        """Display results in a formatted table"""
        
        # Create main status table
        table = Table(title="🚀 System Status Overview")
        table.add_column("Service", style="cyan", no_wrap=True)
        table.add_column("Status", style="magenta")
        table.add_column("Details", style="green")
        
        # Redis status
        redis_status = results["redis"]["status"]
        redis_emoji = "✅" if redis_status == "healthy" else "❌"
        redis_details = f"Ping: {results['redis'].get('ping', 'N/A')}"
        if redis_status == "healthy":
            redis_details += f" | Memory: {results['redis'].get('memory_usage', 'N/A')}"
        table.add_row("Redis", f"{redis_emoji} {redis_status.title()}", redis_details)
        
        # API status
        api_status = results["api"]["status"]
        api_emoji = "✅" if api_status == "healthy" else "❌"
        api_details = f"Status Code: {results['api'].get('status_code', 'N/A')}"
        table.add_row("API Server", f"{api_emoji} {api_status.title()}", api_details)
        
        # Celery status
        celery_status = results["celery"]["status"]
        celery_emoji = "✅" if celery_status == "healthy" else "❌"
        celery_details = f"Workers Active: {results['celery'].get('workers_active', False)}"
        table.add_row("Celery Worker", f"{celery_emoji} {celery_status.title()}", celery_details)
        
        # System resources
        system_status = results["system"]["status"]
        system_emoji = "✅" if system_status == "healthy" else "❌"
        if system_status == "healthy":
            memory_percent = results["system"]["memory"]["percent"]
            cpu_percent = results["system"]["cpu_percent"]
            system_details = f"Memory: {memory_percent:.1f}% | CPU: {cpu_percent:.1f}%"
        else:
            system_details = "Error checking resources"
        table.add_row("System Resources", f"{system_emoji} {system_status.title()}", system_details)
        
        # Video files
        video_status = results["videos"]["status"]
        video_emoji = "✅" if video_status == "healthy" else "❌"
        video_count = results["videos"].get("video_count", 0)
        clip_count = results["videos"].get("clip_count", 0)
        video_details = f"Videos: {video_count} | Clips: {clip_count}"
        table.add_row("Video Files", f"{video_emoji} {video_status.title()}", video_details)
        
        console.print(table)
        
        # Show detailed errors if any
        errors = []
        for service, data in results.items():
            if isinstance(data, dict) and data.get("error"):
                errors.append(f"[red]{service.title()}: {data['error']}[/red]")
        
        if errors:
            console.print("\n[bold red]⚠️ Errors Found:[/bold red]")
            for error in errors:
                console.print(f"  • {error}")
        
        # Overall status
        all_healthy = all(
            data.get("status") == "healthy" 
            for data in results.values() 
            if isinstance(data, dict) and "status" in data
        )
        
        if all_healthy:
            console.print("\n[bold green]🎉 All systems are healthy and ready for testing![/bold green]")
        else:
            console.print("\n[bold yellow]⚠️ Some issues detected. Please review the errors above.[/bold yellow]")
        
        return all_healthy
    
    def save_results(self, results: Dict[str, Any], filename: str = None):
        """Save results to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"system_status_report_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        console.print(f"\n📄 Status report saved to: [cyan]{filename}[/cyan]")
        return filename

def main():
    """Main function to run system status check"""
    checker = SystemStatusChecker()
    
    try:
        results = checker.run_comprehensive_check()
        all_healthy = checker.display_results(results)
        report_file = checker.save_results(results)
        
        # Return exit code based on system health
        sys.exit(0 if all_healthy else 1)
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Status check interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Error during status check: {e}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    main