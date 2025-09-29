from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Union
import logging
import traceback
from datetime import datetime

# Configure logger
logger = logging.getLogger(__name__)

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Global error handling middleware for the application."""
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            return await self.handle_exception(request, exc)
    
    async def handle_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """Handle different types of exceptions and return appropriate responses."""
        
        # Log the exception
        logger.error(
            f"Exception occurred: {type(exc).__name__}: {str(exc)}",
            extra={
                "path": request.url.path,
                "method": request.method,
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
                "timestamp": datetime.utcnow().isoformat(),
                "traceback": traceback.format_exc()
            }
        )
        
        # Handle specific exception types
        if isinstance(exc, HTTPException):
            return await self.handle_http_exception(exc)
        elif isinstance(exc, RequestValidationError):
            return await self.handle_validation_error(exc)
        elif isinstance(exc, StarletteHTTPException):
            return await self.handle_starlette_exception(exc)
        else:
            return await self.handle_generic_exception(exc)
    
    async def handle_http_exception(self, exc: HTTPException) -> JSONResponse:
        """Handle FastAPI HTTP exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "type": "http_exception",
                    "message": exc.detail,
                    "status_code": exc.status_code
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    async def handle_validation_error(self, exc: RequestValidationError) -> JSONResponse:
        """Handle request validation errors."""
        errors = []
        for error in exc.errors():
            errors.append({
                "field": " -> ".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })
        
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "type": "validation_error",
                    "message": "Request validation failed",
                    "details": errors
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    async def handle_starlette_exception(self, exc: StarletteHTTPException) -> JSONResponse:
        """Handle Starlette HTTP exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "type": "starlette_exception",
                    "message": exc.detail,
                    "status_code": exc.status_code
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    async def handle_generic_exception(self, exc: Exception) -> JSONResponse:
        """Handle generic exceptions."""
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "type": "internal_server_error",
                    "message": "An internal server error occurred",
                    "details": str(exc) if logger.level <= logging.DEBUG else None
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )

class AuthenticationError(HTTPException):
    """Custom authentication error."""
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(status_code=401, detail=detail)

class AuthorizationError(HTTPException):
    """Custom authorization error."""
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(status_code=403, detail=detail)

class ResourceNotFoundError(HTTPException):
    """Custom resource not found error."""
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=404, detail=detail)

class ConflictError(HTTPException):
    """Custom conflict error."""
    def __init__(self, detail: str = "Resource conflict"):
        super().__init__(status_code=409, detail=detail)

class RateLimitError(HTTPException):
    """Custom rate limit error."""
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(status_code=429, detail=detail)

class ValidationError(HTTPException):
    """Custom validation error."""
    def __init__(self, detail: str = "Validation failed"):
        super().__init__(status_code=400, detail=detail)

# Error response helpers
def create_error_response(
    message: str,
    status_code: int = 400,
    error_type: str = "error",
    details: Union[dict, list, None] = None
) -> JSONResponse:
    """Create a standardized error response."""
    content = {
        "error": {
            "type": error_type,
            "message": message,
            "status_code": status_code
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if details:
        content["error"]["details"] = details
    
    return JSONResponse(status_code=status_code, content=content)

def create_validation_error_response(
    errors: list,
    message: str = "Validation failed"
) -> JSONResponse:
    """Create a validation error response."""
    return create_error_response(
        message=message,
        status_code=422,
        error_type="validation_error",
        details=errors
    )

def create_auth_error_response(
    message: str = "Authentication required"
) -> JSONResponse:
    """Create an authentication error response."""
    return create_error_response(
        message=message,
        status_code=401,
        error_type="authentication_error"
    )

def create_permission_error_response(
    message: str = "Insufficient permissions"
) -> JSONResponse:
    """Create a permission error response."""
    return create_error_response(
        message=message,
        status_code=403,
        error_type="authorization_error"
    )