"""Enhanced OpenAPI documentation with comprehensive examples and error responses.

Provides detailed API documentation for production deployment:
- Comprehensive request/response examples
- Detailed error response schemas
- Production scenario documentation
- Security documentation
- Rate limiting information
- Performance guidelines
"""

from typing import Dict, Any, List, Optional
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import HTMLResponse
import json


def get_enhanced_openapi_schema(app: FastAPI) -> Dict[str, Any]:
    """Generate enhanced OpenAPI schema with comprehensive documentation.
    
    Args:
        app: FastAPI application instance
    
    Returns:
        Enhanced OpenAPI schema
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Clip Generation API",
        version="1.0.0",
        description=get_api_description(),
        routes=app.routes,
        servers=get_server_configurations()
    )
    
    # Add enhanced components
    openapi_schema["components"] = {
        **openapi_schema.get("components", {}),
        **get_enhanced_components()
    }
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = get_security_schemes()
    
    # Add enhanced examples
    add_enhanced_examples(openapi_schema)
    
    # Add error responses
    add_error_responses(openapi_schema)
    
    # Add rate limiting information
    add_rate_limiting_info(openapi_schema)
    
    # Add performance guidelines
    add_performance_guidelines(openapi_schema)
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


def get_api_description() -> str:
    """Get comprehensive API description."""
    return """
# Clip Generation API

A production-ready API for generating video clips with advanced features including:

## Features
- **Video Processing**: Advanced video editing and clip generation
- **Real-time Progress**: WebSocket-based progress tracking
- **Caching**: Redis-based caching for improved performance
- **Security**: JWT authentication and rate limiting
- **Monitoring**: Comprehensive health checks and metrics
- **Data Integrity**: File validation and checksums
- **Scalability**: Horizontal scaling support

## Authentication
All endpoints require JWT authentication unless specified otherwise.
Include the token in the Authorization header: `Bearer <token>`

## Rate Limiting
- **Standard endpoints**: 100 requests per minute
- **Upload endpoints**: 10 requests per minute
- **Processing endpoints**: 5 requests per minute

## Error Handling
The API uses standard HTTP status codes and provides detailed error messages.
All errors include a correlation ID for tracking.

## Performance Guidelines
- Use pagination for list endpoints
- Implement client-side caching where appropriate
- Monitor rate limits to avoid throttling
- Use WebSocket connections for real-time updates

