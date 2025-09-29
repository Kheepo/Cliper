#!/usr/bin/env python3
"""
Comprehensive integration tests for API documentation enhancement module.
Tests OpenAPI schema generation, security schemes, documentation routes, and validation.
"""

import pytest
import json
import yaml
from typing import Dict, Any
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from api.core.api_docs import (
    APIDocumentationEnhancer,
    DocumentationMiddleware,
    DocumentationGenerator,
    setup_api_documentation,
    create_endpoint_docs,
    create_response_examples,
    DocumentationLevel,
    SecuritySchemeType
)


class TestAPIDocumentationEnhancer:
    """Test the API documentation enhancer."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI(
            title="Test API",
            description="Test API for documentation",
            version="1.0.0"
        )
        self.enhancer = APIDocumentationEnhancer()
    
    def test_enhance_openapi_schema_basic(self):
        """Test basic OpenAPI schema enhancement."""
        original_schema = {
            "openapi": "3.0.2",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {},
            "components": {}
        }
        
        enhanced = self.enhancer.enhance_openapi_schema(
            original_schema,
            self.app
        )
        
        # Check enhanced info section
        assert "contact" in enhanced["info"]
        assert "license" in enhanced["info"]
        assert "termsOfService" in enhanced["info"]
        
        # Check servers section
        assert "servers" in enhanced
        assert len(enhanced["servers"]) > 0
        
        # Check security schemes
        assert "components" in enhanced
        assert "securitySchemes" in enhanced["components"]
        
        # Check custom extensions
        assert "x-rate-limiting" in enhanced
        assert "x-api-version" in enhanced
        assert "x-monitoring" in enhanced
    
    def test_enhance_security_schemes(self):
        """Test security schemes enhancement."""
        schema = {"components": {}}
        
        self.enhancer._enhance_security_schemes(schema)
        
        security_schemes = schema["components"]["securitySchemes"]
        
        # Check Bearer token scheme
        assert "BearerAuth" in security_schemes
        bearer_auth = security_schemes["BearerAuth"]
        assert bearer_auth["type"] == "http"
        assert bearer_auth["scheme"] == "bearer"
        assert bearer_auth["bearerFormat"] == "JWT"
        
        # Check API Key scheme
        assert "ApiKeyAuth" in security_schemes
        api_key_auth = security_schemes["ApiKeyAuth"]
        assert api_key_auth["type"] == "apiKey"
        assert api_key_auth["in"] == "header"
        assert api_key_auth["name"] == "X-API-Key"
    
    def test_enhance_error_responses(self):
        """Test error responses enhancement."""
        schema = {"components": {"schemas": {}}}
        
        self.enhancer._enhance_error_responses(schema)
        
        schemas = schema["components"]["schemas"]
        
        # Check error schemas
        assert "ErrorResponse" in schemas
        assert "ValidationError" in schemas
        assert "RateLimitError" in schemas
        assert "AuthenticationError" in schemas
        
        # Validate error response structure
        error_response = schemas["ErrorResponse"]
        assert "properties" in error_response
        assert "error" in error_response["properties"]
        assert "message" in error_response["properties"]
        assert "timestamp" in error_response["properties"]
    
    def test_add_custom_extensions(self):
        """Test custom extensions addition."""
        schema = {}
        
        self.enhancer._add_custom_extensions(schema)
        
        # Check rate limiting extension
        assert "x-rate-limiting" in schema
        rate_limiting = schema["x-rate-limiting"]
        assert "global" in rate_limiting
        assert "endpoints" in rate_limiting
        
        # Check API version extension
        assert "x-api-version" in schema
        version_info = schema["x-api-version"]
        assert "current" in version_info
        assert "supported" in version_info
        
        # Check monitoring extension
        assert "x-monitoring" in schema
        monitoring = schema["x-monitoring"]
        assert "health_check" in monitoring
        assert "metrics" in monitoring


class TestDocumentationMiddleware:
    """Test the documentation middleware."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI()
        self.middleware = DocumentationMiddleware(self.app)
        self.client = TestClient(self.app)
    
    def test_middleware_adds_headers(self):
        """Test that middleware adds documentation headers."""
        @self.app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        response = self.client.get("/test")
        
        # Check documentation headers
        assert "X-API-Docs" in response.headers
        assert "X-API-Version" in response.headers
        assert "X-Schema-Version" in response.headers
    
    def test_middleware_logs_access(self):
        """Test that middleware logs documentation access."""
        @self.app.get("/docs/openapi.json")
        async def docs_endpoint():
            return {"openapi": "3.0.2"}
        
        with patch('api.core.api_docs.logger') as mock_logger:
            response = self.client.get("/docs/openapi.json")
            
            # Check that access was logged
            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args[0][0]
            assert "Documentation accessed" in call_args


