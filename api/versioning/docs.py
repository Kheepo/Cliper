"""API Documentation Generator for Cliper Application.

This module provides comprehensive API documentation generation with versioning support,
interactive documentation, and enterprise-grade features.
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from .models import APIVersion, VersionInfo, APIDocumentation


class APIDocumentationGenerator:
    """Generates comprehensive API documentation with versioning support."""
    
    def __init__(self, app: FastAPI, title: str = "Cliper API", version: str = "1.0.0"):
        self.app = app
        self.title = title
        self.version = version
        self.docs_cache: Dict[str, Any] = {}
        
    def generate_openapi_schema(self, api_version: APIVersion = APIVersion.V1) -> Dict[str, Any]:
        """Generate OpenAPI schema for specific API version."""
        cache_key = f"openapi_{api_version.value}"
        
        if cache_key in self.docs_cache:
            return self.docs_cache[cache_key]
            
        # Base OpenAPI schema
        openapi_schema = get_openapi(
            title=f"{self.title} - {api_version.value.upper()}",
            version=self.version,
            description=self._get_api_description(api_version),
            routes=self.app.routes,
            servers=self._get_servers(api_version)
        )
        
        # Add custom extensions
        openapi_schema.update({
            "info": {
                **openapi_schema["info"],
                "contact": {
                    "name": "Cliper API Support",
                    "email": "support@cliper.app",
                    "url": "https://cliper.app/support"
                },
                "license": {
                    "name": "MIT",
                    "url": "https://opensource.org/licenses/MIT"
                },
                "termsOfService": "https://cliper.app/terms",
                "x-logo": {
                    "url": "https://cliper.app/logo.png",
                    "altText": "Cliper Logo"
                }
            },
            "externalDocs": {
                "description": "Find more info here",
                "url": "https://docs.cliper.app"
            },
            "x-tagGroups": [
                {
                    "name": "Core Features",
                    "tags": ["upload", "processing", "download"]
                },
                {
                    "name": "Authentication",
                    "tags": ["auth", "users"]
                },
                {
                    "name": "System",
                    "tags": ["health", "metrics", "admin"]
                }
            ]
        })
        
        # Add security schemes
        openapi_schema["components"] = openapi_schema.get("components", {})
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT token obtained from Supabase Auth"
            },
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key for service-to-service authentication"
            }
        }
        
        # Add rate limiting information
        openapi_schema["x-rateLimit"] = {
            "upload": "10 requests per minute",
            "processing": "5 requests per minute",
            "general": "100 requests per minute"
        }
        
        self.docs_cache[cache_key] = openapi_schema
        return openapi_schema
        
    def _get_api_description(self, api_version: APIVersion) -> str:
        """Get API description based on version."""
        descriptions = {
            APIVersion.V1: """
            # Cliper API v1
            
            The Cliper API provides powerful video processing capabilities with AI-powered features.
            
            ## Features
            - **Video Upload**: Upload videos for processing
            - **URL Processing**: Process videos from URLs
            - **AI Enhancement**: AI-powered video analysis and enhancement
            - **Real-time Processing**: WebSocket support for real-time updates
            - **Secure Authentication**: Firebase Auth integration
            
            ## Rate Limits
            - Upload endpoints: 10 requests/minute
            - Processing endpoints: 5 requests/minute
            - General endpoints: 100 requests/minute
            
            ## Authentication
            All endpoints require authentication via Firebase JWT tokens or API keys.
            """,
            APIVersion.V2: """
            # Cliper API v2 (Beta)
            
            Enhanced version of the Cliper API with improved performance and new features.
            
            ## New Features
            - **Batch Processing**: Process multiple videos simultaneously
            - **Advanced Analytics**: Detailed processing metrics
            - **Webhook Support**: Real-time notifications
            - **Enhanced Security**: Additional security measures
            
            ## Migration Guide
            See our migration guide at https://docs.cliper.app/migration/v2
            """
        }
        return descriptions.get(api_version, "Cliper API")
        
    def _get_servers(self, api_version: APIVersion) -> List[Dict[str, str]]:
        """Get server configurations for API version."""
        return [
            {
                "url": f"https://api.cliper.app/{api_version.value}",
                "description": "Production server"
            },
            {
                "url": f"https://staging-api.cliper.app/{api_version.value}",
                "description": "Staging server"
            },
            {
                "url": f"http://localhost:8000/{api_version.value}",
                "description": "Development server"
            }
        ]
        
    def generate_swagger_ui(self, api_version: APIVersion = APIVersion.V1) -> HTMLResponse:
        """Generate Swagger UI for specific API version."""
        openapi_url = f"/api/{api_version.value}/openapi.json"
        
        return get_swagger_ui_html(
            openapi_url=openapi_url,
            title=f"{self.title} - {api_version.value.upper()} - Swagger UI",
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css",
            swagger_ui_parameters={
                "deepLinking": True,
                "displayRequestDuration": True,
                "docExpansion": "none",
                "operationsSorter": "alpha",
                "filter": True,
                "showExtensions": True,
                "showCommonExtensions": True,
                "tryItOutEnabled": True
            }
        )
        
    def generate_redoc(self, api_version: APIVersion = APIVersion.V1) -> HTMLResponse:
        """Generate ReDoc documentation for specific API version."""
        openapi_url = f"/api/{api_version.value}/openapi.json"
        
        return get_redoc_html(
            openapi_url=openapi_url,
            title=f"{self.title} - {api_version.value.upper()} - ReDoc",
            redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js",
            redoc_favicon_url="https://cliper.app/favicon.ico",
            with_google_fonts=True
        )
        
    def generate_api_changelog(self) -> Dict[str, Any]:
        """Generate API changelog."""
        return {
            "changelog": [
                {
                    "version": "2.0.0-beta",
                    "date": "2024-01-15",
                    "changes": [
                        "Added batch processing endpoints",
                        "Enhanced security with additional rate limiting",
                        "Improved error handling and responses",
                        "Added webhook support for real-time notifications"
                    ],
                    "breaking_changes": [
                        "Authentication header format changed",
                        "Response format updated for consistency"
                    ]
                },
                {
                    "version": "1.2.0",
                    "date": "2024-01-01",
                    "changes": [
                        "Added URL processing endpoint",
                        "Improved video upload performance",
                        "Enhanced error messages"
                    ],
                    "breaking_changes": []
                },
                {
                    "version": "1.1.0",
                    "date": "2023-12-15",
                    "changes": [
                        "Added authentication middleware",
                        "Implemented rate limiting",
                        "Added health check endpoints"
                    ],
                    "breaking_changes": []
                },
                {
                    "version": "1.0.0",
                    "date": "2023-12-01",
                    "changes": [
                        "Initial API release",
                        "Video upload functionality",
                        "Basic processing capabilities"
                    ],
                    "breaking_changes": []
                }
            ]
        }
        
    def generate_sdk_examples(self) -> Dict[str, Any]:
        """Generate SDK examples for different programming languages."""
        return {
            "python": {
                "installation": "pip install cliper-sdk",
                "example": """
