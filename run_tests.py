#!/usr/bin/env python3
"""
Comprehensive Test Runner for Cliper Application

This script provides a unified interface for running all types of tests:
- Unit tests
- Integration tests
- End-to-end tests
- Performance tests
- Security tests

Usage:
    python run_tests.py --unit
    python run_tests.py --integration
    python run_tests.py --e2e
    python run_tests.py --all
    python run_tests.py --performance
    python run_tests.py --security
"""

import argparse
import os
import sys
import subprocess
import time
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test-runner.log')
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Test execution result"""
    name: str
    success: bool
    duration: float
    output: str
    error: Optional[str] = None
    coverage: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


class TestRunner:
    """Main test runner class"""
    
    def __init__(self):
        self.project_root = project_root
        self.test_results: List[TestResult] = []
        self.start_time = time.time()
        
        # Ensure test directories exist
        self._setup_test_environment()
    
    def _setup_test_environment(self):
        """Setup test environment and directories"""
        test_dirs = [
            'test_uploads',
            'test_temp', 
            'test_output',
            'logs',
            'test-results',
            'coverage-reports'
        ]
        
        for dir_name in test_dirs:
            dir_path = self.project_root / dir_name
            dir_path.mkdir(exist_ok=True)
        
        # Set test environment variables
        os.environ.update({
            'ENVIRONMENT': 'test',
            'DEBUG': 'true',
            'LOG_LEVEL': 'DEBUG',
            'SECRET_KEY': 'test-secret-key-for-testing-only',
            'SUPABASE_URL': 'http://localhost:54321',
            'SUPABASE_ANON_KEY': 'test-anon-key',
            'SUPABASE_SERVICE_ROLE_KEY': 'test-service-role-key',
            'REDIS_URL': 'redis://localhost:6379/0',
            'OPENAI_API_KEY': 'test-openai-key',
            'ANTHROPIC_API_KEY': 'test-anthropic-key',
            'GOOGLE_API_KEY': 'test-google-key',
            'UPLOAD_PATH': str(self.project_root / 'test_uploads'),
            'TEMP_PATH': str(self.project_root / 'test_temp'),
            'OUTPUT_PATH': str(self.project_root / 'test_output'),
            'FFMPEG_PATH': '/usr/bin/ffmpeg',
            'MAX_UPLOAD_SIZE': '104857600',
            'MAX_CLIP_DURATION': '300',
            'ENABLE_RATE_LIMITING': 'false',
            'ENABLE_MONITORING': 'false',
            'ENABLE_WEBSOCKETS': 'true'
        })
    
    def _run_command(self, command: List[str], cwd: Optional[Path] = None, 
                    timeout: int = 300) -> TestResult:
        """Run a command and capture results"""
        start_time = time.time()
        cwd = cwd or self.project_root
        
        logger.info(f"Running command: {' '.join(command)}")
        
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            duration = time.time() - start_time
            success = result.returncode == 0
            
            return TestResult(
                name=' '.join(command[:2]),
                success=success,
                duration=duration,
                output=result.stdout,
                error=result.stderr if not success else None
            )
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return TestResult(
                name=' '.join(command[:2]),
                success=False,
                duration=duration,
                output='',
                error=f'Command timed out after {timeout} seconds'
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                name=' '.join(command[:2]),
                success=False,
                duration=duration,
                output='',
                error=str(e)
            )
    
    def run_unit_tests(self, coverage: bool = False, xml_report: bool = False) -> TestResult:
        """Run unit tests"""
        logger.info("Running unit tests...")
        
        command = ['python', '-m', 'pytest', 'tests/unit/', '-v', '--tb=short']
        
        if coverage:
            command.extend([
                '--cov=api',
                '--cov-report=term-missing',
                '--cov-report=html:coverage-reports/html',
                '--cov-fail-under=80'
            ])
            
            if xml_report:
                command.append('--cov-report=xml:coverage.xml')
        
        command.extend([
            '--junitxml=test-results/unit-tests.xml',
            '--maxfail=10'
        ])
        
        result = self._run_command(command)
        result.name = 'Unit Tests'
        
        # Extract coverage if available
        if coverage and result.success:
            try:
                coverage_file = self.project_root / 'coverage.xml'
                if coverage_file.exists():
                    # Parse coverage from XML (simplified)
                    with open(coverage_file) as f:
                        content = f.read()
                        if 'line-rate=' in content:
                            import re
                            match = re.search(r'line-rate="([0-9.]+)"', content)
                            if match:
                                result.coverage = float(match.group(1)) * 100
            except Exception as e:
                logger.warning(f"Could not parse coverage: {e}")
        
        self.test_results.append(result)
        return result
    
    def run_integration_tests(self, coverage: bool = False) -> TestResult:
        """Run integration tests"""
        logger.info("Running integration tests...")
        
        command = [
            'python', '-m', 'pytest', 'tests/integration/', '-v',
            '--tb=short', '--junitxml=test-results/integration-tests.xml',
            '--maxfail=5'
        ]
        
        if coverage:
            command.extend([
                '--cov=api',
                '--cov-append',
                '--cov-report=term-missing'
            ])
        
        result = self._run_command(command, timeout=600)
        result.name = 'Integration Tests'
        
        self.test_results.append(result)
        return result
    
    def run_e2e_tests(self) -> TestResult:
        """Run end-to-end tests"""
        logger.info("Running end-to-end tests...")
        
        command = [
            'python', '-m', 'pytest', 'tests/e2e/', '-v',
            '--tb=short', '--junitxml=test-results/e2e-tests.xml',
            '--maxfail=3'
        ]
        
        result = self._run_command(command, timeout=900)
        result.name = 'End-to-End Tests'
        
        self.test_results.append(result)
        return result
    
    def run_performance_tests(self) -> TestResult:
        """Run performance tests"""
        logger.info("Running performance tests...")
        
        command = [
            'python', '-m', 'pytest', 'tests/performance/', '-v',
            '--tb=short', '--junitxml=test-results/performance-tests.xml',
            '--benchmark-only', '--benchmark-json=test-results/benchmark.json'
        ]
        
        result = self._run_command(command, timeout=1200)
        result.name = 'Performance Tests'
        
        # Parse benchmark results
        try:
            benchmark_file = self.project_root / 'test-results' / 'benchmark.json'
            if benchmark_file.exists():
                with open(benchmark_file) as f:
                    benchmark_data = json.load(f)
                    result.details = {'benchmarks': benchmark_data}
        except Exception as e:
            logger.warning(f"Could not parse benchmark results: {e}")
        
        self.test_results.append(result)
        return result
    
    def run_security_tests(self) -> TestResult:
        """Run security tests"""
        logger.info("Running security tests...")
        
        # Run bandit security linter
        bandit_result = self._run_command([
            'bandit', '-r', 'api/', '-f', 'json', '-o', 'test-results/bandit.json'
        ])
        
        # Run safety check
        safety_result = self._run_command([
            'safety', 'check', '--json', '--output', 'test-results/safety.json'
        ])
        
        # Run security-focused tests
        pytest_result = self._run_command([
            'python', '-m', 'pytest', 'tests/security/', '-v',
            '--tb=short', '--junitxml=test-results/security-tests.xml'
        ])
        
        # Combine results
        success = bandit_result.success and safety_result.success and pytest_result.success
        duration = bandit_result.duration + safety_result.duration + pytest_result.duration
        
        output = f"Bandit: {bandit_result.output}\n\nSafety: {safety_result.output}\n\nPytest: {pytest_result.output}"
        error = None
        if not success:
            errors = []
            if bandit_result.error:
                errors.append(f"Bandit: {bandit_result.error}")
            if safety_result.error:
                errors.append(f"Safety: {safety_result.error}")
            if pytest_result.error:
                errors.append(f"Pytest: {pytest_result.error}")
            error = "\n\n".join(errors)
        
        result = TestResult(
            name='Security Tests',
            success=success,
            duration=duration,
            output=output,
            error=error
        )
        
        self.test_results.append(result)
        return result
    
    def run_linting(self) -> TestResult:
        """Run code linting"""
        logger.info("Running code linting...")
        
        # Run flake8
        flake8_result = self._run_command([
            'flake8', 'api/', 'tests/', '--count', '--statistics',
            '--tee', '--output-file=test-results/flake8.txt'
        ])
        
        # Run mypy
        mypy_result = self._run_command([
            'mypy', 'api/', '--ignore-missing-imports',
            '--show-error-codes', '--pretty'
        ])
        
        # Run black check
        black_result = self._run_command([
            'black', '--check', '--diff', 'api/', 'tests/'
        ])
        
        # Run isort check
        isort_result = self._run_command([
            'isort', '--check-only', '--diff', 'api/', 'tests/'
        ])
        
        # Combine results
        success = all([
            flake8_result.success,
            mypy_result.success,
            black_result.success,
            isort_result.success
        ])
        
        duration = sum([
            flake8_result.duration,
            mypy_result.duration,
            black_result.duration,
            isort_result.duration
        ])
        
        output = f"""Flake8: {flake8_result.output}

