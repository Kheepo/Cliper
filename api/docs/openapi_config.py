"""Enhanced OpenAPI documentation configuration.

Provides:
- Custom OpenAPI schema with detailed descriptions
- Comprehensive error response schemas
- Request/response examples
- Authentication documentation
- Rate limiting information
- Production-ready API documentation
"""

from typing import Dict, Any, List, Optional
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import HTMLResponse
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str
    request_id: Optional[str] = None


class ValidationErrorResponse(BaseModel):
    """Validation error response model."""
    error: str = "validation_error"
    message: str
    details: List[Dict[str, Any]]
    timestamp: str
    request_id: Optional[str] = None


class RateLimitErrorResponse(BaseModel):
    """Rate limit error response model."""
    error: str = "rate_limit_exceeded"
    message: str = "Rate limit exceeded"
    retry_after: int
    limit: int
    remaining: int
    reset_time: str
    timestamp: str


class AuthErrorResponse(BaseModel):
    """Authentication error response model."""
    error: str = "authentication_error"
    message: str
    timestamp: str
    request_id: Optional[str] = None


# Common response schemas for reuse across endpoints
COMMON_RESPONSES = {
    400: {
        "description": "Bad Request",
        "model": ErrorResponse
    },
    401: {
        "description": "Unauthorized",
        "model": AuthErrorResponse
    },
    403: {
        "description": "Forbidden",
        "model": ErrorResponse
    },
    422: {
        "description": "Validation Error",
        "model": ValidationErrorResponse
    },
    429: {
        "description": "Rate Limit Exceeded",
        "model": RateLimitErrorResponse
    },
    500: {
        "description": "Internal Server Error",
        "model": ErrorResponse
    }
}

# Authentication examples for documentation
AUTH_EXAMPLES = {
    "login_request": {
        "summary": "User login",
        "description": "Login with email and password",
        "value": {
            "email": "user@example.com",
            "password": "secure_password123"
        }
    },
    "register_request": {
        "summary": "User registration",
        "description": "Register a new user account",
        "value": {
            "email": "newuser@example.com",
            "password": "secure_password123",
            "name": "John Doe"
        }
    },
    "token_response": {
        "summary": "Authentication token",
        "description": "Successful authentication response",
        "value": {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "expires_in": 3600,
            "refresh_token": "refresh_token_here"
        }
    },
    "auth_response": {
        "user": {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "auth_id": "auth_123456789",
            "email": "user@example.com",
            "display_name": "John Doe",
            "photo_url": "https://example.com/avatar.jpg",
            "created_at": "2024-01-15T10:30:00Z",
            "last_login": "2024-01-15T10:30:00Z"
        },
        "tokens": {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": None
        },
        "message": "Token verified successfully"
    },
    "user_response": {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "auth_id": "auth_123456789",
        "email": "user@example.com",
        "display_name": "John Doe",
        "photo_url": "https://example.com/avatar.jpg",
        "created_at": "2024-01-15T10:30:00Z",
        "last_login": "2024-01-15T10:30:00Z"
     }
}

