# Clip Generation API Documentation

## Overview

The Clip Generation API is a production-ready system for automatically generating video clips from longer videos using AI-powered analysis. The system provides robust error handling, monitoring, security, and scalability features.

## Table of Contents

1. [Authentication](#authentication)
2. [Core Endpoints](#core-endpoints)
3. [Monitoring Endpoints](#monitoring-endpoints)
4. [Error Handling](#error-handling)
5. [Rate Limiting](#rate-limiting)
6. [WebSocket Events](#websocket-events)
7. [Data Models](#data-models)
8. [Security](#security)
9. [Performance](#performance)
10. [Deployment](#deployment)

## Authentication

### API Key Authentication

```http
Authorization: Bearer YOUR_API_KEY
```

### JWT Token Authentication

```http
Authorization: Bearer YOUR_JWT_TOKEN
```

## Core Endpoints

### Generate Clip

Create a new clip generation task.

**Endpoint:** `POST /api/clips/generate`

**Request Body:**
```json
{
  "video_url": "https://example.com/video.mp4",
  "requirements": {
    "duration": 30,
    "platform": "youtube",
    "style": "engaging",
    "target_audience": "general",
    "include_captions": true,
    "aspect_ratio": "16:9"
  },
  "user_id": "user123",
  "priority": "normal",
  "callback_url": "https://your-app.com/webhook"
}
```

**Response:**
```json
{
  "task_id": "task_abc123",
  "status": "pending",
  "estimated_completion": "2024-01-15T10:30:00Z",
  "queue_position": 3
}
```

**Status Codes:**
- `200 OK` - Task created successfully
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Authentication required
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

### Get Task Status

Retrieve the status of a clip generation task.

**Endpoint:** `GET /api/clips/tasks/{task_id}`

**Response:**
```json
{
  "task_id": "task_abc123",
  "status": "completed",
  "progress": 100,
  "created_at": "2024-01-15T10:00:00Z",
  "completed_at": "2024-01-15T10:25:00Z",
  "result": {
    "clip_url": "https://storage.example.com/clips/clip_abc123.mp4",
    "thumbnail_url": "https://storage.example.com/thumbnails/thumb_abc123.jpg",
    "metadata": {
      "title": "Amazing Tech Innovation",
      "description": "A compelling clip about the latest technology trends",
      "tags": ["technology", "innovation", "future"],
      "duration": 30.5,
      "file_size": 15728640,
      "resolution": "1920x1080",
      "bitrate": "4000kbps"
    },
    "analytics": {
      "engagement_score": 0.85,
      "sentiment_score": 0.72,
      "topic_relevance": 0.91
    }
  },
  "error": null
}
```

### List Tasks

Retrieve a list of clip generation tasks for a user.

**Endpoint:** `GET /api/clips/tasks`

**Query Parameters:**
- `user_id` (string) - Filter by user ID
- `status` (string) - Filter by status (pending, processing, completed, failed)
- `limit` (integer) - Number of results per page (default: 20, max: 100)
- `offset` (integer) - Pagination offset (default: 0)
- `sort` (string) - Sort field (created_at, completed_at, priority)
- `order` (string) - Sort order (asc, desc)

**Response:**
```json
{
  "tasks": [
    {
      "task_id": "task_abc123",
      "status": "completed",
      "created_at": "2024-01-15T10:00:00Z",
      "video_url": "https://example.com/video.mp4",
      "requirements": {
        "duration": 30,
        "platform": "youtube"
      }
    }
  ],
  "total": 150,
  "limit": 20,
  "offset": 0,
  "has_more": true
}
```

### Cancel Task

Cancel a pending or processing task.

**Endpoint:** `DELETE /api/clips/tasks/{task_id}`

**Response:**
```json
{
  "task_id": "task_abc123",
  "status": "cancelled",
  "message": "Task cancelled successfully"
}
```

### Retry Failed Task

Retry a failed task.

**Endpoint:** `POST /api/clips/tasks/{task_id}/retry`

**Response:**
```json
{
  "task_id": "task_abc123",
  "status": "pending",
  "retry_count": 1,
  "estimated_completion": "2024-01-15T11:00:00Z"
}
```

### Batch Operations

Process multiple videos in a single request.

**Endpoint:** `POST /api/clips/batch`

**Request Body:**
```json
{
  "videos": [
    {
      "video_url": "https://example.com/video1.mp4",
      "requirements": {
        "duration": 30,
        "platform": "youtube"
      }
    },
    {
      "video_url": "https://example.com/video2.mp4",
      "requirements": {
        "duration": 60,
        "platform": "tiktok"
      }
    }
  ],
  "user_id": "user123",
  "priority": "high"
}
```

**Response:**
```json
{
  "batch_id": "batch_xyz789",
  "task_ids": ["task_abc123", "task_def456"],
  "status": "pending",
  "total_tasks": 2
}
```

## Monitoring Endpoints

### System Health

Get overall system health status.

**Endpoint:** `GET /api/monitoring/health`

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "checks": {
    "database": {
      "status": "healthy",
      "response_time": 15,
      "last_check": "2024-01-15T10:29:55Z"
    },
    "redis": {
      "status": "healthy",
      "response_time": 5,
      "last_check": "2024-01-15T10:29:55Z"
    },
    "storage": {
      "status": "healthy",
      "available_space": "85%",
      "last_check": "2024-01-15T10:29:50Z"
    },
    "llm_service": {
      "status": "healthy",
      "response_time": 250,
      "last_check": "2024-01-15T10:29:45Z"
    }
  },
  "uptime": 86400,
  "version": "1.0.0"
}
```

### System Metrics

Get system performance metrics.

**Endpoint:** `GET /api/monitoring/metrics`

**Query Parameters:**
- `time_range` (string) - Time range (1h, 6h, 24h, 7d)
- `metrics` (string) - Comma-separated list of metric names

**Response:**
```json
{
  "metrics": {
    "system.cpu.usage": {
      "current": 45.2,
      "average": 42.8,
      "peak": 78.5,
      "unit": "percent"
    },
    "system.memory.usage": {
      "current": 68.1,
      "average": 65.3,
      "peak": 82.7,
      "unit": "percent"
    },
    "app.requests.total": {
      "current": 1250,
      "rate": 15.2,
      "unit": "requests/minute"
    },
    "app.tasks.pending": {
      "current": 23,
      "average": 18.5,
      "unit": "count"
    }
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "time_range": "1h"
}
```

### Active Alerts

Get current system alerts.

**Endpoint:** `GET /api/monitoring/alerts`

**Response:**
```json
{
  "alerts": [
    {
      "id": "alert_123",
      "severity": "warning",
      "metric": "system.memory.usage",
      "message": "Memory usage above 80%",
      "value": 82.5,
      "threshold": 80.0,
      "triggered_at": "2024-01-15T10:25:00Z",
      "status": "active"
    }
  ],
  "total": 1
}
```

## Error Handling

### Error Response Format

All error responses follow a consistent format:

```json
{
  "error": {
    "code": "INVALID_VIDEO_URL",
    "message": "The provided video URL is not accessible",
    "details": {
      "url": "https://example.com/invalid.mp4",
      "status_code": 404
    },
    "timestamp": "2024-01-15T10:30:00Z",
    "request_id": "req_abc123"
  }
}
```

### Common Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `INVALID_VIDEO_URL` | Video URL is not accessible | 400 |
| `UNSUPPORTED_FORMAT` | Video format not supported | 400 |
| `VIDEO_TOO_LONG` | Video exceeds maximum duration | 400 |
| `INSUFFICIENT_CREDITS` | User has insufficient credits | 402 |
| `RATE_LIMIT_EXCEEDED` | Too many requests | 429 |
| `TASK_NOT_FOUND` | Task ID not found | 404 |
| `PROCESSING_FAILED` | Clip generation failed | 500 |
| `SERVICE_UNAVAILABLE` | External service unavailable | 503 |

## Rate Limiting

### Rate Limit Headers

All responses include rate limit information:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642248600
X-RateLimit-Window: 3600
```

### Rate Limit Tiers

| Tier | Requests/Hour | Concurrent Tasks |
|------|---------------|------------------|
| Free | 100 | 2 |
| Basic | 1,000 | 5 |
| Pro | 10,000 | 20 |
| Enterprise | Unlimited | 100 |

## WebSocket Events

### Connection

Connect to real-time updates:

```javascript
const ws = new WebSocket('wss://api.example.com/ws/tasks/{task_id}');
```

### Event Types

#### Task Status Update

```json
{
  "type": "task_status",
  "data": {
    "task_id": "task_abc123",
    "status": "processing",
    "progress": 45,
    "stage": "video_analysis",
    "estimated_completion": "2024-01-15T10:35:00Z"
  }
}
```

#### Task Completed

```json
{
  "type": "task_completed",
  "data": {
    "task_id": "task_abc123",
    "clip_url": "https://storage.example.com/clips/clip_abc123.mp4",
    "metadata": {
      "title": "Amazing Tech Innovation",
      "duration": 30.5
    }
  }
}
```

#### Task Failed

```json
{
  "type": "task_failed",
  "data": {
    "task_id": "task_abc123",
    "error": {
      "code": "PROCESSING_FAILED",
      "message": "Failed to extract audio from video"
    },
    "retry_available": true
  }
}
```

## Data Models

### Task Model

```typescript
interface Task {
  task_id: string;
  user_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
  video_url: string;
  requirements: ClipRequirements;
  result?: ClipResult;
  error?: ErrorInfo;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  priority: 'low' | 'normal' | 'high' | 'urgent';
  retry_count: number;
  max_retries: number;
}
```

### Clip Requirements

```typescript
interface ClipRequirements {
  duration: number; // seconds
  platform: 'youtube' | 'tiktok' | 'instagram' | 'twitter' | 'linkedin';
  style?: 'engaging' | 'educational' | 'entertaining' | 'professional';
  target_audience?: string;
  include_captions?: boolean;
  aspect_ratio?: '16:9' | '9:16' | '1:1' | '4:3';
  quality?: 'low' | 'medium' | 'high' | 'ultra';
  start_time?: number; // preferred start time in seconds
  end_time?: number; // preferred end time in seconds
  keywords?: string[];
  exclude_segments?: Array<{start: number; end: number}>;
}
```

### Clip Result

```typescript
interface ClipResult {
  clip_url: string;
  thumbnail_url: string;
  metadata: ClipMetadata;
  analytics: ClipAnalytics;
  processing_time: number;
  file_size: number;
}
```

## Security

### Input Validation

- All inputs are validated and sanitized
- File uploads are scanned for malware
- URLs are validated for safety
- SQL injection protection
- XSS prevention

### Data Protection

- All data encrypted in transit (TLS 1.3)
- Sensitive data encrypted at rest
- Regular security audits
- GDPR compliance
- SOC 2 Type II certified

### Access Control

- Role-based access control (RBAC)
- API key rotation
- IP whitelisting available
- Audit logging

## Performance

### Response Times

- API endpoints: < 200ms (95th percentile)
- Task creation: < 500ms
- Status queries: < 100ms
- WebSocket latency: < 50ms

### Throughput

- API requests: 10,000+ RPS
- Concurrent tasks: 1,000+
- Video processing: 100+ videos/minute

### Caching

- Redis for session data
- CDN for static assets
- Database query caching
- Result caching for duplicate requests

## Deployment

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/db
REDIS_URL=redis://host:6379/0

# External Services
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# LLM Services
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key

# Storage
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
S3_BUCKET_NAME=your-bucket

# Security
JWT_SECRET=your-jwt-secret
API_KEY_SALT=your-api-key-salt

# Monitoring
SENTRY_DSN=your-sentry-dsn
DATADOG_API_KEY=your-datadog-key

# Performance
WORKER_CONCURRENCY=4
MAX_QUEUE_SIZE=1000
REQUEST_TIMEOUT=300
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: clip-generation-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: clip-generation-api
  template:
    metadata:
      labels:
        app: clip-generation-api
    spec:
      containers:
      - name: api
        image: clip-generation-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: database-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/monitoring/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/monitoring/health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Monitoring Setup

```yaml
# Prometheus configuration
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'clip-generation-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/api/monitoring/metrics/prometheus'
    scrape_interval: 30s
```

### Load Balancer Configuration

```nginx
upstream clip_api {
    least_conn;
    server api-1:8000 max_fails=3 fail_timeout=30s;
    server api-2:8000 max_fails=3 fail_timeout=30s;
    server api-3:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name api.example.com;
    
    location / {
        proxy_pass http://clip_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
    
    location /ws/ {
        proxy_pass http://clip_api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

## Support

### Documentation

- API Reference: https://docs.example.com/api
- SDK Documentation: https://docs.example.com/sdk
- Tutorials: https://docs.example.com/tutorials

### Support Channels

- Email: support@example.com
- Discord: https://discord.gg/example
- GitHub Issues: https://github.com/example/clip-api/issues

### SLA

- Uptime: 99.9%
- Response Time: < 200ms (95th percentile)
- Support Response: < 4 hours (business hours)
- Critical Issues: < 1 hour

---

*Last updated: January 15, 2024*
*API Version: 1.0.0*