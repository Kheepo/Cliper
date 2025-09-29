"""
Hashtag and Posting Recommendation Service for Cliper
Analyzes trending hashtags and optimal posting times for maximum engagement
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
import re
from collections import defaultdict, Counter
import numpy as np
from statistics import mean, median

from .unified_llm_service import UnifiedLLMService, TaskType, LLMResponse
from .viral_scoring import ViralScoringService, ComprehensiveViralAnalysis
from api.models.pydantic_models import PlatformEnum

logger = logging.getLogger(__name__)

class HashtagCategory(Enum):
    """Categories of hashtags for better organization"""
    TRENDING = "trending"
    NICHE = "niche"
    BRANDED = "branded"
    COMMUNITY = "community"
    SEASONAL = "seasonal"
    EVERGREEN = "evergreen"
    LOCATION = "location"
    EMOTION = "emotion"

class EngagementTimeSlot(Enum):
    """Time slots for optimal posting"""
    EARLY_MORNING = "early_morning"  # 6-9 AM
    MORNING = "morning"              # 9-12 PM
    AFTERNOON = "afternoon"          # 12-3 PM
    LATE_AFTERNOON = "late_afternoon" # 3-6 PM
    EVENING = "evening"              # 6-9 PM
    NIGHT = "night"                  # 9-12 AM
    LATE_NIGHT = "late_night"        # 12-6 AM

@dataclass
class HashtagRecommendation:
    """Individual hashtag recommendation with metadata"""
    tag: str
    category: HashtagCategory
    relevance_score: float  # 0.0 to 1.0
    trending_score: float   # 0.0 to 1.0
    competition_level: str  # "low", "medium", "high"
    estimated_reach: int
    engagement_rate: float
    platform_specific_data: Dict[str, Any]
    reasoning: str

@dataclass
class PostingTimeRecommendation:
    """Optimal posting time recommendation"""
    platform: PlatformEnum
    day_of_week: str
    time_slot: EngagementTimeSlot
    optimal_time: str  # HH:MM format
    timezone: str
    engagement_score: float  # 0.0 to 1.0
    audience_activity: float  # 0.0 to 1.0
    competition_level: str
    reasoning: str

@dataclass
class PlatformHashtagStrategy:
    """Platform-specific hashtag strategy"""
    platform: PlatformEnum
    recommended_hashtags: List[HashtagRecommendation]
    hashtag_count_range: Tuple[int, int]  # (min, max) recommended count
    mix_strategy: Dict[str, float]  # percentage of each category
    posting_times: List[PostingTimeRecommendation]
    content_optimization_tips: List[str]

@dataclass
class ComprehensiveRecommendations:
    """Complete hashtag and posting recommendations"""
    content_summary: str
    target_audience: str
    platform_strategies: Dict[str, PlatformHashtagStrategy]
    cross_platform_hashtags: List[str]
    content_themes: List[str]
    seasonal_considerations: List[str]
    performance_predictions: Dict[str, Dict[str, float]]
    processing_time: float
    metadata: Dict[str, Any]

class HashtagRecommendationService:
    """AI-powered hashtag and posting recommendation service"""
    
    def __init__(self):
        self.llm_service = UnifiedLLMService()
        self.viral_scoring_service = ViralScoringService()
        
        # Platform-specific hashtag limits and best practices
        self.platform_hashtag_limits = {
            PlatformEnum.TIKTOK: {"min": 3, "max": 5, "optimal": 4},
            PlatformEnum.INSTAGRAM: {"min": 5, "max": 30, "optimal": 11},
            PlatformEnum.YOUTUBE: {"min": 3, "max": 15, "optimal": 8}
        }
        
        # Platform-specific hashtag strategies
        self.platform_strategies = {
            PlatformEnum.TIKTOK: {
                "trending_weight": 0.4,
                "niche_weight": 0.3,
                "viral_weight": 0.3,
                "max_competition_tags": 2,
                "preferred_categories": ["trending", "niche", "emotion"],
                "avoid_categories": ["branded", "location"],
                "character_limit": 100,
                "optimal_mix": {
                    HashtagCategory.TRENDING: 0.4,
                    HashtagCategory.NICHE: 0.4,
                    HashtagCategory.EMOTION: 0.2
                }
            },
            PlatformEnum.INSTAGRAM: {
                "trending_weight": 0.25,
                "niche_weight": 0.35,
                "viral_weight": 0.2,
                "branded_weight": 0.2,
                "max_competition_tags": 5,
                "preferred_categories": ["niche", "community", "branded", "location"],
                "avoid_categories": [],
                "character_limit": 2200,
                "optimal_mix": {
                    HashtagCategory.NICHE: 0.35,
                    HashtagCategory.COMMUNITY: 0.25,
                    HashtagCategory.TRENDING: 0.2,
                    HashtagCategory.BRANDED: 0.1,
                    HashtagCategory.LOCATION: 0.1
                }
            },
            PlatformEnum.YOUTUBE: {
                "trending_weight": 0.2,
                "niche_weight": 0.4,
                "viral_weight": 0.2,
                "educational_weight": 0.2,
                "max_competition_tags": 3,
                "preferred_categories": ["niche", "evergreen", "educational"],
                "avoid_categories": ["emotion"],
                "character_limit": 500,
                "optimal_mix": {
                    HashtagCategory.NICHE: 0.4,
                    HashtagCategory.EVERGREEN: 0.3,
                    HashtagCategory.TRENDING: 0.2,
                    HashtagCategory.COMMUNITY: 0.1
                }
            }
        }
        
        # Enhanced trending hashtag databases with performance data
        self.trending_hashtags_enhanced = {
            PlatformEnum.TIKTOK: {
                "entertainment": [
                    {"tag": "fyp", "trend_score": 0.95, "competition": "high", "engagement_rate": 0.08},
                    {"tag": "viral", "trend_score": 0.9, "competition": "high", "engagement_rate": 0.07},
                    {"tag": "trending", "trend_score": 0.85, "competition": "high", "engagement_rate": 0.06},
                    {"tag": "comedy", "trend_score": 0.8, "competition": "medium", "engagement_rate": 0.09},
                    {"tag": "funny", "trend_score": 0.75, "competition": "medium", "engagement_rate": 0.08}
                ],
                "education": [
                    {"tag": "learn", "trend_score": 0.8, "competition": "medium", "engagement_rate": 0.1},
                    {"tag": "educational", "trend_score": 0.75, "competition": "low", "engagement_rate": 0.12},
                    {"tag": "tips", "trend_score": 0.7, "competition": "medium", "engagement_rate": 0.09},
                    {"tag": "howto", "trend_score": 0.65, "competition": "low", "engagement_rate": 0.11},
                    {"tag": "knowledge", "trend_score": 0.6, "competition": "low", "engagement_rate": 0.1}
                ]
            },
            PlatformEnum.INSTAGRAM: {
                "lifestyle": [
                    {"tag": "lifestyle", "trend_score": 0.85, "competition": "high", "engagement_rate": 0.06},
                    {"tag": "daily", "trend_score": 0.8, "competition": "medium", "engagement_rate": 0.07},
                    {"tag": "motivation", "trend_score": 0.75, "competition": "medium", "engagement_rate": 0.08},
                    {"tag": "inspiration", "trend_score": 0.7, "competition": "medium", "engagement_rate": 0.07},
                    {"tag": "selfcare", "trend_score": 0.65, "competition": "low", "engagement_rate": 0.09}
                ],
                "business": [
                    {"tag": "entrepreneur", "trend_score": 0.8, "competition": "medium", "engagement_rate": 0.08},
                    {"tag": "business", "trend_score": 0.75, "competition": "high", "engagement_rate": 0.06},
                    {"tag": "success", "trend_score": 0.7, "competition": "medium", "engagement_rate": 0.07},
                    {"tag": "mindset", "trend_score": 0.65, "competition": "low", "engagement_rate": 0.09},
                    {"tag": "growth", "trend_score": 0.6, "competition": "low", "engagement_rate": 0.08}
                ]
            },
            PlatformEnum.YOUTUBE: {
                "technology": [
                    {"tag": "tech", "trend_score": 0.8, "competition": "medium", "engagement_rate": 0.05},
                    {"tag": "review", "trend_score": 0.75, "competition": "high", "engagement_rate": 0.04},
                    {"tag": "tutorial", "trend_score": 0.7, "competition": "medium", "engagement_rate": 0.06},
                    {"tag": "howto", "trend_score": 0.65, "competition": "low", "engagement_rate": 0.07},
                    {"tag": "explained", "trend_score": 0.6, "competition": "low", "engagement_rate": 0.06}
                ]
            }
        }
        
        logger.info("Enhanced HashtagRecommendationService initialized")
    
    async def generate_recommendations(
        self,
        content_analysis: ComprehensiveViralAnalysis,
        transcription: Dict[str, Any],
        target_platforms: List[PlatformEnum] = None,
        target_audience: str = None,
        content_category: str = None
    ) -> ComprehensiveRecommendations:
        """
        Generate comprehensive hashtag and posting recommendations
        
        Args:
            content_analysis: Viral analysis results
            transcription: Video transcription data
            target_platforms: Platforms to generate recommendations for
            target_audience: Target audience description
            content_category: Content category (entertainment, education, etc.)
        
        Returns:
            ComprehensiveRecommendations with hashtags and posting strategies
        """
        start_time = time.time()
        
        if target_platforms is None:
            target_platforms = [PlatformEnum.TIKTOK, PlatformEnum.INSTAGRAM, PlatformEnum.YOUTUBE]
        
        logger.info(f"Generating recommendations for {len(target_platforms)} platforms")
        
        try:
            # Step 1: Analyze content for hashtag extraction
            content_features = await self._extract_content_features(
                content_analysis, transcription, target_audience, content_category
            )
            
            # Step 2: Generate platform-specific strategies
            platform_strategies = {}
            for platform in target_platforms:
                strategy = await self._generate_platform_strategy(
                    platform, content_features, content_analysis
                )
                platform_strategies[platform.value] = strategy
            
            # Step 3: Identify cross-platform hashtags
            cross_platform_hashtags = self._identify_cross_platform_hashtags(platform_strategies)
            
            # Step 4: Generate performance predictions
            performance_predictions = await self._predict_performance(
                platform_strategies, content_analysis
            )
            
            processing_time = time.time() - start_time
            
            return ComprehensiveRecommendations(
                content_summary=content_features.get('summary', ''),
                target_audience=target_audience or content_features.get('inferred_audience', 'General'),
                platform_strategies=platform_strategies,
                cross_platform_hashtags=cross_platform_hashtags,
                content_themes=content_features.get('themes', []),
                seasonal_considerations=content_features.get('seasonal_factors', []),
                performance_predictions=performance_predictions,
                processing_time=processing_time,
                metadata={
                    'analysis_timestamp': datetime.utcnow().isoformat(),
                    'platforms_analyzed': [p.value for p in target_platforms],
                    'content_category': content_category,
                    'ai_provider_used': 'unified_llm_service'
                }
            )
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return await self._generate_fallback_recommendations(
                target_platforms, content_category
            )
    
    async def _extract_content_features(
        self,
        content_analysis: ComprehensiveViralAnalysis,
        transcription: Dict[str, Any],
        target_audience: str = None,
        content_category: str = None
    ) -> Dict[str, Any]:
        """Extract features from content for hashtag generation"""
        
        # Extract text content
        text_content = ""
        if transcription and 'segments' in transcription:
            text_content = " ".join([
                segment.get('text', '') for segment in transcription['segments']
            ])
        
        # Create analysis prompt
        prompt = self._create_content_analysis_prompt(
            text_content, content_analysis, target_audience, content_category
        )
        
        try:
            response = await self.llm_service._execute_with_fallback(
                task_type=TaskType.CONTENT_ANALYSIS,
                prompt=prompt,
                max_tokens=1000
            )
            
            if response.success and response.data:
                # Parse the structured response
                features = self._parse_content_features(response.data)
                return features
            else:
                logger.warning("LLM content analysis failed, using fallback")
                return self._generate_fallback_content_features(text_content, content_analysis)
                
        except Exception as e:
            logger.error(f"Error in content feature extraction: {e}")
            return self._generate_fallback_content_features(text_content, content_analysis)
    
    def _create_content_analysis_prompt(
        self,
        text_content: str,
        content_analysis: ComprehensiveViralAnalysis,
        target_audience: str = None,
        content_category: str = None
    ) -> str:
        """Create prompt for content analysis"""
        
        prompt = f"""
