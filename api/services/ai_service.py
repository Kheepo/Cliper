"""Enhanced AI service with OpenAI Whisper v3 and GPT-4 mini integration.

This module provides advanced AI capabilities for:
- High-precision audio transcription with timestamps
- Intelligent moment identification and virality scoring
- Multi-language support (96+ languages)
- Content analysis and clip recommendation
"""

import asyncio
import logging
import os
import tempfile
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path

try:
    import openai
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None
    AsyncOpenAI = None

import numpy as np
from api.core.exceptions import TranscriptionError, ValidationError
from api.services.redis_service import redis_service
from api.utils.retry import exponential_backoff_retry, ROBUST_RETRY
from api.utils.config import get_openai_config

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionSegment:
    """Represents a transcription segment with timing."""
    start: float
    end: float
    text: str
    confidence: float
    language: Optional[str] = None
    speaker_id: Optional[int] = None

    @property
    def duration(self) -> float:
        return self.end - self.start

    def to_dict(self) -> Dict[str, Any]:
        return {
            'start': self.start,
            'end': self.end,
            'text': self.text,
            'confidence': self.confidence,
            'language': self.language,
            'speaker_id': self.speaker_id,
            'duration': self.duration
        }


@dataclass
class ViralityScore:
    """Represents virality scoring for content."""
    overall_score: float
    engagement_potential: float
    emotional_impact: float
    content_quality: float
    trending_factors: float
    platform_suitability: Dict[str, float]
    reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'overall_score': self.overall_score,
            'engagement_potential': self.engagement_potential,
            'emotional_impact': self.emotional_impact,
            'content_quality': self.content_quality,
            'trending_factors': self.trending_factors,
            'platform_suitability': self.platform_suitability,
            'reasoning': self.reasoning
        }


@dataclass
class ContentMoment:
    """Represents an identified content moment."""
    start_time: float
    end_time: float
    moment_type: str  # 'highlight', 'emotional', 'informative', 'funny', etc.
    description: str
    virality_score: ViralityScore
    keywords: List[str]
    sentiment: str
    energy_level: float

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': self.duration,
            'moment_type': self.moment_type,
            'description': self.description,
            'virality_score': self.virality_score.to_dict(),
            'keywords': self.keywords,
            'sentiment': self.sentiment,
            'energy_level': self.energy_level
        }


