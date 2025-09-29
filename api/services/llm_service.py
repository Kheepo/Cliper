import asyncio
import logging
import json
import os
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import openai
from openai import AsyncOpenAI
import tiktoken
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ViralityScore:
    """Represents a virality score for a content segment."""
    start_time: float
    end_time: float
    score: float
    reasons: List[str]
    keywords: List[str]
    emotion: str
    engagement_factors: Dict[str, float]

class LLMService:
    """
    Enhanced LLM service for intelligent moment identification and virality scoring.
    Uses GPT-4 mini for cost-effective and accurate analysis.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize LLM service with OpenAI API.
        
        Args:
            api_key: OpenAI API key (uses environment variable if None)
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = 'gpt-4o-mini'  # Cost-effective model for analysis
        self.max_tokens_per_request = 4000
        self.encoding = tiktoken.encoding_for_model("gpt-4")
        
        logger.info(f"LLMService initialized with model: {self.model}")
    
    def _count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken.
        
        Args:
            text: Input text
            
        Returns:
            Number of tokens
        """
        try:
            return len(self.encoding.encode(text))
        except Exception as e:
            logger.warning(f"Error counting tokens: {e}")
            return len(text.split()) * 1.3  # Rough estimate
    
    def _chunk_transcript(self, segments: List[Dict], max_tokens: int = 3000) -> List[List[Dict]]:
        """
        Split transcript segments into chunks that fit within token limits.
        
        Args:
            segments: List of transcript segments
            max_tokens: Maximum tokens per chunk
            
        Returns:
            List of segment chunks
        """
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for segment in segments:
            segment_text = segment.get('text', '')
            segment_tokens = self._count_tokens(segment_text)
            
            if current_tokens + segment_tokens > max_tokens and current_chunk:
                chunks.append(current_chunk)
                current_chunk = [segment]
                current_tokens = segment_tokens
            else:
                current_chunk.append(segment)
                current_tokens += segment_tokens
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    async def analyze_virality(
        self,
        transcript_segments: List[Dict],
        video_metadata: Dict[str, Any],
        target_platform: str = 'general',
        content_type: str = 'general'
    ) -> List[ViralityScore]:
        """
        Analyze transcript segments for viral potential using GPT-4 mini.
        
        Args:
            transcript_segments: List of transcript segments with timestamps
            video_metadata: Video metadata (duration, title, etc.)
            target_platform: Target platform (youtube, tiktok, instagram, general)
            content_type: Content type (educational, entertainment, news, etc.)
            
        Returns:
            List of virality scores for segments
        """
        try:
            logger.info(f"Analyzing virality for {len(transcript_segments)} segments")
            
            # Chunk segments to fit within token limits
            chunks = self._chunk_transcript(transcript_segments)
            all_scores = []
            
            for i, chunk in enumerate(chunks):
                logger.info(f"Processing chunk {i+1}/{len(chunks)}")
                
                chunk_scores = await self._analyze_chunk_virality(
                    chunk, video_metadata, target_platform, content_type
                )
                all_scores.extend(chunk_scores)
                
                # Rate limiting - small delay between requests
                if i < len(chunks) - 1:
                    await asyncio.sleep(0.5)
            
            # Sort by start time and merge overlapping segments
            all_scores.sort(key=lambda x: x.start_time)
            merged_scores = self._merge_overlapping_scores(all_scores)
            
            logger.info(f"Generated {len(merged_scores)} virality scores")
            return merged_scores
            
        except Exception as e:
            logger.error(f"Error analyzing virality: {e}")
            return self._generate_fallback_scores(transcript_segments)
    
    async def _analyze_chunk_virality(
        self,
        segments: List[Dict],
        video_metadata: Dict[str, Any],
        target_platform: str,
        content_type: str
    ) -> List[ViralityScore]:
        """
        Analyze a chunk of segments for virality.
        
        Args:
            segments: Chunk of transcript segments
            video_metadata: Video metadata
            target_platform: Target platform
            content_type: Content type
            
        Returns:
            List of virality scores
        """
        try:
            # Prepare transcript text with timestamps
            transcript_text = "\n".join([
                f"[{seg.get('start', 0):.1f}s - {seg.get('end', 0):.1f}s]: {seg.get('text', '').strip()}"
                for seg in segments if seg.get('text', '').strip()
            ])
            
            if not transcript_text.strip():
                return []
            
            # Create analysis prompt
            prompt = self._create_virality_prompt(
                transcript_text, video_metadata, target_platform, content_type
            )
            
            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert content analyst specializing in viral content identification. Analyze the provided transcript and identify segments with high viral potential."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=self.max_tokens_per_request,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            result = json.loads(response.choices[0].message.content)
            return self._parse_virality_response(result, segments)
            
        except Exception as e:
            logger.error(f"Error in chunk virality analysis: {e}")
            return self._generate_fallback_scores(segments)
    
    def _create_virality_prompt(
        self,
        transcript: str,
        metadata: Dict[str, Any],
        platform: str,
        content_type: str
    ) -> str:
        """
        Create a detailed prompt for virality analysis.
        
        Args:
            transcript: Transcript text with timestamps
            metadata: Video metadata
            platform: Target platform
            content_type: Content type
            
        Returns:
            Analysis prompt
        """
        platform_guidelines = {
            'youtube': 'Focus on educational value, storytelling, and retention hooks. Optimal clip length: 30-90 seconds.',
            'tiktok': 'Prioritize quick hooks, trending topics, and visual appeal. Optimal clip length: 15-60 seconds.',
            'instagram': 'Emphasize aesthetic appeal, lifestyle content, and engagement. Optimal clip length: 15-90 seconds.',
            'general': 'Balance entertainment, information, and engagement across platforms. Optimal clip length: 30-90 seconds.'
        }
        
        content_guidelines = {
            'educational': 'Look for clear explanations, aha moments, practical tips, and valuable insights.',
            'entertainment': 'Identify funny moments, surprising twists, emotional peaks, and engaging stories.',
            'news': 'Focus on breaking information, expert opinions, key facts, and impactful statements.',
            'general': 'Identify engaging moments that combine entertainment, information, or emotional impact.'
        }
        
        return f"""
Analyze the following video transcript for viral potential. Identify segments that would make compelling short-form clips.

VIDEO METADATA:
- Duration: {metadata.get('duration', 0):.1f} seconds
- Platform: {platform}
- Content Type: {content_type}

PLATFORM GUIDELINES:
{platform_guidelines.get(platform, platform_guidelines['general'])}

CONTENT GUIDELINES:
{content_guidelines.get(content_type, content_guidelines['general'])}

TRANSCRIPT:
{transcript}

ANALYSIS CRITERIA:
1. Hook Strength (0-10): How quickly does the segment grab attention?
2. Retention Value (0-10): How likely is the audience to watch until the end?
3. Shareability (0-10): How likely is the audience to share this content?
4. Emotional Impact (0-10): How strong is the emotional response?
5. Information Value (0-10): How valuable or surprising is the information?
6. Trending Potential (0-10): How well does it align with current trends?

Please respond with a JSON object containing:
{{
  "segments": [
    {{
      "start_time": float,
      "end_time": float,
      "virality_score": float (0-10),
      "hook_strength": float (0-10),
      "retention_value": float (0-10),
      "shareability": float (0-10),
      "emotional_impact": float (0-10),
      "information_value": float (0-10),
      "trending_potential": float (0-10),
      "primary_emotion": string,
      "keywords": [string],
      "reasons": [string],
      "recommended_clip_length": float
    }}
  ],
  "overall_analysis": {{
    "total_segments_analyzed": int,
    "high_potential_segments": int,
    "dominant_themes": [string],
    "recommended_strategy": string
  }}
}}

Focus on segments with virality_score >= 6.0. Provide specific, actionable reasons for each score.
"""
    
    def _parse_virality_response(
        self, 
        response: Dict[str, Any], 
        original_segments: List[Dict]
    ) -> List[ViralityScore]:
        """
        Parse the LLM response into ViralityScore objects.
        
        Args:
            response: LLM response dictionary
            original_segments: Original transcript segments
            
        Returns:
            List of ViralityScore objects
        """
        try:
            scores = []
            segments = response.get('segments', [])
            
            for segment in segments:
                # Validate required fields
                if not all(key in segment for key in ['start_time', 'end_time', 'virality_score']):
                    continue
                
                # Calculate engagement factors
                engagement_factors = {
                    'hook_strength': segment.get('hook_strength', 5.0),
                    'retention_value': segment.get('retention_value', 5.0),
                    'shareability': segment.get('shareability', 5.0),
                    'emotional_impact': segment.get('emotional_impact', 5.0),
                    'information_value': segment.get('information_value', 5.0),
                    'trending_potential': segment.get('trending_potential', 5.0)
                }
                
                score = ViralityScore(
                    start_time=float(segment['start_time']),
                    end_time=float(segment['end_time']),
                    score=float(segment['virality_score']),
                    reasons=segment.get('reasons', []),
                    keywords=segment.get('keywords', []),
                    emotion=segment.get('primary_emotion', 'neutral'),
                    engagement_factors=engagement_factors
                )
                
                # Only include high-potential segments
                if score.score >= 6.0:
                    scores.append(score)
            
            return scores
            
        except Exception as e:
            logger.error(f"Error parsing virality response: {e}")
            return self._generate_fallback_scores(original_segments)
    
    def _merge_overlapping_scores(self, scores: List[ViralityScore]) -> List[ViralityScore]:
        """
        Merge overlapping virality scores to avoid duplicate segments.
        
        Args:
            scores: List of virality scores
            
        Returns:
            Merged list of scores
        """
        if not scores:
            return []
        
        merged = []
        current = scores[0]
        
        for next_score in scores[1:]:
            # Check for overlap (with 2-second buffer)
            if next_score.start_time <= current.end_time + 2.0:
                # Merge scores - keep higher score and combine metadata
                if next_score.score > current.score:
                    current = ViralityScore(
                        start_time=current.start_time,
                        end_time=max(current.end_time, next_score.end_time),
                        score=next_score.score,
                        reasons=list(set(current.reasons + next_score.reasons)),
                        keywords=list(set(current.keywords + next_score.keywords)),
                        emotion=next_score.emotion,
                        engagement_factors={
                            k: max(current.engagement_factors.get(k, 0), 
                                  next_score.engagement_factors.get(k, 0))
                            for k in set(current.engagement_factors.keys()) | 
                                   set(next_score.engagement_factors.keys())
                        }
                    )
                else:
                    current = ViralityScore(
                        start_time=current.start_time,
                        end_time=max(current.end_time, next_score.end_time),
                        score=current.score,
                        reasons=list(set(current.reasons + next_score.reasons)),
                        keywords=list(set(current.keywords + next_score.keywords)),
                        emotion=current.emotion,
                        engagement_factors=current.engagement_factors
                    )
            else:
                merged.append(current)
                current = next_score
        
        merged.append(current)
        return merged
    
    def _generate_fallback_scores(self, segments: List[Dict]) -> List[ViralityScore]:
        """
        Generate fallback virality scores when LLM analysis fails.
        
        Args:
            segments: Transcript segments
            
        Returns:
            List of fallback scores
        """
        try:
            scores = []
            
            # Simple heuristic-based scoring
            for i, segment in enumerate(segments):
                text = segment.get('text', '').lower()
                start_time = segment.get('start', 0)
                end_time = segment.get('end', start_time + 30)
                
                # Basic scoring based on text analysis
                score = 5.0  # Base score
                reasons = []
                keywords = []
                
                # Check for engagement indicators
                engagement_words = [
                    'amazing', 'incredible', 'shocking', 'surprising', 'wow',
                    'secret', 'trick', 'hack', 'tip', 'mistake', 'wrong',
                    'truth', 'reveal', 'expose', 'hidden', 'unknown'
                ]
                
                for word in engagement_words:
                    if word in text:
                        score += 0.5
                        keywords.append(word)
                        reasons.append(f"Contains engagement word: {word}")
                
                # Check for questions
                if '?' in text:
                    score += 0.3
                    reasons.append("Contains question")
                
                # Check for emotional indicators
                emotional_words = [
                    'love', 'hate', 'angry', 'excited', 'scared', 'happy',
                    'sad', 'frustrated', 'amazed', 'shocked'
                ]
                
                emotion = 'neutral'
                for word in emotional_words:
                    if word in text:
                        score += 0.2
                        emotion = word
                        reasons.append(f"Emotional content: {word}")
                        break
                
                # Only include segments with decent scores
                if score >= 6.0:
                    scores.append(ViralityScore(
                        start_time=start_time,
                        end_time=end_time,
                        score=min(score, 10.0),
                        reasons=reasons or ["Fallback scoring"],
                        keywords=keywords,
                        emotion=emotion,
                        engagement_factors={
                            'hook_strength': score * 0.8,
                            'retention_value': score * 0.7,
                            'shareability': score * 0.6,
                            'emotional_impact': score * 0.5,
                            'information_value': score * 0.9,
                            'trending_potential': score * 0.4
                        }
                    ))
            
            logger.info(f"Generated {len(scores)} fallback virality scores")
            return scores
            
        except Exception as e:
            logger.error(f"Error generating fallback scores: {e}")
            return []
    
    async def identify_key_moments(
        self,
        transcript_segments: List[Dict],
        video_metadata: Dict[str, Any],
        moment_types: List[str] = None
    ) -> Dict[str, List[Dict]]:
        """
        Identify specific types of key moments in the content.
        
        Args:
            transcript_segments: List of transcript segments
            video_metadata: Video metadata
            moment_types: Types of moments to identify
            
        Returns:
            Dictionary of moment types and their segments
        """
        if moment_types is None:
            moment_types = ['hooks', 'climax', 'insights', 'quotes', 'transitions']
        
        try:
            # Prepare transcript
            transcript_text = "\n".join([
                f"[{seg.get('start', 0):.1f}s]: {seg.get('text', '').strip()}"
                for seg in transcript_segments if seg.get('text', '').strip()
            ])
            
            prompt = f"""
Analyze the following transcript and identify key moments of the specified types.

TRANSCRIPT:
{transcript_text}

IDENTIFY THESE MOMENT TYPES:
{', '.join(moment_types)}

For each moment type, provide:
- Timestamp range
- Confidence score (0-10)
- Description
- Why it's significant

Respond with JSON:
{{
  "moments": {{
    "hooks": [{{"start": float, "end": float, "confidence": float, "description": string, "significance": string}}],
    "climax": [...],
    "insights": [...],
    "quotes": [...],
    "transitions": [...]
  }}
}}
"""
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert content analyst. Identify key moments in video content with precision."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=2000,
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get('moments', {})
            
        except Exception as e:
            logger.error(f"Error identifying key moments: {e}")
            return {moment_type: [] for moment_type in moment_types}
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get API usage statistics.
        
        Returns:
            Usage statistics
        """
        return {
            'model': self.model,
            'max_tokens_per_request': self.max_tokens_per_request,
            'encoding': self.encoding.name,
            'timestamp': datetime.now().isoformat()
        }