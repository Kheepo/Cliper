#!/usr/bin/env python3
"""
Comprehensive Test Report Generator
Generates a detailed report of all test modules and their status.
"""

import subprocess
import json
import sys
from pathlib import Path

def run_test_module(module_path):
    """Run a specific test module and return results."""
    try:
        result = subprocess.run(
            ['python', '-m', 'pytest', module_path, '--tb=no', '-q'],
            capture_output=True,
            text=True,
            cwd='.',
            timeout=60
        )
        
        output_lines = result.stdout.strip().split('\n')
        summary_line = [line for line in output_lines if 'failed' in line or 'passed' in line or 'error' in line][-1] if output_lines else ''
        
        return {
            'exit_code': result.returncode,
            'status': 'PASSED' if result.returncode == 0 else 'FAILED',
            'summary': summary_line,
            'stderr': result.stderr.strip() if result.stderr else ''
        }
    except subprocess.TimeoutExpired:
        return {
            'exit_code': -1,
            'status': 'TIMEOUT',
            'summary': 'Test execution timed out',
            'stderr': ''
        }
    except Exception as e:
        return {
            'exit_code': -1,
            'status': 'ERROR',
            'summary': f'Error running test: {str(e)}',
            'stderr': ''
        }

def main():
    """Generate comprehensive test report."""
    print("=" * 80)
    print("COMPREHENSIVE TEST REPORT")
    print("=" * 80)
    
    # Define test modules to check
    unit_tests = [
        'api/tests/unit/test_models.py',
        'api/tests/unit/test_validation.py', 
        'api/tests/unit/test_security.py',
        'api/tests/unit/test_auth_middleware.py',
        'api/tests/unit/test_error_handler.py'
    ]
    
    integration_tests = [
        'api/tests/integration/test_auth_workflow.py',
        'api/tests/integration/test_clips_workflow.py',
        'api/tests/integration/test_video_processing_workflow.py'
    ]
    
    results = {
        'unit_tests': {},
        'integration_tests': {},
        'summary': {
            'total_modules': 0,
            'passed_modules': 0,
            'failed_modules': 0,
            'error_modules': 0
        }
    }
    
    print("\n📋 UNIT TESTS")
    print("-" * 40)
    
    for test_module in unit_tests:
        if Path(test_module).exists():
            print(f"Running {test_module}...")
            result = run_test_module(test_module)
            results['unit_tests'][test_module] = result
            results['summary']['total_modules'] += 1
            
            if result['status'] == 'PASSED':
                results['summary']['passed_modules'] += 1
                print(f"  ✅ {result['status']}: {result['summary']}")
            elif result['status'] == 'FAILED':
                results['summary']['failed_modules'] += 1
                print(f"  ❌ {result['status']}: {result['summary']}")
            else:
                results['summary']['error_modules'] += 1
                print(f"  ⚠️  {result['status']}: {result['summary']}")
        else:
            print(f"  ⚠️  MISSING: {test_module}")
    
    print("\n🔗 INTEGRATION TESTS")
    print("-" * 40)
    
    for test_module in integration_tests:
        if Path(test_module).exists():
            print(f"Running {test_module}...")
            result = run_test_module(test_module)
            results['integration_tests'][test_module] = result
            results['summary']['total_modules'] += 1
            
            if result['status'] == 'PASSED':
                results['summary']['passed_modules'] += 1
                print(f"  ✅ {result['status']}: {result['summary']}")
            elif result['status'] == 'FAILED':
                results['summary']['failed_modules'] += 1
                print(f"  ❌ {result['status']}: {result['summary']}")
            else:
                results['summary']['error_modules'] += 1
                print(f"  ⚠️  {result['status']}: {result['summary']}")
        else:
            print(f"  ⚠️  MISSING: {test_module}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    
    summary = results['summary']
    print(f"Total Modules Tested: {summary['total_modules']}")
    print(f"✅ Passed: {summary['passed_modules']}")
    print(f"❌ Failed: {summary['failed_modules']}")
    print(f"⚠️  Errors: {summary['error_modules']}")
    
    if summary['total_modules'] > 0:
        pass_rate = (summary['passed_modules'] / summary['total_modules']) * 100
        print(f"\n📈 Pass Rate: {pass_rate:.1f}%")
    
    # API Server Status
    print("\n🌐 API SERVER STATUS")
    print("-" * 40)
    try:
        import requests
        response = requests.get('http://localhost:8000/health', timeout=5)
        if response.status_code == 200:
            print("  ✅ API Server: RUNNING")
            print(f"  📡 Health Check: {response.json()}")
        else:
            print(f"  ❌ API Server: UNHEALTHY (Status: {response.status_code})")
    except requests.exceptions.ConnectionError:
        print("  ❌ API Server: NOT RESPONDING")
    except Exception as e:
        print(f"  ⚠️  API Server: ERROR ({str(e)})")
    
    # Recommendations
    print("\n💡 RECOMMENDATIONS")
    print("-" * 40)
    
    if summary['failed_modules'] > 0:
        print("  • Fix failing test modules before deployment")
        print("  • Review import paths and dependencies")
        print("  • Check middleware configuration")
    
    if summary['error_modules'] > 0:
        print("  • Investigate test execution errors")
        print("  • Verify test environment setup")
    
    if summary['passed_modules'] == summary['total_modules']:
        print("  • All tests passing! Ready for deployment")
        print("  • Consider adding more integration tests")
    
    print("\n" + "=" * 80)
    
    # Save detailed results to JSON
    with open('test_report.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("📄 Detailed report saved to: test_report.json")
    
    return summary['failed_modules'] + summary['error_modules']

if __name__ == '__main__':
    exit_code = main()
    sys.exit(min(exit_code, 1))  # Return 1 if any failures, 0 if all pass