#!/usr/bin/env python3
"""
Comprehensive API documentation enhancement module for production environments.
Provides advanced OpenAPI schema generation, documentation utilities, and integration
with existing security and monitoring systems.
"""

import json
import os
from typing import Dict, Any, List, Optional, Union, Type, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.models import OpenAPI, Info, Contact, License, Server, Tag
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from .logging_config import get_logger
from .config import get_settings
from .api_enhancements import APIError, ValidationError, ErrorDetail


logger = get_logger(__name__)
settings = get_settings()


class DocumentationLevel(Enum):
    """Documentation detail levels."""
    BASIC = "basic"
    DETAILED = "detailed"
    COMPREHENSIVE = "comprehensive"


class SecuritySchemeType(Enum):
    """Security scheme types."""
    BEARER = "bearer"
    API_KEY = "apiKey"
    OAUTH2 = "oauth2"
    BASIC = "basic"


@dataclass
class APIDocumentationConfig:
    """Configuration for API documentation generation."""
    title: str = "Cliper API"
    description: str = "Comprehensive API for clip management and analytics"
    version: str = "1.0.0"
    contact_name: str = "API Support"
    contact_email: str = "api-support@cliper.com"
    contact_url: str = "https://cliper.com/support"
    license_name: str = "MIT"
    license_url: str = "https://opensource.org/licenses/MIT"
    terms_of_service: str = "https://cliper.com/terms"
    documentation_level: DocumentationLevel = DocumentationLevel.COMPREHENSIVE
    include_examples: bool = True
    include_error_responses: bool = True
    include_security_schemes: bool = True
    include_rate_limiting: bool = True
    include_versioning: bool = True
    export_formats: List[str] = field(default_factory=lambda: ["json", "yaml"])


@dataclass
class EndpointDocumentation:
    """Documentation for a specific API endpoint."""
    path: str
    method: str
    summary: str
    description: str
    tags: List[str] = field(default_factory=list)
    examples: Dict[str, Any] = field(default_factory=dict)
    error_responses: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    security_requirements: List[str] = field(default_factory=list)
    rate_limit: Optional[str] = None
    deprecated: bool = False
    version_added: Optional[str] = None
    version_deprecated: Optional[str] = None


@dataclass
class SchemaDocumentation:
    """Documentation for API schemas/models."""
    name: str
    description: str
    examples: Dict[str, Any] = field(default_factory=dict)
    properties: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    required_fields: List[str] = field(default_factory=list)
    validation_rules: Dict[str, str] = field(default_factory=dict)


