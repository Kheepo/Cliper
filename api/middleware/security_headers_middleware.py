"""Security Headers and CORS Middleware.

Provides comprehensive security headers and CORS configuration:
- CORS with configurable origins and methods
- Security headers (HSTS, CSP, X-Frame-Options, etc.)
- Content Security Policy with nonce support
- Rate limiting headers
- Security event logging
"""

import logging
import secrets
import time
from typing import List, Dict, Optional, Set
from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response as StarletteResponse

from api.core.config import settings
from api.utils.structured_logging import StructuredLogger

logger = logging.getLogger(__name__)
structured_logger = StructuredLogger("security_headers_middleware")

class SecurityConfig:
    """Security configuration settings."""
    
    # CORS settings
    ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://yourdomain.com",
        "https://www.yourdomain.com"
    ]
    
    ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    ALLOWED_HEADERS = [
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "X-CSRF-Token",
        "X-Request-ID"
    ]
    
    # Security headers
    HSTS_MAX_AGE = 31536000  # 1 year
    HSTS_INCLUDE_SUBDOMAINS = True
    HSTS_PRELOAD = True
    
    # Content Security Policy
    CSP_DIRECTIVES = {
        "default-src": ["'self'"],
        "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'", "https://cdn.jsdelivr.net"],
        "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
        "font-src": ["'self'", "https://fonts.gstatic.com"],
        "img-src": ["'self'", "data:", "https:"],
        "connect-src": ["'self'", "https://api.stripe.com", "wss:"],
        "frame-ancestors": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"]
    }
    
    # Feature Policy / Permissions Policy
    PERMISSIONS_POLICY = {
        "camera": [],
        "microphone": [],
        "geolocation": [],
        "payment": ["self"],
        "usb": [],
        "magnetometer": [],
        "gyroscope": [],
        "accelerometer": []
    }
    
    # Security headers configuration
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-Download-Options": "noopen",
        "X-Permitted-Cross-Domain-Policies": "none"
    }
    
    # Rate limiting
    RATE_LIMIT_HEADERS = True
    
    # Security monitoring
    LOG_SECURITY_HEADERS = True
    SUSPICIOUS_HEADERS = [
        "x-forwarded-for",
        "x-real-ip",
        "x-cluster-client-ip",
        "cf-connecting-ip"
    ]

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding comprehensive security headers."""
    
    def __init__(self, app, config: SecurityConfig = None):
        super().__init__(app)
        self.config = config or SecurityConfig()
        self._nonce_cache: Dict[str, float] = {}
        
    def _generate_nonce(self) -> str:
        """Generate cryptographically secure nonce for CSP."""
        nonce = secrets.token_urlsafe(16)
        
        # Store nonce with timestamp for cleanup
        current_time = time.time()
        self._nonce_cache[nonce] = current_time
        
        # Clean old nonces (older than 1 hour)
        cutoff_time = current_time - 3600
        self._nonce_cache = {
            n: t for n, t in self._nonce_cache.items() 
            if t > cutoff_time
        }
        
        return nonce
    
    def _build_csp_header(self, nonce: str) -> str:
        """Build Content Security Policy header with nonce."""
        directives = []
        
        for directive, sources in self.config.CSP_DIRECTIVES.items():
            if directive == "script-src":
                # Add nonce to script-src
                sources_with_nonce = sources + [f"'nonce-{nonce}'"]
                directives.append(f"{directive} {' '.join(sources_with_nonce)}")
            else:
                directives.append(f"{directive} {' '.join(sources)}")
        
        return "; ".join(directives)
    
    def _build_permissions_policy_header(self) -> str:
        """Build Permissions Policy header."""
        policies = []
        
        for feature, allowlist in self.config.PERMISSIONS_POLICY.items():
            if not allowlist:
                policies.append(f"{feature}=()")
            else:
                allowed = ' '.join(f'"{origin}"' for origin in allowlist)
                policies.append(f"{feature}=({allowed})")
        
        return ", ".join(policies)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address with proxy support."""
        # Check for forwarded headers (in order of preference)
        forwarded_headers = [
            "cf-connecting-ip",  # Cloudflare
            "x-forwarded-for",   # Standard proxy header
            "x-real-ip",         # Nginx
            "x-cluster-client-ip" # Kubernetes
        ]
        
        for header in forwarded_headers:
            ip = request.headers.get(header)
            if ip:
                # Take first IP if comma-separated
                return ip.split(',')[0].strip()
        
        # Fallback to direct connection
        return request.client.host if request.client else "unknown"
    
    def _detect_suspicious_activity(self, request: Request) -> List[str]:
        """Detect potentially suspicious request patterns."""
        suspicious_indicators = []
        
        # Check for suspicious headers
        for header in self.config.SUSPICIOUS_HEADERS:
            if header in request.headers:
                suspicious_indicators.append(f"suspicious_header:{header}")
        
        # Check for unusual user agents
        user_agent = request.headers.get("user-agent", "").lower()
        suspicious_ua_patterns = [
            "bot", "crawler", "spider", "scraper", "scanner",
            "curl", "wget", "python-requests", "postman"
        ]
        
        for pattern in suspicious_ua_patterns:
            if pattern in user_agent:
                suspicious_indicators.append(f"suspicious_ua:{pattern}")
                break
        
        # Check for missing common headers
        expected_headers = ["accept", "accept-language", "user-agent"]
        missing_headers = [
            header for header in expected_headers 
            if header not in request.headers
        ]
        
        if missing_headers:
            suspicious_indicators.append(f"missing_headers:{','.join(missing_headers)}")
        
        # Check for unusual request patterns
        if request.method in ["PUT", "DELETE", "PATCH"] and not request.headers.get("authorization"):
            suspicious_indicators.append("unauthenticated_modification")
        
        return suspicious_indicators
    
    def _add_security_headers(self, response: Response, nonce: str) -> None:
        """Add all security headers to response."""
        # Basic security headers
        for header, value in self.config.SECURITY_HEADERS.items():
            response.headers[header] = value
        
        # HSTS header (only for HTTPS)
        hsts_value = f"max-age={self.config.HSTS_MAX_AGE}"
        if self.config.HSTS_INCLUDE_SUBDOMAINS:
            hsts_value += "; includeSubDomains"
        if self.config.HSTS_PRELOAD:
            hsts_value += "; preload"
        response.headers["Strict-Transport-Security"] = hsts_value
        
        # Content Security Policy
        csp_header = self._build_csp_header(nonce)
        response.headers["Content-Security-Policy"] = csp_header
        
        # Permissions Policy
        permissions_header = self._build_permissions_policy_header()
        response.headers["Permissions-Policy"] = permissions_header
        
        # Additional security headers
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        
        # Server information hiding
        response.headers["Server"] = "SecureAPI/1.0"
        
        # Cache control for sensitive endpoints
        if any(path in str(response.headers.get("location", "")) for path in ["/auth", "/admin", "/api/user"]):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
    
    def _add_rate_limit_headers(self, response: Response, request: Request) -> None:
        """Add rate limiting information headers."""
        if not self.config.RATE_LIMIT_HEADERS:
            return
        
        # These would typically come from your rate limiting middleware
        # For now, we'll add placeholder headers
        response.headers["X-RateLimit-Limit"] = "1000"
        response.headers["X-RateLimit-Remaining"] = "999"
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 3600)
        response.headers["X-RateLimit-Policy"] = "1000;w=3600"
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and add security headers to response."""
        start_time = time.time()
        
        # Generate nonce for this request
        nonce = self._generate_nonce()
        
        # Store nonce in request state for use in templates
        request.state.csp_nonce = nonce
        
        # Get client information
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        
        # Detect suspicious activity
        suspicious_indicators = self._detect_suspicious_activity(request)
        
        # Log security events if enabled
        if self.config.LOG_SECURITY_HEADERS:
            if suspicious_indicators:
                structured_logger.log_security_event(
                    event_type="suspicious_request",
                    ip_address=client_ip,
                    user_agent=user_agent,
                    indicators=suspicious_indicators,
                    path=str(request.url.path),
                    method=request.method
                )
        
        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log security-related errors
            structured_logger.log_security_event(
                event_type="request_error",
                ip_address=client_ip,
                user_agent=user_agent,
                error=str(e),
                path=str(request.url.path),
                method=request.method
            )
            raise
        
        # Add security headers
        self._add_security_headers(response, nonce)
        
        # Add rate limiting headers
        self._add_rate_limit_headers(response, request)
        
        # Add timing information
        processing_time = time.time() - start_time
        response.headers["X-Response-Time"] = f"{processing_time:.3f}s"
        
        # Add request ID if available
        request_id = getattr(request.state, 'request_id', None)
        if request_id:
            response.headers["X-Request-ID"] = request_id
        
        return response

def setup_cors_middleware(app):
    """Setup CORS middleware with security-focused configuration."""
    config = SecurityConfig()
    
    # Determine allowed origins based on environment
    allowed_origins = config.ALLOWED_ORIGINS
    
    # In production, be more restrictive
    if hasattr(settings, 'ENVIRONMENT') and settings.ENVIRONMENT == 'production':
        # Only allow specific production domains
        allowed_origins = [
            origin for origin in allowed_origins 
            if not origin.startswith('http://localhost')
        ]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=config.ALLOWED_METHODS,
        allow_headers=config.ALLOWED_HEADERS,
        expose_headers=[
            "X-Request-ID",
            "X-Response-Time",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset"
        ],
        max_age=86400  # 24 hours
    )

def setup_security_headers_middleware(app):
    """Setup security headers middleware."""
    config = SecurityConfig()
    app.add_middleware(SecurityHeadersMiddleware, config=config)

# Utility function to get CSP nonce in templates
def get_csp_nonce(request: Request) -> str:
    """Get CSP nonce for the current request."""
    return getattr(request.state, 'csp_nonce', '')