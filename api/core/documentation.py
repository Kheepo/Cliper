"""Enhanced OpenAPI documentation configuration.

Provides comprehensive API documentation with:
- Detailed endpoint descriptions and examples
- Error response schemas and examples
- Production-ready documentation
- Interactive API explorer enhancements
"""

from typing import Dict, Any, List, Optional
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import HTMLResponse
import json


def get_custom_openapi_schema(app: FastAPI) -> Dict[str, Any]:
    """Generate enhanced OpenAPI schema with comprehensive documentation."""
    
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Clip Generation API",
        version="2.0.0",
        description=get_api_description(),
        routes=app.routes,
        tags=get_openapi_tags()
    )
    
    # Add custom components
    openapi_schema["components"] = {
        **openapi_schema.get("components", {}),
        **get_custom_components()
    }
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = get_security_schemes()
    
    # Add servers
    openapi_schema["servers"] = get_api_servers()
    
    # Enhance paths with examples and error responses
    enhance_paths_documentation(openapi_schema)
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


def get_api_description() -> str:
    """Get comprehensive API description."""
    return """
# Clip Generation API

A production-ready API for generating video clips with advanced features including:

## 🎬 Core Features
- **Video Processing**: Advanced FFmpeg-based video processing with GPU acceleration
- **Real-time Progress**: WebSocket-based progress tracking and live updates
- **Quality Control**: Multiple quality presets and custom encoding parameters
- **Batch Processing**: Efficient batch operations for multiple clips
- **Content Analysis**: AI-powered content analysis and optimization

## 🔒 Security & Authentication
- **JWT Authentication**: Secure token-based authentication
- **Role-based Access**: Granular permissions and user roles
- **Rate Limiting**: Configurable rate limits per endpoint
- **Input Validation**: Comprehensive request validation and sanitization

## 📊 Monitoring & Observability
- **Health Checks**: Comprehensive health monitoring endpoints
- **Metrics**: Prometheus-compatible metrics and monitoring
- **Logging**: Structured logging with correlation IDs
- **Performance**: Real-time performance metrics and optimization

## 🚀 Production Features
- **Horizontal Scaling**: Load balancer support and clustering
- **Data Integrity**: File validation and checksum verification
- **Caching**: Redis-based caching for improved performance
- **Error Handling**: Comprehensive error handling and recovery

## 📖 Getting Started

### Authentication
All API endpoints require authentication. Obtain a JWT token by calling the `/auth/login` endpoint:

```bash
curl -X POST "/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "your_username", "password": "your_password"}'
```

### Basic Usage
1. **Upload a video**: Use `/clips/upload` to upload your source video
2. **Create a clip**: Call `/clips/generate` with your clip parameters
3. **Monitor progress**: Connect to WebSocket `/ws/clips/{clip_id}` for real-time updates
4. **Download result**: Retrieve the processed clip from `/clips/{clip_id}/download`

### Rate Limits
- **Standard users**: 100 requests per minute
- **Premium users**: 1000 requests per minute
- **Batch operations**: 10 concurrent operations

### Error Handling
All errors follow RFC 7807 Problem Details format with detailed error information.

### Support
- **Documentation**: Complete API reference below
- **Examples**: Interactive examples in each endpoint
- **Status Page**: Monitor API status at `/health`
"""


def get_openapi_tags() -> List[Dict[str, Any]]:
    """Get OpenAPI tags with descriptions."""
    return [
        {
            "name": "authentication",
            "description": "User authentication and authorization endpoints"
        },
        {
            "name": "clips",
            "description": "Video clip generation and management operations"
        },
        {
            "name": "uploads",
            "description": "File upload and storage management"
        },
        {
            "name": "websockets",
            "description": "Real-time communication and progress updates"
        },
        {
            "name": "health",
            "description": "System health monitoring and diagnostics"
        },
        {
            "name": "integrity",
            "description": "Data integrity validation and checksum management"
        },
        {
            "name": "monitoring",
            "description": "System metrics and performance monitoring"
        },
        {
            "name": "admin",
            "description": "Administrative operations and system management"
        }
    ]


def get_security_schemes() -> Dict[str, Any]:
    """Get security scheme definitions."""
    return {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token obtained from /auth/login endpoint"
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key for service-to-service authentication"
        }
    }


