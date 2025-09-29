from typing import Any, Dict, List, Optional, Union
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import json
import logging
import time
from datetime import datetime

from ..validation.enhanced_validators import (
    EnhancedInputValidator,
    SecurityValidationError
)

logger = logging.getLogger(__name__)

class ValidationConfig:
    """Configuration for validation middleware"""
    
    def __init__(
        self,
        max_request_size: int = 10 * 1024 * 1024,  # 10MB
        max_json_depth: int = 10,
        max_json_keys: int = 100,
        validate_query_params: bool = True,
        validate_path_params: bool = True,
        validate_headers: bool = True,
        validate_body: bool = True,
        blocked_user_agents: List[str] = None,
        allowed_content_types: List[str] = None,
        exempt_paths: List[str] = None
    ):
        self.max_request_size = max_request_size
        self.max_json_depth = max_json_depth
        self.max_json_keys = max_json_keys
        self.validate_query_params = validate_query_params
        self.validate_path_params = validate_path_params
        self.validate_headers = validate_headers
        self.validate_body = validate_body
        self.blocked_user_agents = blocked_user_agents or [
            'sqlmap', 'nikto', 'nmap', 'masscan', 'zap', 'burp'
        ]
        self.allowed_content_types = allowed_content_types or [
            'application/json',
            'application/x-www-form-urlencoded',
            'multipart/form-data',
            'text/plain',
            'application/octet-stream'
        ]
        self.exempt_paths = exempt_paths or [
            '/health',
            '/metrics',
            '/docs',
            '/openapi.json',
            '/redoc'
        ]

