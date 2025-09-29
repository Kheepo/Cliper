#!/usr/bin/env python3
"""
Comprehensive Video Functionality Verification Script
Senior Software Engineer Production Readiness Assessment

This script conducts thorough verification of all video functionality components
for production deployment readiness.
"""

import os
import sys
import json
import time
import asyncio
import logging
import subprocess
import tempfile
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add API path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

@dataclass
class TestResult:
    """Test result data structure."""
    component: str
    test_name: str
    status: str  # PASS, FAIL, SKIP
    duration: float
    details: str
    critical: bool = False
    performance_metrics: Optional[Dict] = None

class VideoFunctionalityVerifier:
    """Comprehensive video functionality verification system."""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time = time.time()
        self.setup_logging()
        self.api_base_url = "http://localhost:8000"
        self.test_video_path = None
        self.temp_dir = tempfile.mkdtemp()
        
    def setup_logging(self):
        """Setup comprehensive logging."""
        log_dir = Path("verification_logs")
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"video_verification_{timestamp}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("Video Functionality Verification Started")
    
    def add_result(self, component: str, test_name: str, status: str, 
                   duration: float, details: str, critical: bool = False,
                   performance_metrics: Optional[Dict] = None):
        """Add test result."""
        result = TestResult(
            component=component,
            test_name=test_name,
            status=status,
            duration=duration,
            details=details,
            critical=critical,
            performance_metrics=performance_metrics
        )
        self.results.append(result)
        
        status_marker = "[PASS]" if status == "PASS" else "[FAIL]" if status == "FAIL" else "[SKIP]"
        critical_marker = " [CRITICAL]" if critical else ""
        self.logger.info(f"{status_marker} {component}.{test_name}: {status}{critical_marker} ({duration:.2f}s)")
        
        if status == "FAIL" and critical:
            self.logger.error(f"CRITICAL FAILURE: {details}")
    
    def create_test_video(self) -> str:
        """Create a test video file for verification."""
        test_video = os.path.join(self.temp_dir, "test_video.mp4")
        
        # Create a simple test video using FFmpeg
        # First check if ffmpeg is available
        ffmpeg_cmd = self.find_ffmpeg_executable()
        if not ffmpeg_cmd:
            self.logger.warning("FFmpeg not found, skipping test video creation")
            return None
            
        cmd = [
            ffmpeg_cmd, "-f", "lavfi", "-i", "testsrc=duration=10:size=1920x1080:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=10",
            "-c:v", "libx264", "-c:a", "aac", "-y", test_video
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            self.test_video_path = test_video
            return test_video
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to create test video: {e}")
            return None
    
    def find_ffmpeg_executable(self) -> Optional[str]:
        """Find FFmpeg executable in system PATH or common locations."""
        # Common FFmpeg locations on Windows
        common_paths = [
            "ffmpeg",
            "ffmpeg.exe",
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
            "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
            "C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe"
        ]
        
        for path in common_paths:
            try:
                result = subprocess.run([path, "-version"], 
                                      capture_output=True, timeout=5)
                if result.returncode == 0:
                    return path
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue
        
        return None
    
    def verify_ffmpeg_installation(self) -> bool:
        """Verify FFmpeg installation and capabilities."""
        start_time = time.time()
        
        try:
            # Check FFmpeg version
            ffmpeg_cmd = self.find_ffmpeg_executable()
            if not ffmpeg_cmd:
                self.add_result("FFmpeg", "installation_verification", "FAIL", 
                              time.time() - start_time, "FFmpeg not found in system", critical=True)
                return False
                
            result = subprocess.run([ffmpeg_cmd, "-version"], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                version_info = result.stdout.split('\n')[0]
                
                # Check for required codecs
                codec_result = subprocess.run([ffmpeg_cmd, "-codecs"], 
                                            capture_output=True, text=True, timeout=10)
                
                required_codecs = ['libx264', 'aac', 'libvpx']
                missing_codecs = []
                
                for codec in required_codecs:
                    if codec not in codec_result.stdout:
                        missing_codecs.append(codec)
                
                if missing_codecs:
                    details = f"Missing codecs: {', '.join(missing_codecs)}"
                    self.add_result("FFmpeg", "codec_verification", "FAIL", 
                                  time.time() - start_time, details, critical=True)
                    return False
                
                self.add_result("FFmpeg", "installation_verification", "PASS", 
                              time.time() - start_time, f"Version: {version_info}")
                return True
            else:
                self.add_result("FFmpeg", "installation_verification", "FAIL", 
                              time.time() - start_time, "FFmpeg not found", critical=True)
                return False
                
        except Exception as e:
            self.add_result("FFmpeg", "installation_verification", "FAIL", 
                          time.time() - start_time, str(e), critical=True)
            return False
    
    def verify_clip_generation_accuracy(self):
        """Verify clip generation accuracy across platforms."""
        self.logger.info("Verifying Clip Generation Accuracy")
        
        platforms = [
            {"name": "youtube", "aspect_ratio": "16:9", "resolution": "1920x1080"},
            {"name": "tiktok", "aspect_ratio": "9:16", "resolution": "1080x1920"},
            {"name": "instagram_feed", "aspect_ratio": "1:1", "resolution": "1080x1080"},
            {"name": "instagram_stories", "aspect_ratio": "9:16", "resolution": "1080x1920"}
        ]
        
        for platform in platforms:
            start_time = time.time()
            
            try:
                # Test platform configuration
                sys.path.insert(0, 'api')
                from tasks import _get_platform_config
                
                config = _get_platform_config(platform["name"])
                
                if config:
                    # Verify configuration matches expected values
                    expected_resolution = platform["resolution"]
                    if config.get("resolution") == expected_resolution:
                        self.add_result("ClipGeneration", f"{platform['name']}_config", "PASS", 
                                      time.time() - start_time, 
                                      f"Configuration valid: {config['resolution']}")
                    else:
                        self.add_result("ClipGeneration", f"{platform['name']}_config", "FAIL", 
                                      time.time() - start_time, 
                                      f"Resolution mismatch: expected {expected_resolution}, got {config.get('resolution')}",
                                      critical=True)
                else:
                    self.add_result("ClipGeneration", f"{platform['name']}_config", "FAIL", 
                                  time.time() - start_time, "No configuration returned", critical=True)
                    
            except Exception as e:
                self.add_result("ClipGeneration", f"{platform['name']}_config", "FAIL", 
                              time.time() - start_time, str(e), critical=True)
    
    def verify_video_processing_pipeline(self):
        """Verify video processing pipeline functionality."""
        self.logger.info("Verifying Video Processing Pipeline")
        
        if not self.test_video_path:
            self.add_result("VideoProcessing", "pipeline_test", "SKIP", 0, 
                          "No test video available", critical=True)
            return
        
        start_time = time.time()
        
        try:
            # Test basic video processing
            output_path = os.path.join(self.temp_dir, "processed_test.mp4")
            
            cmd = [
                "ffmpeg", "-i", self.test_video_path,
                "-t", "10",  # 10 second clip
                "-c:v", "libx264", "-c:a", "aac",
                "-y", output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            
            if result.returncode == 0 and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                self.add_result("VideoProcessing", "basic_processing", "PASS", 
                              time.time() - start_time, 
                              f"Processed video created: {file_size} bytes")
            else:
                self.add_result("VideoProcessing", "basic_processing", "FAIL", 
                              time.time() - start_time, 
                              f"Processing failed: {result.stderr.decode()}", critical=True)
                
        except Exception as e:
            self.add_result("VideoProcessing", "basic_processing", "FAIL", 
                          time.time() - start_time, str(e), critical=True)
    
    def verify_api_endpoints(self):
        """Verify API endpoints functionality."""
        self.logger.info("Verifying API Endpoints")
        
        endpoints = [
            {
                "name": "health_check",
                "url": f"{self.api_base_url}/health",
                "method": "GET",
                "expected_status": 200
            },
            {
                "name": "api_docs",
                "url": f"{self.api_base_url}/docs",
                "method": "GET",
                "expected_status": 200
            }
        ]
        
        for endpoint in endpoints:
            start_time = time.time()
            
            try:
                response = requests.get(endpoint["url"], timeout=10)
                
                if response.status_code == endpoint["expected_status"]:
                    self.add_result("API", endpoint["name"], "PASS", 
                                  time.time() - start_time, 
                                  f"Status: {response.status_code}")
                else:
                    self.add_result("API", endpoint["name"], "FAIL", 
                                  time.time() - start_time, 
                                  f"Expected {endpoint['expected_status']}, got {response.status_code}")
                    
            except requests.exceptions.ConnectionError:
                self.add_result("API", endpoint["name"], "SKIP", 
                              time.time() - start_time, "API server not running")
            except Exception as e:
                self.add_result("API", endpoint["name"], "FAIL", 
                              time.time() - start_time, str(e))
    
    def verify_performance_benchmarks(self):
        """Verify performance benchmarks."""
        self.logger.info("Verifying Performance Benchmarks")
        
        # Memory usage test
        start_time = time.time()
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            performance_metrics = {
                "memory_usage_mb": memory_mb,
                "cpu_percent": process.cpu_percent()
            }
            
            if memory_mb < 500:  # Less than 500MB
                self.add_result("Performance", "memory_usage", "PASS", 
                              time.time() - start_time, 
                              f"Memory usage: {memory_mb:.2f}MB",
                              performance_metrics=performance_metrics)
            else:
                self.add_result("Performance", "memory_usage", "FAIL", 
                              time.time() - start_time, 
                              f"High memory usage: {memory_mb:.2f}MB",
                              performance_metrics=performance_metrics)
                
        except Exception as e:
            self.add_result("Performance", "memory_usage", "FAIL", 
                          time.time() - start_time, str(e))
    
    def verify_security_components(self):
        """Verify security components."""
        self.logger.info("Verifying Security Components")
        
        start_time = time.time()
        
        try:
            # Check if security middleware is available
            sys.path.insert(0, 'api')
            
            security_components = [
                "middleware.security",
                "middleware.auth",
                "security.hardening"
            ]
            
            available_components = []
            missing_components = []
            
            for component in security_components:
                try:
                    __import__(component)
                    available_components.append(component)
                except ImportError:
                    missing_components.append(component)
            
            if missing_components:
                self.add_result("Security", "component_availability", "FAIL", 
                              time.time() - start_time, 
                              f"Missing components: {', '.join(missing_components)}",
                              critical=True)
            else:
                self.add_result("Security", "component_availability", "PASS", 
                              time.time() - start_time, 
                              f"All components available: {', '.join(available_components)}")
                
        except Exception as e:
            self.add_result("Security", "component_availability", "FAIL", 
                          time.time() - start_time, str(e))
    
    def verify_cross_platform_compatibility(self):
        """Verify cross-platform compatibility."""
        self.logger.info("Verifying Cross-Platform Compatibility")
        
        start_time = time.time()
        
        try:
            import platform
            system_info = {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "python_version": platform.python_version()
            }
            
            # Check Python version compatibility
            python_version = tuple(map(int, platform.python_version().split('.')))
            
            if python_version >= (3, 8):
                self.add_result("Compatibility", "python_version", "PASS", 
                              time.time() - start_time, 
                              f"Python {platform.python_version()} supported")
            else:
                self.add_result("Compatibility", "python_version", "FAIL", 
                              time.time() - start_time, 
                              f"Python {platform.python_version()} not supported (requires 3.8+)",
                              critical=True)
            
            # Check OS compatibility
            supported_os = ["Windows", "Linux", "Darwin"]  # Darwin = macOS
            if system_info["system"] in supported_os:
                self.add_result("Compatibility", "operating_system", "PASS", 
                              time.time() - start_time, 
                              f"OS {system_info['system']} supported")
            else:
                self.add_result("Compatibility", "operating_system", "FAIL", 
                              time.time() - start_time, 
                              f"OS {system_info['system']} not officially supported")
                
        except Exception as e:
            self.add_result("Compatibility", "system_check", "FAIL", 
                          time.time() - start_time, str(e))
    
    def generate_comprehensive_report(self) -> Dict[str, Any]:
        """Generate comprehensive verification report."""
        total_duration = time.time() - self.start_time
        
        # Categorize results
        passed = [r for r in self.results if r.status == "PASS"]
        failed = [r for r in self.results if r.status == "FAIL"]
        skipped = [r for r in self.results if r.status == "SKIP"]
        critical_failures = [r for r in failed if r.critical]
        
        # Calculate success rate
        total_tests = len(self.results)
        success_rate = (len(passed) / total_tests * 100) if total_tests > 0 else 0
        
        # Determine production readiness
        production_ready = len(critical_failures) == 0 and success_rate >= 80
        
        report = {
            "verification_summary": {
                "timestamp": datetime.now().isoformat(),
                "total_duration_seconds": round(total_duration, 2),
                "total_tests": total_tests,
                "passed": len(passed),
                "failed": len(failed),
                "skipped": len(skipped),
                "success_rate_percent": round(success_rate, 2),
                "critical_failures": len(critical_failures),
                "production_ready": production_ready
            },
            "component_breakdown": {},
            "critical_issues": [],
            "performance_metrics": {},
            "recommendations": []
        }
        
        # Group results by component
        components = {}
        for result in self.results:
            if result.component not in components:
                components[result.component] = []
            components[result.component].append(result)
        
        # Generate component breakdown
        for component, results in components.items():
            component_passed = len([r for r in results if r.status == "PASS"])
            component_total = len(results)
            component_success_rate = (component_passed / component_total * 100) if component_total > 0 else 0
            
            report["component_breakdown"][component] = {
                "total_tests": component_total,
                "passed": component_passed,
                "failed": len([r for r in results if r.status == "FAIL"]),
                "skipped": len([r for r in results if r.status == "SKIP"]),
                "success_rate_percent": round(component_success_rate, 2),
                "tests": [
                    {
                        "name": r.test_name,
                        "status": r.status,
                        "duration": r.duration,
                        "details": r.details,
                        "critical": r.critical
                    } for r in results
                ]
            }
        
        # Collect critical issues
        for failure in critical_failures:
            report["critical_issues"].append({
                "component": failure.component,
                "test": failure.test_name,
                "details": failure.details
            })
        
        # Collect performance metrics
        for result in self.results:
            if result.performance_metrics:
                report["performance_metrics"][f"{result.component}.{result.test_name}"] = result.performance_metrics
        
        # Generate recommendations
        if critical_failures:
            report["recommendations"].append("[CRITICAL] Resolve all critical failures before production deployment")
        
        if success_rate < 80:
            report["recommendations"].append("[WARNING] Improve test success rate to at least 80% for production readiness")
        
        if len(skipped) > 0:
            report["recommendations"].append(f"[INFO] Review and address {len(skipped)} skipped tests")
        
        if production_ready:
            report["recommendations"].append("[SUCCESS] System appears ready for production deployment")
        else:
            report["recommendations"].append("[CRITICAL] System NOT ready for production deployment")
        
        return report
    
    def run_comprehensive_verification(self):
        """Run comprehensive video functionality verification."""
        self.logger.info("Starting Comprehensive Video Functionality Verification")
        
        # Create test video
        self.logger.info("Creating test video...")
        self.create_test_video()
        
        # Run all verification tests
        verification_steps = [
            self.verify_ffmpeg_installation,
            self.verify_clip_generation_accuracy,
            self.verify_video_processing_pipeline,
            self.verify_api_endpoints,
            self.verify_performance_benchmarks,
            self.verify_security_components,
            self.verify_cross_platform_compatibility
        ]
        
        for step in verification_steps:
            try:
                step()
            except Exception as e:
                self.logger.error(f"Verification step failed: {step.__name__}: {e}")
                self.add_result("System", step.__name__, "FAIL", 0, str(e), critical=True)
        
        # Generate and save report
        report = self.generate_comprehensive_report()
        
        # Save report to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"video_verification_report_{timestamp}.json"
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.logger.info(f"Verification report saved to: {report_file}")
        
        # Print summary
        self.print_summary(report)
        
        return report
    
    def print_summary(self, report: Dict[str, Any]):
        """Print verification summary."""
        summary = report["verification_summary"]
        
        print("\n" + "="*80)
        print("VIDEO FUNCTIONALITY VERIFICATION SUMMARY")
        print("="*80)
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Skipped: {summary['skipped']}")
        print(f"Success Rate: {summary['success_rate_percent']}%")
        print(f"Critical Failures: {summary['critical_failures']}")
        print(f"Total Duration: {summary['total_duration_seconds']}s")
        
        if summary['production_ready']:
            print("\n[SUCCESS] PRODUCTION READY: System passed verification!")
        else:
            print("\n[CRITICAL] NOT PRODUCTION READY: Critical issues found!")
        
        if report['critical_issues']:
            print("\nCRITICAL ISSUES:")
            for issue in report['critical_issues']:
                print(f"   - {issue['component']}.{issue['test']}: {issue['details']}")
        
        print("\nRECOMMENDATIONS:")
        for rec in report['recommendations']:
            print(f"   - {rec}")
        
        print("\n" + "="*80)

def main():
    """Main verification function."""
    verifier = VideoFunctionalityVerifier()
    
    try:
        report = verifier.run_comprehensive_verification()
        
        # Exit with appropriate code
        if report["verification_summary"]["production_ready"]:
            sys.exit(0)  # Success
        else:
            sys.exit(1)  # Failure
            
    except KeyboardInterrupt:
        print("\n[WARNING] Verification interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n[ERROR] Verification failed with error: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        if hasattr(verifier, 'temp_dir') and os.path.exists(verifier.temp_dir):
            import shutil
            shutil.rmtree(verifier.temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()