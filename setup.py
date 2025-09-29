"""
Setup script for Cliper application
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")


def check_ffmpeg():
    """Check if FFmpeg is installed."""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ FFmpeg is installed")
            return True
    except FileNotFoundError:
        pass
    
    print("❌ FFmpeg is not installed")
    print("Please install FFmpeg:")
    print("  - macOS: brew install ffmpeg")
    print("  - Ubuntu/Debian: sudo apt install ffmpeg")
    print("  - Windows: Download from https://ffmpeg.org/download.html")
    return False


def create_directories():
    """Create necessary directories."""
    directories = [
        'uploads',
        'uploads/videos',
        'uploads/clips',
        'uploads/downloaded',
        'temp',
        'logs',
        'media'
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {directory}")


def copy_env_file():
    """Copy environment file if it doesn't exist."""
    env_file = Path('.env')
    env_example = Path('env.example')
    
    if not env_file.exists() and env_example.exists():
        shutil.copy(env_example, env_file)
        print("✅ Created .env file from template")
        print("⚠️  Please edit .env file with your actual configuration values")
    elif env_file.exists():
        print("✅ .env file already exists")
    else:
        print("⚠️  No .env.example file found, creating basic .env")
        with open(env_file, 'w') as f:
            f.write("""# Cliper Application Configuration
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
APP_PORT=8000
SECRET_KEY=your-secret-key-here-change-in-production
SUPABASE_URL=your-supabase-url
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=your-openai-api-key
""")


def install_dependencies():
    """Install Python dependencies."""
    print("📦 Installing Python dependencies...")
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], check=True)
        print("✅ Python dependencies installed")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install Python dependencies: {e}")
        return False
    return True


def install_node_dependencies():
    """Install Node.js dependencies."""
    if Path('package.json').exists():
        print("📦 Installing Node.js dependencies...")
        try:
            subprocess.run(['npm', 'install'], check=True)
            print("✅ Node.js dependencies installed")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install Node.js dependencies: {e}")
            return False
    return True


def check_redis():
    """Check if Redis is running."""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("✅ Redis is running")
        return True
    except Exception:
        print("⚠️  Redis is not running or not accessible")
        print("Please start Redis:")
        print("  - macOS: brew services start redis")
        print("  - Ubuntu/Debian: sudo systemctl start redis")
        print("  - Docker: docker run -d -p 6379:6379 redis:alpine")
        return False


def run_tests():
    """Run basic tests to verify installation."""
    print("🧪 Running basic tests...")
    try:
        # Test imports
        import api.services.unified_ai_service
        import api.services.unified_video_processor
        import api.services.unified_task_processor
        print("✅ Core modules import successfully")
        
        # Test FFmpeg
        from api.services.unified_video_processor import unified_video_processor
        health = unified_video_processor.health_check()
        if health.get('status') == 'healthy':
            print("✅ Video processor is healthy")
        else:
            print("⚠️  Video processor has issues")
        
        return True
    except Exception as e:
        print(f"❌ Tests failed: {e}")
        return False


def main():
    """Main setup function."""
    print("🚀 Setting up Cliper application...")
    print("=" * 50)
    
    # Check requirements
    check_python_version()
    
    # Check FFmpeg
    ffmpeg_ok = check_ffmpeg()
    
    # Create directories
    create_directories()
    
    # Copy environment file
    copy_env_file()
    
    # Install dependencies
    deps_ok = install_dependencies()
    node_deps_ok = install_node_dependencies()
    
    # Check Redis
    redis_ok = check_redis()
    
    print("\n" + "=" * 50)
    print("📋 Setup Summary:")
    print(f"  Python dependencies: {'✅' if deps_ok else '❌'}")
    print(f"  Node.js dependencies: {'✅' if node_deps_ok else '❌'}")
    print(f"  FFmpeg: {'✅' if ffmpeg_ok else '❌'}")
    print(f"  Redis: {'✅' if redis_ok else '❌'}")
    
    if deps_ok and ffmpeg_ok:
        print("\n🧪 Running verification tests...")
        tests_ok = run_tests()
        
        if tests_ok:
            print("\n🎉 Setup completed successfully!")
            print("\n📝 Next steps:")
            print("1. Edit .env file with your actual configuration values")
            print("2. Set up your Supabase project and add credentials")
            print("3. Add your OpenAI API key")
            print("4. Start Redis: redis-server")
            print("5. Start the application: python -m uvicorn api.main:app --reload")
        else:
            print("\n⚠️  Setup completed with warnings")
            print("Some tests failed. Please check the error messages above.")
    else:
        print("\n❌ Setup failed")
        print("Please resolve the issues above and run setup again")
        sys.exit(1)


if __name__ == "__main__":
    main()