Mypy: {mypy_result.output}

Black: {black_result.output}

Isort: {isort_result.output}"""
        
        error = None
        if not success:
            errors = []
            for name, res in [('Flake8', flake8_result), ('Mypy', mypy_result), 
                            ('Black', black_result), ('Isort', isort_result)]:
                if res.error:
                    errors.append(f"{name}: {res.error}")
            error = "\n\n".join(errors)
        
        result = TestResult(
            name='Code Linting',
            success=success,
            duration=duration,
            output=output,
            error=error
        )
        
        self.test_results.append(result)
        return result
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        total_duration = time.time() - self.start_time
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_duration': total_duration,
            'summary': {
                'total_tests': len(self.test_results),
                'passed': sum(1 for r in self.test_results if r.success),
                'failed': sum(1 for r in self.test_results if not r.success),
                'success_rate': (sum(1 for r in self.test_results if r.success) / len(self.test_results) * 100) if self.test_results else 0
            },
            'results': []
        }
        
        for result in self.test_results:
            report['results'].append({
                'name': result.name,
                'success': result.success,
                'duration': result.duration,
                'coverage': result.coverage,
                'error': result.error,
                'details': result.details
            })
        
        # Save report
        report_file = self.project_root / 'test-results' / 'test-report.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report
    
    def print_summary(self):
        """Print test summary to console"""
        report = self.generate_report()
        
        print("\n" + "="*80)
        print("TEST EXECUTION SUMMARY")
        print("="*80)
        print(f"Total Duration: {report['total_duration']:.2f}s")
        print(f"Tests Run: {report['summary']['total_tests']}")
        print(f"Passed: {report['summary']['passed']}")
        print(f"Failed: {report['summary']['failed']}")
        print(f"Success Rate: {report['summary']['success_rate']:.1f}%")
        print()
        
        for result in self.test_results:
            status = "✅ PASS" if result.success else "❌ FAIL"
            print(f"{status} {result.name} ({result.duration:.2f}s)")
            
            if result.coverage:
                print(f"     Coverage: {result.coverage:.1f}%")
            
            if result.error:
                print(f"     Error: {result.error[:100]}...")
        
        print("\n" + "="*80)
        
        # Exit with appropriate code
        if report['summary']['failed'] > 0:
            sys.exit(1)
        else:
            print("All tests passed! 🎉")
            sys.exit(0)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Cliper Test Runner')
    parser.add_argument('--unit', action='store_true', help='Run unit tests')
    parser.add_argument('--integration', action='store_true', help='Run integration tests')
    parser.add_argument('--e2e', action='store_true', help='Run end-to-end tests')
    parser.add_argument('--performance', action='store_true', help='Run performance tests')
    parser.add_argument('--security', action='store_true', help='Run security tests')
    parser.add_argument('--lint', action='store_true', help='Run code linting')
    parser.add_argument('--all', action='store_true', help='Run all tests')
    parser.add_argument('--coverage', action='store_true', help='Generate coverage report')
    parser.add_argument('--xml-report', action='store_true', help='Generate XML coverage report')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    runner = TestRunner()
    
    try:
        if args.all:
            runner.run_linting()
            runner.run_unit_tests(coverage=args.coverage, xml_report=args.xml_report)
            runner.run_integration_tests(coverage=args.coverage)
            runner.run_e2e_tests()
            runner.run_performance_tests()
            runner.run_security_tests()
        else:
            if args.lint:
                runner.run_linting()
            if args.unit:
                runner.run_unit_tests(coverage=args.coverage, xml_report=args.xml_report)
            if args.integration:
                runner.run_integration_tests(coverage=args.coverage)
            if args.e2e:
                runner.run_e2e_tests()
            if args.performance:
                runner.run_performance_tests()
            if args.security:
                runner.run_security_tests()
            
            # If no specific test type specified, run unit tests
            if not any([args.lint, args.unit, args.integration, args.e2e, 
                       args.performance, args.security]):
                runner.run_unit_tests(coverage=args.coverage, xml_report=args.xml_report)
        
        runner.print_summary()
        
    except KeyboardInterrupt:
        logger.info("Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()