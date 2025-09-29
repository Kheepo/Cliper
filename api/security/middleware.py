"""Security middleware for FastAPI application."""

import time
import logging
from typing import Callable, Optional
from datetime import datetime

from fastapi import FastAPI, Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
import redis

from .security_config import (
    SecurityConfig,
    InputValidator,
    RateLimiter,
    SecurityHeaders,
    IPFilter,
    TokenManager
)

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Comprehensive security middleware."""
    
    def __init__(self, app: FastAPI, redis_client: Optional[redis.Redis] = None):
        super().__init__(app)
        self.redis_client = redis_client
        self.rate_limiter = RateLimiter(redis_client) if redis_client else None
        
        # Endpoints that require authentication
        self.protected_endpoints = {
            '/api/v1/upload',
            '/api/v1/process',
            '/api/v1/user',
            '/api/v1/admin'
        }
        
        # Endpoints exempt from security checks (health, metrics, docs, auth)
        self.exempt_endpoints = {
            '/health',
            '/metrics',
            '/docs',
            '/redoc',
            '/openapi.json',
            '/api/info',
            '/api/status',
            '/api/auth/me',
            '/api/auth/status'
        }
        
        # Endpoints with custom rate limits
        self.rate_limit_overrides = {
            '/api/v1/upload': {'limit': 10, 'window': 3600},  # 10 uploads per hour
            '/api/v1/auth/login': {'limit': 5, 'window': 900},  # 5 login attempts per 15 min
            '/api/v1/auth/register': {'limit': 3, 'window': 3600},  # 3 registrations per hour
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through security checks."""
        start_time = time.time()
        
        try:
            # Check if endpoint is exempt from security checks
            if self._is_exempt_endpoint(request.url.path):
                # Skip all security checks for exempt endpoints
                response = await call_next(request)
                return SecurityHeaders.add_security_headers(response)
            
            # 1. IP filtering
            client_ip = self._get_client_ip(request)
            if not IPFilter.is_allowed_ip(client_ip):
                logger.warning(f"Blocked request from IP: {client_ip}")
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Access denied from this IP address"}
                )
            
            # 2. HTTPS enforcement
            if SecurityConfig.FORCE_HTTPS and request.url.scheme != 'https':
                logger.warning(f"HTTP request blocked: {request.url}")
                return JSONResponse(
                    status_code=status.HTTP_426_UPGRADE_REQUIRED,
                    content={"detail": "HTTPS required"}
                )
            
            # 3. Rate limiting
            if self.rate_limiter:
                rate_limit_result = await self._check_rate_limit(request, client_ip)
                if not rate_limit_result['allowed']:
                    logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                    response = JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={
                            "detail": "Rate limit exceeded",
                            "retry_after": rate_limit_result['retry_after']
                        }
                    )
                    response.headers['Retry-After'] = str(rate_limit_result['retry_after'])
                    response.headers['X-RateLimit-Limit'] = str(rate_limit_result['limit'])
                    response.headers['X-RateLimit-Remaining'] = str(rate_limit_result['remaining'])
                    response.headers['X-RateLimit-Reset'] = str(rate_limit_result['reset_time'])
                    return response
            
            # 4. Authentication check
            if self._requires_authentication(request.url.path):
                auth_result = await self._check_authentication(request)
                if not auth_result['valid']:
                    logger.warning(f"Authentication failed for {request.url.path}")
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail": auth_result.get('error', 'Authentication required')}
                    )
                # Add user info to request state
                request.state.user = auth_result.get('user')
            
            # 5. Input validation for POST/PUT requests
            if request.method in ['POST', 'PUT', 'PATCH']:
                await self._validate_request_body(request)
            
            # 6. Process request
            response = await call_next(request)
            
            # 7. Add security headers
            response = SecurityHeaders.add_security_headers(response)
            
            # 8. Log request
            processing_time = time.time() - start_time
            logger.info(
                f"{request.method} {request.url.path} - "
                f"Status: {response.status_code} - "
                f"Time: {processing_time:.3f}s - "
                f"IP: {client_ip}"
            )
            
            return response
            
        except HTTPException as e:
            logger.error(f"HTTP Exception: {e.detail} - IP: {client_ip}")
            response = JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail}
            )
            return SecurityHeaders.add_security_headers(response)
            
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)} - IP: {client_ip}")
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"}
            )
            return SecurityHeaders.add_security_headers(response)
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        # Check for forwarded headers (when behind proxy/load balancer)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return request.client.host
    
    async def _check_rate_limit(self, request: Request, client_ip: str) -> dict:
        """Check rate limiting for request."""
        # Create rate limit key
        endpoint = request.url.path
        rate_key = f"rate_limit:{client_ip}:{endpoint}"
        
        # Check for custom rate limits
        if endpoint in self.rate_limit_overrides:
            limit_config = self.rate_limit_overrides[endpoint]
            return self.rate_limiter.is_allowed(
                rate_key,
                limit=limit_config['limit'],
                window=limit_config['window']
            )
        
        # Use default rate limits
        return self.rate_limiter.is_allowed(rate_key)
    
    def _is_exempt_endpoint(self, path: str) -> bool:
        """Check if endpoint is exempt from security checks."""
        return path in self.exempt_endpoints or any(path.startswith(exempt) for exempt in self.exempt_endpoints)
    
    def _requires_authentication(self, path: str) -> bool:
        """Check if endpoint requires authentication."""
        for protected_path in self.protected_endpoints:
            if path.startswith(protected_path):
                return True
        return False
    
    async def _check_authentication(self, request: Request) -> dict:
        """Check request authentication."""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return {'valid': False, 'error': 'Missing or invalid authorization header'}
        
        token = auth_header.split(' ')[1]
        token_result = TokenManager.verify_token(token)
        
        if not token_result['valid']:
            return token_result
        
        # Add user information from token payload
        payload = token_result['payload']
        return {
            'valid': True,
            'user': {
                'id': payload.get('user_id'),
                'email': payload.get('email'),
                'role': payload.get('role', 'user')
            }
        }
    
    async def _validate_request_body(self, request: Request) -> None:
        """Validate request body for security threats."""
        try:
            # Get request body
            body = await request.body()
            if not body:
                return
            
            body_str = body.decode('utf-8')
            
            # Check for SQL injection
            if InputValidator.check_sql_injection(body_str):
                logger.warning(f"SQL injection attempt detected from {self._get_client_ip(request)}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid input detected"
                )
            
            # Check for XSS
            if InputValidator.check_xss(body_str):
                logger.warning(f"XSS attempt detected from {self._get_client_ip(request)}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid input detected"
                )
            
        except UnicodeDecodeError:
            # Binary data (like file uploads) - skip text validation
            pass
        except Exception as e:
            logger.error(f"Error validating request body: {str(e)}")
            # Don't block request for validation errors
            pass


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF protection middleware."""
    
    def __init__(self, app: FastAPI, secret_key: str):
        super().__init__(app)
        self.secret_key = secret_key
        self.safe_methods = {'GET', 'HEAD', 'OPTIONS', 'TRACE'}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check CSRF token for unsafe methods."""
        if request.method not in self.safe_methods:
            csrf_token = request.headers.get('X-CSRF-Token')
            if not csrf_token or not self._verify_csrf_token(csrf_token):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "CSRF token missing or invalid"}
                )
        
        response = await call_next(request)
        
        # Add CSRF token to response for safe methods
        if request.method in self.safe_methods:
            csrf_token = self._generate_csrf_token()
            response.headers['X-CSRF-Token'] = csrf_token
        
        return response
    
    def _generate_csrf_token(self) -> str:
        """Generate CSRF token."""
        import hmac
        import hashlib
        import time
        
        timestamp = str(int(time.time()))
        message = f"{timestamp}:{self.secret_key}"
        signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"{timestamp}:{signature}"
    
    def _verify_csrf_token(self, token: str) -> bool:
        """Verify CSRF token."""
        try:
            import hmac
            import hashlib
            import time
            
            timestamp_str, signature = token.split(':', 1)
            timestamp = int(timestamp_str)
            
            # Check if token is not too old (1 hour)
            if time.time() - timestamp > 3600:
                return False
            
            message = f"{timestamp_str}:{self.secret_key}"
            expected_signature = hmac.new(
                self.secret_key.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except (ValueError, IndexError):
            return False


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Enhanced request logging middleware."""
    
    def __init__(self, app: FastAPI):
        super().__init__(app)
        self.sensitive_headers = {
            'authorization', 'cookie', 'x-api-key', 'x-auth-token'
        }
        self.sensitive_params = {
            'password', 'token', 'secret', 'key', 'auth'
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response details."""
        start_time = time.time()
        request_id = request.headers.get('X-Request-ID', 'unknown')
        
        # Log request
        self._log_request(request, request_id)
        
        try:
            response = await call_next(request)
            processing_time = time.time() - start_time
            
            # Log response
            self._log_response(request, response, processing_time, request_id)
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                f"Request failed - ID: {request_id} - "
                f"Error: {str(e)} - Time: {processing_time:.3f}s"
            )
            raise
    
    def _log_request(self, request: Request, request_id: str) -> None:
        """Log incoming request details."""
        # Filter sensitive headers
        headers = {
            k: v if k.lower() not in self.sensitive_headers else '[REDACTED]'
            for k, v in request.headers.items()
        }
        
        # Filter sensitive query parameters
        query_params = {
            k: v if not any(sensitive in k.lower() for sensitive in self.sensitive_params) else '[REDACTED]'
            for k, v in request.query_params.items()
        }
        
        logger.info(
            f"Request - ID: {request_id} - "
            f"Method: {request.method} - "
            f"URL: {request.url.path} - "
            f"IP: {request.client.host} - "
            f"User-Agent: {request.headers.get('user-agent', 'unknown')} - "
            f"Query: {query_params}"
        )
    
    def _log_response(self, request: Request, response: Response, 
                     processing_time: float, request_id: str) -> None:
        """Log response details."""
        logger.info(
            f"Response - ID: {request_id} - "
            f"Status: {response.status_code} - "
            f"Time: {processing_time:.3f}s - "
            f"Size: {response.headers.get('content-length', 'unknown')} bytes"
        )
        
        # Log slow requests
        if processing_time > 5.0:  # 5 seconds
            logger.warning(
                f"Slow request - ID: {request_id} - "
                f"URL: {request.url.path} - "
                f"Time: {processing_time:.3f}s"
            )


def setup_security_middleware(app: FastAPI, redis_client: Optional[redis.Redis] = None) -> None:
    """Setup all security middleware for the application."""
    
    # Add security middleware
    app.add_middleware(SecurityMiddleware, redis_client=redis_client)
    
    # Add CSRF protection
    if SecurityConfig.JWT_SECRET_KEY:
        app.add_middleware(CSRFMiddleware, secret_key=SecurityConfig.JWT_SECRET_KEY)
    
    # Add request logging
    app.add_middleware(RequestLoggingMiddleware)
    
    logger.info("Security middleware configured successfully")