Analyze the following video content for hashtag and posting recommendations:

CONTENT TRANSCRIPT:
{text_content[:2000]}...

VIRAL ANALYSIS SUMMARY:
- Overall Viral Score: {content_analysis.overall_viral_score:.2f}
- Key Strengths: {', '.join(content_analysis.strengths[:3])}
- Content Summary: {content_analysis.content_summary}

TARGET AUDIENCE: {target_audience or 'Not specified'}
CONTENT CATEGORY: {content_category or 'Not specified'}

Please provide a structured analysis in JSON format with the following fields:
{{
    "summary": "Brief content summary",
    "themes": ["theme1", "theme2", "theme3"],
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "emotions": ["emotion1", "emotion2"],
    "inferred_audience": "audience description",
    "content_type": "entertainment/education/lifestyle/etc",
    "seasonal_factors": ["factor1", "factor2"],
    "trending_topics": ["topic1", "topic2"],
    "call_to_actions": ["action1", "action2"]
}}

Focus on identifying:
1. Main themes and topics
2. Emotional tone and appeal
3. Target audience characteristics
4. Trending elements
5. Seasonal relevance
6. Call-to-action opportunities
"""
        return prompt
    
    def _parse_content_features(self, llm_response: str) -> Dict[str, Any]:
        """Parse LLM response into structured content features"""
        try:
            # Try to extract JSON from the response
            json_start = llm_response.find('{')
            json_end = llm_response.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = llm_response[json_start:json_end]
                features = json.loads(json_str)
                return features
            else:
                # Fallback parsing
                return self._parse_content_features_fallback(llm_response)
                
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from LLM response, using fallback")
            return self._parse_content_features_fallback(llm_response)
    
    def _parse_content_features_fallback(self, llm_response: str) -> Dict[str, Any]:
        """Fallback content feature parsing"""
        return {
            "summary": "Content analysis from video transcript",
            "themes": ["general", "entertainment"],
            "keywords": ["video", "content", "viral"],
            "emotions": ["engaging", "entertaining"],
            "inferred_audience": "General audience",
            "content_type": "entertainment",
            "seasonal_factors": [],
            "trending_topics": ["viral", "trending"],
            "call_to_actions": ["like", "share", "follow"]
        }
    
    def _generate_fallback_content_features(
        self,
        text_content: str,
        content_analysis: ComprehensiveViralAnalysis
    ) -> Dict[str, Any]:
        """Generate fallback content features when LLM fails"""
        
        # Extract keywords from transcript
        words = re.findall(r'\b\w+\b', text_content.lower())
        word_freq = Counter(words)
        common_words = [word for word, count in word_freq.most_common(10) 
                       if len(word) > 3 and word not in ['this', 'that', 'with', 'have']]
        
        return {
            "summary": content_analysis.content_summary or "Video content analysis",
            "themes": common_words[:3] if common_words else ["general"],
            "keywords": common_words[:5] if common_words else ["video", "content"],
            "emotions": ["engaging"] if content_analysis.overall_viral_score > 0.6 else ["neutral"],
            "inferred_audience": "General audience",
            "content_type": "entertainment",
            "seasonal_factors": [],
            "trending_topics": ["viral"] if content_analysis.overall_viral_score > 0.7 else [],
            "call_to_actions": ["like", "share"]
        }
    
    async def _generate_platform_strategy(
        self,
        platform: PlatformEnum,
        content_features: Dict[str, Any],
        content_analysis: ComprehensiveViralAnalysis
    ) -> PlatformHashtagStrategy:
        """Generate platform-specific hashtag strategy"""
        
        # Generate hashtag recommendations
        hashtag_recommendations = await self._generate_hashtag_recommendations(
            platform, content_features, content_analysis
        )
        
        # Generate posting time recommendations
        posting_times = self._generate_posting_time_recommendations(platform, content_features)
        
        # Get platform limits
        limits = self.platform_hashtag_limits[platform]
        
        # Generate content optimization tips
        optimization_tips = self._generate_optimization_tips(platform, content_analysis)
        
        return PlatformHashtagStrategy(
            platform=platform,
            recommended_hashtags=hashtag_recommendations,
            hashtag_count_range=(limits["min"], limits["max"]),
            mix_strategy={
                "trending": 0.3,
                "niche": 0.4,
                "branded": 0.1,
                "community": 0.2
            },
            posting_times=posting_times,
            content_optimization_tips=optimization_tips
        )
    
    async def _generate_hashtag_recommendations(
        self,
        platform: PlatformEnum,
        content_features: Dict[str, Any],
        content_analysis: ComprehensiveViralAnalysis
    ) -> List[HashtagRecommendation]:
        """Generate sophisticated hashtag recommendations for a specific platform"""
        
        recommendations = []
        platform_strategy = self.platform_strategies[platform]
        content_type = content_features.get('content_type', 'general')
        
        # Algorithm 1: Trending-based recommendations
        trending_recs = await self._generate_trending_recommendations(
            platform, content_type, content_analysis
        )
        recommendations.extend(trending_recs)
        
        # Algorithm 2: Content similarity recommendations
        similarity_recs = await self._generate_similarity_recommendations(
            platform, content_features, content_analysis
        )
        recommendations.extend(similarity_recs)
        
        # Algorithm 3: Niche targeting recommendations
        niche_recs = await self._generate_niche_recommendations(
            platform, content_features, content_analysis
        )
        recommendations.extend(niche_recs)
        
        # Algorithm 4: Viral amplification recommendations
        viral_recs = await self._generate_viral_amplification_recommendations(
            platform, content_analysis
        )
        recommendations.extend(viral_recs)
        
        # Remove duplicates and optimize mix
        unique_recommendations = self._remove_duplicates_and_optimize(
            recommendations, platform_strategy
        )
        
        # Score and rank recommendations
        scored_recommendations = self._score_and_rank_recommendations(
            unique_recommendations, platform, content_analysis
        )
        
        # Apply platform-specific limits
        optimal_count = self.platform_hashtag_limits[platform]["optimal"]
        return scored_recommendations[:optimal_count]
    
    async def _generate_trending_recommendations(
        self,
        platform: PlatformEnum,
        content_type: str,
        content_analysis: ComprehensiveViralAnalysis
    ) -> List[HashtagRecommendation]:
        """Generate recommendations based on trending hashtags"""
        
        recommendations = []
        trending_data = self.trending_hashtags_enhanced.get(platform, {})
        
        # Get trending hashtags for content type
        content_hashtags = trending_data.get(content_type, [])
        if not content_hashtags:
            # Fallback to general trending hashtags
            content_hashtags = trending_data.get('general', [])
        
        for hashtag_data in content_hashtags[:3]:  # Top 3 trending
            recommendations.append(HashtagRecommendation(
                tag=hashtag_data["tag"],
                category=HashtagCategory.TRENDING,
                relevance_score=hashtag_data["trend_score"],
                trending_score=hashtag_data["trend_score"],
                competition_level=hashtag_data["competition"],
                estimated_reach=self._calculate_estimated_reach(hashtag_data, content_analysis),
                engagement_rate=hashtag_data["engagement_rate"],
                platform_specific_data={
                    "trend_duration": 7,  # days
                    "growth_rate": 15.0,  # percentage
                    "usage_count": 1000000
                },
                reasoning=f"Trending hashtag with {hashtag_data['trend_score']:.1%} trend score"
            ))
        
        return recommendations
    
    async def _generate_similarity_recommendations(
        self,
        platform: PlatformEnum,
        content_features: Dict[str, Any],
        content_analysis: ComprehensiveViralAnalysis
    ) -> List[HashtagRecommendation]:
        """Generate recommendations based on content similarity"""
        
        recommendations = []
        themes = content_features.get('themes', [])
        keywords = content_features.get('keywords', [])
        
        # Generate hashtags from content themes and keywords
        content_tags = []
        
        # Process themes
        for theme in themes[:3]:
            processed_tag = self._process_hashtag(theme)
            if processed_tag and len(processed_tag) > 2:
                content_tags.append(processed_tag)
        
        # Process keywords
        for keyword in keywords[:3]:
            processed_tag = self._process_hashtag(keyword)
            if processed_tag and len(processed_tag) > 2:
                content_tags.append(processed_tag)
        
        # Create recommendations from content tags
        for tag in content_tags:
            recommendations.append(HashtagRecommendation(
                tag=tag,
                category=HashtagCategory.NICHE,
                relevance_score=0.85,
                trending_score=0.6,
                competition_level="medium",
                estimated_reach=self._estimate_niche_reach(tag, content_analysis),
                engagement_rate=0.1,
                platform_specific_data={},
                reasoning=f"Content-derived hashtag from theme/keyword analysis"
            ))
        
        return recommendations[:4]  # Limit to 4 content-based tags
    
    async def _generate_niche_recommendations(
        self,
        platform: PlatformEnum,
        content_features: Dict[str, Any],
        content_analysis: ComprehensiveViralAnalysis
    ) -> List[HashtagRecommendation]:
        """Generate niche hashtag recommendations"""
        
        recommendations = []
        content_type = content_features.get('content_type', 'general')
        
        # Niche hashtag database (can be expanded with real data)
        niche_hashtags = {
            "entertainment": ["comedyskits", "funnyvideos", "entertainment", "laughs"],
            "education": ["learnontiktok", "edutok", "studytips", "knowledge"],
            "lifestyle": ["lifehacks", "dailyroutine", "selfimprovement", "wellness"],
            "technology": ["techreview", "gadgets", "innovation", "futuretech"],
            "business": ["entrepreneurlife", "businesstips", "startup", "hustle"]
        }
        
        relevant_niches = niche_hashtags.get(content_type, ["general", "content", "creator"])
        
        for niche_tag in relevant_niches[:3]:
            recommendations.append(HashtagRecommendation(
                tag=niche_tag,
                category=HashtagCategory.NICHE,
                relevance_score=0.8,
                trending_score=0.5,
                competition_level="low",
                estimated_reach=25000,
                engagement_rate=0.12,
                platform_specific_data={},
                reasoning=f"Niche hashtag for {content_type} content"
            ))
        
        return recommendations
    
    async def _generate_viral_amplification_recommendations(
        self,
        platform: PlatformEnum,
        content_analysis: ComprehensiveViralAnalysis
    ) -> List[HashtagRecommendation]:
        """Generate hashtags that can amplify viral potential"""
        
        recommendations = []
        viral_score = content_analysis.overall_viral_score
        
        # Viral amplification hashtags based on content viral score
        if viral_score > 0.8:
            viral_tags = ["viral", "trending", "mustwatch", "amazing"]
        elif viral_score > 0.6:
            viral_tags = ["interesting", "cool", "awesome", "share"]
        else:
            viral_tags = ["content", "creator", "new", "check"]
        
        for tag in viral_tags[:2]:  # Limit to 2 viral amplification tags
            recommendations.append(HashtagRecommendation(
                tag=tag,
                category=HashtagCategory.EVERGREEN,
                relevance_score=viral_score,
                trending_score=0.7,
                competition_level="high" if viral_score > 0.7 else "medium",
                estimated_reach=int(viral_score * 50000),
                engagement_rate=viral_score * 0.1,
                platform_specific_data={},
                reasoning=f"Viral amplification tag based on {viral_score:.1%} viral score"
            ))
        
        return recommendations
    
    def _process_hashtag(self, text: str) -> str:
        """Process text into a valid hashtag"""
        if not text:
            return ""
        
        # Remove special characters and spaces
        processed = re.sub(r'[^a-zA-Z0-9]', '', text.lower())
        
        # Ensure it's not too long
        if len(processed) > 20:
            processed = processed[:20]
        
        return processed
    
    def _calculate_estimated_reach(
        self,
        hashtag_data: Dict[str, Any],
        content_analysis: ComprehensiveViralAnalysis
    ) -> int:
        """Calculate estimated reach for a hashtag"""
        
        base_reach = 50000  # Base reach for trending hashtags
        trend_multiplier = hashtag_data.get("trend_score", 0.5)
        viral_multiplier = content_analysis.overall_viral_score
        
        # Adjust for competition
        competition = hashtag_data.get("competition", "medium")
        competition_multiplier = {"low": 1.2, "medium": 1.0, "high": 0.8}[competition]
        
        estimated_reach = int(
            base_reach * trend_multiplier * viral_multiplier * competition_multiplier
        )
        
        return max(1000, estimated_reach)  # Minimum 1000 reach
    
    def _estimate_niche_reach(
        self,
        tag: str,
        content_analysis: ComprehensiveViralAnalysis
    ) -> int:
        """Estimate reach for niche hashtags"""
        
        base_reach = 15000  # Lower base reach for niche tags
        viral_multiplier = content_analysis.overall_viral_score
        
        # Niche tags typically have higher engagement but lower reach
        estimated_reach = int(base_reach * viral_multiplier * 1.5)
        
        return max(500, estimated_reach)
    
    def _remove_duplicates_and_optimize(
        self,
        recommendations: List[HashtagRecommendation],
        platform_strategy: Dict[str, Any]
    ) -> List[HashtagRecommendation]:
        """Remove duplicates and optimize hashtag mix"""
        
        # Remove duplicates based on tag name
        seen_tags = set()
        unique_recommendations = []
        
        for rec in recommendations:
            if rec.tag not in seen_tags:
                seen_tags.add(rec.tag)
                unique_recommendations.append(rec)
        
        # Optimize mix based on platform strategy
        optimal_mix = platform_strategy.get("optimal_mix", {})
        category_counts = defaultdict(int)
        optimized_recommendations = []
        
        # Sort by relevance score first
        unique_recommendations.sort(key=lambda x: x.relevance_score, reverse=True)
        
        for rec in unique_recommendations:
            category = rec.category
            current_count = category_counts[category]
            max_count = int(optimal_mix.get(category, 0.2) * 10)  # Rough limit
            
            if current_count < max_count:
                optimized_recommendations.append(rec)
                category_counts[category] += 1
        
        return optimized_recommendations
    
    def _score_and_rank_recommendations(
        self,
        recommendations: List[HashtagRecommendation],
        platform: PlatformEnum,
        content_analysis: ComprehensiveViralAnalysis
    ) -> List[HashtagRecommendation]:
        """Score and rank hashtag recommendations"""
        
        platform_strategy = self.platform_strategies[platform]
        
        for rec in recommendations:
            # Calculate composite score
            relevance_weight = 0.3
            trending_weight = platform_strategy.get("trending_weight", 0.3)
            engagement_weight = 0.2
            competition_weight = 0.2  # Lower competition = higher score
            
            # Competition score (inverse)
            competition_scores = {"low": 1.0, "medium": 0.7, "high": 0.4}
            competition_score = competition_scores.get(rec.competition_level, 0.5)
            
            # Calculate composite score
            composite_score = (
                rec.relevance_score * relevance_weight +
                rec.trending_score * trending_weight +
                rec.engagement_rate * 10 * engagement_weight +  # Scale engagement rate
                competition_score * competition_weight
            )
            
            # Update relevance score with composite score
            rec.relevance_score = min(1.0, composite_score)
        
        # Sort by composite score
        recommendations.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return recommendations

    async def quick_hashtag_recommendations(
        self,
        content_text: str,
        platform: PlatformEnum,
        content_category: str = None
    ) -> List[str]:
        """Quick hashtag recommendations for simple use cases"""
        
        try:
            # Simple keyword extraction
            words = re.findall(r'\b\w+\b', content_text.lower())
            keywords = [word for word in set(words) if len(word) > 3][:3]
            
            # Get trending hashtags
            trending = self.trending_hashtags.get(platform, {}).get(content_category or 'general', [])
            
            # Combine keywords and trending
            recommendations = keywords + trending[:3]
            
            # Limit to platform optimal count
            optimal_count = self.platform_hashtag_limits[platform]["optimal"]
            return recommendations[:optimal_count]
            
        except Exception as e:
            logger.error(f"Error in quick recommendations: {e}")
            return ["viral", "trending", "content"]


class HashtagAlgorithm(Enum):
    """Different hashtag recommendation algorithms"""
    TRENDING_BASED = "trending_based"
    CONTENT_SIMILARITY = "content_similarity"
    ENGAGEMENT_OPTIMIZATION = "engagement_optimization"
    NICHE_TARGETING = "niche_targeting"
    VIRAL_AMPLIFICATION = "viral_amplification"

@dataclass
class TrendingHashtagData:
    """Data structure for trending hashtag information"""
    tag: str
    platform: PlatformEnum
    trend_score: float  # 0.0 to 1.0
    growth_rate: float  # percentage growth
    usage_count: int
    engagement_rate: float
    competition_level: str
    trend_duration: int  # days trending
    related_tags: List[str]
    category: str

@dataclass
class HashtagPerformanceMetrics:
    """Performance metrics for hashtag recommendations"""
    tag: str
    platform: PlatformEnum
    estimated_reach: int
    estimated_impressions: int
    estimated_engagement: int
    click_through_rate: float
    conversion_probability: float
    viral_potential: float
    audience_alignment: float

@dataclass
class ViralHashtagInsights:
    """Insights from viral scoring integration"""
    viral_factors_alignment: Dict[str, float]
    viral_moment_hashtags: List[str]
    engagement_boosting_tags: List[str]
    audience_resonance_score: float
    content_amplification_potential: float
    platform_optimization_score: float

class HashtagRecommendationService:
    """AI-powered hashtag and posting recommendation service"""
    
    def __init__(self):
        self.llm_service = UnifiedLLMService()
        self.viral_scoring_service = ViralScoringService()
        
        # Platform-specific hashtag limits and best practices
        self.platform_hashtag_limits = {
            PlatformEnum.TIKTOK: {"min": 3, "max": 5, "optimal": 4},
            PlatformEnum.INSTAGRAM: {"min": 5, "max": 30, "optimal": 11},
            PlatformEnum.YOUTUBE: {"min": 3, "max": 15, "optimal": 8}
        }
        
        # Platform-specific hashtag strategies
        self.platform_strategies = {
            PlatformEnum.TIKTOK: {
                "trending_weight": 0.4,
                "niche_weight": 0.3,
                "viral_weight": 0.3,
                "max_competition_tags": 2,
                "preferred_categories": ["trending", "niche", "emotion"],
                "avoid_categories": ["branded", "location"],
                "character_limit": 100,
                "optimal_mix": {
                    HashtagCategory.TRENDING: 0.4,
                    HashtagCategory.NICHE: 0.4,
                    HashtagCategory.EMOTION: 0.2
                }
            },
            PlatformEnum.INSTAGRAM: {
                "trending_weight": 0.25,
                "niche_weight": 0.35,
                "viral_weight": 0.2,
                "branded_weight": 0.2,
                "max_competition_tags": 5,
                "preferred_categories": ["niche", "community", "branded", "location"],
                "avoid_categories": [],
                "character_limit": 2200,
                "optimal_mix": {
                    HashtagCategory.NICHE: 0.35,
                    HashtagCategory.COMMUNITY: 0.25,
                    HashtagCategory.TRENDING: 0.2,
                    HashtagCategory.BRANDED: 0.1,
                    HashtagCategory.LOCATION: 0.1
                }
            },
            PlatformEnum.YOUTUBE: {
                "trending_weight": 0.2,
                "niche_weight": 0.4,
                "viral_weight": 0.2,
                "educational_weight": 0.2,
                "max_competition_tags": 3,
                "preferred_categories": ["niche", "evergreen", "educational"],
                "avoid_categories": ["emotion"],
                "character_limit": 500,
                "optimal_mix": {
                    HashtagCategory.NICHE: 0.4,
                    HashtagCategory.EVERGREEN: 0.3,
                    HashtagCategory.TRENDING: 0.2,
                    HashtagCategory.COMMUNITY: 0.1
                }
            }
        }
        
        # Enhanced trending hashtag databases with performance data
        self.trending_hashtags_enhanced = {
            PlatformEnum.TIKTOK: {
                "entertainment": [
                    {"tag": "fyp", "trend_score": 0.95, "competition": "high", "engagement_rate": 0.08},
                    {"tag": "viral", "trend_score": 0.9, "competition": "high", "engagement_rate": 0.07},
                    {"tag": "trending", "trend_score": 0.85, "competition": "high", "engagement_rate": 0.06},
                    {"tag": "comedy", "trend_score": 0.8, "competition": "medium", "engagement_rate": 0.09},
                    {"tag": "funny", "trend_score": 0.75, "competition": "medium", "engagement_rate": 0.08}
                ],
                "education": [
                    {"tag": "learn", "trend_score": 0.8, "competition": "medium", "engagement_rate": 0.1},
                    {"tag": "educational", "trend_score": 0.75, "competition": "low", "engagement_rate": 0.12},
                    {"tag": "tips", "trend_score": 0.7, "competition": "medium", "engagement_rate": 0.09},
                    {"tag": "howto", "trend_score": 0.65, "competition": "low", "engagement_rate": 0.11},
                    {"tag": "knowledge", "trend_score": 0.6, "competition": "low", "engagement_rate": 0.1}
                ]
            },
            PlatformEnum.INSTAGRAM: {
                "lifestyle": [
                    {"tag": "lifestyle", "trend_score": 0.85, "competition": "high", "engagement_rate": 0.06},
                    {"tag": "daily", "trend_score": 0.8, "competition": "medium", "engagement_rate": 0.07},
                    {"tag": "motivation", "trend_score": 0.75, "competition": "medium", "engagement_rate": 0.08},
                    {"tag": "inspiration", "trend_score": 0.7, "competition": "medium", "engagement_rate": 0.07},
                    {"tag": "selfcare", "trend_score": 0.65, "competition": "low", "engagement_rate": 0.09}
                ],
                "business": [
                    {"tag": "entrepreneur", "trend_score": 0.8, "competition": "medium", "engagement_rate": 0.08},
                    {"tag": "business", "trend_score": 0.75, "competition": "high", "engagement_rate": 0.06},
                    {"tag": "success", "trend_score": 0.7, "competition": "medium", "engagement_rate": 0.07},
                    {"tag": "mindset", "trend_score": 0.65, "competition": "low", "engagement_rate": 0.09},
                    {"tag": "growth", "trend_score": 0.6, "competition": "low", "engagement_rate": 0.08}
                ]
            },
            PlatformEnum.YOUTUBE: {
                "technology": [
                    {"tag": "tech", "trend_score": 0.8, "competition": "medium", "engagement_rate": 0.05},
                    {"tag": "review", "trend_score": 0.75, "competition": "high", "engagement_rate": 0.04},
                    {"tag": "tutorial", "trend_score": 0.7, "competition": "medium", "engagement_rate": 0.06},
                    {"tag": "howto", "trend_score": 0.65, "competition": "low", "engagement_rate": 0.07},
                    {"tag": "explained", "trend_score": 0.6, "competition": "low", "engagement_rate": 0.06}
                ]
            }
        }
        
        logger.info("Enhanced HashtagRecommendationService initialized")

    async def get_trending_hashtags(
        self,
        platform: PlatformEnum,
        category: Optional[str] = None,
        limit: int = 20
    ) -> List[Any]:
        """
        Get trending hashtags for a specific platform
        
        Args:
            platform: Target platform
            category: Optional category filter
            limit: Maximum number of hashtags to return
        
        Returns:
            List of trending hashtag objects with performance metrics
        """
        try:
            logger.info(f"Fetching trending hashtags for {platform.value}, category: {category}, limit: {limit}")
            
            # Get trending hashtags from our enhanced database
            trending_data = self.trending_hashtags_enhanced.get(platform, {})
            
            # If category is specified, get hashtags for that category
            if category and category in trending_data:
                hashtag_list = trending_data[category]
            else:
                # Get all hashtags from all categories for this platform
                hashtag_list = []
                for cat_hashtags in trending_data.values():
                    hashtag_list.extend(cat_hashtags)
            
            # Convert to hashtag objects with required attributes
            trending_hashtags = []
            for hashtag_data in hashtag_list[:limit]:
                # Create a hashtag object with the expected attributes
                hashtag_obj = type('HashtagObject', (), {
                    'hashtag': hashtag_data["tag"],
                    'trend_score': hashtag_data["trend_score"],
                    'engagement_prediction': hashtag_data["engagement_rate"],
                    'competition_level': hashtag_data["competition"],
                    'category': type('CategoryObject', (), {'value': category or 'general'})(),
                    'performance_metrics': {
                        'trend_score': hashtag_data["trend_score"],
                        'engagement_rate': hashtag_data["engagement_rate"],
                        'competition_level': hashtag_data["competition"],
                        'estimated_reach': int(hashtag_data["trend_score"] * 50000),
                        'usage_frequency': int(hashtag_data["trend_score"] * 100000),
                        'growth_rate': hashtag_data["trend_score"] * 15.0
                    }
                })()
                
                trending_hashtags.append(hashtag_obj)
            
            # Sort by trend score (highest first)
            trending_hashtags.sort(key=lambda x: x.trend_score, reverse=True)
            
            logger.info(f"Successfully fetched {len(trending_hashtags)} trending hashtags for {platform.value}")
            return trending_hashtags
            
        except Exception as e:
            logger.error(f"Error fetching trending hashtags: {e}")
            # Return fallback hashtags
            fallback_hashtags = []
            fallback_tags = ["viral", "trending", "content", "popular", "fyp"]
            
            for i, tag in enumerate(fallback_tags[:limit]):
                hashtag_obj = type('HashtagObject', (), {
                    'hashtag': tag,
                    'trend_score': 0.8 - (i * 0.1),
                    'engagement_prediction': 0.07 - (i * 0.01),
                    'competition_level': "medium",
                    'category': type('CategoryObject', (), {'value': 'general'})(),
                    'performance_metrics': {
                        'trend_score': 0.8 - (i * 0.1),
                        'engagement_rate': 0.07 - (i * 0.01),
                        'competition_level': "medium",
                        'estimated_reach': 30000 - (i * 5000),
                        'usage_frequency': 80000 - (i * 10000),
                        'growth_rate': 10.0 - (i * 1.0)
                    }
                })()
                fallback_hashtags.append(hashtag_obj)
            
            return fallback_hashtags

    async def generate_recommendations_with_viral_integration(
        self,
        content_analysis: ComprehensiveViralAnalysis,
        transcription: Dict[str, Any],
        target_platforms: List[PlatformEnum] = None,
        target_audience: str = None,
        content_category: str = None
    ) -> ComprehensiveRecommendations:
        """
        Enhanced recommendation generation with deep viral scoring integration
        """
        start_time = time.time()
        
        if target_platforms is None:
            target_platforms = [PlatformEnum.TIKTOK, PlatformEnum.INSTAGRAM, PlatformEnum.YOUTUBE]
        
        logger.info(f"Generating viral-enhanced recommendations for {len(target_platforms)} platforms")
        
        try:
            # Step 1: Extract viral insights for hashtag optimization
            viral_insights = await self._extract_viral_hashtag_insights(content_analysis)
            
            # Step 2: Analyze content with viral context
            content_features = await self._extract_content_features_with_viral_context(
                content_analysis, transcription, target_audience, content_category, viral_insights
            )
            
            # Step 3: Generate platform-specific strategies with viral optimization
            platform_strategies = {}
            for platform in target_platforms:
                strategy = await self._generate_viral_optimized_platform_strategy(
                    platform, content_features, content_analysis, viral_insights
                )
                platform_strategies[platform.value] = strategy
            
            # Step 4: Identify cross-platform hashtags with viral potential
            cross_platform_hashtags = self._identify_viral_cross_platform_hashtags(
                platform_strategies, viral_insights
            )
            
            # Step 5: Generate enhanced performance predictions
            performance_predictions = await self._predict_viral_enhanced_performance(
                platform_strategies, content_analysis, viral_insights
            )
            
            processing_time = time.time() - start_time
            
            return ComprehensiveRecommendations(
                content_summary=content_features.get('summary', ''),
                target_audience=target_audience or content_features.get('inferred_audience', 'General'),
                platform_strategies=platform_strategies,
                cross_platform_hashtags=cross_platform_hashtags,
                content_themes=content_features.get('themes', []),
                seasonal_considerations=content_features.get('seasonal_factors', []),
                performance_predictions=performance_predictions,
                processing_time=processing_time,
                metadata={
                    'analysis_timestamp': datetime.utcnow().isoformat(),
                    'platforms_analyzed': [p.value for p in target_platforms],
                    'content_category': content_category,
                    'ai_provider_used': 'unified_llm_service',
                    'viral_integration_enabled': True,
                    'viral_score': content_analysis.overall_viral_score,
                    'viral_insights': asdict(viral_insights)
                }
            )
            
        except Exception as e:
            logger.error(f"Error generating viral-enhanced recommendations: {e}")
            return await self._generate_fallback_recommendations(
                target_platforms, content_category
            )
    
    async def _extract_viral_hashtag_insights(
        self,
        content_analysis: ComprehensiveViralAnalysis
    ) -> ViralHashtagInsights:
        """Extract hashtag-relevant insights from viral analysis"""
        
        # Analyze viral factors for hashtag alignment
        viral_factors_alignment = {}
        for factor in content_analysis.viral_factors:
            factor_name = factor.factor_type.value
            viral_factors_alignment[factor_name] = factor.score
        
        # Extract hashtags from viral moments
        viral_moment_hashtags = []
        for moment in content_analysis.viral_moments:
            # Extract potential hashtags from moment descriptions
            words = re.findall(r'\b\w+\b', moment.description.lower())
            relevant_words = [word for word in words if len(word) > 3 and word not in ['this', 'that', 'with', 'have']]
            viral_moment_hashtags.extend(relevant_words[:2])  # Top 2 words per moment
        
        # Identify engagement-boosting tags based on viral factors
        engagement_boosting_tags = []
        high_scoring_factors = [f for f in content_analysis.viral_factors if f.score > 0.7]
        
        for factor in high_scoring_factors:
            factor_type = factor.factor_type.value
            if factor_type == "hook_strength":
                engagement_boosting_tags.extend(["attention", "hook", "watch"])
            elif factor_type == "emotional_impact":
                engagement_boosting_tags.extend(["emotional", "feels", "impact"])
            elif factor_type == "shareability":
                engagement_boosting_tags.extend(["share", "viral", "mustwatch"])
            elif factor_type == "trend_alignment":
                engagement_boosting_tags.extend(["trending", "trend", "viral"])
        
        # Calculate audience resonance score
        audience_resonance_score = mean([
            factor.score for factor in content_analysis.viral_factors
            if factor.factor_type.value in ["emotional_impact", "relatability", "authenticity"]
        ]) if content_analysis.viral_factors else 0.5
        
        # Calculate content amplification potential
        amplification_factors = [
            factor.score for factor in content_analysis.viral_factors
            if factor.factor_type.value in ["shareability", "hook_strength", "trend_alignment"]
        ]
        content_amplification_potential = mean(amplification_factors) if amplification_factors else 0.5
        
        return ViralHashtagInsights(
            viral_factors_alignment=viral_factors_alignment,
            viral_moment_hashtags=list(set(viral_moment_hashtags[:10])),  # Unique, top 10
            engagement_boosting_tags=list(set(engagement_boosting_tags[:8])),  # Unique, top 8
            audience_resonance_score=audience_resonance_score,
            content_amplification_potential=content_amplification_potential,
            platform_optimization_score=content_analysis.overall_viral_score
        )
    
    async def _extract_content_features_with_viral_context(
        self,
        content_analysis: ComprehensiveViralAnalysis,
        transcription: Dict[str, Any],
        target_audience: str = None,
        content_category: str = None,
        viral_insights: ViralHashtagInsights = None
    ) -> Dict[str, Any]:
        """Extract content features enhanced with viral context"""
        
        # Get base content features
        base_features = await self._extract_content_features(
            content_analysis, transcription, target_audience, content_category
        )
        
        # Enhance with viral insights
        if viral_insights:
            # Add viral moment keywords to themes
            viral_themes = viral_insights.viral_moment_hashtags
            base_features['themes'] = list(set(base_features.get('themes', []) + viral_themes))
            
            # Add engagement boosting keywords
            base_features['viral_keywords'] = viral_insights.engagement_boosting_tags
            
            # Enhance emotional analysis
            if viral_insights.audience_resonance_score > 0.7:
                base_features['emotions'].extend(["resonant", "relatable"])
            
            # Add viral amplification indicators
            base_features['amplification_potential'] = viral_insights.content_amplification_potential
            base_features['viral_factors'] = viral_insights.viral_factors_alignment
        
        return base_features
    
    async def _generate_viral_optimized_platform_strategy(
        self,
        platform: PlatformEnum,
        content_features: Dict[str, Any],
        content_analysis: ComprehensiveViralAnalysis,
        viral_insights: ViralHashtagInsights
    ) -> PlatformHashtagStrategy:
        """Generate platform strategy optimized with viral insights"""
        
        # Generate viral-enhanced hashtag recommendations
        hashtag_recommendations = await self._generate_viral_enhanced_hashtag_recommendations(
            platform, content_features, content_analysis, viral_insights
        )
        
        # Generate posting time recommendations with viral timing
        posting_times = self._generate_viral_optimized_posting_times(
            platform, content_features, viral_insights
        )
        
        # Get platform limits
        limits = self.platform_hashtag_limits[platform]
        
        # Generate viral-aware optimization tips
        optimization_tips = self._generate_viral_optimization_tips(
            platform, content_analysis, viral_insights
        )
        
        # Calculate viral-enhanced mix strategy
        mix_strategy = self._calculate_viral_mix_strategy(platform, viral_insights)
        
        return PlatformHashtagStrategy(
            platform=platform,
            recommended_hashtags=hashtag_recommendations,
            hashtag_count_range=(limits["min"], limits["max"]),
            mix_strategy=mix_strategy,
            posting_times=posting_times,
            content_optimization_tips=optimization_tips
        )
    
    async def _generate_viral_enhanced_hashtag_recommendations(
        self,
        platform: PlatformEnum,
        content_features: Dict[str, Any],
        content_analysis: ComprehensiveViralAnalysis,
        viral_insights: ViralHashtagInsights
    ) -> List[HashtagRecommendation]:
        """Generate hashtag recommendations enhanced with viral insights"""
        
        recommendations = []
        platform_strategy = self.platform_strategies[platform]
        
        # Algorithm 1: Viral factor-based recommendations
        viral_factor_recs = await self._generate_viral_factor_recommendations(
            platform, viral_insights, content_analysis
        )
        recommendations.extend(viral_factor_recs)
        
        # Algorithm 2: Enhanced trending recommendations with viral context
        trending_recs = await self._generate_viral_trending_recommendations(
            platform, content_features, content_analysis, viral_insights
        )
        recommendations.extend(trending_recs)
        
        # Algorithm 3: Viral moment-based recommendations
        moment_recs = await self._generate_viral_moment_recommendations(
            platform, viral_insights, content_analysis
        )
        recommendations.extend(moment_recs)
        
        # Algorithm 4: Engagement amplification recommendations
        amplification_recs = await self._generate_engagement_amplification_recommendations(
            platform, viral_insights, content_analysis
        )
        recommendations.extend(amplification_recs)
        
        # Algorithm 5: Standard content-based recommendations (existing)
        content_recs = await self._generate_similarity_recommendations(
            platform, content_features, content_analysis
        )
        recommendations.extend(content_recs)
        
        # Remove duplicates and optimize with viral context
        unique_recommendations = self._remove_duplicates_and_viral_optimize(
            recommendations, platform_strategy, viral_insights
        )
        
        # Score and rank with viral enhancement
        scored_recommendations = self._score_and_rank_viral_recommendations(
            unique_recommendations, platform, content_analysis, viral_insights
        )
        
        # Apply platform-specific limits
        optimal_count = self.platform_hashtag_limits[platform]["optimal"]
        return scored_recommendations[:optimal_count]
    
    async def _generate_viral_factor_recommendations(
        self,
        platform: PlatformEnum,
        viral_insights: ViralHashtagInsights,
        content_analysis: ComprehensiveViralAnalysis
    ) -> List[HashtagRecommendation]:
        """Generate recommendations based on viral factors"""
        
        recommendations = []
        
        # Map viral factors to hashtags
        factor_hashtag_mapping = {
            "hook_strength": ["hook", "attention", "watch", "captivating"],
            "emotional_impact": ["emotional", "feels", "touching", "powerful"],
            "shareability": ["share", "viral", "mustwatch", "amazing"],
            "trend_alignment": ["trending", "trend", "viral", "popular"],
            "authenticity": ["real", "authentic", "genuine", "honest"],
            "relatability": ["relatable", "mood", "same", "truth"]
        }
        
        # Generate hashtags for high-scoring viral factors
        for factor_name, score in viral_insights.viral_factors_alignment.items():
            if score > 0.6:  # Only use factors with good scores
                relevant_hashtags = factor_hashtag_mapping.get(factor_name, [])
                
                for hashtag in relevant_hashtags[:2]:  # Top 2 hashtags per factor
                    recommendations.append(HashtagRecommendation(
                        tag=hashtag,
                        category=HashtagCategory.EMOTION if factor_name in ["emotional_impact", "authenticity"] else HashtagCategory.TRENDING,
                        relevance_score=score,
                        trending_score=score * 0.8,
                        competition_level="medium",
                        estimated_reach=int(score * 40000),
                        engagement_rate=score * 0.12,
                        platform_specific_data={
                            "viral_factor": factor_name,
                            "factor_score": score
                        },
                        reasoning=f"Viral factor '{factor_name}' scored {score:.1%}"
                    ))
        
        return recommendations[:4]  # Limit to top 4 viral factor hashtags
    
    async def _generate_viral_trending_recommendations(
        self,
        platform: PlatformEnum,
        content_features: Dict[str, Any],
        content_analysis: ComprehensiveViralAnalysis,
        viral_insights: ViralHashtagInsights
    ) -> List[HashtagRecommendation]:
        """Generate trending recommendations enhanced with viral context"""
        
        # Get base trending recommendations
        base_trending = await self._generate_trending_recommendations(
            platform, content_features.get('content_type', 'general'), content_analysis
        )
        
        # Enhance with viral context
        for rec in base_trending:
            # Boost relevance for high viral potential content
            if viral_insights.content_amplification_potential > 0.7:
                rec.relevance_score = min(1.0, rec.relevance_score * 1.2)
                rec.estimated_reach = int(rec.estimated_reach * 1.3)
                rec.reasoning += f" (Boosted for {viral_insights.content_amplification_potential:.1%} viral potential)"
        
        return base_trending
    
    async def _generate_viral_moment_recommendations(
        self,
        platform: PlatformEnum,
        viral_insights: ViralHashtagInsights,
        content_analysis: ComprehensiveViralAnalysis
    ) -> List[HashtagRecommendation]:
        """Generate recommendations based on viral moments"""
        
        recommendations = []
        
        # Use viral moment hashtags
        for hashtag in viral_insights.viral_moment_hashtags[:3]:
            processed_tag = self._process_hashtag(hashtag)
            if processed_tag and len(processed_tag) > 2:
                recommendations.append(HashtagRecommendation(
                    tag=processed_tag,
                    category=HashtagCategory.NICHE,
                    relevance_score=0.8,
                    trending_score=0.6,
                    competition_level="low",
                    estimated_reach=20000,
                    engagement_rate=0.15,  # Higher engagement for niche viral moments
                    platform_specific_data={
                        "source": "viral_moment",
                        "moment_context": "extracted_from_viral_analysis"
                    },
                    reasoning="Hashtag derived from viral moment analysis"
                ))
        
        return recommendations
    
    async def _generate_engagement_amplification_recommendations(
        self,
        platform: PlatformEnum,
        viral_insights: ViralHashtagInsights,
        content_analysis: ComprehensiveViralAnalysis
    ) -> List[HashtagRecommendation]:
        """Generate hashtags specifically for engagement amplification"""
        
        recommendations = []
        
        # Use engagement boosting tags
        for tag in viral_insights.engagement_boosting_tags[:3]:
            recommendations.append(HashtagRecommendation(
                tag=tag,
                category=HashtagCategory.EVERGREEN,
                relevance_score=viral_insights.audience_resonance_score,
                trending_score=0.7,
                competition_level="medium",
                estimated_reach=int(viral_insights.audience_resonance_score * 35000),
                engagement_rate=viral_insights.audience_resonance_score * 0.1,
                platform_specific_data={
                    "amplification_type": "engagement_boost",
                    "resonance_score": viral_insights.audience_resonance_score
                },
                reasoning=f"Engagement amplification tag (resonance: {viral_insights.audience_resonance_score:.1%})"
            ))
        
        return recommendations
    
    def _remove_duplicates_and_viral_optimize(
        self,
        recommendations: List[HashtagRecommendation],
        platform_strategy: Dict[str, Any],
        viral_insights: ViralHashtagInsights
    ) -> List[HashtagRecommendation]:
        """Remove duplicates and optimize with viral context"""
        
        # Remove duplicates
        seen_tags = set()
        unique_recommendations = []
        
        for rec in recommendations:
            if rec.tag not in seen_tags:
                seen_tags.add(rec.tag)
                unique_recommendations.append(rec)
        
        # Prioritize viral-enhanced recommendations
        viral_priority_categories = [HashtagCategory.EMOTION, HashtagCategory.TRENDING]
        
        # Sort by viral relevance and category priority
        def viral_sort_key(rec):
            category_priority = 1.0 if rec.category in viral_priority_categories else 0.8
            viral_boost = 1.2 if "viral_factor" in rec.platform_specific_data else 1.0
            return rec.relevance_score * category_priority * viral_boost
        
        unique_recommendations.sort(key=viral_sort_key, reverse=True)
        
        return unique_recommendations
    
    def _score_and_rank_viral_recommendations(
        self,
        recommendations: List[HashtagRecommendation],
        platform: PlatformEnum,
        content_analysis: ComprehensiveViralAnalysis,
        viral_insights: ViralHashtagInsights
    ) -> List[HashtagRecommendation]:
        """Score and rank recommendations with viral enhancement"""
        
        platform_strategy = self.platform_strategies[platform]
        
        for rec in recommendations:
            # Base scoring
            relevance_weight = 0.25
            trending_weight = platform_strategy.get("trending_weight", 0.25)
            engagement_weight = 0.2
            competition_weight = 0.15
            viral_weight = 0.15  # New viral factor weight
            
            # Competition score (inverse)
            competition_scores = {"low": 1.0, "medium": 0.7, "high": 0.4}
            competition_score = competition_scores.get(rec.competition_level, 0.5)
            
            # Viral enhancement score
            viral_score = 0.5  # Default
            if "viral_factor" in rec.platform_specific_data:
                viral_score = rec.platform_specific_data["factor_score"]
            elif rec.category == HashtagCategory.EMOTION:
                viral_score = viral_insights.audience_resonance_score
            elif rec.category == HashtagCategory.TRENDING:
                viral_score = viral_insights.content_amplification_potential
            
            # Calculate enhanced composite score
            composite_score = (
                rec.relevance_score * relevance_weight +
                rec.trending_score * trending_weight +
                rec.engagement_rate * 10 * engagement_weight +
                competition_score * competition_weight +
                viral_score * viral_weight
            )
            
            # Update relevance score with composite score
            rec.relevance_score = min(1.0, composite_score)
        
        # Sort by enhanced composite score
        recommendations.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return recommendations
    
    def _generate_viral_optimized_posting_times(
        self,
        platform: PlatformEnum,
        content_features: Dict[str, Any],
        viral_insights: ViralHashtagInsights
    ) -> List[PostingTimeRecommendation]:
        """Generate posting times optimized for viral content"""
        
        base_times = self._generate_posting_time_recommendations(platform, content_features)
        
        # Enhance with viral timing insights
        for time_rec in base_times:
            # Boost engagement scores for high viral potential
            if viral_insights.content_amplification_potential > 0.7:
                time_rec.engagement_score = min(1.0, time_rec.engagement_score * 1.15)
                time_rec.reasoning += f" (Optimized for {viral_insights.content_amplification_potential:.1%} viral potential)"
        
        return base_times
    
    def _generate_viral_optimization_tips(
        self,
        platform: PlatformEnum,
        content_analysis: ComprehensiveViralAnalysis,
        viral_insights: ViralHashtagInsights
    ) -> List[str]:
        """Generate optimization tips enhanced with viral insights"""
        
        base_tips = self._generate_optimization_tips(platform, content_analysis)
        viral_tips = []
        
        # Add viral-specific tips
        if viral_insights.content_amplification_potential > 0.8:
            viral_tips.append("Content has exceptional viral potential - consider promoting immediately")
        
        if viral_insights.audience_resonance_score > 0.7:
            viral_tips.append("High audience resonance detected - engage actively with early comments")
        
        # Add factor-specific tips
        for factor_name, score in viral_insights.viral_factors_alignment.items():
            if score > 0.8:
                if factor_name == "hook_strength":
                    viral_tips.append("Strong hook detected - use attention-grabbing thumbnails")
                elif factor_name == "shareability":
                    viral_tips.append("High shareability - encourage sharing in captions")
                elif factor_name == "emotional_impact":
                    viral_tips.append("Strong emotional impact - leverage in storytelling")
        
        # Combine and limit tips
        all_tips = viral_tips + base_tips
        return all_tips[:7]  # Return top 7 tips
    
    def _calculate_viral_mix_strategy(
        self,
        platform: PlatformEnum,
        viral_insights: ViralHashtagInsights
    ) -> Dict[str, float]:
        """Calculate hashtag mix strategy based on viral insights"""
        
        base_strategy = {
            "trending": 0.3,
            "niche": 0.3,
            "viral_enhanced": 0.2,
            "engagement": 0.2
        }
        
        # Adjust based on viral potential
        if viral_insights.content_amplification_potential > 0.7:
            base_strategy["trending"] = 0.4
            base_strategy["viral_enhanced"] = 0.3
            base_strategy["niche"] = 0.2
            base_strategy["engagement"] = 0.1
        elif viral_insights.audience_resonance_score > 0.7:
            base_strategy["engagement"] = 0.3
            base_strategy["niche"] = 0.3
            base_strategy["trending"] = 0.2
            base_strategy["viral_enhanced"] = 0.2
        
        return base_strategy
    
    def _identify_viral_cross_platform_hashtags(
        self,
        platform_strategies: Dict[str, PlatformHashtagStrategy],
        viral_insights: ViralHashtagInsights
    ) -> List[str]:
        """Identify cross-platform hashtags with viral enhancement"""
        
        base_cross_platform = self._identify_cross_platform_hashtags(platform_strategies)
        
        # Add viral-specific cross-platform hashtags
        viral_cross_platform = []
        
        # Add high-scoring viral hashtags that work across platforms
        for tag in viral_insights.engagement_boosting_tags:
            if tag in ["viral", "trending", "share", "amazing", "watch"]:
                viral_cross_platform.append(tag)
        
        # Combine and deduplicate
        all_cross_platform = list(set(base_cross_platform + viral_cross_platform))
        
        return all_cross_platform[:8]  # Return top 8 cross-platform hashtags
    
    async def _predict_viral_enhanced_performance(
        self,
        platform_strategies: Dict[str, PlatformHashtagStrategy],
        content_analysis: ComprehensiveViralAnalysis,
        viral_insights: ViralHashtagInsights
    ) -> Dict[str, Dict[str, float]]:
        """Predict performance with viral enhancement"""
        
        base_predictions = await self._predict_performance(platform_strategies, content_analysis)
        
        # Enhance predictions with viral insights
        for platform_name, predictions in base_predictions.items():
            viral_multiplier = 1.0 + (viral_insights.content_amplification_potential * 0.5)
            engagement_multiplier = 1.0 + (viral_insights.audience_resonance_score * 0.3)
            
            # Apply viral enhancements
            predictions["estimated_views"] = int(predictions["estimated_views"] * viral_multiplier)
            predictions["estimated_engagement_rate"] = min(0.2, predictions["estimated_engagement_rate"] * engagement_multiplier)
            predictions["estimated_shares"] = int(predictions["estimated_shares"] * viral_multiplier * 1.2)
            predictions["viral_potential_score"] = viral_insights.content_amplification_potential
            predictions["audience_resonance_score"] = viral_insights.audience_resonance_score
            
            # Update confidence score
            predictions["confidence_score"] = min(0.95, predictions["confidence_score"] * 1.1)
        
        return base_predictions

    async def quick_hashtag_recommendations(
        self,
        content_text: str,
        platform: PlatformEnum,
        content_category: str = None
    ) -> List[str]:
        """Quick hashtag recommendations for simple use cases"""
        
        try:
            # Simple keyword extraction
            words = re.findall(r'\b\w+\b', content_text.lower())
            keywords = [word for word in set(words) if len(word) > 3][:3]
            
            # Get trending hashtags
            trending = self.trending_hashtags.get(platform, {}).get(content_category or 'general', [])
            
            # Combine keywords and trending
            recommendations = keywords + trending[:3]
            
            # Limit to platform optimal count
            optimal_count = self.platform_hashtag_limits[platform]["optimal"]
            return recommendations[:optimal_count]
            
        except Exception as e:
            logger.error(f"Error in quick recommendations: {e}")
            return ["viral", "trending", "content"]