## Support
For technical support, contact: support@clipapi.com
"""


def get_server_configurations() -> List[Dict[str, str]]:
    """Get server configurations for different environments."""
    return [
        {
            "url": "https://api.clipgen.com",
            "description": "Production server"
        },
        {
            "url": "https://staging-api.clipgen.com",
            "description": "Staging server"
        },
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        }
    ]


def get_security_schemes() -> Dict[str, Any]:
    """Get security scheme definitions."""
    return {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token for authentication"
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key for service-to-service authentication"
        }
    }


def get_enhanced_components() -> Dict[str, Any]:
    """Get enhanced component schemas."""
    return {
        "schemas": {
            "ErrorResponse": {
                "type": "object",
                "properties": {
                    "error": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Error code for programmatic handling",
                                "example": "VALIDATION_ERROR"
                            },
                            "message": {
                                "type": "string",
                                "description": "Human-readable error message",
                                "example": "Invalid input parameters"
                            },
                            "details": {
                                "type": "object",
                                "description": "Additional error details",
                                "example": {"field": "duration", "reason": "must be positive"}
                            },
                            "correlation_id": {
                                "type": "string",
                                "description": "Unique identifier for error tracking",
                                "example": "req_123456789"
                            },
                            "timestamp": {
                                "type": "string",
                                "format": "date-time",
                                "description": "Error occurrence timestamp",
                                "example": "2024-01-15T10:30:00Z"
                            }
                        },
                        "required": ["code", "message", "correlation_id", "timestamp"]
                    }
                },
                "required": ["error"]
            },
            "ValidationErrorResponse": {
                "type": "object",
                "properties": {
                    "error": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "example": "VALIDATION_ERROR"
                            },
                            "message": {
                                "type": "string",
                                "example": "Request validation failed"
                            },
                            "validation_errors": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "field": {"type": "string"},
                                        "message": {"type": "string"},
                                        "value": {"type": "string"}
                                    }
                                },
                                "example": [
                                    {
                                        "field": "duration",
                                        "message": "must be greater than 0",
                                        "value": "-5"
                                    }
                                ]
                            },
                            "correlation_id": {"type": "string"},
                            "timestamp": {"type": "string", "format": "date-time"}
                        }
                    }
                }
            },
            "RateLimitResponse": {
                "type": "object",
                "properties": {
                    "error": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "example": "RATE_LIMIT_EXCEEDED"
                            },
                            "message": {
                                "type": "string",
                                "example": "Rate limit exceeded"
                            },
                            "retry_after": {
                                "type": "integer",
                                "description": "Seconds to wait before retrying",
                                "example": 60
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Rate limit threshold",
                                "example": 100
                            },
                            "remaining": {
                                "type": "integer",
                                "description": "Remaining requests in current window",
                                "example": 0
                            },
                            "reset_time": {
                                "type": "string",
                                "format": "date-time",
                                "description": "When the rate limit resets",
                                "example": "2024-01-15T10:31:00Z"
                            }
                        }
                    }
                }
            },
            "HealthStatus": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["healthy", "degraded", "unhealthy"],
                        "example": "healthy"
                    },
                    "timestamp": {
                        "type": "string",
                        "format": "date-time",
                        "example": "2024-01-15T10:30:00Z"
                    },
                    "version": {
                        "type": "string",
                        "example": "1.0.0"
                    },
                    "uptime": {
                        "type": "number",
                        "description": "Uptime in seconds",
                        "example": 86400
                    },
                    "checks": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string"},
                                "response_time": {"type": "number"},
                                "message": {"type": "string"}
                            }
                        },
                        "example": {
                            "database": {
                                "status": "healthy",
                                "response_time": 0.05,
                                "message": "Connection successful"
                            },
                            "redis": {
                                "status": "healthy",
                                "response_time": 0.02,
                                "message": "Cache operational"
                            }
                        }
                    }
                }
            },
            "ClipRequest": {
                "type": "object",
                "properties": {
                    "video_url": {
                        "type": "string",
                        "format": "uri",
                        "description": "URL of the source video",
                        "example": "https://example.com/video.mp4"
                    },
                    "start_time": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Start time in seconds",
                        "example": 10.5
                    },
                    "duration": {
                        "type": "number",
                        "minimum": 0.1,
                        "maximum": 300,
                        "description": "Clip duration in seconds (max 5 minutes)",
                        "example": 30.0
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["mp4", "webm", "gif"],
                        "default": "mp4",
                        "description": "Output format for the clip",
                        "example": "mp4"
                    },
                    "quality": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "ultra"],
                        "default": "medium",
                        "description": "Output quality setting",
                        "example": "high"
                    },
                    "filters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "parameters": {"type": "object"}
                            }
                        },
                        "description": "Video filters to apply",
                        "example": [
                            {
                                "type": "brightness",
                                "parameters": {"value": 0.1}
                            }
                        ]
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Additional metadata for the clip",
                        "example": {
                            "title": "My Awesome Clip",
                            "tags": ["highlight", "sports"]
                        }
                    }
                },
                "required": ["video_url", "start_time", "duration"]
            },
            "ClipResponse": {
                "type": "object",
                "properties": {
                    "clip_id": {
                        "type": "string",
                        "description": "Unique identifier for the clip",
                        "example": "clip_123456789"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "processing", "completed", "failed"],
                        "example": "processing"
                    },
                    "progress": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Processing progress percentage",
                        "example": 45.5
                    },
                    "download_url": {
                        "type": "string",
                        "format": "uri",
                        "description": "URL to download the completed clip",
                        "example": "https://cdn.example.com/clips/clip_123456789.mp4"
                    },
                    "thumbnail_url": {
                        "type": "string",
                        "format": "uri",
                        "description": "URL to the clip thumbnail",
                        "example": "https://cdn.example.com/thumbnails/clip_123456789.jpg"
                    },
                    "file_size": {
                        "type": "integer",
                        "description": "File size in bytes",
                        "example": 5242880
                    },
                    "duration": {
                        "type": "number",
                        "description": "Actual clip duration in seconds",
                        "example": 30.0
                    },
                    "created_at": {
                        "type": "string",
                        "format": "date-time",
                        "example": "2024-01-15T10:30:00Z"
                    },
                    "expires_at": {
                        "type": "string",
                        "format": "date-time",
                        "description": "When the clip will be automatically deleted",
                        "example": "2024-01-22T10:30:00Z"
                    },
                    "checksum": {
                        "type": "string",
                        "description": "SHA256 checksum for file integrity",
                        "example": "a1b2c3d4e5f6..."
                    }
                },
                "required": ["clip_id", "status", "created_at"]
            }
        },
        "examples": get_request_examples(),
        "headers": {
            "X-Correlation-ID": {
                "description": "Unique request identifier for tracking",
                "schema": {"type": "string"},
                "example": "req_123456789"
            },
            "X-Rate-Limit-Remaining": {
                "description": "Number of requests remaining in current window",
                "schema": {"type": "integer"},
                "example": 95
            },
            "X-Rate-Limit-Reset": {
                "description": "Unix timestamp when rate limit resets",
                "schema": {"type": "integer"},
                "example": 1642248600
            }
        }
    }


def get_request_examples() -> Dict[str, Any]:
    """Get comprehensive request examples."""
    return {
        "BasicClipRequest": {
            "summary": "Basic clip generation",
            "description": "Simple clip generation with minimal parameters",
            "value": {
                "video_url": "https://example.com/sample-video.mp4",
                "start_time": 30.0,
                "duration": 15.0
            }
        },
        "AdvancedClipRequest": {
            "summary": "Advanced clip with filters",
            "description": "Clip generation with quality settings and filters",
            "value": {
                "video_url": "https://example.com/sample-video.mp4",
                "start_time": 45.5,
                "duration": 30.0,
                "output_format": "mp4",
                "quality": "high",
                "filters": [
                    {
                        "type": "brightness",
                        "parameters": {"value": 0.1}
                    },
                    {
                        "type": "contrast",
                        "parameters": {"value": 1.2}
                    }
                ],
                "metadata": {
                    "title": "Highlight Reel",
                    "tags": ["sports", "highlight"],
                    "description": "Best moments from the game"
                }
            }
        },
        "GifClipRequest": {
            "summary": "GIF generation",
            "description": "Generate an animated GIF from video",
            "value": {
                "video_url": "https://example.com/funny-moment.mp4",
                "start_time": 12.0,
                "duration": 3.0,
                "output_format": "gif",
                "quality": "medium",
                "filters": [
                    {
                        "type": "scale",
                        "parameters": {"width": 480, "height": 270}
                    }
                ]
            }
        }
    }


def add_enhanced_examples(openapi_schema: Dict[str, Any]) -> None:
    """Add enhanced examples to API endpoints."""
    paths = openapi_schema.get("paths", {})
    
    # Add examples for clip generation endpoint
    if "/clips" in paths and "post" in paths["/clips"]:
        paths["/clips"]["post"]["requestBody"]["content"]["application/json"]["examples"] = {
            "basic": get_request_examples()["BasicClipRequest"],
            "advanced": get_request_examples()["AdvancedClipRequest"],
            "gif": get_request_examples()["GifClipRequest"]
        }
    
    # Add response examples
    for path_data in paths.values():
        for method_data in path_data.values():
            if isinstance(method_data, dict) and "responses" in method_data:
                add_response_examples(method_data["responses"])


def add_response_examples(responses: Dict[str, Any]) -> None:
    """Add examples to response schemas."""
    if "200" in responses:
        responses["200"]["content"] = {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Successful response",
                        "value": {
                            "clip_id": "clip_abc123def456",
                            "status": "processing",
                            "progress": 25.5,
                            "created_at": "2024-01-15T10:30:00Z",
                            "expires_at": "2024-01-22T10:30:00Z"
                        }
                    }
                }
            }
        }


def add_error_responses(openapi_schema: Dict[str, Any]) -> None:
    """Add comprehensive error responses to all endpoints."""
    common_errors = {
        "400": {
            "description": "Bad Request - Invalid input parameters",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ValidationErrorResponse"},
                    "examples": {
                        "validation_error": {
                            "summary": "Validation error",
                            "value": {
                                "error": {
                                    "code": "VALIDATION_ERROR",
                                    "message": "Request validation failed",
                                    "validation_errors": [
                                        {
                                            "field": "duration",
                                            "message": "must be greater than 0",
                                            "value": "-5"
                                        }
                                    ],
                                    "correlation_id": "req_123456789",
                                    "timestamp": "2024-01-15T10:30:00Z"
                                }
                            }
                        }
                    }
                }
            }
        },
        "401": {
            "description": "Unauthorized - Invalid or missing authentication",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "examples": {
                        "missing_token": {
                            "summary": "Missing authentication token",
                            "value": {
                                "error": {
                                    "code": "MISSING_TOKEN",
                                    "message": "Authentication token is required",
                                    "correlation_id": "req_123456789",
                                    "timestamp": "2024-01-15T10:30:00Z"
                                }
                            }
                        },
                        "invalid_token": {
                            "summary": "Invalid authentication token",
                            "value": {
                                "error": {
                                    "code": "INVALID_TOKEN",
                                    "message": "Authentication token is invalid or expired",
                                    "correlation_id": "req_123456789",
                                    "timestamp": "2024-01-15T10:30:00Z"
                                }
                            }
                        }
                    }
                }
            }
        },
        "403": {
            "description": "Forbidden - Insufficient permissions",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "examples": {
                        "insufficient_permissions": {
                            "summary": "Insufficient permissions",
                            "value": {
                                "error": {
                                    "code": "INSUFFICIENT_PERMISSIONS",
                                    "message": "You don't have permission to access this resource",
                                    "correlation_id": "req_123456789",
                                    "timestamp": "2024-01-15T10:30:00Z"
                                }
                            }
                        }
                    }
                }
            }
        },
        "404": {
            "description": "Not Found - Resource does not exist",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "examples": {
                        "resource_not_found": {
                            "summary": "Resource not found",
                            "value": {
                                "error": {
                                    "code": "RESOURCE_NOT_FOUND",
                                    "message": "The requested resource was not found",
                                    "correlation_id": "req_123456789",
                                    "timestamp": "2024-01-15T10:30:00Z"
                                }
                            }
                        }
                    }
                }
            }
        },
        "429": {
            "description": "Too Many Requests - Rate limit exceeded",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/RateLimitResponse"},
                    "examples": {
                        "rate_limit_exceeded": {
                            "summary": "Rate limit exceeded",
                            "value": {
                                "error": {
                                    "code": "RATE_LIMIT_EXCEEDED",
                                    "message": "Rate limit exceeded. Please try again later.",
                                    "retry_after": 60,
                                    "limit": 100,
                                    "remaining": 0,
                                    "reset_time": "2024-01-15T10:31:00Z"
                                }
                            }
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
                    "examples": {
                        "internal_error": {
                            "summary": "Internal server error",
                            "value": {
                                "error": {
                                    "code": "INTERNAL_ERROR",
                                    "message": "An unexpected error occurred. Please try again later.",
                                    "correlation_id": "req_123456789",
                                    "timestamp": "2024-01-15T10:30:00Z"
                                }
                            }
                        }
                    }
                }
            }
        },
        "503": {
            "description": "Service Unavailable - Service temporarily unavailable",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "examples": {
                        "service_unavailable": {
                            "summary": "Service unavailable",
                            "value": {
                                "error": {
                                    "code": "SERVICE_UNAVAILABLE",
                                    "message": "Service is temporarily unavailable. Please try again later.",
                                    "correlation_id": "req_123456789",
                                    "timestamp": "2024-01-15T10:30:00Z"
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    # Add error responses to all endpoints
    paths = openapi_schema.get("paths", {})
    for path_data in paths.values():
        for method_data in path_data.values():
            if isinstance(method_data, dict) and "responses" in method_data:
                # Add common error responses
                for status_code, error_response in common_errors.items():
                    if status_code not in method_data["responses"]:
                        method_data["responses"][status_code] = error_response


def add_rate_limiting_info(openapi_schema: Dict[str, Any]) -> None:
    """Add rate limiting information to the schema."""
    if "info" not in openapi_schema:
        openapi_schema["info"] = {}
    
    openapi_schema["info"]["x-rate-limiting"] = {
        "description": "API rate limiting information",
        "limits": {
            "standard": {
                "requests": 100,
                "window": "1 minute",
                "description": "Standard endpoints"
            },
            "upload": {
                "requests": 10,
                "window": "1 minute",
                "description": "File upload endpoints"
            },
            "processing": {
                "requests": 5,
                "window": "1 minute",
                "description": "Video processing endpoints"
            }
        },
        "headers": {
            "X-Rate-Limit-Remaining": "Number of requests remaining in current window",
            "X-Rate-Limit-Reset": "Unix timestamp when rate limit resets",
            "Retry-After": "Seconds to wait before retrying (when rate limited)"
        }
    }


def add_performance_guidelines(openapi_schema: Dict[str, Any]) -> None:
    """Add performance guidelines to the schema."""
    if "info" not in openapi_schema:
        openapi_schema["info"] = {}
    
    openapi_schema["info"]["x-performance-guidelines"] = {
        "description": "Performance optimization guidelines",
        "recommendations": {
            "pagination": {
                "description": "Use pagination for list endpoints",
                "parameters": {
                    "page": "Page number (1-based)",
                    "limit": "Items per page (max 100)"
                }
            },
            "caching": {
                "description": "Implement client-side caching",
                "headers": {
                    "Cache-Control": "Caching directives",
                    "ETag": "Entity tag for cache validation",
                    "Last-Modified": "Last modification timestamp"
                }
            },
            "compression": {
                "description": "Enable compression for better performance",
                "supported": ["gzip", "deflate", "br"]
            },
            "websockets": {
                "description": "Use WebSocket connections for real-time updates",
                "endpoint": "/ws/progress/{clip_id}"
            }
        },
        "limits": {
            "file_size": "Maximum file size: 500MB",
            "video_duration": "Maximum video duration: 2 hours",
            "clip_duration": "Maximum clip duration: 5 minutes",
            "concurrent_processing": "Maximum concurrent clips: 3 per user"
        }
    }


def get_custom_swagger_ui_html(
    openapi_url: str = "/openapi.json",
    title: str = "Clip Generation API Documentation",
    swagger_js_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
    swagger_css_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
) -> HTMLResponse:
    """Get custom Swagger UI HTML with enhanced styling."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
        <link rel="stylesheet" type="text/css" href="{swagger_css_url}" />
        <style>
            .swagger-ui .topbar {{ display: none }}
            .swagger-ui .info {{ margin: 20px 0 }}
            .swagger-ui .info .title {{ color: #3b82f6 }}
            .swagger-ui .scheme-container {{ background: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0 }}
            .swagger-ui .btn.authorize {{ background-color: #3b82f6; border-color: #3b82f6 }}
            .swagger-ui .btn.authorize:hover {{ background-color: #2563eb; border-color: #2563eb }}
        </style>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="{swagger_js_url}"></script>
        <script>
            SwaggerUIBundle({{
                url: '{openapi_url}',
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.presets.standalone
                ],
                layout: "BaseLayout",
                deepLinking: true,
                showExtensions: true,
                showCommonExtensions: true,
                tryItOutEnabled: true,
                requestInterceptor: function(request) {{
                    // Add correlation ID to all requests
                    request.headers['X-Correlation-ID'] = 'req_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
                    return request;
                }}
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


def get_custom_redoc_html(
    openapi_url: str = "/openapi.json",
    title: str = "Clip Generation API Documentation",
    redoc_js_url: str = "https://cdn.jsdelivr.net/npm/redoc@2.0.0/bundles/redoc.standalone.js",
) -> HTMLResponse:
    """Get custom ReDoc HTML with enhanced styling."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ margin: 0; padding: 0; }}
        </style>
    </head>
    <body>
        <redoc spec-url='{openapi_url}' theme='{{
            "colors": {{
                "primary": {{
                    "main": "#3b82f6"
                }}
            }},
            "typography": {{
                "fontSize": "14px",
                "lineHeight": "1.5em",
                "code": {{
                    "fontSize": "13px"
                }},
                "headings": {{
                    "fontFamily": "Montserrat, sans-serif",
                    "fontWeight": "600"
                }}
            }}
        }}'></redoc>
        <script src="{redoc_js_url}"></script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


# Production scenario examples
PRODUCTION_SCENARIOS = {
    "high_volume_processing": {
        "description": "Handling high volume clip generation",
        "example": {
            "scenario": "Processing 1000+ clips per hour",
            "recommendations": [
                "Use batch processing endpoints",
                "Implement queue-based processing",
                "Monitor system resources",
                "Use horizontal scaling"
            ],
            "endpoints": ["/clips/batch", "/clips/queue", "/health/metrics"]
        }
    },
    "live_streaming": {
        "description": "Real-time clip generation from live streams",
        "example": {
            "scenario": "Creating clips from live video streams",
            "recommendations": [
                "Use WebSocket for real-time updates",
                "Implement stream buffering",
                "Handle network interruptions",
                "Use low-latency processing"
            ],
            "endpoints": ["/clips/live", "/ws/progress", "/streams"]
        }
    },
    "content_moderation": {
        "description": "Automated content moderation for clips",
        "example": {
            "scenario": "Scanning clips for inappropriate content",
            "recommendations": [
                "Integrate with moderation APIs",
                "Implement approval workflows",
                "Use content analysis",
                "Handle false positives"
            ],
            "endpoints": ["/clips/moderate", "/clips/approve", "/moderation/status"]
        }
    }
}