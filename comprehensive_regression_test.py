#!/usr/bin/env python3
"""
Comprehensive Regression Testing Suite
Executes performance benchmarking, security validation, and full feature testing
"""

import os
import sys
import json
import time
import logging
import requests
import subprocess
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import psutil
import hashlib
import re
from urllib.parse import urlparse

# Configure logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('regression_test.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class ComprehensiveRegressionTester:
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'test_categories': {
                'performance': {},
                'security': {},
                'functionality': {},
                'compatibility': {},
                'infrastructure': {}
            },
            'performance_metrics': {},
            'security_findings': {},
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
        self.start_time = time.time()
        
    def log_test_result(self, category: str, test_name: str, passed: bool, details: str, critical: bool = False, metrics: Dict = None):
        """Log test result and update summary"""
        status = "[PASS]" if passed else "[FAIL]"
        logger.info(f"{status} {category}/{test_name}: {details}")
        
        if category not in self.results['test_categories']:
            self.results['test_categories'][category] = {}
            
        self.results['test_categories'][category][test_name] = {
            'passed': passed,
            'details': details,
            'critical': critical,
            'timestamp': datetime.now().isoformat(),
            'metrics': metrics or {}
        }
        
        if metrics:
            self.results['performance_metrics'][f"{category}_{test_name}"] = metrics
        
        self.results['summary']['total_tests'] += 1
        if passed:
            self.results['summary']['passed'] += 1
        else:
            self.results['summary']['failed'] += 1
            if critical:
                self.results['summary']['critical_issues'].append(f"{category}/{test_name}: {details}")
            else:
                self.results['summary']['warnings'].append(f"{category}/{test_name}: {details}")
    
    def test_system_performance(self):
        """Test system performance metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage_mb = memory.used / (1024 * 1024)
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('.')
            disk_percent = (disk.used / disk.total) * 100
            
            metrics = {
                'cpu_percent': cpu_percent,
                'memory_usage_mb': round(memory_usage_mb, 2),
                'memory_percent': memory_percent,
                'disk_percent': round(disk_percent, 2)
            }
            
            # Performance thresholds
            performance_good = (
                cpu_percent < 80 and
                memory_percent < 85 and
                disk_percent < 90
            )
            
            self.log_test_result(
                'performance',
                'System Resources',
                performance_good,
                f"CPU: {cpu_percent}%, Memory: {memory_percent:.1f}%, Disk: {disk_percent:.1f}%",
                critical=not performance_good,
                metrics=metrics
            )
            
        except Exception as e:
            self.log_test_result(
                'performance',
                'System Resources',
                False,
                f'Error measuring system performance: {str(e)}',
                critical=True
            )
    
    def test_build_performance(self):
        """Test build and compilation performance"""
        try:
            # Check if package.json exists
            package_json = self.project_root / 'package.json'
            if not package_json.exists():
                self.log_test_result(
                    'performance',
                    'Build Performance',
                    False,
                    'No package.json found - cannot test build performance',
                    critical=True
                )
                return
            
            # Test TypeScript compilation if tsconfig exists
            tsconfig = self.project_root / 'tsconfig.json'
            if tsconfig.exists():
                start_time = time.time()
                try:
                    result = subprocess.run(
                        ['npx', 'tsc', '--noEmit'],
                        cwd=self.project_root,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    compile_time = time.time() - start_time
                    
                    metrics = {
                        'typescript_compile_time_seconds': round(compile_time, 2),
                        'typescript_errors': len(result.stderr.split('\n')) if result.stderr else 0
                    }
                    
                    if result.returncode == 0:
                        self.log_test_result(
                            'performance',
                            'TypeScript Compilation',
                            True,
                            f'Compilation successful in {compile_time:.2f}s',
                            metrics=metrics
                        )
                    else:
                        self.log_test_result(
                            'performance',
                            'TypeScript Compilation',
                            False,
                            f'Compilation failed with {metrics["typescript_errors"]} errors',
                            critical=True,
                            metrics=metrics
                        )
                        
                except subprocess.TimeoutExpired:
                    self.log_test_result(
                        'performance',
                        'TypeScript Compilation',
                        False,
                        'Compilation timeout (>60s) - performance issue',
                        critical=True
                    )
                except Exception as e:
                    self.log_test_result(
                        'performance',
                        'TypeScript Compilation',
                        False,
                        f'Compilation error: {str(e)}'
                    )
            else:
                self.log_test_result(
                    'performance',
                    'TypeScript Compilation',
                    True,
                    'No TypeScript configuration found - skipping'
                )
                
        except Exception as e:
            self.log_test_result(
                'performance',
                'Build Performance',
                False,
                f'Error testing build performance: {str(e)}'
            )
    
    def test_dependency_security(self):
        """Test dependency security vulnerabilities"""
        try:
            package_json = self.project_root / 'package.json'
            if not package_json.exists():
                self.log_test_result(
                    'security',
                    'Dependency Security',
                    False,
                    'No package.json found - cannot audit dependencies',
                    critical=True
                )
                return
            
            # Run npm audit
            try:
                result = subprocess.run(
                    ['npm', 'audit', '--json'],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.stdout:
                    try:
                        audit_data = json.loads(result.stdout)
                        vulnerabilities = audit_data.get('vulnerabilities', {})
                        
                        critical_vulns = sum(1 for v in vulnerabilities.values() if v.get('severity') == 'critical')
                        high_vulns = sum(1 for v in vulnerabilities.values() if v.get('severity') == 'high')
                        moderate_vulns = sum(1 for v in vulnerabilities.values() if v.get('severity') == 'moderate')
                        
                        metrics = {
                            'critical_vulnerabilities': critical_vulns,
                            'high_vulnerabilities': high_vulns,
                            'moderate_vulnerabilities': moderate_vulns,
                            'total_vulnerabilities': len(vulnerabilities)
                        }
                        
                        self.results['security_findings']['dependency_audit'] = metrics
                        
                        if critical_vulns > 0:
                            self.log_test_result(
                                'security',
                                'Dependency Security',
                                False,
                                f'Critical vulnerabilities found: {critical_vulns} critical, {high_vulns} high',
                                critical=True,
                                metrics=metrics
                            )
                        elif high_vulns > 0:
                            self.log_test_result(
                                'security',
                                'Dependency Security',
                                False,
                                f'High vulnerabilities found: {high_vulns} high, {moderate_vulns} moderate',
                                metrics=metrics
                            )
                        else:
                            self.log_test_result(
                                'security',
                                'Dependency Security',
                                True,
                                f'No critical/high vulnerabilities found: {moderate_vulns} moderate',
                                metrics=metrics
                            )
                            
                    except json.JSONDecodeError:
                        self.log_test_result(
                            'security',
                            'Dependency Security',
                            False,
                            'Unable to parse npm audit output'
                        )
                else:
                    self.log_test_result(
                        'security',
                        'Dependency Security',
                        True,
                        'No vulnerabilities detected'
                    )
                    
            except subprocess.TimeoutExpired:
                self.log_test_result(
                    'security',
                    'Dependency Security',
                    False,
                    'npm audit timeout - unable to complete security scan'
                )
            except Exception as e:
                self.log_test_result(
                    'security',
                    'Dependency Security',
                    False,
                    f'npm audit failed: {str(e)}'
                )
                
        except Exception as e:
            self.log_test_result(
                'security',
                'Dependency Security',
                False,
                f'Error testing dependency security: {str(e)}'
            )
    
    def test_code_security_patterns(self):
        """Test for insecure code patterns"""
        try:
            security_issues = []
            
            # Search in source files for basic security patterns
            src_path = self.project_root / 'src'
            if src_path.exists():
                for file_path in src_path.rglob('*'):
                    if file_path.suffix in ['.ts', '.tsx', '.js', '.jsx']:
                        try:
                            content = file_path.read_text(encoding='utf-8')
                            
                            # Check for hardcoded secrets (simple patterns)
                            if 'password=' in content.lower() or 'apikey=' in content.lower():
                                security_issues.append({
                                    'file': str(file_path.relative_to(self.project_root)),
                                    'type': 'hardcoded_secrets',
                                    'matches': 1
                                })
                            
                            # Check for console logs
                            if 'console.log(' in content or 'console.debug(' in content:
                                security_issues.append({
                                    'file': str(file_path.relative_to(self.project_root)),
                                    'type': 'console_logs',
                                    'matches': content.count('console.')
                                })
                            
                            # Check for innerHTML usage
                            if 'innerHTML' in content:
                                security_issues.append({
                                    'file': str(file_path.relative_to(self.project_root)),
                                    'type': 'xss_vulnerabilities',
                                    'matches': content.count('innerHTML')
                                })
                                        
                        except Exception:
                            continue
            
            # Categorize security issues
            critical_issues = [issue for issue in security_issues if issue['type'] in ['hardcoded_secrets', 'xss_vulnerabilities']]
            warning_issues = [issue for issue in security_issues if issue['type'] in ['console_logs']]
            
            metrics = {
                'critical_security_issues': len(critical_issues),
                'warning_security_issues': len(warning_issues),
                'total_security_issues': len(security_issues)
            }
            
            self.results['security_findings']['code_patterns'] = {
                'critical_issues': critical_issues,
                'warning_issues': warning_issues,
                'metrics': metrics
            }
            
            if len(critical_issues) > 0:
                self.log_test_result(
                    'security',
                    'Code Security Patterns',
                    False,
                    f'Critical security issues found: {len(critical_issues)} critical, {len(warning_issues)} warnings',
                    critical=True,
                    metrics=metrics
                )
            elif len(warning_issues) > 10:
                self.log_test_result(
                    'security',
                    'Code Security Patterns',
                    False,
                    f'Multiple security warnings: {len(warning_issues)} issues found',
                    metrics=metrics
                )
            else:
                self.log_test_result(
                    'security',
                    'Code Security Patterns',
                    True,
                    f'No critical security issues: {len(warning_issues)} minor warnings',
                    metrics=metrics
                )
                
        except Exception as e:
            self.log_test_result(
                'security',
                'Code Security Patterns',
                False,
                f'Error scanning code security patterns: {str(e)}'
            )
    
    def test_api_functionality(self):
        """Test API functionality and endpoints"""
        try:
            # Check for API routes
            api_path = self.project_root / 'api'
            if not api_path.exists():
                self.log_test_result(
                    'functionality',
                    'API Functionality',
                    False,
                    'No API directory found',
                    critical=True
                )
                return
            
            # Count API endpoints
            endpoint_count = 0
            route_files = []
            
            for file_path in api_path.rglob('*.py'):
                try:
                    content = file_path.read_text(encoding='utf-8')
                    if any(term in content.lower() for term in ['@app.', '@router.', 'fastapi', 'flask']):
                        route_files.append(str(file_path.relative_to(self.project_root)))
                        # Count route decorators
                        endpoint_count += content.lower().count('@app.') + content.lower().count('@router.')
                except Exception:
                    continue
            
            metrics = {
                'api_route_files': len(route_files),
                'estimated_endpoints': endpoint_count
            }
            
            if endpoint_count >= 5:
                self.log_test_result(
                    'functionality',
                    'API Functionality',
                    True,
                    f'API implementation found: {endpoint_count} endpoints in {len(route_files)} files',
                    metrics=metrics
                )
            elif endpoint_count >= 1:
                self.log_test_result(
                    'functionality',
                    'API Functionality',
                    True,
                    f'Basic API implementation: {endpoint_count} endpoints',
                    metrics=metrics
                )
            else:
                self.log_test_result(
                    'functionality',
                    'API Functionality',
                    False,
                    'No API endpoints detected',
                    critical=True,
                    metrics=metrics
                )
                
        except Exception as e:
            self.log_test_result(
                'functionality',
                'API Functionality',
                False,
                f'Error testing API functionality: {str(e)}'
            )
    
    def test_frontend_functionality(self):
        """Test frontend functionality and components"""
        try:
            src_path = self.project_root / 'src'
            if not src_path.exists():
                self.log_test_result(
                    'functionality',
                    'Frontend Functionality',
                    False,
                    'No src directory found',
                    critical=True
                )
                return
            
            # Count components and pages
            component_count = 0
            page_count = 0
            hook_count = 0
            
            for file_path in src_path.rglob('*'):
                if file_path.suffix in ['.ts', '.tsx', '.js', '.jsx']:
                    try:
                        content = file_path.read_text(encoding='utf-8')
                        
                        # Check for React components
                        if 'export default function' in content or 'export const' in content:
                            if 'components' in str(file_path):
                                component_count += 1
                            elif any(term in str(file_path).lower() for term in ['page', 'view', 'screen']):
                                page_count += 1
                        
                        # Check for custom hooks
                        if 'use' in content and 'hook' in str(file_path).lower():
                            hook_count += 1
                            
                    except Exception:
                        continue
            
            metrics = {
                'component_count': component_count,
                'page_count': page_count,
                'hook_count': hook_count
            }
            
            total_components = component_count + page_count
            
            if total_components >= 10:
                self.log_test_result(
                    'functionality',
                    'Frontend Functionality',
                    True,
                    f'Rich frontend: {component_count} components, {page_count} pages, {hook_count} hooks',
                    metrics=metrics
                )
            elif total_components >= 3:
                self.log_test_result(
                    'functionality',
                    'Frontend Functionality',
                    True,
                    f'Basic frontend: {component_count} components, {page_count} pages',
                    metrics=metrics
                )
            else:
                self.log_test_result(
                    'functionality',
                    'Frontend Functionality',
                    False,
                    'Minimal frontend implementation detected',
                    metrics=metrics
                )
                
        except Exception as e:
            self.log_test_result(
                'functionality',
                'Frontend Functionality',
                False,
                f'Error testing frontend functionality: {str(e)}'
            )
    
    def test_database_functionality(self):
        """Test database functionality and models"""
        try:
            # Check for database models and configurations
            database_indicators = {
                'supabase': False,
                'prisma': False,
                'mongoose': False,
                'sqlalchemy': False,
                'database_models': 0
            }
            
            # Check configuration files
            config_files = ['package.json', '.env', '.env.local', 'supabase/config.toml']
            for config_file in config_files:
                file_path = self.project_root / config_file
                if file_path.exists():
                    try:
                        content = file_path.read_text(encoding='utf-8').lower()
                        
                        if 'supabase' in content:
                            database_indicators['supabase'] = True
                        if 'prisma' in content:
                            database_indicators['prisma'] = True
                        if 'mongoose' in content:
                            database_indicators['mongoose'] = True
                        if 'sqlalchemy' in content:
                            database_indicators['sqlalchemy'] = True
                            
                    except Exception:
                        continue
            
            # Check for model files
            search_paths = [self.project_root / 'api', self.project_root / 'src']
            for search_path in search_paths:
                if search_path.exists():
                    for file_path in search_path.rglob('*'):
                        if file_path.suffix in ['.py', '.ts', '.js']:
                            try:
                                content = file_path.read_text(encoding='utf-8').lower()
                                
                                if any(term in content for term in ['model', 'schema', 'table', 'collection']):
                                    database_indicators['database_models'] += 1
                                    
                            except Exception:
                                continue
            
            configured_dbs = [k for k, v in database_indicators.items() if v and k != 'database_models']
            model_count = database_indicators['database_models']
            
            metrics = {
                'configured_databases': len(configured_dbs),
                'database_types': configured_dbs,
                'model_files': model_count
            }
            
            if len(configured_dbs) >= 1 and model_count >= 3:
                self.log_test_result(
                    'functionality',
                    'Database Functionality',
                    True,
                    f'Database configured: {", ".join(configured_dbs)} with {model_count} model files',
                    metrics=metrics
                )
            elif len(configured_dbs) >= 1:
                self.log_test_result(
                    'functionality',
                    'Database Functionality',
                    True,
                    f'Database configured: {", ".join(configured_dbs)} with basic models',
                    metrics=metrics
                )
            else:
                self.log_test_result(
                    'functionality',
                    'Database Functionality',
                    False,
                    'No database configuration detected',
                    critical=True,
                    metrics=metrics
                )
                
        except Exception as e:
            self.log_test_result(
                'functionality',
                'Database Functionality',
                False,
                f'Error testing database functionality: {str(e)}'
            )
    
    def test_browser_compatibility(self):
        """Test browser compatibility features"""
        try:
            # Check for browser compatibility configurations
            compatibility_features = {
                'babel_config': False,
                'browserslist': False,
                'polyfills': False,
                'css_prefixes': False,
                'es6_transpilation': False
            }
            
            # Check configuration files
            config_files = {
                'babel.config.js': 'babel_config',
                '.babelrc': 'babel_config',
                'package.json': 'browserslist',
                '.browserslistrc': 'browserslist'
            }
            
            for config_file, feature in config_files.items():
                file_path = self.project_root / config_file
                if file_path.exists():
                    try:
                        content = file_path.read_text(encoding='utf-8').lower()
                        
                        if feature == 'babel_config' and 'babel' in content:
                            compatibility_features['babel_config'] = True
                        elif feature == 'browserslist' and 'browserslist' in content:
                            compatibility_features['browserslist'] = True
                            
                        # Check for polyfills
                        if any(term in content for term in ['polyfill', 'core-js']):
                            compatibility_features['polyfills'] = True
                            
                    except Exception:
                        continue
            
            # Check source files for compatibility features
            src_path = self.project_root / 'src'
            if src_path.exists():
                for file_path in src_path.rglob('*'):
                    if file_path.suffix in ['.ts', '.tsx', '.js', '.jsx', '.css', '.scss']:
                        try:
                            content = file_path.read_text(encoding='utf-8').lower()
                            
                            # Check for CSS prefixes
                            if any(prefix in content for prefix in ['-webkit-', '-moz-', '-ms-', '-o-']):
                                compatibility_features['css_prefixes'] = True
                            
                            # Check for ES6+ features with transpilation
                            if any(feature in content for feature in ['=>', 'const ', 'let ']):
                                compatibility_features['es6_transpilation'] = True
                                
                        except Exception:
                            continue
            
            implemented_features = [k for k, v in compatibility_features.items() if v]
            
            metrics = {
                'compatibility_features': len(implemented_features),
                'features': implemented_features
            }
            
            if len(implemented_features) >= 4:
                self.log_test_result(
                    'compatibility',
                    'Browser Compatibility',
                    True,
                    f'Excellent browser support: {", ".join(implemented_features)}',
                    metrics=metrics
                )
            elif len(implemented_features) >= 2:
                self.log_test_result(
                    'compatibility',
                    'Browser Compatibility',
                    True,
                    f'Good browser support: {", ".join(implemented_features)}',
                    metrics=metrics
                )
            else:
                self.log_test_result(
                    'compatibility',
                    'Browser Compatibility',
                    False,
                    'Limited browser compatibility features',
                    metrics=metrics
                )
                
        except Exception as e:
            self.log_test_result(
                'compatibility',
                'Browser Compatibility',
                False,
                f'Error testing browser compatibility: {str(e)}'
            )
    
    def test_responsive_design(self):
        """Test responsive design implementation"""
        try:
            responsive_features = {
                'css_media_queries': 0,
                'tailwind_responsive': False,
                'bootstrap_responsive': False,
                'flexbox_grid': False,
                'mobile_first': False
            }
            
            src_path = self.project_root / 'src'
            if src_path.exists():
                for file_path in src_path.rglob('*'):
                    if file_path.suffix in ['.css', '.scss', '.ts', '.tsx', '.js', '.jsx']:
                        try:
                            content = file_path.read_text(encoding='utf-8').lower()
                            
                            # Count media queries
                            responsive_features['css_media_queries'] += content.count('@media')
                            
                            # Check for responsive frameworks
                            if any(cls in content for cls in ['sm:', 'md:', 'lg:', 'xl:']):
                                responsive_features['tailwind_responsive'] = True
                            if any(cls in content for cls in ['col-sm-', 'col-md-', 'col-lg-']):
                                responsive_features['bootstrap_responsive'] = True
                            if any(term in content for term in ['flexbox', 'flex', 'grid']):
                                responsive_features['flexbox_grid'] = True
                            if 'mobile-first' in content or 'min-width' in content:
                                responsive_features['mobile_first'] = True
                                
                        except Exception:
                            continue
            
            # Evaluate responsive design quality
            responsive_score = 0
            if responsive_features['css_media_queries'] >= 3:
                responsive_score += 2
            elif responsive_features['css_media_queries'] >= 1:
                responsive_score += 1
                
            if responsive_features['tailwind_responsive'] or responsive_features['bootstrap_responsive']:
                responsive_score += 2
            if responsive_features['flexbox_grid']:
                responsive_score += 1
            if responsive_features['mobile_first']:
                responsive_score += 1
            
            metrics = {
                'responsive_score': responsive_score,
                'media_queries': responsive_features['css_media_queries'],
                'framework_responsive': responsive_features['tailwind_responsive'] or responsive_features['bootstrap_responsive']
            }
            
            if responsive_score >= 5:
                self.log_test_result(
                    'compatibility',
                    'Responsive Design',
                    True,
                    f'Excellent responsive design: {responsive_features["css_media_queries"]} media queries, framework support',
                    metrics=metrics
                )
            elif responsive_score >= 3:
                self.log_test_result(
                    'compatibility',
                    'Responsive Design',
                    True,
                    f'Good responsive design: {responsive_features["css_media_queries"]} media queries',
                    metrics=metrics
                )
            else:
                self.log_test_result(
                    'compatibility',
                    'Responsive Design',
                    False,
                    'Limited responsive design implementation',
                    metrics=metrics
                )
                
        except Exception as e:
            self.log_test_result(
                'compatibility',
                'Responsive Design',
                False,
                f'Error testing responsive design: {str(e)}'
            )
    
    def test_infrastructure_readiness(self):
        """Test infrastructure and deployment readiness"""
        try:
            infrastructure_features = {
                'docker': False,
                'ci_cd': False,
                'environment_config': False,
                'build_scripts': False,
                'deployment_config': False
            }
            
            # Check for infrastructure files
            infra_files = {
                'Dockerfile': 'docker',
                'docker-compose.yml': 'docker',
                '.github/workflows': 'ci_cd',
                '.gitlab-ci.yml': 'ci_cd',
                'vercel.json': 'deployment_config',
                'netlify.toml': 'deployment_config',
                '.env.example': 'environment_config'
            }
            
            for file_name, feature in infra_files.items():
                file_path = self.project_root / file_name
                if file_path.exists():
                    infrastructure_features[feature] = True
            
            # Check package.json for build scripts
            package_json = self.project_root / 'package.json'
            if package_json.exists():
                try:
                    with open(package_json, 'r', encoding='utf-8') as f:
                        package_data = json.load(f)
                        scripts = package_data.get('scripts', {})
                        
                        if any(script in scripts for script in ['build', 'start', 'dev']):
                            infrastructure_features['build_scripts'] = True
                            
                except Exception:
                    pass
            
            implemented_features = [k for k, v in infrastructure_features.items() if v]
            
            metrics = {
                'infrastructure_features': len(implemented_features),
                'features': implemented_features
            }
            
            if len(implemented_features) >= 4:
                self.log_test_result(
                    'infrastructure',
                    'Infrastructure Readiness',
                    True,
                    f'Production-ready infrastructure: {", ".join(implemented_features)}',
                    metrics=metrics
                )
            elif len(implemented_features) >= 2:
                self.log_test_result(
                    'infrastructure',
                    'Infrastructure Readiness',
                    True,
                    f'Basic infrastructure: {", ".join(implemented_features)}',
                    metrics=metrics
                )
            else:
                self.log_test_result(
                    'infrastructure',
                    'Infrastructure Readiness',
                    False,
                    'Minimal infrastructure configuration',
                    critical=True,
                    metrics=metrics
                )
                
        except Exception as e:
            self.log_test_result(
                'infrastructure',
                'Infrastructure Readiness',
                False,
                f'Error testing infrastructure readiness: {str(e)}'
            )
    
    def run_all_tests(self):
        """Run all regression tests"""
        logger.info("Starting comprehensive regression testing...")
        
        # Performance tests
        self.test_system_performance()
        self.test_build_performance()
        
        # Security tests
        self.test_dependency_security()
        self.test_code_security_patterns()
        
        # Functionality tests
        self.test_api_functionality()
        self.test_frontend_functionality()
        self.test_database_functionality()
        
        # Compatibility tests
        self.test_browser_compatibility()
        self.test_responsive_design()
        
        # Infrastructure tests
        self.test_infrastructure_readiness()
        
        # Calculate overall metrics
        total_time = time.time() - self.start_time
        
        # Determine production readiness
        critical_failures = len(self.results['summary']['critical_issues'])
        total_tests = self.results['summary']['total_tests']
        passed_tests = self.results['summary']['passed']
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        self.results['summary']['success_rate'] = success_rate
        self.results['summary']['test_duration_seconds'] = round(total_time, 2)
        self.results['summary']['production_ready'] = critical_failures <= 2 and success_rate >= 75
        
        return self.results
    
    def generate_report(self):
        """Generate detailed regression test report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f'regression_test_report_{timestamp}.json'
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Detailed report saved to: {report_file}")
        return report_file
    
    def print_summary(self):
        """Print comprehensive regression test summary"""
        summary = self.results['summary']
        
        print("\n" + "="*80)
        print("COMPREHENSIVE REGRESSION TEST SUMMARY")
        print("="*80)
        
        print(f"\nTest Duration: {summary.get('test_duration_seconds', 0):.1f} seconds")
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Success Rate: {summary.get('success_rate', 0):.1f}%")
        
        # Category breakdown
        print("\n[INFO] Test Categories:")
        for category, tests in self.results['test_categories'].items():
            if tests:
                passed = sum(1 for test in tests.values() if test['passed'])
                total = len(tests)
                print(f"  {category.title()}: {passed}/{total} passed")
        
        # Performance metrics summary
        if self.results['performance_metrics']:
            print("\n[INFO] Key Performance Metrics:")
            for test_name, metrics in self.results['performance_metrics'].items():
                print(f"  {test_name}:")
                for key, value in metrics.items():
                    print(f"    - {key}: {value}")
        
        # Security findings summary
        if self.results['security_findings']:
            print("\n[INFO] Security Findings:")
            for finding_type, findings in self.results['security_findings'].items():
                if isinstance(findings, dict) and 'metrics' in findings:
                    metrics = findings['metrics']
                    print(f"  {finding_type.title()}:")
                    for key, value in metrics.items():
                        print(f"    - {key}: {value}")
        
        status = "PRODUCTION READY" if summary['production_ready'] else "NOT PRODUCTION READY"
        status_marker = "[SUCCESS]" if summary['production_ready'] else "[CRITICAL]"
        print(f"\nOverall Status: {status_marker} {status}")
        
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
        tester = ComprehensiveRegressionTester()
        results = tester.run_all_tests()
        
        # Generate detailed report
        report_file = tester.generate_report()
        
        # Print summary
        tester.print_summary()
        
        # Exit with appropriate code
        if results['summary']['production_ready']:
            logger.info("Comprehensive regression testing completed successfully")
            sys.exit(0)
        else:
            logger.error("Comprehensive regression testing failed - critical issues found")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Regression testing failed: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()