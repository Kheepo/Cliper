# Unified LLM Service Documentation

## Overview

The Unified LLM Service is a production-ready solution that intelligently combines OpenAI and Google Gemini APIs to provide optimal clip generation for video content. The service implements intelligent routing, fallback mechanisms, caching, and comprehensive error handling.

## Architecture

### Core Components

1. **UnifiedLLMService**: Main service class that orchestrates API calls
2. **Intelligent Routing**: Task-specific provider selection
3. **Fallback Mechanisms**: Graceful degradation when APIs are unavailable
4. **Caching Layer**: Response caching with TTL for performance optimization
5. **Error Handling**: Comprehensive error handling and logging

### Provider Selection Strategy

```python
Provider Preferences by Task Type:
- Segment Selection: OpenAI → Gemini → Fallback
- Virality Analysis: Gemini → OpenAI → Fallback
- Hashtag Generation: Gemini → OpenAI → Fallback
- Content Summary: Gemini → OpenAI → Fallback
- Posting Recommendations: Gemini → OpenAI → Fallback
```

## Configuration

### Environment Variables

Add these to your `.env` file:

```env
# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key-here

# Google Gemini Configuration
GEMINI_API_KEY=your-gemini-api-key-here
```

### Model Configuration

- **OpenAI**: Uses `gpt-3.5-turbo` for cost-effectiveness and reliability
- **Gemini**: Uses `gemini-1.5-flash` for fast content analysis

## Usage Examples

### Basic Initialization

```python
from api.services.unified_llm_service import UnifiedLLMService

# Initialize the service
service = UnifiedLLMService()

# Check provider availability
print(f"OpenAI available: {service.openai_available}")
print(f"Gemini available: {service.gemini_available}")
```

### Segment Selection

```python
# Prepare video data
transcription = {
    "segments": [
        {"start": 0.0, "end": 30.0, "text": "Welcome to this tutorial"},
        {"start": 30.0, "end": 60.0, "text": "Here's the main content"}
    ],
    "text": "Welcome to this tutorial. Here's the main content."
}

scenes = [{"timestamp": 15.0, "description": "Close-up shot"}]
emotions = [{"timestamp": 20.0, "emotion": "excitement", "confidence": 0.8}]
viral_score = {"overall_score": 0.7, "factors": ["engaging_content"]}

# Select optimal segments
result = await service.select_optimal_segments(
    transcription=transcription,
    scenes=scenes,
    emotions=emotions,
    viral_score=viral_score,
    platform="tiktok",
    max_segments=2
)

print(f"Selected {len(result.segments)} segments")
print(f"Strategy: {result.selection_strategy}")
```

### Virality Analysis

```python
# Analyze viral potential
transcript = {
    "text": "Amazing cooking tutorial with secret ingredients",
    "segments": [...]
}

video_features = {
    "duration": 120.0,
    "resolution": "1080p",
    "audio_quality": "high"
}

virality_scores = await service.analyze_virality(
    transcript=transcript,
    video_features=video_features
)

for score in virality_scores:
    print(f"{score.niche}: {score.score:.2f} - {score.explanation}")
```

### Hashtag Generation

```python
# Generate hashtags
hashtags = await service.generate_hashtags(
    transcript=transcript,
    niches=["Educational/Tutorial", "Technology/Review"],
    platform="instagram"
)

for hashtag in hashtags:
    print(f"{hashtag.tag} (relevance: {hashtag.relevance_score:.2f})")
```

## API Integration

The service is integrated into the main FastAPI application with test endpoints:

### Available Endpoints

- `GET /api/llm/status` - Check LLM service status
- `POST /api/llm/test/segments` - Test segment selection
- `POST /api/llm/test/virality` - Test virality analysis
- `POST /api/llm/test/hashtags` - Test hashtag generation
- `GET /api/llm/cache/stats` - Get cache statistics

### Example API Usage

```bash
# Check service status
curl -X GET "http://localhost:8000/api/llm/status"

# Test segment selection
curl -X POST "http://localhost:8000/api/llm/test/segments" \
  -H "Content-Type: application/json" \
  -d '{
    "transcription": {"text": "Sample video content"},
    "platform": "tiktok",
    "max_segments": 2
  }'
```

## Performance Features

### Caching

- **TTL**: 1 hour (3600 seconds)
- **Key Generation**: MD5 hash of task type and parameters
- **Cache Statistics**: Available via `get_cache_stats()` method

### Async Processing

- All API calls are asynchronous for better performance
- Concurrent processing where possible
- Non-blocking fallback mechanisms

### Error Handling

- Graceful degradation when APIs are unavailable
- Comprehensive logging for debugging
- Fallback responses for all major functions

## Monitoring and Logging

### Log Levels

- **INFO**: Service initialization, provider availability
- **WARNING**: Fallback usage, API key issues
- **ERROR**: API failures, parsing errors

### Metrics Available

```python
# Get cache statistics
cache_stats = service.get_cache_stats()
print(f"Total entries: {cache_stats['total_entries']}")
print(f"Valid entries: {cache_stats['valid_entries']}")
print(f"Providers: {cache_stats['providers_available']}")
```

## Production Deployment

### Requirements

1. **API Keys**: At least one of OpenAI or Gemini API key
2. **Dependencies**: `openai`, `google-generativeai` packages
3. **Environment**: Python 3.8+ with asyncio support

### Best Practices

1. **API Key Security**: Store keys in environment variables, never in code
2. **Rate Limiting**: Monitor API usage to avoid rate limits
3. **Error Monitoring**: Set up alerts for API failures
4. **Cache Management**: Monitor cache hit rates and adjust TTL as needed

### Fallback Behavior

- **No API Keys**: Service uses rule-based fallbacks
- **API Failures**: Automatic fallback to alternative provider
- **Parsing Errors**: Default responses with appropriate warnings

## Troubleshooting

### Common Issues

1. **"API key not found"**: Check environment variables
2. **"Model not found"**: Verify API key permissions
3. **"Parsing errors"**: Check API response format

### Debug Mode

```python
import logging
logging.getLogger('api.services.unified_llm_service').setLevel(logging.DEBUG)
```

## Future Enhancements

- **Additional Providers**: Support for Claude, Cohere, etc.
- **Advanced Caching**: Redis-based distributed caching
- **Rate Limiting**: Built-in rate limiting per provider
- **Metrics Dashboard**: Real-time monitoring interface
- **A/B Testing**: Provider performance comparison

## Support

For issues or questions:
1. Check logs for error details
2. Verify API key configuration
3. Test with individual providers
4. Review fallback behavior

---

*Last updated: January 2025*
*Version: 1.0.0*