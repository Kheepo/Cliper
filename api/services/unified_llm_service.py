import os
import json
import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
from enum import Enum
import hashlib
from functools import wraps

# OpenAI imports
try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AsyncOpenAI = None

# Gemini imports
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None

# Local imports
from api.models.pydantic_models import ViralityScore, Hashtag, PostingRecommendation

@dataclass
class ClipSegment:
    """Represents a video segment selected for clip generation"""
    start_time: float
    end_time: float
    virality_score: float
    content_summary: str
    keywords: List[str] = None
    duration: float = None
    confidence: float = None
    engagement_factors: List[str] = None
    platform_suitability: Dict[str, float] = None
    clip_type: str = "highlight"  # 'highlight', 'teaser', 'summary'
    reasoning: str = None
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []
        if self.duration is None:
            self.duration = self.end_time - self.start_time
        if self.engagement_factors is None:
            self.engagement_factors = []
        if self.platform_suitability is None:
            self.platform_suitability = {}

@dataclass
class SegmentSelectionResult:
    """Result of AI-powered segment selection"""
    segments: List[ClipSegment]
    total_processing_time: float
    selection_strategy: str
    metadata: Dict[str, Any]

logger = logging.getLogger(__name__)

class LLMProvider(Enum):
    """Available LLM providers"""
    OPENAI = "openai"
    GEMINI = "gemini"
    FALLBACK = "fallback"

class TaskType(Enum):
    """Types of LLM tasks for intelligent routing"""
    SEGMENT_SELECTION = "segment_selection"  # Complex reasoning - prefer OpenAI
    VIRALITY_ANALYSIS = "virality_analysis"  # Content analysis - prefer Gemini
    HASHTAG_GENERATION = "hashtag_generation"  # Creative - prefer Gemini
    POSTING_RECOMMENDATIONS = "posting_recommendations"  # Analysis - prefer Gemini
    CONTENT_SUMMARY = "content_summary"  # Analysis - prefer Gemini

@dataclass
class LLMResponse:
    """Standardized LLM response format"""
    success: bool
    data: Any
    provider: LLMProvider
    processing_time: float
    tokens_used: Optional[int] = None
    error: Optional[str] = None
    fallback_used: bool = False

@dataclass
class ViralMoment:
    """Represents a specific viral moment in the video"""
    start_time: float
    end_time: float
    viral_score: float
    moment_type: str
    description: str
    key_features: List[str]
    confidence: float

@dataclass
class DetailedViralAnalysis:
    """Comprehensive viral analysis with timestamps"""
    overall_viral_score: float
    viral_moments: List[ViralMoment]
    content_summary: str
    strengths: List[str]
    improvement_suggestions: List[str]
    processing_time: float
    provider_used: str

