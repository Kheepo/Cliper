import pytest
import numpy as np
import cv2
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from api.video_processor import VideoProcessor


class TestViralMomentDetection:
    """Test enhanced viral moment detection algorithms"""
    
    @pytest.fixture
    def video_processor(self):
        """Create a video processor instance for testing"""
        return VideoProcessor()
    
    @pytest.fixture
    def sample_audio_features(self):
        """Create sample audio features for testing"""
        return {
            'mfcc': np.random.rand(13, 100),
            'spectral_centroid': np.random.rand(1, 100),
            'spectral_rolloff': np.random.rand(1, 100),
            'zero_crossing_rate': np.random.rand(1, 100),
            'tempo': 120.0,
            'chroma': np.random.rand(12, 100)
        }
    
    @pytest.fixture
    def sample_visual_features(self):
        """Create sample visual features for testing"""
        return {
            'scene_changes': [1.5, 3.2, 5.8, 8.1],
            'motion_intensity': np.random.rand(100),
            'face_detections': [
                {'timestamp': 2.0, 'confidence': 0.95, 'bbox': [100, 100, 50, 50]},
                {'timestamp': 4.5, 'confidence': 0.87, 'bbox': [120, 110, 45, 45]}
            ],
            'color_variance': np.random.rand(100),
            'edge_density': np.random.rand(100)
        }
    
    def test_detect_volume_spikes(self, video_processor):
        """Test volume spike detection"""
        # Create sample audio with volume spikes
        sample_rate = 22050
        duration = 10  # seconds
        audio_data = np.random.normal(0, 0.1, sample_rate * duration)
        
        # Add volume spikes at specific times
        spike_times = [2, 5, 8]  # seconds
        for spike_time in spike_times:
            start_idx = spike_time * sample_rate
            end_idx = start_idx + sample_rate // 10  # 0.1 second spike
            audio_data[start_idx:end_idx] *= 5  # 5x volume increase
        
        spikes = video_processor._detect_volume_spikes(audio_data, sample_rate)
        
        assert len(spikes) >= len(spike_times)
        # Check that detected spikes are near our inserted spikes
        for spike_time in spike_times:
            assert any(abs(spike['timestamp'] - spike_time) < 1.0 for spike in spikes)
    
    def test_detect_scene_changes(self, video_processor):
        """Test scene change detection"""
        # Create mock video frames with scene changes
        frames = []
        
        # First scene: mostly blue
        for i in range(30):
            frame = np.zeros((240, 320, 3), dtype=np.uint8)
            frame[:, :, 2] = 200  # Blue channel
            frames.append(frame)
        
        # Scene change: switch to red
        for i in range(30):
            frame = np.zeros((240, 320, 3), dtype=np.uint8)
            frame[:, :, 0] = 200  # Red channel
            frames.append(frame)
        
        # Another scene change: switch to green
        for i in range(30):
            frame = np.zeros((240, 320, 3), dtype=np.uint8)
            frame[:, :, 1] = 200  # Green channel
            frames.append(frame)
        
        scene_changes = video_processor._detect_scene_changes(frames, fps=30)
        
        assert len(scene_changes) >= 2  # Should detect at least 2 scene changes
        # Scene changes should be around 1 second and 2 seconds
        expected_times = [1.0, 2.0]
        for expected_time in expected_times:
            assert any(abs(change - expected_time) < 0.5 for change in scene_changes)
    
    def test_detect_motion_intensity(self, video_processor):
        """Test motion intensity detection"""
        # Create frames with varying motion
        frames = []
        
        # Static frames
        static_frame = np.zeros((240, 320, 3), dtype=np.uint8)
        for i in range(10):
            frames.append(static_frame.copy())
        
        # Moving object frames
        for i in range(10):
            frame = np.zeros((240, 320, 3), dtype=np.uint8)
            # Add a moving white rectangle
            x = i * 10
            cv2.rectangle(frame, (x, 100), (x + 50, 150), (255, 255, 255), -1)
            frames.append(frame)
        
        motion_data = video_processor._analyze_motion_intensity(frames, fps=30)
        
        assert len(motion_data) > 0
        # Motion should be higher in the second half
        first_half_avg = np.mean(motion_data[:len(motion_data)//2])
        second_half_avg = np.mean(motion_data[len(motion_data)//2:])
        assert second_half_avg > first_half_avg
    
    @patch('face_recognition.face_locations')
    def test_detect_faces(self, mock_face_locations, video_processor):
        """Test face detection"""
        # Mock face detection results
        mock_face_locations.side_effect = [
            [(50, 150, 100, 100)],  # One face in first frame
            [],  # No faces in second frame
            [(60, 160, 110, 110), (200, 300, 250, 250)]  # Two faces in third frame
        ]
        
        frames = [np.zeros((240, 320, 3), dtype=np.uint8) for _ in range(3)]
        
        face_data = video_processor._detect_faces_in_frames(frames, fps=30)
        
        assert len(face_data) == 2  # Should detect faces in 2 frames
        assert face_data[0]['timestamp'] == 0.0
        assert face_data[0]['count'] == 1
        assert face_data[1]['timestamp'] == 2/30  # Third frame
        assert face_data[1]['count'] == 2
    
    def test_analyze_audio_sentiment(self, video_processor):
        """Test audio sentiment analysis"""
        # Mock transcription with various sentiments
        transcription = [
            {'text': 'This is amazing and wonderful!', 'start': 0.0, 'end': 2.0},
            {'text': 'I hate this terrible situation.', 'start': 2.0, 'end': 4.0},
            {'text': 'This is okay, nothing special.', 'start': 4.0, 'end': 6.0},
            {'text': 'Absolutely fantastic and incredible!', 'start': 6.0, 'end': 8.0}
        ]
        
        sentiment_data = video_processor._analyze_audio_sentiment(transcription)
        
        assert len(sentiment_data) == 4
        
        # Check sentiment scores
        positive_segments = [s for s in sentiment_data if s['sentiment'] > 0.1]
        negative_segments = [s for s in sentiment_data if s['sentiment'] < -0.1]
        
        assert len(positive_segments) >= 2  # Should detect positive segments
        assert len(negative_segments) >= 1   # Should detect negative segment
    
    def test_detect_laughter_applause(self, video_processor):
        """Test laughter and applause detection"""
        # Create mock audio features that simulate laughter/applause patterns
        sample_rate = 22050
        duration = 10
        
        # Mock audio with high-frequency content (laughter-like)
        audio_data = np.random.normal(0, 0.1, sample_rate * duration)
        
        # Add high-frequency bursts at specific times
        laughter_times = [2, 6]
        for laugh_time in laughter_times:
            start_idx = laugh_time * sample_rate
            end_idx = start_idx + sample_rate // 2  # 0.5 second burst
            # Add high-frequency noise
            high_freq = np.sin(2 * np.pi * 2000 * np.linspace(0, 0.5, end_idx - start_idx))
            audio_data[start_idx:end_idx] += high_freq * 0.5
        
        laughter_data = video_processor._detect_laughter_applause(audio_data, sample_rate)
        
        assert len(laughter_data) > 0
        # Should detect events near our inserted laughter times
        for laugh_time in laughter_times:
            assert any(abs(event['timestamp'] - laugh_time) < 1.0 for event in laughter_data)
    
    def test_calculate_engagement_score(self, video_processor, sample_audio_features, sample_visual_features):
        """Test engagement score calculation"""
        # Mock various features
        volume_spikes = [
            {'timestamp': 2.0, 'intensity': 0.8},
            {'timestamp': 5.0, 'intensity': 0.9}
        ]
        
        sentiment_data = [
            {'timestamp': 1.0, 'sentiment': 0.7, 'confidence': 0.8},
            {'timestamp': 3.0, 'sentiment': -0.3, 'confidence': 0.6},
            {'timestamp': 6.0, 'sentiment': 0.9, 'confidence': 0.9}
        ]
        
        laughter_data = [
            {'timestamp': 2.5, 'confidence': 0.7, 'type': 'laughter'}
        ]
        
        # Calculate engagement score for a specific timestamp
        timestamp = 2.0
        score = video_processor._calculate_engagement_score(
            timestamp,
            sample_audio_features,
            sample_visual_features,
            volume_spikes,
            sentiment_data,
            laughter_data
        )
        
        assert 0 <= score <= 1  # Score should be normalized
        assert isinstance(score, (int, float))
    
    def test_identify_viral_segments(self, video_processor):
        """Test viral segment identification"""
        # Mock engagement scores over time
        duration = 60  # 1 minute video
        timestamps = np.linspace(0, duration, 100)
        
        # Create engagement scores with peaks
        engagement_scores = np.random.normal(0.3, 0.1, 100)
        
        # Add viral peaks
        peak_indices = [20, 50, 80]
        for idx in peak_indices:
            engagement_scores[idx:idx+5] = np.random.uniform(0.8, 0.95, 5)
        
        segments = video_processor._identify_viral_segments(
            timestamps, engagement_scores, min_duration=3.0
        )
        
        assert len(segments) > 0
        
        # Check that segments have required properties
        for segment in segments:
            assert 'start_time' in segment
            assert 'end_time' in segment
            assert 'score' in segment
            assert 'duration' in segment
            assert segment['duration'] >= 3.0  # Minimum duration
            assert 0 <= segment['score'] <= 1
    
    def test_viral_moment_integration(self, video_processor):
        """Test integration of all viral detection components"""
        # Create a mock video file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
            try:
                # Mock the various analysis methods
                with patch.object(video_processor, '_detect_volume_spikes') as mock_volume:
                    with patch.object(video_processor, '_detect_scene_changes') as mock_scenes:
                        with patch.object(video_processor, '_analyze_motion_intensity') as mock_motion:
                            with patch.object(video_processor, '_detect_faces_in_frames') as mock_faces:
                                with patch.object(video_processor, '_analyze_audio_sentiment') as mock_sentiment:
                                    with patch.object(video_processor, '_detect_laughter_applause') as mock_laughter:
                                        
                                        # Setup mock returns
                                        mock_volume.return_value = [{'timestamp': 5.0, 'intensity': 0.8}]
                                        mock_scenes.return_value = [2.0, 8.0]
                                        mock_motion.return_value = np.random.rand(100)
                                        mock_faces.return_value = [{'timestamp': 3.0, 'count': 2}]
                                        mock_sentiment.return_value = [{'timestamp': 4.0, 'sentiment': 0.7}]
                                        mock_laughter.return_value = [{'timestamp': 6.0, 'confidence': 0.8}]
                                        
                                        # Mock video loading and processing
                                        with patch('cv2.VideoCapture') as mock_cap:
                                            mock_cap_instance = Mock()
                                            mock_cap_instance.isOpened.return_value = True
                                            mock_cap_instance.get.side_effect = lambda prop: {
                                                cv2.CAP_PROP_FPS: 30.0,
                                                cv2.CAP_PROP_FRAME_COUNT: 300.0
                                            }.get(prop, 0)
                                            mock_cap_instance.read.return_value = (True, np.zeros((240, 320, 3), dtype=np.uint8))
                                            mock_cap.return_value = mock_cap_instance
                                            
                                            # Test the viral detection
                                            result = video_processor._detect_viral_moments_advanced(temp_video.name)
                                            
                                            assert 'viral_segments' in result
                                            assert 'analysis_data' in result
                                            assert isinstance(result['viral_segments'], list)
                                            
                                            # Verify all detection methods were called
                                            mock_volume.assert_called_once()
                                            mock_scenes.assert_called_once()
                                            mock_motion.assert_called_once()
                                            mock_faces.assert_called_once()
                                            mock_sentiment.assert_called_once()
                                            mock_laughter.assert_called_once()
            
            finally:
                if os.path.exists(temp_video.name):
                    os.unlink(temp_video.name)
    
    def test_viral_score_calculation(self, video_processor):
        """Test viral score calculation with various factors"""
        # Test different combinations of viral indicators
        test_cases = [
            {
                'volume_spike': True,
                'scene_change': True,
                'high_motion': True,
                'faces_present': True,
                'positive_sentiment': True,
                'laughter_detected': True,
                'expected_score_range': (0.7, 1.0)
            },
            {
                'volume_spike': False,
                'scene_change': False,
                'high_motion': False,
                'faces_present': False,
                'positive_sentiment': False,
                'laughter_detected': False,
                'expected_score_range': (0.0, 0.3)
            },
            {
                'volume_spike': True,
                'scene_change': False,
                'high_motion': True,
                'faces_present': True,
                'positive_sentiment': False,
                'laughter_detected': True,
                'expected_score_range': (0.4, 0.7)
            }
        ]
        
        for case in test_cases:
            # Mock the individual detection results based on test case
            timestamp = 5.0
            
            # Create mock data based on test case
            volume_spikes = [{'timestamp': timestamp, 'intensity': 0.8}] if case['volume_spike'] else []
            scene_changes = [timestamp] if case['scene_change'] else []
            motion_data = [0.8] if case['high_motion'] else [0.2]
            face_data = [{'timestamp': timestamp, 'count': 2}] if case['faces_present'] else []
            sentiment_data = [{'timestamp': timestamp, 'sentiment': 0.7}] if case['positive_sentiment'] else [{'timestamp': timestamp, 'sentiment': -0.3}]
            laughter_data = [{'timestamp': timestamp, 'confidence': 0.8}] if case['laughter_detected'] else []
            
            # Calculate score
            score = video_processor._calculate_viral_score(
                timestamp,
                volume_spikes,
                scene_changes,
                motion_data,
                face_data,
                sentiment_data,
                laughter_data
            )
            
            min_score, max_score = case['expected_score_range']
            assert min_score <= score <= max_score, f"Score {score} not in expected range {case['expected_score_range']} for case {case}"


if __name__ == "__main__":
    pytest.main([__file__])