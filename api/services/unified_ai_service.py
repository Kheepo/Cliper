"""
Unified AI Service for Cliper
Consolidates all AI functionality into a single, robust service
"""

import asyncio
import logging
import os
import json
import tempfile
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import numpy as np

try:
    import openai
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None
    AsyncOpenAI = None

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionSegment:
    """Represents a transcription segment with timing."""
    start: float
    end: float
    text: str
    confidence: float
    language: Optional[str] = None

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
            'duration': self.duration
        }


@dataclass
class ViralityScore:
    """Represents virality scoring for content."""
    start_time: float
    end_time: float
    overall_score: float
    engagement_potential: float
    emotional_impact: float
    content_quality: float
    trending_factors: float
    platform_suitability: Dict[str, float]
    reasoning: str
    keywords: List[str]
    moment_type: str
    energy_level: float

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': self.duration,
            'overall_score': self.overall_score,
            'engagement_potential': self.engagement_potential,
            'emotional_impact': self.emotional_impact,
            'content_quality': self.content_quality,
            'trending_factors': self.trending_factors,
            'platform_suitability': self.platform_suitability,
            'reasoning': self.reasoning,
            'keywords': self.keywords,
            'moment_type': self.moment_type,
            'energy_level': self.energy_level
        }


@dataclass
class ClipSegment:
    """Represents a recommended clip segment."""
    start_time: float
    end_time: float
    virality_score: ViralityScore
    recommended_duration: float
    platform_optimizations: Dict[str, Dict[str, Any]]
    title_suggestions: List[str]
    hashtags: List[str]
    description: str

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': self.duration,
            'virality_score': self.virality_score.to_dict(),
            'recommended_duration': self.recommended_duration,
            'platform_optimizations': self.platform_optimizations,
            'title_suggestions': self.title_suggestions,
            'hashtags': self.hashtags,
            'description': self.description
        }


