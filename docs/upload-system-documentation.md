# Video Upload System Documentation

## Overview

The enhanced video upload system provides robust, resumable file uploads with comprehensive error handling, retry logic, and resource monitoring. This system is designed to handle various network conditions and file sizes while providing excellent user experience.

## Architecture Components

### 1. Core Services

#### ResumableUploadService (`src/services/resumableUpload.ts`)
- **Purpose**: Handles chunked file uploads with resumption capability
- **Key Features**:
  - 5MB chunk size for optimal performance
  - Session persistence in localStorage
  - Automatic cleanup of expired sessions (24-hour timeout)
  - Parallel chunk uploads (max 3 concurrent)
  - Exponential backoff retry logic

#### ErrorCategorizationService (`src/services/errorCategorization.ts`)
- **Purpose**: Categorizes and handles different types of upload errors
- **Error Categories**:
  - Network errors (connection issues, timeouts)
  - Server errors (5xx status codes)
  - Authentication errors (401, 403)
  - File format/size errors
  - Rate limiting errors
  - Unknown errors

#### ResourceMonitorService (`src/services/resourceMonitor.ts`)
- **Purpose**: Monitors system resources and manages upload tasks
- **Features**:
  - Memory usage tracking
  - Active upload monitoring
  - Automatic cleanup of failed uploads
  - Performance metrics collection

### 2. Enhanced API Service (`src/services/api.ts`)

#### Upload Functions
- `uploadVideo()`: Enhanced with better error categorization
- `processUrl()`: Added retry logic with exponential backoff

#### Timeout Handling
- Upload timeout: 30 seconds
- Processing timeout: 5 minutes (300 seconds)
- Configurable timeout values

## Upload Flow

### 1. File Selection
```
User selects file → File validation → Session check
```

### 2. Upload Process
```
File chunking → Parallel upload → Progress tracking → Completion
     ↓              ↓               ↓              ↓
Resume check → Retry logic → User feedback → Cleanup
```

### 3. Error Handling Flow
```
Error occurs → Categorization → Retry strategy → User notification
     ↓              ↓              ↓              ↓
Log error → Determine cause → Apply backoff → Show message
```

## Key Features

### 1. Resumable Uploads
- **Chunking**: Files split into 5MB chunks
- **Session Management**: Upload state persisted in localStorage
- **Resume Logic**: Automatically resumes interrupted uploads
- **Cleanup**: Expired sessions removed after 24 hours

### 2. Retry Logic
- **Exponential Backoff**: Delays increase exponentially (1s, 2s, 4s, 8s...)
- **Jitter**: Random delay added to prevent thundering herd
- **Max Retries**: Configurable per error type (2-5 attempts)
- **Smart Retry**: Different strategies for different error types

### 3. Error Categorization
- **Automatic Classification**: Errors categorized by type and severity
- **User-Friendly Messages**: Technical errors translated to user language
- **Suggested Actions**: Context-aware recommendations
- **Retry Strategies**: Tailored retry logic per error category

### 4. Resource Monitoring
- **Memory Tracking**: Monitors memory usage during uploads
- **Performance Metrics**: Tracks upload speeds and success rates
- **Cleanup Mechanisms**: Automatic cleanup of failed uploads
- **Resource Limits**: Prevents system overload

## Error Handling Strategy

### Error Categories and Responses

| Category | Severity | Retryable | Max Retries | Base Delay |
|----------|----------|-----------|-------------|------------|
| Network | Medium | Yes | 5 | 1s |
| Server | High | Yes | 3 | 2s |
| Authentication | Critical | No | 0 | - |
| File Format | High | No | 0 | - |
| File Size | Medium | No | 0 | - |
| Rate Limit | Medium | Yes | 3 | 5s |
| Timeout | Medium | Yes | 5 | 1s |

### Retry Strategies

#### Network Errors
- **Max Retries**: 5
- **Backoff**: Exponential (1s → 2s → 4s → 8s → 16s)
- **Max Delay**: 30 seconds
- **Jitter**: ±50% random variation

#### Server Errors
- **Max Retries**: 3
- **Backoff**: Exponential with higher multiplier (2s → 5s → 12.5s)
- **Max Delay**: 60 seconds
- **Special Handling**: 503 Service Unavailable gets longer delays

#### Rate Limiting
- **Max Retries**: 3
- **Backoff**: Aggressive exponential (5s → 15s → 45s)
- **Max Delay**: 120 seconds
- **Respect Headers**: Uses Retry-After header when available