# Job examples for documentation
JOB_EXAMPLES = {
    "job_request": {
        "video_id": "550e8400-e29b-41d4-a716-446655440000",
        "duration": 30,
        "platform": "youtube",
        "style": "engaging",
        "target_audience": "general",
        "content_type": "educational",
        "custom_prompt": "Focus on the most exciting moments",
        "quality_settings": {
            "resolution": "1080p",
            "bitrate": 5000,
            "fps": 30
        }
    },
    "job_response": {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "video_id": "550e8400-e29b-41d4-a716-446655440000",
        "user_id": "user_123",
        "status": "processing",
        "progress": 0,
        "duration": 30,
        "platform": "youtube",
        "style": "engaging",
        "created_at": "2024-01-15T10:30:00Z",
        "updated_at": "2024-01-15T10:30:00Z",
        "estimated_completion": "2024-01-15T10:35:00Z",
        "job_id": "job_456"
    },
    "job_status_response": {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "status": "completed",
        "progress": 100,
        "result": {
            "clip_url": "https://api.example.com/clips/123e4567-e89b-12d3-a456-426614174000/download",
            "thumbnail_url": "https://api.example.com/clips/123e4567-e89b-12d3-a456-426614174000/thumbnail",
            "duration": 30.5,
            "file_size": 15728640
        },
        "created_at": "2024-01-15T10:30:00Z",
         "updated_at": "2024-01-15T10:35:00Z",
         "completed_at": "2024-01-15T10:35:00Z"
     },
     "job_create": {
         "video_id": "550e8400-e29b-41d4-a716-446655440000",
         "duration": 30,
         "platform": "youtube",
         "style": "engaging",
         "target_audience": "general",
         "content_type": "educational",
         "custom_prompt": "Focus on the most exciting moments"
     },
     "job_url_create": {
         "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
         "duration": 30,
         "platform": "youtube",
         "style": "engaging",
         "target_audience": "general",
         "content_type": "educational",
         "custom_prompt": "Focus on the most exciting moments"
     },
     "job_result": {
         "id": "123e4567-e89b-12d3-a456-426614174000",
         "status": "completed",
         "progress": 100,
         "result_url": "https://api.example.com/clips/123e4567-e89b-12d3-a456-426614174000/download",
         "thumbnail_url": "https://api.example.com/clips/123e4567-e89b-12d3-a456-426614174000/thumbnail",
         "duration": 30.5,
         "file_size": 15728640,
         "created_at": "2024-01-15T10:30:00Z",
         "completed_at": "2024-01-15T10:35:00Z"
     }
}

# Clip examples for documentation
CLIP_EXAMPLES = {
    "clip_create": {
        "video_id": "550e8400-e29b-41d4-a716-446655440000",
        "start_time": 10.5,
        "end_time": 40.5,
        "title": "Amazing Moment",
        "description": "The most exciting part of the video",
        "tags": ["highlight", "exciting", "viral"]
    },
    "clip_request": {
        "video_id": "550e8400-e29b-41d4-a716-446655440000",
        "start_time": 10.5,
        "end_time": 40.5,
        "title": "Amazing Moment",
        "description": "The most exciting part of the video",
        "tags": ["highlight", "exciting", "viral"]
    },
    "clip_response": {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "video_id": "550e8400-e29b-41d4-a716-446655440000",
        "user_id": "user_123",
        "title": "Amazing Moment",
        "description": "The most exciting part of the video",
        "start_time": 10.5,
        "end_time": 40.5,
        "duration": 30.0,
        "file_url": "https://api.example.com/clips/123e4567-e89b-12d3-a456-426614174000/download",
        "thumbnail_url": "https://api.example.com/clips/123e4567-e89b-12d3-a456-426614174000/thumbnail",
        "file_size": 15728640,
        "status": "completed",
        "created_at": "2024-01-15T10:30:00Z",
        "updated_at": "2024-01-15T10:35:00Z",
        "tags": ["highlight", "exciting", "viral"]
    },
    "clip_list_response": {
        "clips": [
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "title": "Amazing Moment",
                "duration": 30.0,
                "thumbnail_url": "https://api.example.com/clips/123e4567-e89b-12d3-a456-426614174000/thumbnail",
                "created_at": "2024-01-15T10:30:00Z",
                "status": "completed"
            }
        ],
        "total": 1,
        "page": 1,
        "per_page": 10,
        "total_pages": 1
     },
     "clip_update": {
         "title": "Updated Amazing Moment",
         "description": "Updated description for the most exciting part",
         "tags": ["highlight", "exciting", "viral", "updated"]
     },
     "clips_summary": {
         "total_clips": 25,
         "total_duration": 750.5,
         "average_duration": 30.02,
         "most_popular_tags": ["highlight", "exciting", "viral"],
         "clips_by_status": {
             "completed": 20,
             "processing": 3,
             "failed": 2
         },
         "recent_activity": {
             "clips_created_today": 5,
             "clips_created_this_week": 15
         }
     },
     "clip_generation": {
         "job_id": "123e4567-e89b-12d3-a456-426614174000",
         "video_id": "550e8400-e29b-41d4-a716-446655440000",
         "status": "processing",
         "progress": 45,
         "estimated_completion": "2024-01-15T10:35:00Z",
         "clips_generated": 2,
         "clips_remaining": 3,
         "current_stage": "video_analysis",
         "processing_time": 120.5
     }
}


