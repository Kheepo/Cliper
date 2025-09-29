
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