import cliper

# Initialize client
client = cliper.Client(api_key="your-api-key")

# Upload video
with open("video.mp4", "rb") as f:
    result = client.upload_video(f, filename="video.mp4")
    
print(f"Video ID: {result.video_id}")
print(f"Status: {result.status}")
"""
            },
            "javascript": {
                "installation": "npm install @cliper/sdk",
                "example": """
import { CliperClient } from '@cliper/sdk';

// Initialize client
const client = new CliperClient({ apiKey: 'your-api-key' });

// Upload video
const fileInput = document.getElementById('video-file');
const file = fileInput.files[0];

const result = await client.uploadVideo(file);
console.log('Video ID:', result.videoId);
console.log('Status:', result.status);
"""
            },
            "curl": {
                "example": """
# Upload video
curl -X POST "https://api.cliper.app/v1/upload" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@video.mp4"
  
# Process URL
curl -X POST "https://api.cliper.app/v1/process-url" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/video.mp4"}'
"""
            }
        }
        
    def export_documentation(self, output_dir: str = "docs") -> None:
        """Export documentation to files."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Export OpenAPI schemas
        for version in APIVersion:
            schema = self.generate_openapi_schema(version)
            schema_file = output_path / f"openapi_{version.value}.json"
            with open(schema_file, "w") as f:
                json.dump(schema, f, indent=2)
                
        # Export changelog
        changelog = self.generate_api_changelog()
        changelog_file = output_path / "changelog.json"
        with open(changelog_file, "w") as f:
            json.dump(changelog, f, indent=2)
            
        # Export SDK examples
        examples = self.generate_sdk_examples()
        examples_file = output_path / "sdk_examples.json"
        with open(examples_file, "w") as f:
            json.dump(examples, f, indent=2)
            
        print(f"Documentation exported to {output_path}")


def generate_api_docs(app: FastAPI) -> APIDocumentationGenerator:
    """Factory function to create API documentation generator."""
    return APIDocumentationGenerator(app)


def setup_documentation_routes(app: FastAPI, doc_generator: APIDocumentationGenerator) -> None:
    """Setup documentation routes for the FastAPI app."""
    
    @app.get("/api/v1/openapi.json", include_in_schema=False)
    async def get_v1_openapi():
        return doc_generator.generate_openapi_schema(APIVersion.V1)
        
    @app.get("/api/v2/openapi.json", include_in_schema=False)
    async def get_v2_openapi():
        return doc_generator.generate_openapi_schema(APIVersion.V2)
        
    @app.get("/docs/v1", include_in_schema=False)
    async def get_v1_docs():
        return doc_generator.generate_swagger_ui(APIVersion.V1)
        
    @app.get("/docs/v2", include_in_schema=False)
    async def get_v2_docs():
        return doc_generator.generate_swagger_ui(APIVersion.V2)
        
    @app.get("/redoc/v1", include_in_schema=False)
    async def get_v1_redoc():
        return doc_generator.generate_redoc(APIVersion.V1)
        
    @app.get("/redoc/v2", include_in_schema=False)
    async def get_v2_redoc():
        return doc_generator.generate_redoc(APIVersion.V2)
        
    @app.get("/api/changelog", include_in_schema=False)
    async def get_changelog():
        return doc_generator.generate_api_changelog()
        
    @app.get("/api/sdk-examples", include_in_schema=False)
    async def get_sdk_examples():
        return doc_generator.generate_sdk_examples()