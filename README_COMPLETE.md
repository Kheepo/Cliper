# Cliper - AI-Powered Video Clip Generation System

**Cliper** is a sophisticated web application that uses artificial intelligence to automatically analyze long-form videos and create optimized, viral-ready clips for social media platforms.

## 🎯 What Cliper Does

### Core Functionality
- **🎥 Video Processing**: Upload videos (MP4, MOV, AVI) up to 2GB or provide URLs from YouTube, Vimeo, TikTok
- **🧠 AI Analysis**: Uses OpenAI's LLM to analyze video content, identify engaging segments, and extract transcripts
- **📊 Virality Scoring**: Advanced algorithms identify the most viral-worthy moments based on engagement factors
- **✂️ Clip Generation**: Automatically creates optimized clips for different platforms (TikTok, YouTube, Instagram, Twitter)
- **🎨 Platform Optimization**: Each clip is optimized for specific platform requirements (aspect ratio, duration, format)
- **🏷️ Content Enhancement**: Generates titles, hashtags, and descriptions for each clip

### Supported Platforms
- **TikTok**: 9:16 aspect ratio, 15-60 seconds, optimized for viral content
- **YouTube Shorts**: 9:16 aspect ratio, 15-60 seconds, educational focus
- **Instagram Reels**: 9:16 aspect ratio, 15-90 seconds, aesthetic appeal
- **Twitter Video**: 16:9 aspect ratio, 10-140 seconds, newsworthy content

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Node.js 18+
- FFmpeg
- Redis
- OpenAI API key
- Supabase account

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/cliper.git
   cd cliper
   ```

2. **Run the setup script**
   ```bash
   python setup.py
   ```

3. **Configure environment**
   ```bash
   cp env.example .env
   # Edit .env with your actual configuration values
   ```

4. **Start Redis**
   ```bash
   # macOS
   brew services start redis
   
   # Ubuntu/Debian
   sudo systemctl start redis
   
   # Docker
   docker run -d -p 6379:6379 redis:alpine
   ```

5. **Start the application**
   ```bash
   # Development mode
   python -m uvicorn api.main:app --reload
   
   # Or using Docker
   docker-compose up --build
   ```

6. **Run integration tests**
   ```bash
   python test_system_integration.py
   ```

## 🏗️ Architecture

### Backend Services
- **Unified AI Service** (`api/services/unified_ai_service.py`): Handles transcription, virality analysis, and content generation
- **Unified Video Processor** (`api/services/unified_video_processor.py`): Manages video processing, clip creation, and thumbnails
- **Unified Task Processor** (`api/services/unified_task_processor.py`): Orchestrates the complete pipeline
- **Unified API Router** (`api/routers/unified_api.py`): Provides a single, coherent API interface

### Frontend
- **React + TypeScript**: Modern, responsive user interface
- **Supabase Auth**: Secure user authentication
- **Real-time Updates**: WebSocket connections for processing progress

### Infrastructure
- **FastAPI**: High-performance Python web framework
- **Celery**: Distributed task queue for background processing
- **Redis**: Caching and message broker
- **Supabase**: Database and authentication
- **OpenAI**: AI services for transcription and analysis

## 📡 API Endpoints

### Core Endpoints
- `POST /api/v1/videos/upload` - Upload video for processing
- `POST /api/v1/videos/process-url` - Process video from URL
- `GET /api/v1/jobs/{job_id}/status` - Get job status
- `GET /api/v1/jobs/{job_id}/results` - Get job results
- `GET /api/v1/clips/{clip_id}/download` - Download generated clip

### Management Endpoints
- `GET /api/v1/jobs` - Get user's jobs
- `GET /api/v1/clips` - Get user's clips
- `DELETE /api/v1/clips/{clip_id}` - Delete clip

### System Endpoints
- `GET /api/v1/health` - Health check
- `GET /api/v1/status` - System status
- `GET /api/v1/stats` - Processing statistics

## 🔧 Configuration

### Environment Variables

```bash
# Application
ENVIRONMENT=development
DEBUG=true
SECRET_KEY=your-secret-key

# Database (Supabase)
SUPABASE_URL=your-supabase-url
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key

# AI Services
OPENAI_API_KEY=your-openai-api-key
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini

# Redis
REDIS_URL=redis://localhost:6379/0