class APIDocumentationEnhancer:
    """Enhanced API documentation generator with production features."""
    
    def __init__(self, app: FastAPI, config: APIDocumentationConfig = None):
        self.app = app
        self.config = config or APIDocumentationConfig()
        self.logger = get_logger(__name__)
        
        # Documentation storage
        self.endpoint_docs: Dict[str, EndpointDocumentation] = {}
        self.schema_docs: Dict[str, SchemaDocumentation] = {}
        self.custom_examples: Dict[str, Any] = {}
        self.error_responses: Dict[int, Dict[str, Any]] = {}
        
        # Initialize default error responses
        self._initialize_default_error_responses()
        
        # Initialize security schemes
        self._initialize_security_schemes()
        
        # Initialize tags
        self._initialize_tags()
    
    def _initialize_default_error_responses(self):
        """Initialize standard error response schemas."""
        self.error_responses = {
            400: {
                "description": "Bad Request - Invalid input parameters",
                "content": {
                    "application/json": {
                        "schema": ValidationError.schema(),
                        "examples": {
                            "validation_error": {
                                "summary": "Validation Error Example",
                                "value": {
                                    "error": "validation_error",
                                    "message": "Request validation failed",
                                    "details": [
                                        {
                                            "field": "email",
                                            "message": "Invalid email format",
                                            "code": "invalid_email"
                                        }
                                    ],
                                    "timestamp": "2024-01-01T12:00:00Z"
                                }
                            }
                        }
                    }
                }
            },
            401: {
                "description": "Unauthorized - Authentication required",
                "content": {
                    "application/json": {
                        "schema": APIError.schema(),
                        "examples": {
                            "unauthorized": {
                                "summary": "Authentication Required",
                                "value": {
                                    "error": "unauthorized",
                                    "message": "Authentication credentials required",
                                    "timestamp": "2024-01-01T12:00:00Z"
                                }
                            }
                        }
                    }
                }
            },
            403: {
                "description": "Forbidden - Insufficient permissions",
                "content": {
                    "application/json": {
                        "schema": APIError.schema(),
                        "examples": {
                            "forbidden": {
                                "summary": "Insufficient Permissions",
                                "value": {
                                    "error": "forbidden",
                                    "message": "Insufficient permissions to access this resource",
                                    "timestamp": "2024-01-01T12:00:00Z"
                                }
                            }
                        }
                    }
                }
            },
            404: {
                "description": "Not Found - Resource does not exist",
                "content": {
                    "application/json": {
                        "schema": APIError.schema(),
                        "examples": {
                            "not_found": {
                                "summary": "Resource Not Found",
                                "value": {
                                    "error": "not_found",
                                    "message": "The requested resource was not found",
                                    "timestamp": "2024-01-01T12:00:00Z"
                                }
                            }
                        }
                    }
                }
            },
            422: {
                "description": "Unprocessable Entity - Request validation failed",
                "content": {
                    "application/json": {
                        "schema": ValidationError.schema(),
                        "examples": {
                            "validation_failed": {
                                "summary": "Request Validation Failed",
                                "value": {
                                    "error": "validation_error",
                                    "message": "Request validation failed",
                                    "details": [
                                        {
                                            "field": "title",
                                            "message": "Field is required",
                                            "code": "required"
                                        }
                                    ],
                                    "timestamp": "2024-01-01T12:00:00Z"
                                }
                            }
                        }
                    }
                }
            },
            429: {
                "description": "Too Many Requests - Rate limit exceeded",
                "content": {
                    "application/json": {
                        "schema": APIError.schema(),
                        "examples": {
                            "rate_limit_exceeded": {
                                "summary": "Rate Limit Exceeded",
                                "value": {
                                    "error": "rate_limit_exceeded",
                                    "message": "Rate limit exceeded. Please try again later.",
                                    "timestamp": "2024-01-01T12:00:00Z"
                                }
                            }
                        }
                    }
                }
            },
            500: {
                "description": "Internal Server Error - Unexpected server error",
                "content": {
                    "application/json": {
                        "schema": APIError.schema(),
                        "examples": {
                            "internal_error": {
                                "summary": "Internal Server Error",
                                "value": {
                                    "error": "internal_server_error",
                                    "message": "An unexpected error occurred",
                                    "timestamp": "2024-01-01T12:00:00Z"
                                }
                            }
                        }
                    }
                }
            }
        }
    
    def _initialize_security_schemes(self):
        """Initialize security schemes for the API."""
        self.security_schemes = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT Bearer token authentication"
            },
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key authentication"
            },
            "OAuth2": {
                "type": "oauth2",
                "flows": {
                    "authorizationCode": {
                        "authorizationUrl": "https://api.cliper.com/oauth/authorize",
                        "tokenUrl": "https://api.cliper.com/oauth/token",
                        "scopes": {
                            "read": "Read access to resources",
                            "write": "Write access to resources",
                            "admin": "Administrative access"
                        }
                    }
                },
                "description": "OAuth2 authentication with authorization code flow"
            }
        }
    
    def _initialize_tags(self):
        """Initialize API tags for organization."""
        self.tags = [
            {
                "name": "Authentication",
                "description": "User authentication and authorization endpoints"
            },
            {
                "name": "Clips",
                "description": "Clip management and operations"
            },
            {
                "name": "Users",
                "description": "User management and profile operations"
            },
            {
                "name": "Analytics",
                "description": "Analytics and reporting endpoints"
            },
            {
                "name": "Search",
                "description": "Search and discovery functionality"
            },
            {
                "name": "Admin",
                "description": "Administrative operations (admin access required)"
            },
            {
                "name": "System",
                "description": "System health and monitoring endpoints"
            }
        ]
    
    def add_endpoint_documentation(
        self,
        path: str,
        method: str,
        summary: str,
        description: str,
        tags: List[str] = None,
        examples: Dict[str, Any] = None,
        error_responses: Dict[int, Dict[str, Any]] = None,
        security_requirements: List[str] = None,
        rate_limit: str = None,
        deprecated: bool = False,
        version_added: str = None
    ):
        """Add documentation for a specific endpoint."""
        endpoint_key = f"{method.upper()}:{path}"
        
        self.endpoint_docs[endpoint_key] = EndpointDocumentation(
            path=path,
            method=method.upper(),
            summary=summary,
            description=description,
            tags=tags or [],
            examples=examples or {},
            error_responses=error_responses or {},
            security_requirements=security_requirements or [],
            rate_limit=rate_limit,
            deprecated=deprecated,
            version_added=version_added
        )
    
    def add_schema_documentation(
        self,
        name: str,
        description: str,
        examples: Dict[str, Any] = None,
        properties: Dict[str, Dict[str, Any]] = None,
        required_fields: List[str] = None,
        validation_rules: Dict[str, str] = None
    ):
        """Add documentation for a schema/model."""
        self.schema_docs[name] = SchemaDocumentation(
            name=name,
            description=description,
            examples=examples or {},
            properties=properties or {},
            required_fields=required_fields or [],
            validation_rules=validation_rules or {}
        )
    
    def generate_enhanced_openapi(self) -> Dict[str, Any]:
        """Generate enhanced OpenAPI specification."""
        try:
            # Get base OpenAPI spec
            openapi_schema = get_openapi(
                title=self.config.title,
                version=self.config.version,
                description=self.config.description,
                routes=self.app.routes,
                tags=self.tags
            )
            
            # Enhance with additional information
            self._enhance_info_section(openapi_schema)
            self._enhance_servers_section(openapi_schema)
            self._enhance_security_section(openapi_schema)
            self._enhance_paths_section(openapi_schema)
            self._enhance_components_section(openapi_schema)
            
            # Add custom extensions
            self._add_custom_extensions(openapi_schema)
            
            return openapi_schema
            
        except Exception as e:
            self.logger.error(f"Error generating enhanced OpenAPI spec: {e}")
            raise
    
    def _enhance_info_section(self, openapi_schema: Dict[str, Any]):
        """Enhance the info section of OpenAPI spec."""
        info = openapi_schema.get("info", {})
        
        # Add contact information
        info["contact"] = {
            "name": self.config.contact_name,
            "email": self.config.contact_email,
            "url": self.config.contact_url
        }
        
        # Add license information
        info["license"] = {
            "name": self.config.license_name,
            "url": self.config.license_url
        }
        
        # Add terms of service
        info["termsOfService"] = self.config.terms_of_service
        
        # Add custom extensions
        info["x-api-id"] = "cliper-api"
        info["x-audience"] = "public"
        info["x-api-category"] = "media-management"
        
        openapi_schema["info"] = info
    
    def _enhance_servers_section(self, openapi_schema: Dict[str, Any]):
        """Enhance the servers section of OpenAPI spec."""
        servers = [
            {
                "url": "https://api.cliper.com/v1",
                "description": "Production server"
            },
            {
                "url": "https://staging-api.cliper.com/v1",
                "description": "Staging server"
            },
            {
                "url": "http://localhost:8000/v1",
                "description": "Development server"
            }
        ]
        
        openapi_schema["servers"] = servers
    
    def _enhance_security_section(self, openapi_schema: Dict[str, Any]):
        """Enhance security schemes and requirements."""
        if not self.config.include_security_schemes:
            return
        
        # Add security schemes to components
        components = openapi_schema.setdefault("components", {})
        components["securitySchemes"] = self.security_schemes
        
        # Add global security requirements
        openapi_schema["security"] = [
            {"BearerAuth": []},
            {"ApiKeyAuth": []}
        ]
    
    def _enhance_paths_section(self, openapi_schema: Dict[str, Any]):
        """Enhance paths with additional documentation."""
        paths = openapi_schema.get("paths", {})
        
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method.lower() in ["get", "post", "put", "patch", "delete"]:
                    self._enhance_operation(operation, path, method)
        
        openapi_schema["paths"] = paths
    
    def _enhance_operation(self, operation: Dict[str, Any], path: str, method: str):
        """Enhance a single operation with additional documentation."""
        endpoint_key = f"{method.upper()}:{path}"
        endpoint_doc = self.endpoint_docs.get(endpoint_key)
        
        # Add standard error responses
        if self.config.include_error_responses:
            responses = operation.setdefault("responses", {})
            
            # Add common error responses
            for status_code, error_response in self.error_responses.items():
                if str(status_code) not in responses:
                    responses[str(status_code)] = error_response
        
        # Add rate limiting information
        if self.config.include_rate_limiting:
            operation.setdefault("x-rate-limit", "100 requests per minute")
        
        # Add versioning information
        if self.config.include_versioning:
            operation.setdefault("x-version", "1.0")
        
        # Add endpoint-specific documentation
        if endpoint_doc:
            if endpoint_doc.rate_limit:
                operation["x-rate-limit"] = endpoint_doc.rate_limit
            
            if endpoint_doc.deprecated:
                operation["deprecated"] = True
            
            if endpoint_doc.version_added:
                operation["x-version-added"] = endpoint_doc.version_added
            
            # Add examples to request body
            if endpoint_doc.examples and "requestBody" in operation:
                request_body = operation["requestBody"]
                content = request_body.get("content", {})
                
                for media_type, media_content in content.items():
                    if "examples" not in media_content:
                        media_content["examples"] = endpoint_doc.examples
    
    def _enhance_components_section(self, openapi_schema: Dict[str, Any]):
        """Enhance components section with additional schemas and examples."""
        components = openapi_schema.setdefault("components", {})
        
        # Add custom examples
        if self.custom_examples:
            components["examples"] = self.custom_examples
        
        # Enhance existing schemas with documentation
        schemas = components.get("schemas", {})
        
        for schema_name, schema_doc in self.schema_docs.items():
            if schema_name in schemas:
                schema = schemas[schema_name]
                
                # Add description
                if schema_doc.description:
                    schema["description"] = schema_doc.description
                
                # Add examples
                if schema_doc.examples:
                    schema["examples"] = schema_doc.examples
                
                # Add property descriptions
                if schema_doc.properties and "properties" in schema:
                    for prop_name, prop_doc in schema_doc.properties.items():
                        if prop_name in schema["properties"]:
                            schema["properties"][prop_name].update(prop_doc)
    
    def _add_custom_extensions(self, openapi_schema: Dict[str, Any]):
        """Add custom OpenAPI extensions."""
        # Add API metadata
        openapi_schema["x-api-metadata"] = {
            "generated_at": datetime.utcnow().isoformat(),
            "generator": "cliper-api-docs",
            "version": "1.0.0",
            "documentation_level": self.config.documentation_level.value
        }
        
        # Add rate limiting information
        openapi_schema["x-rate-limiting"] = {
            "default_limit": "100 requests per minute",
            "burst_limit": "200 requests per minute",
            "policies": [
                {
                    "name": "authenticated",
                    "limit": "1000 requests per hour"
                },
                {
                    "name": "anonymous",
                    "limit": "100 requests per hour"
                }
            ]
        }
        
        # Add error handling information
        openapi_schema["x-error-handling"] = {
            "error_format": "RFC 7807 Problem Details",
            "error_codes": list(self.error_responses.keys()),
            "retry_policy": {
                "max_retries": 3,
                "backoff_strategy": "exponential",
                "retry_codes": [429, 500, 502, 503, 504]
            }
        }
    
    def export_documentation(self, output_dir: str = "docs/api") -> Dict[str, str]:
        """Export API documentation in multiple formats."""
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Generate OpenAPI spec
            openapi_spec = self.generate_enhanced_openapi()
            
            exported_files = {}
            
            # Export JSON format
            if "json" in self.config.export_formats:
                json_file = output_path / "openapi.json"
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(openapi_spec, f, indent=2, ensure_ascii=False)
                exported_files["json"] = str(json_file)
            
            # Export YAML format
            if "yaml" in self.config.export_formats:
                try:
                    import yaml
                    yaml_file = output_path / "openapi.yaml"
                    with open(yaml_file, "w", encoding="utf-8") as f:
                        yaml.dump(openapi_spec, f, default_flow_style=False, allow_unicode=True)
                    exported_files["yaml"] = str(yaml_file)
                except ImportError:
                    self.logger.warning("PyYAML not installed, skipping YAML export")
            
            # Export HTML documentation
            if "html" in self.config.export_formats:
                html_file = self._generate_html_documentation(openapi_spec, output_path)
                if html_file:
                    exported_files["html"] = html_file
            
            self.logger.info(f"Documentation exported to {output_dir}")
            return exported_files
            
        except Exception as e:
            self.logger.error(f"Error exporting documentation: {e}")
            raise
    
    def _generate_html_documentation(self, openapi_spec: Dict[str, Any], output_path: Path) -> Optional[str]:
        """Generate HTML documentation using Swagger UI."""
        try:
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{self.config.title} - API Documentation</title>
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@4.15.5/swagger-ui.css" />
    <style>
        html {{
            box-sizing: border-box;
            overflow: -moz-scrollbars-vertical;
            overflow-y: scroll;
        }}
        *, *:before, *:after {{
            box-sizing: inherit;
        }}
        body {{
            margin:0;
            background: #fafafa;
        }}
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@4.15.5/swagger-ui-bundle.js"></script>
    <script src="https://unpkg.com/swagger-ui-dist@4.15.5/swagger-ui-standalone-preset.js"></script>
    <script>
        window.onload = function() {{
            const ui = SwaggerUIBundle({{
                spec: {json.dumps(openapi_spec)},
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                layout: "StandaloneLayout"
            }});
        }};
    </script>
