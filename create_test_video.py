import cv2
import numpy as np
import os

def create_small_test_video():
    """Create a very small test video file for upload testing"""
    filename = "small_test_video.mp4"
    
    # Create a video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filename, fourcc, 1.0, (64, 64))  # Very small resolution, 1 FPS
    
    # Create 3 frames (3 seconds at 1 FPS)
    for i in range(3):
        # Create a simple colored frame
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        frame[:, :] = [i * 80, 100, 200 - i * 60]  # Different colors for each frame
        
        # Add some text
        cv2.putText(frame, str(i), (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        out.write(frame)
    
    out.release()
    
    # Check file size
    if os.path.exists(filename):
        size = os.path.getsize(filename)
        print(f"✅ Created {filename} ({size} bytes)")
        return filename
    else:
        print("❌ Failed to create test video")
        return None

if __name__ == "__main__":
    create_small_test_video()