class UnifiedAIService:
    """Unified AI service that consolidates all AI functionality."""

    def __init__(self):
        """Initialize the unified AI service."""
        self.client = None
        self.enabled = False
        self.model = 'gpt-4o-mini'
        self._initialize_openai()
        
        # Platform specifications
        self.platform_specs = {
            'tiktok': {
                'max_duration': 60,
                'min_duration': 15,
                'aspect_ratio': '9:16',
                'resolution': '1080x1920',
                'optimal_duration': 30,
                'engagement_factors': ['hook', 'trending', 'visual_appeal']
            },
            'youtube': {
                'max_duration': 60,
                'min_duration': 15,
                'aspect_ratio': '16:9',
                'resolution': '1920x1080',
                'optimal_duration': 45,
                'engagement_factors': ['educational', 'entertainment', 'retention']
            },
            'instagram': {
                'max_duration': 90,
                'min_duration': 15,
                'aspect_ratio': '9:16',
                'resolution': '1080x1920',
                'optimal_duration': 30,
                'engagement_factors': ['aesthetic', 'lifestyle', 'shareable']
            },
            'twitter': {
                'max_duration': 140,
                'min_duration': 10,
                'aspect_ratio': '16:9',
                'resolution': '1280x720',
                'optimal_duration': 30,
                'engagement_factors': ['newsworthy', 'controversial', 'quotable']
            }
        }

    def _initialize_openai(self):
        """Initialize OpenAI client."""
        if not OPENAI_AVAILABLE:
            logger.warning("OpenAI not available, AI features disabled")
            return

        try:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key or api_key.startswith('sk-xxx'):
                logger.warning("OpenAI API key not configured, AI features disabled")
                return

            self.client = AsyncOpenAI(api_key=api_key)
            self.enabled = True
            logger.info("OpenAI client initialized successfully")
            
        except Exception as e:
            logger.warning(f"OpenAI initialization failed: {e}. AI features disabled.")
            self.enabled = False

    async def transcribe_audio(self, audio_path: str, language: Optional[str] = None) -> List[TranscriptionSegment]:
        """Transcribe audio using OpenAI Whisper."""
        
        if not self.enabled:
            logger.warning("AI service not available, using fallback transcription")
            return self._fallback_transcription()

        try:
            # Prepare audio file for Whisper
            audio_file_path = await self._prepare_audio_for_whisper(audio_path)
            
            with open(audio_file_path, 'rb') as audio_file:
                transcript = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )

            # Process segments
            segments = []
            for segment in transcript.segments:
                segments.append(TranscriptionSegment(
                    start=segment.start,
                    end=segment.end,
                    text=segment.text.strip(),
                    confidence=getattr(segment, 'avg_logprob', 0.8),
                    language=transcript.language
                ))
            
            logger.info(f"Transcribed {len(segments)} segments from {audio_path}")
            return segments
            
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return self._fallback_transcription()
        finally:
            # Cleanup temporary files
            if 'audio_file_path' in locals() and audio_file_path != audio_path:
                try:
                    os.unlink(audio_file_path)
                except Exception:
                    pass

    async def analyze_virality(
        self,
        transcription_segments: List[TranscriptionSegment],
        video_metadata: Dict[str, Any],
        target_platforms: List[str] = None
    ) -> List[ViralityScore]:
        """Analyze content for viral potential."""
        
        if not self.enabled:
            logger.warning("AI service not available, using fallback analysis")
            return self._fallback_virality_analysis(transcription_segments)

        if target_platforms is None:
            target_platforms = ['general']

        try:
            # Prepare content for analysis
            content_text = self._prepare_content_for_analysis(transcription_segments)
            
            # Analyze with GPT-4
            analysis_prompt = self._build_virality_analysis_prompt(
                content_text, video_metadata, target_platforms
            )
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert content analyst specializing in viral video content identification. Analyze the provided content and identify the most engaging moments with precise timing and reasoning."
                    },
                    {
                        "role": "user",
                        "content": analysis_prompt
                    }
                ],
                temperature=0.3,
                max_tokens=3000,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            result = json.loads(response.choices[0].message.content)
            return self._parse_virality_response(result, transcription_segments)
            
        except Exception as e:
            logger.error(f"Virality analysis failed: {e}")
            return self._fallback_virality_analysis(transcription_segments)

    async def generate_clip_segments(
        self,
        transcription_segments: List[TranscriptionSegment],
        virality_scores: List[ViralityScore],
        video_metadata: Dict[str, Any],
        target_platforms: List[str],
        max_clips: int = 5
    ) -> List[ClipSegment]:
        """Generate optimized clip segments based on virality analysis."""
        
        if not self.enabled:
            logger.warning("AI service not available, using fallback segment generation")
            return self._fallback_clip_segments(virality_scores, target_platforms, max_clips)

        try:
            # Prepare content for clip generation
            content_text = self._prepare_content_for_analysis(transcription_segments)
            virality_data = [score.to_dict() for score in virality_scores]
            
            # Generate clip segments
            clip_prompt = self._build_clip_generation_prompt(
                content_text, virality_data, video_metadata, target_platforms, max_clips
            )
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert video editor specializing in creating viral short-form content. Generate optimized clip segments based on virality analysis."
                    },
                    {
                        "role": "user",
                        "content": clip_prompt
                    }
                ],
                temperature=0.4,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            result = json.loads(response.choices[0].message.content)
            return self._parse_clip_segments_response(result, virality_scores)
            
        except Exception as e:
            logger.error(f"Clip segment generation failed: {e}")
            return self._fallback_clip_segments(virality_scores, target_platforms, max_clips)

    async def generate_hashtags(
        self,
        content_description: str,
        platform: str,
        content_type: str = "general"
    ) -> List[str]:
        """Generate relevant hashtags for content."""
        
        if not self.enabled:
            logger.warning("AI service not available, using fallback hashtags")
            return self._fallback_hashtags(content_description, platform)

        try:
            prompt = f"""
Generate 10-15 relevant hashtags for this content on {platform}:

Content Description: {content_description}
Platform: {platform}
Content Type: {content_type}

Consider:
- Platform-specific hashtag conventions
- Trending topics
- Content relevance
- Character limits
- Engagement potential

Return as JSON array of strings:
["#hashtag1", "#hashtag2", ...]
"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a social media expert specializing in hashtag optimization for viral content."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.5,
                max_tokens=500
            )
            
            # Parse response
            hashtags_text = response.choices[0].message.content.strip()
            if hashtags_text.startswith('[') and hashtags_text.endswith(']'):
                hashtags = json.loads(hashtags_text)
                return hashtags[:15]  # Limit to 15 hashtags
            
            # Fallback parsing
            hashtags = []
            for line in hashtags_text.split('\n'):
                line = line.strip()
                if line.startswith('#'):
                    hashtags.append(line)
            
            return hashtags[:15]
            
        except Exception as e:
            logger.error(f"Hashtag generation failed: {e}")
            return self._fallback_hashtags(content_description, platform)

    def _prepare_audio_for_whisper(self, audio_path: str) -> str:
        """Prepare audio file for Whisper processing."""
        # Check if file is already in supported format
        supported_formats = ['.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm']
        file_ext = os.path.splitext(audio_path)[1].lower()
        
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
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return temp_file.name
        except subprocess.CalledProcessError:
            os.unlink(temp_file.name)
            raise Exception("Audio conversion failed")

    def _prepare_content_for_analysis(self, segments: List[TranscriptionSegment]) -> str:
        """Prepare transcription content for analysis."""
        content_lines = []
        
        for segment in segments:
            timestamp = f"[{segment.start:.1f}s - {segment.end:.1f}s]"
            content_lines.append(f"{timestamp}: {segment.text}")
        
        return "\n".join(content_lines)

    def _build_virality_analysis_prompt(
        self,
        content_text: str,
        video_metadata: Dict[str, Any],
        target_platforms: List[str]
    ) -> str:
        """Build virality analysis prompt."""
        
        platform_info = []
        for platform in target_platforms:
            if platform in self.platform_specs:
                spec = self.platform_specs[platform]
                platform_info.append(f"- {platform.upper()}: {spec['optimal_duration']}s optimal, {spec['aspect_ratio']} aspect ratio")
        
        return f"""