class UnifiedLLMService:
    """Unified LLM service with intelligent routing between OpenAI and Gemini"""
    
    def __init__(self):
        self.openai_client = None
        self.gemini_model = None
        self.openai_available = False
        self.gemini_available = False
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour cache TTL
        
        # Initialize providers
        self._initialize_providers()
        
        # Provider preferences for different task types
        self.provider_preferences = {
            TaskType.SEGMENT_SELECTION: [LLMProvider.OPENAI, LLMProvider.GEMINI],
            TaskType.VIRALITY_ANALYSIS: [LLMProvider.GEMINI, LLMProvider.OPENAI],
            TaskType.HASHTAG_GENERATION: [LLMProvider.GEMINI, LLMProvider.OPENAI],
            TaskType.POSTING_RECOMMENDATIONS: [LLMProvider.GEMINI, LLMProvider.OPENAI],
            TaskType.CONTENT_SUMMARY: [LLMProvider.GEMINI, LLMProvider.OPENAI]
        }
        
        logger.info(f"UnifiedLLMService initialized - OpenAI: {self.openai_available}, Gemini: {self.gemini_available}")
    
    def _initialize_providers(self):
        """Initialize available LLM providers"""
        # Initialize OpenAI
        openai_key = os.getenv('OPENAI_API_KEY')
        if openai_key and OPENAI_AVAILABLE and not openai_key.startswith('your-') and len(openai_key) > 20:
            try:
                self.openai_client = AsyncOpenAI(api_key=openai_key)
                self.openai_available = True
                logger.info("OpenAI client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.openai_available = False
        else:
            logger.warning("OpenAI API key not found or invalid")
        
        # Initialize Gemini
        gemini_key = os.getenv('GEMINI_API_KEY')
        if gemini_key and GEMINI_AVAILABLE and not gemini_key.startswith('your-') and len(gemini_key) > 20:
            try:
                genai.configure(api_key=gemini_key)
                self.gemini_model = genai.GenerativeModel('gemini-1.5-pro')
                self.gemini_available = True
                logger.info("Gemini client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
                self.gemini_available = False
        else:
            logger.warning("Gemini API key not found or invalid")
    
    def _get_cache_key(self, task_type: TaskType, **kwargs) -> str:
        """Generate cache key for request"""
        key_data = f"{task_type.value}_{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_entry: Dict) -> bool:
        """Check if cache entry is still valid"""
        return time.time() - cache_entry['timestamp'] < self.cache_ttl
    
    def _get_preferred_provider(self, task_type: TaskType) -> LLMProvider:
        """Get preferred provider for task type based on availability"""
        preferences = self.provider_preferences.get(task_type, [LLMProvider.OPENAI, LLMProvider.GEMINI])
        
        for provider in preferences:
            if provider == LLMProvider.OPENAI and self.openai_available:
                return provider
            elif provider == LLMProvider.GEMINI and self.gemini_available:
                return provider
        
        # Fallback to any available provider
        if self.openai_available:
            return LLMProvider.OPENAI
        elif self.gemini_available:
            return LLMProvider.GEMINI
        else:
            return LLMProvider.FALLBACK
    
    async def _call_openai(self, prompt: str, system_prompt: str = None, max_tokens: int = 2000) -> Dict:
        """Call OpenAI API"""
        if not self.openai_available:
            raise Exception("OpenAI not available")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = await self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7
        )
        
        return {
            "content": response.choices[0].message.content,
            "tokens_used": response.usage.total_tokens if response.usage else None
        }
    
    async def _call_gemini(self, prompt: str, max_tokens: int = 2000) -> Dict:
        """Call Gemini API"""
        if not self.gemini_available:
            raise Exception("Gemini not available")
        
        # Configure generation settings
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": max_tokens,
        }
        
        response = await asyncio.to_thread(
            self.gemini_model.generate_content,
            prompt,
            generation_config=generation_config
        )
        
        return {
            "content": response.text,
            "tokens_used": None  # Gemini doesn't provide token usage in the same way
        }
    
    async def _execute_with_fallback(self, task_type: TaskType, prompt: str, system_prompt: str = None, max_tokens: int = 2000) -> LLMResponse:
        """Execute LLM request with intelligent routing and fallback"""
        start_time = time.time()
        
        # Check cache first
        cache_key = self._get_cache_key(task_type, prompt=prompt, system_prompt=system_prompt)
        if cache_key in self.cache and self._is_cache_valid(self.cache[cache_key]):
            cached_result = self.cache[cache_key]['data']
            logger.info(f"Cache hit for {task_type.value}")
            return LLMResponse(
                success=True,
                data=cached_result,
                provider=LLMProvider(self.cache[cache_key]['provider']),
                processing_time=time.time() - start_time,
                fallback_used=False
            )
        
        # Get preferred provider
        preferred_provider = self._get_preferred_provider(task_type)
        providers_to_try = [preferred_provider]
        
        # Add fallback providers
        if preferred_provider == LLMProvider.OPENAI and self.gemini_available:
            providers_to_try.append(LLMProvider.GEMINI)
        elif preferred_provider == LLMProvider.GEMINI and self.openai_available:
            providers_to_try.append(LLMProvider.OPENAI)
        
        last_error = None
        fallback_used = False
        
        for i, provider in enumerate(providers_to_try):
            if i > 0:
                fallback_used = True
                logger.warning(f"Falling back to {provider.value} for {task_type.value}")
            
            try:
                if provider == LLMProvider.OPENAI:
                    result = await self._call_openai(prompt, system_prompt, max_tokens)
                elif provider == LLMProvider.GEMINI:
                    result = await self._call_gemini(prompt, max_tokens)
                else:
                    continue
                
                # Cache successful result
                self.cache[cache_key] = {
                    'data': result['content'],
                    'provider': provider.value,
                    'timestamp': time.time()
                }
                
                return LLMResponse(
                    success=True,
                    data=result['content'],
                    provider=provider,
                    processing_time=time.time() - start_time,
                    tokens_used=result.get('tokens_used'),
                    fallback_used=fallback_used
                )
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"Error with {provider.value}: {e}")
                continue
        
        # All providers failed
        return LLMResponse(
            success=False,
            data=None,
            provider=LLMProvider.FALLBACK,
            processing_time=time.time() - start_time,
            error=last_error,
            fallback_used=True
        )
    
    async def select_optimal_segments(
        self,
        transcription: Dict[str, Any],
        scenes: List[Any],
        emotions: List[Any],
        viral_score: Dict[str, Any],
        platform: str = "youtube",
        clip_type: str = "highlight",
        max_segments: int = 3
    ) -> SegmentSelectionResult:
        """AI-powered segment selection using the best available provider"""
        
        # Prepare analysis context
        context = self._prepare_analysis_context(transcription, scenes, emotions, viral_score, platform)
        
        # Generate segment recommendations
        prompt = self._generate_segment_selection_prompt(context, platform, clip_type, max_segments)
        
        system_prompt = """You are an expert video editor and content strategist specializing in creating viral clips.
Analyze the provided video data and recommend the best segments for clip creation.
Respond with valid JSON only, no additional text."""
        
        response = await self._execute_with_fallback(
            TaskType.SEGMENT_SELECTION,
            prompt,
            system_prompt,
            max_tokens=2000
        )
        
        if not response.success:
            # Fallback to rule-based selection
            return self._fallback_segment_selection(transcription, scenes, emotions, viral_score)
        
        try:
            # Parse JSON response
            segments_data = json.loads(response.data)
            segments = []
            
            for seg in segments_data.get('segments', []):
                segments.append(ClipSegment(
                    start_time=seg['start_time'],
                    end_time=seg['end_time'],
                    duration=seg['end_time'] - seg['start_time'],
                    confidence=seg.get('confidence', 0.8),
                    virality_score=seg.get('virality_score', 0.7),
                    engagement_factors=seg.get('engagement_factors', []),
                    content_summary=seg.get('content_summary', ''),
                    platform_scores=seg.get('platform_scores', {})
                ))
            
            return SegmentSelectionResult(
                segments=segments,
                total_processing_time=response.processing_time,
                selection_strategy=f"AI-powered ({response.provider.value})",
                metadata={
                    'provider': response.provider.value,
                    'fallback_used': response.fallback_used,
                    'tokens_used': response.tokens_used,
                    'reasoning': segments_data.get('reasoning', '')
                }
            )
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse segment selection response: {e}")
            return self._fallback_segment_selection(transcription, scenes, emotions, viral_score)
    
    def _prepare_analysis_context(self, transcription, scenes, emotions, viral_score, platform):
        """Prepare analysis context for AI processing"""
        # Extract key speech segments
        speech_segments = []
        if isinstance(transcription, dict) and 'segments' in transcription:
            for segment in transcription['segments'][:10]:  # Limit to first 10 segments
                speech_segments.append({
                    'start': segment.get('start', 0),
                    'end': segment.get('end', 0),
                    'text': segment.get('text', '').strip(),
                    'confidence': segment.get('confidence', 0)
                })
        
        # Process scene data
        scene_data = []
        if scenes:
            for i, scene in enumerate(scenes[:5]):  # Limit to first 5 scenes
                scene_data.append({
                    'scene_number': i + 1,
                    'timestamp': scene.get('timestamp', 0),
                    'description': scene.get('description', ''),
                    'visual_features': scene.get('features', [])
                })
        
        # Process emotion data
        emotion_data = []
        if emotions:
            for emotion in emotions[:10]:  # Limit to first 10 emotions
                emotion_data.append({
                    'timestamp': emotion.get('timestamp', 0),
                    'emotion': emotion.get('emotion', ''),
                    'confidence': emotion.get('confidence', 0),
                    'intensity': emotion.get('intensity', 0)
                })
        
        return {
            'speech_segments': speech_segments,
            'scenes': scene_data,
            'emotions': emotion_data,
            'viral_score': viral_score,
            'platform': platform,
            'keywords': transcription.get('keywords', []) if isinstance(transcription, dict) else [],
            'full_text': transcription.get('text', '') if isinstance(transcription, dict) else '',
            'video_duration': max([s.get('end', 0) for s in speech_segments] + [0])
        }
    
    def _generate_segment_selection_prompt(self, context, platform, clip_type, max_segments):
        """Generate prompt for segment selection"""
        return f"""Analyze this video content and recommend the best {max_segments} segments for {clip_type} clips on {platform}.

Video Analysis Data:
- Duration: {context['video_duration']:.1f} seconds
- Platform: {platform}
- Clip Type: {clip_type}

Speech Segments:
{json.dumps(context['speech_segments'], indent=2)}

Scene Information:
{json.dumps(context['scenes'], indent=2)}

Emotion Analysis:
{json.dumps(context['emotions'], indent=2)}

Viral Score Data:
{json.dumps(context['viral_score'], indent=2)}

Platform Guidelines for {platform}:
- Optimal length: 15-60 seconds
- Hook within first 3 seconds
- High engagement moments
- Clear narrative arc
- Strong emotional impact

Respond with JSON in this exact format:
{{
  "segments": [
    {{
      "start_time": 0.0,
      "end_time": 30.0,
      "confidence": 0.9,
      "virality_score": 0.8,
      "engagement_factors": ["strong_hook", "emotional_peak"],
      "content_summary": "Brief description",
      "platform_scores": {{
        "youtube": 0.9,
        "tiktok": 0.7,
        "instagram": 0.8
      }}
    }}
  ],
  "reasoning": "Explanation of selection criteria"
}}"""
    
    def _fallback_segment_selection(self, transcription, scenes, emotions, viral_score):
        """Fallback segment selection when AI is not available"""
        # Simple rule-based selection
        segments = []
        
        # Create a basic segment from the middle of the video
        if isinstance(transcription, dict) and 'segments' in transcription:
            total_duration = max([s.get('end', 0) for s in transcription['segments']] + [30])
            
            # Select middle segment
            start_time = max(0, total_duration * 0.3)
            end_time = min(total_duration, start_time + 30)
            
            segments.append(ClipSegment(
                start_time=start_time,
                end_time=end_time,
                virality_score=0.5,
                content_summary="Auto-selected segment",
                keywords=["fallback"],
                duration=end_time - start_time,
                confidence=0.6,
                engagement_factors=["fallback_selection"],
                platform_suitability={"youtube": 0.5, "tiktok": 0.5, "instagram": 0.5}
            ))
        
        return SegmentSelectionResult(
            segments=segments,
            total_processing_time=0.1,
            selection_strategy="Rule-based fallback",
            metadata={
                'provider': 'fallback',
                'fallback_used': True,
                'fallback_reason': 'AI services unavailable'
            }
        )
    
    async def analyze_virality(
        self,
        transcript: Dict[str, Any],
        video_features: Dict[str, Any]
    ) -> List[ViralityScore]:
        """Analyze video content for viral potential"""
        
        prompt = self._generate_virality_analysis_prompt(transcript, video_features)
        
        response = await self._execute_with_fallback(
            TaskType.VIRALITY_ANALYSIS,
            prompt,
            max_tokens=1500
        )
        
        if not response.success:
            return self._fallback_virality_analysis()
        
        try:
            # Parse the response
            scores_data = json.loads(response.data)
            
            virality_scores = []
            for score_data in scores_data:
                virality_scores.append(ViralityScore(
                    niche=score_data['niche'],
                    score=float(score_data['score']),
                    explanation=score_data['explanation']
                ))
            
            return virality_scores
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse virality analysis response: {e}")
            return self._fallback_virality_analysis()
    
    def _generate_virality_analysis_prompt(self, transcript, video_features):
        """Generate prompt for virality analysis"""
        return f"""Analyze this video content for viral potential across different niches.

Transcript Data:
{json.dumps(transcript, indent=2)}

Video Features:
{json.dumps(video_features, indent=2)}

Analyze the viral potential for these niches:
1. Entertainment/Comedy
2. Educational/Tutorial
3. Lifestyle/Vlog
4. Technology/Review
5. Sports/Fitness

For each niche, provide a score from 0.0 to 1.0 and detailed explanation.

Respond with JSON array in this exact format:
[
  {{
    "niche": "Entertainment/Comedy",
    "score": 0.8,
    "explanation": "Detailed explanation of why this content fits this niche and its viral potential"
  }},
  {{
    "niche": "Educational/Tutorial",
    "score": 0.6,
    "explanation": "Detailed explanation for educational value and viral potential"
  }}
]"""
    
    def _fallback_virality_analysis(self):
        """Fallback virality analysis"""
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
    
    async def generate_hashtags(
        self,
        transcript: Dict[str, Any],
        niches: List[str],
        platform: str = "instagram"
    ) -> List[Hashtag]:
        """Generate relevant hashtags for the content"""
        
        prompt = f"""Generate relevant hashtags for this video content on {platform}.

Transcript: {json.dumps(transcript, indent=2)}
Niches: {niches}
Platform: {platform}

Generate 10-15 hashtags that are:
1. Relevant to the content
2. Popular on {platform}
3. Mix of broad and niche-specific tags
4. Trending when possible

Respond with JSON: {{"hashtags": [{{"tag": "#example", "platform": "{platform}", "relevance_score": 0.9}}]}}"""
        
        response = await self._execute_with_fallback(
            TaskType.HASHTAG_GENERATION,
            prompt,
            max_tokens=800
        )
        
        if not response.success:
            return self._fallback_hashtags(niches, platform)
        
        try:
            hashtag_data = json.loads(response.data)
            hashtags = []
            
            for tag_info in hashtag_data.get('hashtags', []):
                hashtags.append(Hashtag(
                    tag=tag_info['tag'],
                    platform=tag_info['platform'],
                    relevance_score=tag_info.get('relevance_score', 0.7)
                ))
            
            return hashtags
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse hashtag response: {e}")
            return self._fallback_hashtags(niches, platform)
    
    def _fallback_hashtags(self, niches, platform="instagram"):
        """Fallback hashtag generation"""
        basic_tags = ["#viral", "#content", "#video", "#trending"]
        
        # Clean niche names for hashtag formatting
        niche_tags = []
        for niche in niches[:3]:
            # Remove special characters and spaces, keep only alphanumeric
            clean_niche = ''.join(c for c in niche.lower() if c.isalnum())
            if clean_niche:  # Only add if there's content left
                niche_tags.append(f"#{clean_niche}")
        
        hashtags = []
        for tag in basic_tags + niche_tags:
            hashtags.append(Hashtag(
                tag=tag,
                platform=platform,
                relevance_score=0.5
            ))
        
        return hashtags
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_entries = len(self.cache)
        valid_entries = sum(1 for entry in self.cache.values() if self._is_cache_valid(entry))
        
        return {
            'total_entries': total_entries,
            'valid_entries': valid_entries,
            'expired_entries': total_entries - valid_entries,
            'cache_ttl_seconds': self.cache_ttl,
            'providers_available': {
                'openai': self.openai_available,
                'gemini': self.gemini_available
            }
        }
    
    async def generate_posting_recommendations(
        self,
        transcript: Dict[str, Any],
        niches: List[str],
        platform: str = "youtube"
    ) -> List[PostingRecommendation]:
        """Generate posting recommendations for the content"""
        
        prompt = f"""Generate posting recommendations for this video content on {platform}.

Transcript: {json.dumps(transcript, indent=2)}
Niches: {niches}
Platform: {platform}

Provide recommendations for:
1. Best posting times
2. Optimal video format/aspect ratio
3. Title suggestions
4. Description strategies
5. Engagement tactics

Respond with JSON: {{"recommendations": [{{"platform": "{platform}", "optimal_times": ["7:00 PM", "9:00 PM"], "format_suggestions": {{"title": "Engaging title", "description": "Detailed description"}}}}]}}"""
        
        response = await self._execute_with_fallback(
            TaskType.POSTING_RECOMMENDATIONS,
            prompt,
            max_tokens=1000
        )
        
        if not response.success:
            return self._fallback_posting_recommendations(platform)
        
        try:
            rec_data = json.loads(response.data)
            recommendations = []
            
            for rec_info in rec_data.get('recommendations', []):
                recommendations.append(PostingRecommendation(
                    platform=rec_info['platform'],
                    optimal_times=rec_info['optimal_times'],
                    format_suggestions=rec_info['format_suggestions']
                ))
            
            return recommendations
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse posting recommendations: {e}")
            return self._fallback_posting_recommendations(platform)
    
    def _fallback_posting_recommendations(self, platform):
        """Fallback posting recommendations"""
        return [
            PostingRecommendation(
                platform=platform,
                optimal_times=["7:00 PM", "9:00 PM", "12:00 PM"],
                format_suggestions={
                    "title": "Create engaging, descriptive titles",
                    "description": "Include relevant keywords and call-to-action",
                    "thumbnail": "Use bright, high-contrast thumbnails",
                    "hashtags": "Use 5-10 relevant hashtags"
                }
            )
        ]
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get current service status"""
        return {
            "openai_available": self.openai_available,
            "gemini_available": self.gemini_available,
            "cache_size": len(self.cache),
            "provider_preferences": {k.value: [p.value for p in v] for k, v in self.provider_preferences.items()}
        }
    
    def clear_cache(self):
        """Clear the response cache"""
        self.cache.clear()
        logger.info("LLM response cache cleared")

# Global instance
_unified_llm_service = None

def get_unified_llm_service() -> UnifiedLLMService:
    """Get unified LLM service instance with lazy initialization"""
    global _unified_llm_service
    if _unified_llm_service is None:
        _unified_llm_service = UnifiedLLMService()
    return _unified_llm_service

# Export the service instance
unified_llm_service = get_unified_llm_service()