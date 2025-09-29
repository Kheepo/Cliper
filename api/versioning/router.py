"""API versioning router for handling different API versions."""

from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from .models import (
    APIVersion, VersionInfo, VersionStatus, VersionedResponse,
    ErrorResponse, PaginationMeta, PaginatedResponse
)

class APIVersionRouter:
    """Router for handling API versioning."""
    
    def __init__(self):
        self.versions: Dict[APIVersion, VersionInfo] = {}
        self.routers: Dict[APIVersion, APIRouter] = {}
        self.default_version = APIVersion.V1
        self.latest_version = APIVersion.V1
        
        # Initialize default versions
        self._initialize_versions()
    
    def _initialize_versions(self):
        """Initialize default API versions."""
        # Version 1 - Stable
        self.versions[APIVersion.V1] = VersionInfo(
            version=APIVersion.V1,
            status=VersionStatus.STABLE,
            release_date=datetime(2024, 1, 1),
            description="Initial stable release with core video processing features",
            new_features=[
                "Video upload and processing",
                "URL-based video processing",
                "Real-time WebSocket updates",
                "Basic authentication",
                "Health monitoring"
            ],
            documentation_url="/docs/v1"
        )
        
        # Version 2 - Beta (future)
        self.versions[APIVersion.V2] = VersionInfo(
            version=APIVersion.V2,
            status=VersionStatus.BETA,
            release_date=datetime(2024, 6, 1),
            description="Enhanced version with improved performance and new features",
            new_features=[
                "Batch video processing",
                "Advanced analytics",
                "Enhanced security",
                "Improved error handling",
                "Rate limiting"
            ],
            breaking_changes=[
                "Authentication token format changed",
                "Response structure updated",
                "Some endpoint paths modified"
            ],
            documentation_url="/docs/v2",
            migration_guide_url="/docs/migration/v1-to-v2"
        )
        
        # Create routers for each version
        for version in self.versions.keys():
            self.routers[version] = APIRouter(
                prefix=f"/{version.value}",
                tags=[f"API {version.value.upper()}"]
            )
    
    def get_version_from_request(self, request: Request) -> APIVersion:
        """Extract API version from request."""
        # Check URL path first
        path_parts = request.url.path.strip('/').split('/')
        if path_parts and path_parts[0] in [v.value for v in APIVersion]:
            return APIVersion(path_parts[0])
        
        # Check Accept header
        accept_header = request.headers.get('Accept', '')
        if 'application/vnd.cliper.v1+json' in accept_header:
            return APIVersion.V1
        elif 'application/vnd.cliper.v2+json' in accept_header:
            return APIVersion.V2
        
        # Check custom header
        version_header = request.headers.get('X-API-Version')
        if version_header:
            try:
                return APIVersion(version_header.lower())
            except ValueError:
                pass
        
        # Check query parameter
        version_param = request.query_params.get('version')
        if version_param:
            try:
                return APIVersion(version_param.lower())
            except ValueError:
                pass
        
        # Return default version
        return self.default_version
    
    def get_router(self, version: APIVersion) -> APIRouter:
        """Get router for specific API version."""
        if version == APIVersion.LATEST:
            version = self.latest_version
        
        if version not in self.routers:
            raise HTTPException(
                status_code=400,
                detail=f"API version {version.value} is not supported"
            )
        
        return self.routers[version]
    
    def get_version_info(self, version: APIVersion) -> VersionInfo:
        """Get version information."""
        if version == APIVersion.LATEST:
            version = self.latest_version
        
        if version not in self.versions:
            raise HTTPException(
                status_code=404,
                detail=f"Version {version.value} not found"
            )
        
        return self.versions[version]
    
    def list_versions(self) -> List[VersionInfo]:
        """List all available API versions."""
        return list(self.versions.values())
    
    def is_version_deprecated(self, version: APIVersion) -> bool:
        """Check if version is deprecated."""
        version_info = self.get_version_info(version)
        return version_info.status in [VersionStatus.DEPRECATED, VersionStatus.SUNSET]
    
    def create_versioned_response(
        self,
        data: Any,
        version: APIVersion,
        request_id: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
        links: Optional[Dict[str, str]] = None
    ) -> VersionedResponse:
        """Create a versioned response."""
        return VersionedResponse(
            api_version=version,
            request_id=request_id,
            data=data,
            meta=meta,
            links=links
        )
    
    def create_paginated_response(
        self,
        data: List[Any],
        version: APIVersion,
        page: int,
        per_page: int,
        total: int,
        request_id: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
        links: Optional[Dict[str, str]] = None
    ) -> PaginatedResponse:
        """Create a paginated response."""
        pages = (total + per_page - 1) // per_page
        
        pagination = PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1
        )
        
        return PaginatedResponse(
            api_version=version,
            request_id=request_id,
            data=data,
            pagination=pagination,
            meta=meta,
            links=links
        )
    
    def create_error_response(
        self,
        error: Dict[str, Any],
        version: APIVersion,
        request_id: Optional[str] = None
    ) -> ErrorResponse:
        """Create an error response."""
        return ErrorResponse(
            api_version=version,
            request_id=request_id,
            error=error
        )

