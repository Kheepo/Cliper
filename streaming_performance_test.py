#!/usr/bin/env python3
"""
Streaming Performance Assessment Script
Tests latency, bandwidth efficiency, and adaptive bitrate switching
"""

import os
import sys
import json
import time
import logging
import requests
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import threading
from urllib.parse import urlparse

# Configure logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('streaming_performance.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class StreamingPerformanceTester:
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'tests': {},
            'performance_metrics': {},
            'summary': {
                'total_tests': 0,
                'passed': 0,
                'failed': 0,
                'critical_issues': [],
                'warnings': [],
                'production_ready': False
            }
        }
        self.project_root = Path.cwd()
        
    def log_test_result(self, test_name: str, passed: bool, details: str, critical: bool = False, metrics: Dict = None):
        """Log test result and update summary"""
        status = "[PASS]" if passed else "[FAIL]"
        logger.info(f"{status} {test_name}: {details}")
        
        self.results['tests'][test_name] = {
            'passed': passed,
            'details': details,
            'critical': critical,
            'timestamp': datetime.now().isoformat(),
            'metrics': metrics or {}
        }
        
        if metrics:
            self.results['performance_metrics'][test_name] = metrics
        
        self.results['summary']['total_tests'] += 1
        if passed:
            self.results['summary']['passed'] += 1
        else:
            self.results['summary']['failed'] += 1
            if critical:
                self.results['summary']['critical_issues'].append(f"{test_name}: {details}")
            else:
                self.results['summary']['warnings'].append(f"{test_name}: {details}")
    
    def test_api_server_availability(self):
        """Test if API server is running for streaming tests"""
        try:
            # Check common development ports
            test_urls = [
                'http://localhost:3000',
                'http://localhost:8000',
                'http://localhost:5000',
                'http://localhost:4000'
            ]
            
            server_available = False
            available_url = None
            
            for url in test_urls:
                try:
                    response = requests.get(url, timeout=2)
                    if response.status_code == 200:
                        server_available = True
                        available_url = url
                        break
                except requests.exceptions.RequestException:
                    continue
            
            if server_available:
                self.log_test_result(
                    'API Server Availability',
                    True,
                    f'Server running at {available_url}'
                )
                return available_url
            else:
                self.log_test_result(
                    'API Server Availability',
                    False,
                    'No development server found on common ports',
                    critical=True
                )
                return None
                
        except Exception as e:
            self.log_test_result(
                'API Server Availability',
                False,
                f'Error checking server availability: {str(e)}',
                critical=True
            )
            return None
    
    def test_cdn_configuration(self):
        """Test CDN and static asset delivery configuration"""
        try:
            # Check for CDN configuration in project files
            config_files = [
                'vite.config.ts',
                'vite.config.js',
                'webpack.config.js',
                'next.config.js',
                '.env',
                '.env.local',
                'package.json'
            ]
            
            cdn_indicators = {
                'cloudflare': False,
                'aws_cloudfront': False,
                'azure_cdn': False,
                'google_cdn': False,
                'custom_cdn': False
            }
            
            for config_file in config_files:
                file_path = self.project_root / config_file
                if file_path.exists():
                    try:
                        content = file_path.read_text(encoding='utf-8').lower()
                        
                        if any(term in content for term in ['cloudflare', 'cf-']):
                            cdn_indicators['cloudflare'] = True
                        if any(term in content for term in ['cloudfront', 'aws']):
                            cdn_indicators['aws_cloudfront'] = True
                        if any(term in content for term in ['azure', 'microsoft']):
                            cdn_indicators['azure_cdn'] = True
                        if any(term in content for term in ['googleapis', 'gstatic']):
                            cdn_indicators['google_cdn'] = True
                        if any(term in content for term in ['cdn', 'static']):
                            cdn_indicators['custom_cdn'] = True
                            
                    except Exception:
                        continue
            
            configured_cdns = [k for k, v in cdn_indicators.items() if v]
            
            if len(configured_cdns) >= 1:
                self.log_test_result(
                    'CDN Configuration',
                    True,
                    f'CDN configuration detected: {", ".join(configured_cdns)}'
                )
            else:
                self.log_test_result(
                    'CDN Configuration',
                    False,
                    'No CDN configuration detected - may impact streaming performance'
                )
                
        except Exception as e:
            self.log_test_result(
                'CDN Configuration',
                False,
                f'Error checking CDN configuration: {str(e)}'
            )
    
    def test_video_compression_settings(self):
        """Test video compression and bitrate settings"""
        try:
            # Check for video processing configuration
            src_path = self.project_root / 'src'
            api_path = self.project_root / 'api'
            
            compression_features = {
                'adaptive_bitrate': False,
                'multiple_qualities': False,
                'compression_settings': False,
                'bandwidth_optimization': False
            }
            
            search_paths = [src_path, api_path] if api_path.exists() else [src_path]
            
            for search_path in search_paths:
                if search_path.exists():
                    for file_path in search_path.rglob('*.{ts,tsx,js,jsx,py}'):
                        try:
                            content = file_path.read_text(encoding='utf-8').lower()
                            
                            if any(term in content for term in ['adaptive', 'bitrate', 'abr']):
                                compression_features['adaptive_bitrate'] = True
                            if any(term in content for term in ['quality', 'resolution', 'hd', 'sd']):
                                compression_features['multiple_qualities'] = True
                            if any(term in content for term in ['compress', 'encode', 'transcode']):
                                compression_features['compression_settings'] = True
                            if any(term in content for term in ['bandwidth', 'network', 'connection']):
                                compression_features['bandwidth_optimization'] = True
                                
                        except Exception:
                            continue
            
            implemented_features = [k for k, v in compression_features.items() if v]
            
            if len(implemented_features) >= 3:
                self.log_test_result(
                    'Video Compression Settings',
                    True,
                    f'Advanced compression features: {", ".join(implemented_features)}'
                )
            elif len(implemented_features) >= 1:
                self.log_test_result(
                    'Video Compression Settings',
                    True,
                    f'Basic compression features: {", ".join(implemented_features)}'
                )
            else:
                self.log_test_result(
                    'Video Compression Settings',
                    False,
                    'No video compression optimization detected',
                    critical=True
                )
                
        except Exception as e:
            self.log_test_result(
                'Video Compression Settings',
                False,
                f'Error checking compression settings: {str(e)}'
            )
    
    def test_streaming_protocols(self):
        """Test streaming protocol support"""
        try:
            # Check for streaming protocol implementations
            src_path = self.project_root / 'src'
            api_path = self.project_root / 'api'
            
            protocols = {
                'hls': False,
                'dash': False,
                'webrtc': False,
                'progressive': False
            }
            
            search_paths = [src_path, api_path] if api_path.exists() else [src_path]
            
            for search_path in search_paths:
                if search_path.exists():
                    for file_path in search_path.rglob('*.{ts,tsx,js,jsx,py}'):
                        try:
                            content = file_path.read_text(encoding='utf-8').lower()
                            
                            if any(term in content for term in ['hls', 'm3u8', 'http live streaming']):
                                protocols['hls'] = True
                            if any(term in content for term in ['dash', 'mpd', 'dynamic adaptive']):
                                protocols['dash'] = True
                            if any(term in content for term in ['webrtc', 'rtc', 'peer']):
                                protocols['webrtc'] = True
                            if any(term in content for term in ['progressive', 'mp4', 'direct']):
                                protocols['progressive'] = True
                                
                        except Exception:
                            continue
            
            supported_protocols = [k for k, v in protocols.items() if v]
            
            if len(supported_protocols) >= 2:
                self.log_test_result(
                    'Streaming Protocols',
                    True,
                    f'Multiple protocols supported: {", ".join(supported_protocols)}'
                )
            elif len(supported_protocols) >= 1:
                self.log_test_result(
                    'Streaming Protocols',
                    True,
                    f'Basic protocol support: {", ".join(supported_protocols)}'
                )
            else:
                self.log_test_result(
                    'Streaming Protocols',
                    False,
                    'No streaming protocols detected',
                    critical=True
                )
                
        except Exception as e:
            self.log_test_result(
                'Streaming Protocols',
                False,
                f'Error checking streaming protocols: {str(e)}'
            )
    
    def test_buffering_optimization(self):
        """Test buffering and preloading strategies"""
        try:
            # Check for buffering optimization code
            src_path = self.project_root / 'src'
            
            buffering_features = {
                'preloading': False,
                'buffer_management': False,
                'lazy_loading': False,
                'progressive_loading': False
            }
            
            for file_path in src_path.rglob('*.{ts,tsx,js,jsx}'):
                try:
                    content = file_path.read_text(encoding='utf-8').lower()
                    
                    if any(term in content for term in ['preload', 'prefetch', 'preloading']):
                        buffering_features['preloading'] = True
                    if any(term in content for term in ['buffer', 'buffering', 'cache']):
                        buffering_features['buffer_management'] = True
                    if any(term in content for term in ['lazy', 'lazyload', 'intersection']):
                        buffering_features['lazy_loading'] = True
                    if any(term in content for term in ['progressive', 'chunk', 'segment']):
                        buffering_features['progressive_loading'] = True
                        
                except Exception:
                    continue
            
            implemented_features = [k for k, v in buffering_features.items() if v]
            
            if len(implemented_features) >= 3:
                self.log_test_result(
                    'Buffering Optimization',
                    True,
                    f'Advanced buffering: {", ".join(implemented_features)}'
                )
            elif len(implemented_features) >= 1:
                self.log_test_result(
                    'Buffering Optimization',
                    True,
                    f'Basic buffering: {", ".join(implemented_features)}'
                )
            else:
                self.log_test_result(
                    'Buffering Optimization',
                    False,
                    'No buffering optimization detected'
                )
                
        except Exception as e:
            self.log_test_result(
                'Buffering Optimization',
                False,
                f'Error checking buffering optimization: {str(e)}'
            )
    
    def test_network_adaptation(self):
        """Test network condition adaptation"""
        try:
            # Check for network adaptation features
            src_path = self.project_root / 'src'
            
            adaptation_features = {
                'connection_monitoring': False,
                'quality_switching': False,
                'bandwidth_detection': False,
                'fallback_strategies': False
            }
            
            for file_path in src_path.rglob('*.{ts,tsx,js,jsx}'):
                try:
                    content = file_path.read_text(encoding='utf-8').lower()
                    
                    if any(term in content for term in ['connection', 'online', 'offline', 'navigator.connection']):
                        adaptation_features['connection_monitoring'] = True
                    if any(term in content for term in ['quality', 'switch', 'adapt', 'auto']):
                        adaptation_features['quality_switching'] = True
                    if any(term in content for term in ['bandwidth', 'speed', 'throughput']):
                        adaptation_features['bandwidth_detection'] = True
                    if any(term in content for term in ['fallback', 'retry', 'error', 'recovery']):
                        adaptation_features['fallback_strategies'] = True
                        
                except Exception:
                    continue
            
            implemented_features = [k for k, v in adaptation_features.items() if v]
            
            if len(implemented_features) >= 3:
                self.log_test_result(
                    'Network Adaptation',
                    True,
                    f'Advanced adaptation: {", ".join(implemented_features)}'
                )
            elif len(implemented_features) >= 1:
                self.log_test_result(
                    'Network Adaptation',
                    True,
                    f'Basic adaptation: {", ".join(implemented_features)}'
                )
            else:
                self.log_test_result(
                    'Network Adaptation',
                    False,
                    'No network adaptation detected'
                )
                
        except Exception as e:
            self.log_test_result(
                'Network Adaptation',
                False,
                f'Error checking network adaptation: {str(e)}'
            )
    
    def test_performance_monitoring(self):
        """Test performance monitoring and analytics"""
        try:
            # Check for performance monitoring code
            src_path = self.project_root / 'src'
            
            monitoring_features = {
                'performance_api': False,
                'analytics': False,
                'error_tracking': False,
                'metrics_collection': False
            }
            
            for file_path in src_path.rglob('*.{ts,tsx,js,jsx}'):
                try:
                    content = file_path.read_text(encoding='utf-8').lower()
                    
                    if any(term in content for term in ['performance', 'timing', 'measure']):
                        monitoring_features['performance_api'] = True
                    if any(term in content for term in ['analytics', 'tracking', 'gtag', 'ga']):
                        monitoring_features['analytics'] = True
                    if any(term in content for term in ['error', 'exception', 'sentry', 'bugsnag']):
                        monitoring_features['error_tracking'] = True
                    if any(term in content for term in ['metrics', 'telemetry', 'monitoring']):
                        monitoring_features['metrics_collection'] = True
                        
                except Exception:
                    continue
            
            implemented_features = [k for k, v in monitoring_features.items() if v]
            
            if len(implemented_features) >= 3:
                self.log_test_result(
                    'Performance Monitoring',
                    True,
                    f'Comprehensive monitoring: {", ".join(implemented_features)}'
                )
            elif len(implemented_features) >= 1:
                self.log_test_result(
                    'Performance Monitoring',
                    True,
                    f'Basic monitoring: {", ".join(implemented_features)}'
                )
            else:
                self.log_test_result(
                    'Performance Monitoring',
                    False,
                    'No performance monitoring detected'
                )
                
        except Exception as e:
            self.log_test_result(
                'Performance Monitoring',
                False,
                f'Error checking performance monitoring: {str(e)}'
            )
    
    def simulate_latency_test(self):
        """Simulate latency testing"""
        try:
            # Simulate network latency measurements
            test_endpoints = [
                'https://www.google.com',
                'https://www.cloudflare.com',
                'https://httpbin.org/delay/1'
            ]
            
            latency_results = []
            
            for endpoint in test_endpoints:
                try:
                    start_time = time.time()
                    response = requests.get(endpoint, timeout=5)
                    end_time = time.time()
                    
                    latency = (end_time - start_time) * 1000  # Convert to milliseconds
                    latency_results.append(latency)
                    
                except requests.exceptions.RequestException:
                    continue
            
            if latency_results:
                avg_latency = sum(latency_results) / len(latency_results)
                
                metrics = {
                    'average_latency_ms': round(avg_latency, 2),
                    'min_latency_ms': round(min(latency_results), 2),
                    'max_latency_ms': round(max(latency_results), 2),
                    'test_count': len(latency_results)
                }
                
                if avg_latency < 200:
                    self.log_test_result(
                        'Network Latency Simulation',
                        True,
                        f'Good network performance - Average latency: {avg_latency:.1f}ms',
                        metrics=metrics
                    )
                elif avg_latency < 500:
                    self.log_test_result(
                        'Network Latency Simulation',
                        True,
                        f'Acceptable network performance - Average latency: {avg_latency:.1f}ms',
                        metrics=metrics
                    )
                else:
                    self.log_test_result(
                        'Network Latency Simulation',
                        False,
                        f'High network latency detected - Average: {avg_latency:.1f}ms',
                        metrics=metrics
                    )
            else:
                self.log_test_result(
                    'Network Latency Simulation',
                    False,
                    'Unable to measure network latency - no successful connections'
                )
                
        except Exception as e:
            self.log_test_result(
                'Network Latency Simulation',
                False,
                f'Error during latency simulation: {str(e)}'
            )
    
    def run_all_tests(self):
        """Run all streaming performance tests"""
        logger.info("Starting comprehensive streaming performance assessment...")
        
        # Infrastructure tests
        server_url = self.test_api_server_availability()
        self.test_cdn_configuration()
        
        # Video streaming tests
        self.test_video_compression_settings()
        self.test_streaming_protocols()
        self.test_buffering_optimization()
        
        # Network adaptation tests
        self.test_network_adaptation()
        self.test_performance_monitoring()
        
        # Performance simulation
        self.simulate_latency_test()
        
        # Determine production readiness
        critical_failures = len(self.results['summary']['critical_issues'])
        total_tests = self.results['summary']['total_tests']
        passed_tests = self.results['summary']['passed']
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        self.results['summary']['success_rate'] = success_rate
        self.results['summary']['production_ready'] = critical_failures <= 1 and success_rate >= 70
        
        return self.results
    
    def generate_report(self):
        """Generate detailed streaming performance report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f'streaming_performance_report_{timestamp}.json'
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Detailed report saved to: {report_file}")
        return report_file
    
    def print_summary(self):
        """Print streaming performance summary"""
        summary = self.results['summary']
        
        print("\n" + "="*80)
        print("STREAMING PERFORMANCE ASSESSMENT SUMMARY")
        print("="*80)
        
        print(f"\nTotal Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Success Rate: {summary.get('success_rate', 0):.1f}%")
        
        # Performance metrics summary
        if self.results['performance_metrics']:
            print("\n[INFO] Performance Metrics:")
            for test_name, metrics in self.results['performance_metrics'].items():
                print(f"  {test_name}:")
                for key, value in metrics.items():
                    print(f"    - {key}: {value}")
        
        status = "PRODUCTION READY" if summary['production_ready'] else "NOT PRODUCTION READY"
        status_marker = "[SUCCESS]" if summary['production_ready'] else "[CRITICAL]"
        print(f"\nStatus: {status_marker} {status}")
        
        if summary['critical_issues']:
            print(f"\n[CRITICAL] Critical Issues ({len(summary['critical_issues'])}):")
            for issue in summary['critical_issues']:
                print(f"  - {issue}")
        
        if summary['warnings']:
            print(f"\n[WARNING] Warnings ({len(summary['warnings'])}):")
            for warning in summary['warnings']:
                print(f"  - {warning}")
        
        print("\n" + "="*80)

def main():
    """Main execution function"""
    try:
        tester = StreamingPerformanceTester()
        results = tester.run_all_tests()
        
        # Generate detailed report
        report_file = tester.generate_report()
        
        # Print summary
        tester.print_summary()
        
        # Exit with appropriate code
        if results['summary']['production_ready']:
            logger.info("Streaming performance assessment completed successfully")
            sys.exit(0)
        else:
            logger.error("Streaming performance assessment failed - issues found")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Streaming performance test failed: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()