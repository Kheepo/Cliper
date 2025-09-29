# Cliper - AI-Powered Video Clip Generation System

A production-ready, scalable video clip generation system that uses AI to intelligently select and create video segments from longer content.

## 🚀 Features

- **AI-Powered Segment Selection**: Uses LLM analysis to identify the most engaging parts of videos
- **Automated Clip Generation**: FFmpeg-based video processing with platform optimization
- **Real-time Progress Tracking**: WebSocket-based live updates during processing
- **Scalable Architecture**: Celery-based task queue with Redis backend
- **Production Ready**: Comprehensive monitoring, logging, and error recovery
- **Security First**: Input validation, file security checks, and user permission verification
- **Performance Optimized**: Memory management, disk space monitoring, and processing limits

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   API Server    │    │   AI Service    │
│   (React/Vue)   │◄──►│   (FastAPI)     │◄──►│   (OpenAI)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Database      │    │   Task Queue    │    │   File Storage  │
│   (Supabase)    │◄──►│   (Celery)      │◄──►│   (Local/S3)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Monitoring    │    │   Message Broker│    │   Media Proc.   │
│ (Prometheus)    │◄──►│   (Redis)       │◄──►│   (FFmpeg)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📋 Prerequisites

- **Docker & Docker Compose**: For containerized deployment
- **Python 3.9+**: For local development
- **Node.js 18+**: For frontend development
- **FFmpeg**: For video processing
- **Redis**: For task queue and caching
- **Supabase Account**: For database and authentication
- **OpenAI API Key**: For AI-powered analysis

## 🛠️ Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd cliper
cp .env.example .env
```

### 2. Configure Environment

Edit `.env` file with your configuration:

```bash
# Core Configuration
ENVIRONMENT=production
SECRET_KEY=your-secret-key-here
DEBUG=false

# Database (Supabase)
SUPABASE_URL=your-supabase-url
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# AI Service
OPENAI_API_KEY=your-openai-api-key

# Redis
REDIS_URL=redis://redis:6379/0

# File Storage
UPLOAD_PATH=/app/uploads
MAX_FILE_SIZE=500MB
```

### 3. Deploy with Docker

```bash
# Production deployment
python deploy.py

# Or manual deployment
docker-compose up -d
```

### 4. Verify Deployment

```bash
# Check service health
curl http://localhost:8000/health

# View logs
docker-compose logs -f app

# Monitor services
docker-compose ps
```

## 🔧 Development Setup

### Backend Development

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run database migrations
python -m alembic upgrade head

# Start development server
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Start Celery worker
celery -A api.tasks.celery_app worker --loglevel=info

# Start Celery beat (scheduler)
celery -A api.tasks.celery_app beat --loglevel=info
```

### Frontend Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

### Running Tests

```bash
# Run all tests
python run_tests.py

# Run specific test types
python run_tests.py --unit
python run_tests.py --integration
python run_tests.py --e2e

# Run with coverage
python run_tests.py --coverage

# Run tests in parallel
python run_tests.py --parallel
```

## 📊 Monitoring & Observability

### Health Checks

- **Application Health**: `GET /health`
- **API Health**: `GET /api/v1/health`
- **Database Health**: `GET /api/v1/health/database`
- **Redis Health**: `GET /api/v1/health/redis`

### Metrics & Monitoring

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **Flower (Celery)**: http://localhost:5555

### Logging

```bash
# View application logs
docker-compose logs -f app

# View worker logs
docker-compose logs -f worker

# View all logs
docker-compose logs -f

# Filter logs by level
docker-compose logs -f app | grep ERROR
```

## 🔒 Security

### Authentication & Authorization

- JWT-based authentication via Supabase
- Role-based access control (RBAC)
- API key authentication for external services

### Input Validation

- File type and size validation
- Path traversal protection
- SQL injection prevention
- XSS protection

### Security Headers

- CORS configuration
- Content Security Policy (CSP)
- HTTPS enforcement
- Rate limiting

## 🚀 Deployment

### Production Deployment

```bash
# Automated deployment
python deploy.py --config deployment.yml

# Validate environment only
python deploy.py --validate-only

# Deploy with verbose logging
python deploy.py --verbose
```

### Rollback