Analyze the following video content and identify the top 5 most viral-worthy moments.

VIDEO METADATA:
- Duration: {video_metadata.get('duration', 'Unknown')} seconds
- Title: {video_metadata.get('title', 'Unknown')}

TARGET PLATFORMS:
{chr(10).join(platform_info)}

TRANSCRIPTION WITH TIMESTAMPS:
{content_text}

For each identified moment, provide:
1. Start and end timestamps (in seconds)
2. Moment type (hook, climax, insight, emotional, funny, controversial, etc.)
3. Virality score breakdown (0-100 for each):
   - Overall score
   - Engagement potential
   - Emotional impact
   - Content quality
   - Trending factors
   - Platform suitability scores for each target platform
4. Reasoning for the score
5. Key keywords/topics
6. Energy level (0-100)

Format your response as JSON:
{{
  "moments": [
    {{
      "start_time": 0.0,
      "end_time": 30.0,
      "moment_type": "hook",
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
      "reasoning": "Strong opening hook with trending topic",
      "keywords": ["keyword1", "keyword2"],
      "energy_level": 85
    }}
  ]
}}

Focus on segments with overall_score >= 70. Provide specific, actionable reasoning for each score.
"""

    def _build_clip_generation_prompt(
        self,
        content_text: str,
        virality_data: List[Dict[str, Any]],
        video_metadata: Dict[str, Any],
        target_platforms: List[str],
        max_clips: int
    ) -> str:
        """Build clip generation prompt."""
        
        return f"""
Based on the virality analysis, generate {max_clips} optimized clip segments for the target platforms.

CONTENT:
{content_text}

VIRALITY ANALYSIS:
{json.dumps(virality_data, indent=2)}

TARGET PLATFORMS: {', '.join(target_platforms)}

For each clip segment, provide:
1. Start and end timestamps
2. Recommended duration for each platform
3. Platform-specific optimizations (aspect ratio, format, etc.)
4. Title suggestions (3-5 options)
5. Relevant hashtags (5-10)
6. Description/summary