class TestDocumentationGenerator:
    """Test the documentation generator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI(
            title="Test API",
            description="Test API for documentation",
            version="1.0.0"
        )
        self.generator = DocumentationGenerator()
    
    def test_generate_openapi_json(self):
        """Test OpenAPI JSON generation."""
        schema = {
            "openapi": "3.0.2",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {}
        }
        
        json_output = self.generator.generate_openapi_json(schema)
        
        # Validate JSON format
        parsed = json.loads(json_output)
        assert parsed["openapi"] == "3.0.2"
        assert parsed["info"]["title"] == "Test API"
    
    def test_generate_openapi_yaml(self):
        """Test OpenAPI YAML generation."""
        schema = {
            "openapi": "3.0.2",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {}
        }
        
        yaml_output = self.generator.generate_openapi_yaml(schema)
        
        # Validate YAML format
        parsed = yaml.safe_load(yaml_output)
        assert parsed["openapi"] == "3.0.2"
        assert parsed["info"]["title"] == "Test API"
    
    def test_generate_postman_collection(self):
        """Test Postman collection generation."""
        schema = {
            "openapi": "3.0.2",
            "info": {"title": "Test API", "version": "1.0.0"},
            "servers": [{"url": "https://api.example.com"}],
            "paths": {
                "/users": {
                    "get": {
                        "summary": "Get users",
                        "responses": {"200": {"description": "Success"}}
                    }
                }
            }
        }
        
        collection = self.generator.generate_postman_collection(schema)
        
        # Validate Postman collection structure
        parsed = json.loads(collection)
        assert "info" in parsed
        assert "item" in parsed
        assert parsed["info"]["name"] == "Test API"
    
    def test_generate_sdk_examples(self):
        """Test SDK examples generation."""
        endpoint_info = {
            "method": "GET",
            "path": "/users",
            "summary": "Get users",
            "parameters": [],
            "responses": {"200": {"description": "Success"}}
        }
        
        examples = self.generator.generate_sdk_examples(
            endpoint_info,
            "https://api.example.com"
        )
        
        # Check that examples are generated for different languages
        assert "python" in examples
        assert "javascript" in examples
        assert "curl" in examples
        
        # Validate Python example
        python_example = examples["python"]
        assert "import requests" in python_example
        assert "https://api.example.com/users" in python_example


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_create_endpoint_docs(self):
        """Test endpoint documentation creation."""
        docs = create_endpoint_docs(
            summary="Test endpoint",
            description="A test endpoint for documentation",
            tags=["test"],
            responses={
                200: {"description": "Success", "model": dict},
                400: {"description": "Bad request"}
            },
            examples=[
                {
                    "name": "Basic example",
                    "summary": "A basic example",
                    "value": {"message": "Hello, World!"}
                }
            ]
        )
        
        assert docs.summary == "Test endpoint"
        assert docs.description == "A test endpoint for documentation"
        assert "test" in docs.tags
        assert len(docs.responses) == 2
        assert len(docs.examples) == 1
    
    def test_create_response_examples(self):
        """Test response examples creation."""
        examples = create_response_examples({
            "success": {"message": "Operation successful", "data": {}},
            "error": {"error": "Invalid input", "code": "VALIDATION_ERROR"}
        })
        
        assert "success" in examples
        assert "error" in examples
        assert examples["success"]["value"]["message"] == "Operation successful"
        assert examples["error"]["value"]["error"] == "Invalid input"


class TestIntegration:
    """Integration tests for the complete documentation system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI(
            title="Integration Test API",
            description="API for integration testing",
            version="1.0.0"
        )
        
        # Add a test endpoint
        @self.app.get("/test")
        async def test_endpoint():
            """Test endpoint for documentation."""
            return {"message": "test"}
        
        # Setup enhanced documentation
        setup_api_documentation(self.app)
        
        self.client = TestClient(self.app)
    
    def test_enhanced_openapi_endpoint(self):
        """Test enhanced OpenAPI endpoint."""
        response = self.client.get("/docs/openapi.json")
        
        assert response.status_code == 200
        schema = response.json()
        
        # Check enhanced features
        assert "x-rate-limiting" in schema
        assert "x-api-version" in schema
        assert "x-monitoring" in schema
        
        # Check security schemes
        assert "components" in schema
        assert "securitySchemes" in schema["components"]
        assert "BearerAuth" in schema["components"]["securitySchemes"]
    
    def test_swagger_ui_endpoint(self):
        """Test Swagger UI endpoint."""
        response = self.client.get("/docs/swagger")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Swagger UI" in response.text
    
    def test_redoc_endpoint(self):
        """Test ReDoc endpoint."""
        response = self.client.get("/docs/redoc")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "ReDoc" in response.text
    
    def test_postman_collection_endpoint(self):
        """Test Postman collection endpoint."""
        response = self.client.get("/docs/postman")
        
        assert response.status_code == 200
        collection = response.json()
        
        # Check Postman collection structure
        assert "info" in collection
        assert "item" in collection
        assert collection["info"]["name"] == "Integration Test API"
    
    def test_health_check_endpoint(self):
        """Test documentation health check endpoint."""
        response = self.client.get("/docs/health")
        
        assert response.status_code == 200
        health = response.json()
        
        # Check health response structure
        assert "status" in health
        assert "documentation" in health
        assert "timestamp" in health
        assert health["status"] == "healthy"
    
    def test_yaml_export_endpoint(self):
        """Test YAML export endpoint."""
        response = self.client.get("/docs/openapi.yaml")
        
        assert response.status_code == 200
        assert "application/x-yaml" in response.headers["content-type"]
        
        # Validate YAML content
        yaml_content = yaml.safe_load(response.content)
        assert "openapi" in yaml_content
        assert "info" in yaml_content


