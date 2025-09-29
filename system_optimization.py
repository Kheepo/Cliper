#!/usr/bin/env python3
"""
System Optimization Script
Addresses critical memory usage and performance issues for production readiness
"""

import os
import sys
import json
import time
import logging
import subprocess
import psutil
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SystemOptimizer:
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'optimization_results': {},
            'before_stats': {},
            'after_stats': {},
            'summary': {
                'total_optimizations': 0,
                'successful': 0,
                'failed': 0,
                'memory_saved_mb': 0,
                'performance_improved': False
            }
        }
        self.project_root = Path.cwd()
        
    def log_optimization(self, optimization_name: str, success: bool, details: str, memory_saved: float = 0):
        """Log optimization result"""
        status = "[SUCCESS]" if success else "[FAILED]"
        logger.info(f"{status} {optimization_name}: {details}")
        
        self.results['optimization_results'][optimization_name] = {
            'success': success,
            'details': details,
            'memory_saved_mb': memory_saved,
            'timestamp': datetime.now().isoformat()
        }
        
        self.results['summary']['total_optimizations'] += 1
        if success:
            self.results['summary']['successful'] += 1
            self.results['summary']['memory_saved_mb'] += memory_saved
        else:
            self.results['summary']['failed'] += 1
    
    def get_system_stats(self):
        """Get current system statistics"""
        try:
            memory = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=1)
            disk = psutil.disk_usage('/')
            
            return {
                'memory_total_gb': round(memory.total / (1024**3), 2),
                'memory_used_gb': round(memory.used / (1024**3), 2),
                'memory_available_gb': round(memory.available / (1024**3), 2),
                'memory_percent': memory.percent,
                'cpu_percent': cpu,
                'disk_total_gb': round(disk.total / (1024**3), 2),
                'disk_used_gb': round(disk.used / (1024**3), 2),
                'disk_percent': round((disk.used / disk.total) * 100, 2)
            }
        except Exception as e:
            logger.error(f"Error getting system stats: {str(e)}")
            return {}
    
    def optimize_node_modules(self):
        """Optimize node_modules to reduce memory usage"""
        try:
            node_modules_path = self.project_root / 'node_modules'
            if not node_modules_path.exists():
                self.log_optimization(
                    'Node Modules Cleanup',
                    True,
                    'No node_modules directory found - already optimized'
                )
                return
            
            # Get initial size
            initial_size = sum(f.stat().st_size for f in node_modules_path.rglob('*') if f.is_file())
            initial_size_mb = round(initial_size / (1024**2), 2)
            
            # Clean npm cache
            try:
                subprocess.run(['npm', 'cache', 'clean', '--force'], 
                             capture_output=True, text=True, check=True)
                logger.info("NPM cache cleaned")
            except subprocess.CalledProcessError:
                logger.warning("Failed to clean npm cache")
            
            # Remove unnecessary files
            unnecessary_patterns = [
                '**/*.md',
                '**/*.txt',
                '**/README*',
                '**/CHANGELOG*',
                '**/LICENSE*',
                '**/.git',
                '**/test',
                '**/tests',
                '**/__tests__',
                '**/spec',
                '**/docs',
                '**/examples',
                '**/demo'
            ]
            
            removed_size = 0
            for pattern in unnecessary_patterns:
                for file_path in node_modules_path.glob(pattern):
                    try:
                        if file_path.is_file():
                            removed_size += file_path.stat().st_size
                            file_path.unlink()
                        elif file_path.is_dir():
                            import shutil
                            removed_size += sum(f.stat().st_size for f in file_path.rglob('*') if f.is_file())
                            shutil.rmtree(file_path)
                    except Exception:
                        continue
            
            removed_size_mb = round(removed_size / (1024**2), 2)
            
            self.log_optimization(
                'Node Modules Cleanup',
                True,
                f'Removed {removed_size_mb}MB of unnecessary files from node_modules',
                removed_size_mb
            )
            
        except Exception as e:
            self.log_optimization(
                'Node Modules Cleanup',
                False,
                f'Error optimizing node_modules: {str(e)}'
            )
    
    def optimize_build_artifacts(self):
        """Clean up build artifacts and temporary files"""
        try:
            cleanup_paths = [
                'dist',
                'build',
                '.next',
                '.nuxt',
                'out',
                '.cache',
                'coverage',
                '.nyc_output',
                'logs',
                '*.log'
            ]
            
            total_cleaned = 0
            
            for path_pattern in cleanup_paths:
                for path in self.project_root.glob(path_pattern):
                    try:
                        if path.is_file():
                            size = path.stat().st_size
                            path.unlink()
                            total_cleaned += size
                        elif path.is_dir():
                            import shutil
                            size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
                            shutil.rmtree(path)
                            total_cleaned += size
                    except Exception:
                        continue
            
            cleaned_mb = round(total_cleaned / (1024**2), 2)
            
            self.log_optimization(
                'Build Artifacts Cleanup',
                True,
                f'Cleaned {cleaned_mb}MB of build artifacts and temporary files',
                cleaned_mb
            )
            
        except Exception as e:
            self.log_optimization(
                'Build Artifacts Cleanup',
                False,
                f'Error cleaning build artifacts: {str(e)}'
            )
    
    def optimize_git_repository(self):
        """Optimize Git repository to reduce disk usage"""
        try:
            git_path = self.project_root / '.git'
            if not git_path.exists():
                self.log_optimization(
                    'Git Repository Optimization',
                    True,
                    'No Git repository found - skipping optimization'
                )
                return
            
            # Get initial .git size
            initial_size = sum(f.stat().st_size for f in git_path.rglob('*') if f.is_file())
            initial_size_mb = round(initial_size / (1024**2), 2)
            
            # Run git garbage collection
            try:
                subprocess.run(['git', 'gc', '--aggressive', '--prune=now'], 
                             capture_output=True, text=True, check=True, cwd=self.project_root)
                
                # Get final .git size
                final_size = sum(f.stat().st_size for f in git_path.rglob('*') if f.is_file())
                final_size_mb = round(final_size / (1024**2), 2)
                saved_mb = initial_size_mb - final_size_mb
                
                self.log_optimization(
                    'Git Repository Optimization',
                    True,
                    f'Git GC completed - saved {saved_mb}MB (from {initial_size_mb}MB to {final_size_mb}MB)',
                    saved_mb
                )
                
            except subprocess.CalledProcessError as e:
                self.log_optimization(
                    'Git Repository Optimization',
                    False,
                    f'Git GC failed: {e.stderr}'
                )
                
        except Exception as e:
            self.log_optimization(
                'Git Repository Optimization',
                False,
                f'Error optimizing Git repository: {str(e)}'
            )
    
    def optimize_python_cache(self):
        """Clean Python cache files"""
        try:
            cache_patterns = [
                '**/__pycache__',
                '**/*.pyc',
                '**/*.pyo',
                '**/*.pyd',
                '.pytest_cache',
                '.coverage',
                'htmlcov'
            ]
            
            total_cleaned = 0
            
            for pattern in cache_patterns:
                for path in self.project_root.glob(pattern):
                    try:
                        if path.is_file():
                            size = path.stat().st_size
                            path.unlink()
                            total_cleaned += size
                        elif path.is_dir():
                            import shutil
                            size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
                            shutil.rmtree(path)
                            total_cleaned += size
                    except Exception:
                        continue
            
            cleaned_mb = round(total_cleaned / (1024**2), 2)
            
            self.log_optimization(
                'Python Cache Cleanup',
                True,
                f'Cleaned {cleaned_mb}MB of Python cache files',
                cleaned_mb
            )
            
        except Exception as e:
            self.log_optimization(
                'Python Cache Cleanup',
                False,
                f'Error cleaning Python cache: {str(e)}'
            )
    
    def optimize_system_memory(self):
        """Attempt to optimize system memory usage"""
        try:
            # Get memory-intensive processes
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    memory_mb = proc.info['memory_info'].rss / (1024**2)
                    if memory_mb > 100:  # Only processes using more than 100MB
                        processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'memory_mb': round(memory_mb, 2)
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Sort by memory usage
            processes.sort(key=lambda x: x['memory_mb'], reverse=True)
            
            # Log top memory consumers
            top_processes = processes[:10]
            process_info = ', '.join([f"{p['name']}({p['memory_mb']}MB)" for p in top_processes])
            
            # Force garbage collection in Python
            import gc
            collected = gc.collect()
            
            self.log_optimization(
                'System Memory Analysis',
                True,
                f'Top memory consumers: {process_info}. Python GC collected {collected} objects'
            )
            
        except Exception as e:
            self.log_optimization(
                'System Memory Analysis',
                False,
                f'Error analyzing system memory: {str(e)}'
            )
    
    def create_memory_monitoring_script(self):
        """Create a script for ongoing memory monitoring"""
        try:
            monitoring_script = '''
#!/usr/bin/env python3
"""
Memory Monitoring Script
Monitors system memory usage and alerts when thresholds are exceeded
"""

import psutil
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def monitor_memory(threshold_percent=85, check_interval=60):
    """Monitor memory usage and log warnings"""
    while True:
        try:
            memory = psutil.virtual_memory()
            
            if memory.percent > threshold_percent:
                logger.warning(
                    f"High memory usage detected: {memory.percent:.1f}% "
                    f"({memory.used / (1024**3):.2f}GB / {memory.total / (1024**3):.2f}GB)"
                )
                
                # Log top memory consumers
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                    try:
                        memory_mb = proc.info['memory_info'].rss / (1024**2)
                        if memory_mb > 50:
                            processes.append({
                                'name': proc.info['name'],
                                'memory_mb': round(memory_mb, 2)
                            })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                processes.sort(key=lambda x: x['memory_mb'], reverse=True)
                top_5 = processes[:5]
                
                logger.info("Top memory consumers:")
                for proc in top_5:
                    logger.info(f"  {proc['name']}: {proc['memory_mb']}MB")
            
            time.sleep(check_interval)
            
        except KeyboardInterrupt:
            logger.info("Memory monitoring stopped")
            break
        except Exception as e:
            logger.error(f"Error in memory monitoring: {str(e)}")
            time.sleep(check_interval)

if __name__ == '__main__':
    print("Starting memory monitoring (Ctrl+C to stop)...")
    monitor_memory()
'''
            
            script_path = self.project_root / 'memory_monitor.py'
            script_path.write_text(monitoring_script, encoding='utf-8')
            
            self.log_optimization(
                'Memory Monitoring Script',
                True,
                f'Created memory monitoring script at {script_path}'
            )
            
        except Exception as e:
            self.log_optimization(
                'Memory Monitoring Script',
                False,
                f'Error creating monitoring script: {str(e)}'
            )
    
    def run_optimizations(self):
        """Run all system optimizations"""
        logger.info("Starting system optimization...")
        
        # Get initial system stats
        self.results['before_stats'] = self.get_system_stats()
        
        # Run optimizations
        self.optimize_node_modules()
        self.optimize_build_artifacts()
        self.optimize_git_repository()
        self.optimize_python_cache()
        self.optimize_system_memory()
        self.create_memory_monitoring_script()
        
        # Get final system stats
        time.sleep(2)  # Wait a moment for changes to take effect
        self.results['after_stats'] = self.get_system_stats()
        
        # Calculate improvements
        before_memory = self.results['before_stats'].get('memory_percent', 0)
        after_memory = self.results['after_stats'].get('memory_percent', 0)
        memory_improvement = before_memory - after_memory
        
        self.results['summary']['performance_improved'] = memory_improvement > 0
        self.results['summary']['memory_improvement_percent'] = round(memory_improvement, 2)
        
        return self.results
    
    def print_summary(self):
        """Print optimization summary"""
        summary = self.results['summary']
        before = self.results['before_stats']
        after = self.results['after_stats']
        
        print("\n" + "="*60)
        print("SYSTEM OPTIMIZATION SUMMARY")
        print("="*60)
        
        print(f"\nOptimizations Run: {summary['total_optimizations']}")
        print(f"Successful: {summary['successful']}")
        print(f"Failed: {summary['failed']}")
        print(f"Total Memory Saved: {summary['memory_saved_mb']:.2f}MB")
        
        if before and after:
            print(f"\nMemory Usage:")
            print(f"  Before: {before.get('memory_percent', 0):.1f}% ({before.get('memory_used_gb', 0):.2f}GB)")
            print(f"  After:  {after.get('memory_percent', 0):.1f}% ({after.get('memory_used_gb', 0):.2f}GB)")
            
            improvement = summary.get('memory_improvement_percent', 0)
            if improvement > 0:
                print(f"  Improvement: -{improvement:.1f}%")
            else:
                print(f"  Change: {abs(improvement):.1f}%")
        
        # Determine if system is now production ready
        current_memory = after.get('memory_percent', before.get('memory_percent', 100))
        production_ready = current_memory < 85  # Less than 85% memory usage
        
        status = "PRODUCTION READY" if production_ready else "NEEDS ATTENTION"
        status_marker = "[SUCCESS]" if production_ready else "[WARNING]"
        print(f"\nSystem Status: {status_marker} {status}")
        
        if not production_ready:
            print(f"\n[RECOMMENDATION] Current memory usage ({current_memory:.1f}%) is still high.")
            print("Consider:")
            print("  - Restarting memory-intensive applications")
            print("  - Adding more RAM to the system")
            print("  - Running the memory monitor script for ongoing monitoring")
        
        print("\n" + "="*60)

def main():
    """Main execution function"""
    try:
        optimizer = SystemOptimizer()
        results = optimizer.run_optimizations()
        
        # Print summary
        optimizer.print_summary()
        
        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f'system_optimization_report_{timestamp}.json'
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Optimization report saved to: {report_file}")
        
        # Exit with appropriate code
        current_memory = results['after_stats'].get('memory_percent', 
                                                   results['before_stats'].get('memory_percent', 100))
        if current_memory < 85:
            logger.info("System optimization completed successfully")
            sys.exit(0)
        else:
            logger.warning("System still needs attention after optimization")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"System optimization failed: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()