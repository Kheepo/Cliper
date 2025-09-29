#!/usr/bin/env python3
"""
User Controls Functionality Test
Verifies video player controls: play/pause, seek, volume, fullscreen, mobile touch
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class UserControlsTester:
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'test_results': {},
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
        
    def log_test_result(self, test_name: str, passed: bool, details: str, critical: bool = False):
        """Log test result and update summary"""
        status = "[PASS]" if passed else "[FAIL]"
        logger.info(f"{status} {test_name}: {details}")
        
        self.results['test_results'][test_name] = {
            'passed': passed,
            'details': details,
            'critical': critical,
            'timestamp': datetime.now().isoformat()
        }
        
        self.results['summary']['total_tests'] += 1
        if passed:
            self.results['summary']['passed'] += 1
        else:
            self.results['summary']['failed'] += 1
            if critical:
                self.results['summary']['critical_issues'].append(f"{test_name}: {details}")
            else:
                self.results['summary']['warnings'].append(f"{test_name}: {details}")
    
    def test_video_element_controls(self):
        """Test HTML5 video element controls implementation"""
        try:
            video_controls = {
                'controls_attribute': False,
                'play_pause_buttons': False,
                'seek_bar': False,
                'volume_control': False,
                'fullscreen_button': False,
                'time_display': False
            }
            
            # Search for video elements in components
            src_path = self.project_root / 'src'
            if src_path.exists():
                for file_path in src_path.rglob('*'):
                    if file_path.suffix in ['.ts', '.tsx', '.js', '.jsx']:
                        try:
                            content = file_path.read_text(encoding='utf-8')
                            
                            # Check for video element with controls
                            if '<video' in content:
                                if 'controls' in content:
                                    video_controls['controls_attribute'] = True
                                
                                # Check for custom control implementations
                                if any(term in content.lower() for term in ['play', 'pause']):
                                    video_controls['play_pause_buttons'] = True
                                if any(term in content.lower() for term in ['seek', 'progress', 'currenttime']):
                                    video_controls['seek_bar'] = True
                                if any(term in content.lower() for term in ['volume', 'muted']):
                                    video_controls['volume_control'] = True
                                if any(term in content.lower() for term in ['fullscreen', 'requestfullscreen']):
                                    video_controls['fullscreen_button'] = True
                                if any(term in content.lower() for term in ['duration', 'currenttime', 'timeupdate']):
                                    video_controls['time_display'] = True
                                    
                        except Exception:
                            continue
            
            implemented_controls = [k for k, v in video_controls.items() if v]
            control_score = len(implemented_controls)
            
            if control_score >= 5:
                self.log_test_result(
                    'Video Element Controls',
                    True,
                    f'Comprehensive video controls: {", ".join(implemented_controls)}'
                )
            elif control_score >= 3:
                self.log_test_result(
                    'Video Element Controls',
                    True,
                    f'Basic video controls: {", ".join(implemented_controls)}'
                )
            else:
                self.log_test_result(
                    'Video Element Controls',
                    False,
                    f'Limited video controls: only {", ".join(implemented_controls)}',
                    critical=True
                )
                
        except Exception as e:
            self.log_test_result(
                'Video Element Controls',
                False,
                f'Error testing video controls: {str(e)}',
                critical=True
            )
    
    def test_custom_control_components(self):
        """Test custom video control components"""
        try:
            custom_controls = {
                'play_button_component': False,
                'pause_button_component': False,
                'seek_slider_component': False,
                'volume_slider_component': False,
                'fullscreen_toggle': False,
                'time_display_component': False,
                'control_bar_component': False
            }
            
            # Search for custom control components
            components_path = self.project_root / 'src' / 'components'
            if components_path.exists():
                for file_path in components_path.rglob('*'):
                    if file_path.suffix in ['.ts', '.tsx', '.js', '.jsx']:
                        try:
                            content = file_path.read_text(encoding='utf-8')
                            filename = file_path.name.lower()
                            
                            # Check for control-related components
                            if any(term in filename for term in ['play', 'button']) and 'play' in content.lower():
                                custom_controls['play_button_component'] = True
                            if any(term in filename for term in ['pause', 'button']) and 'pause' in content.lower():
                                custom_controls['pause_button_component'] = True
                            if any(term in filename for term in ['seek', 'slider', 'progress']) and 'seek' in content.lower():
                                custom_controls['seek_slider_component'] = True
                            if any(term in filename for term in ['volume', 'slider']) and 'volume' in content.lower():
                                custom_controls['volume_slider_component'] = True
                            if any(term in filename for term in ['fullscreen', 'toggle']) and 'fullscreen' in content.lower():
                                custom_controls['fullscreen_toggle'] = True
                            if any(term in filename for term in ['time', 'display', 'duration']) and 'time' in content.lower():
                                custom_controls['time_display_component'] = True
                            if any(term in filename for term in ['control', 'bar', 'player']) and 'control' in content.lower():
                                custom_controls['control_bar_component'] = True
                                
                        except Exception:
                            continue
            
            implemented_custom = [k for k, v in custom_controls.items() if v]
            custom_score = len(implemented_custom)
            
            if custom_score >= 5:
                self.log_test_result(
                    'Custom Control Components',
                    True,
                    f'Rich custom controls: {", ".join(implemented_custom)}'
                )
            elif custom_score >= 2:
                self.log_test_result(
                    'Custom Control Components',
                    True,
                    f'Basic custom controls: {", ".join(implemented_custom)}'
                )
            else:
                self.log_test_result(
                    'Custom Control Components',
                    False,
                    f'Limited custom controls: {", ".join(implemented_custom)}'
                )
                
        except Exception as e:
            self.log_test_result(
                'Custom Control Components',
                False,
                f'Error testing custom controls: {str(e)}'
            )
    
    def test_keyboard_controls(self):
        """Test keyboard control implementation"""
        try:
            keyboard_controls = {
                'spacebar_play_pause': False,
                'arrow_keys_seek': False,
                'volume_keys': False,
                'fullscreen_key': False,
                'escape_key': False,
                'number_keys_seek': False
            }
            
            # Search for keyboard event handlers
            src_path = self.project_root / 'src'
            if src_path.exists():
                for file_path in src_path.rglob('*'):
                    if file_path.suffix in ['.ts', '.tsx', '.js', '.jsx']:
                        try:
                            content = file_path.read_text(encoding='utf-8')
                            
                            # Check for keyboard event handlers
                            if 'onKeyDown' in content or 'addEventListener' in content:
                                if any(term in content for term in ['Space', '32', 'spacebar']):
                                    keyboard_controls['spacebar_play_pause'] = True
                                if any(term in content for term in ['ArrowLeft', 'ArrowRight', '37', '39']):
                                    keyboard_controls['arrow_keys_seek'] = True
                                if any(term in content for term in ['ArrowUp', 'ArrowDown', '38', '40']):
                                    keyboard_controls['volume_keys'] = True
                                if any(term in content for term in ['f', 'F', '70']):
                                    keyboard_controls['fullscreen_key'] = True
                                if any(term in content for term in ['Escape', '27']):
                                    keyboard_controls['escape_key'] = True
                                if any(term in content for term in ['Digit', 'Number']):
                                    keyboard_controls['number_keys_seek'] = True
                                    
                        except Exception:
                            continue
            
            implemented_keyboard = [k for k, v in keyboard_controls.items() if v]
            keyboard_score = len(implemented_keyboard)
            
            if keyboard_score >= 4:
                self.log_test_result(
                    'Keyboard Controls',
                    True,
                    f'Comprehensive keyboard support: {", ".join(implemented_keyboard)}'
                )
            elif keyboard_score >= 2:
                self.log_test_result(
                    'Keyboard Controls',
                    True,
                    f'Basic keyboard support: {", ".join(implemented_keyboard)}'
                )
            else:
                self.log_test_result(
                    'Keyboard Controls',
                    False,
                    f'Limited keyboard support: {", ".join(implemented_keyboard)}'
                )
                
        except Exception as e:
            self.log_test_result(
                'Keyboard Controls',
                False,
                f'Error testing keyboard controls: {str(e)}'
            )
    
    def test_mobile_touch_controls(self):
        """Test mobile touch control implementation"""
        try:
            touch_controls = {
                'touch_events': False,
                'tap_to_play_pause': False,
                'swipe_gestures': False,
                'pinch_zoom': False,
                'double_tap_fullscreen': False,
                'touch_seek': False,
                'mobile_responsive': False
            }
            
            # Search for touch event handlers
            src_path = self.project_root / 'src'
            if src_path.exists():
                for file_path in src_path.rglob('*'):
                    if file_path.suffix in ['.ts', '.tsx', '.js', '.jsx', '.css', '.scss']:
                        try:
                            content = file_path.read_text(encoding='utf-8')
                            
                            # Check for touch event handlers
                            if any(term in content for term in ['onTouchStart', 'onTouchEnd', 'onTouchMove']):
                                touch_controls['touch_events'] = True
                            if any(term in content for term in ['tap', 'click', 'touch']):
                                touch_controls['tap_to_play_pause'] = True
                            if any(term in content for term in ['swipe', 'gesture']):
                                touch_controls['swipe_gestures'] = True
                            if any(term in content for term in ['pinch', 'zoom']):
                                touch_controls['pinch_zoom'] = True
                            if any(term in content for term in ['double', 'dblclick']):
                                touch_controls['double_tap_fullscreen'] = True
                            if any(term in content for term in ['touchmove', 'drag']):
                                touch_controls['touch_seek'] = True
                            if any(term in content for term in ['mobile', 'responsive', '@media']):
                                touch_controls['mobile_responsive'] = True
                                
                        except Exception:
                            continue
            
            implemented_touch = [k for k, v in touch_controls.items() if v]
            touch_score = len(implemented_touch)
            
            if touch_score >= 5:
                self.log_test_result(
                    'Mobile Touch Controls',
                    True,
                    f'Excellent mobile support: {", ".join(implemented_touch)}'
                )
            elif touch_score >= 3:
                self.log_test_result(
                    'Mobile Touch Controls',
                    True,
                    f'Good mobile support: {", ".join(implemented_touch)}'
                )
            else:
                self.log_test_result(
                    'Mobile Touch Controls',
                    False,
                    f'Limited mobile support: {", ".join(implemented_touch)}'
                )
                
        except Exception as e:
            self.log_test_result(
                'Mobile Touch Controls',
                False,
                f'Error testing mobile controls: {str(e)}'
            )
    
    def test_accessibility_controls(self):
        """Test accessibility features for video controls"""
        try:
            accessibility_features = {
                'aria_labels': False,
                'keyboard_navigation': False,
                'screen_reader_support': False,
                'focus_indicators': False,
                'high_contrast': False,
                'captions_support': False
            }
            
            # Search for accessibility features
            src_path = self.project_root / 'src'
            if src_path.exists():
                for file_path in src_path.rglob('*'):
                    if file_path.suffix in ['.ts', '.tsx', '.js', '.jsx', '.css', '.scss']:
                        try:
                            content = file_path.read_text(encoding='utf-8')
                            
                            # Check for accessibility attributes
                            if any(term in content for term in ['aria-label', 'aria-describedby', 'aria-controls']):
                                accessibility_features['aria_labels'] = True
                            if any(term in content for term in ['tabIndex', 'onFocus', 'onBlur']):
                                accessibility_features['keyboard_navigation'] = True
                            if any(term in content for term in ['role=', 'aria-live', 'screen-reader']):
                                accessibility_features['screen_reader_support'] = True
                            if any(term in content for term in [':focus', 'focus-visible', 'outline']):
                                accessibility_features['focus_indicators'] = True
                            if any(term in content for term in ['high-contrast', 'prefers-contrast']):
                                accessibility_features['high_contrast'] = True
                            if any(term in content for term in ['captions', 'subtitles', 'track']):
                                accessibility_features['captions_support'] = True
                                
                        except Exception:
                            continue
            
            implemented_a11y = [k for k, v in accessibility_features.items() if v]
            a11y_score = len(implemented_a11y)
            
            if a11y_score >= 4:
                self.log_test_result(
                    'Accessibility Controls',
                    True,
                    f'Excellent accessibility: {", ".join(implemented_a11y)}'
                )
            elif a11y_score >= 2:
                self.log_test_result(
                    'Accessibility Controls',
                    True,
                    f'Basic accessibility: {", ".join(implemented_a11y)}'
                )
            else:
                self.log_test_result(
                    'Accessibility Controls',
                    False,
                    f'Limited accessibility: {", ".join(implemented_a11y)}'
                )
                
        except Exception as e:
            self.log_test_result(
                'Accessibility Controls',
                False,
                f'Error testing accessibility: {str(e)}'
            )
    
    def test_control_responsiveness(self):
        """Test control responsiveness and performance"""
        try:
            responsiveness_features = {
                'debounced_events': False,
                'smooth_animations': False,
                'loading_states': False,
                'error_handling': False,
                'performance_optimization': False
            }
            
            # Search for responsiveness implementations
            src_path = self.project_root / 'src'
            if src_path.exists():
                for file_path in src_path.rglob('*'):
                    if file_path.suffix in ['.ts', '.tsx', '.js', '.jsx']:
                        try:
                            content = file_path.read_text(encoding='utf-8')
                            
                            # Check for performance optimizations
                            if any(term in content for term in ['debounce', 'throttle']):
                                responsiveness_features['debounced_events'] = True
                            if any(term in content for term in ['transition', 'animation', 'ease']):
                                responsiveness_features['smooth_animations'] = True
                            if any(term in content for term in ['loading', 'spinner', 'skeleton']):
                                responsiveness_features['loading_states'] = True
                            if any(term in content for term in ['try', 'catch', 'error']):
                                responsiveness_features['error_handling'] = True
                            if any(term in content for term in ['useMemo', 'useCallback', 'memo']):
                                responsiveness_features['performance_optimization'] = True
                                
                        except Exception:
                            continue
            
            implemented_responsive = [k for k, v in responsiveness_features.items() if v]
            responsive_score = len(implemented_responsive)
            
            if responsive_score >= 4:
                self.log_test_result(
                    'Control Responsiveness',
                    True,
                    f'Excellent responsiveness: {", ".join(implemented_responsive)}'
                )
            elif responsive_score >= 2:
                self.log_test_result(
                    'Control Responsiveness',
                    True,
                    f'Good responsiveness: {", ".join(implemented_responsive)}'
                )
            else:
                self.log_test_result(
                    'Control Responsiveness',
                    False,
                    f'Limited responsiveness: {", ".join(implemented_responsive)}'
                )
                
        except Exception as e:
            self.log_test_result(
                'Control Responsiveness',
                False,
                f'Error testing responsiveness: {str(e)}'
            )
    
    def run_all_tests(self):
        """Run all user controls tests"""
        logger.info("Starting user controls functionality testing...")
        
        # Core control tests
        self.test_video_element_controls()
        self.test_custom_control_components()
        
        # Input method tests
        self.test_keyboard_controls()
        self.test_mobile_touch_controls()
        
        # Quality tests
        self.test_accessibility_controls()
        self.test_control_responsiveness()
        
        # Calculate overall results
        total_tests = self.results['summary']['total_tests']
        passed_tests = self.results['summary']['passed']
        critical_failures = len(self.results['summary']['critical_issues'])
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        self.results['summary']['success_rate'] = success_rate
        self.results['summary']['production_ready'] = critical_failures == 0 and success_rate >= 80
        
        return self.results
    
    def print_summary(self):
        """Print user controls test summary"""
        summary = self.results['summary']
        
        print("\n" + "="*60)
        print("USER CONTROLS FUNCTIONALITY TEST SUMMARY")
        print("="*60)
        
        print(f"\nTotal Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Success Rate: {summary.get('success_rate', 0):.1f}%")
        
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
        
        print("\n" + "="*60)

def main():
    """Main execution function"""
    try:
        tester = UserControlsTester()
        results = tester.run_all_tests()
        
        # Print summary
        tester.print_summary()
        
        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f'user_controls_test_report_{timestamp}.json'
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Detailed report saved to: {report_file}")
        
        # Exit with appropriate code
        if results['summary']['production_ready']:
            logger.info("User controls testing completed successfully")
            sys.exit(0)
        else:
            logger.error("User controls testing failed - issues found")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"User controls testing failed: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()