# Video Analysis Application - Technical Architecture Document

## 1. Architecture Design

```mermaid
graph TD
    A[User Browser] --> B[React Frontend Application]
    B --> C[FastAPI Backend]
    B --> G[Supabase Authentication]
    C --> D[SQLAlchemy ORM]
    D --> E[PostgreSQL Database]
    C --> F[Redis Cache]
    C --> H[Celery Task Queue]
    C --> I[File Storage System]
    H --> J[Video Processing Workers]
    J --> K[AI Analysis Services]
    
    subgraph "Frontend Layer"
        B
    end
    
    subgraph "Backend Layer"
        C
        D
        H
        J
    end
    
    subgraph "Data Layer"
        E
        F
        I
    end
    
    subgraph "External Services"
        G
        K
    end
```

## 2. Technology Description

- **Frontend**: React@18 + TypeScript + Tailwind CSS + Vite + Supabase SDK
- **Backend**: FastAPI + SQLAlchemy ORM + Celery + Redis
- **Database**: PostgreSQL with SQLAlchemy models, Redis for caching
- **Authentication**: Supabase Authentication (client-side) + Supabase Auth (server-side)
- **Task Processing**: Celery with Redis broker
- **File Storage**: Local storage with cloud migration support
- **Real-time**: WebSocket integration

## 3. Route Definitions

| Route | Purpose |
|-------|---------|
| / | Home page with upload interface and recent activity |
| /login | User authentication page |
| /register | User registration page |
| /dashboard | Real-time job monitoring and analytics |
| /history | Complete processing history with filtering |
| /settings | User preferences and account management |
| /results/:jobId | Detailed results viewing and download |
| /forgot-password | Password recovery page |

## 4. API Definitions

### 4.1 Core API

**Authentication Endpoints**
```
POST /api/auth/register
```
Request:
| Param Name | Param Type | isRequired | Description |
|------------|------------|------------|-------------|
| email | string | true | User email address |
| password | string | true | User password (min 8 characters) |
| name | string | true | User display name |

Response:
| Param Name | Param Type | Description |
|------------|------------|-------------|
| success | boolean | Registration status |
| user | object | User information |
| token | string | JWT authentication token |

```
POST /api/auth/login
```
Request:
| Param Name | Param Type | isRequired | Description |
|------------|------------|------------|-------------|
| email | string | true | User email address |
| password | string | true | User password |

Response:
| Param Name | Param Type | Description |
|------------|------------|-------------|
| success | boolean | Login status |
| user | object | User information |
| token | string | JWT authentication token |

**Job Management Endpoints**
```
POST /api/jobs/upload
```
Request:
| Param Name | Param Type | isRequired | Description |
|------------|------------|------------|-------------|
| file | file | true | Video file to process |
| settings | object | false | Processing preferences |

Response:
| Param Name | Param Type | Description |
|------------|------------|-------------|
| job_id | string | Unique job identifier |
| status | string | Initial job status |
| estimated_time | number | Estimated processing time in minutes |

```
POST /api/jobs/url
```
Request:
| Param Name | Param Type | isRequired | Description |
|------------|------------|------------|-------------|
| url | string | true | Video URL to process |
| platform | string | false | Platform type (youtube, tiktok, etc.) |
| settings | object | false | Processing preferences |

Response:
| Param Name | Param Type | Description |
|------------|------------|-------------|
| job_id | string | Unique job identifier |
| status | string | Initial job status |
| estimated_time | number | Estimated processing time in minutes |

```
GET /api/jobs/{job_id}/status
```
Response:
| Param Name | Param Type | Description |
|------------|------------|-------------|
| job_id | string | Job identifier |
| status | string | Current job status |
| progress | number | Completion percentage (0-100) |
| error_message | string | Error details if failed |
| results | object | Processing results if completed |

```
GET /api/jobs/history
```
Query Parameters:
| Param Name | Param Type | isRequired | Description |
|------------|------------|------------|-------------|
| page | number | false | Page number for pagination |
| limit | number | false | Items per page (default: 20) |
| status | string | false | Filter by job status |
| date_from | string | false | Filter from date (ISO format) |
| date_to | string | false | Filter to date (ISO format) |

Response:
| Param Name | Param Type | Description |
|------------|------------|-------------|
| jobs | array | List of user jobs |
| total | number | Total number of jobs |
| page | number | Current page number |
| pages | number | Total number of pages |

**User Management Endpoints**
```
GET /api/users/profile
```
Response:
| Param Name | Param Type | Description |
|------------|------------|-------------|
| user_id | string | User identifier |
| email | string | User email |
| name | string | User display name |
| plan | string | Subscription plan |
| usage_stats | object | Usage statistics |

```
PUT /api/users/settings
```
Request:
| Param Name | Param Type | isRequired | Description |
|------------|------------|------------|-------------|
| preferences | object | true | User preferences object |

Response:
| Param Name | Param Type | Description |
|------------|------------|-------------|
| success | boolean | Update status |
| settings | object | Updated settings |