def get_custom_openapi_schema(app: FastAPI) -> Dict[str, Any]:
    """Generate custom OpenAPI schema with enhanced documentation."""
    
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Clip Generation API",
        version="1.0.0",
        description="""
        # Clip Generation API
        
        A comprehensive API for generating video clips with AI-powered content analysis.
        
        ## Features
        
        - **Video Processing**: Upload and process videos with advanced compression and optimization
        - **AI-Powered Analysis**: Automatic content analysis and clip generation using LLM services
        - **Real-time Updates**: WebSocket integration for live progress tracking
        - **User Management**: Secure authentication and user management
        - **Performance Monitoring**: Built-in metrics and monitoring capabilities
        - **Scalable Architecture**: Production-ready with load balancing and caching
        
        ## Authentication
        
        This API supports two authentication methods:
        
        1. **Bearer Token**: Use JWT tokens for user authentication
        2. **API Key**: Use API keys for service-to-service communication
        
        ## Rate Limiting
        
        API requests are rate-limited to ensure fair usage:
        
        - **Authenticated users**: 1000 requests per hour
        - **Anonymous users**: 100 requests per hour
        - **Premium users**: 5000 requests per hour
        
        Rate limit headers are included in all responses:
        - `X-RateLimit-Limit`: Request limit per window
        - `X-RateLimit-Remaining`: Remaining requests in current window
        - `X-RateLimit-Reset`: Time when the rate limit resets
        
        ## Error Handling
        
        The API uses standard HTTP status codes and returns detailed error information:
        
        - `400 Bad Request`: Invalid request parameters
        - `401 Unauthorized`: Authentication required
        - `403 Forbidden`: Insufficient permissions
        - `404 Not Found`: Resource not found
        - `422 Unprocessable Entity`: Validation errors
        - `429 Too Many Requests`: Rate limit exceeded
        - `500 Internal Server Error`: Server error
        - `503 Service Unavailable`: Service temporarily unavailable
        
        ## WebSocket Integration
        
        Real-time updates are available through WebSocket connections:
        
        - **Job Updates**: `/ws/jobs/{job_id}` - Get real-time job progress
        - **User Notifications**: `/ws/user/{user_id}` - Receive user-specific notifications
        - **System Monitoring**: `/ws/monitoring` - System metrics and alerts
        
        ## Performance
        
        The API is optimized for high performance:
        
        - **Caching**: Redis-based caching for frequently accessed data
        - **Connection Pooling**: Efficient database and external service connections
        - **Async Processing**: Non-blocking operations for better throughput
        - **Load Balancing**: Support for horizontal scaling
        
        ## Support
        
        For support and documentation:
        - **API Documentation**: Available at `/docs` and `/redoc`
        - **Health Check**: `/health` endpoint for service monitoring
        - **Metrics**: `/metrics` endpoint for Prometheus integration
        """,
        routes=app.routes,
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token for user authentication"
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key for service authentication"
        }
    }
    
    # Add common response schemas
    openapi_schema["components"]["schemas"].update({
        "ErrorResponse": {
            "type": "object",
            "properties": {
                "error": {"type": "string", "description": "Error code"},
                "message": {"type": "string", "description": "Human-readable error message"},
                "details": {"type": "object", "description": "Additional error details"},
                "timestamp": {"type": "string", "format": "date-time"},
                "request_id": {"type": "string", "description": "Unique request identifier"}
            },
            "required": ["error", "message", "timestamp"]
        },
        "ValidationErrorResponse": {
            "type": "object",
            "properties": {
                "error": {"type": "string", "default": "validation_error"},
                "message": {"type": "string"},
                "details": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {"type": "string"},
                            "message": {"type": "string"},
                            "value": {"type": "string"}
                        }
                    }
                },
                "timestamp": {"type": "string", "format": "date-time"},
                "request_id": {"type": "string"}
            }
        },
        "RateLimitErrorResponse": {
            "type": "object",
            "properties": {
                "error": {"type": "string", "default": "rate_limit_exceeded"},
                "message": {"type": "string", "default": "Rate limit exceeded"},
                "retry_after": {"type": "integer", "description": "Seconds to wait before retrying"},
                "limit": {"type": "integer", "description": "Request limit per window"},
                "remaining": {"type": "integer", "description": "Remaining requests"},
                "reset_time": {"type": "string", "format": "date-time"},
                "timestamp": {"type": "string", "format": "date-time"}
            }
        }
    })
    
    # Add common response headers
    common_headers = {
        "X-Request-ID": {
            "description": "Unique request identifier",
            "schema": {"type": "string"}
        },
        "X-RateLimit-Limit": {
            "description": "Request limit per window",
            "schema": {"type": "integer"}
        },
        "X-RateLimit-Remaining": {
            "description": "Remaining requests in current window",
            "schema": {"type": "integer"}
        },
        "X-RateLimit-Reset": {
            "description": "Time when rate limit resets (Unix timestamp)",
            "schema": {"type": "integer"}
        }
    }
    
    # Add common error responses to all endpoints
    for path_item in openapi_schema["paths"].values():
        for operation in path_item.values():
            if isinstance(operation, dict) and "responses" in operation:
                # Add common error responses
                operation["responses"].update({
                    "400": {
                        "description": "Bad Request",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                        "headers": common_headers
                    },
                    "401": {
                        "description": "Unauthorized",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                        "headers": common_headers
                    },
                    "403": {
                        "description": "Forbidden",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                        "headers": common_headers
                    },
                    "422": {
                        "description": "Validation Error",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ValidationErrorResponse"}
                            }
                        },
                        "headers": common_headers
                    },
                    "429": {
                        "description": "Rate Limit Exceeded",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/RateLimitErrorResponse"}
                            }
                        },
                        "headers": common_headers
                    },
                    "500": {
                        "description": "Internal Server Error",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                        "headers": common_headers
                    }
                })
                
                # Add common headers to success responses
                for status_code, response in operation["responses"].items():
                    if status_code.startswith("2") and "headers" not in response:
                        response["headers"] = common_headers
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


