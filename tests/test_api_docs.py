#!/usr/bin/env python3
"""
Comprehensive integration tests for API documentation enhancement module.

Tests:
- OpenAPI schema generation and validation
- Documentation endpoint functionality
- Security scheme integration
- Error response documentation
- Custom extensions and metadata
- Performance and reliability
"""

import json
import pytest
import yaml
from typing import Dict, Any
from unittest.mock import Mock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import validate, ValidationError as JsonSchemaValidationError

from api.core.api_docs import (
    APIDocumentationEnhancer,
    DocumentationLevel,
    SecuritySchemeType,
    APIDocumentationConfig,
    setup_api_documentation,
    create_endpoint_docs,
    create_response_examples
)


class TestAPIDocumentationEnhancer:
    """Test the API documentation enhancer functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI(
            title="Test API",
            description="Test API for documentation",
            version="1.0.0"
        )
        
        self.config = APIDocumentationConfig(
            title="Enhanced Test API",
            description="Enhanced test API with comprehensive documentation",
            version="1.0.0",
            contact={"name": "Test Team", "email": "test@example.com"},
            license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
            servers=[
                {"url": "https://api.test.com", "description": "Production server"},
                {"url": "https://staging-api.test.com", "description": "Staging server"}
            ],
            documentation_level=DocumentationLevel.COMPREHENSIVE
        )
        
        self.enhancer = APIDocumentationEnhancer(self.config)
    
    def test_enhancer_initialization(self):
        """Test enhancer initialization with configuration."""
        assert self.enhancer.config == self.config
        assert self.enhancer.config.documentation_level == DocumentationLevel.COMPREHENSIVE
    
    def test_enhance_openapi_schema_basic(self):
        """Test basic OpenAPI schema enhancement."""
        # Add a simple endpoint
        @self.app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        # Generate base schema
        from fastapi.openapi.utils import get_openapi
        base_schema = get_openapi(
            title=self.app.title,
            version=self.app.version,
            description=self.app.description,
            routes=self.app.routes
        )
        
        # Enhance schema
        enhanced_schema = self.enhancer.enhance_openapi_schema(base_schema)
        
        # Verify enhancements
        assert enhanced_schema["info"]["title"] == "Enhanced Test API"
        assert enhanced_schema["info"]["description"] == "Enhanced test API with comprehensive documentation"
        assert "contact" in enhanced_schema["info"]
        assert "license" in enhanced_schema["info"]
        assert "servers" in enhanced_schema
        assert len(enhanced_schema["servers"]) == 2
    
    def test_security_schemes_integration(self):
        """Test security schemes integration."""
        base_schema = {"info": {"title": "Test", "version": "1.0.0"}, "paths": {}, "components": {}}
        enhanced_schema = self.enhancer.enhance_openapi_schema(base_schema)
        
        # Verify security schemes
        security_schemes = enhanced_schema["components"]["securitySchemes"]
        assert "BearerAuth" in security_schemes
        assert "ApiKeyAuth" in security_schemes
        assert security_schemes["BearerAuth"]["type"] == "http"
        assert security_schemes["BearerAuth"]["scheme"] == "bearer"
        assert security_schemes["ApiKeyAuth"]["type"] == "apiKey"
        assert security_schemes["ApiKeyAuth"]["in"] == "header"
    
    def test_error_response_schemas(self):
        """Test error response schema generation."""
        base_schema = {"info": {"title": "Test", "version": "1.0.0"}, "paths": {}, "components": {}}
        enhanced_schema = self.enhancer.enhance_openapi_schema(base_schema)
        
        # Verify error response schemas
        schemas = enhanced_schema["components"]["schemas"]
        assert "ErrorResponse" in schemas
        assert "ValidationErrorResponse" in schemas
        assert "RateLimitErrorResponse" in schemas
        assert "AuthErrorResponse" in schemas
        
        # Verify error response structure
        error_schema = schemas["ErrorResponse"]
        assert "properties" in error_schema
        assert "error" in error_schema["properties"]
        assert "message" in error_schema["properties"]
        assert "timestamp" in error_schema["properties"]
    
    def test_custom_extensions(self):
        """Test custom OpenAPI extensions."""
        base_schema = {"info": {"title": "Test", "version": "1.0.0"}, "paths": {}, "components": {}}
        enhanced_schema = self.enhancer.enhance_openapi_schema(base_schema)
        
        # Verify custom extensions
        assert "x-rate-limiting" in enhanced_schema
        assert "x-api-version" in enhanced_schema
        assert "x-monitoring" in enhanced_schema
        
        # Verify rate limiting extension
        rate_limiting = enhanced_schema["x-rate-limiting"]
        assert "default_limits" in rate_limiting
        assert "headers" in rate_limiting
        
        # Verify monitoring extension
        monitoring = enhanced_schema["x-monitoring"]
        assert "health_check" in monitoring
        assert "metrics" in monitoring


class TestDocumentationEndpoints:
    """Test documentation endpoint functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI(title="Test API", version="1.0.0")
        
        # Add test endpoint
        @self.app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        # Setup enhanced documentation
        setup_api_documentation(self.app)
        
        self.client = TestClient(self.app)
    
    def test_enhanced_openapi_json_endpoint(self):
        """Test enhanced OpenAPI JSON endpoint."""
        response = self.client.get("/docs/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        assert "info" in schema
        assert "paths" in schema
        assert "components" in schema
        
        # Verify enhancements
        assert "securitySchemes" in schema["components"]
        assert "x-rate-limiting" in schema
        assert "x-api-version" in schema
    
    def test_enhanced_openapi_yaml_endpoint(self):
        """Test enhanced OpenAPI YAML endpoint."""
        response = self.client.get("/docs/openapi.yaml")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/x-yaml"
        
        # Verify YAML content
        schema = yaml.safe_load(response.content)
        assert "info" in schema
        assert "paths" in schema
        assert "components" in schema
    
    def test_swagger_ui_endpoint(self):
        """Test custom Swagger UI endpoint."""
        response = self.client.get("/docs/swagger")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        
        # Verify HTML content contains Swagger UI
        content = response.content.decode()
        assert "swagger-ui" in content.lower()
        assert "openapi.json" in content
    
    def test_redoc_endpoint(self):
        """Test custom ReDoc endpoint."""
        response = self.client.get("/docs/redoc")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        
        # Verify HTML content contains ReDoc
        content = response.content.decode()
        assert "redoc" in content.lower()
        assert "openapi.json" in content
    
    def test_health_endpoint(self):
        """Test documentation health endpoint."""
        response = self.client.get("/docs/health")
        assert response.status_code == 200
        
        health_data = response.json()
        assert "status" in health_data
        assert "documentation" in health_data
        assert "endpoints" in health_data
        assert health_data["status"] == "healthy"


class TestUtilityFunctions:
    """Test utility functions for documentation."""
    
    def test_create_endpoint_docs(self):
        """Test endpoint documentation creation."""
        docs = create_endpoint_docs(
            summary="Test endpoint",
            description="A test endpoint for documentation",
            tags=["test"],
            responses={
                200: {"description": "Success", "content": {"application/json": {"example": {"message": "success"}}}},
                400: {"description": "Bad request"}
            }
        )
        
        assert docs["summary"] == "Test endpoint"
        assert docs["description"] == "A test endpoint for documentation"
        assert docs["tags"] == ["test"]
        assert 200 in docs["responses"]
        assert 400 in docs["responses"]
    
    def test_create_response_examples(self):
        """Test response examples creation."""
        examples = create_response_examples(
            success_example={"message": "success", "data": {"id": 1}},
            error_examples={
                400: {"error": "bad_request", "message": "Invalid input"},
                404: {"error": "not_found", "message": "Resource not found"}
            }
        )
        
        assert "200" in examples
        assert "400" in examples
        assert "404" in examples
        
        # Verify success example
        success_example = examples["200"]
        assert "content" in success_example
        assert "application/json" in success_example["content"]
        
        # Verify error examples
        error_example = examples["400"]
        assert "content" in error_example
        assert "application/json" in error_example["content"]


class TestPerformanceAndReliability:
    """Test performance and reliability of documentation system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI(title="Performance Test API", version="1.0.0")
        
        # Add multiple test endpoints
        for i in range(10):
            def create_endpoint(index):
                @self.app.get(f"/test{index}")
                async def test_endpoint():
                    return {"message": f"test{index}"}
                return test_endpoint
            
            create_endpoint(i)
        
        setup_api_documentation(self.app)
        self.client = TestClient(self.app)
    
    def test_schema_generation_performance(self):
        """Test schema generation performance with multiple endpoints."""
        import time
        
        start_time = time.time()
        response = self.client.get("/docs/openapi.json")
        end_time = time.time()
        
        assert response.status_code == 200
        
        # Schema generation should be fast (< 1 second for 10 endpoints)
        generation_time = end_time - start_time
        assert generation_time < 1.0, f"Schema generation took {generation_time:.2f}s, expected < 1.0s"
    
    def test_concurrent_documentation_access(self):
        """Test concurrent access to documentation endpoints."""
        import threading
        import time
        
        results = []
        
        def access_docs():
            try:
                response = self.client.get("/docs/openapi.json")
                results.append(response.status_code == 200)
            except Exception as e:
                results.append(False)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=access_docs)
            threads.append(thread)
        
        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        
        # All requests should succeed
        assert all(results), f"Some concurrent requests failed: {results}"
        
        # Concurrent access should be reasonably fast
        total_time = end_time - start_time
        assert total_time < 5.0, f"Concurrent access took {total_time:.2f}s, expected < 5.0s"
    
    def test_memory_usage_stability(self):
        """Test memory usage stability during repeated access."""
        import gc
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Make multiple requests
        for _ in range(50):
            response = self.client.get("/docs/openapi.json")
            assert response.status_code == 200
        
        # Force garbage collection
        gc.collect()
        
        # Check final memory usage
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (< 50MB)
        max_increase = 50 * 1024 * 1024  # 50MB
        assert memory_increase < max_increase, f"Memory increased by {memory_increase / 1024 / 1024:.2f}MB, expected < 50MB"


class TestOpenAPIValidation:
    """Test OpenAPI specification validation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI(title="Validation Test API", version="1.0.0")
        
        # Add test endpoint with comprehensive documentation
        @self.app.post("/test", **create_endpoint_docs(
            summary="Test endpoint",
            description="A comprehensive test endpoint",
            tags=["test"],
            responses=create_response_examples(
                success_example={"message": "success"},
                error_examples={400: {"error": "bad_request"}}
            )
        ))
        async def test_endpoint(data: dict):
            return {"message": "success"}
        
        setup_api_documentation(self.app)
        self.client = TestClient(self.app)
    
    def test_openapi_schema_validation(self):
        """Test OpenAPI schema validation against specification."""
        response = self.client.get("/docs/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        
        # Basic OpenAPI 3.0 structure validation
        required_fields = ["openapi", "info", "paths"]
        for field in required_fields:
            assert field in schema, f"Required field '{field}' missing from OpenAPI schema"
        
        # Validate info section
        info = schema["info"]
        assert "title" in info
        assert "version" in info
        
        # Validate paths section
        paths = schema["paths"]
        assert isinstance(paths, dict)
        
        # Validate components section if present
        if "components" in schema:
            components = schema["components"]
            if "schemas" in components:
                assert isinstance(components["schemas"], dict)
            if "securitySchemes" in components:
                assert isinstance(components["securitySchemes"], dict)
    
    def test_response_schema_consistency(self):
        """Test response schema consistency."""
        response = self.client.get("/docs/openapi.json")
        schema = response.json()
        
        # Check that all referenced schemas exist
        if "components" in schema and "schemas" in schema["components"]:
            schemas = schema["components"]["schemas"]
            
            # Verify error response schemas are present
            error_schemas = ["ErrorResponse", "ValidationErrorResponse", "RateLimitErrorResponse", "AuthErrorResponse"]
            for error_schema in error_schemas:
                assert error_schema in schemas, f"Error schema '{error_schema}' not found in components"
    
    def test_security_scheme_validation(self):
        """Test security scheme validation."""
        response = self.client.get("/docs/openapi.json")
        schema = response.json()
        
        if "components" in schema and "securitySchemes" in schema["components"]:
            security_schemes = schema["components"]["securitySchemes"]
            
            # Validate Bearer auth scheme
            if "BearerAuth" in security_schemes:
                bearer_auth = security_schemes["BearerAuth"]
                assert bearer_auth["type"] == "http"
                assert bearer_auth["scheme"] == "bearer"
            
            # Validate API key scheme
            if "ApiKeyAuth" in security_schemes:
                api_key_auth = security_schemes["ApiKeyAuth"]
                assert api_key_auth["type"] == "apiKey"
                assert "in" in api_key_auth
                assert "name" in api_key_auth


if __name__ == "__main__":
    pytest.main([__file__, "-v"])