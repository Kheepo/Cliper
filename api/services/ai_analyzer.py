import os
import json
import asyncio
import tempfile
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import cv2
import numpy as np
from openai import AsyncOpenAI

@dataclass
class AnalysisSegment:
    """Represents a time segment with analysis data"""
    start_time: float
    end_time: float
    confidence: float
    data: Dict[str, Any]

@dataclass
class AnalysisResult:
    """Complete analysis result for a video"""
    transcription: Dict[str, Any]
    scenes: List[AnalysisSegment]
    emotions: List[AnalysisSegment]
    faces: List[AnalysisSegment]
    viral_score: Dict[str, Any]
    processing_time: float
    metadata: Dict[str, Any]

class AIVideoAnalyzer:
    """AI-powered video analysis service"""
    
    def __init__(self):
        self.temp_dir = "temp_analysis"
        os.makedirs(self.temp_dir, exist_ok=True)
        self.openai_client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        if not os.getenv('OPENAI_API_KEY'):
            print("Warning: OPENAI_API_KEY not found in environment variables")
    
    async def analyze_video(self, video_path: str, job_id: str) -> AnalysisResult:
        """Perform comprehensive AI analysis on video"""
        start_time = datetime.utcnow()
        
        try:
            # Extract audio for speech analysis
            audio_path = await self._extract_audio(video_path, job_id)
            
            # Run all analysis tasks concurrently
            tasks = [
                self._analyze_speech(audio_path),
                self._analyze_scenes(video_path),
                self._analyze_emotions(video_path),
                self._detect_faces(video_path),
                self._get_video_metadata(video_path)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            transcription = results[0] if not isinstance(results[0], Exception) else {}
            scenes = results[1] if not isinstance(results[1], Exception) else []
            emotions = results[2] if not isinstance(results[2], Exception) else []
            faces = results[3] if not isinstance(results[3], Exception) else []
            metadata = results[4] if not isinstance(results[4], Exception) else {}
            
            # Calculate viral potential score
            viral_score = await self._calculate_viral_score(
                transcription, scenes, emotions, faces, metadata
            )
            
            # Clean up temporary files
            self._cleanup_temp_files([audio_path])
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return AnalysisResult(
                transcription=transcription,
                scenes=scenes,
                emotions=emotions,
                faces=faces,
                viral_score=viral_score,
                processing_time=processing_time,
                metadata=metadata
            )
            
        except Exception as e:
            raise Exception(f"Video analysis failed: {str(e)}")
    
    async def _extract_audio(self, video_path: str, job_id: str = None) -> str:
        """Extract audio from video for speech analysis"""
        if job_id:
            audio_path = os.path.join(self.temp_dir, f"{job_id}_audio.wav")
        else:
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            audio_path = os.path.join(self.temp_dir, f"{base_name}_audio.wav")
        
        # Check if FFmpeg is available
        try:
            check_process = await asyncio.create_subprocess_exec(
                'ffmpeg', '-version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await check_process.communicate()
            ffmpeg_available = check_process.returncode == 0
        except FileNotFoundError:
            ffmpeg_available = False
        
        if ffmpeg_available:
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vn',  # No video
                '-acodec', 'pcm_s16le',  # PCM 16-bit
                '-ar', '16000',  # 16kHz sample rate
                '-ac', '1',  # Mono
                '-y',  # Overwrite output
                audio_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"FFmpeg failed: {stderr.decode()}")
            
            # Verify the audio file was created and has content
            if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
                raise Exception("Audio extraction produced empty file")
        else:
            # Create a mock audio file for testing when FFmpeg is not available
            print(f"⚠️  FFmpeg not available, creating mock audio file for testing")
            with open(audio_path, 'wb') as f:
                # Write minimal WAV header for a 1-second silent audio
                f.write(b'RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x08\x00\x00')
                f.write(b'\x00' * 2048)  # Silent audio data
        
        return audio_path
    
    async def _analyze_speech(self, audio_path: str) -> Dict[str, Any]:
        """Perform speech recognition and transcription using OpenAI Whisper"""
        try:
            # Use OpenAI Whisper API for real speech recognition
            with open(audio_path, 'rb') as audio_file:
                transcript = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularities=["word"]
                )
            
            # Process Whisper response
            full_text = transcript.text
            segments = []
            
            if hasattr(transcript, 'segments') and transcript.segments:
                for segment in transcript.segments:
                    segments.append({
                        'start': segment.start,
                        'end': segment.end,
                        'text': segment.text.strip(),
                        'confidence': getattr(segment, 'avg_logprob', 0.0) + 1.0  # Convert logprob to confidence
                    })
            
            # Calculate additional metrics
            words = full_text.split()
            word_count = len(words)
            duration = segments[-1]['end'] if segments else 0
            speaking_rate = word_count / duration if duration > 0 else 0
            
            # Extract keywords (simple approach - most frequent words excluding common words)
            common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those'}
            word_freq = {}
            for word in words:
                clean_word = word.lower().strip('.,!?;:')
                if clean_word not in common_words and len(clean_word) > 2:
                    word_freq[clean_word] = word_freq.get(clean_word, 0) + 1
            
            keywords = sorted(word_freq.keys(), key=lambda x: word_freq[x], reverse=True)[:10]
            
            # Extract word-level timestamps if available
            word_timestamps = []
            if hasattr(transcript, 'words') and transcript.words:
                for word_info in transcript.words:
                    word_timestamps.append({
                        'word': word_info.word,
                        'start': word_info.start,
                        'end': word_info.end
                    })
            
            transcription = {
                'text': full_text,
                'segments': segments,
                'language': transcript.language,
                'confidence': sum(seg['confidence'] for seg in segments) / len(segments) if segments else 0,
                'word_count': word_count,
                'speaking_rate': speaking_rate,
                'keywords': keywords,
                'duration': duration,
                'word_timestamps': word_timestamps
            }
            
            return transcription
            
        except Exception as e:
            # Fallback to mock data if Whisper fails
            return {
                'text': 'Transcription failed - using fallback',
                'segments': [],
                'language': 'en',
                'confidence': 0.0,
                'word_count': 0,
                'speaking_rate': 0.0,
                'keywords': [],
                'error': f'Speech analysis failed: {str(e)}'
            }
    
    async def _analyze_scenes(self, video_path: str) -> List[AnalysisSegment]:
        """Detect scene changes and analyze visual content using OpenCV"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise Exception("Could not open video file")
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            
            scenes = []
            prev_frame = None
            scene_start = 0.0
            frame_idx = 0
            scene_threshold = 0.3  # Threshold for scene change detection
            
            # Sample frames every 0.5 seconds for performance
            sample_interval = max(1, int(fps * 0.5))
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_idx % sample_interval == 0:
                    current_time = frame_idx / fps
                    
                    # Convert to grayscale for scene detection
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    
                    if prev_frame is not None:
                        # Calculate histogram difference for scene change detection
                        hist1 = cv2.calcHist([prev_frame], [0], None, [256], [0, 256])
                        hist2 = cv2.calcHist([gray], [0], None, [256], [0, 256])
                        
                        # Normalize histograms
                        cv2.normalize(hist1, hist1, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
                        cv2.normalize(hist2, hist2, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
                        
                        # Calculate correlation coefficient
                        correlation = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
                        
                        # If correlation is low, we have a scene change
                        if correlation < (1 - scene_threshold):
                            # Analyze the previous scene
                            scene_data = await self._analyze_scene_segment(video_path, scene_start, current_time)
                            scenes.append(AnalysisSegment(
                                start_time=scene_start,
                                end_time=current_time,
                                confidence=1 - correlation,
                                data=scene_data
                            ))
                            scene_start = current_time
                    
                    prev_frame = gray.copy()
                
                frame_idx += 1
            
            # Add the final scene
            if scene_start < duration:
                scene_data = await self._analyze_scene_segment(video_path, scene_start, duration)
                scenes.append(AnalysisSegment(
                    start_time=scene_start,
                    end_time=duration,
                    confidence=0.8,
                    data=scene_data
                ))
            
            cap.release()
            return scenes
            
        except Exception as e:
            # Fallback to mock data if OpenCV fails
            return [
                AnalysisSegment(
                    start_time=0.0,
                    end_time=15.0,
                    confidence=0.5,
                    data={
                        'scene_type': 'unknown',
                        'brightness': 0.5,
                        'contrast': 0.5,
                        'motion_level': 'medium',
                        'dominant_colors': ['#808080'],
                        'objects_detected': [],
                        'error': f'Scene analysis failed: {str(e)}'
                    }
                )
            ]
    
    async def _analyze_scene_segment(self, video_path: str, start_time: float, end_time: float) -> Dict[str, Any]:
        """Analyze a specific scene segment for visual properties"""
        try:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            # Jump to middle of segment for analysis
            mid_time = (start_time + end_time) / 2
            frame_number = int(mid_time * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                raise Exception("Could not read frame")
            
            # Analyze frame properties
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Calculate brightness (mean intensity)
            brightness = np.mean(gray) / 255.0
            
            # Calculate contrast (standard deviation)
            contrast = np.std(gray) / 255.0
            
            # Detect motion level by analyzing frame differences
            motion_level = 'medium'  # Default
            if end_time - start_time > 2:  # Only for longer segments
                # Sample a few frames to detect motion
                cap = cv2.VideoCapture(video_path)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                ret1, frame1 = cap.read()
                cap.set(cv2.CAP_PROP_POS_FRAMES, min(frame_number + int(fps), int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) - 1))
                ret2, frame2 = cap.read()
                cap.release()
                
                if ret1 and ret2:
                    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
                    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
                    diff = cv2.absdiff(gray1, gray2)
                    motion_score = np.mean(diff) / 255.0
                    
                    if motion_score > 0.1:
                        motion_level = 'high'
                    elif motion_score > 0.05:
                        motion_level = 'medium'
                    else:
                        motion_level = 'low'
            
            # Extract dominant colors
            dominant_colors = self._extract_dominant_colors(frame)
            
            # Classify scene type based on properties
            scene_type = self._classify_scene_type(brightness, contrast, motion_level)
            
            return {
                'scene_type': scene_type,
                'brightness': round(brightness, 2),
                'contrast': round(contrast, 2),
                'motion_level': motion_level,
                'dominant_colors': dominant_colors,
                'objects_detected': []  # Could be enhanced with object detection
            }
            
        except Exception as e:
            return {
                'scene_type': 'unknown',
                'brightness': 0.5,
                'contrast': 0.5,
                'motion_level': 'medium',
                'dominant_colors': ['#808080'],
                'objects_detected': [],
                'error': str(e)
            }
    
    def _extract_dominant_colors(self, frame: np.ndarray, k: int = 3) -> List[str]:
        """Extract dominant colors from frame using K-means clustering"""
        try:
            # Reshape frame to be a list of pixels
            data = frame.reshape((-1, 3))
            data = np.float32(data)
            
            # Apply K-means clustering
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
            _, labels, centers = cv2.kmeans(data, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
            
            # Convert centers to hex colors
            colors = []
            for center in centers:
                # Convert BGR to RGB and then to hex
                b, g, r = center.astype(int)
                hex_color = f'#{r:02x}{g:02x}{b:02x}'
                colors.append(hex_color)
            
            return colors
            
        except Exception:
            return ['#808080']  # Default gray
    
    def _classify_scene_type(self, brightness: float, contrast: float, motion_level: str) -> str:
        """Classify scene type based on visual properties"""
        if motion_level == 'low' and brightness > 0.6:
            return 'talking_head'
        elif motion_level == 'high':
            return 'action'
        elif brightness < 0.3:
            return 'dark_scene'
        elif contrast > 0.6:
            return 'high_contrast'
        else:
            return 'general'

    def _analyze_frame_emotion(self, frame: np.ndarray, faces: np.ndarray, gray: np.ndarray) -> Dict[str, Any]:
        """Analyze emotion from a single frame based on facial features and scene properties"""
        try:
            num_faces = len(faces)
            
            # Basic emotion inference based on visual cues
            brightness = np.mean(gray) / 255.0
            contrast = np.std(gray) / 255.0
            
            # Simple heuristic-based emotion detection
            if num_faces == 0:
                emotion = 'neutral'
                confidence = 0.3
                energy_level = 'low'
            elif num_faces == 1:
                # Single face - analyze facial region
                x, y, w, h = faces[0]
                face_roi = gray[y:y+h, x:x+w]
                
                # Analyze facial features (simplified)
                face_brightness = np.mean(face_roi) / 255.0
                face_contrast = np.std(face_roi) / 255.0
                
                # Heuristic emotion classification
                if face_contrast > 0.6 and brightness > 0.5:
                    emotion = 'happy'
                    confidence = 0.7
                    energy_level = 'high'
                elif face_contrast < 0.3:
                    emotion = 'sad'
                    confidence = 0.6
                    energy_level = 'low'
                elif brightness < 0.3:
                    emotion = 'serious'
                    confidence = 0.5
                    energy_level = 'medium'
                else:
                    emotion = 'neutral'
                    confidence = 0.5
                    energy_level = 'medium'
            else:
                # Multiple faces - group setting
                emotion = 'social'
                confidence = 0.6
                energy_level = 'high'
            
            # Generate emotion scores
            emotion_scores = {
                'happy': 0.1,
                'sad': 0.1,
                'angry': 0.05,
                'surprised': 0.1,
                'neutral': 0.4,
                'serious': 0.15,
                'social': 0.1
            }
            
            # Boost the detected emotion
            if emotion in emotion_scores:
                emotion_scores[emotion] = confidence
                # Normalize other scores
                remaining_score = 1.0 - confidence
                other_emotions = [k for k in emotion_scores.keys() if k != emotion]
                for other in other_emotions:
                    emotion_scores[other] = remaining_score / len(other_emotions)
            
            # Determine sentiment
            if emotion in ['happy', 'social']:
                sentiment = 'positive'
            elif emotion in ['sad', 'angry']:
                sentiment = 'negative'
            else:
                sentiment = 'neutral'
            
            return {
                'primary_emotion': emotion,
                'emotion_scores': emotion_scores,
                'sentiment': sentiment,
                'energy_level': energy_level,
                'faces_detected': num_faces,
                'confidence': confidence,
                'facial_features': {
                    'brightness': round(brightness, 2),
                    'contrast': round(contrast, 2)
                }
            }
            
        except Exception as e:
            return {
                'primary_emotion': 'neutral',
                'emotion_scores': {'neutral': 1.0},
                'sentiment': 'neutral',
                'energy_level': 'medium',
                'faces_detected': 0,
                'confidence': 0.3,
                'error': str(e)
            }

    async def _analyze_emotions(self, video_path: str) -> List[AnalysisSegment]:
        """Analyze emotional content and sentiment using OpenCV face detection"""
        try:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            
            # Load face cascade classifier
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            
            emotions = []
            segment_duration = 5.0  # Analyze in 5-second segments
            
            for start_time in np.arange(0, duration, segment_duration):
                end_time = min(start_time + segment_duration, duration)
                
                # Sample frames from this segment
                mid_time = (start_time + end_time) / 2
                frame_number = int(mid_time * fps)
                
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                ret, frame = cap.read()
                
                if not ret:
                    continue
                
                # Convert to grayscale for face detection
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Detect faces
                faces = face_cascade.detectMultiScale(gray, 1.1, 4)
                
                # Analyze emotion based on facial features and scene properties
                emotion_data = self._analyze_frame_emotion(frame, faces, gray)
                
                emotions.append(AnalysisSegment(
                    start_time=start_time,
                    end_time=end_time,
                    confidence=emotion_data['confidence'],
                    data=emotion_data
                ))
            
            cap.release()
            return emotions
            
        except Exception as e:
            # Fallback to mock data on error
            return [
                AnalysisSegment(
                    start_time=0.0,
                    end_time=10.0,
                    confidence=0.5,
                    data={
                        'primary_emotion': 'neutral',
                        'emotion_scores': {
                            'neutral': 0.5,
                            'happy': 0.2,
                            'sad': 0.1,
                            'angry': 0.1,
                            'surprised': 0.1
                        },
                        'sentiment': 'neutral',
                        'energy_level': 'medium',
                        'faces_detected': 0,
                        'error': str(e)
                    }
                )
            ]
    
    async def _detect_faces(self, video_path: str) -> List[AnalysisSegment]:
        """Detect and track faces in video using OpenCV"""
        try:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            
            # Load face cascade classifier
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            
            faces = []
            segment_duration = 3.0  # Analyze in 3-second segments
            
            for start_time in np.arange(0, duration, segment_duration):
                end_time = min(start_time + segment_duration, duration)
                
                # Sample multiple frames from this segment for better detection
                frame_samples = 3
                all_faces = []
                confidences = []
                
                for i in range(frame_samples):
                    sample_time = start_time + (i * segment_duration / frame_samples)
                    frame_number = int(sample_time * fps)
                    
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                    ret, frame = cap.read()
                    
                    if not ret:
                        continue
                    
                    # Convert to grayscale for face detection
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    
                    # Detect faces with different scale factors for better accuracy
                    detected_faces = face_cascade.detectMultiScale(
                        gray, 
                        scaleFactor=1.1, 
                        minNeighbors=5, 
                        minSize=(30, 30)
                    )
                    
                    if len(detected_faces) > 0:
                        all_faces.append(detected_faces)
                        # Calculate confidence based on detection consistency
                        confidence = min(0.9, 0.5 + (len(detected_faces) * 0.1))
                        confidences.append(confidence)
                
                # Process detected faces for this segment
                if all_faces:
                    # Use the detection with most faces (most representative)
                    best_detection_idx = max(range(len(all_faces)), key=lambda i: len(all_faces[i]))
                    best_faces = all_faces[best_detection_idx]
                    avg_confidence = sum(confidences) / len(confidences)
                    
                    # Convert face data to our format
                    face_positions = []
                    for (x, y, w, h) in best_faces:
                        face_positions.append({
                            'x': int(x),
                            'y': int(y),
                            'width': int(w),
                            'height': int(h)
                        })
                    
                    # Determine face quality based on size and detection confidence
                    avg_face_size = np.mean([pos['width'] * pos['height'] for pos in face_positions])
                    if avg_face_size > 5000 and avg_confidence > 0.8:
                        face_quality = 'high'
                    elif avg_face_size > 2000 and avg_confidence > 0.6:
                        face_quality = 'medium'
                    else:
                        face_quality = 'low'
                    
                    faces.append(AnalysisSegment(
                        start_time=start_time,
                        end_time=end_time,
                        confidence=avg_confidence,
                        data={
                            'face_count': len(best_faces),
                            'face_positions': face_positions,
                            'face_quality': face_quality,
                            'tracking_id': f'face_segment_{len(faces):03d}',
                            'avg_face_size': int(avg_face_size),
                            'detection_method': 'opencv_haar'
                        }
                    ))
                else:
                    # No faces detected in this segment
                    faces.append(AnalysisSegment(
                        start_time=start_time,
                        end_time=end_time,
                        confidence=0.1,
                        data={
                            'face_count': 0,
                            'face_positions': [],
                            'face_quality': 'none',
                            'tracking_id': f'no_face_segment_{len(faces):03d}',
                            'detection_method': 'opencv_haar'
                        }
                    ))
            
            cap.release()
            return faces
            
        except Exception as e:
            # Fallback to mock data on error
            return [
                AnalysisSegment(
                    start_time=0.0,
                    end_time=10.0,
                    confidence=0.3,
                    data={
                        'face_count': 0,
                        'face_positions': [],
                        'face_quality': 'unknown',
                        'tracking_id': 'error_fallback',
                        'error': str(e)
                    }
                )
            ]
    
    async def _get_video_metadata(self, video_path: str) -> Dict[str, Any]:
        """Extract technical video metadata"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                probe_data = json.loads(stdout.decode())
                
                # Extract relevant metadata
                format_info = probe_data.get('format', {})
                video_streams = [s for s in probe_data.get('streams', []) if s.get('codec_type') == 'video']
                
                if video_streams:
                    video_stream = video_streams[0]
                    return {
                        'duration': float(format_info.get('duration', 0)),
                        'bitrate': int(format_info.get('bit_rate', 0)),
                        'size': int(format_info.get('size', 0)),
                        'width': video_stream.get('width', 0),
                        'height': video_stream.get('height', 0),
                        'fps': eval(video_stream.get('r_frame_rate', '0/1')),
                        'codec': video_stream.get('codec_name', ''),
                        'aspect_ratio': f"{video_stream.get('width', 0)}:{video_stream.get('height', 0)}"
                    }
            
            return {}
            
        except Exception as e:
            return {'metadata_error': str(e)}
    
    async def _calculate_viral_score(self, transcription: Dict, scenes: List, 
                                   emotions: List, faces: List, metadata: Dict) -> Dict[str, Any]:
        """Calculate viral potential score based on comprehensive analysis"""
        try:
            # Enhanced scoring factors
            scores = {
                'engagement': 0,
                'emotion': 0,
                'visual_appeal': 0,
                'content_quality': 0,
                'technical_quality': 0,
                'engagement_hooks': 0  # New factor for viral potential
            }
            
            # Enhanced engagement scoring (based on faces and eye contact)
            if faces:
                face_score = 0
                total_duration = 0
                
                for f in faces:
                    duration = f.end_time - f.start_time
                    face_count = f.data.get('face_count', 0)
                    face_quality = f.data.get('face_quality', 'low')
                    avg_face_size = f.data.get('avg_face_size', 0)
                    
                    # Optimal face count scoring
                    if face_count == 1:
                        count_score = 100  # Single person content often performs well
                    elif face_count == 2:
                        count_score = 90   # Duo content
                    elif 3 <= face_count <= 4:
                        count_score = 70   # Group content
                    else:
                        count_score = 30   # No faces or crowd
                    
                    # Quality multiplier
                    quality_multiplier = {'high': 1.0, 'medium': 0.8, 'low': 0.5, 'none': 0.2}.get(face_quality, 0.2)
                    
                    # Face size bonus (larger faces = more engaging)
                    size_bonus = min(1.2, 1.0 + (avg_face_size / 10000) * 0.2) if avg_face_size > 0 else 1.0
                    
                    segment_score = count_score * quality_multiplier * size_bonus
                    face_score += segment_score * duration
                    total_duration += duration
                
                scores['engagement'] = min(face_score / total_duration if total_duration > 0 else 30, 100)
            else:
                scores['engagement'] = 20
            
            # Enhanced emotion scoring (positive emotions boost score)
            if emotions:
                positive_emotions = ['happy', 'excited', 'surprised', 'social']
                high_energy_emotions = ['excited', 'surprised', 'happy']
                emotion_score = 0
                total_duration = 0
                
                for emotion_segment in emotions:
                    duration = emotion_segment.end_time - emotion_segment.start_time
                    primary = emotion_segment.data.get('primary_emotion', 'neutral')
                    energy_level = emotion_segment.data.get('energy_level', 'medium')
                    
                    # Base emotion score
                    if primary in positive_emotions:
                        base_score = 80
                    elif primary == 'neutral':
                        base_score = 40
                    else:
                        base_score = 20
                    
                    # Energy level multiplier
                    energy_multiplier = {'high': 1.3, 'medium': 1.0, 'low': 0.7}.get(energy_level, 1.0)
                    
                    # High energy emotions get bonus
                    if primary in high_energy_emotions and energy_level == 'high':
                        base_score *= 1.2
                    
                    emotion_score += base_score * energy_multiplier * duration
                    total_duration += duration
                
                scores['emotion'] = min(emotion_score / total_duration if total_duration > 0 else 40, 100)
            else:
                scores['emotion'] = 40
            
            # Enhanced visual appeal (based on scene analysis)
            if scenes:
                visual_score = 0
                total_segments = len(scenes)
                
                for scene in scenes:
                    scene_data = scene.data
                    brightness = scene_data.get('brightness', 0.5)
                    contrast = scene_data.get('contrast', 0.5)
                    motion_level = scene_data.get('motion_level', 'medium')
                    scene_type = scene_data.get('scene_type', 'general')
                    
                    # Optimal brightness range (peak at 0.6)
                    brightness_score = max(20, 100 - abs(brightness - 0.6) * 200)
                    
                    # High contrast is generally good
                    contrast_score = min(100, contrast * 150)
                    
                    # Motion level scoring
                    motion_score = {'high': 90, 'medium': 70, 'low': 50}.get(motion_level, 50)
                    
                    # Scene type bonus
                    scene_bonus = {'action': 1.2, 'talking_head': 1.0, 'high_contrast': 1.1}.get(scene_type, 1.0)
                    
                    segment_score = (brightness_score + contrast_score + motion_score) / 3 * scene_bonus
                    visual_score += min(100, segment_score)
                
                scores['visual_appeal'] = visual_score / total_segments
            else:
                scores['visual_appeal'] = 50
            
            # Enhanced content quality (based on transcription)
            if transcription and 'word_count' in transcription:
                word_count = transcription['word_count']
                speaking_rate = transcription.get('speaking_rate', 1.0)
                keywords = transcription.get('keywords', [])
                
                # Optimal word count and speaking rate
                word_score = min(word_count * 1.5, 100)  # More words = better content
                rate_score = 100 if 1.2 <= speaking_rate <= 2.2 else 70 if 0.8 <= speaking_rate <= 2.8 else 40
                
                # Keyword engagement bonus
                engaging_words = ['amazing', 'incredible', 'wow', 'awesome', 'unbelievable', 'shocking']
                keyword_bonus = min(20, len([w for w in keywords if w.lower() in engaging_words]) * 5)
                
                scores['content_quality'] = min((word_score + rate_score) / 2 + keyword_bonus, 100)
            else:
                scores['content_quality'] = 30
            
            # Technical quality (based on metadata)
            if metadata:
                duration = metadata.get('duration', 0)
                width = metadata.get('width', 0)
                height = metadata.get('height', 0)
                fps = metadata.get('fps', 0)
                
                # Optimal duration (15-60 seconds for viral content)
                if 15 <= duration <= 60:
                    duration_score = 100
                elif 10 <= duration <= 90:
                    duration_score = 80
                elif duration <= 120:
                    duration_score = 60
                else:
                    duration_score = 40
                
                # Resolution score
                if width >= 1920 and height >= 1080:
                    resolution_score = 100
                elif width >= 1280 and height >= 720:
                    resolution_score = 80
                elif width >= 854 and height >= 480:
                    resolution_score = 60
                else:
                    resolution_score = 40
                
                # Frame rate score
                if fps >= 30:
                    fps_score = 100
                elif fps >= 24:
                    fps_score = 80
                elif fps >= 15:
                    fps_score = 60
                else:
                    fps_score = 40
                
                scores['technical_quality'] = (duration_score + resolution_score + fps_score) / 3
            else:
                scores['technical_quality'] = 50
            
            # New engagement hooks score
            hook_score = 0
            
            # Check for strong opening (first 3 seconds)
            if emotions:
                opening_emotions = [seg for seg in emotions if seg.start_time < 3]
                if opening_emotions:
                    opening_emotion = opening_emotions[0].data.get('primary_emotion', 'neutral')
                    if opening_emotion in ['excited', 'surprised', 'happy']:
                        hook_score += 30
            
            # Check for face in opening
            if faces:
                opening_faces = [seg for seg in faces if seg.start_time < 3]
                if opening_faces and opening_faces[0].data.get('face_count', 0) > 0:
                    hook_score += 20
            
            # Check for engaging speech patterns
            if transcription and 'keywords' in transcription:
                keywords = transcription['keywords']
                question_words = ['what', 'how', 'why', 'when', 'where', 'who']
                if any(word in ' '.join(keywords).lower() for word in question_words):
                    hook_score += 15
            
            # Check for dynamic content (scene changes)
            if scenes and len(scenes) >= 3:
                hook_score += 20
            
            # Pacing variety bonus
            if scenes and len(scenes) > 1:
                durations = [seg.end_time - seg.start_time for seg in scenes]
                if len(set([round(d) for d in durations])) > 1:  # Varied pacing
                    hook_score += 15
            
            scores['engagement_hooks'] = min(hook_score, 100)
            
            # Calculate overall viral score (weighted average)
            weights = {
                'engagement': 0.22,
                'emotion': 0.20,
                'visual_appeal': 0.18,
                'content_quality': 0.16,
                'technical_quality': 0.12,
                'engagement_hooks': 0.12
            }
            
            overall_score = sum(scores[key] * weights[key] for key in scores)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(scores, metadata)
            
            return {
                'overall_score': round(overall_score, 1),
                'category_scores': scores,
                'grade': self._get_viral_grade(overall_score),
                'recommendations': recommendations,
                'optimal_platforms': self._suggest_platforms(scores, metadata),
                'hashtag_suggestions': self._suggest_hashtags(transcription, emotions),
                'best_posting_times': self._suggest_posting_times(scores)
            }
            
        except Exception as e:
            return {
                'overall_score': 0,
                'error': f'Viral score calculation failed: {str(e)}'
            }
    
    def _generate_recommendations(self, scores: Dict, metadata: Dict) -> List[str]:
        """Generate improvement recommendations"""
        recommendations = []
        
        if scores['engagement'] < 70:
            recommendations.append("Increase eye contact and facial expressions for better engagement")
        
        if scores['emotion'] < 60:
            recommendations.append("Add more positive emotions and energy to boost appeal")
        
        if scores['visual_appeal'] < 70:
            recommendations.append("Improve lighting and add more dynamic visual elements")
        
        if scores['content_quality'] < 60:
            recommendations.append("Enhance content with more compelling narrative and keywords")
        
        if scores['technical_quality'] < 70:
            recommendations.append("Improve video quality: higher resolution, better frame rate")
        
        duration = metadata.get('duration', 0)
        if duration > 60:
            recommendations.append("Consider shortening video to 15-60 seconds for better viral potential")
        
        return recommendations
    
    def _get_viral_grade(self, score: float) -> str:
        """Convert score to letter grade"""
        if score >= 90: return 'A+'
        elif score >= 85: return 'A'
        elif score >= 80: return 'A-'
        elif score >= 75: return 'B+'
        elif score >= 70: return 'B'
        elif score >= 65: return 'B-'
        elif score >= 60: return 'C+'
        elif score >= 55: return 'C'
        elif score >= 50: return 'C-'
        else: return 'D'
    
    def _suggest_platforms(self, scores: Dict, metadata: Dict) -> List[str]:
        """Suggest optimal social media platforms"""
        platforms = []
        duration = metadata.get('duration', 0)
        
        if duration <= 30 and scores['emotion'] > 70:
            platforms.append('TikTok')
        
        if duration <= 60 and scores['visual_appeal'] > 70:
            platforms.append('Instagram Reels')
        
        if scores['engagement'] > 70:
            platforms.append('YouTube Shorts')
        
        if scores['content_quality'] > 70:
            platforms.append('Twitter')
        
        return platforms or ['YouTube', 'Instagram']
    
    def _suggest_hashtags(self, transcription: Dict, emotions: List) -> List[str]:
        """Suggest relevant hashtags"""
        hashtags = ['#viral', '#trending']
        
        if transcription and 'keywords' in transcription:
            for keyword in transcription['keywords'][:3]:
                hashtags.append(f'#{keyword.lower()}')
        
        if emotions:
            primary_emotions = [e.data.get('primary_emotion') for e in emotions]
            if 'happy' in primary_emotions:
                hashtags.extend(['#happy', '#positive'])
            if 'excited' in primary_emotions:
                hashtags.extend(['#excited', '#energy'])
        
        return hashtags[:10]  # Limit to 10 hashtags
    
    def _suggest_posting_times(self, scores: Dict) -> List[str]:
        """Suggest optimal posting times"""
        # Mock optimal times based on content type
        if scores['engagement'] > 80:
            return ['7-9 AM', '12-1 PM', '7-9 PM']
        elif scores['emotion'] > 70:
            return ['6-8 AM', '5-7 PM', '8-10 PM']
        else:
            return ['9-11 AM', '2-4 PM', '6-8 PM']
    
    def _cleanup_temp_files(self, file_paths: List[str]):
        """Clean up temporary files"""
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass  # Ignore cleanup errors

# Global analyzer instance
ai_analyzer = AIVideoAnalyzer()