# File Storage
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=2147483648  # 2GB
```

### Feature Flags
```bash
FEATURE_AI_SEGMENTS=true
FEATURE_THUMBNAILS=true
FEATURE_REALTIME=true
FEATURE_AUTO_OPTIMIZE=true
FEATURE_ERROR_RECOVERY=true
FEATURE_MONITORING=true
```

## 🧪 Testing

### Run All Tests
```bash
python test_system_integration.py
```

### Individual Component Tests
```bash
# Test AI service
python -c "from api.services.unified_ai_service import unified_ai_service; import asyncio; print(asyncio.run(unified_ai_service.health_check()))"

# Test video processor
python -c "from api.services.unified_video_processor import unified_video_processor; print(unified_video_processor.health_check())"

# Test task processor
python -c "from api.services.unified_task_processor import unified_task_processor; import asyncio; print(asyncio.run(unified_task_processor.health_check()))"
```

## 🚀 Deployment

### Docker Deployment
```bash
# Build and start all services
docker-compose up --build

# Production deployment
ENVIRONMENT=production docker-compose up --build
```

### Manual Deployment
```bash
# Install dependencies
pip install -r requirements.txt
npm install

# Start services
redis-server
celery -A api.celery_unified_tasks worker --loglevel=info
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### Production Considerations
- Set up SSL certificates
- Configure proper logging
- Set up monitoring (Prometheus/Grafana)
- Configure backup strategies
- Set up load balancing

## 📊 Monitoring

### Health Checks
- `GET /api/v1/health` - Overall system health
- `GET /api/v1/status` - Detailed component status
- `GET /api/v1/stats` - Processing statistics

### Metrics
- Processing time per job
- Success/failure rates
- Resource usage (CPU, memory, disk)
- Queue lengths and processing rates

## 🔒 Security

### Authentication
- Supabase JWT tokens
- Role-based access control
- Rate limiting per user

### Data Protection
- File upload validation
- Secure file storage
- Automatic cleanup of temporary files
- Input sanitization

## 🛠️ Development

### Project Structure
```
cliper/
├── api/                    # Backend API
│   ├── services/          # Core services
│   ├── routers/           # API endpoints
│   ├── middleware/        # Authentication & security
│   └── celery_unified_tasks.py
├── src/                   # Frontend React app
├── uploads/               # File storage
├── temp/                  # Temporary files
├── logs/                  # Application logs
├── docker-compose.yml     # Docker configuration
├── requirements.txt       # Python dependencies
├── package.json          # Node.js dependencies
├── setup.py              # Setup script
└── test_system_integration.py
```

### Adding New Features
1. Create service in `api/services/`
2. Add API endpoints in `api/routers/`
3. Update task processor if needed
4. Add tests
5. Update documentation

## 🐛 Troubleshooting

### Common Issues

**FFmpeg not found**
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

**Redis connection failed**
```bash
# Check if Redis is running
redis-cli ping

# Start Redis
redis-server
```

**OpenAI API errors**
- Check API key in `.env` file
- Verify API key has sufficient credits
- Check rate limits

**Video processing fails**
- Verify video file format is supported
- Check file size limits
- Ensure sufficient disk space

### Debug Mode
```bash
DEBUG=true LOG_LEVEL=DEBUG python -m uvicorn api.main:app --reload
```

## 📈 Performance Optimization

### System Requirements
- **Minimum**: 4GB RAM, 2 CPU cores, 10GB disk space
- **Recommended**: 8GB RAM, 4 CPU cores, 50GB disk space
- **Production**: 16GB RAM, 8 CPU cores, 100GB+ disk space

### Optimization Tips
- Use GPU acceleration for video processing (NVIDIA CUDA)
- Configure Redis with appropriate memory limits
- Set up CDN for static file delivery
- Use multiple Celery workers for parallel processing

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Documentation**: Check this README and inline code comments
- **Issues**: Create an issue on GitHub
- **Discussions**: Use GitHub Discussions for questions

## 🎉 Success!

If you've followed this guide, you should now have a fully functional Cliper application that can:

✅ Accept video uploads and URLs  
✅ Transcribe audio using AI  
✅ Analyze content for viral potential  
✅ Generate optimized clips for multiple platforms  
✅ Provide real-time processing updates  
✅ Handle errors gracefully with fallback mechanisms  
✅ Scale horizontally with Celery workers  
✅ Monitor system health and performance  

**Happy clipping! 🎬✨**
