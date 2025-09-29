"""Comprehensive API documentation system for the clip generation platform.

Provides:
- Automatic API documentation generation
- Interactive API explorer
- Schema validation and examples
- Authentication documentation
- Rate limiting information
- Error code documentation
- SDK generation support
"""

import json
import yaml
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from fastapi import FastAPI, APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from pydantic import BaseModel

from api.utils.enhanced_logging import get_logger
from api.config.production import get_settings


logger = get_logger(__name__)
settings = get_settings()


class DocumentationType(str, Enum):
    """Types of documentation."""
    OPENAPI = "openapi"
    SWAGGER = "swagger"
    REDOC = "redoc"
    POSTMAN = "postman"
    MARKDOWN = "markdown"
    HTML = "html"


class AuthenticationType(str, Enum):
    """Authentication types."""
    BEARER = "bearer"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC = "basic"


class ParameterType(str, Enum):
    """Parameter types."""
    QUERY = "query"
    PATH = "path"
    HEADER = "header"
    BODY = "body"
    FORM = "form"


@dataclass
class APIParameter:
    """API parameter definition."""
    name: str
    type: ParameterType
    data_type: str
    description: str = ""
    required: bool = False
    default_value: Any = None
    example: Any = None
    enum_values: Optional[List[str]] = None
    format: Optional[str] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    pattern: Optional[str] = None


@dataclass
class APIResponse:
    """API response definition."""
    status_code: int
    description: str
    content_type: str = "application/json"
    schema: Optional[Dict[str, Any]] = None
    example: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None


@dataclass
class APIEndpoint:
    """API endpoint definition."""
    path: str
    method: str
    summary: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    
    # Parameters
    parameters: List[APIParameter] = field(default_factory=list)
    request_body: Optional[Dict[str, Any]] = None
    
    # Responses
    responses: List[APIResponse] = field(default_factory=list)
    
    # Authentication
    authentication_required: bool = False
    authentication_types: List[AuthenticationType] = field(default_factory=list)
    
    # Rate limiting
    rate_limit: Optional[str] = None
    
    # Additional metadata
    deprecated: bool = False
    version: str = "1.0"
    examples: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class APISchema:
    """API schema definition."""
    name: str
    type: str
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    required: List[str] = field(default_factory=list)
    example: Optional[Dict[str, Any]] = None


@dataclass
class APIDocumentation:
    """Complete API documentation."""
    title: str
    description: str
    version: str
    base_url: str
    
    # Endpoints
    endpoints: List[APIEndpoint] = field(default_factory=list)
    
    # Schemas
    schemas: List[APISchema] = field(default_factory=list)
    
    # Authentication
    authentication_methods: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Contact and license
    contact: Optional[Dict[str, str]] = None
    license: Optional[Dict[str, str]] = None
    
    # Servers
    servers: List[Dict[str, str]] = field(default_factory=list)
    
    # Tags
    tags: List[Dict[str, str]] = field(default_factory=list)


class ErrorCode(BaseModel):
    """Error code documentation."""
    code: str
    status_code: int
    message: str
    description: str
    example: Optional[Dict[str, Any]] = None
    resolution: Optional[str] = None


class RateLimitInfo(BaseModel):
    """Rate limit information."""
    endpoint: str
    limit: int
    window: str  # e.g., "1m", "1h", "1d"
    description: str
    headers: List[str] = []


class SDKExample(BaseModel):
    """SDK usage example."""
    language: str
    title: str
    description: str
    code: str
    dependencies: List[str] = []


