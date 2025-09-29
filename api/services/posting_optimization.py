"""
Posting Time Optimization Service for Cliper
Analyzes audience engagement patterns and determines optimal posting times
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
import numpy as np
from statistics import mean, median
from collections import defaultdict

from .unified_llm_service import UnifiedLLMService, TaskType, LLMResponse
from api.models.pydantic_models import PlatformEnum

logger = logging.getLogger(__name__)

class AudienceSegment(Enum):
    """Different audience segments with different engagement patterns"""
    STUDENTS = "students"
    WORKING_PROFESSIONALS = "working_professionals"
    PARENTS = "parents"
    SENIORS = "seniors"
    CREATORS = "creators"
    GENERAL = "general"

class GeographicRegion(Enum):
    """Geographic regions for timezone considerations"""
    NORTH_AMERICA = "north_america"
    EUROPE = "europe"
    ASIA_PACIFIC = "asia_pacific"
    LATIN_AMERICA = "latin_america"
    MIDDLE_EAST_AFRICA = "middle_east_africa"
    GLOBAL = "global"

@dataclass
class EngagementPattern:
    """Engagement pattern for specific time periods"""
    hour: int
    day_of_week: int  # 0=Monday, 6=Sunday
    engagement_score: float  # 0.0 to 1.0
    audience_activity: float  # 0.0 to 1.0
    competition_level: float  # 0.0 to 1.0
    conversion_rate: float  # 0.0 to 1.0
    sample_size: int
    confidence: float

@dataclass
class OptimalPostingWindow:
    """Optimal posting time window"""
    start_time: str  # HH:MM format
    end_time: str    # HH:MM format
    peak_time: str   # HH:MM format
    day_of_week: str
    timezone: str
    engagement_score: float
    expected_reach: int
    competition_level: str
    audience_segments: List[AudienceSegment]
    reasoning: str

@dataclass
class AudienceInsights:
    """Insights about the target audience"""
    primary_segment: AudienceSegment
    geographic_distribution: Dict[str, float]
    age_distribution: Dict[str, float]
    activity_patterns: Dict[str, float]
    platform_preferences: Dict[str, float]
    engagement_triggers: List[str]
    optimal_content_length: Dict[str, int]

@dataclass
class PostingStrategy:
    """Complete posting strategy for a platform"""
    platform: PlatformEnum
    optimal_windows: List[OptimalPostingWindow]
    posting_frequency: Dict[str, int]  # daily, weekly recommendations
    content_scheduling_tips: List[str]
    audience_insights: AudienceInsights
    seasonal_adjustments: Dict[str, float]
    performance_metrics: Dict[str, float]

class PostingOptimizationService:
    """Service for optimizing posting times based on audience engagement patterns"""
    
    def __init__(self):
        self.llm_service = UnifiedLLMService()
        
        # Platform-specific engagement patterns (baseline data)
        self.platform_engagement_patterns = {
            PlatformEnum.TIKTOK: {
                "peak_hours": [9, 12, 19, 21],
                "peak_days": [1, 2, 4, 5],  # Tuesday, Wednesday, Friday, Saturday
                "audience_segments": [AudienceSegment.STUDENTS, AudienceSegment.GENERAL],
                "optimal_frequency": {"daily": 1, "weekly": 7},
                "engagement_decay": 2  # hours
            },
            PlatformEnum.INSTAGRAM: {
                "peak_hours": [11, 14, 17, 20],
                "peak_days": [1, 2, 3, 4],  # Tuesday-Friday
                "audience_segments": [AudienceSegment.WORKING_PROFESSIONALS, AudienceSegment.CREATORS],
                "optimal_frequency": {"daily": 1, "weekly": 5},
                "engagement_decay": 4  # hours
            },
            PlatformEnum.YOUTUBE: {
                "peak_hours": [14, 17, 20, 22],
                "peak_days": [4, 5, 6],  # Friday-Sunday
                "audience_segments": [AudienceSegment.GENERAL, AudienceSegment.WORKING_PROFESSIONALS],
                "optimal_frequency": {"daily": 0.3, "weekly": 2},
                "engagement_decay": 24  # hours
            }
        }
        
        # Audience segment activity patterns
        self.audience_patterns = {
            AudienceSegment.STUDENTS: {
                "active_hours": [7, 8, 12, 13, 16, 17, 20, 21, 22],
                "peak_days": [0, 1, 2, 3, 4, 6],  # Weekdays + Sunday
                "timezone_preference": "local",
                "content_preferences": ["entertainment", "education", "trends"]
            },
            AudienceSegment.WORKING_PROFESSIONALS: {
                "active_hours": [7, 8, 12, 13, 17, 18, 19, 20],
                "peak_days": [0, 1, 2, 3, 4],  # Weekdays
                "timezone_preference": "business_hours",
                "content_preferences": ["education", "lifestyle", "news"]
            },
            AudienceSegment.PARENTS: {
                "active_hours": [9, 10, 14, 15, 20, 21],
                "peak_days": [0, 1, 2, 3, 4, 6],  # Weekdays + Sunday
                "timezone_preference": "local",
                "content_preferences": ["family", "education", "lifestyle"]
            },
            AudienceSegment.CREATORS: {
                "active_hours": [10, 11, 14, 15, 16, 19, 20, 21],
                "peak_days": [0, 1, 2, 3, 4, 5, 6],  # All days
                "timezone_preference": "global",
                "content_preferences": ["trends", "education", "behind_scenes"]
            }
        }
        
        # Geographic timezone mappings
        self.timezone_mappings = {
            GeographicRegion.NORTH_AMERICA: ["EST", "CST", "MST", "PST"],
            GeographicRegion.EUROPE: ["GMT", "CET", "EET"],
            GeographicRegion.ASIA_PACIFIC: ["JST", "AEST", "IST"],
            GeographicRegion.LATIN_AMERICA: ["BRT", "ART", "COT"],
            GeographicRegion.MIDDLE_EAST_AFRICA: ["EAT", "CAT", "WAT"]
        }
        
        logger.info("PostingOptimizationService initialized")
    
    async def optimize_posting_strategy(
        self,
        platform: PlatformEnum,
        target_audience: str = None,
        content_category: str = None,
        geographic_region: GeographicRegion = GeographicRegion.GLOBAL,
        historical_performance: Dict[str, Any] = None
    ) -> PostingStrategy:
        """
        Generate optimized posting strategy for a platform
        
        Args:
            platform: Target platform
            target_audience: Description of target audience
            content_category: Type of content being posted
            geographic_region: Primary geographic region of audience
            historical_performance: Historical performance data if available
        
        Returns:
            PostingStrategy with optimal timing and insights
        """
        logger.info(f"Optimizing posting strategy for {platform.value}")
        
        try:
            # Step 1: Analyze audience characteristics
            audience_insights = await self._analyze_audience(
                target_audience, content_category, geographic_region
            )
            
            # Step 2: Calculate optimal posting windows
            optimal_windows = self._calculate_optimal_windows(
                platform, audience_insights, geographic_region
            )
            
            # Step 3: Determine posting frequency
            posting_frequency = self._calculate_posting_frequency(
                platform, audience_insights, historical_performance
            )
            
            # Step 4: Generate content scheduling tips
            scheduling_tips = self._generate_scheduling_tips(
                platform, audience_insights, optimal_windows
            )
            
            # Step 5: Calculate seasonal adjustments
            seasonal_adjustments = self._calculate_seasonal_adjustments(
                platform, content_category
            )
            
            # Step 6: Predict performance metrics
            performance_metrics = self._predict_performance_metrics(
                platform, optimal_windows, audience_insights
            )
            
            return PostingStrategy(
                platform=platform,
                optimal_windows=optimal_windows,
                posting_frequency=posting_frequency,
                content_scheduling_tips=scheduling_tips,
                audience_insights=audience_insights,
                seasonal_adjustments=seasonal_adjustments,
                performance_metrics=performance_metrics
            )
            
        except Exception as e:
            logger.error(f"Error optimizing posting strategy: {e}")
            return self._generate_fallback_strategy(platform, geographic_region)
    
    async def _analyze_audience(
        self,
        target_audience: str = None,
        content_category: str = None,
        geographic_region: GeographicRegion = GeographicRegion.GLOBAL
    ) -> AudienceInsights:
        """Analyze audience characteristics for posting optimization"""
        
        if target_audience:
            # Use LLM to analyze audience description
            audience_analysis = await self._llm_analyze_audience(target_audience, content_category)
            if audience_analysis:
                return audience_analysis
        
        # Fallback to default audience insights
        return self._generate_default_audience_insights(content_category, geographic_region)
    
    async def _llm_analyze_audience(
        self,
        target_audience: str,
        content_category: str = None
    ) -> Optional[AudienceInsights]:
        """Use LLM to analyze audience characteristics"""
        
        prompt = f"""
