"""
AI-Powered Viral Scoring Service for Cliper
Analyzes video content for viral potential using ML algorithms and LLM analysis
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import numpy as np
from statistics import mean, median

from .unified_llm_service import UnifiedLLMService, TaskType, LLMResponse
from ..models.pydantic_models import ViralityScore, PlatformEnum, Hashtag, PostingRecommendation

logger = logging.getLogger(__name__)

class ViralFactorType(Enum):
    """Types of viral factors that contribute to content virality"""
    EMOTIONAL_HOOK = "emotional_hook"
    VISUAL_APPEAL = "visual_appeal"
    AUDIO_QUALITY = "audio_quality"
    PACING = "pacing"
    SURPRISE_ELEMENT = "surprise_element"
    RELATABILITY = "relatability"
    TRENDING_TOPIC = "trending_topic"
    CALL_TO_ACTION = "call_to_action"
    STORYTELLING = "storytelling"
    HUMOR = "humor"
    EDUCATIONAL_VALUE = "educational_value"
    CONTROVERSY = "controversy"

@dataclass
class ViralFactor:
    """Individual viral factor with score and reasoning"""
    factor_type: ViralFactorType
    score: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    reasoning: str
    timestamp_relevance: Optional[Tuple[float, float]] = None  # (start, end) if time-specific

@dataclass
class PlatformViralScore:
    """Platform-specific viral score with optimization suggestions"""
    platform: PlatformEnum
    score: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    optimization_suggestions: List[str]
    ideal_duration: Tuple[float, float]  # (min, max) seconds
    key_factors: List[ViralFactor]

@dataclass
class ViralMoment:
    """Specific moment in video with high viral potential"""
    start_time: float
    end_time: float
    viral_score: float
    moment_type: str
    description: str
    key_features: List[str]
    confidence: float
    platform_suitability: Dict[str, float]

@dataclass
class ComprehensiveViralAnalysis:
    """Complete viral analysis result"""
    overall_viral_score: float
    confidence: float
    platform_scores: Dict[str, PlatformViralScore]
    viral_moments: List[ViralMoment]
    viral_factors: List[ViralFactor]
    content_summary: str
    strengths: List[str]
    improvement_suggestions: List[str]
    processing_time: float
    metadata: Dict[str, Any]

class ViralScoringService:
    """AI-powered viral scoring service with platform-specific analysis"""
    
    def __init__(self):
        self.llm_service = UnifiedLLMService()
        
        # Platform-specific viral factor weights
        self.platform_weights = {
            PlatformEnum.TIKTOK: {
                ViralFactorType.EMOTIONAL_HOOK: 0.25,
                ViralFactorType.VISUAL_APPEAL: 0.20,
                ViralFactorType.PACING: 0.15,
                ViralFactorType.SURPRISE_ELEMENT: 0.15,
                ViralFactorType.TRENDING_TOPIC: 0.10,
                ViralFactorType.HUMOR: 0.10,
                ViralFactorType.CALL_TO_ACTION: 0.05
            },
            PlatformEnum.INSTAGRAM: {
                ViralFactorType.VISUAL_APPEAL: 0.30,
                ViralFactorType.EMOTIONAL_HOOK: 0.20,
                ViralFactorType.STORYTELLING: 0.15,
                ViralFactorType.RELATABILITY: 0.15,
                ViralFactorType.TRENDING_TOPIC: 0.10,
                ViralFactorType.CALL_TO_ACTION: 0.10
            },
            PlatformEnum.YOUTUBE: {
                ViralFactorType.STORYTELLING: 0.25,
                ViralFactorType.EDUCATIONAL_VALUE: 0.20,
                ViralFactorType.EMOTIONAL_HOOK: 0.15,
                ViralFactorType.VISUAL_APPEAL: 0.15,
                ViralFactorType.AUDIO_QUALITY: 0.10,
                ViralFactorType.RELATABILITY: 0.10,
                ViralFactorType.CALL_TO_ACTION: 0.05
            }
        }
        
        # Platform-specific optimal durations (in seconds)
        self.platform_durations = {
            PlatformEnum.TIKTOK: (15, 60),
            PlatformEnum.INSTAGRAM: (15, 90),
            PlatformEnum.YOUTUBE: (30, 300)
        }
        
        logger.info("ViralScoringService initialized")
    
    async def analyze_viral_potential(
        self,
        transcription: Dict[str, Any],
        scenes: List[Any] = None,
        emotions: List[Any] = None,
        video_metadata: Dict[str, Any] = None,
        target_platforms: List[PlatformEnum] = None
    ) -> ComprehensiveViralAnalysis:
        """
        Comprehensive viral potential analysis for video content
        
        Args:
            transcription: Video transcription data
            scenes: Scene analysis data
            emotions: Emotion analysis data
            video_metadata: Additional video metadata
            target_platforms: Platforms to analyze for (default: all major platforms)
        
        Returns:
            ComprehensiveViralAnalysis with detailed scoring and recommendations
        """
        start_time = time.time()
        
        if target_platforms is None:
            target_platforms = [PlatformEnum.TIKTOK, PlatformEnum.INSTAGRAM, PlatformEnum.YOUTUBE]
        
        logger.info(f"Starting viral analysis for {len(target_platforms)} platforms")
        
        try:
            # Step 1: Extract content features
            content_features = self._extract_content_features(transcription, scenes, emotions, video_metadata)
            
            # Step 2: Analyze viral factors using AI
            viral_factors = await self._analyze_viral_factors(content_features)
            
            # Step 3: Calculate platform-specific scores
            platform_scores = {}
            for platform in target_platforms:
                platform_score = await self._calculate_platform_score(
                    platform, viral_factors, content_features
                )
                platform_scores[platform.value] = platform_score
            
            # Step 4: Identify viral moments
            viral_moments = await self._identify_viral_moments(content_features, viral_factors)
            
            # Step 5: Calculate overall viral score
            overall_score = self._calculate_overall_score(platform_scores, viral_factors)
            
            # Step 6: Generate insights and recommendations
            insights = await self._generate_insights(viral_factors, platform_scores, content_features)
            
            processing_time = time.time() - start_time
            
            return ComprehensiveViralAnalysis(
                overall_viral_score=overall_score,
                confidence=self._calculate_confidence(viral_factors, platform_scores),
                platform_scores=platform_scores,
                viral_moments=viral_moments,
                viral_factors=viral_factors,
                content_summary=insights.get('summary', ''),
                strengths=insights.get('strengths', []),
                improvement_suggestions=insights.get('improvements', []),
                processing_time=processing_time,
                metadata={
                    'analysis_timestamp': datetime.utcnow().isoformat(),
                    'platforms_analyzed': [p.value for p in target_platforms],
                    'total_factors_analyzed': len(viral_factors),
                    'ai_provider_used': 'unified_llm_service'
                }
            )
            
        except Exception as e:
            logger.error(f"Error in viral analysis: {e}")
            # Return fallback analysis
            return self._create_fallback_analysis(target_platforms, time.time() - start_time)

    async def analyze_comprehensive_viral_potential(
        self,
        video_url: str,
        clip_segments: Optional[List[Dict[str, Any]]] = None,
        platforms: Optional[List[str]] = None,
        include_insights: bool = True
    ) -> ComprehensiveViralAnalysis:
        """
        Comprehensive viral potential analysis for video content via URL
        
        Args:
            video_url: URL of the video to analyze
            clip_segments: Optional specific segments to analyze
            platforms: Target platforms for analysis
            include_insights: Whether to include AI-generated insights
        
        Returns:
            ComprehensiveViralAnalysis with detailed scoring and recommendations
        """
        start_time = time.time()
        
        # Convert platform strings to enums
        if platforms:
            target_platforms = []
            for platform in platforms:
                try:
                    target_platforms.append(PlatformEnum(platform.lower()))
                except ValueError:
                    logger.warning(f"Unknown platform: {platform}")
        else:
            target_platforms = [PlatformEnum.TIKTOK, PlatformEnum.INSTAGRAM, PlatformEnum.YOUTUBE]
        
        logger.info(f"Starting comprehensive viral analysis for video: {video_url}")
        
        try:
            # For now, create mock content features since we don't have video processing
            # In a real implementation, this would extract features from the video
            content_features = {
                'duration': 45,  # Mock duration
                'word_count': 150,  # Mock word count
                'speaking_pace': 120,  # Mock speaking pace
                'silence_ratio': 0.15,  # Mock silence ratio
                'speech_segments': [{'start': 0, 'end': 45, 'text': 'Mock transcript'}],
                'emotional_peaks': [{'timestamp': 15, 'intensity': 0.8}],
                'scene_changes': [{'timestamp': 10}, {'timestamp': 25}]
            }
            
            # Analyze viral factors using AI
            viral_factors = await self._analyze_viral_factors(content_features)
            
            # Calculate platform-specific scores
            platform_scores = {}
            for platform in target_platforms:
                platform_score = await self._calculate_platform_score(
                    platform, viral_factors, content_features
                )
                platform_scores[platform.value] = platform_score
            
            # Identify viral moments
            viral_moments = await self._identify_viral_moments(content_features, viral_factors)
            
            # Calculate overall viral score
            overall_score = self._calculate_overall_score(platform_scores, viral_factors)
            
            # Generate insights and recommendations if requested
            insights = {}
            if include_insights:
                insights = await self._generate_insights(viral_factors, platform_scores, content_features)
            
            processing_time = time.time() - start_time
            
            # Convert viral moments to ViralityScore format for API compatibility
            virality_scores = []
            for moment in viral_moments:
                virality_score = ViralityScore(
                    start_time=moment.start_time,
                    end_time=moment.end_time,
                    score=moment.viral_score,
                    reasons=[moment.description],
                    keywords=moment.key_features,
                    emotion=moment.moment_type,
                    engagement_factors={
                        'viral_score': moment.viral_score,
                        'confidence': moment.confidence
                    }
                )
                virality_scores.append(virality_score)
            
            # Generate hashtags
            hashtags = []
            for factor in viral_factors[:5]:  # Top 5 factors for hashtags
                hashtag = Hashtag(
                    tag=f"#{factor.factor_type.value.replace('_', '')}",
                    platform="general",
                    relevance_score=factor.score
                )
                hashtags.append(hashtag)
            
            # Generate posting recommendations
            posting_recommendations = []
            for platform in target_platforms:
                platform_score = platform_scores.get(platform.value)
                if platform_score:
                    recommendation = PostingRecommendation(
                        platform=platform.value,
                        optimal_times=["12:00", "18:00", "20:00"],  # Mock optimal times
                        format_suggestions={
                            "duration": f"{platform_score.ideal_duration[0]}-{platform_score.ideal_duration[1]}s",
                            "suggestions": platform_score.optimization_suggestions[:3]
                        }
                    )
                    posting_recommendations.append(recommendation)
            
            # Create result object with API-compatible format
            result = ComprehensiveViralAnalysis(
                overall_viral_score=overall_score,
                confidence=self._calculate_confidence(viral_factors, platform_scores),
                platform_scores=platform_scores,
                viral_moments=viral_moments,
                viral_factors=viral_factors,
                content_summary=insights.get('summary', 'Viral analysis completed'),
                strengths=insights.get('strengths', []),
                improvement_suggestions=insights.get('improvements', []),
                processing_time=processing_time,
                metadata={
                    'analysis_timestamp': datetime.utcnow().isoformat(),
                    'platforms_analyzed': [p.value for p in target_platforms],
                    'total_factors_analyzed': len(viral_factors),
                    'ai_provider_used': 'unified_llm_service',
                    'video_url': video_url
                }
            )
            
            # Add API-compatible attributes for the response
            result.viral_moments = virality_scores  # Override with API format
            result.hashtags = hashtags
            result.posting_recommendations = posting_recommendations
            result.insights = insights.get('insights', [
                f"Overall viral score: {overall_score:.2f}",
                f"Best platform: {max(platform_scores.keys(), key=lambda k: platform_scores[k].score)}",
                f"Key strengths: {', '.join(insights.get('strengths', ['Good content quality']))}"
            ])
            
            return result
            
        except Exception as e:
            logger.error(f"Error in comprehensive viral analysis: {e}")
            # Return fallback analysis
            return self._create_comprehensive_fallback_analysis(target_platforms, time.time() - start_time, video_url)
    
    def _extract_content_features(
        self,
        transcription: Dict[str, Any],
        scenes: List[Any] = None,
        emotions: List[Any] = None,
        video_metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Extract key features from video content for analysis"""
        features = {
            'duration': 0,
            'word_count': 0,
            'speech_segments': [],
            'emotional_peaks': [],
            'scene_changes': [],
            'key_phrases': [],
            'speaking_pace': 0,
            'silence_ratio': 0
        }
        
        # Process transcription
        if transcription and 'segments' in transcription:
            segments = transcription['segments']
            features['speech_segments'] = segments
            
            # Calculate basic metrics
            total_words = 0
            total_speech_time = 0
            
            for segment in segments:
                if 'text' in segment:
                    words = len(segment['text'].split())
                    total_words += words
                
                if 'start' in segment and 'end' in segment:
                    duration = segment['end'] - segment['start']
                    total_speech_time += duration
                    features['duration'] = max(features['duration'], segment['end'])
            
            features['word_count'] = total_words
            if total_speech_time > 0:
                features['speaking_pace'] = total_words / (total_speech_time / 60)  # words per minute
                features['silence_ratio'] = max(0, (features['duration'] - total_speech_time) / features['duration'])
        
        # Process emotions
        if emotions:
            features['emotional_peaks'] = [
                {
                    'timestamp': emotion.get('timestamp', 0),
                    'emotion': emotion.get('dominant_emotion', 'neutral'),
                    'intensity': emotion.get('confidence', 0)
                }
                for emotion in emotions
                if emotion.get('confidence', 0) > 0.7  # High confidence emotions only
            ]
        
        # Process scenes
        if scenes:
            features['scene_changes'] = [
                {
                    'timestamp': scene.get('timestamp', 0),
                    'scene_type': scene.get('scene_type', 'unknown'),
                    'visual_complexity': scene.get('complexity', 0)
                }
                for scene in scenes
            ]
        
        # Add video metadata
        if video_metadata:
            features.update({
                'file_size': video_metadata.get('file_size', 0),
                'resolution': video_metadata.get('resolution', ''),
                'fps': video_metadata.get('fps', 0)
            })
        
        return features
    
    async def _analyze_viral_factors(self, content_features: Dict[str, Any]) -> List[ViralFactor]:
        """Use AI to analyze viral factors in the content"""
        
        # Prepare analysis prompt
        prompt = self._create_viral_analysis_prompt(content_features)
        
        system_prompt = """You are an expert social media strategist and viral content analyst. 
Analyze the provided video content features and identify viral factors.
Respond with valid JSON only, following the specified format."""
        
        response = await self.llm_service._execute_with_fallback(
            TaskType.VIRALITY_ANALYSIS,
            prompt,
            system_prompt,
            max_tokens=2000
        )
        
        if not response.success:
            logger.warning("AI viral factor analysis failed, using fallback")
            return self._fallback_viral_factors(content_features)
        
        try:
            analysis_data = json.loads(response.data)
            viral_factors = []
            
            for factor_data in analysis_data.get('viral_factors', []):
                factor = ViralFactor(
                    factor_type=ViralFactorType(factor_data['factor_type']),
                    score=max(0.0, min(1.0, factor_data['score'])),
                    confidence=max(0.0, min(1.0, factor_data['confidence'])),
                    reasoning=factor_data['reasoning'],
                    timestamp_relevance=tuple(factor_data['timestamp_relevance']) if factor_data.get('timestamp_relevance') else None
                )
                viral_factors.append(factor)
            
            return viral_factors
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse viral factor analysis: {e}")
            return self._fallback_viral_factors(content_features)
    
    async def _calculate_platform_score(
        self,
        platform: PlatformEnum,
        viral_factors: List[ViralFactor],
        content_features: Dict[str, Any]
    ) -> PlatformViralScore:
        """Calculate platform-specific viral score"""
        
        platform_weights = self.platform_weights.get(platform, {})
        weighted_score = 0.0
        total_weight = 0.0
        key_factors = []
        
        # Calculate weighted score based on platform preferences
        for factor in viral_factors:
            weight = platform_weights.get(factor.factor_type, 0.05)  # Default small weight
            weighted_score += factor.score * weight * factor.confidence
            total_weight += weight
            
            # Include factors with significant impact
            if weight > 0.1 or factor.score > 0.8:
                key_factors.append(factor)
        
        # Normalize score
        if total_weight > 0:
            platform_score = weighted_score / total_weight
        else:
            platform_score = 0.5  # Neutral score if no weights
        
        # Apply platform-specific adjustments
        platform_score = self._apply_platform_adjustments(platform, platform_score, content_features)
        
        # Generate optimization suggestions
        suggestions = await self._generate_platform_suggestions(platform, viral_factors, content_features)
        
        # Calculate confidence based on factor confidence and coverage
        confidence = self._calculate_platform_confidence(viral_factors, platform_weights)
        
        return PlatformViralScore(
            platform=platform,
            score=max(0.0, min(1.0, platform_score)),
            confidence=confidence,
            optimization_suggestions=suggestions,
            ideal_duration=self.platform_durations.get(platform, (30, 120)),
            key_factors=key_factors
        )
    
    def _apply_platform_adjustments(
        self,
        platform: PlatformEnum,
        base_score: float,
        content_features: Dict[str, Any]
    ) -> float:
        """Apply platform-specific adjustments to the base score"""
        
        duration = content_features.get('duration', 0)
        ideal_min, ideal_max = self.platform_durations.get(platform, (30, 120))
        
        # Duration penalty/bonus
        duration_factor = 1.0
        if duration < ideal_min:
            duration_factor = 0.8  # Penalty for too short
        elif duration > ideal_max * 2:
            duration_factor = 0.7  # Penalty for too long
        elif ideal_min <= duration <= ideal_max:
            duration_factor = 1.1  # Bonus for ideal duration
        
        # Platform-specific adjustments
        if platform == PlatformEnum.TIKTOK:
            # TikTok favors fast-paced content
            pace = content_features.get('speaking_pace', 0)
            if pace > 150:  # Fast speaking
                duration_factor *= 1.05
        
        elif platform == PlatformEnum.YOUTUBE:
            # YouTube favors longer, educational content
            if duration > 60:  # Longer content
                duration_factor *= 1.05
        
        return base_score * duration_factor
    
    async def _identify_viral_moments(
        self,
        content_features: Dict[str, Any],
        viral_factors: List[ViralFactor]
    ) -> List[ViralMoment]:
        """Identify specific moments with high viral potential"""
        
        viral_moments = []
        
        # Analyze emotional peaks
        for peak in content_features.get('emotional_peaks', []):
            if peak['intensity'] > 0.8:  # High intensity emotions
                moment = ViralMoment(
                    start_time=max(0, peak['timestamp'] - 2),
                    end_time=peak['timestamp'] + 3,
                    viral_score=peak['intensity'] * 0.9,
                    moment_type='emotional_peak',
                    description=f"High {peak['emotion']} moment",
                    key_features=[f"Strong {peak['emotion']} emotion"],
                    confidence=peak['intensity'],
                    platform_suitability={
                        'tiktok': 0.9 if peak['emotion'] in ['joy', 'surprise'] else 0.7,
                        'instagram': 0.8,
                        'youtube': 0.7
                    }
                )
                viral_moments.append(moment)
        
        # Analyze factors with timestamp relevance
        for factor in viral_factors:
            if factor.timestamp_relevance and factor.score > 0.7:
                start_time, end_time = factor.timestamp_relevance
                moment = ViralMoment(
                    start_time=start_time,
                    end_time=end_time,
                    viral_score=factor.score * factor.confidence,
                    moment_type=factor.factor_type.value,
                    description=factor.reasoning,
                    key_features=[factor.factor_type.value],
                    confidence=factor.confidence,
                    platform_suitability=self._calculate_moment_platform_suitability(factor.factor_type)
                )
                viral_moments.append(moment)
        
        # Sort by viral score and return top moments
        viral_moments.sort(key=lambda x: x.viral_score, reverse=True)
        return viral_moments[:10]  # Top 10 moments
    
    def _calculate_moment_platform_suitability(self, factor_type: ViralFactorType) -> Dict[str, float]:
        """Calculate how suitable a viral moment is for each platform"""
        
        suitability = {
            'tiktok': 0.5,
            'instagram': 0.5,
            'youtube': 0.5
        }
        
        if factor_type == ViralFactorType.HUMOR:
            suitability.update({'tiktok': 0.9, 'instagram': 0.8, 'youtube': 0.7})
        elif factor_type == ViralFactorType.EDUCATIONAL_VALUE:
            suitability.update({'youtube': 0.9, 'instagram': 0.6, 'tiktok': 0.4})
        elif factor_type == ViralFactorType.VISUAL_APPEAL:
            suitability.update({'instagram': 0.9, 'tiktok': 0.8, 'youtube': 0.7})
        elif factor_type == ViralFactorType.SURPRISE_ELEMENT:
            suitability.update({'tiktok': 0.9, 'instagram': 0.7, 'youtube': 0.6})
        
        return suitability
    
    def _calculate_overall_score(
        self,
        platform_scores: Dict[str, PlatformViralScore],
        viral_factors: List[ViralFactor]
    ) -> float:
        """Calculate overall viral score across all platforms"""
        
        if not platform_scores:
            return 0.0
        
        # Weighted average of platform scores
        platform_weights = {'tiktok': 0.4, 'instagram': 0.35, 'youtube': 0.25}
        weighted_sum = 0.0
        total_weight = 0.0
        
        for platform_name, platform_score in platform_scores.items():
            weight = platform_weights.get(platform_name, 0.33)
            weighted_sum += platform_score.score * weight
            total_weight += weight
        
        if total_weight > 0:
            return weighted_sum / total_weight
        else:
            return mean([ps.score for ps in platform_scores.values()])
    
    def _calculate_confidence(
        self,
        viral_factors: List[ViralFactor],
        platform_scores: Dict[str, PlatformViralScore]
    ) -> float:
        """Calculate overall confidence in the viral analysis"""
        
        if not viral_factors:
            return 0.0
        
        # Factor confidence
        factor_confidence = mean([f.confidence for f in viral_factors])
        
        # Platform confidence
        platform_confidence = mean([ps.confidence for ps in platform_scores.values()]) if platform_scores else 0.5
        
        # Coverage confidence (how many factors we analyzed)
        coverage_confidence = min(1.0, len(viral_factors) / 8)  # Ideal: 8+ factors
        
        return (factor_confidence * 0.5 + platform_confidence * 0.3 + coverage_confidence * 0.2)
    
    def _calculate_platform_confidence(
        self,
        viral_factors: List[ViralFactor],
        platform_weights: Dict[ViralFactorType, float]
    ) -> float:
        """Calculate confidence for a specific platform analysis"""
        
        if not viral_factors:
            return 0.0
        
        # Weight coverage - how well do our factors cover this platform's preferences
        covered_weight = sum(
            platform_weights.get(factor.factor_type, 0) * factor.confidence
            for factor in viral_factors
        )
        total_weight = sum(platform_weights.values())
        
        coverage = covered_weight / total_weight if total_weight > 0 else 0.0
        
        # Factor quality
        avg_confidence = mean([f.confidence for f in viral_factors])
        
        return (coverage * 0.7 + avg_confidence * 0.3)
    
    async def _generate_insights(
        self,
        viral_factors: List[ViralFactor],
        platform_scores: Dict[str, PlatformViralScore],
        content_features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate insights and recommendations using AI"""
        
        # Prepare insights prompt
        insights_prompt = self._create_insights_prompt(viral_factors, platform_scores, content_features)
        
        system_prompt = """You are an expert content strategist. Provide actionable insights and recommendations 
for improving viral potential. Respond with valid JSON only."""
        
        response = await self.llm_service._execute_with_fallback(
            TaskType.CONTENT_SUMMARY,
            insights_prompt,
            system_prompt,
            max_tokens=1500
        )
        
        if response.success:
            try:
                return json.loads(response.data)
            except json.JSONDecodeError:
                pass
        
        # Fallback insights
        return self._generate_fallback_insights(viral_factors, platform_scores)
    
    async def _generate_platform_suggestions(
        self,
        platform: PlatformEnum,
        viral_factors: List[ViralFactor],
        content_features: Dict[str, Any]
    ) -> List[str]:
        """Generate platform-specific optimization suggestions"""
        
        suggestions = []
        duration = content_features.get('duration', 0)
        ideal_min, ideal_max = self.platform_durations.get(platform, (30, 120))
        
        # Duration suggestions
        if duration < ideal_min:
            suggestions.append(f"Consider extending content to {ideal_min}-{ideal_max} seconds for optimal {platform.value} performance")
        elif duration > ideal_max * 2:
            suggestions.append(f"Consider shortening content to under {ideal_max} seconds for better {platform.value} engagement")
        
        # Platform-specific suggestions
        if platform == PlatformEnum.TIKTOK:
            suggestions.extend([
                "Add trending hashtags and sounds",
                "Include a strong hook in the first 3 seconds",
                "Use vertical video format (9:16)",
                "Add captions for accessibility"
            ])
        elif platform == PlatformEnum.INSTAGRAM:
            suggestions.extend([
                "Optimize for visual appeal with good lighting",
                "Include engaging captions with relevant hashtags",
                "Consider carousel format for multiple clips",
                "Use Instagram-specific features like polls or questions"
            ])
        elif platform == PlatformEnum.YOUTUBE:
            suggestions.extend([
                "Create compelling thumbnails",
                "Include educational or entertainment value",
                "Optimize title and description for SEO",
                "Add end screens and cards for engagement"
            ])
        
        return suggestions[:5]  # Limit to top 5 suggestions
    
    def _create_viral_analysis_prompt(self, content_features: Dict[str, Any]) -> str:
        """Create prompt for AI viral factor analysis"""
        
        return f"""
Analyze the following video content features for viral potential:

Duration: {content_features.get('duration', 0)} seconds
Word Count: {content_features.get('word_count', 0)}
Speaking Pace: {content_features.get('speaking_pace', 0)} words/minute
Silence Ratio: {content_features.get('silence_ratio', 0):.2f}

Speech Segments: {len(content_features.get('speech_segments', []))} segments
Emotional Peaks: {len(content_features.get('emotional_peaks', []))} peaks
Scene Changes: {len(content_features.get('scene_changes', []))} changes

Identify viral factors and score them. Respond with JSON in this format:
{{
    "viral_factors": [
        {{
            "factor_type": "emotional_hook",
            "score": 0.8,
            "confidence": 0.9,
            "reasoning": "Strong emotional content detected",
            "timestamp_relevance": [10.5, 15.2]
        }}
    ]
}}

Available factor types: {[f.value for f in ViralFactorType]}
"""
    
    def _create_insights_prompt(
        self,
        viral_factors: List[ViralFactor],
        platform_scores: Dict[str, PlatformViralScore],
        content_features: Dict[str, Any]
    ) -> str:
        """Create prompt for generating insights and recommendations"""
        
        factor_summary = [
            f"{f.factor_type.value}: {f.score:.2f} ({f.reasoning})"
            for f in viral_factors[:5]
        ]
        
        platform_summary = [
            f"{name}: {score.score:.2f}"
            for name, score in platform_scores.items()
        ]
        
        return f"""
Analyze this viral scoring data and provide insights:

Top Viral Factors:
{chr(10).join(factor_summary)}

Platform Scores:
{chr(10).join(platform_summary)}

Content Duration: {content_features.get('duration', 0)} seconds

Provide insights in JSON format:
{{
    "summary": "Brief content summary",
    "strengths": ["strength1", "strength2"],
    "improvements": ["improvement1", "improvement2"]
}}
"""
    
    def _fallback_viral_factors(self, content_features: Dict[str, Any]) -> List[ViralFactor]:
        """Generate fallback viral factors when AI analysis fails"""
        
        factors = []
        
        # Basic duration-based factor
        duration = content_features.get('duration', 0)
        if 15 <= duration <= 60:
            factors.append(ViralFactor(
                factor_type=ViralFactorType.PACING,
                score=0.7,
                confidence=0.6,
                reasoning="Good duration for social media"
            ))
        
        # Speaking pace factor
        pace = content_features.get('speaking_pace', 0)
        if pace > 100:
            factors.append(ViralFactor(
                factor_type=ViralFactorType.PACING,
                score=0.6,
                confidence=0.5,
                reasoning="Moderate speaking pace detected"
            ))
        
        # Emotional peaks factor
        if content_features.get('emotional_peaks'):
            factors.append(ViralFactor(
                factor_type=ViralFactorType.EMOTIONAL_HOOK,
                score=0.6,
                confidence=0.5,
                reasoning="Emotional content detected"
            ))
        
        return factors
    
    def _generate_fallback_insights(
        self,
        viral_factors: List[ViralFactor],
        platform_scores: Dict[str, PlatformViralScore]
    ) -> Dict[str, Any]:
        """Generate fallback insights when AI analysis fails"""
        
        avg_score = mean([f.score for f in viral_factors]) if viral_factors else 0.5
        
        return {
            'summary': f"Content shows {'good' if avg_score > 0.6 else 'moderate'} viral potential",
            'strengths': [f.factor_type.value.replace('_', ' ').title() for f in viral_factors if f.score > 0.7],
            'improvements': [
                "Add more emotional hooks",
                "Improve visual appeal",
                "Optimize for platform-specific features"
            ]
        }
    
    def _create_fallback_analysis(
        self,
        target_platforms: List[PlatformEnum],
        processing_time: float
    ) -> ComprehensiveViralAnalysis:
        """Create fallback analysis when main analysis fails"""
        
        fallback_factors = [
            ViralFactor(
                factor_type=ViralFactorType.VISUAL_APPEAL,
                score=0.5,
                confidence=0.3,
                reasoning="Fallback analysis - limited data available"
            )
        ]
        
        platform_scores = {}
        for platform in target_platforms:
            platform_scores[platform.value] = PlatformViralScore(
                platform=platform,
                score=0.5,
                confidence=0.3,
                optimization_suggestions=["Improve content quality", "Add engaging elements"],
                ideal_duration=self.platform_durations.get(platform, (30, 120)),
                key_factors=fallback_factors
            )
        
        return ComprehensiveViralAnalysis(
            overall_viral_score=0.5,
            confidence=0.3,
            platform_scores=platform_scores,
            viral_moments=[],
            viral_factors=fallback_factors,
            content_summary="Limited analysis available",
            strengths=["Content uploaded successfully"],
            improvement_suggestions=["Improve content quality", "Add more engaging elements"],
            processing_time=processing_time,
            metadata={
                'analysis_type': 'fallback',
                'timestamp': datetime.utcnow().isoformat()
            }
        )

    def _create_comprehensive_fallback_analysis(
        self,
        target_platforms: List[PlatformEnum],
        processing_time: float,
        video_url: str
    ) -> ComprehensiveViralAnalysis:
        """Create comprehensive fallback analysis when main analysis fails"""
        
        fallback_factors = [
            ViralFactor(
                factor_type=ViralFactorType.VISUAL_APPEAL,
                score=0.5,
                confidence=0.3,
                reasoning="Fallback analysis - limited data available"
            )
        ]
        
        platform_scores = {}
        for platform in target_platforms:
            platform_scores[platform.value] = PlatformViralScore(
                platform=platform,
                score=0.5,
                confidence=0.3,
                optimization_suggestions=["Improve content quality", "Add engaging elements"],
                ideal_duration=self.platform_durations.get(platform, (30, 120)),
                key_factors=fallback_factors
            )
        
        # Create fallback viral moments
        fallback_moments = [
            ViralityScore(
                start_time=0.0,
                end_time=30.0,
                score=0.5,
                reasons=["Fallback analysis"],
                keywords=["content"],
                emotion="neutral",
                engagement_factors={'confidence': 0.3}
            )
        ]
        
        # Create fallback hashtags
        fallback_hashtags = [
            Hashtag(tag="#content", platform="general", relevance_score=0.5),
            Hashtag(tag="#video", platform="general", relevance_score=0.4)
        ]
        
        # Create fallback recommendations
        fallback_recommendations = []
        for platform in target_platforms:
            recommendation = PostingRecommendation(
                platform=platform.value,
                optimal_times=["12:00", "18:00"],
                format_suggestions={
                    "type": "Standard post",
                    "description": "Regular social media content"
                }
            )
            fallback_recommendations.append(recommendation)
        
        result = ComprehensiveViralAnalysis(
            overall_viral_score=0.5,
            confidence=0.3,
            platform_scores=platform_scores,
            viral_moments=[],
            viral_factors=fallback_factors,
            content_summary="Fallback analysis - limited data available",
            strengths=["Content uploaded successfully"],
            improvement_suggestions=["Improve content quality", "Add more engaging elements"],
            processing_time=processing_time,
            metadata={
                'analysis_type': 'comprehensive_fallback',
                'timestamp': datetime.utcnow().isoformat(),
                'video_url': video_url
            }
        )
        
        # Add API-compatible attributes
        result.viral_moments = fallback_moments
        result.hashtags = fallback_hashtags
        result.posting_recommendations = fallback_recommendations
        result.insights = [
            "Fallback analysis performed due to processing limitations",
            "Consider re-uploading with better quality video",
            "Manual review recommended for optimal results"
        ]
        
        return result

# Convenience function for quick viral scoring
async def quick_viral_score(
    transcription: Dict[str, Any],
    platform: PlatformEnum = PlatformEnum.TIKTOK
) -> float:
    """Quick viral score for a single platform"""
    service = ViralScoringService()
    analysis = await service.analyze_viral_potential(
        transcription=transcription,
        target_platforms=[platform]
    )
    return analysis.platform_scores.get(platform.value, PlatformViralScore(platform, 0.5, 0.3, [], (30, 60), [])).score