def get_api_examples() -> Dict[str, Any]:
    """Get comprehensive API examples for documentation."""
    
    return {
        "clip_generation": {
            "request": {
                "video_id": "550e8400-e29b-41d4-a716-446655440000",
                "duration": 30,
                "platform": "youtube",
                "style": "engaging",
                "target_audience": "general",
                "content_type": "educational",
                "custom_prompt": "Focus on the most exciting moments",
                "quality_settings": {
                    "resolution": "1080p",
                    "bitrate": 5000,
                    "fps": 30
                }
            },
            "response": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "video_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user_123",
                "status": "processing",
                "progress": 0,
                "duration": 30,
                "platform": "youtube",
                "style": "engaging",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
                "estimated_completion": "2024-01-15T10:35:00Z",
                "job_id": "job_456"
            }
        },
        "authentication": {
            "login_request": {
                "email": "user@example.com",
                "password": "secure_password123"
            },
            "login_response": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600,
                "refresh_token": "refresh_token_here",
                "user": {
                    "id": "user_123",
                    "email": "user@example.com",
                    "name": "John Doe",
                    "plan": "premium"
                }
            }
        },
        "websocket_messages": {
            "job_progress": {
                "type": "job_progress",
                "job_id": "job_456",
                "progress": 75,
                "status": "processing",
                "stage": "generating_clips",
                "estimated_completion": "2024-01-15T10:33:00Z",
                "message": "Generating clip 3 of 4"
            },
            "job_completed": {
                "type": "job_completed",
                "job_id": "job_456",
                "status": "completed",
                "result": {
                    "clip_id": "123e4567-e89b-12d3-a456-426614174000",
                    "download_url": "https://api.example.com/clips/123e4567-e89b-12d3-a456-426614174000/download",
                    "thumbnail_url": "https://api.example.com/clips/123e4567-e89b-12d3-a456-426614174000/thumbnail",
                    "duration": 30.5,
                    "file_size": 15728640
                }
            },
            "error": {
                "type": "error",
                "job_id": "job_456",
                "error_code": "processing_failed",
                "message": "Video processing failed due to unsupported format",
                "details": {
                    "error_type": "format_error",
                    "supported_formats": ["mp4", "avi", "mov", "mkv"]
                }
            }
        },
        "analytics": {
            "user_analytics": {
                "user_id": "user_123",
                "period": "last_30_days",
                "total_clips": 45,
                "total_duration": 1350,
                "most_used_platform": "youtube",
                "average_clip_duration": 30,
                "success_rate": 95.6,
                "popular_styles": [
                    {"style": "engaging", "count": 20},
                    {"style": "professional", "count": 15},
                    {"style": "casual", "count": 10}
                ]
            },
            "system_metrics": {
                "timestamp": "2024-01-15T10:30:00Z",
                "active_users": 1250,
                "processing_jobs": 23,
                "completed_jobs_today": 456,
                "average_processing_time": 180,
                "system_load": {
                    "cpu_percent": 65.2,
                    "memory_percent": 78.5,
                    "disk_percent": 45.1
                },
                "queue_status": {
                    "pending": 12,
                    "processing": 23,
                    "failed": 2
                }
            }
        },
        "error_responses": {
            "validation_error": {
                "error": "validation_error",
                "message": "Request validation failed",
                "details": [
                    {
                        "field": "duration",
                        "message": "Duration must be between 10 and 300 seconds",
                        "value": "5"
                    },
                    {
                        "field": "platform",
                        "message": "Platform must be one of: youtube, tiktok, instagram",
                        "value": "invalid_platform"
                    }
                ],
                "timestamp": "2024-01-15T10:30:00Z",
                "request_id": "req_789"
            },
            "rate_limit_error": {
                "error": "rate_limit_exceeded",
                "message": "Rate limit exceeded",
                "retry_after": 3600,
                "limit": 1000,
                "remaining": 0,
                "reset_time": "2024-01-15T11:30:00Z",
                "timestamp": "2024-01-15T10:30:00Z"
            },
            "authentication_error": {
                "error": "authentication_error",
                "message": "Invalid or expired token",
                "timestamp": "2024-01-15T10:30:00Z",
                "request_id": "req_789"
            },
            "server_error": {
                "error": "internal_server_error",
                "message": "An unexpected error occurred",
                "details": {
                    "error_id": "err_123",
                    "support_contact": "support@example.com"
                },
                "timestamp": "2024-01-15T10:30:00Z",
                "request_id": "req_789"
            }
        }
    }