def get_api_servers() -> List[Dict[str, Any]]:
    """Get API server definitions."""
    return [
        {
            "url": "https://api.clipgen.example.com",
            "description": "Production server"
        },
        {
            "url": "https://staging-api.clipgen.example.com",
            "description": "Staging server"
        },
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        }
    ]


def get_custom_components() -> Dict[str, Any]:
    """Get custom OpenAPI components."""
    return {
        "schemas": {
            "ErrorResponse": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "description": "Error type URI",
                        "example": "https://api.clipgen.example.com/errors/validation-error"
                    },
                    "title": {
                        "type": "string",
                        "description": "Human-readable error title",
                        "example": "Validation Error"
                    },
                    "status": {
                        "type": "integer",
                        "description": "HTTP status code",
                        "example": 400
                    },
                    "detail": {
                        "type": "string",
                        "description": "Detailed error description",
                        "example": "The provided video format is not supported"
                    },
                    "instance": {
                        "type": "string",
                        "description": "Request instance identifier",
                        "example": "/clips/generate"
                    },
                    "errors": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"},
                                "message": {"type": "string"},
                                "code": {"type": "string"}
                            }
                        },
                        "description": "Detailed field-level errors"
                    },
                    "correlation_id": {
                        "type": "string",
                        "description": "Request correlation ID for tracking",
                        "example": "req_123e4567-e89b-12d3-a456-426614174000"
                    }
                },
                "required": ["type", "title", "status", "detail"]
            },
            "ProgressUpdate": {
                "type": "object",
                "properties": {
                    "clip_id": {
                        "type": "string",
                        "description": "Unique clip identifier",
                        "example": "clip_123e4567"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["queued", "processing", "completed", "failed"],
                        "description": "Current processing status"
                    },
                    "progress": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Processing progress percentage",
                        "example": 75.5
                    },
                    "stage": {
                        "type": "string",
                        "description": "Current processing stage",
                        "example": "encoding"
                    },
                    "eta_seconds": {
                        "type": "integer",
                        "description": "Estimated time to completion in seconds",
                        "example": 120
                    },
                    "message": {
                        "type": "string",
                        "description": "Human-readable status message",
                        "example": "Encoding video at 1080p quality"
                    },
                    "timestamp": {
                        "type": "string",
                        "format": "date-time",
                        "description": "Update timestamp"
                    }
                },
                "required": ["clip_id", "status", "progress", "timestamp"]
            },
            "HealthStatus": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["healthy", "degraded", "unhealthy"],
                        "description": "Overall system health status"
                    },
                    "timestamp": {
                        "type": "string",
                        "format": "date-time",
                        "description": "Health check timestamp"
                    },
                    "version": {
                        "type": "string",
                        "description": "API version",
                        "example": "2.0.0"
                    },
                    "uptime_seconds": {
                        "type": "integer",
                        "description": "System uptime in seconds",
                        "example": 86400
                    },
                    "checks": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string"},
                                "response_time_ms": {"type": "number"},
                                "message": {"type": "string"}
                            }
                        },
                        "description": "Individual component health checks"
                    }
                },
                "required": ["status", "timestamp", "version"]
            }
        },
        "examples": {
            "ClipGenerationRequest": {
                "summary": "Basic clip generation",
                "description": "Generate a 30-second clip from a video",
                "value": {
                    "source_url": "https://example.com/video.mp4",
                    "start_time": 60.0,
                    "duration": 30.0,
                    "quality": "1080p",
                    "format": "mp4",
                    "audio_enabled": True,
                    "metadata": {
                        "title": "Sample Clip",
                        "description": "A sample video clip"
                    }
                }
            },
            "BatchClipRequest": {
                "summary": "Batch clip generation",
                "description": "Generate multiple clips from the same source",
                "value": {
                    "source_url": "https://example.com/video.mp4",
                    "clips": [
                        {
                            "start_time": 0.0,
                            "duration": 15.0,
                            "quality": "720p"
                        },
                        {
                            "start_time": 30.0,
                            "duration": 20.0,
                            "quality": "1080p"
                        }
                    ],
                    "format": "mp4",
                    "parallel_processing": True
                }
            },
            "ValidationError": {
                "summary": "Validation error response",
                "description": "Example of validation error with field details",
                "value": {
                    "type": "https://api.clipgen.example.com/errors/validation-error",
                    "title": "Validation Error",
                    "status": 400,
                    "detail": "Request validation failed",
                    "instance": "/clips/generate",
                    "errors": [
                        {
                            "field": "duration",
                            "message": "Duration must be between 1 and 300 seconds",
                            "code": "VALUE_OUT_OF_RANGE"
                        },
                        {
                            "field": "quality",
                            "message": "Unsupported quality setting",
                            "code": "INVALID_VALUE"
                        }
                    ],
                    "correlation_id": "req_123e4567-e89b-12d3-a456-426614174000"
                }
            },
            "ProcessingError": {
                "summary": "Processing error response",
                "description": "Example of video processing error",
                "value": {
                    "type": "https://api.clipgen.example.com/errors/processing-error",
                    "title": "Processing Error",
                    "status": 422,
                    "detail": "Video processing failed due to unsupported codec",
                    "instance": "/clips/clip_123e4567/process",
                    "correlation_id": "req_123e4567-e89b-12d3-a456-426614174000",
                    "metadata": {
                        "ffmpeg_error": "Unsupported codec: hevc",
                        "suggested_action": "Convert video to supported format (h264, vp9)"
                    }
                }
            },
            "HealthyStatus": {
                "summary": "Healthy system status",
                "description": "Example of healthy system response",
                "value": {
                    "status": "healthy",
                    "timestamp": "2024-01-15T10:30:00Z",
                    "version": "2.0.0",
                    "uptime_seconds": 86400,
                    "checks": {
                        "database": {
                            "status": "healthy",
                            "response_time_ms": 5.2,
                            "message": "Database connection successful"
                        },
                        "redis": {
                            "status": "healthy",
                            "response_time_ms": 1.8,
                            "message": "Cache connection successful"
                        },
                        "storage": {
                            "status": "healthy",
                            "response_time_ms": 12.5,
                            "message": "Storage accessible"
                        }
                    }
                }
            }
        }
    }


