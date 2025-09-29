#!/usr/bin/env python3
"""
Integration module for connecting API documentation with existing security and monitoring systems.
Provides seamless integration between documentation, authentication, rate limiting, and monitoring.
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from fastapi import FastAPI, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .api_docs import (
    APIDocumentationEnhancer,
    APIDocumentationConfig,
    DocumentationLevel,
    SecuritySchemeType
)
from ..security.middleware import SecurityMiddleware
from ..middleware.rate_limiting import RateLimitMiddleware
from ..middleware.auth_middleware import AuthMiddleware, require_auth, require_admin
from ..utils.monitoring import MetricsCollector, HealthChecker
from ..utils.health_checker import HealthCheckManager
from ..monitoring.performance_monitor import PerformanceMonitor
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class SecurityDocumentationIntegrator:
    """Integrates security middleware with API documentation."""
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.security_schemes = {}
        self.rate_limits = {}
        self.auth_requirements = {}
        
    def extract_security_info(self) -> Dict[str, Any]:
        """Extract security information from middleware."""
        security_info = {
            "authentication": self._extract_auth_info(),
            "rate_limiting": self._extract_rate_limit_info(),
            "security_headers": self._extract_security_headers(),
            "csrf_protection": self._extract_csrf_info()
        }
        
        logger.info("Extracted security information for documentation")
        return security_info
    
    def _extract_auth_info(self) -> Dict[str, Any]:
        """Extract authentication information."""
        return {
            "schemes": {
                "bearer": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "JWT token for user authentication"
                },
                "api_key": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                    "description": "API key for service-to-service authentication"
                }
            },
            "flows": {
                "authorization_code": {
                    "authorizationUrl": "/api/auth/authorize",
                    "tokenUrl": "/api/auth/token",
                    "scopes": {
                        "read": "Read access to resources",
                        "write": "Write access to resources",
                        "admin": "Administrative access"
                    }
                }
            },
            "roles": ["user", "premium", "admin"],
            "permissions": [
                "clips:read", "clips:write", "clips:delete",
                "users:read", "users:write", "admin:all"
            ]
        }
    
    def _extract_rate_limit_info(self) -> Dict[str, Any]:
        """Extract rate limiting information."""
        return {
            "global": {
                "requests_per_minute": 100,
                "requests_per_hour": 1000,
                "burst_limit": 20
            },
            "endpoints": {
                "/api/auth/login": {
                    "requests_per_minute": 5,
                    "window_minutes": 15,
                    "description": "Login attempts are limited to prevent brute force attacks"
                },
                "/api/clips/upload": {
                    "requests_per_hour": 10,
                    "max_file_size": "100MB",
                    "description": "Upload limits to manage server resources"
                },
                "/api/clips/process": {
                    "requests_per_minute": 5,
                    "concurrent_limit": 3,
                    "description": "Processing limits to ensure quality of service"
                }
            },
            "user_tiers": {
                "free": {"multiplier": 1.0, "description": "Standard rate limits"},
                "premium": {"multiplier": 5.0, "description": "5x higher rate limits"},
                "enterprise": {"multiplier": 20.0, "description": "20x higher rate limits"}
            }
        }
    
    def _extract_security_headers(self) -> Dict[str, Any]:
        """Extract security headers information."""
        return {
            "required_headers": {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "X-XSS-Protection": "1; mode=block",
                "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
                "Content-Security-Policy": "default-src 'self'"
            },
            "cors": {
                "allowed_origins": ["https://app.cliper.com", "https://admin.cliper.com"],
                "allowed_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allowed_headers": ["Authorization", "Content-Type", "X-API-Key"],
                "expose_headers": ["X-Request-ID", "X-Rate-Limit-Remaining"]
            }
        }
    
    def _extract_csrf_info(self) -> Dict[str, Any]:
        """Extract CSRF protection information."""
        return {
            "enabled": True,
            "token_header": "X-CSRF-Token",
            "safe_methods": ["GET", "HEAD", "OPTIONS", "TRACE"],
            "description": "CSRF protection for state-changing operations"
        }


class MonitoringDocumentationIntegrator:
    """Integrates monitoring systems with API documentation."""
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.metrics_collector = None
        self.health_checker = None
        self.performance_monitor = None
        
    def extract_monitoring_info(self) -> Dict[str, Any]:
        """Extract monitoring information for documentation."""
        monitoring_info = {
            "health_checks": self._extract_health_check_info(),
            "metrics": self._extract_metrics_info(),
            "performance": self._extract_performance_info(),
            "alerting": self._extract_alerting_info()
        }
        
        logger.info("Extracted monitoring information for documentation")
        return monitoring_info
    
    def _extract_health_check_info(self) -> Dict[str, Any]:
        """Extract health check information."""
        return {
            "endpoints": {
                "/health": {
                    "description": "Basic health check",
                    "response_time_target": "< 100ms",
                    "checks": ["api_status", "database", "redis"]
                },
                "/health/detailed": {
                    "description": "Detailed health check with component status",
                    "response_time_target": "< 500ms",
                    "checks": ["database", "redis", "storage", "external_apis"]
                },
                "/health/ready": {
                    "description": "Readiness probe for Kubernetes",
                    "response_time_target": "< 50ms",
                    "checks": ["startup_complete", "dependencies_ready"]
                }
            },
            "components": {
                "database": {
                    "type": "postgresql",
                    "timeout": "5s",
                    "critical": True
                },
                "redis": {
                    "type": "redis",
                    "timeout": "2s",
                    "critical": True
                },
                "storage": {
                    "type": "s3",
                    "timeout": "10s",
                    "critical": False
                }
            }
        }
    
    def _extract_metrics_info(self) -> Dict[str, Any]:
        """Extract metrics information."""
        return {
            "endpoints": {
                "/metrics": {
                    "format": "prometheus",
                    "description": "Prometheus-compatible metrics endpoint"
                },
                "/metrics/json": {
                    "format": "json",
                    "description": "JSON-formatted metrics for custom dashboards"
                }
            },
            "categories": {
                "system": {
                    "metrics": ["cpu_usage", "memory_usage", "disk_usage", "network_io"],
                    "description": "System resource metrics"
                },
                "application": {
                    "metrics": ["request_count", "response_time", "error_rate", "active_connections"],
                    "description": "Application performance metrics"
                },
                "business": {
                    "metrics": ["clips_processed", "users_active", "storage_used", "revenue"],
                    "description": "Business and usage metrics"
                }
            },
            "retention": {
                "high_resolution": "24 hours",
                "medium_resolution": "7 days",
                "low_resolution": "90 days"
            }
        }
    
    def _extract_performance_info(self) -> Dict[str, Any]:
        """Extract performance monitoring information."""
        return {
            "sla_targets": {
                "availability": "99.9%",
                "response_time_p95": "500ms",
                "response_time_p99": "1000ms",
                "error_rate": "< 0.1%"
            },
            "monitoring": {
                "request_tracing": True,
                "performance_profiling": True,
                "resource_monitoring": True,
                "dependency_tracking": True
            },
            "alerts": {
                "response_time_threshold": "1000ms",
                "error_rate_threshold": "1%",
                "availability_threshold": "99%",
                "resource_usage_threshold": "80%"
            }
        }
    
    def _extract_alerting_info(self) -> Dict[str, Any]:
        """Extract alerting information."""
        return {
            "channels": {
                "email": {"enabled": True, "severity": ["critical", "warning"]},
                "slack": {"enabled": True, "severity": ["critical"]},
                "pagerduty": {"enabled": True, "severity": ["critical"]}
            },
            "rules": {
                "high_error_rate": {
                    "condition": "error_rate > 1% for 5 minutes",
                    "severity": "critical",
                    "description": "Error rate exceeds acceptable threshold"
                },
                "slow_response_time": {
                    "condition": "p95_response_time > 1000ms for 10 minutes",
                    "severity": "warning",
                    "description": "Response time degradation detected"
                },
                "service_down": {
                    "condition": "health_check_failed for 2 minutes",
                    "severity": "critical",
                    "description": "Service health check failing"
                }
            }
        }


class IntegratedDocumentationEnhancer(APIDocumentationEnhancer):
    """Enhanced documentation with security and monitoring integration."""
    
    def __init__(self, app: FastAPI):
        super().__init__()
        self.app = app
        self.security_integrator = SecurityDocumentationIntegrator(app)
        self.monitoring_integrator = MonitoringDocumentationIntegrator(app)
        
    def enhance_openapi_schema(self, schema: Dict[str, Any], app: FastAPI) -> Dict[str, Any]:
        """Enhance OpenAPI schema with integrated security and monitoring info."""
        # Call parent enhancement
        enhanced_schema = super().enhance_openapi_schema(schema, app)
        
        # Add integrated security information
        security_info = self.security_integrator.extract_security_info()
        self._integrate_security_info(enhanced_schema, security_info)
        
        # Add integrated monitoring information
        monitoring_info = self.monitoring_integrator.extract_monitoring_info()
        self._integrate_monitoring_info(enhanced_schema, monitoring_info)
        
        # Add integration-specific extensions
        self._add_integration_extensions(enhanced_schema)
        
        logger.info("Enhanced OpenAPI schema with integrated security and monitoring")
        return enhanced_schema
    
    def _integrate_security_info(self, schema: Dict[str, Any], security_info: Dict[str, Any]):
        """Integrate security information into schema."""
        # Enhance security schemes with real configuration
        if "components" not in schema:
            schema["components"] = {}
        if "securitySchemes" not in schema["components"]:
            schema["components"]["securitySchemes"] = {}
            
        # Add detailed security schemes
        auth_schemes = security_info["authentication"]["schemes"]
        for scheme_name, scheme_config in auth_schemes.items():
            schema["components"]["securitySchemes"][scheme_name] = scheme_config
        
        # Add security extensions
        schema["x-security"] = {
            "authentication": security_info["authentication"],
            "rate_limiting": security_info["rate_limiting"],
            "security_headers": security_info["security_headers"],
            "csrf_protection": security_info["csrf_protection"]
        }
    
    def _integrate_monitoring_info(self, schema: Dict[str, Any], monitoring_info: Dict[str, Any]):
        """Integrate monitoring information into schema."""
        # Add monitoring extensions
        schema["x-monitoring"] = {
            "health_checks": monitoring_info["health_checks"],
            "metrics": monitoring_info["metrics"],
            "performance": monitoring_info["performance"],
            "alerting": monitoring_info["alerting"]
        }
        
        # Add monitoring endpoints to paths
        if "paths" not in schema:
            schema["paths"] = {}
            
        # Add health check endpoints
        health_endpoints = monitoring_info["health_checks"]["endpoints"]
        for endpoint, config in health_endpoints.items():
            if endpoint not in schema["paths"]:
                schema["paths"][endpoint] = {
                    "get": {
                        "tags": ["monitoring"],
                        "summary": config["description"],
                        "description": f"Health check endpoint. Target response time: {config['response_time_target']}",
                        "responses": {
                            "200": {
                                "description": "Healthy",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/HealthResponse"}
                                    }
                                }
                            },
                            "503": {
                                "description": "Unhealthy",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/HealthResponse"}
                                    }
                                }
                            }
                        }
                    }
                }
    
    def _add_integration_extensions(self, schema: Dict[str, Any]):
        """Add integration-specific extensions."""
        schema["x-integration"] = {
            "version": "1.0.0",
            "features": {
                "security_integration": True,
                "monitoring_integration": True,
                "real_time_metrics": True,
                "automated_documentation": True
            },
            "last_updated": datetime.utcnow().isoformat(),
            "documentation_level": "production"
        }


def setup_integrated_documentation(
    app: FastAPI,
    config: Optional[APIDocumentationConfig] = None
) -> IntegratedDocumentationEnhancer:
    """Setup integrated documentation with security and monitoring."""
    if config is None:
        config = APIDocumentationConfig(
            title=app.title,
            description=app.description,
            version=app.version,
            level=DocumentationLevel.PRODUCTION,
            include_examples=True,
            include_error_responses=True,
            include_security_schemes=True,
            include_rate_limiting=True,
            include_monitoring_endpoints=True
        )
    
    # Create integrated enhancer
    enhancer = IntegratedDocumentationEnhancer(app)
    
    # Setup custom OpenAPI schema
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
            
        # Get base schema
        from fastapi.openapi.utils import get_openapi
        openapi_schema = get_openapi(
            title=config.title,
            version=config.version,
            description=config.description,
            routes=app.routes,
        )
        
        # Enhance with integrated features
        enhanced_schema = enhancer.enhance_openapi_schema(openapi_schema, app)
        
        app.openapi_schema = enhanced_schema
        return app.openapi_schema
    
    app.openapi = custom_openapi
    
    logger.info("Setup integrated API documentation with security and monitoring")
    return enhancer


# Utility functions for endpoint documentation
def document_security_requirements(*schemes: str):
    """Decorator to document security requirements for endpoints."""
    def decorator(func):
        if not hasattr(func, "__security_schemes__"):
            func.__security_schemes__ = []
        func.__security_schemes__.extend(schemes)
        return func
    return decorator


def document_rate_limits(**limits):
    """Decorator to document rate limits for endpoints."""
    def decorator(func):
        if not hasattr(func, "__rate_limits__"):
            func.__rate_limits__ = {}
        func.__rate_limits__.update(limits)
        return func
    return decorator


def document_monitoring(health_check: bool = False, metrics: bool = False):
    """Decorator to document monitoring features for endpoints."""
    def decorator(func):
        if not hasattr(func, "__monitoring__"):
            func.__monitoring__ = {}
        func.__monitoring__.update({
            "health_check": health_check,
            "metrics": metrics
        })
        return func
    return decorator