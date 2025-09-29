#!/usr/bin/env python3
"""
Create a small test video with audio for upload testing
"""

import cv2
import numpy as np
import subprocess
import os

def create_test_video_with_audio():
    """Create a small test video with audio track"""
    print("🎬 Creating test video with audio...")
    
    # Video parameters
    width, height = 64, 64
    fps = 30
    duration = 3  # seconds
    total_frames = fps * duration
    
    # Create temporary video without audio
    temp_video = 'temp_video_no_audio.mp4'
    
    # Create video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_video, fourcc, fps, (width, height))
    
    # Generate frames with simple animation
    for frame_num in range(total_frames):
        # Create a frame with changing colors
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Create a moving circle
        center_x = int((frame_num / total_frames) * width)
        center_y = height // 2
        color = (int(255 * frame_num / total_frames), 100, 200)
        
        cv2.circle(frame, (center_x, center_y), 10, color, -1)
        
        # Add some text
        cv2.putText(frame, f'{frame_num}', (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)
        
        out.write(frame)
    
    out.release()
    
    # Add audio using ffmpeg
    output_file = 'test_video_with_audio.mp4'
    
    # Generate a simple sine wave audio (440Hz tone)
    cmd = [
        'ffmpeg', '-y',  # -y to overwrite output file
        '-i', temp_video,  # input video
        '-f', 'lavfi',  # use lavfi (libavfilter) input
        '-i', f'sine=frequency=440:duration={duration}',  # generate sine wave
        '-c:v', 'copy',  # copy video stream
        '-c:a', 'aac',  # encode audio as AAC
        '-shortest',  # finish when shortest input ends
        output_file
    ]
    
    try:
        print("🔊 Adding audio track...")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✅ Created {output_file} with audio")
        
        # Clean up temporary file
        if os.path.exists(temp_video):
            os.remove(temp_video)
            
        # Check file size
        if os.path.exists(output_file):
            size = os.path.getsize(output_file)
            print(f"📁 File size: {size} bytes")
            return output_file
        else:
            print("❌ Failed to create output file")
            return None
            
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg failed: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return None
    except FileNotFoundError:
        print("❌ FFmpeg not found. Please install FFmpeg to create video with audio.")
        print("💡 Falling back to video without audio...")
        
        # Rename the temp file as fallback
        if os.path.exists(temp_video):
            os.rename(temp_video, 'test_video_fallback.mp4')
            return 'test_video_fallback.mp4'
        return None

if __name__ == "__main__":
    result = create_test_video_with_audio()
    if result:
        print(f"🎉 Test video created: {result}")
    else:
        print("❌ Failed to create test video")