class ValidationMiddleware(BaseHTTPMiddleware):
    """Comprehensive input validation middleware"""
    
    def __init__(self, app: ASGIApp, config: ValidationConfig = None):
        super().__init__(app)
        self.config = config or ValidationConfig()
        self.validator = EnhancedInputValidator()
        
    async def dispatch(self, request: Request, call_next):
        """Main middleware dispatch method"""
        start_time = time.time()
        
        try:
            # Skip validation for exempt paths
            path = request.url.path
            is_exempt = self._is_exempt_path(path)
            logger.info(f"Validation middleware: path={path}, exempt_paths={self.config.exempt_paths}, is_exempt={is_exempt}")
            
            if is_exempt:
                logger.info(f"Skipping validation for exempt path: {path}")
                return await call_next(request)
            
            # Validate request
            await self._validate_request(request)
            
            # Process request
            response = await call_next(request)
            
            # Log successful validation
            processing_time = time.time() - start_time
            logger.info(
                f"Request validated successfully",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "client_ip": self._get_client_ip(request),
                    "processing_time": processing_time,
                    "status_code": response.status_code
                }
            )
            
            return response
            
        except SecurityValidationError as e:
            logger.warning(
                f"Security validation failed: {str(e)}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "client_ip": self._get_client_ip(request),
                    "user_agent": request.headers.get("user-agent", "unknown"),
                    "error": str(e)
                }
            )
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid input", "message": "Request contains invalid or potentially malicious content"}
            )
            
        except HTTPException as e:
            logger.warning(
                f"HTTP validation error: {e.detail}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "client_ip": self._get_client_ip(request),
                    "status_code": e.status_code,
                    "error": e.detail
                }
            )
            return JSONResponse(
                status_code=e.status_code,
                content={"error": "Validation failed", "message": e.detail}
            )
            
        except Exception as e:
            logger.error(
                f"Unexpected validation error: {str(e)}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "client_ip": self._get_client_ip(request),
                    "error": str(e)
                },
                exc_info=True
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error", "message": "Request validation failed"}
            )
    
    def _is_exempt_path(self, path: str) -> bool:
        """Check if path is exempt from validation"""
        return any(path.startswith(exempt) for exempt in self.config.exempt_paths)
    
    async def _validate_request(self, request: Request):
        """Comprehensive request validation"""
        # Validate request size
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.config.max_request_size:
            raise HTTPException(
                status_code=413,
                detail=f"Request too large. Maximum size: {self.config.max_request_size} bytes"
            )
        
        # Validate user agent
        await self._validate_user_agent(request)
        
        # Validate content type
        await self._validate_content_type(request)
        
        # Validate headers
        if self.config.validate_headers:
            await self._validate_headers(request)
        
        # Validate query parameters
        if self.config.validate_query_params:
            await self._validate_query_params(request)
        
        # Validate path parameters
        if self.config.validate_path_params:
            await self._validate_path_params(request)
        
        # Validate request body
        if self.config.validate_body and request.method in ["POST", "PUT", "PATCH"]:
            await self._validate_body(request)
    
    async def _validate_user_agent(self, request: Request):
        """Validate user agent for known malicious patterns"""
        user_agent = request.headers.get("user-agent", "").lower()
        
        for blocked_agent in self.config.blocked_user_agents:
            if blocked_agent.lower() in user_agent:
                raise SecurityValidationError(f"Blocked user agent detected: {blocked_agent}")
        
        # Check for suspicious patterns
        suspicious_patterns = [
            r'<script',
            r'javascript:',
            r'vbscript:',
            r'data:text/html',
            r'\x00',
            r'%00'
        ]
        
        for pattern in suspicious_patterns:
            if pattern in user_agent:
                raise SecurityValidationError("Suspicious user agent pattern detected")
    
    async def _validate_content_type(self, request: Request):
        """Validate content type"""
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            
            if content_type:
                # Extract base content type (remove charset, boundary, etc.)
                base_content_type = content_type.split(';')[0].strip().lower()
                
                if base_content_type not in self.config.allowed_content_types:
                    raise HTTPException(
                        status_code=415,
                        detail=f"Unsupported content type: {base_content_type}"
                    )
    
    async def _validate_headers(self, request: Request):
        """Validate request headers"""
        dangerous_headers = [
            'x-forwarded-host',
            'x-original-url',
            'x-rewrite-url'
        ]
        
        # Headers that should be excluded from SQL injection checks
        # as they commonly contain characters that trigger false positives
        excluded_headers = [
            'accept',
            'accept-encoding',
            'accept-language',
            'content-type',
            'user-agent',
            'cache-control',
            'if-none-match',
            'if-modified-since'
        ]
        
        for header_name, header_value in request.headers.items():
            # Check for dangerous headers
            if header_name.lower() in dangerous_headers:
                logger.warning(f"Potentially dangerous header detected: {header_name}")
            
            # Validate header values
            if isinstance(header_value, str):
                # Check for injection attempts (but skip common headers that have false positives)
                if self.validator.check_xss(header_value):
                    raise SecurityValidationError(f"XSS attempt detected in header: {header_name}")
                
                # Only check SQL injection for headers that aren't in the excluded list
                if header_name.lower() not in excluded_headers and self.validator.check_sql_injection(header_value):
                    raise SecurityValidationError(f"SQL injection attempt detected in header: {header_name}")
                
                # Check for null bytes and control characters
                if '\x00' in header_value or any(ord(c) < 32 and c not in '\t\n\r' for c in header_value):
                    raise SecurityValidationError(f"Invalid characters in header: {header_name}")
    
    async def _validate_query_params(self, request: Request):
        """Validate query parameters"""
        for param_name, param_value in request.query_params.items():
            # Validate parameter name
            if self.validator.check_xss(param_name) or self.validator.check_sql_injection(param_name):
                raise SecurityValidationError(f"Invalid query parameter name: {param_name}")
            
            # Validate parameter value
            if isinstance(param_value, str):
                if self.validator.check_xss(param_value):
                    raise SecurityValidationError(f"XSS attempt in query parameter: {param_name}")
                
                if self.validator.check_sql_injection(param_value):
                    raise SecurityValidationError(f"SQL injection attempt in query parameter: {param_name}")
                
                if self.validator.check_path_traversal(param_value):
                    raise SecurityValidationError(f"Path traversal attempt in query parameter: {param_name}")
                
                # Check parameter length
                if len(param_value) > 1000:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Query parameter too long: {param_name}"
                    )
    
    async def _validate_path_params(self, request: Request):
        """Validate path parameters"""
        path = request.url.path
        
        # Check for path traversal
        if self.validator.check_path_traversal(path):
            raise SecurityValidationError("Path traversal attempt detected")
        
        # Check for encoded attacks
        decoded_path = path
        try:
            import urllib.parse
            decoded_path = urllib.parse.unquote(path)
        except Exception:
            pass
        
        if self.validator.check_xss(decoded_path) or self.validator.check_sql_injection(decoded_path):
            raise SecurityValidationError("Malicious content detected in path")
        
        # Check path length
        if len(path) > 2048:
            raise HTTPException(
                status_code=414,
                detail="Request URI too long"
            )
    
    async def _validate_body(self, request: Request):
        """Validate request body"""
        content_type = request.headers.get("content-type", "")
        
        if "application/json" in content_type:
            await self._validate_json_body(request)
        elif "application/x-www-form-urlencoded" in content_type:
            await self._validate_form_body(request)
        elif "multipart/form-data" in content_type:
            await self._validate_multipart_body(request)
    
    async def _validate_json_body(self, request: Request):
        """Validate JSON request body"""
        try:
            # Read body
            body = await request.body()
            
            if not body:
                return
            
            # Check body size
            if len(body) > self.config.max_request_size:
                raise HTTPException(
                    status_code=413,
                    detail="Request body too large"
                )
            
            # Parse JSON
            try:
                data = json.loads(body)
            except json.JSONDecodeError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid JSON: {str(e)}"
                )
            
            # Validate JSON structure
            if not self.validator.validate_json_structure(
                data, 
                max_depth=self.config.max_json_depth,
                max_keys=self.config.max_json_keys
            ):
                raise HTTPException(
                    status_code=400,
                    detail="JSON structure too complex"
                )
            
            # Validate JSON content
            await self._validate_json_content(data)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error validating JSON body: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Invalid request body"
            )
    
    async def _validate_json_content(self, data: Any, path: str = "root"):
        """Recursively validate JSON content"""
        if isinstance(data, dict):
            for key, value in data.items():
                # Validate key
                if isinstance(key, str):
                    if self.validator.check_xss(key) or self.validator.check_sql_injection(key):
                        raise SecurityValidationError(f"Malicious content in JSON key at {path}.{key}")
                
                # Recursively validate value
                await self._validate_json_content(value, f"{path}.{key}")
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                await self._validate_json_content(item, f"{path}[{i}]")
        
        elif isinstance(data, str):
            # Validate string content
            if self.validator.check_xss(data):
                raise SecurityValidationError(f"XSS attempt detected in JSON at {path}")
            
            if self.validator.check_sql_injection(data):
                raise SecurityValidationError(f"SQL injection attempt detected in JSON at {path}")
            
            if self.validator.check_path_traversal(data):
                raise SecurityValidationError(f"Path traversal attempt detected in JSON at {path}")
            
            # Check string length
            if len(data) > 10000:
                raise HTTPException(
                    status_code=400,
                    detail=f"String too long in JSON at {path}"
                )
    
    async def _validate_form_body(self, request: Request):
        """Validate form-encoded request body"""
        try:
            form_data = await request.form()
            
            for field_name, field_value in form_data.items():
                # Validate field name
                if self.validator.check_xss(field_name) or self.validator.check_sql_injection(field_name):
                    raise SecurityValidationError(f"Malicious content in form field name: {field_name}")
                
                # Validate field value
                if isinstance(field_value, str):
                    if self.validator.check_xss(field_value):
                        raise SecurityValidationError(f"XSS attempt in form field: {field_name}")
                    
                    if self.validator.check_sql_injection(field_value):
                        raise SecurityValidationError(f"SQL injection attempt in form field: {field_name}")
                    
                    if self.validator.check_path_traversal(field_value):
                        raise SecurityValidationError(f"Path traversal attempt in form field: {field_name}")
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error validating form body: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Invalid form data"
            )
    
    async def _validate_multipart_body(self, request: Request):
        """Validate multipart form data"""
        try:
            form_data = await request.form()
            
            for field_name, field_value in form_data.items():
                # Validate field name
                if self.validator.check_xss(field_name) or self.validator.check_sql_injection(field_name):
                    raise SecurityValidationError(f"Malicious content in multipart field name: {field_name}")
                
                # Handle file uploads
                if hasattr(field_value, 'filename'):
                    await self._validate_file_upload(field_value)
                elif isinstance(field_value, str):
                    # Validate text field
                    if self.validator.check_xss(field_value):
                        raise SecurityValidationError(f"XSS attempt in multipart field: {field_name}")
                    
                    if self.validator.check_sql_injection(field_value):
                        raise SecurityValidationError(f"SQL injection attempt in multipart field: {field_name}")
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error validating multipart body: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Invalid multipart data"
            )
    
    async def _validate_file_upload(self, file_field):
        """Validate file upload"""
        if hasattr(file_field, 'filename') and file_field.filename:
            # Validate filename
            if not self.validator.validate_filename(file_field.filename):
                raise SecurityValidationError(f"Invalid or unsafe filename: {file_field.filename}")
            
            # Validate content type
            content_type = getattr(file_field, 'content_type', '')
            if content_type:
                allowed_file_types = [
                    'video/mp4', 'video/avi', 'video/mov', 'video/wmv',
                    'audio/mp3', 'audio/wav', 'audio/aac',
                    'image/jpeg', 'image/png', 'image/gif',
                    'application/pdf', 'text/plain'
                ]
                
                if content_type not in allowed_file_types:
                    raise HTTPException(
                        status_code=415,
                        detail=f"File type not allowed: {content_type}"
                    )
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        # Check for forwarded headers
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to client host
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"

# Factory function for easy integration
def create_validation_middleware(
    max_request_size: int = 10 * 1024 * 1024,
    max_json_depth: int = 10,
    max_json_keys: int = 100,
    exempt_paths: List[str] = None
) -> ValidationMiddleware:
    """Create validation middleware with custom configuration"""
    config = ValidationConfig(
        max_request_size=max_request_size,
        max_json_depth=max_json_depth,
        max_json_keys=max_json_keys,
        exempt_paths=exempt_paths
    )
    
    return lambda app: ValidationMiddleware(app, config)