def enhance_paths_documentation(openapi_schema: Dict[str, Any]) -> None:
    """Enhance path documentation with examples and error responses."""
    
    # Common error responses
    common_errors = {
        "400": {
            "description": "Bad Request - Invalid input parameters",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "examples": {
                        "validation_error": {"$ref": "#/components/examples/ValidationError"}
                    }
                }
            }
        },
        "401": {
            "description": "Unauthorized - Authentication required",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "example": {
                        "type": "https://api.clipgen.example.com/errors/unauthorized",
                        "title": "Unauthorized",
                        "status": 401,
                        "detail": "Valid authentication token required",
                        "instance": "/clips/generate"
                    }
                }
            }
        },
        "403": {
            "description": "Forbidden - Insufficient permissions",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "example": {
                        "type": "https://api.clipgen.example.com/errors/forbidden",
                        "title": "Forbidden",
                        "status": 403,
                        "detail": "Insufficient permissions for this operation",
                        "instance": "/admin/users"
                    }
                }
            }
        },
        "404": {
            "description": "Not Found - Resource does not exist",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "example": {
                        "type": "https://api.clipgen.example.com/errors/not-found",
                        "title": "Not Found",
                        "status": 404,
                        "detail": "The requested clip was not found",
                        "instance": "/clips/nonexistent_id"
                    }
                }
            }
        },
        "422": {
            "description": "Unprocessable Entity - Processing error",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "examples": {
                        "processing_error": {"$ref": "#/components/examples/ProcessingError"}
                    }
                }
            }
        },
        "429": {
            "description": "Too Many Requests - Rate limit exceeded",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "example": {
                        "type": "https://api.clipgen.example.com/errors/rate-limit",
                        "title": "Rate Limit Exceeded",
                        "status": 429,
                        "detail": "Rate limit of 100 requests per minute exceeded",
                        "instance": "/clips/generate",
                        "metadata": {
                            "retry_after_seconds": 60,
                            "limit": 100,
                            "window_seconds": 60
                        }
                    }
                }
            }
        },
        "500": {
            "description": "Internal Server Error - Unexpected server error",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "example": {
                        "type": "https://api.clipgen.example.com/errors/internal-error",
                        "title": "Internal Server Error",
                        "status": 500,
                        "detail": "An unexpected error occurred while processing your request",
                        "instance": "/clips/generate",
                        "correlation_id": "req_123e4567-e89b-12d3-a456-426614174000"
                    }
                }
            }
        }
    }
    
    # Add common error responses to all paths
    for path_data in openapi_schema.get("paths", {}).values():
        for method_data in path_data.values():
            if isinstance(method_data, dict) and "responses" in method_data:
                # Add common errors if not already present
                for error_code, error_response in common_errors.items():
                    if error_code not in method_data["responses"]:
                        method_data["responses"][error_code] = error_response