Format your response as JSON:
{{
  "clips": [
    {{
      "start_time": 0.0,
      "end_time": 30.0,
      "recommended_duration": 30.0,
      "platform_optimizations": {{
        "tiktok": {{"duration": 30, "aspect_ratio": "9:16", "format": "mp4"}},
        "youtube": {{"duration": 45, "aspect_ratio": "16:9", "format": "mp4"}}
      }},
      "title_suggestions": ["Title 1", "Title 2", "Title 3"],
      "hashtags": ["#hashtag1", "#hashtag2"],
      "description": "Clip description"
    }}
  ]
}}
"""

    def _parse_virality_response(
        self,
        response: Dict[str, Any],
        segments: List[TranscriptionSegment]
    ) -> List[ViralityScore]:
        """Parse virality analysis response."""
        
        try:
            scores = []
            moments = response.get('moments', [])
            
            for moment in moments:
                score = ViralityScore(
                    start_time=float(moment['start_time']),
                    end_time=float(moment['end_time']),
                    overall_score=float(moment['overall_score']),
                    engagement_potential=float(moment['engagement_potential']),
                    emotional_impact=float(moment['emotional_impact']),
                    content_quality=float(moment['content_quality']),
                    trending_factors=float(moment['trending_factors']),
                    platform_suitability=moment['platform_suitability'],
                    reasoning=moment['reasoning'],
                    keywords=moment.get('keywords', []),
                    moment_type=moment['moment_type'],
                    energy_level=float(moment['energy_level'])
                )
                scores.append(score)
            
            return scores
            
        except Exception as e:
            logger.error(f"Failed to parse virality response: {e}")
            return self._fallback_virality_analysis(segments)

    def _parse_clip_segments_response(
        self,
        response: Dict[str, Any],
        virality_scores: List[ViralityScore]
    ) -> List[ClipSegment]:
        """Parse clip segments response."""
        
        try:
            clips = []
            clip_data = response.get('clips', [])
            
            for clip_info in clip_data:
                # Find matching virality score
                matching_score = None
                for score in virality_scores:
                    if (abs(score.start_time - clip_info['start_time']) < 5 and
                        abs(score.end_time - clip_info['end_time']) < 5):
                        matching_score = score
                        break
                
                if not matching_score:
                    # Create a default virality score
                    matching_score = ViralityScore(
                        start_time=clip_info['start_time'],
                        end_time=clip_info['end_time'],
                        overall_score=70.0,
                        engagement_potential=70.0,
                        emotional_impact=70.0,
                        content_quality=70.0,
                        trending_factors=70.0,
                        platform_suitability={},
                        reasoning="Generated from clip analysis",
                        keywords=[],
                        moment_type="clip",
                        energy_level=70.0
                    )
                
                clip = ClipSegment(
                    start_time=clip_info['start_time'],
                    end_time=clip_info['end_time'],
                    virality_score=matching_score,
                    recommended_duration=clip_info['recommended_duration'],
                    platform_optimizations=clip_info['platform_optimizations'],
                    title_suggestions=clip_info['title_suggestions'],
                    hashtags=clip_info['hashtags'],
                    description=clip_info['description']
                )
                clips.append(clip)
            
            return clips
            
        except Exception as e:
            logger.error(f"Failed to parse clip segments response: {e}")
            return self._fallback_clip_segments(virality_scores, ['general'], len(clip_data))

    # Fallback methods for when AI service is unavailable
    def _fallback_transcription(self) -> List[TranscriptionSegment]:
        """Fallback transcription when AI service is unavailable."""
        return [
            TranscriptionSegment(
                start=0.0,
                end=30.0,
                text="[AI service unavailable - fallback transcription]",
                confidence=0.5,
                language="en"
            )
        ]

    def _fallback_virality_analysis(self, segments: List[TranscriptionSegment]) -> List[ViralityScore]:
        """Fallback virality analysis when AI service is unavailable."""
        scores = []
        
        for i, segment in enumerate(segments[:5]):  # Limit to 5 segments
            score = ViralityScore(
                start_time=segment.start,
                end_time=segment.end,
                overall_score=60.0 + (i * 5),  # Increasing scores
                engagement_potential=65.0,
                emotional_impact=60.0,
                content_quality=70.0,
                trending_factors=55.0,
                platform_suitability={
                    'tiktok': 65.0,
                    'youtube': 70.0,
                    'instagram': 68.0,
                    'twitter': 60.0
                },
                reasoning="Fallback analysis - AI service unavailable",
                keywords=["content", "video"],
                moment_type="highlight",
                energy_level=65.0
            )
            scores.append(score)
        
        return scores

    def _fallback_clip_segments(
        self,
        virality_scores: List[ViralityScore],
        target_platforms: List[str],
        max_clips: int
    ) -> List[ClipSegment]:
        """Fallback clip segments when AI service is unavailable."""
        clips = []
        
        for i, score in enumerate(virality_scores[:max_clips]):
            platform_optimizations = {}
            for platform in target_platforms:
                if platform in self.platform_specs:
                    spec = self.platform_specs[platform]
                    platform_optimizations[platform] = {
                        'duration': spec['optimal_duration'],
                        'aspect_ratio': spec['aspect_ratio'],
                        'resolution': spec['resolution']
                    }
            
            clip = ClipSegment(
                start_time=score.start_time,
                end_time=score.end_time,
                virality_score=score,
                recommended_duration=score.duration,
                platform_optimizations=platform_optimizations,
                title_suggestions=[
                    f"Clip {i+1}",
                    f"Highlight {i+1}",
                    f"Best Moment {i+1}"
                ],
                hashtags=["#video", "#content", "#highlight"],
                description=f"Generated clip segment {i+1}"
            )
            clips.append(clip)
        
        return clips

    def _fallback_hashtags(self, content_description: str, platform: str) -> List[str]:
        """Fallback hashtags when AI service is unavailable."""
        base_hashtags = ["#video", "#content", "#viral"]
        platform_hashtags = {
            'tiktok': ["#tiktok", "#fyp", "#trending"],
            'youtube': ["#youtube", "#shorts", "#subscribe"],
            'instagram': ["#instagram", "#reels", "#explore"],
            'twitter': ["#twitter", "#viral", "#trending"]
        }
        
        hashtags = base_hashtags + platform_hashtags.get(platform, [])
        return hashtags[:10]

    async def health_check(self) -> Dict[str, Any]:
        """Check AI service health."""
        if not self.enabled:
            return {
                'status': 'disabled',
                'reason': 'OpenAI not configured',
                'fallback_available': True
            }
        
        try:
            # Simple API test
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            
            return {
                'status': 'healthy',
                'model': self.model,
                'whisper_available': True,
                'fallback_available': True
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'fallback_available': True
            }


# Global AI service instance
unified_ai_service = UnifiedAIService()