</body>
</html>
            """
            
            html_file = output_path / "index.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            return str(html_file)
            
        except Exception as e:
            self.logger.error(f"Error generating HTML documentation: {e}")
            return None
    
    def validate_openapi_spec(self, openapi_spec: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate OpenAPI specification for compliance."""
        try:
            if openapi_spec is None:
                openapi_spec = self.generate_enhanced_openapi()
            
            validation_results = {
                "valid": True,
                "errors": [],
                "warnings": [],
                "info": []
            }
            
            # Basic structure validation
            required_fields = ["openapi", "info", "paths"]
            for field in required_fields:
                if field not in openapi_spec:
                    validation_results["errors"].append(f"Missing required field: {field}")
                    validation_results["valid"] = False
            
            # Info section validation
            if "info" in openapi_spec:
                info = openapi_spec["info"]
                required_info_fields = ["title", "version"]
                for field in required_info_fields:
                    if field not in info:
                        validation_results["errors"].append(f"Missing required info field: {field}")
                        validation_results["valid"] = False
            
            # Paths validation
            if "paths" in openapi_spec:
                paths = openapi_spec["paths"]
                if not paths:
                    validation_results["warnings"].append("No paths defined in the API")
                
                for path, path_item in paths.items():
                    if not path.startswith("/"):
                        validation_results["errors"].append(f"Path '{path}' must start with '/'")
                        validation_results["valid"] = False
            
            # Security schemes validation
            if "components" in openapi_spec and "securitySchemes" in openapi_spec["components"]:
                validation_results["info"].append("Security schemes are properly defined")
            else:
                validation_results["warnings"].append("No security schemes defined")
            
            return validation_results
            
        except Exception as e:
            self.logger.error(f"Error validating OpenAPI spec: {e}")
            return {
                "valid": False,
                "errors": [f"Validation error: {str(e)}"],
                "warnings": [],
                "info": []
            }