def get_custom_swagger_ui_html(
    openapi_url: str,
    title: str,
    swagger_js_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
    swagger_css_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
) -> HTMLResponse:
    """Generate custom Swagger UI HTML with enhanced features."""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
        <link rel="stylesheet" type="text/css" href="{swagger_css_url}" />
        <link rel="icon" type="image/png" href="/static/favicon.png" sizes="32x32" />
        <style>
            .swagger-ui .topbar {{ display: none }}
            .swagger-ui .info .title {{ color: #3b82f6 }}
            .swagger-ui .scheme-container {{ background: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .swagger-ui .info .description {{ font-size: 14px; line-height: 1.6; }}
            .swagger-ui .info .description h1 {{ color: #1e293b; font-size: 24px; margin-top: 30px; }}
            .swagger-ui .info .description h2 {{ color: #334155; font-size: 20px; margin-top: 25px; }}
            .swagger-ui .info .description h3 {{ color: #475569; font-size: 16px; margin-top: 20px; }}
            .swagger-ui .info .description code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 4px; }}
            .swagger-ui .info .description pre {{ background: #0f172a; color: #e2e8f0; padding: 16px; border-radius: 8px; overflow-x: auto; }}
        </style>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="{swagger_js_url}"></script>
        <script>
            const ui = SwaggerUIBundle({{
                url: '{openapi_url}',
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.presets.standalone
                ],
                layout: "StandaloneLayout",
                deepLinking: true,
                showExtensions: true,
                showCommonExtensions: true,
                tryItOutEnabled: true,
                requestInterceptor: (request) => {{
                    // Add correlation ID to all requests
                    request.headers['X-Correlation-ID'] = 'req_' + Math.random().toString(36).substr(2, 9);
                    return request;
                }},
                responseInterceptor: (response) => {{
                    // Log response for debugging
                    console.log('API Response:', response);
                    return response;
                }},
                onComplete: () => {{
                    console.log('Swagger UI loaded successfully');
                }},
                validatorUrl: null,
                docExpansion: 'list',
                operationsSorter: 'alpha',
                tagsSorter: 'alpha',
                filter: true,
                syntaxHighlight: {{
                    activated: true,
                    theme: 'agate'
                }}
            }});
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)


def get_custom_redoc_html(
    openapi_url: str,
    title: str,
    redoc_js_url: str = "https://cdn.jsdelivr.net/npm/redoc@2.0.0/bundles/redoc.standalone.js",
) -> HTMLResponse:
    """Generate custom ReDoc HTML with enhanced features."""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="icon" type="image/png" href="/static/favicon.png" sizes="32x32" />
        <style>
            body {{ margin: 0; padding: 0; }}
        </style>
    </head>
    <body>
        <redoc spec-url='{openapi_url}' 
               theme='{{
                   "colors": {{
                       "primary": {{
                           "main": "#3b82f6"
                       }}
                   }},
                   "typography": {{
                       "fontSize": "14px",
                       "lineHeight": "1.6",
                       "code": {{
                           "fontSize": "13px"
                       }}
                   }}
               }}'
               expand-responses="200,201"
               required-props-first="true"
               sort-props-alphabetically="true"
               hide-download-button="false"
               native-scrollbars="true">
        </redoc>
        <script src="{redoc_js_url}"></script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)


def setup_documentation_routes(app: FastAPI) -> None:
    """Setup custom documentation routes."""
    
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_custom_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Interactive API Documentation"
        )
    
    @app.get("/redoc", include_in_schema=False)
    async def custom_redoc_html():
        return get_custom_redoc_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - API Documentation"
        )
    
    @app.get("/openapi.json", include_in_schema=False)
    async def get_openapi_endpoint():
        return get_custom_openapi_schema(app)


def add_example_responses(app: FastAPI) -> None:
    """Add example responses to specific endpoints."""
    
    # This would be called after all routes are added
    # to enhance specific endpoints with detailed examples
    pass