def setup_enhanced_docs(app: FastAPI):
    """Setup enhanced API documentation with custom UI."""
    
    # Set custom OpenAPI schema
    app.openapi = lambda: get_custom_openapi_schema(app)
    
    # Custom Swagger UI
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Interactive API Documentation",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
            swagger_ui_parameters={
                "deepLinking": True,
                "displayRequestDuration": True,
                "docExpansion": "none",
                "operationsSorter": "method",
                "filter": True,
                "showExtensions": True,
                "showCommonExtensions": True,
                "tryItOutEnabled": True
            }
        )
    
    # Custom ReDoc
    @app.get("/redoc", include_in_schema=False)
    async def redoc_html():
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - API Documentation",
            redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.0.0/bundles/redoc.standalone.js",
        )
    
    # API Examples endpoint
    @app.get("/api/examples", include_in_schema=False)
    async def get_api_examples_endpoint():
        """Get comprehensive API examples."""
        return get_api_examples()
    
    # Enhanced documentation page
    @app.get("/api-guide", response_class=HTMLResponse, include_in_schema=False)
    async def api_guide():
        """Enhanced API guide with examples and best practices."""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Clip Generation API - Developer Guide</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; margin: 0; padding: 20px; background: #f8f9fa; }
                .container { max-width: 1200px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                h1, h2, h3 { color: #2c3e50; }
                .code-block { background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; margin: 15px 0; }
                .endpoint { background: #e8f5e8; padding: 15px; border-left: 4px solid #28a745; margin: 15px 0; }
                .warning { background: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 15px 0; }
                .error { background: #f8d7da; padding: 15px; border-left: 4px solid #dc3545; margin: 15px 0; }
                .nav { background: #2c3e50; color: white; padding: 15px; margin: -40px -40px 40px -40px; border-radius: 8px 8px 0 0; }
                .nav a { color: #ecf0f1; text-decoration: none; margin-right: 20px; }
                .nav a:hover { color: #3498db; }
                table { width: 100%; border-collapse: collapse; margin: 15px 0; }
                th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
                th { background-color: #f2f2f2; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="nav">
                    <h2 style="margin: 0; display: inline-block;">Clip Generation API - Developer Guide</h2>
                    <div style="float: right;">
                        <a href="/docs">Swagger UI</a>
                        <a href="/redoc">ReDoc</a>
                        <a href="/api/examples">Examples</a>
                    </div>
                    <div style="clear: both;"></div>
                </div>
                
                <h2>Quick Start</h2>
                <p>Get started with the Clip Generation API in minutes:</p>
                
                <div class="endpoint">
                    <h3>1. Authentication</h3>
                    <div class="code-block">
POST /api/auth/login
Content-Type: application/json

{
  "email": "your@email.com",
  "password": "your_password"
}
                    </div>
                </div>
                
                <div class="endpoint">
                    <h3>2. Upload Video</h3>
                    <div class="code-block">
POST /api/videos/upload
Authorization: Bearer YOUR_TOKEN
Content-Type: multipart/form-data

file: [video_file]
title: "My Video"
description: "Video description"
                    </div>
                </div>
                
                <div class="endpoint">
                    <h3>3. Generate Clip</h3>
                    <div class="code-block">
POST /api/clips/generate
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "video_id": "video_uuid",
  "duration": 30,
  "platform": "youtube",
  "style": "engaging"
}
                    </div>
                </div>
                
                <h2>Rate Limits</h2>
                <table>
                    <tr><th>User Type</th><th>Requests/Hour</th><th>Concurrent Jobs</th></tr>
                    <tr><td>Free</td><td>100</td><td>1</td></tr>
                    <tr><td>Premium</td><td>1,000</td><td>5</td></tr>
                    <tr><td>Enterprise</td><td>10,000</td><td>20</td></tr>
                </table>
                
                <h2>WebSocket Integration</h2>
                <p>Get real-time updates on your clip generation jobs:</p>
                <div class="code-block">
const ws = new WebSocket('wss://api.example.com/ws/jobs/YOUR_JOB_ID');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Progress:', data.progress + '%');
};
                </div>
                
                <h2>Error Handling</h2>
                <div class="warning">
                    <strong>Best Practice:</strong> Always check the response status and handle errors appropriately.
                </div>
                
                <h3>Common Error Codes</h3>
                <table>
                    <tr><th>Code</th><th>Description</th><th>Action</th></tr>
                    <tr><td>400</td><td>Bad Request</td><td>Check request parameters</td></tr>
                    <tr><td>401</td><td>Unauthorized</td><td>Refresh authentication token</td></tr>
                    <tr><td>429</td><td>Rate Limited</td><td>Wait and retry after rate limit reset</td></tr>
                    <tr><td>503</td><td>Service Unavailable</td><td>Retry with exponential backoff</td></tr>
                </table>
                
                <h2>SDKs and Libraries</h2>
                <p>Official SDKs available for:</p>
                <ul>
                    <li><strong>Python:</strong> <code>pip install clip-generation-sdk</code></li>
                    <li><strong>JavaScript:</strong> <code>npm install @clipgen/sdk</code></li>
                    <li><strong>Go:</strong> <code>go get github.com/clipgen/go-sdk</code></li>
                </ul>
                
                <h2>Support</h2>
                <p>Need help? Contact us:</p>
                <ul>
                    <li><strong>Documentation:</strong> <a href="/docs">/docs</a></li>
                    <li><strong>Status Page:</strong> <a href="/health">System Status</a></li>
                    <li><strong>Support:</strong> support@example.com</li>
                </ul>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)