## User Experience Features

### 1. Progress Tracking
- **Real-time Updates**: Progress bar updates as chunks upload
- **Detailed Status**: Shows current chunk and total progress
- **Speed Indicators**: Upload speed and time remaining
- **Pause/Resume**: Users can pause and resume uploads

### 2. Error Feedback
- **Clear Messages**: Non-technical error descriptions
- **Suggested Actions**: Actionable recommendations
- **Retry Indicators**: Shows retry attempts and remaining tries
- **Context Information**: Includes file name and operation details

### 3. Status Indicators
- **Visual Icons**: Success, error, and progress icons
- **Color Coding**: Green (success), red (error), blue (progress)
- **Interactive Controls**: Pause, resume, and cancel buttons
- **Detailed Information**: Expandable error details

## Configuration

### Upload Settings
```typescript
const UPLOAD_CONFIG = {
  CHUNK_SIZE: 5 * 1024 * 1024, // 5MB
  MAX_CONCURRENT_CHUNKS: 3,
  SESSION_TIMEOUT: 24 * 60 * 60 * 1000, // 24 hours
  UPLOAD_TIMEOUT: 30000, // 30 seconds
  PROCESSING_TIMEOUT: 300000, // 5 minutes
}
```

### Retry Settings
```typescript
const RETRY_CONFIG = {
  MAX_RETRIES: {
    NETWORK: 5,
    SERVER: 3,
    RATE_LIMIT: 3,
    DEFAULT: 2
  },
  BASE_DELAYS: {
    NETWORK: 1000,
    SERVER: 2000,
    RATE_LIMIT: 5000,
    DEFAULT: 1000
  },
  MAX_DELAYS: {
    NETWORK: 30000,
    SERVER: 60000,
    RATE_LIMIT: 120000,
    DEFAULT: 10000
  }
}
```

## Testing Strategy

### Test Scenarios
1. **Small Files** (< 1MB): Quick upload validation
2. **Medium Files** (1-10MB): Chunk upload testing
3. **Large Files** (> 10MB): Full resumable upload testing
4. **Network Interruption**: Resume capability testing
5. **Server Errors**: Error handling and retry testing
6. **Rate Limiting**: Backoff strategy testing

### Test Tools
- **Test File Generator**: `createTestFile(sizeInMB, name)` function
- **Network Simulation**: Browser dev tools throttling
- **Error Simulation**: Mock server responses
- **Performance Monitoring**: Resource usage tracking

## Monitoring and Debugging

### Logging
- **Upload Events**: Start, progress, completion, errors
- **Retry Attempts**: Each retry with reason and delay
- **Resource Usage**: Memory and performance metrics
- **Error Details**: Full error context and stack traces

### Metrics
- **Success Rate**: Percentage of successful uploads
- **Average Upload Time**: Performance benchmarking
- **Error Distribution**: Most common error types
- **Retry Effectiveness**: Success rate after retries

## Future Enhancements

### Planned Features
1. **WebSocket Progress**: Real-time processing updates
2. **Background Uploads**: Service worker integration
3. **Bandwidth Adaptation**: Dynamic chunk size adjustment
4. **Offline Support**: Queue uploads when offline
5. **Advanced Analytics**: Detailed performance insights

### Performance Optimizations
1. **Compression**: Client-side video compression
2. **CDN Integration**: Direct uploads to CDN
3. **Parallel Processing**: Multiple file uploads
4. **Smart Scheduling**: Optimal upload timing

## Troubleshooting

### Common Issues

#### Upload Fails Immediately
- **Check**: Network connectivity
- **Verify**: Authentication status
- **Validate**: File format and size

#### Upload Stalls
- **Check**: Browser console for errors
- **Verify**: Server availability
- **Try**: Refresh page and resume

#### High Memory Usage
- **Check**: File size and chunk settings
- **Verify**: Multiple concurrent uploads
- **Try**: Reduce chunk size or concurrent uploads

### Debug Commands
```javascript
// Check upload sessions
localStorage.getItem('resumable_upload_sessions')

// Monitor resource usage
resourceMonitorService.getMetrics()

// Test error categorization
errorCategorizationService.categorizeError(error)
```

## Conclusion

The enhanced upload system provides a robust, user-friendly solution for video file uploads with comprehensive error handling, resumable uploads, and resource monitoring. The modular architecture allows for easy maintenance and future enhancements while ensuring reliable performance across various network conditions and file sizes.