Analyze the following target audience for social media posting optimization:

TARGET AUDIENCE: {target_audience}
CONTENT CATEGORY: {content_category or 'Not specified'}

Please provide a structured analysis in JSON format:
{{
    "primary_segment": "students/working_professionals/parents/seniors/creators/general",
    "geographic_distribution": {{"north_america": 0.4, "europe": 0.3, "asia_pacific": 0.2, "other": 0.1}},
    "age_distribution": {{"18-24": 0.3, "25-34": 0.4, "35-44": 0.2, "45+": 0.1}},
    "activity_patterns": {{"morning": 0.2, "afternoon": 0.3, "evening": 0.4, "night": 0.1}},
    "platform_preferences": {{"tiktok": 0.4, "instagram": 0.4, "youtube": 0.2}},
    "engagement_triggers": ["trend1", "trend2", "trend3"],
    "optimal_content_length": {{"tiktok": 30, "instagram": 60, "youtube": 180}}
}}

Focus on:
1. Primary audience segment
2. Geographic and age distribution
3. Daily activity patterns
4. Platform preferences
5. Content that drives engagement
6. Optimal content length preferences
"""
        
        try:
            response = await self.llm_service._execute_with_fallback(
                task_type=TaskType.CONTENT_ANALYSIS,
                prompt=prompt,
                max_tokens=800
            )
            
            if response.success and response.data:
                # Parse the structured response
                analysis = self._parse_audience_analysis(response.data)
                return analysis
            else:
                logger.warning("LLM audience analysis failed")
                return None
                
        except Exception as e:
            logger.error(f"Error in LLM audience analysis: {e}")
            return None
    
    def _parse_audience_analysis(self, llm_response: str) -> Optional[AudienceInsights]:
        """Parse LLM audience analysis response"""
        try:
            # Extract JSON from response
            json_start = llm_response.find('{')
            json_end = llm_response.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = llm_response[json_start:json_end]
                data = json.loads(json_str)
                
                # Map string to enum
                segment_mapping = {
                    "students": AudienceSegment.STUDENTS,
                    "working_professionals": AudienceSegment.WORKING_PROFESSIONALS,
                    "parents": AudienceSegment.PARENTS,
                    "seniors": AudienceSegment.SENIORS,
                    "creators": AudienceSegment.CREATORS,
                    "general": AudienceSegment.GENERAL
                }
                
                primary_segment = segment_mapping.get(
                    data.get("primary_segment", "general"),
                    AudienceSegment.GENERAL
                )
                
                return AudienceInsights(
                    primary_segment=primary_segment,
                    geographic_distribution=data.get("geographic_distribution", {}),
                    age_distribution=data.get("age_distribution", {}),
                    activity_patterns=data.get("activity_patterns", {}),
                    platform_preferences=data.get("platform_preferences", {}),
                    engagement_triggers=data.get("engagement_triggers", []),
                    optimal_content_length=data.get("optimal_content_length", {})
                )
            
            return None
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse audience analysis: {e}")
            return None
    
    def _generate_default_audience_insights(
        self,
        content_category: str = None,
        geographic_region: GeographicRegion = GeographicRegion.GLOBAL
    ) -> AudienceInsights:
        """Generate default audience insights based on content category"""
        
        # Default mappings based on content category
        category_mappings = {
            "entertainment": AudienceSegment.GENERAL,
            "education": AudienceSegment.STUDENTS,
            "business": AudienceSegment.WORKING_PROFESSIONALS,
            "lifestyle": AudienceSegment.PARENTS,
            "technology": AudienceSegment.WORKING_PROFESSIONALS,
            "gaming": AudienceSegment.STUDENTS
        }
        
        primary_segment = category_mappings.get(content_category, AudienceSegment.GENERAL)
        
        # Default geographic distribution
        geo_distribution = {
            "north_america": 0.35,
            "europe": 0.25,
            "asia_pacific": 0.25,
            "other": 0.15
        }
        
        return AudienceInsights(
            primary_segment=primary_segment,
            geographic_distribution=geo_distribution,
            age_distribution={"18-24": 0.3, "25-34": 0.4, "35-44": 0.2, "45+": 0.1},
            activity_patterns={"morning": 0.2, "afternoon": 0.3, "evening": 0.4, "night": 0.1},
            platform_preferences={"tiktok": 0.35, "instagram": 0.35, "youtube": 0.3},
            engagement_triggers=["trending", "relatable", "educational"],
            optimal_content_length={"tiktok": 30, "instagram": 60, "youtube": 180}
        )
    
    def _calculate_optimal_windows(
        self,
        platform: PlatformEnum,
        audience_insights: AudienceInsights,
        geographic_region: GeographicRegion
    ) -> List[OptimalPostingWindow]:
        """Calculate optimal posting windows based on audience patterns"""
        
        platform_patterns = self.platform_engagement_patterns[platform]
        audience_patterns = self.audience_patterns[audience_insights.primary_segment]
        
        optimal_windows = []
        
        # Calculate windows for each day of the week
        for day in range(7):  # 0=Monday, 6=Sunday
            day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][day]
            
            # Check if this day is good for the platform and audience
            platform_day_score = 1.0 if day in platform_patterns["peak_days"] else 0.6
            audience_day_score = 1.0 if day in audience_patterns["peak_days"] else 0.5
            
            if platform_day_score * audience_day_score > 0.5:
                # Find optimal hours for this day
                optimal_hours = self._find_optimal_hours(
                    platform_patterns["peak_hours"],
                    audience_patterns["active_hours"]
                )
                
                for hour in optimal_hours[:2]:  # Top 2 hours per day
                    engagement_score = self._calculate_engagement_score(
                        hour, day, platform, audience_insights
                    )
                    
                    if engagement_score > 0.6:  # Only include high-engagement windows
                        window = OptimalPostingWindow(
                            start_time=f"{hour:02d}:00",
                            end_time=f"{(hour + 1) % 24:02d}:00",
                            peak_time=f"{hour:02d}:30",
                            day_of_week=day_name,
                            timezone="UTC",
                            engagement_score=engagement_score,
                            expected_reach=int(engagement_score * 10000),
                            competition_level=self._get_competition_level(hour, day, platform),
                            audience_segments=[audience_insights.primary_segment],
                            reasoning=f"High engagement window for {audience_insights.primary_segment.value} on {platform.value}"
                        )
                        optimal_windows.append(window)
        
        # Sort by engagement score and return top windows
        optimal_windows.sort(key=lambda x: x.engagement_score, reverse=True)
        return optimal_windows[:10]  # Return top 10 windows
    
    def _find_optimal_hours(
        self,
        platform_peak_hours: List[int],
        audience_active_hours: List[int]
    ) -> List[int]:
        """Find hours that overlap between platform peaks and audience activity"""
        
        # Calculate score for each hour
        hour_scores = {}
        
        for hour in range(24):
            platform_score = 1.0 if hour in platform_peak_hours else 0.3
            audience_score = 1.0 if hour in audience_active_hours else 0.2
            
            # Combine scores with weights
            combined_score = platform_score * 0.6 + audience_score * 0.4
            hour_scores[hour] = combined_score
        
        # Sort hours by score
        sorted_hours = sorted(hour_scores.items(), key=lambda x: x[1], reverse=True)
        return [hour for hour, score in sorted_hours if score > 0.5]
    
    def _calculate_engagement_score(
        self,
        hour: int,
        day: int,
        platform: PlatformEnum,
        audience_insights: AudienceInsights
    ) -> float:
        """Calculate engagement score for specific time"""
        
        platform_patterns = self.platform_engagement_patterns[platform]
        audience_patterns = self.audience_patterns[audience_insights.primary_segment]
        
        # Base scores
        platform_hour_score = 1.0 if hour in platform_patterns["peak_hours"] else 0.5
        platform_day_score = 1.0 if day in platform_patterns["peak_days"] else 0.6
        audience_hour_score = 1.0 if hour in audience_patterns["active_hours"] else 0.3
        audience_day_score = 1.0 if day in audience_patterns["peak_days"] else 0.4
        
        # Competition factor (lower competition = higher score)
        competition_factor = 1.0 - (len(platform_patterns["peak_hours"]) * 0.1)
        
        # Combine all factors
        engagement_score = (
            platform_hour_score * 0.25 +
            platform_day_score * 0.25 +
            audience_hour_score * 0.3 +
            audience_day_score * 0.2
        ) * competition_factor
        
        return min(1.0, engagement_score)
    
    def _get_competition_level(self, hour: int, day: int, platform: PlatformEnum) -> str:
        """Determine competition level for posting time"""
        
        platform_patterns = self.platform_engagement_patterns[platform]
        
        if hour in platform_patterns["peak_hours"] and day in platform_patterns["peak_days"]:
            return "high"
        elif hour in platform_patterns["peak_hours"] or day in platform_patterns["peak_days"]:
            return "medium"
        else:
            return "low"
    
    def _calculate_posting_frequency(
        self,
        platform: PlatformEnum,
        audience_insights: AudienceInsights,
        historical_performance: Dict[str, Any] = None
    ) -> Dict[str, int]:
        """Calculate optimal posting frequency"""
        
        platform_patterns = self.platform_engagement_patterns[platform]
        base_frequency = platform_patterns["optimal_frequency"]
        
        # Adjust based on audience engagement
        audience_activity = audience_insights.activity_patterns
        activity_multiplier = sum(audience_activity.values()) / len(audience_activity)
        
        # Adjust based on historical performance if available
        performance_multiplier = 1.0
        if historical_performance and "engagement_rate" in historical_performance:
            engagement_rate = historical_performance["engagement_rate"]
            performance_multiplier = min(1.5, max(0.5, engagement_rate * 2))
        
        adjusted_frequency = {}
        for period, freq in base_frequency.items():
            adjusted_freq = int(freq * activity_multiplier * performance_multiplier)
            adjusted_frequency[period] = max(1, adjusted_freq) if period == "weekly" else adjusted_freq
        
        return adjusted_frequency
    
    def _generate_scheduling_tips(
        self,
        platform: PlatformEnum,
        audience_insights: AudienceInsights,
        optimal_windows: List[OptimalPostingWindow]
    ) -> List[str]:
        """Generate content scheduling tips"""
        
        tips = []
        
        # Platform-specific tips
        if platform == PlatformEnum.TIKTOK:
            tips.extend([
                "Post consistently during peak hours for algorithm boost",
                "Use trending sounds and hashtags for maximum reach",
                "Engage with comments within the first hour of posting"
            ])
        elif platform == PlatformEnum.INSTAGRAM:
            tips.extend([
                "Use Instagram Stories to maintain daily presence",
                "Post Reels during high-engagement windows",
                "Schedule posts when your audience is most active"
            ])
        elif platform == PlatformEnum.YOUTUBE:
            tips.extend([
                "Upload videos 2-3 hours before peak viewing times",
                "Maintain consistent upload schedule",
                "Use community posts to engage between video uploads"
            ])
        
        # Audience-specific tips
        segment = audience_insights.primary_segment
        if segment == AudienceSegment.STUDENTS:
            tips.append("Post during lunch breaks and evening study breaks")
        elif segment == AudienceSegment.WORKING_PROFESSIONALS:
            tips.append("Target commute times and lunch hours for maximum engagement")
        elif segment == AudienceSegment.PARENTS:
            tips.append("Post during school hours or after bedtime for better reach")
        
        # Window-specific tips
        if optimal_windows:
            best_window = optimal_windows[0]
            tips.append(f"Your best posting time is {best_window.peak_time} on {best_window.day_of_week}")
        
        return tips[:6]  # Return top 6 tips
    
    def _calculate_seasonal_adjustments(
        self,
        platform: PlatformEnum,
        content_category: str = None
    ) -> Dict[str, float]:
        """Calculate seasonal adjustments for posting strategy"""
        
        # Seasonal multipliers (1.0 = no change, >1.0 = increase, <1.0 = decrease)
        seasonal_adjustments = {
            "spring": 1.0,
            "summer": 1.1,  # Generally higher social media usage
            "fall": 1.05,   # Back to school/work season
            "winter": 0.95, # Holiday season competition
            "holidays": 0.8, # High competition during holidays
            "back_to_school": 1.15,  # High engagement for educational content
            "new_year": 1.2  # High motivation and goal-setting content
        }
        
        # Adjust based on content category
        if content_category == "education":
            seasonal_adjustments["back_to_school"] = 1.3
            seasonal_adjustments["summer"] = 0.9
        elif content_category == "entertainment":
            seasonal_adjustments["summer"] = 1.2
            seasonal_adjustments["holidays"] = 1.1
        
        return seasonal_adjustments
    
    def _predict_performance_metrics(
        self,
        platform: PlatformEnum,
        optimal_windows: List[OptimalPostingWindow],
        audience_insights: AudienceInsights
    ) -> Dict[str, float]:
        """Predict performance metrics for the posting strategy"""
        
        if not optimal_windows:
            return {"estimated_reach": 1000, "engagement_rate": 0.05, "confidence": 0.5}
        
        # Calculate average engagement score
        avg_engagement = mean([window.engagement_score for window in optimal_windows])
        
        # Platform-specific base metrics
        platform_metrics = {
            PlatformEnum.TIKTOK: {"base_reach": 5000, "base_engagement": 0.08},
            PlatformEnum.INSTAGRAM: {"base_reach": 3000, "base_engagement": 0.06},
            PlatformEnum.YOUTUBE: {"base_reach": 2000, "base_engagement": 0.04}
        }
        
        base_metrics = platform_metrics[platform]
        
        # Calculate predicted metrics
        estimated_reach = int(base_metrics["base_reach"] * avg_engagement * 1.5)
        engagement_rate = base_metrics["base_engagement"] * avg_engagement
        confidence = min(0.9, avg_engagement + 0.1)
        
        return {
            "estimated_reach": estimated_reach,
            "engagement_rate": engagement_rate,
            "confidence": confidence,
            "optimal_windows_count": len(optimal_windows)
        }
    
    def _generate_fallback_strategy(
        self,
        platform: PlatformEnum,
        geographic_region: GeographicRegion
    ) -> PostingStrategy:
        """Generate fallback posting strategy when analysis fails"""
        
        platform_patterns = self.platform_engagement_patterns[platform]
        
        # Create basic optimal windows
        optimal_windows = []
        for hour in platform_patterns["peak_hours"][:2]:
            for day in platform_patterns["peak_days"][:3]:
                day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][day]
                
                window = OptimalPostingWindow(
                    start_time=f"{hour:02d}:00",
                    end_time=f"{(hour + 1) % 24:02d}:00",
                    peak_time=f"{hour:02d}:30",
                    day_of_week=day_name,
                    timezone="UTC",
                    engagement_score=0.7,
                    expected_reach=5000,
                    competition_level="medium",
                    audience_segments=[AudienceSegment.GENERAL],
                    reasoning=f"General optimal time for {platform.value}"
                )
                optimal_windows.append(window)
        
        # Basic audience insights
        audience_insights = AudienceInsights(
            primary_segment=AudienceSegment.GENERAL,
            geographic_distribution={"global": 1.0},
            age_distribution={"18-34": 0.6, "35+": 0.4},
            activity_patterns={"morning": 0.2, "afternoon": 0.3, "evening": 0.5},
            platform_preferences={platform.value: 1.0},
            engagement_triggers=["trending", "relatable"],
            optimal_content_length={platform.value: 60}
        )
        
        return PostingStrategy(
            platform=platform,
            optimal_windows=optimal_windows[:5],
            posting_frequency=platform_patterns["optimal_frequency"],
            content_scheduling_tips=["Post consistently", "Engage with audience"],
            audience_insights=audience_insights,
            seasonal_adjustments={"default": 1.0},
            performance_metrics={"estimated_reach": 3000, "engagement_rate": 0.06}
        )