#!/usr/bin/env python3
"""Comprehensive test runner for the enhanced video processing system.

This script provides:
- Automated test execution with different test suites
- Performance benchmarking and reporting
- Coverage analysis
- Test result aggregation
- CI/CD integration support
"""

import os
import sys
import subprocess
import argparse
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
import psutil


class TestRunner:
    """Enhanced test runner with comprehensive reporting."""
    
    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root or os.getcwd())
        self.test_dir = self.project_root / "api" / "tests"
        self.reports_dir = self.project_root / "test_reports"
        self.reports_dir.mkdir(exist_ok=True)
        
        # Test suites configuration
        self.test_suites = {
            'unit': {
                'description': 'Unit tests for individual components',
                'markers': 'unit',
                'files': ['test_enhanced_services.py'],
                'timeout': 300  # 5 minutes
            },
            'integration': {
                'description': 'Integration tests for service interactions',
                'markers': 'integration',
                'files': ['test_integration.py'],
                'timeout': 600  # 10 minutes
            },
            'performance': {
                'description': 'Performance and benchmark tests',
                'markers': 'performance',
                'files': ['test_performance.py'],
                'timeout': 900  # 15 minutes
            },
            'all': {
                'description': 'All tests',
                'markers': None,
                'files': None,
                'timeout': 1800  # 30 minutes
            }
        }
        
        # Performance thresholds (industry standards)
        self.performance_thresholds = {
            'api_response_time_p95': 1.0,  # 1 second
            'api_response_time_mean': 0.5,  # 500ms
            'memory_usage_max': 80.0,  # 80%
            'cpu_usage_max': 90.0,  # 90%
            'success_rate_min': 99.0,  # 99%
            'throughput_min': 10.0,  # 10 requests/second
            'error_rate_max': 1.0  # 1%
        }
    
    def run_test_suite(self, suite_name: str, verbose: bool = False, 
                      coverage: bool = False, parallel: bool = False) -> Dict[str, Any]:
        """Run a specific test suite."""
        if suite_name not in self.test_suites:
            raise ValueError(f"Unknown test suite: {suite_name}")
        
        suite_config = self.test_suites[suite_name]
        print(f"\n🧪 Running {suite_name} tests: {suite_config['description']}")
        
        # Build pytest command
        cmd = self._build_pytest_command(
            suite_name=suite_name,
            verbose=verbose,
            coverage=coverage,
            parallel=parallel
        )
        
        # Record system state before tests
        pre_test_state = self._get_system_state()
        
        # Run tests
        start_time = time.time()
        result = self._execute_command(cmd, timeout=suite_config['timeout'])
        end_time = time.time()
        
        # Record system state after tests
        post_test_state = self._get_system_state()
        
        # Parse results
        test_results = self._parse_test_results(result, suite_name)
        test_results.update({
            'suite_name': suite_name,
            'duration': end_time - start_time,
            'pre_test_state': pre_test_state,
            'post_test_state': post_test_state,
            'command': ' '.join(cmd),
            'timestamp': time.time()
        })
        
        # Generate report
        self._generate_test_report(test_results, suite_name)
        
        return test_results
    
    def run_all_suites(self, **kwargs) -> Dict[str, Any]:
        """Run all test suites and generate comprehensive report."""
        print("\n🚀 Starting comprehensive test execution...")
        
        all_results = {}
        overall_start_time = time.time()
        
        # Run each suite
        for suite_name in ['unit', 'integration', 'performance']:
            try:
                results = self.run_test_suite(suite_name, **kwargs)
                all_results[suite_name] = results
                
                # Print summary
                self._print_suite_summary(suite_name, results)
                
            except Exception as e:
                print(f"❌ Failed to run {suite_name} tests: {e}")
                all_results[suite_name] = {
                    'success': False,
                    'error': str(e),
                    'duration': 0
                }
        
        overall_end_time = time.time()
        
        # Generate comprehensive report
        comprehensive_results = {
            'suites': all_results,
            'total_duration': overall_end_time - overall_start_time,
            'timestamp': time.time(),
            'performance_analysis': self._analyze_performance(all_results),
            'recommendations': self._generate_recommendations(all_results)
        }
        
        self._generate_comprehensive_report(comprehensive_results)
        self._print_final_summary(comprehensive_results)
        
        return comprehensive_results
    
    def _build_pytest_command(self, suite_name: str, verbose: bool = False,
                             coverage: bool = False, parallel: bool = False) -> List[str]:
        """Build pytest command with appropriate options."""
        cmd = ['python', '-m', 'pytest']
        
        # Add test directory
        cmd.append(str(self.test_dir))
        
        # Add suite-specific options
        suite_config = self.test_suites[suite_name]
        
        if suite_config['markers']:
            cmd.extend(['-m', suite_config['markers']])
        
        if suite_config['files'] and suite_name != 'all':
            # Replace test directory with specific files
            cmd[-1] = ' '.join(str(self.test_dir / f) for f in suite_config['files'])
        
        # Add common options
        cmd.extend([
            '--tb=short',  # Short traceback format
            '--strict-markers',  # Strict marker checking
            '--disable-warnings',  # Disable warnings for cleaner output
        ])
        
        # Add verbose output
        if verbose:
            cmd.append('-v')
        
        # Add coverage
        if coverage:
            cmd.extend([
                '--cov=api',
                '--cov-report=html:test_reports/coverage_html',
                '--cov-report=xml:test_reports/coverage.xml',
                '--cov-report=term-missing'
            ])
        
        # Add parallel execution
        if parallel:
            cpu_count = psutil.cpu_count()
            cmd.extend(['-n', str(min(cpu_count, 4))])  # Max 4 workers
        
        # Add output options
        cmd.extend([
            '--junitxml=test_reports/junit.xml',
            '--json-report',
            f'--json-report-file=test_reports/{suite_name}_results.json'
        ])
        
        return cmd
    
    def _execute_command(self, cmd: List[str], timeout: int) -> subprocess.CompletedProcess:
        """Execute command with timeout and error handling."""
        try:
            print(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.project_root
            )
            return result
        
        except subprocess.TimeoutExpired:
            raise Exception(f"Tests timed out after {timeout} seconds")
        except Exception as e:
            raise Exception(f"Failed to execute tests: {e}")
    
    def _get_system_state(self) -> Dict[str, Any]:
        """Get current system resource state."""
        try:
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            disk = psutil.disk_usage('/')
            
            return {
                'memory_percent': memory.percent,
                'memory_available_gb': memory.available / (1024**3),
                'cpu_percent': cpu_percent,
                'disk_percent': disk.percent,
                'disk_free_gb': disk.free / (1024**3)
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _parse_test_results(self, result: subprocess.CompletedProcess, 
                           suite_name: str) -> Dict[str, Any]:
        """Parse test execution results."""
        # Try to load JSON report
        json_report_path = self.reports_dir / f"{suite_name}_results.json"
        json_data = {}
        
        if json_report_path.exists():
            try:
                with open(json_report_path, 'r') as f:
                    json_data = json.load(f)
            except Exception as e:
                print(f"Warning: Could not parse JSON report: {e}")
        
        # Parse basic results from output
        output_lines = result.stdout.split('\n') if result.stdout else []
        
        # Extract test counts
        test_counts = {'passed': 0, 'failed': 0, 'skipped': 0, 'errors': 0}
        
        for line in output_lines:
            if 'passed' in line and 'failed' in line:
                # Parse pytest summary line
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.isdigit() and i + 1 < len(parts):
                        count = int(part)
                        status = parts[i + 1].lower()
                        if status.startswith('passed'):
                            test_counts['passed'] = count
                        elif status.startswith('failed'):
                            test_counts['failed'] = count
                        elif status.startswith('skipped'):
                            test_counts['skipped'] = count
                        elif status.startswith('error'):
                            test_counts['errors'] = count
        
        return {
            'success': result.returncode == 0,
            'return_code': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'test_counts': test_counts,
            'json_data': json_data
        }
    
    def _analyze_performance(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze performance test results against thresholds."""
        performance_results = all_results.get('performance', {})
        
        if not performance_results.get('success'):
            return {'status': 'failed', 'reason': 'Performance tests failed'}
        
        analysis = {
            'status': 'passed',
            'threshold_violations': [],
            'recommendations': []
        }
        
        # Analyze against thresholds
        json_data = performance_results.get('json_data', {})
        
        # Check test duration
        duration = performance_results.get('duration', 0)
        if duration > 900:  # 15 minutes
            analysis['threshold_violations'].append({
                'metric': 'test_duration',
                'value': duration,
                'threshold': 900,
                'severity': 'warning'
            })
        
        # Check memory usage
        post_state = performance_results.get('post_test_state', {})
        memory_percent = post_state.get('memory_percent', 0)
        
        if memory_percent > self.performance_thresholds['memory_usage_max']:
            analysis['threshold_violations'].append({
                'metric': 'memory_usage',
                'value': memory_percent,
                'threshold': self.performance_thresholds['memory_usage_max'],
                'severity': 'critical'
            })
        
        # Generate recommendations
        if analysis['threshold_violations']:
            analysis['status'] = 'warning'
            analysis['recommendations'].extend([
                "Consider optimizing memory usage in video processing",
                "Implement more aggressive garbage collection",
                "Review chunk processing sizes"
            ])
        
        return analysis
    
    def _generate_recommendations(self, all_results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []
        
        # Check overall success rate
        total_passed = sum(r.get('test_counts', {}).get('passed', 0) for r in all_results.values())
        total_failed = sum(r.get('test_counts', {}).get('failed', 0) for r in all_results.values())
        total_tests = total_passed + total_failed
        
        if total_tests > 0:
            success_rate = (total_passed / total_tests) * 100
            
            if success_rate < 95:
                recommendations.append("🔴 Critical: Test success rate below 95%. Review failing tests immediately.")
            elif success_rate < 99:
                recommendations.append("🟡 Warning: Test success rate below 99%. Consider improving test reliability.")
            else:
                recommendations.append("✅ Excellent: Test success rate above 99%.")
        
        # Check performance
        perf_results = all_results.get('performance', {})
        if not perf_results.get('success'):
            recommendations.append("🔴 Critical: Performance tests failed. Review system performance.")
        
        # Check integration
        integration_results = all_results.get('integration', {})
        if not integration_results.get('success'):
            recommendations.append("🔴 Critical: Integration tests failed. Review service interactions.")
        
        # General recommendations
        recommendations.extend([
            "📊 Monitor test execution times and optimize slow tests",
            "🔄 Run tests regularly in CI/CD pipeline",
            "📈 Track test metrics over time for trend analysis",
            "🛡️ Maintain test coverage above 80%",
            "🧪 Add more edge case testing for robustness"
        ])
        
        return recommendations
    
    def _generate_test_report(self, results: Dict[str, Any], suite_name: str):
        """Generate detailed test report for a suite."""
        report_path = self.reports_dir / f"{suite_name}_report.json"
        
        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"📄 Test report saved: {report_path}")
    
    def _generate_comprehensive_report(self, results: Dict[str, Any]):
        """Generate comprehensive test report."""
        report_path = self.reports_dir / "comprehensive_report.json"
        
        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        # Generate HTML report
        html_report = self._generate_html_report(results)
        html_path = self.reports_dir / "test_report.html"
        
        with open(html_path, 'w') as f:
            f.write(html_report)
        
        print(f"📄 Comprehensive report saved: {report_path}")
        print(f"🌐 HTML report saved: {html_path}")
    
    def _generate_html_report(self, results: Dict[str, Any]) -> str:
        """Generate HTML test report."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Video Processing System - Test Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .suite {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .success {{ background: #d4edda; border-color: #c3e6cb; }}
                .failure {{ background: #f8d7da; border-color: #f5c6cb; }}
                .warning {{ background: #fff3cd; border-color: #ffeaa7; }}
                .metric {{ display: inline-block; margin: 10px; padding: 10px; background: #f8f9fa; border-radius: 3px; }}
                .recommendations {{ background: #e7f3ff; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background: #f2f2f2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🧪 Video Processing System - Test Report</h1>
                <p>Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>Total Duration: {results['total_duration']:.2f} seconds</p>
            </div>
        """
        
        # Add suite summaries
        for suite_name, suite_results in results['suites'].items():
            success_class = 'success' if suite_results.get('success') else 'failure'
            test_counts = suite_results.get('test_counts', {})
            
            html += f"""
            <div class="suite {success_class}">
                <h2>📋 {suite_name.title()} Tests</h2>
                <div class="metric">Duration: {suite_results.get('duration', 0):.2f}s</div>
                <div class="metric">Passed: {test_counts.get('passed', 0)}</div>
                <div class="metric">Failed: {test_counts.get('failed', 0)}</div>
                <div class="metric">Skipped: {test_counts.get('skipped', 0)}</div>
                <div class="metric">Errors: {test_counts.get('errors', 0)}</div>
            </div>
            """
        
        # Add performance analysis
        perf_analysis = results.get('performance_analysis', {})
        analysis_class = 'success' if perf_analysis.get('status') == 'passed' else 'warning'
        
        html += f"""
        <div class="suite {analysis_class}">
            <h2>📊 Performance Analysis</h2>
            <p>Status: {perf_analysis.get('status', 'unknown').title()}</p>
        """
        
        violations = perf_analysis.get('threshold_violations', [])
        if violations:
            html += "<h3>Threshold Violations:</h3><ul>"
            for violation in violations:
                html += f"<li>{violation['metric']}: {violation['value']} (threshold: {violation['threshold']})</li>"
            html += "</ul>"
        
        html += "</div>"
        
        # Add recommendations
        recommendations = results.get('recommendations', [])
        html += """
        <div class="recommendations">
            <h2>💡 Recommendations</h2>
            <ul>
        """
        
        for rec in recommendations:
            html += f"<li>{rec}</li>"
        
        html += """
            </ul>
        </div>
        </body>
        </html>
        """
        
        return html
    
    def _print_suite_summary(self, suite_name: str, results: Dict[str, Any]):
        """Print summary for a test suite."""
        success = results.get('success', False)
        duration = results.get('duration', 0)
        test_counts = results.get('test_counts', {})
        
        status_emoji = "✅" if success else "❌"
        print(f"\n{status_emoji} {suite_name.title()} Tests Summary:")
        print(f"   Duration: {duration:.2f}s")
        print(f"   Passed: {test_counts.get('passed', 0)}")
        print(f"   Failed: {test_counts.get('failed', 0)}")
        print(f"   Skipped: {test_counts.get('skipped', 0)}")
        print(f"   Errors: {test_counts.get('errors', 0)}")
    
    def _print_final_summary(self, results: Dict[str, Any]):
        """Print final comprehensive summary."""
        print("\n" + "="*60)
        print("🎯 FINAL TEST SUMMARY")
        print("="*60)
        
        total_duration = results['total_duration']
        print(f"⏱️  Total Duration: {total_duration:.2f} seconds")
        
        # Calculate totals
        total_passed = sum(r.get('test_counts', {}).get('passed', 0) for r in results['suites'].values())
        total_failed = sum(r.get('test_counts', {}).get('failed', 0) for r in results['suites'].values())
        total_skipped = sum(r.get('test_counts', {}).get('skipped', 0) for r in results['suites'].values())
        total_errors = sum(r.get('test_counts', {}).get('errors', 0) for r in results['suites'].values())
        total_tests = total_passed + total_failed + total_skipped + total_errors
        
        print(f"📊 Total Tests: {total_tests}")
        print(f"✅ Passed: {total_passed}")
        print(f"❌ Failed: {total_failed}")
        print(f"⏭️  Skipped: {total_skipped}")
        print(f"💥 Errors: {total_errors}")
        
        if total_tests > 0:
            success_rate = (total_passed / total_tests) * 100
            print(f"📈 Success Rate: {success_rate:.1f}%")
        
        # Performance status
        perf_analysis = results.get('performance_analysis', {})
        perf_status = perf_analysis.get('status', 'unknown')
        perf_emoji = "✅" if perf_status == 'passed' else "⚠️" if perf_status == 'warning' else "❌"
        print(f"{perf_emoji} Performance: {perf_status.title()}")
        
        print("\n📄 Reports generated in: test_reports/")
        print("🌐 Open test_reports/test_report.html for detailed results")
        
        # Overall status
        all_success = all(r.get('success', False) for r in results['suites'].values())
        overall_emoji = "🎉" if all_success else "⚠️"
        overall_status = "ALL TESTS PASSED" if all_success else "SOME TESTS FAILED"
        
        print(f"\n{overall_emoji} {overall_status}")
        print("="*60)


def main():
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(description='Enhanced Video Processing System Test Runner')
    
    parser.add_argument(
        'suite',
        nargs='?',
        default='all',
        choices=['unit', 'integration', 'performance', 'all'],
        help='Test suite to run (default: all)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    parser.add_argument(
        '-c', '--coverage',
        action='store_true',
        help='Generate coverage report'
    )
    
    parser.add_argument(
        '-p', '--parallel',
        action='store_true',
        help='Run tests in parallel'
    )
    
    parser.add_argument(
        '--project-root',
        help='Project root directory (default: current directory)'
    )
    
    args = parser.parse_args()
    
    # Initialize test runner
    runner = TestRunner(project_root=args.project_root)
    
    try:
        if args.suite == 'all':
            results = runner.run_all_suites(
                verbose=args.verbose,
                coverage=args.coverage,
                parallel=args.parallel
            )
        else:
            results = runner.run_test_suite(
                suite_name=args.suite,
                verbose=args.verbose,
                coverage=args.coverage,
                parallel=args.parallel
            )
        
        # Exit with appropriate code
        if args.suite == 'all':
            all_success = all(r.get('success', False) for r in results['suites'].values())
            sys.exit(0 if all_success else 1)
        else:
            sys.exit(0 if results.get('success', False) else 1)
    
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()