**Results Endpoints**
```
GET /api/results/{job_id}
```
Response:
| Param Name | Param Type | Description |
|------------|------------|-------------|
| job_id | string | Job identifier |
| clips | array | Generated video clips |
| analysis | object | AI analysis results |
| download_urls | array | Download links for clips |

```
GET /api/results/{job_id}/download
```
Query Parameters:
| Param Name | Param Type | isRequired | Description |
|------------|------------|------------|-------------|
| format | string | false | Download format (mp4, zip) |
| quality | string | false | Video quality (720p, 1080p) |

Response: Binary file download

## 5. Server Architecture Diagram

```mermaid
graph TD
    A[Client Request] --> B[FastAPI Router]
    B --> C[Supabase Auth Middleware]
    C --> D[Rate Limiting Middleware]
    D --> E[Controller Layer]
    E --> F[Service Layer]
    F --> G[SQLAlchemy Repository Layer]
    G --> H[SQLAlchemy ORM]
    H --> I[(PostgreSQL)]
    
    F --> J[Cache Layer]
    J --> K[(Redis)]
    
    F --> L[Task Queue]
    L --> M[Celery Workers]
    M --> N[Video Processing]
    M --> O[AI Analysis]
    
    subgraph "API Server"
        B
        C
        D
        E
        F
        G
        H
        J
        L
    end
    
    subgraph "Background Processing"
        M
        N
        O
    end
```

## 6. Data Model

### 6.1 Data Model Definition

```mermaid
erDiagram
    USERS ||--o{ JOBS : creates
    USERS ||--o{ USER_SETTINGS : has
    JOBS ||--o{ RESULTS : produces
    JOBS ||--o{ JOB_LOGS : generates
    
    USERS {
        uuid id PK
        string auth_id UK
        string email UK
        string name
        string plan
        integer usage_count
        timestamp created_at
        timestamp updated_at
    }
    
    JOBS {
        uuid id PK
        uuid user_id FK
        string status
        string job_type
        string file_path
        string url
        integer progress
        string error_message
        jsonb settings
        timestamp created_at
        timestamp updated_at
    }
    
    RESULTS {
        uuid id PK
        uuid job_id FK
        jsonb clips_data
        jsonb analysis_data
        jsonb file_paths
        timestamp created_at
    }
    
    USER_SETTINGS {
        uuid id PK
        uuid user_id FK
        jsonb preferences
        timestamp updated_at
    }
    
    JOB_LOGS {
        uuid id PK
        uuid job_id FK
        string level
        string message
        jsonb metadata
        timestamp created_at
    }
```

### 6.2 Data Definition Language

**SQLAlchemy Models**
```python
# api/database/models.py
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    auth_id = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    plan = Column(String(20), default='free', nullable=False, index=True)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint("plan IN ('free', 'premium', 'enterprise')", name='check_plan'),
    )
```

```python
class Job(Base):
    __tablename__ = 'jobs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    status = Column(String(50), default='pending', nullable=False, index=True)
    job_type = Column(String(50), nullable=False, index=True)
    file_path = Column(String(500))
    url = Column(String(500))
    progress = Column(Integer, default=0)
    error_message = Column(Text)
    settings = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="jobs")
    results = relationship("Result", back_populates="job", cascade="all, delete-orphan")
    logs = relationship("JobLog", back_populates="job", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')", name='check_status'),
        CheckConstraint("job_type IN ('upload', 'url')", name='check_job_type'),
        CheckConstraint("progress >= 0 AND progress <= 100", name='check_progress'),
    )
```

```python
class Result(Base):
    __tablename__ = 'results'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True)
    clips_data = Column(JSON, default=[])
    analysis_data = Column(JSON, default={})
    file_paths = Column(JSON, default=[])
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    job = relationship("Job", back_populates="results")
```

```python
class UserSettings(Base):
    __tablename__ = 'user_settings'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    preferences = Column(JSON, default={})
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", back_populates="settings")
```

```python
class JobLog(Base):
    __tablename__ = 'job_logs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True)
    level = Column(String(20), nullable=False, index=True)
    message = Column(Text, nullable=False)
    metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    job = relationship("Job", back_populates="logs")
    
    __table_args__ = (
        CheckConstraint("level IN ('debug', 'info', 'warning', 'error')", name='check_level'),
    )
```

**Database Connection Setup**
```python
# api/database/connection.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import os

# Database URL configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://user:password@localhost/video_analysis"
)

# For development, you can also use SQLite:
# DATABASE_URL = "sqlite:///./video_analysis.db"

engine = create_engine(
    DATABASE_URL,
    poolclass=StaticPool if "sqlite" in DATABASE_URL else None,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=True  # Set to False in production
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create tables
def create_tables():
    from .models import Base
    Base.metadata.create_all(bind=engine)
```

**Supabase Authentication Integration**

```python
# api/auth/supabase_auth.py
from supabase import create_client, Client
from api.core.config import settings
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os

# Initialize Supabase client
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)

security = HTTPBearer()

async def verify_supabase_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        user = supabase.auth.get_user(token)
        return user
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

async def get_current_user(user_data: dict = Depends(verify_supabase_token)):
    return {
        "uid": token_data["uid"],
        "email": token_data.get("email"),
        "name": token_data.get("name", "")
    }
```