```bash
# Automatic rollback (if health checks fail)
python deploy.py

# Manual rollback
python deploy.py --rollback /path/to/backup
```

### Scaling

```bash
# Scale workers
docker-compose up -d --scale worker=3

# Scale application
docker-compose up -d --scale app=2
```

## 📈 Performance Optimization

### Resource Management

- **Memory**: Automatic cleanup and garbage collection
- **Disk Space**: Monitoring and cleanup of temporary files
- **CPU**: Processing limits and queue management
- **Network**: Connection pooling and request optimization

### Caching Strategy

- **Redis**: Session and temporary data caching
- **Application**: In-memory caching for frequently accessed data
- **CDN**: Static asset caching (if configured)

### Database Optimization

- **Connection Pooling**: Efficient database connections
- **Indexing**: Optimized queries with proper indexes
- **Partitioning**: Large table partitioning for performance

## 🔧 Configuration

### Environment Variables

See `.env.example` for all available configuration options.

### Feature Flags

```bash
# Enable/disable features
FEATURE_AI_ANALYSIS=true
FEATURE_THUMBNAIL_GENERATION=true
FEATURE_BATCH_PROCESSING=true
FEATURE_REAL_TIME_UPDATES=true
```

### Performance Tuning

```bash
# Worker configuration
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_PREFETCH_MULTIPLIER=1

# Memory limits
MAX_MEMORY_USAGE=80
MAX_DISK_USAGE=90

# Processing limits
MAX_CONCURRENT_JOBS=10
MAX_FILE_SIZE=500MB
```

## 🐛 Troubleshooting

### Common Issues

#### Service Won't Start

```bash
# Check Docker status
docker-compose ps

# View service logs
docker-compose logs app

# Restart services
docker-compose restart
```

#### Database Connection Issues

```bash
# Test database connection
python -c "from api.database import test_connection; test_connection()"

# Check Supabase status
curl -I https://your-project.supabase.co
```

#### Worker Not Processing Jobs

```bash
# Check Celery worker status
celery -A api.tasks.celery_app inspect active

# Restart worker
docker-compose restart worker

# Check Redis connection
redis-cli ping
```

#### High Memory Usage

```bash
# Monitor memory usage
docker stats

# Check for memory leaks
python -m memory_profiler api/main.py

# Restart services
docker-compose restart
```

### Performance Issues

#### Slow Video Processing

- Check FFmpeg configuration
- Verify hardware acceleration
- Monitor disk I/O
- Check available CPU cores

#### Database Slow Queries

- Enable query logging
- Check for missing indexes
- Analyze query execution plans
- Consider connection pooling

## 📚 API Documentation

### Core Endpoints

- **POST /api/v1/clips/generate**: Generate clips from video
- **GET /api/v1/clips/{clip_id}**: Get clip details
- **GET /api/v1/clips/{clip_id}/status**: Get generation status
- **DELETE /api/v1/clips/{clip_id}**: Delete clip

### WebSocket Events

- **clip.generation.started**: Clip generation started
- **clip.generation.progress**: Progress update
- **clip.generation.completed**: Generation completed
- **clip.generation.failed**: Generation failed

### Authentication

```bash
# JWT Token
Authorization: Bearer <jwt-token>

# API Key
X-API-Key: <api-key>
```

## 🤝 Contributing

### Development Workflow

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

### Code Standards

- **Python**: PEP 8, Black formatting
- **JavaScript**: ESLint, Prettier
- **Documentation**: Comprehensive docstrings
- **Testing**: Minimum 80% coverage

### Commit Messages

```
feat: add new clip generation feature
fix: resolve memory leak in worker
docs: update API documentation
test: add integration tests for clips
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Documentation**: Check this README and inline documentation
- **Issues**: Create an issue on GitHub
- **Discussions**: Use GitHub Discussions for questions
- **Security**: Report security issues privately

## 🗺️ Roadmap

- [ ] Multi-platform video optimization
- [ ] Advanced AI analysis features
- [ ] Batch processing improvements
- [ ] Real-time collaboration
- [ ] Mobile app support
- [ ] Cloud storage integration
- [ ] Advanced analytics dashboard

---

**Built with ❤️ for content creators and developers**