@pytest.fixture
def sample_app():
    """Create a sample FastAPI app for testing."""
    app = FastAPI(
        title="Sample API",
        description="A sample API for testing",
        version="1.0.0"
    )
    
    @app.get("/users")
    async def get_users():
        """Get all users."""
        return [{"id": 1, "name": "John Doe"}]
    
    @app.post("/users")
    async def create_user(user: dict):
        """Create a new user."""
        return {"id": 2, "name": user.get("name", "Unknown")}
    
    return app


def test_full_documentation_workflow(sample_app):
    """Test the complete documentation workflow."""
    # Setup enhanced documentation
    setup_api_documentation(sample_app)
    
    client = TestClient(sample_app)
    
    # Test OpenAPI schema generation
    response = client.get("/docs/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    
    # Verify enhanced features
    assert "x-rate-limiting" in schema
    assert "x-api-version" in schema
    assert "x-monitoring" in schema
    
    # Verify security schemes
    security_schemes = schema["components"]["securitySchemes"]
    assert "BearerAuth" in security_schemes
    assert "ApiKeyAuth" in security_schemes
    
    # Verify error response schemas
    schemas = schema["components"]["schemas"]
    assert "ErrorResponse" in schemas
    assert "ValidationError" in schemas
    
    # Test documentation endpoints
    endpoints_to_test = [
        "/docs/swagger",
        "/docs/redoc",
        "/docs/postman",
        "/docs/health",
        "/docs/openapi.yaml"
    ]
    
    for endpoint in endpoints_to_test:
        response = client.get(endpoint)
        assert response.status_code == 200, f"Failed to access {endpoint}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])