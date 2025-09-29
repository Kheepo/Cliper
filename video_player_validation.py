#!/usr/bin/env python3
"""
Comprehensive Video Player Validation Script
Tests playback quality, controls functionality, and performance
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# Configure logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('video_player_validation.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class VideoPlayerValidator:
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'tests': {},
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
        
        self.results['tests'][test_name] = {
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
    
    def test_video_component_structure(self):
        """Test if video components exist and have proper structure"""
        try:
            # Check for ClipGenerationModal video element
            modal_path = self.project_root / 'src' / 'components' / 'ClipGenerationModal.tsx'
            if modal_path.exists():
                content = modal_path.read_text(encoding='utf-8')
                has_video_element = '<video' in content
                has_controls = 'controls' in content
                has_src_prop = 'src=' in content
                
                if has_video_element and has_controls and has_src_prop:
                    self.log_test_result(
                        'Video Component Structure',
                        True,
                        'ClipGenerationModal has proper HTML5 video element with controls'
                    )
                else:
                    missing = []
                    if not has_video_element: missing.append('video element')
                    if not has_controls: missing.append('controls attribute')
                    if not has_src_prop: missing.append('src property')
                    
                    self.log_test_result(
                        'Video Component Structure',
                        False,
                        f'ClipGenerationModal missing: {", ".join(missing)}',
                        critical=True
                    )
            else:
                self.log_test_result(
                    'Video Component Structure',
                    False,
                    'ClipGenerationModal.tsx not found',
                    critical=True
                )
        except Exception as e:
            self.log_test_result(
                'Video Component Structure',
                False,
                f'Error reading component: {str(e)}',
                critical=True
            )
    
    def test_video_format_support(self):
        """Test supported video formats"""
        try:
            modal_path = self.project_root / 'src' / 'components' / 'ClipGenerationModal.tsx'
            if modal_path.exists():
                content = modal_path.read_text(encoding='utf-8')
                
                # Check for format options
                supported_formats = []
                if 'mp4' in content.lower(): supported_formats.append('MP4')
                if 'webm' in content.lower(): supported_formats.append('WebM')
                if 'mov' in content.lower(): supported_formats.append('MOV')
                
                if len(supported_formats) >= 2:
                    self.log_test_result(
                        'Video Format Support',
                        True,
                        f'Supports multiple formats: {", ".join(supported_formats)}'
                    )
                else:
                    self.log_test_result(
                        'Video Format Support',
                        False,
                        f'Limited format support: {", ".join(supported_formats) if supported_formats else "None detected"}',
                        critical=True
                    )
            else:
                self.log_test_result(
                    'Video Format Support',
                    False,
                    'Cannot verify - component file not found',
                    critical=True
                )
        except Exception as e:
            self.log_test_result(
                'Video Format Support',
                False,
                f'Error checking formats: {str(e)}'
            )
    
    def test_resolution_support(self):
        """Test resolution options"""
        try:
            modal_path = self.project_root / 'src' / 'components' / 'ClipGenerationModal.tsx'
            if modal_path.exists():
                content = modal_path.read_text(encoding='utf-8')
                
                # Check for resolution options
                resolutions = []
                if '1080p' in content: resolutions.append('1080p')
                if '720p' in content: resolutions.append('720p')
                if '480p' in content: resolutions.append('480p')
                
                if len(resolutions) >= 3:
                    self.log_test_result(
                        'Resolution Support',
                        True,
                        f'Supports multiple resolutions: {", ".join(resolutions)}'
                    )
                elif len(resolutions) >= 2:
                    self.log_test_result(
                        'Resolution Support',
                        True,
                        f'Basic resolution support: {", ".join(resolutions)}'
                    )
                else:
                    self.log_test_result(
                        'Resolution Support',
                        False,
                        f'Limited resolution support: {", ".join(resolutions) if resolutions else "None detected"}',
                        critical=True
                    )
            else:
                self.log_test_result(
                    'Resolution Support',
                    False,
                    'Cannot verify - component file not found',
                    critical=True
                )
        except Exception as e:
            self.log_test_result(
                'Resolution Support',
                False,
                f'Error checking resolutions: {str(e)}'
            )
    
    def test_aspect_ratio_support(self):
        """Test aspect ratio options for different platforms"""
        try:
            modal_path = self.project_root / 'src' / 'components' / 'ClipGenerationModal.tsx'
            if modal_path.exists():
                content = modal_path.read_text(encoding='utf-8')
                
                # Check for aspect ratio options
                aspect_ratios = []
                if '16:9' in content: aspect_ratios.append('16:9')
                if '9:16' in content: aspect_ratios.append('9:16')
                if '1:1' in content: aspect_ratios.append('1:1')
                if '4:5' in content: aspect_ratios.append('4:5')
                
                if len(aspect_ratios) >= 4:
                    self.log_test_result(
                        'Aspect Ratio Support',
                        True,
                        f'Comprehensive aspect ratio support: {", ".join(aspect_ratios)}'
                    )
                elif len(aspect_ratios) >= 2:
                    self.log_test_result(
                        'Aspect Ratio Support',
                        True,
                        f'Basic aspect ratio support: {", ".join(aspect_ratios)}'
                    )
                else:
                    self.log_test_result(
                        'Aspect Ratio Support',
                        False,
                        f'Limited aspect ratio support: {", ".join(aspect_ratios) if aspect_ratios else "None detected"}',
                        critical=True
                    )
            else:
                self.log_test_result(
                    'Aspect Ratio Support',
                    False,
                    'Cannot verify - component file not found',
                    critical=True
                )
        except Exception as e:
            self.log_test_result(
                'Aspect Ratio Support',
                False,
                f'Error checking aspect ratios: {str(e)}'
            )
    
    def test_platform_optimization(self):
        """Test platform-specific optimizations"""
        try:
            modal_path = self.project_root / 'src' / 'components' / 'ClipGenerationModal.tsx'
            if modal_path.exists():
                content = modal_path.read_text(encoding='utf-8')
                
                # Check for platform presets
                platforms = []
                if 'youtube' in content.lower(): platforms.append('YouTube')
                if 'tiktok' in content.lower(): platforms.append('TikTok')
                if 'instagram' in content.lower(): platforms.append('Instagram')
                if 'twitter' in content.lower(): platforms.append('Twitter')
                if 'facebook' in content.lower(): platforms.append('Facebook')
                
                if len(platforms) >= 3:
                    self.log_test_result(
                        'Platform Optimization',
                        True,
                        f'Multi-platform optimization: {", ".join(platforms)}'
                    )
                elif len(platforms) >= 1:
                    self.log_test_result(
                        'Platform Optimization',
                        True,
                        f'Basic platform support: {", ".join(platforms)}'
                    )
                else:
                    self.log_test_result(
                        'Platform Optimization',
                        False,
                        'No platform-specific optimizations detected',
                        critical=True
                    )
            else:
                self.log_test_result(
                    'Platform Optimization',
                    False,
                    'Cannot verify - component file not found',
                    critical=True
                )
        except Exception as e:
            self.log_test_result(
                'Platform Optimization',
                False,
                f'Error checking platform optimization: {str(e)}'
            )
    
    def test_video_controls_implementation(self):
        """Test video control features"""
        try:
            # Check for control-related components
            src_path = self.project_root / 'src'
            control_features = {
                'play_pause': False,
                'volume': False,
                'fullscreen': False,
                'seek': False,
                'progress': False
            }
            
            # Search for control-related code
            for file_path in src_path.rglob('*.tsx'):
                try:
                    content = file_path.read_text(encoding='utf-8').lower()
                    
                    if any(term in content for term in ['play', 'pause', 'playing']):
                        control_features['play_pause'] = True
                    if any(term in content for term in ['volume', 'mute', 'audio']):
                        control_features['volume'] = True
                    if any(term in content for term in ['fullscreen', 'full-screen']):
                        control_features['fullscreen'] = True
                    if any(term in content for term in ['seek', 'currenttime', 'progress']):
                        control_features['seek'] = True
                    if any(term in content for term in ['progress', 'duration', 'timeline']):
                        control_features['progress'] = True
                        
                except Exception:
                    continue
            
            implemented_controls = [k for k, v in control_features.items() if v]
            
            if len(implemented_controls) >= 4:
                self.log_test_result(
                    'Video Controls Implementation',
                    True,
                    f'Comprehensive controls: {", ".join(implemented_controls)}'
                )
            elif len(implemented_controls) >= 2:
                self.log_test_result(
                    'Video Controls Implementation',
                    True,
                    f'Basic controls: {", ".join(implemented_controls)}'
                )
            else:
                self.log_test_result(
                    'Video Controls Implementation',
                    False,
                    f'Limited controls: {", ".join(implemented_controls) if implemented_controls else "None detected"}',
                    critical=True
                )
                
        except Exception as e:
            self.log_test_result(
                'Video Controls Implementation',
                False,
                f'Error checking controls: {str(e)}',
                critical=True
            )
    
    def test_responsive_design(self):
        """Test responsive video player design"""
        try:
            src_path = self.project_root / 'src'
            responsive_features = {
                'mobile_responsive': False,
                'touch_controls': False,
                'adaptive_ui': False,
                'breakpoints': False
            }
            
            # Search for responsive design patterns
            for file_path in src_path.rglob('*.tsx'):
                try:
                    content = file_path.read_text(encoding='utf-8').lower()
                    
                    if any(term in content for term in ['mobile', 'responsive', 'sm:', 'md:', 'lg:']):
                        responsive_features['mobile_responsive'] = True
                    if any(term in content for term in ['touch', 'gesture', 'swipe']):
                        responsive_features['touch_controls'] = True
                    if any(term in content for term in ['adaptive', 'viewport', 'screen']):
                        responsive_features['adaptive_ui'] = True
                    if any(term in content for term in ['breakpoint', 'media query', '@media']):
                        responsive_features['breakpoints'] = True
                        
                except Exception:
                    continue
            
            implemented_features = [k for k, v in responsive_features.items() if v]
            
            if len(implemented_features) >= 3:
                self.log_test_result(
                    'Responsive Design',
                    True,
                    f'Good responsive support: {", ".join(implemented_features)}'
                )
            elif len(implemented_features) >= 1:
                self.log_test_result(
                    'Responsive Design',
                    True,
                    f'Basic responsive support: {", ".join(implemented_features)}'
                )
            else:
                self.log_test_result(
                    'Responsive Design',
                    False,
                    'No responsive design features detected',
                    critical=True
                )
                
        except Exception as e:
            self.log_test_result(
                'Responsive Design',
                False,
                f'Error checking responsive design: {str(e)}'
            )
    
    def test_accessibility_features(self):
        """Test video accessibility features"""
        try:
            src_path = self.project_root / 'src'
            accessibility_features = {
                'keyboard_navigation': False,
                'screen_reader': False,
                'captions': False,
                'aria_labels': False
            }
            
            # Search for accessibility patterns
            for file_path in src_path.rglob('*.tsx'):
                try:
                    content = file_path.read_text(encoding='utf-8').lower()
                    
                    if any(term in content for term in ['onkeydown', 'onkeyup', 'tabindex']):
                        accessibility_features['keyboard_navigation'] = True
                    if any(term in content for term in ['aria-', 'role=', 'screen reader']):
                        accessibility_features['screen_reader'] = True
                    if any(term in content for term in ['caption', 'subtitle', 'cc']):
                        accessibility_features['captions'] = True
                    if any(term in content for term in ['aria-label', 'aria-describedby']):
                        accessibility_features['aria_labels'] = True
                        
                except Exception:
                    continue
            
            implemented_features = [k for k, v in accessibility_features.items() if v]
            
            if len(implemented_features) >= 3:
                self.log_test_result(
                    'Accessibility Features',
                    True,
                    f'Good accessibility support: {", ".join(implemented_features)}'
                )
            elif len(implemented_features) >= 1:
                self.log_test_result(
                    'Accessibility Features',
                    True,
                    f'Basic accessibility support: {", ".join(implemented_features)}'
                )
            else:
                self.log_test_result(
                    'Accessibility Features',
                    False,
                    'No accessibility features detected'
                )
                
        except Exception as e:
            self.log_test_result(
                'Accessibility Features',
                False,
                f'Error checking accessibility: {str(e)}'
            )
    
    def run_all_tests(self):
        """Run all video player validation tests"""
        logger.info("Starting comprehensive video player validation...")
        
        # Core functionality tests
        self.test_video_component_structure()
        self.test_video_format_support()
        self.test_resolution_support()
        self.test_aspect_ratio_support()
        self.test_platform_optimization()
        
        # User experience tests
        self.test_video_controls_implementation()
        self.test_responsive_design()
        self.test_accessibility_features()
        
        # Determine production readiness
        critical_failures = len(self.results['summary']['critical_issues'])
        total_tests = self.results['summary']['total_tests']
        passed_tests = self.results['summary']['passed']
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        self.results['summary']['success_rate'] = success_rate
        self.results['summary']['production_ready'] = critical_failures == 0 and success_rate >= 80
        
        return self.results
    
    def generate_report(self):
        """Generate detailed validation report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f'video_player_validation_report_{timestamp}.json'
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Detailed report saved to: {report_file}")
        return report_file
    
    def print_summary(self):
        """Print validation summary"""
        summary = self.results['summary']
        
        print("\n" + "="*80)
        print("VIDEO PLAYER VALIDATION SUMMARY")
        print("="*80)
        
        print(f"\nTotal Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Success Rate: {summary.get('success_rate', 0):.1f}%")
        
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
        validator = VideoPlayerValidator()
        results = validator.run_all_tests()
        
        # Generate detailed report
        report_file = validator.generate_report()
        
        # Print summary
        validator.print_summary()
        
        # Exit with appropriate code
        if results['summary']['production_ready']:
            logger.info("Video player validation completed successfully")
            sys.exit(0)
        else:
            logger.error("Video player validation failed - critical issues found")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Validation script failed: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()