class DocumentationGenerator:
    """Generates API documentation in various formats."""
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.documentation = self._extract_documentation()
        
        # Error codes
        self.error_codes = self._initialize_error_codes()
        
        # Rate limits
        self.rate_limits = self._initialize_rate_limits()
        
        # SDK examples
        self.sdk_examples = self._initialize_sdk_examples()
        
        logger.info("Documentation generator initialized")
    
    def _extract_documentation(self) -> APIDocumentation:
        """Extract documentation from FastAPI app."""
        openapi_schema = get_openapi(
            title=self.app.title,
            version=self.app.version,
            description=self.app.description,
            routes=self.app.routes,
        )
        
        # Convert OpenAPI schema to our format
        documentation = APIDocumentation(
            title=openapi_schema.get("info", {}).get("title", "API"),
            description=openapi_schema.get("info", {}).get("description", ""),
            version=openapi_schema.get("info", {}).get("version", "1.0"),
            base_url=settings.api_base_url or "http://localhost:8000"
        )
        
        # Extract endpoints
        paths = openapi_schema.get("paths", {})
        for path, methods in paths.items():
            for method, spec in methods.items():
                endpoint = self._convert_openapi_endpoint(path, method, spec)
                documentation.endpoints.append(endpoint)
        
        # Extract schemas
        components = openapi_schema.get("components", {})
        schemas = components.get("schemas", {})
        for name, schema_spec in schemas.items():
            schema = self._convert_openapi_schema(name, schema_spec)
            documentation.schemas.append(schema)
        
        # Set authentication methods
        security_schemes = components.get("securitySchemes", {})
        for name, scheme in security_schemes.items():
            documentation.authentication_methods[name] = scheme
        
        return documentation
    
    def _convert_openapi_endpoint(self, path: str, method: str, spec: Dict[str, Any]) -> APIEndpoint:
        """Convert OpenAPI endpoint spec to our format."""
        endpoint = APIEndpoint(
            path=path,
            method=method.upper(),
            summary=spec.get("summary", ""),
            description=spec.get("description", ""),
            tags=spec.get("tags", [])
        )
        
        # Extract parameters
        parameters = spec.get("parameters", [])
        for param in parameters:
            api_param = APIParameter(
                name=param.get("name", ""),
                type=ParameterType(param.get("in", "query")),
                data_type=param.get("schema", {}).get("type", "string"),
                description=param.get("description", ""),
                required=param.get("required", False),
                example=param.get("example")
            )
            endpoint.parameters.append(api_param)
        
        # Extract request body
        request_body = spec.get("requestBody")
        if request_body:
            endpoint.request_body = request_body
        
        # Extract responses
        responses = spec.get("responses", {})
        for status_code, response_spec in responses.items():
            api_response = APIResponse(
                status_code=int(status_code),
                description=response_spec.get("description", ""),
                content_type="application/json"
            )
            
            content = response_spec.get("content", {})
            if "application/json" in content:
                api_response.schema = content["application/json"].get("schema")
                api_response.example = content["application/json"].get("example")
            
            endpoint.responses.append(api_response)
        
        # Check for authentication
        security = spec.get("security", [])
        if security:
            endpoint.authentication_required = True
            for sec in security:
                for auth_type in sec.keys():
                    if auth_type == "bearerAuth":
                        endpoint.authentication_types.append(AuthenticationType.BEARER)
                    elif auth_type == "apiKey":
                        endpoint.authentication_types.append(AuthenticationType.API_KEY)
        
        return endpoint
    
    def _convert_openapi_schema(self, name: str, schema_spec: Dict[str, Any]) -> APISchema:
        """Convert OpenAPI schema to our format."""
        return APISchema(
            name=name,
            type=schema_spec.get("type", "object"),
            description=schema_spec.get("description", ""),
            properties=schema_spec.get("properties", {}),
            required=schema_spec.get("required", []),
            example=schema_spec.get("example")
        )
    
    def _initialize_error_codes(self) -> List[ErrorCode]:
        """Initialize error code documentation."""
        return [
            ErrorCode(
                code="INVALID_REQUEST",
                status_code=400,
                message="Invalid request format",
                description="The request body or parameters are malformed or missing required fields.",
                example={"error": "INVALID_REQUEST", "message": "Missing required field 'video_url'"},
                resolution="Check the request format and ensure all required fields are provided."
            ),
            ErrorCode(
                code="UNAUTHORIZED",
                status_code=401,
                message="Authentication required",
                description="The request requires valid authentication credentials.",
                example={"error": "UNAUTHORIZED", "message": "Invalid or missing authentication token"},
                resolution="Provide a valid authentication token in the Authorization header."
            ),
            ErrorCode(
                code="FORBIDDEN",
                status_code=403,
                message="Access denied",
                description="The authenticated user does not have permission to access this resource.",
                example={"error": "FORBIDDEN", "message": "Insufficient permissions"},
                resolution="Ensure the user has the required permissions for this operation."
            ),
            ErrorCode(
                code="NOT_FOUND",
                status_code=404,
                message="Resource not found",
                description="The requested resource does not exist.",
                example={"error": "NOT_FOUND", "message": "Clip not found"},
                resolution="Verify the resource ID and ensure the resource exists."
            ),
            ErrorCode(
                code="RATE_LIMIT_EXCEEDED",
                status_code=429,
                message="Rate limit exceeded",
                description="Too many requests have been made in a short period.",
                example={"error": "RATE_LIMIT_EXCEEDED", "message": "Rate limit exceeded. Try again in 60 seconds."},
                resolution="Wait for the rate limit window to reset before making more requests."
            ),
            ErrorCode(
                code="INTERNAL_ERROR",
                status_code=500,
                message="Internal server error",
                description="An unexpected error occurred on the server.",
                example={"error": "INTERNAL_ERROR", "message": "An unexpected error occurred"},
                resolution="Try again later. If the problem persists, contact support."
            ),
            ErrorCode(
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                message="Service temporarily unavailable",
                description="The service is temporarily unavailable due to maintenance or overload.",
                example={"error": "SERVICE_UNAVAILABLE", "message": "Service temporarily unavailable"},
                resolution="Wait and try again later. Check the service status page for updates."
            )
        ]
    
    def _initialize_rate_limits(self) -> List[RateLimitInfo]:
        """Initialize rate limit documentation."""
        return [
            RateLimitInfo(
                endpoint="/api/clips/generate",
                limit=10,
                window="1m",
                description="Clip generation requests are limited to prevent abuse",
                headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
            ),
            RateLimitInfo(
                endpoint="/api/auth/login",
                limit=5,
                window="1m",
                description="Login attempts are rate limited for security",
                headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
            ),
            RateLimitInfo(
                endpoint="/api/uploads/*",
                limit=20,
                window="1h",
                description="File upload requests are limited by size and frequency",
                headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
            )
        ]
    
    def _initialize_sdk_examples(self) -> List[SDKExample]:
        """Initialize SDK examples."""
        return [
            SDKExample(
                language="python",
                title="Generate Clip",
                description="Generate a clip from a video URL",
                code="""import requests

# Set up authentication
headers = {
    'Authorization': 'Bearer YOUR_API_TOKEN',
    'Content-Type': 'application/json'
}

# Generate clip
response = requests.post(
    'https://api.example.com/api/clips/generate',
    headers=headers,
    json={
        'video_url': 'https://example.com/video.mp4',
        'platform': 'tiktok',
        'duration': 30,
        'style': 'engaging'
    }
)

if response.status_code == 200:
    clip_data = response.json()
    print(f"Clip generated: {clip_data['id']}")
else:
    print(f"Error: {response.json()['message']}")""",
                dependencies=["requests"]
            ),
            SDKExample(
                language="javascript",
                title="Check Clip Status",
                description="Check the status of a clip generation job",
                code="""const axios = require('axios');

// Set up authentication
const headers = {
    'Authorization': 'Bearer YOUR_API_TOKEN',
    'Content-Type': 'application/json'
};

// Check clip status
async function checkClipStatus(clipId) {
    try {
        const response = await axios.get(
            `https://api.example.com/api/clips/${clipId}/status`,
            { headers }
        );
        
        console.log('Clip status:', response.data.status);
        return response.data;
    } catch (error) {
        console.error('Error:', error.response.data.message);
        throw error;
    }
}

// Usage
checkClipStatus('clip-123').then(status => {
    console.log('Status check complete:', status);
});""",
                dependencies=["axios"]
            ),
            SDKExample(
                language="curl",
                title="Upload Video",
                description="Upload a video file for processing",
                code="""# Upload video file
curl -X POST https://api.example.com/api/uploads/video \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -F "file=@/path/to/video.mp4" \
  -F "metadata={\"title\":\"My Video\",\"description\":\"Video for clip generation\"}"

# Response:
# {
#   "id": "upload-123",
#   "url": "https://storage.example.com/uploads/video-123.mp4",
#   "status": "uploaded",
#   "metadata": {
#     "title": "My Video",
#     "description": "Video for clip generation",
#     "duration": 120,
#     "size": 15728640
#   }
# }""",
                dependencies=[]
            )
        ]
    
    def generate_openapi_spec(self) -> Dict[str, Any]:
        """Generate OpenAPI 3.0 specification."""
        return get_openapi(
            title=self.documentation.title,
            version=self.documentation.version,
            description=self.documentation.description,
            routes=self.app.routes,
        )
    
    def generate_postman_collection(self) -> Dict[str, Any]:
        """Generate Postman collection."""
        collection = {
            "info": {
                "name": self.documentation.title,
                "description": self.documentation.description,
                "version": self.documentation.version,
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "auth": {
                "type": "bearer",
                "bearer": [
                    {
                        "key": "token",
                        "value": "{{api_token}}",
                        "type": "string"
                    }
                ]
            },
            "variable": [
                {
                    "key": "base_url",
                    "value": self.documentation.base_url,
                    "type": "string"
                },
                {
                    "key": "api_token",
                    "value": "YOUR_API_TOKEN",
                    "type": "string"
                }
            ],
            "item": []
        }
        
        # Group endpoints by tags
        grouped_endpoints = {}
        for endpoint in self.documentation.endpoints:
            for tag in endpoint.tags or ["Default"]:
                if tag not in grouped_endpoints:
                    grouped_endpoints[tag] = []
                grouped_endpoints[tag].append(endpoint)
        
        # Create Postman items
        for tag, endpoints in grouped_endpoints.items():
            folder = {
                "name": tag,
                "item": []
            }
            
            for endpoint in endpoints:
                item = self._create_postman_item(endpoint)
                folder["item"].append(item)
            
            collection["item"].append(folder)
        
        return collection
    
    def _create_postman_item(self, endpoint: APIEndpoint) -> Dict[str, Any]:
        """Create Postman item from endpoint."""
        item = {
            "name": endpoint.summary or f"{endpoint.method} {endpoint.path}",
            "request": {
                "method": endpoint.method,
                "header": [],
                "url": {
                    "raw": f"{{{{base_url}}}}{endpoint.path}",
                    "host": ["{{base_url}}"],
                    "path": endpoint.path.strip("/").split("/"),
                    "query": []
                },
                "description": endpoint.description
            },
            "response": []
        }
        
        # Add authentication header if required
        if endpoint.authentication_required:
            item["request"]["header"].append({
                "key": "Authorization",
                "value": "Bearer {{api_token}}",
                "type": "text"
            })
        
        # Add parameters
        for param in endpoint.parameters:
            if param.type == ParameterType.QUERY:
                item["request"]["url"]["query"].append({
                    "key": param.name,
                    "value": str(param.example) if param.example else "",
                    "description": param.description,
                    "disabled": not param.required
                })
            elif param.type == ParameterType.HEADER:
                item["request"]["header"].append({
                    "key": param.name,
                    "value": str(param.example) if param.example else "",
                    "description": param.description,
                    "type": "text"
                })
        
        # Add request body
        if endpoint.request_body:
            item["request"]["body"] = {
                "mode": "raw",
                "raw": json.dumps(endpoint.request_body.get("example", {}), indent=2),
                "options": {
                    "raw": {
                        "language": "json"
                    }
                }
            }
            
            item["request"]["header"].append({
                "key": "Content-Type",
                "value": "application/json",
                "type": "text"
            })
        
        return item
    
    def generate_markdown_docs(self) -> str:
        """Generate Markdown documentation."""
        md_content = []
        
        # Title and description
        md_content.append(f"# {self.documentation.title}")
        md_content.append(f"\n{self.documentation.description}\n")
        
        # Table of contents
        md_content.append("## Table of Contents")
        md_content.append("- [Authentication](#authentication)")
        md_content.append("- [Rate Limiting](#rate-limiting)")
        md_content.append("- [Error Codes](#error-codes)")
        md_content.append("- [Endpoints](#endpoints)")
        md_content.append("- [Schemas](#schemas)")
        md_content.append("- [SDK Examples](#sdk-examples)\n")
        
        # Authentication
        md_content.append("## Authentication")
        md_content.append("This API uses Bearer token authentication. Include your API token in the Authorization header:")
        md_content.append("```")
        md_content.append("Authorization: Bearer YOUR_API_TOKEN")
        md_content.append("```\n")
        
        # Rate limiting
        md_content.append("## Rate Limiting")
        md_content.append("The API implements rate limiting to ensure fair usage:")
        md_content.append("| Endpoint | Limit | Window | Description |")
        md_content.append("|----------|-------|--------|-------------|")
        
        for rate_limit in self.rate_limits:
            md_content.append(f"| `{rate_limit.endpoint}` | {rate_limit.limit} | {rate_limit.window} | {rate_limit.description} |")
        
        md_content.append("\n")
        
        # Error codes
        md_content.append("## Error Codes")
        md_content.append("The API returns the following error codes:")
        md_content.append("| Code | Status | Message | Description |")
        md_content.append("|------|--------|---------|-------------|")
        
        for error in self.error_codes:
            md_content.append(f"| `{error.code}` | {error.status_code} | {error.message} | {error.description} |")
        
        md_content.append("\n")
        
        # Endpoints
        md_content.append("## Endpoints")
        
        # Group endpoints by tags
        grouped_endpoints = {}
        for endpoint in self.documentation.endpoints:
            for tag in endpoint.tags or ["Default"]:
                if tag not in grouped_endpoints:
                    grouped_endpoints[tag] = []
                grouped_endpoints[tag].append(endpoint)
        
        for tag, endpoints in grouped_endpoints.items():
            md_content.append(f"\n### {tag}")
            
            for endpoint in endpoints:
                md_content.append(f"\n#### {endpoint.method} {endpoint.path}")
                md_content.append(f"{endpoint.description}\n")
                
                # Parameters
                if endpoint.parameters:
                    md_content.append("**Parameters:**")
                    md_content.append("| Name | Type | Required | Description |")
                    md_content.append("|------|------|----------|-------------|")
                    
                    for param in endpoint.parameters:
                        required = "Yes" if param.required else "No"
                        md_content.append(f"| `{param.name}` | {param.data_type} | {required} | {param.description} |")
                    
                    md_content.append("")
                
                # Responses
                if endpoint.responses:
                    md_content.append("**Responses:**")
                    for response in endpoint.responses:
                        md_content.append(f"- **{response.status_code}**: {response.description}")
                    
                    md_content.append("")
        
        # Schemas
        md_content.append("\n## Schemas")
        for schema in self.documentation.schemas:
            md_content.append(f"\n### {schema.name}")
            md_content.append(f"{schema.description}\n")
            
            if schema.properties:
                md_content.append("**Properties:**")
                md_content.append("| Name | Type | Required | Description |")
                md_content.append("|------|------|----------|-------------|")
                
                for prop_name, prop_spec in schema.properties.items():
                    prop_type = prop_spec.get("type", "unknown")
                    required = "Yes" if prop_name in schema.required else "No"
                    description = prop_spec.get("description", "")
                    md_content.append(f"| `{prop_name}` | {prop_type} | {required} | {description} |")
                
                md_content.append("")
        
        # SDK Examples
        md_content.append("\n## SDK Examples")
        for example in self.sdk_examples:
            md_content.append(f"\n### {example.title} ({example.language})")
            md_content.append(f"{example.description}\n")
            
            if example.dependencies:
                md_content.append(f"**Dependencies:** {', '.join(example.dependencies)}\n")
            
            md_content.append(f"```{example.language}")
            md_content.append(example.code)
            md_content.append("```\n")
        
        return "\n".join(md_content)
    
    def generate_html_docs(self) -> str:
        """Generate HTML documentation."""
        html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - API Documentation</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            border-bottom: 2px solid #eee;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .endpoint {{
            border: 1px solid #ddd;
            border-radius: 8px;
            margin: 20px 0;
            padding: 20px;
        }}
        .method {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            color: white;
            font-weight: bold;
            margin-right: 10px;
        }}
        .method.get {{ background-color: #61affe; }}
        .method.post {{ background-color: #49cc90; }}
        .method.put {{ background-color: #fca130; }}
        .method.delete {{ background-color: #f93e3e; }}
        .method.patch {{ background-color: #50e3c2; }}
        .path {{
            font-family: monospace;
            background-color: #f5f5f5;
            padding: 2px 6px;
            border-radius: 4px;
        }}
        .parameters, .responses {{
            margin-top: 15px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f5f5f5;
        }}
        .code {{
            background-color: #f8f8f8;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 15px;
            font-family: monospace;
            overflow-x: auto;
        }}
        .toc {{
            background-color: #f9f9f9;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }}
        .toc ul {{
            list-style-type: none;
            padding-left: 0;
        }}
        .toc li {{
            margin: 5px 0;
        }}
        .toc a {{
            text-decoration: none;
            color: #0066cc;
        }}
        .toc a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
        <p>{description}</p>
        <p><strong>Version:</strong> {version}</p>
        <p><strong>Base URL:</strong> <code>{base_url}</code></p>
    </div>
    
    <div class="toc">
        <h2>Table of Contents</h2>
        <ul>
            <li><a href="#authentication">Authentication</a></li>
            <li><a href="#rate-limiting">Rate Limiting</a></li>
            <li><a href="#error-codes">Error Codes</a></li>
            <li><a href="#endpoints">Endpoints</a></li>
        </ul>
    </div>
    
    <h2 id="authentication">Authentication</h2>
    <p>This API uses Bearer token authentication. Include your API token in the Authorization header:</p>
    <div class="code">Authorization: Bearer YOUR_API_TOKEN</div>
    
    <h2 id="rate-limiting">Rate Limiting</h2>
    <p>The API implements rate limiting to ensure fair usage:</p>
    <table>
        <tr><th>Endpoint</th><th>Limit</th><th>Window</th><th>Description</th></tr>
        {rate_limits_table}
    </table>
    
    <h2 id="error-codes">Error Codes</h2>
    <p>The API returns the following error codes:</p>
    <table>
        <tr><th>Code</th><th>Status</th><th>Message</th><th>Description</th></tr>
        {error_codes_table}
    </table>
    
    <h2 id="endpoints">Endpoints</h2>
    {endpoints_html}
    
</body>
</html>
        """
        
        # Generate rate limits table
        rate_limits_rows = []
        for rate_limit in self.rate_limits:
            rate_limits_rows.append(
                f"<tr><td><code>{rate_limit.endpoint}</code></td><td>{rate_limit.limit}</td><td>{rate_limit.window}</td><td>{rate_limit.description}</td></tr>"
            )
        rate_limits_table = "\n".join(rate_limits_rows)
        
        # Generate error codes table
        error_codes_rows = []
        for error in self.error_codes:
            error_codes_rows.append(
                f"<tr><td><code>{error.code}</code></td><td>{error.status_code}</td><td>{error.message}</td><td>{error.description}</td></tr>"
            )
        error_codes_table = "\n".join(error_codes_rows)
        
        # Generate endpoints HTML
        endpoints_html = []
        
        # Group endpoints by tags
        grouped_endpoints = {}
        for endpoint in self.documentation.endpoints:
            for tag in endpoint.tags or ["Default"]:
                if tag not in grouped_endpoints:
                    grouped_endpoints[tag] = []
                grouped_endpoints[tag].append(endpoint)
        
        for tag, endpoints in grouped_endpoints.items():
            endpoints_html.append(f"<h3>{tag}</h3>")
            
            for endpoint in endpoints:
                method_class = endpoint.method.lower()
                endpoint_html = f"""
                <div class="endpoint">
                    <h4>
                        <span class="method {method_class}">{endpoint.method}</span>
                        <span class="path">{endpoint.path}</span>
                    </h4>
                    <p>{endpoint.description}</p>
                """
                
                # Parameters
                if endpoint.parameters:
                    endpoint_html += "<div class='parameters'><h5>Parameters:</h5><table><tr><th>Name</th><th>Type</th><th>Required</th><th>Description</th></tr>"
                    
                    for param in endpoint.parameters:
                        required = "Yes" if param.required else "No"
                        endpoint_html += f"<tr><td><code>{param.name}</code></td><td>{param.data_type}</td><td>{required}</td><td>{param.description}</td></tr>"
                    
                    endpoint_html += "</table></div>"
                
                # Responses
                if endpoint.responses:
                    endpoint_html += "<div class='responses'><h5>Responses:</h5><ul>"
                    
                    for response in endpoint.responses:
                        endpoint_html += f"<li><strong>{response.status_code}:</strong> {response.description}</li>"
                    
                    endpoint_html += "</ul></div>"
                
                endpoint_html += "</div>"
                endpoints_html.append(endpoint_html)
        
        endpoints_html_str = "\n".join(endpoints_html)
        
        return html_template.format(
            title=self.documentation.title,
            description=self.documentation.description,
            version=self.documentation.version,
            base_url=self.documentation.base_url,
            rate_limits_table=rate_limits_table,
            error_codes_table=error_codes_table,
            endpoints_html=endpoints_html_str
        )
    
    def export_documentation(self, format: DocumentationType, output_path: Optional[str] = None) -> str:
        """Export documentation in specified format."""
        if format == DocumentationType.OPENAPI:
            content = json.dumps(self.generate_openapi_spec(), indent=2)
            filename = "openapi.json"
        elif format == DocumentationType.POSTMAN:
            content = json.dumps(self.generate_postman_collection(), indent=2)
            filename = "postman_collection.json"
        elif format == DocumentationType.MARKDOWN:
            content = self.generate_markdown_docs()
            filename = "api_docs.md"
        elif format == DocumentationType.HTML:
            content = self.generate_html_docs()
            filename = "api_docs.html"
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        if output_path:
            file_path = Path(output_path)
            file_path.write_text(content, encoding="utf-8")
            logger.info(f"Documentation exported to {file_path}")
            return str(file_path)
        else:
            return content


# Global documentation generator
documentation_generator: Optional[DocumentationGenerator] = None


def initialize_documentation(app: FastAPI) -> DocumentationGenerator:
    """Initialize documentation generator."""
    global documentation_generator
    documentation_generator = DocumentationGenerator(app)
    return documentation_generator


def get_documentation_generator() -> Optional[DocumentationGenerator]:
    """Get the global documentation generator."""
    return documentation_generator


# API Router
router = APIRouter(prefix="/api/docs", tags=["documentation"])


@router.get("/openapi.json")
async def get_openapi_spec():
    """Get OpenAPI specification."""
    if not documentation_generator:
        raise HTTPException(status_code=500, detail="Documentation not initialized")
    
    try:
        spec = documentation_generator.generate_openapi_spec()
        return JSONResponse(content=spec)
    except Exception as e:
        logger.error(f"Error generating OpenAPI spec: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate OpenAPI specification")


@router.get("/postman.json")
async def get_postman_collection():
    """Get Postman collection."""
    if not documentation_generator:
        raise HTTPException(status_code=500, detail="Documentation not initialized")
    
    try:
        collection = documentation_generator.generate_postman_collection()
        return JSONResponse(
            content=collection,
            headers={"Content-Disposition": "attachment; filename=postman_collection.json"}
        )
    except Exception as e:
        logger.error(f"Error generating Postman collection: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate Postman collection")


@router.get("/markdown")
async def get_markdown_docs():
    """Get Markdown documentation."""
    if not documentation_generator:
        raise HTTPException(status_code=500, detail="Documentation not initialized")
    
    try:
        markdown_content = documentation_generator.generate_markdown_docs()
        return JSONResponse(
            content={"content": markdown_content},
            headers={"Content-Disposition": "attachment; filename=api_docs.md"}
        )
    except Exception as e:
        logger.error(f"Error generating Markdown docs: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate Markdown documentation")


@router.get("/html")
async def get_html_docs():
    """Get HTML documentation."""
    if not documentation_generator:
        raise HTTPException(status_code=500, detail="Documentation not initialized")
    
    try:
        html_content = documentation_generator.generate_html_docs()
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"Error generating HTML docs: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate HTML documentation")


@router.get("/swagger")
async def get_swagger_ui():
    """Get Swagger UI."""
    return get_swagger_ui_html(
        openapi_url="/api/docs/openapi.json",
        title="API Documentation - Swagger UI"
    )


@router.get("/redoc")
async def get_redoc():
    """Get ReDoc documentation."""
    return get_redoc_html(
        openapi_url="/api/docs/openapi.json",
        title="API Documentation - ReDoc"
    )


@router.get("/error-codes")
async def get_error_codes():
    """Get error codes documentation."""
    if not documentation_generator:
        raise HTTPException(status_code=500, detail="Documentation not initialized")
    
    try:
        error_codes = [error.dict() for error in documentation_generator.error_codes]
        return JSONResponse(content={"error_codes": error_codes})
    except Exception as e:
        logger.error(f"Error getting error codes: {e}")
        raise HTTPException(status_code=500, detail="Failed to get error codes")


@router.get("/rate-limits")
async def get_rate_limits():
    """Get rate limits documentation."""
    if not documentation_generator:
        raise HTTPException(status_code=500, detail="Documentation not initialized")
    
    try:
        rate_limits = [limit.dict() for limit in documentation_generator.rate_limits]
        return JSONResponse(content={"rate_limits": rate_limits})
    except Exception as e:
        logger.error(f"Error getting rate limits: {e}")
        raise HTTPException(status_code=500, detail="Failed to get rate limits")


@router.get("/sdk-examples")
async def get_sdk_examples(language: Optional[str] = Query(None, description="Filter by programming language")):
    """Get SDK examples."""
    if not documentation_generator:
        raise HTTPException(status_code=500, detail="Documentation not initialized")
    
    try:
        examples = documentation_generator.sdk_examples
        
        if language:
            examples = [ex for ex in examples if ex.language.lower() == language.lower()]
        
        return JSONResponse(content={
            "sdk_examples": [example.dict() for example in examples]
        })
    except Exception as e:
        logger.error(f"Error getting SDK examples: {e}")
        raise HTTPException(status_code=500, detail="Failed to get SDK examples")


@router.post("/export")
async def export_documentation(
    format: DocumentationType,
    filename: Optional[str] = None
):
    """Export documentation in specified format."""
    if not documentation_generator:
        raise HTTPException(status_code=500, detail="Documentation not initialized")
    
    try:
        content = documentation_generator.export_documentation(format)
        
        # Determine filename and content type
        if format == DocumentationType.OPENAPI:
            default_filename = "openapi.json"
            content_type = "application/json"
        elif format == DocumentationType.POSTMAN:
            default_filename = "postman_collection.json"
            content_type = "application/json"
        elif format == DocumentationType.MARKDOWN:
            default_filename = "api_docs.md"
            content_type = "text/markdown"
        elif format == DocumentationType.HTML:
            default_filename = "api_docs.html"
            content_type = "text/html"
        else:
            default_filename = "documentation.txt"
            content_type = "text/plain"
        
        filename = filename or default_filename
        
        return JSONResponse(
            content={"content": content},
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": content_type
            }
        )
    except Exception as e:
        logger.error(f"Error exporting documentation: {e}")
        raise HTTPException(status_code=500, detail="Failed to export documentation")