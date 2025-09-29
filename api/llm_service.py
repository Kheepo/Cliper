import os
import google.generativeai as genai
from typing import List, Dict, Any, Optional
import json
import logging
from .models import ViralityScore, Hashtag, PostingRecommendation
from dataclasses import dataclass
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ViralMoment:
    """Represents a specific viral moment in the video"""
    start_time: float  # seconds
    end_time: float    # seconds
    viral_score: float # 0.0 to 1.0
    moment_type: str   # e.g., "emotional_peak", "humor", "surprise", "educational"
    description: str   # detailed explanation
    key_features: List[str]  # list of features that make it viral
    confidence: float  # AI confidence in this assessment
    
@dataclass
class DetailedViralAnalysis:
    """Comprehensive viral analysis with timestamps"""
    overall_viral_score: float
    viral_moments: List[ViralMoment]
    content_summary: str
    strengths: List[str]
    improvement_suggestions: List[str]
    target_audience: str
    emotional_journey: Dict[str, Any]  # emotion progression throughout video
    engagement_predictions: Dict[str, float]  # platform-specific predictions

class LLMService:
    """Service for AI-powered virality analysis and content generation"""
    
    def __init__(self):
        # Configure Gemini API
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
    
    async def analyze_viral_moments_detailed(self, transcript: str, video_analysis: Dict[str, Any]) -> DetailedViralAnalysis:
        """Perform detailed viral analysis with specific timestamps and reasoning"""
        try:
            # Extract analysis data
            duration = video_analysis.get('duration', 0)
            viral_segments = video_analysis.get('viral_segments', [])
            audio_features = video_analysis.get('audio_features', {})
            visual_features = video_analysis.get('visual_features', {})
            sentiment_analysis = video_analysis.get('sentiment_analysis', {})
            
            prompt = f"""
            Perform a comprehensive viral moment analysis for this video content.
            
            Video Duration: {duration} seconds
            
            Transcript:
            {transcript}
            
            Technical Analysis Data:
            - Viral Segments Found: {len(viral_segments)}
            - Audio Features: Volume spikes at {audio_features.get('volume_spikes', [])}, Laughter detected: {audio_features.get('laughter_detected', False)}
            - Visual Features: Scene changes at {visual_features.get('scene_changes', [])}, Faces detected: {visual_features.get('faces_detected', 0)}
            - Sentiment Analysis: Overall sentiment {sentiment_analysis.get('overall_sentiment', 'neutral')}, Emotional peaks at {sentiment_analysis.get('emotional_peaks', [])}
            
            Candidate Viral Segments:
            {json.dumps(viral_segments, indent=2)}
            
            Please provide a detailed analysis including:
            1. Overall viral score (0.0 to 1.0)
            2. Specific viral moments with exact timestamps
            3. Content summary and emotional journey
            4. Strengths and improvement suggestions
            5. Target audience identification
            6. Platform-specific engagement predictions
            
            For each viral moment, analyze:
            - Why it's engaging (humor, surprise, emotion, education, etc.)
            - Technical features that support virality (audio/visual cues)
            - Confidence level in the assessment
            - Specific improvement suggestions
            
            Return your response as JSON with this exact structure:
            {{
                "overall_viral_score": 0.85,
                "content_summary": "Brief summary of the video content and main themes",
                "target_audience": "Primary demographic and interests",
                "strengths": ["List of content strengths"],
                "improvement_suggestions": ["Specific actionable improvements"],
                "emotional_journey": {{
                    "opening": "emotion at start",
                    "middle": "emotion in middle",
                    "climax": "peak emotional moment",
                    "ending": "emotion at end"
                }},
                "engagement_predictions": {{
                    "tiktok": 0.8,
                    "instagram": 0.7,
                    "youtube": 0.6,
                    "twitter": 0.5
                }},
                "viral_moments": [
                    {{
                        "start_time": 15.5,
                        "end_time": 22.3,
                        "viral_score": 0.9,
                        "moment_type": "humor",
                        "description": "Detailed explanation of why this moment is viral",
                        "key_features": ["specific features that make it engaging"],
                        "confidence": 0.85
                    }}
                ]
            }}
            
            Only return the JSON, no additional text.
            """
            
            response = self.model.generate_content(prompt)
            
            try:
                analysis_data = json.loads(response.text)
                
                # Parse viral moments
                viral_moments = []
                for moment_data in analysis_data.get('viral_moments', []):
                    moment = ViralMoment(
                        start_time=float(moment_data['start_time']),
                        end_time=float(moment_data['end_time']),
                        viral_score=float(moment_data['viral_score']),
                        moment_type=moment_data['moment_type'],
                        description=moment_data['description'],
                        key_features=moment_data['key_features'],
                        confidence=float(moment_data['confidence'])
                    )
                    viral_moments.append(moment)
                
                # Create detailed analysis object
                detailed_analysis = DetailedViralAnalysis(
                    overall_viral_score=float(analysis_data['overall_viral_score']),
                    viral_moments=viral_moments,
                    content_summary=analysis_data['content_summary'],
                    strengths=analysis_data['strengths'],
                    improvement_suggestions=analysis_data['improvement_suggestions'],
                    target_audience=analysis_data['target_audience'],
                    emotional_journey=analysis_data['emotional_journey'],
                    engagement_predictions=analysis_data['engagement_predictions']
                )
                
                return detailed_analysis
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse detailed analysis JSON: {e}")
                logger.error(f"Raw response: {response.text}")
                return self._get_default_detailed_analysis(duration)
                
        except Exception as e:
            logger.error(f"Error in detailed viral analysis: {str(e)}")
            return self._get_default_detailed_analysis(duration)

    async def analyze_virality(self, transcript: str, video_features: Dict[str, Any]) -> List[ViralityScore]:
        """Analyze content for virality potential across different niches with enhanced analysis"""
        try:
            # Extract enhanced features
            audio_features = video_features.get('audio_features', {})
            visual_features = video_features.get('visual_features', {})
            sentiment_data = video_features.get('sentiment_analysis', {})
            viral_segments = video_features.get('viral_segments', [])
            
            # Format JSON data for prompt inclusion
            audio_features_str = json.dumps(audio_features, indent=2)
            visual_features_str = json.dumps(visual_features, indent=2)
            sentiment_data_str = json.dumps(sentiment_data, indent=2)
            resolution_str = str(video_features.get('resolution', {}))
            
            prompt = f"""
            Analyze the following video content for virality potential across different social media niches using comprehensive analysis data.
            
            Video Transcript:
            {transcript}
            
            Enhanced Video Analysis:
            - Duration: {video_features.get('duration', 0)} seconds
            - Motion Score: {video_features.get('motion_score', 0)}
            - Brightness Score: {video_features.get('brightness_score', 0)}
            - Audio Features: {audio_features_str}
            - Visual Features: {visual_features_str}
            - Sentiment Analysis: {sentiment_data_str}
            - Viral Segments Found: {len(viral_segments)}
            - Resolution: {resolution_str}
            
            Please analyze the virality potential for these niches using the enhanced technical analysis:
            1. Entertainment/Comedy
            2. Educational/Tutorial
            3. Lifestyle/Vlog
            4. Technology/Gaming
            5. Business/Entrepreneurship
            6. Health/Fitness
            7. Travel/Adventure
            8. Food/Cooking
            
            For each niche, provide:
            - A virality score from 0.0 to 1.0 (where 1.0 is extremely viral)
            - A detailed explanation incorporating the technical analysis data
            - Consider audio cues (volume spikes, laughter), visual elements (scene changes, faces), and sentiment patterns
            
            Return your response as a JSON array with this structure:
            [
                {
                    "niche": "Entertainment/Comedy",
                    "score": 0.85,
                    "explanation": "Detailed explanation incorporating technical analysis..."
                },
                ...
            ]
            
            Only return the JSON array, no additional text.
            """
            
            response = self.model.generate_content(prompt)
            
            # Parse the JSON response
            try:
                scores_data = json.loads(response.text)
                scores = []
                
                for score_data in scores_data:
                    score = ViralityScore(
                        niche=score_data["niche"],
                        score=float(score_data["score"]),
                        explanation=score_data["explanation"]
                    )
                    scores.append(score)
                
                return scores
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse virality analysis JSON: {e}")
                logger.error(f"Raw response: {response.text}")
                
                # Fallback: return default scores
                return self._get_default_virality_scores()
                
        except Exception as e:
            logger.error(f"Error analyzing virality: {str(e)}")
            return self._get_default_virality_scores()
    
    async def generate_hashtags(self, transcript: str, top_niches: List[str]) -> List[Hashtag]:
        """Generate relevant hashtags for different platforms"""
        try:
            niches_text = ", ".join(top_niches)
            
            prompt = f"""
            Generate relevant hashtags for the following video content across different social media platforms.
            
            Video Transcript:
            {transcript}
            
            Top Performing Niches: {niches_text}
            
            Generate hashtags for these platforms:
            1. TikTok (trending, viral hashtags)
            2. Instagram (aesthetic, discoverable hashtags)
            3. YouTube (searchable, descriptive hashtags)
            4. Twitter (concise, trending hashtags)
            
            For each platform, provide 8-12 hashtags with relevance scores (0.0 to 1.0).
            
            Return your response as a JSON array with this structure:
            [
                {{
                    "tag": "#viral",
                    "platform": "TikTok",
                    "relevance_score": 0.9
                }},
                ...
            ]
            
            Only return the JSON array, no additional text.
            """
            
            response = self.model.generate_content(prompt)
            
            try:
                hashtags_data = json.loads(response.text)
                hashtags = []
                
                for hashtag_data in hashtags_data:
                    hashtag = Hashtag(
                        tag=hashtag_data["tag"],
                        platform=hashtag_data["platform"],
                        relevance_score=float(hashtag_data["relevance_score"])
                    )
                    hashtags.append(hashtag)
                
                return hashtags
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse hashtags JSON: {e}")
                logger.error(f"Raw response: {response.text}")
                
                # Fallback: return default hashtags
                return self._get_default_hashtags()
                
        except Exception as e:
            logger.error(f"Error generating hashtags: {str(e)}")
            return self._get_default_hashtags()
    
    async def generate_posting_recommendations(self, transcript: str, top_niches: List[str]) -> List[PostingRecommendation]:
        """Generate posting time and format recommendations"""
        try:
            niches_text = ", ".join(top_niches)
            
            prompt = f"""
            Generate posting recommendations for the following video content across different social media platforms.
            
            Video Transcript:
            {transcript}
            
            Top Performing Niches: {niches_text}
            
            For each platform, provide:
            1. Optimal posting times (in UTC, format: "HH:MM")
            2. Format suggestions (aspect ratio, duration, style tips)
            
            Platforms to analyze:
            1. TikTok
            2. Instagram (Reels)
            3. YouTube (Shorts)
            4. Twitter
            
            Return your response as a JSON array with this structure:
            [
                {{
                    "platform": "TikTok",
                    "optimal_times": ["14:00", "18:00", "21:00"],
                    "format_suggestions": {{
                        "aspect_ratio": "9:16",
                        "duration": "15-60 seconds",
                        "style_tips": ["Use trending sounds", "Add captions", "Hook viewers in first 3 seconds"]
                    }}
                }},
                ...
            ]
            
            Only return the JSON array, no additional text.
            """
            
            response = self.model.generate_content(prompt)
            
            try:
                recommendations_data = json.loads(response.text)
                recommendations = []
                
                for rec_data in recommendations_data:
                    recommendation = PostingRecommendation(
                        platform=rec_data["platform"],
                        optimal_times=rec_data["optimal_times"],
                        format_suggestions=rec_data["format_suggestions"]
                    )
                    recommendations.append(recommendation)
                
                return recommendations
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse recommendations JSON: {e}")
                logger.error(f"Raw response: {response.text}")
                
                # Fallback: return default recommendations
                return self._get_default_recommendations()
                
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            return self._get_default_recommendations()
    
    def _get_default_detailed_analysis(self, duration: float) -> DetailedViralAnalysis:
        """Fallback detailed viral analysis"""
        return DetailedViralAnalysis(
            overall_viral_score=0.5,
            viral_moments=[
                ViralMoment(
                    start_time=0.0,
                    end_time=min(30.0, duration),
                    viral_score=0.5,
                    moment_type="general",
                    description="Content analysis unavailable - default assessment provided",
                    key_features=["Unable to analyze specific features"],
                    confidence=0.3
                )
            ],
            content_summary="Content analysis unavailable due to technical issues",
            strengths=["Video content present"],
            improvement_suggestions=["Ensure proper video analysis pipeline"],
            target_audience="General audience",
            emotional_journey={
                "opening": "neutral",
                "middle": "neutral", 
                "climax": "neutral",
                "ending": "neutral"
            },
            engagement_predictions={
                "tiktok": 0.4,
                "instagram": 0.4,
                "youtube": 0.4,
                "twitter": 0.3
            }
        )
    
    def _get_default_virality_scores(self) -> List[ViralityScore]:
        """Fallback virality scores"""
        return [
            ViralityScore(
                niche="Entertainment/Comedy",
                score=0.6,
                explanation="Content analysis unavailable - default score provided"
            ),
            ViralityScore(
                niche="Educational/Tutorial",
                score=0.5,
                explanation="Content analysis unavailable - default score provided"
            ),
            ViralityScore(
                niche="Lifestyle/Vlog",
                score=0.4,
                explanation="Content analysis unavailable - default score provided"
            )
        ]
    
    def _get_default_hashtags(self) -> List[Hashtag]:
        """Fallback hashtags"""
        return [
            Hashtag(tag="#viral", platform="TikTok", relevance_score=0.8),
            Hashtag(tag="#trending", platform="TikTok", relevance_score=0.7),
            Hashtag(tag="#content", platform="Instagram", relevance_score=0.6),
            Hashtag(tag="#video", platform="YouTube", relevance_score=0.5)
        ]
    
    def _get_default_recommendations(self) -> List[PostingRecommendation]:
        """Fallback posting recommendations"""
        return [
            PostingRecommendation(
                platform="TikTok",
                optimal_times=["14:00", "18:00", "21:00"],
                format_suggestions={
                    "aspect_ratio": "9:16",
                    "duration": "15-60 seconds",
                    "style_tips": ["Use trending sounds", "Add captions"]
                }
            ),
            PostingRecommendation(
                platform="Instagram",
                optimal_times=["11:00", "15:00", "19:00"],
                format_suggestions={
                    "aspect_ratio": "9:16",
                    "duration": "15-90 seconds",
                    "style_tips": ["Use relevant hashtags", "Engaging thumbnail"]
                }
            )
        ]