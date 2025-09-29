"""Versioning middleware for API version management."""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import re

class VersioningMiddleware(BaseHTTPMiddleware):
    """Middleware to handle API versioning."""
    
    def __init__(self, app, default_version: str = "v1"):
        super().__init__(app)
        self.default_version = default_version
        self.version_pattern = re.compile(r'/v(\d+)/')
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add version information."""
        
        # Extract version from URL path
        version_match = self.version_pattern.search(request.url.path)
        if version_match:
            version = f"v{version_match.group(1)}"
        else:
            version = self.default_version
        
        # Add version to request state
        request.state.api_version = version
        
        # Add version header to response
        response = await call_next(request)
        response.headers["X-API-Version"] = version
        
        return response

class DeprecationMiddleware(BaseHTTPMiddleware):
    """Middleware to handle API deprecation warnings."""
    
    def __init__(self, app, deprecated_versions: list = None):
        super().__init__(app)
        self.deprecated_versions = deprecated_versions or []
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add deprecation warnings for deprecated API versions."""
        
        # Get version from request state (set by APIVersioningMiddleware)
        version = getattr(request.state, 'api_version', 'v1')
        
        response = await call_next(request)
        
        # Add deprecation warning if version is deprecated
        if version in self.deprecated_versions:
            response.headers["Warning"] = f"299 - \"API version {version} is deprecated\""
            response.headers["Sunset"] = "2024-12-31"  # Example sunset date