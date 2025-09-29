# FFmpeg Installation Requirements for Production Deployment

## Overview

FFmpeg is a critical dependency for the Cliper AI video processing pipeline. It's required for video format conversion, audio extraction, and various video manipulation tasks performed by the AI analyzer.

## Installation Requirements

### System Requirements
- **Operating System**: Linux (Ubuntu 20.04+ recommended), Windows Server 2019+, or macOS 10.15+
- **Memory**: Minimum 2GB RAM, 8GB+ recommended for large video files
- **Storage**: At least 1GB free space for FFmpeg binaries and temporary processing files
- **CPU**: Multi-core processor recommended for faster video processing

### FFmpeg Version
- **Minimum Version**: FFmpeg 4.2+
- **Recommended Version**: FFmpeg 5.0+ for optimal performance and latest codec support
- **Required Components**: 
  - libx264 (H.264 encoding)
  - libx265 (H.265 encoding)
  - libmp3lame (MP3 audio encoding)
  - libvorbis (Vorbis audio encoding)
  - libvpx (VP8/VP9 encoding)

## Installation Instructions

### Ubuntu/Debian Linux

```bash
# Update package list
sudo apt update

# Install FFmpeg with essential codecs
sudo apt install ffmpeg

# Verify installation
ffmpeg -version

# Install additional codecs if needed
sudo apt install libx264-dev libx265-dev libmp3lame-dev libvorbis-dev
```

### CentOS/RHEL/Rocky Linux

```bash
# Enable EPEL repository
sudo dnf install epel-release

# Enable RPM Fusion repositories for additional codecs
sudo dnf install --nogpgcheck https://download1.rpmfusion.org/free/el/rpmfusion-free-release-$(rpm -E %rhel).noarch.rpm
sudo dnf install --nogpgcheck https://download1.rpmfusion.org/nonfree/el/rpmfusion-nonfree-release-$(rpm -E %rhel).noarch.rpm

# Install FFmpeg
sudo dnf install ffmpeg ffmpeg-devel

# Verify installation
ffmpeg -version
```

### Windows Server

1. **Download FFmpeg**:
   - Visit https://ffmpeg.org/download.html
   - Download the Windows build (static or shared)
   - Extract to `C:\ffmpeg`

2. **Add to PATH**:
   ```cmd
   setx PATH "%PATH%;C:\ffmpeg\bin" /M
   ```

3. **Verify Installation**:
   ```cmd
   ffmpeg -version
   ```

### macOS

```bash
# Using Homebrew (recommended)
brew install ffmpeg

# Verify installation
ffmpeg -version

# Alternative: Using MacPorts
sudo port install ffmpeg +universal
```

### Docker Installation

For containerized deployments:

```dockerfile
# Add to your Dockerfile
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Verify FFmpeg is available
RUN ffmpeg -version
```

## Configuration for Cliper

### Environment Variables

Set the following environment variables in your production environment:

```bash
# Path to FFmpeg binary (if not in system PATH)
FFMPEG_PATH=/usr/bin/ffmpeg

# FFprobe path (usually installed with FFmpeg)
FFPROBE_PATH=/usr/bin/ffprobe

# Temporary directory for video processing
TEMP_VIDEO_DIR=/tmp/cliper_processing

# Maximum video file size (in MB)
MAX_VIDEO_SIZE=500

# Video processing timeout (in seconds)
VIDEO_PROCESSING_TIMEOUT=300
```

### Performance Optimization

1. **Hardware Acceleration** (if available):
   ```bash
   # Check for hardware acceleration support
   ffmpeg -hwaccels
   
   # Example with NVIDIA GPU acceleration
   ffmpeg -hwaccel cuda -i input.mp4 output.mp4
   ```

2. **CPU Optimization**:
   ```bash
   # Use multiple threads for encoding
   ffmpeg -threads 4 -i input.mp4 output.mp4
   ```

3. **Memory Management**:
   ```bash
   # Limit memory usage for large files
   ffmpeg -analyzeduration 100M -probesize 100M -i input.mp4 output.mp4
   ```

## Verification Script

Create a verification script to ensure FFmpeg is properly installed:

```python
#!/usr/bin/env python3
import subprocess
import sys

def verify_ffmpeg():
    try:
        # Check FFmpeg version
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✓ FFmpeg is installed and accessible")
            print(f"Version: {result.stdout.split()[2]}")
        else:
            print("✗ FFmpeg command failed")
            return False
            
        # Check FFprobe
        result = subprocess.run(['ffprobe', '-version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✓ FFprobe is installed and accessible")
        else:
            print("✗ FFprobe command failed")
            return False
            
        # Test basic functionality
        test_cmd = ['ffmpeg', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=320x240:rate=1', 
                   '-f', 'null', '-']
        result = subprocess.run(test_cmd, capture_output=True, timeout=30)
        if result.returncode == 0:
            print("✓ FFmpeg basic functionality test passed")
        else:
            print("✗ FFmpeg basic functionality test failed")
            return False
            
        return True
        
    except subprocess.TimeoutExpired:
        print("✗ FFmpeg command timed out")
        return False
    except FileNotFoundError:
        print("✗ FFmpeg not found in PATH")
        return False
    except Exception as e:
        print(f"✗ Error testing FFmpeg: {e}")
        return False

if __name__ == "__main__":
    if verify_ffmpeg():
        print("\n🎉 FFmpeg is properly configured for Cliper!")
        sys.exit(0)
    else:
        print("\n❌ FFmpeg configuration issues detected. Please check installation.")
        sys.exit(1)
```

## Troubleshooting

### Common Issues

1. **FFmpeg not found in PATH**:
   - Ensure FFmpeg is installed and added to system PATH
   - Use absolute path in environment variables

2. **Missing codecs**:
   - Install additional codec packages
   - Use static builds that include all codecs

3. **Permission issues**:
   - Ensure the application user has execute permissions for FFmpeg
   - Check temporary directory write permissions

4. **Performance issues**:
   - Enable hardware acceleration if available
   - Adjust thread count based on CPU cores
   - Monitor memory usage during processing

### Monitoring

Implement monitoring for FFmpeg processes:

```python
# Monitor FFmpeg process health
import psutil

def monitor_ffmpeg_processes():
    ffmpeg_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
        if 'ffmpeg' in proc.info['name'].lower():
            ffmpeg_processes.append(proc.info)
    return ffmpeg_processes
```

## Security Considerations

1. **Input Validation**: Always validate video file inputs before processing
2. **Resource Limits**: Set appropriate timeouts and memory limits
3. **Sandboxing**: Consider running FFmpeg in a sandboxed environment
4. **File Permissions**: Restrict access to temporary processing directories

## Production Deployment Checklist

- [ ] FFmpeg installed with required version (4.2+)
- [ ] All necessary codecs available
- [ ] Environment variables configured
- [ ] Verification script passes
- [ ] Performance optimization applied
- [ ] Monitoring implemented
- [ ] Security measures in place
- [ ] Backup plan for FFmpeg failures
- [ ] Documentation updated for operations team

## Support and Maintenance

- **Updates**: Regularly update FFmpeg for security patches and performance improvements
- **Monitoring**: Monitor FFmpeg process performance and resource usage
- **Logs**: Enable detailed logging for troubleshooting
- **Backup**: Maintain fallback options for critical video processing tasks

For additional support, refer to the official FFmpeg documentation at https://ffmpeg.org/documentation.html