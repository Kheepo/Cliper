# Virality Clipper API Documentation

## Overview

The Virality Clipper API is an AI-powered video clipping service that analyzes videos to detect viral content potential and generates optimized clips for social media platforms.

**Base URL:** `http://localhost:8000`

**API Version:** 1.0.0

## Table of Contents

1. [Authentication](#authentication)
2. [Core Endpoints](#core-endpoints)
3. [Performance Monitoring](#performance-monitoring)
4. [Job Management](#job-management)
5. [WebSocket Connections](#websocket-connections)
6. [Data Models](#data-models)
7. [Error Handling](#error-handling)
8. [Rate Limiting](#rate-limiting)
9. [Examples](#examples)

## Authentication

Currently, the API uses user IDs for identification. No authentication tokens are required, but this should be implemented for production use.

## Core Endpoints

### Health Check

#### GET `/`
Basic API status check.

**Response:**
```json
{
  "message": "Virality Clipper API",
  "status": "running"
}
```

#### GET `/api/health`
Detailed health check.

**Response:**
```json
{
  "success": true,
  "message": "ok"
}
```

### Video Processing

#### POST `/api/videos/upload`
Upload a video file for processing.

**Content-Type:** `multipart/form-data`

**Parameters:**
- `file` (required): Video file (MP4, MOV, AVI, QuickTime)
- `user_id` (required): User identifier (UUID format)
- `target_niche` (optional): Target content niche

**Response:**
```json
{
  "job_id": "uuid-string",
  "status": "uploading",
  "estimated_time": 5
}
```

**Example cURL:**
```bash
curl -X POST "http://localhost:8000/api/videos/upload" \
  -F "file=@video.mp4" \
  -F "user_id=123e4567-e89b-12d3-a456-426614174000" \
  -F "target_niche=entertainment"
```

#### POST `/api/videos/process-url`
Process a video from a URL.

**Content-Type:** `application/x-www-form-urlencoded`

**Parameters:**
- `url` (required): Video URL
- `user_id` (required): User identifier (UUID format)
- `target_niche` (optional): Target content niche

**Response:**
```json
{
  "job_id": "uuid-string",
  "status": "pending",
  "video_title": "Processing..."
}
```

**Example cURL:**
```bash
curl -X POST "http://localhost:8000/api/videos/process-url" \
  -d "url=https://example.com/video.mp4" \
  -d "user_id=123e4567-e89b-12d3-a456-426614174000" \
  -d "target_niche=education"
```

### Job Status and Results

#### GET `/api/jobs/{job_id}/status`
Get current job processing status.

**Parameters:**
- `job_id` (path): Job identifier (UUID format)

**Response:**
```json
{
  "job_id": "uuid-string",
  "status": "processing",
  "progress": 75,
  "current_step": "Analyzing content",
  "estimated_remaining": 30.5,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:32:30Z"
}
```

**Status Values:**
- `pending`: Job queued for processing
- `uploading`: File upload in progress
- `analyzing`: Video analysis in progress
- `clipping`: Clip generation in progress
- `complete`: Processing completed successfully
- `failed`: Processing failed

#### GET `/api/jobs/{job_id}/results`
Get job results including clips and analysis.

**Parameters:**
- `job_id` (path): Job identifier (UUID format)

**Response:**
```json
{
  "original_video_url": "/path/to/original.mp4",
  "clipped_video_url": "/path/to/clip.mp4",
  "virality_scores": {
    "entertainment": {
      "score": 8.5,
      "explanation": "High engagement potential due to humor and timing"
    },
    "lifestyle": {
      "score": 6.2,
      "explanation": "Moderate appeal for lifestyle content"
    }
  },
  "hashtags": ["#viral", "#trending", "#entertainment"],
  "posting_recommendations": {
    "tiktok": {
      "optimal_times": ["18:00-20:00", "21:00-23:00"],
      "format_suggestions": {
        "aspect_ratio": "9:16",
        "duration": "15-30s"
      }
    }
  },
  "transcript": "Full transcript of the clip...",
  "clip_start_time": 45,
  "clip_duration": 30
}
```

#### GET `/api/users/{user_id}/history`
Get user's processing history.

**Parameters:**
- `user_id` (path): User identifier (UUID format)

**Response:**
```json
{
  "jobs": [
    {
      "id": "job-uuid",
      "status": "complete",
      "created_at": "2024-01-15T10:30:00Z",
      "metadata": {
        "filename": "video.mp4",
        "target_niche": "entertainment"
      }
    }
  ]
}
```

## Performance Monitoring

### System Metrics

#### GET `/api/performance/system`
Get system performance metrics.

**Response:**
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "cpu": {
    "percent": 45.2,
    "count": 8
  },
  "memory": {
    "total": 16777216000,
    "available": 8388608000,
    "percent": 50.0,
    "used": 8388608000
  },
  "disk": {
    "total": 1000000000000,
    "used": 500000000000,
    "free": 500000000000,
    "percent": 50.0
  },
  "process": {
    "memory_rss": 134217728,
    "memory_vms": 268435456,
    "cpu_percent": 12.5
  }
}
```

#### GET `/api/performance/redis`
Check Redis connection and performance.

**Response:**
```json
{
  "status": "healthy",
  "ping_time_ms": 1.23,
  "version": "7.0.0",
  "uptime_seconds": 86400,
  "memory": {
    "used_memory": 1048576,
    "used_memory_human": "1M",
    "used_memory_peak": 2097152,
    "used_memory_peak_human": "2M"
  },
  "connections": {
    "connected_clients": 5,
    "total_connections_received": 100,
    "rejected_connections": 0
  }
}
```

#### GET `/api/performance/celery`
Get Celery worker status and queue information.

**Response:**
```json
{
  "workers": {
    "active_workers": 2,
    "worker_stats": {},
    "active_tasks": {},
    "scheduled_tasks": {},
    "reserved_tasks": {}
  },
  "queues": {
    "celery": 0,
    "video_processing": 3
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### GET `/api/performance/processing-stats`
Get video processing statistics and bottlenecks.

**Response:**
```json
{
  "summary": {
    "total_jobs_24h": 50,
    "completed_jobs": 45,
    "failed_jobs": 2,
    "processing_jobs": 3,
    "success_rate": 90.0
  },
  "performance": {
    "average_processing_time_seconds": 180.5,
    "average_processing_time_minutes": 3.01
  },
  "bottlenecks": {
    "stuck_jobs": [],
    "stuck_jobs_count": 0,
    "current_step_distribution": {
      "analyzing": 2,
      "clipping": 1
    }
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Job Management

#### POST `/api/jobs/{job_id}/restart`
Restart a specific job.

**Parameters:**
- `job_id` (path): Job identifier (UUID format)

**Response:**
```json
{
  "job_id": "uuid-string",
  "status": "restarted",
  "message": "Job has been restarted successfully",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### POST `/api/jobs/{job_id}/cancel`
Cancel a specific job.

**Parameters:**
- `job_id` (path): Job identifier (UUID format)

**Response:**
```json
{
  "job_id": "uuid-string",
  "status": "cancelled",
  "message": "Job has been cancelled successfully",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### GET `/api/jobs/{job_id}/logs`
Get logs for a specific job.

**Parameters:**
- `job_id` (path): Job identifier (UUID format)
- `limit` (query, optional): Number of log entries to return (default: 50)

**Response:**
```json
{
  "job_id": "uuid-string",
  "logs": [
    {
      "timestamp": "2024-01-15T10:30:00Z",
      "level": "INFO",
      "message": "Job created - Type: upload"
    },
    {
      "timestamp": "2024-01-15T10:32:00Z",
      "level": "INFO",
      "message": "Status: complete - Processing finished"
    }
  ],
  "total_logs": 2
}
```

#### POST `/api/performance/restart-stuck-jobs`
Restart jobs that have been stuck for more than 30 minutes.

**Response:**
```json
{
  "stuck_jobs_found": 2,
  "jobs_restarted": 1,
  "restarted_job_ids": ["uuid-1"],
  "failed_restarts": [
    {
      "job_id": "uuid-2",
      "reason": "Original file not found"
    }
  ],
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## WebSocket Connections

### General WebSocket

#### WS `/ws/{client_id}`
General WebSocket connection for real-time updates.

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/client123');
```

**Subscribe to Job Updates:**
```javascript
ws.send(JSON.stringify({
  "type": "subscribe_job",
  "job_id": "uuid-string"
}));
```

**Ping/Pong:**
```javascript
ws.send(JSON.stringify({"type": "ping"}));
```

### Job-Specific WebSocket

#### WS `/ws/job/{job_id}`
WebSocket connection for specific job updates.

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/job/uuid-string');
```

**Received Messages:**
```javascript
{
  "type": "job_status",
  "job_id": "uuid-string",
  "status": "processing",
  "progress": 50,
  "current_step": "Analyzing content",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Data Models

### JobStatus
```typescript
interface JobStatus {
  job_id: string;
  status: 'pending' | 'uploading' | 'analyzing' | 'clipping' | 'complete' | 'failed';
  progress: number; // 0-100
  current_step: string;
  estimated_remaining: number; // seconds
  created_at: string; // ISO 8601
  updated_at: string; // ISO 8601
}
```

### VideoUploadResponse
```typescript
interface VideoUploadResponse {
  job_id: string;
  status: string;
  estimated_time: number; // minutes
}
```

### ViralityScore
```typescript
interface ViralityScore {
  niche: string;
  score: number; // 0-10
  explanation: string;
}
```

### JobResults
```typescript
interface JobResults {
  original_video_url: string;
  clipped_video_url: string;
  virality_scores: Record<string, {
    score: number;
    explanation: string;
  }>;
  hashtags: string[];
  posting_recommendations: Record<string, {
    optimal_times: string[];
    format_suggestions: Record<string, any>;
  }>;
  transcript: string;
  clip_start_time: number; // seconds
  clip_duration: number; // seconds
}
```

## Error Handling

### HTTP Status Codes

- `200 OK`: Request successful
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

### Error Response Format
```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common Errors

#### Invalid UUID Format
```json
{
  "detail": "Invalid job ID format. Must be a valid UUID."
}
```

#### Unsupported File Type
```json
{
  "detail": "Unsupported file type: video/webm. Allowed types: ['video/mp4', 'video/mov', 'video/avi', 'video/quicktime']"
}
```

#### Job Not Found
```json
{
  "detail": "Job not found"
}
```

#### Job Not Complete
```json
{
  "detail": "Job not complete yet"
}
```

## Rate Limiting

Currently, no rate limiting is implemented. For production use, consider implementing:

- Upload rate limiting (e.g., 10 uploads per hour per user)
- API request rate limiting (e.g., 100 requests per minute per IP)
- WebSocket connection limits

## Examples

### Complete Workflow Example

1. **Upload Video:**
```bash
curl -X POST "http://localhost:8000/api/videos/upload" \
  -F "file=@my_video.mp4" \
  -F "user_id=123e4567-e89b-12d3-a456-426614174000" \
  -F "target_niche=entertainment"
```

Response:
```json
{
  "job_id": "987fcdeb-51a2-43d1-b789-123456789abc",
  "status": "uploading",
  "estimated_time": 5
}
```

2. **Check Status:**
```bash
curl "http://localhost:8000/api/jobs/987fcdeb-51a2-43d1-b789-123456789abc/status"
```

Response:
```json
{
  "job_id": "987fcdeb-51a2-43d1-b789-123456789abc",
  "status": "analyzing",
  "progress": 60,
  "current_step": "Analyzing content for viral potential",
  "estimated_remaining": 45.0,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:31:30Z"
}
```

3. **Get Results (when complete):**
```bash
curl "http://localhost:8000/api/jobs/987fcdeb-51a2-43d1-b789-123456789abc/results"
```

### JavaScript Client Example

```javascript
class ViralityClipperClient {
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }

  async uploadVideo(file, userId, targetNiche = null) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', userId);
    if (targetNiche) {
      formData.append('target_niche', targetNiche);
    }

    const response = await fetch(`${this.baseUrl}/api/videos/upload`, {
      method: 'POST',
      body: formData
    });

    return response.json();
  }

  async getJobStatus(jobId) {
    const response = await fetch(`${this.baseUrl}/api/jobs/${jobId}/status`);
    return response.json();
  }

  async getJobResults(jobId) {
    const response = await fetch(`${this.baseUrl}/api/jobs/${jobId}/results`);
    return response.json();
  }

  connectToJob(jobId, onUpdate) {
    const ws = new WebSocket(`ws://localhost:8000/ws/job/${jobId}`);
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onUpdate(data);
    };

    return ws;
  }
}

// Usage
const client = new ViralityClipperClient();

// Upload and monitor
const fileInput = document.getElementById('video-file');
const file = fileInput.files[0];

client.uploadVideo(file, 'user-uuid', 'entertainment')
  .then(response => {
    console.log('Upload started:', response);
    
    // Connect to WebSocket for real-time updates
    const ws = client.connectToJob(response.job_id, (update) => {
      console.log('Job update:', update);
      
      if (update.status === 'complete') {
        client.getJobResults(response.job_id)
          .then(results => {
            console.log('Results:', results);
          });
      }
    });
  });
```

## Support

For technical support or questions about the API, please refer to:

- API logs: Check `/logs/` directory for detailed error logs
- Health endpoints: Use performance monitoring endpoints to check system status
- WebSocket connections: Use ping/pong for connection health checks

## Changelog

### Version 1.0.0
- Initial API release
- Video upload and URL processing
- Real-time job status updates via WebSocket
- Performance monitoring endpoints
- Job management (restart, cancel, logs)
- Comprehensive error handling