class DocumentationMiddleware(BaseHTTPMiddleware):
    """Middleware to enhance API documentation with runtime information."""
    
    def __init__(self, app, enhancer: APIDocumentationEnhancer):
        super().__init__(app)
        self.enhancer = enhancer
        self.logger = get_logger(__name__)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and enhance documentation."""
        try:
            # Process request
            response = await call_next(request)
            
            # Add documentation headers
            if request.url.path.startswith("/docs") or request.url.path.startswith("/openapi"):
                response.headers["X-API-Docs-Version"] = self.enhancer.config.version
                response.headers["X-API-Docs-Generated"] = datetime.utcnow().isoformat()
            
            return response
            
        except Exception as e:
            self.logger.error(f"Documentation middleware error: {e}")
            return await call_next(request)


# Utility functions for easy integration
def setup_api_documentation(
    app: FastAPI,
    config: APIDocumentationConfig = None,
    auto_export: bool = False,
    export_dir: str = "docs/api"
) -> APIDocumentationEnhancer:
    """Setup API documentation enhancement for a FastAPI app."""
    enhancer = APIDocumentationEnhancer(app, config)
    
    # Add documentation middleware
    app.add_middleware(DocumentationMiddleware, enhancer=enhancer)
    
    # Override OpenAPI generation
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        
        app.openapi_schema = enhancer.generate_enhanced_openapi()
        return app.openapi_schema
    
    app.openapi = custom_openapi
    
    # Auto-export documentation if requested
    if auto_export:
        try:
            enhancer.export_documentation(export_dir)
        except Exception as e:
            logger.error(f"Failed to auto-export documentation: {e}")
    
    return enhancer


def create_endpoint_docs(
    summary: str,
    description: str,
    tags: List[str] = None,
    examples: Dict[str, Any] = None,
    security: List[str] = None,
    rate_limit: str = None
) -> Dict[str, Any]:
    """Create endpoint documentation metadata."""
    return {
        "summary": summary,
        "description": description,
        "tags": tags or [],
        "examples": examples or {},
        "security_requirements": security or [],
        "rate_limit": rate_limit
    }


def create_response_examples(success_example: Any, error_examples: Dict[int, Any] = None) -> Dict[str, Any]:
    """Create response examples for endpoint documentation."""
    examples = {
        "success": {
            "summary": "Successful response",
            "value": success_example
        }
    }
    
    if error_examples:
        for status_code, example in error_examples.items():
            examples[f"error_{status_code}"] = {
                "summary": f"Error {status_code}",
                "value": example
            }
    
    return examples


# Export all public components
__all__ = [
    "APIDocumentationEnhancer",
    "APIDocumentationConfig",
    "EndpointDocumentation",
    "SchemaDocumentation",
    "DocumentationLevel",
    "SecuritySchemeType",
    "DocumentationMiddleware",
    "setup_api_documentation",
    "create_endpoint_docs",
    "create_response_examples"
]