# Global version router instance
version_router = APIVersionRouter()

# Dependency for getting current API version
def get_api_version(request: Request) -> APIVersion:
    """Dependency to get current API version from request."""
    return version_router.get_version_from_request(request)

# Dependency for getting request ID
def get_request_id(request: Request) -> Optional[str]:
    """Dependency to get request ID."""
    return getattr(request.state, 'request_id', None)

# Version validation decorator
def require_version(min_version: APIVersion, max_version: Optional[APIVersion] = None):
    """Decorator to require specific API version range."""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            # This would be implemented in the actual endpoint
            # The middleware would handle version validation
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Deprecation warning decorator
def deprecated_endpoint(version: APIVersion, sunset_date: Optional[datetime] = None):
    """Decorator to mark endpoint as deprecated."""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            # Add deprecation headers in middleware
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Version compatibility utilities
class VersionCompatibility:
    """Utilities for handling version compatibility."""
    
    @staticmethod
    def transform_response_v1_to_v2(v1_response: Dict[str, Any]) -> Dict[str, Any]:
        """Transform v1 response format to v2."""
        # Example transformation logic
        if 'status' in v1_response:
            v1_response['state'] = v1_response.pop('status')
        
        if 'created_at' in v1_response:
            v1_response['timestamp'] = v1_response['created_at']
        
        return v1_response
    
    @staticmethod
    def transform_request_v2_to_v1(v2_request: Dict[str, Any]) -> Dict[str, Any]:
        """Transform v2 request format to v1."""
        # Example transformation logic
        if 'state' in v2_request:
            v2_request['status'] = v2_request.pop('state')
        
        return v2_request
    
    @staticmethod
    def is_compatible(from_version: APIVersion, to_version: APIVersion) -> bool:
        """Check if versions are compatible."""
        # Define compatibility matrix
        compatibility_matrix = {
            APIVersion.V1: [APIVersion.V1],
            APIVersion.V2: [APIVersion.V1, APIVersion.V2]
        }
        
        return to_version in compatibility_matrix.get(from_version, [])

# Response format utilities
class ResponseFormatter:
    """Utilities for formatting responses based on API version."""
    
    @staticmethod
    def format_for_version(data: Any, version: APIVersion) -> Dict[str, Any]:
        """Format response data for specific API version."""
        if version == APIVersion.V1:
            return ResponseFormatter._format_v1(data)
        elif version == APIVersion.V2:
            return ResponseFormatter._format_v2(data)
        else:
            return data
    
    @staticmethod
    def _format_v1(data: Any) -> Dict[str, Any]:
        """Format response for API v1."""
        if isinstance(data, dict):
            # V1 uses snake_case and simpler structure
            formatted = {}
            for key, value in data.items():
                # Convert camelCase to snake_case
                snake_key = ''.join(['_' + c.lower() if c.isupper() else c for c in key]).lstrip('_')
                formatted[snake_key] = value
            return formatted
        return data
    
    @staticmethod
    def _format_v2(data: Any) -> Dict[str, Any]:
        """Format response for API v2."""
        if isinstance(data, dict):
            # V2 uses camelCase and enhanced structure
            formatted = {}
            for key, value in data.items():
                # Convert snake_case to camelCase
                components = key.split('_')
                camel_key = components[0] + ''.join(word.capitalize() for word in components[1:])
                formatted[camel_key] = value
            return formatted
        return data