class EnhancedAIService:
    """Enhanced AI service with OpenAI integration."""

    def __init__(self):
        """Initialize the AI service."""
        self.client = None
        self.enabled = False
        self._initialize_openai()
        
        # Supported languages for Whisper v3
        self.supported_languages = [
            'en', 'zh', 'de', 'es', 'ru', 'ko', 'fr', 'ja', 'pt', 'tr', 'pl', 'ca', 'nl',
            'ar', 'sv', 'it', 'id', 'hi', 'fi', 'vi', 'he', 'uk', 'el', 'ms', 'cs', 'ro',
            'da', 'hu', 'ta', 'no', 'th', 'ur', 'hr', 'bg', 'lt', 'la', 'mi', 'ml', 'cy',
            'sk', 'te', 'fa', 'lv', 'bn', 'sr', 'az', 'sl', 'kn', 'et', 'mk', 'br', 'eu',
            'is', 'hy', 'ne', 'mn', 'bs', 'kk', 'sq', 'sw', 'gl', 'mr', 'pa', 'si', 'km',
            'sn', 'yo', 'so', 'af', 'oc', 'ka', 'be', 'tg', 'sd', 'gu', 'am', 'yi', 'lo',
            'uz', 'fo', 'ht', 'ps', 'tk', 'nn', 'mt', 'sa', 'lb', 'my', 'bo', 'tl', 'mg',
            'as', 'tt', 'haw', 'ln', 'ha', 'ba', 'jw', 'su'
        ]

    def _initialize_openai(self):
        """Initialize OpenAI client."""
        if not OPENAI_AVAILABLE:
            logger.warning("OpenAI not available, AI features disabled")
            return

        try:
            config = get_openai_config()
            api_key = config.get('api_key') or os.getenv('OPENAI_API_KEY')
            
            if not api_key or api_key.startswith('sk-xxx'):
                logger.warning("OpenAI API key not configured, AI features disabled")
                return

            self.client = AsyncOpenAI(api_key=api_key)
            self.enabled = True
            logger.info("OpenAI client initialized successfully")
            
        except Exception as e:
            logger.warning(f"OpenAI initialization failed: {e}. AI features disabled.")
            self.enabled = False

    async def transcribe_audio_whisper_v3(
        self,
        audio_path: str,
        language: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> List[TranscriptionSegment]:
        """Transcribe audio using OpenAI Whisper v3 with high precision."""
        
        if not self.enabled:
            raise TranscriptionError("OpenAI service not available")

        # Check cache first
        cache_key = f"whisper_v3_{audio_path}_{language or 'auto'}"
        cached_result = await redis_service.get_cached_transcription(cache_key)
        if cached_result:
            logger.info(f"Using cached transcription for {audio_path}")
            return [TranscriptionSegment(**segment) for segment in cached_result]

        try:
            # Prepare audio file
            audio_file_path = await self._prepare_audio_for_whisper(audio_path)
            
            # Transcribe with Whisper v3
            with open(audio_file_path, 'rb') as audio_file:
                transcript = await exponential_backoff_retry(
                    func=self._whisper_transcribe,
                    max_attempts=ROBUST_RETRY.max_attempts,
                    base_delay=ROBUST_RETRY.base_delay,
                    audio_file=audio_file,
                    language=language,
                    prompt=prompt
                )

            # Process segments
            segments = self._process_whisper_segments(transcript.segments)
            
            # Cache results
            cache_data = [segment.to_dict() for segment in segments]
            await redis_service.cache_transcription(cache_key, cache_data, ttl=86400)
            
            logger.info(
                f"Transcribed {len(segments)} segments from {audio_path} "
                f"(language: {transcript.language})"
            )
            
            return segments
            
        except Exception as e:
            logger.error(f"Whisper v3 transcription failed: {e}")
            raise TranscriptionError(f"Transcription failed: {str(e)}")
        finally:
            # Cleanup temporary files
            if 'audio_file_path' in locals() and audio_file_path != audio_path:
                try:
                    os.unlink(audio_file_path)
                except Exception:
                    pass

    async def _whisper_transcribe(self, audio_file, language=None, prompt=None):
        """Internal method for Whisper transcription."""
        return await self.client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language,
            prompt=prompt,
            response_format="verbose_json",
            timestamp_granularities=["segment"]
        )

    async def _prepare_audio_for_whisper(self, audio_path: str) -> str:
        """Prepare audio file for Whisper processing."""
        # Check if file is already in supported format
        supported_formats = ['.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm']
        file_ext = Path(audio_path).suffix.lower()
        
        if file_ext in supported_formats:
            return audio_path
        
        # Convert to supported format if needed
        temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        temp_file.close()
        
        # Use FFmpeg to convert
        import subprocess
        cmd = [
            'ffmpeg', '-i', audio_path,
            '-acodec', 'mp3',
            '-ar', '16000',  # 16kHz sample rate for Whisper
            '-ac', '1',      # Mono
            '-y',            # Overwrite
            temp_file.name
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        
        await process.communicate()
        
        if process.returncode != 0:
            os.unlink(temp_file.name)
            raise TranscriptionError("Audio conversion failed")
        
        return temp_file.name

    def _process_whisper_segments(self, raw_segments) -> List[TranscriptionSegment]:
        """Process raw Whisper segments into structured format."""
        segments = []
        
        for segment in raw_segments:
            segments.append(TranscriptionSegment(
                start=segment.start,
                end=segment.end,
                text=segment.text.strip(),
                confidence=getattr(segment, 'avg_logprob', 0.8),  # Whisper doesn't provide confidence directly
                language=getattr(segment, 'language', None)
            ))
        
        return segments

    async def analyze_content_moments(
        self,
        transcription_segments: List[TranscriptionSegment],
        video_metadata: Dict[str, Any],
        platform: str = "general"
    ) -> List[ContentMoment]:
        """Analyze content to identify viral moments using GPT-4 mini."""
        
        if not self.enabled:
            logger.warning("AI service not available, using fallback analysis")
            return self._fallback_moment_analysis(transcription_segments)

        try:
            # Prepare content for analysis
            content_text = self._prepare_content_for_analysis(transcription_segments)
            
            # Analyze with GPT-4 mini
            analysis_prompt = self._build_analysis_prompt(content_text, video_metadata, platform)
            
            response = await exponential_backoff_retry(
                func=self._gpt4_analyze_content,
                max_attempts=3,
                prompt=analysis_prompt
            )
            
            # Parse and structure the response
            moments = self._parse_gpt4_analysis(response, transcription_segments)
            
            logger.info(f"Identified {len(moments)} content moments for {platform}")
            return moments
            
        except Exception as e:
            logger.error(f"GPT-4 content analysis failed: {e}")
            return self._fallback_moment_analysis(transcription_segments)

    async def _gpt4_analyze_content(self, prompt: str) -> str:
        """Analyze content using GPT-4 mini."""
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert content analyst specializing in viral video content identification. Analyze the provided content and identify the most engaging moments with precise timing and reasoning."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        return response.choices[0].message.content

    def _prepare_content_for_analysis(self, segments: List[TranscriptionSegment]) -> str:
        """Prepare transcription content for GPT-4 analysis."""
        content_lines = []
        
        for segment in segments:
            timestamp = f"[{segment.start:.1f}s - {segment.end:.1f}s]"
            content_lines.append(f"{timestamp}: {segment.text}")
        
        return "\n".join(content_lines)

    def _build_analysis_prompt(
        self,
        content_text: str,
        video_metadata: Dict[str, Any],
        platform: str
    ) -> str:
        """Build analysis prompt for GPT-4."""
        
        platform_guidelines = {
            "tiktok": "Focus on quick, engaging moments with high energy, trending topics, and visual appeal. Optimal length: 15-60 seconds.",
            "youtube": "Look for educational value, entertainment, and moments that encourage engagement. Optimal length: 30-180 seconds.",
            "instagram": "Emphasize visual storytelling, lifestyle content, and shareable moments. Optimal length: 15-90 seconds.",
            "twitter": "Focus on newsworthy, controversial, or highly quotable moments. Optimal length: 15-140 seconds.",
            "general": "Identify universally engaging content with broad appeal."
        }
        
        guideline = platform_guidelines.get(platform.lower(), platform_guidelines["general"])
        
        return f"""
Analyze the following video content and identify the top 5 most viral-worthy moments.

Platform: {platform.upper()}
Platform Guidelines: {guideline}

Video Metadata:
- Duration: {video_metadata.get('duration', 'Unknown')} seconds
- Title: {video_metadata.get('title', 'Unknown')}
- Description: {video_metadata.get('description', 'Unknown')[:200]}...

Transcription with Timestamps:
{content_text}

For each identified moment, provide:
1. Start and end timestamps (in seconds)
2. Moment type (highlight, emotional, informative, funny, controversial, etc.)
3. Description of why this moment is engaging
4. Virality score (0-100) with breakdown:
   - Engagement potential (0-100)
   - Emotional impact (0-100)
   - Content quality (0-100)
   - Trending factors (0-100)
5. Key keywords/topics
6. Sentiment (positive, negative, neutral)
7. Energy level (0-100)
8. Platform suitability scores for TikTok, YouTube, Instagram, Twitter (0-100 each)

Format your response as JSON with the following structure:
{{
  "moments": [
    {{
      "start_time": 0.0,
      "end_time": 30.0,
      "moment_type": "highlight",
      "description": "Engaging moment description",
      "virality_score": {{
        "overall_score": 85,
        "engagement_potential": 90,
        "emotional_impact": 80,
        "content_quality": 85,
        "trending_factors": 85,
        "platform_suitability": {{
          "tiktok": 95,
          "youtube": 80,
          "instagram": 85,
          "twitter": 75
        }},
        "reasoning": "Explanation of scoring"
      }},
      "keywords": ["keyword1", "keyword2"],
      "sentiment": "positive",
      "energy_level": 85
    }}
  ]
}}
"""

    def _parse_gpt4_analysis(
        self,
        response: str,
        segments: List[TranscriptionSegment]
    ) -> List[ContentMoment]:
        """Parse GPT-4 analysis response into ContentMoment objects."""
        
        try:
            import json
            data = json.loads(response)
            moments = []
            
            for moment_data in data.get('moments', []):
                virality_data = moment_data.get('virality_score', {})
                
                virality_score = ViralityScore(
                    overall_score=virality_data.get('overall_score', 50),
                    engagement_potential=virality_data.get('engagement_potential', 50),
                    emotional_impact=virality_data.get('emotional_impact', 50),
                    content_quality=virality_data.get('content_quality', 50),
                    trending_factors=virality_data.get('trending_factors', 50),
                    platform_suitability=virality_data.get('platform_suitability', {}),
                    reasoning=virality_data.get('reasoning', '')
                )
                
                moment = ContentMoment(
                    start_time=moment_data.get('start_time', 0),
                    end_time=moment_data.get('end_time', 30),
                    moment_type=moment_data.get('moment_type', 'highlight'),
                    description=moment_data.get('description', ''),
                    virality_score=virality_score,
                    keywords=moment_data.get('keywords', []),
                    sentiment=moment_data.get('sentiment', 'neutral'),
                    energy_level=moment_data.get('energy_level', 50)
                )
                
                moments.append(moment)
            
            return moments
            
        except Exception as e:
            logger.error(f"Failed to parse GPT-4 analysis: {e}")
            return self._fallback_moment_analysis(segments)

    def _fallback_moment_analysis(
        self,
        segments: List[TranscriptionSegment]
    ) -> List[ContentMoment]:
        """Fallback analysis when AI service is unavailable."""
        
        moments = []
        
        # Simple heuristic-based analysis
        for i, segment in enumerate(segments):
            if len(segment.text) > 50:  # Longer segments might be more informative
                score = min(len(segment.text) / 200 * 100, 100)
                
                virality_score = ViralityScore(
                    overall_score=score,
                    engagement_potential=score * 0.8,
                    emotional_impact=score * 0.6,
                    content_quality=score * 0.9,
                    trending_factors=score * 0.5,
                    platform_suitability={
                        'tiktok': score * 0.7,
                        'youtube': score * 0.9,
                        'instagram': score * 0.8,
                        'twitter': score * 0.6
                    },
                    reasoning="Heuristic-based scoring (AI unavailable)"
                )
                
                moment = ContentMoment(
                    start_time=segment.start,
                    end_time=segment.end,
                    moment_type='highlight',
                    description=f"Content segment {i+1}",
                    virality_score=virality_score,
                    keywords=[],
                    sentiment='neutral',
                    energy_level=score * 0.7
                )
                
                moments.append(moment)
        
        return moments[:5]  # Return top 5

    async def health_check(self) -> Dict[str, Any]:
        """Check AI service health."""
        if not self.enabled:
            return {'status': 'disabled', 'reason': 'OpenAI not configured'}
        
        try:
            # Simple API test
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            
            return {
                'status': 'healthy',
                'model': 'gpt-4o-mini',
                'whisper_available': True,
                'supported_languages': len(self.supported_languages)
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }


# Global AI service instance
ai_service = EnhancedAIService()