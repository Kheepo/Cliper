#!/usr/bin/env python3
"""
Example endpoints demonstrating the enhanced API documentation system.
Shows how to use the documentation decorators and utilities for comprehensive API docs.
"""

from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, Query, Path, Body
from pydantic import BaseModel, Field
from datetime import datetime

from api.core.api_docs import (
    create_endpoint_docs,
    create_response_examples,
    setup_api_documentation,
    APIDocumentationConfig,
    DocumentationLevel
)


# Pydantic models for request/response
class User(BaseModel):
    """User model with comprehensive field documentation."""
    id: int = Field(..., description="Unique user identifier", example=1)
    username: str = Field(
        ..., 
        description="Username (3-50 characters, alphanumeric and underscores only)",
        min_length=3,
        max_length=50,
        regex=r"^[a-zA-Z0-9_]+$",
        example="john_doe"
    )
    email: str = Field(
        ..., 
        description="Valid email address",
        example="john.doe@example.com"
    )
    full_name: Optional[str] = Field(
        None, 
        description="User's full name",
        example="John Doe"
    )
    is_active: bool = Field(
        True, 
        description="Whether the user account is active",
        example=True
    )
    created_at: datetime = Field(
        ..., 
        description="Account creation timestamp",
        example="2024-01-15T10:30:00Z"
    )
    last_login: Optional[datetime] = Field(
        None, 
        description="Last login timestamp",
        example="2024-01-20T14:45:00Z"
    )


class UserCreate(BaseModel):
    """User creation request model."""
    username: str = Field(
        ..., 
        description="Desired username",
        min_length=3,
        max_length=50,
        example="new_user"
    )
    email: str = Field(
        ..., 
        description="User's email address",
        example="new.user@example.com"
    )
    password: str = Field(
        ..., 
        description="Password (minimum 8 characters)",
        min_length=8,
        example="SecurePass123!"
    )
    full_name: Optional[str] = Field(
        None, 
        description="User's full name",
        example="New User"
    )


class UserUpdate(BaseModel):
    """User update request model."""
    email: Optional[str] = Field(
        None, 
        description="New email address",
        example="updated.email@example.com"
    )
    full_name: Optional[str] = Field(
        None, 
        description="Updated full name",
        example="Updated Name"
    )
    is_active: Optional[bool] = Field(
        None, 
        description="Update account status",
        example=False
    )


class UserList(BaseModel):
    """Paginated user list response."""
    users: List[User] = Field(
        ..., 
        description="List of users"
    )
    total: int = Field(
        ..., 
        description="Total number of users",
        example=150
    )
    page: int = Field(
        ..., 
        description="Current page number",
        example=1
    )
    per_page: int = Field(
        ..., 
        description="Number of users per page",
        example=20
    )
    has_next: bool = Field(
        ..., 
        description="Whether there are more pages",
        example=True
    )


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str = Field(
        ..., 
        description="Error type or code",
        example="VALIDATION_ERROR"
    )
    message: str = Field(
        ..., 
        description="Human-readable error message",
        example="The provided data is invalid"
    )
    details: Optional[dict] = Field(
        None, 
        description="Additional error details",
        example={"field": "email", "issue": "Invalid email format"}
    )
    timestamp: datetime = Field(
        ..., 
        description="Error occurrence timestamp",
        example="2024-01-20T15:30:00Z"
    )


# Create FastAPI app with enhanced documentation
app = FastAPI(
    title="User Management API",
    description="Comprehensive user management system with enhanced documentation",
    version="2.0.0",
    contact={
        "name": "API Support",
        "email": "support@example.com",
        "url": "https://example.com/support"
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    }
)


# Mock database for demonstration
users_db = [
    User(
        id=1,
        username="john_doe",
        email="john.doe@example.com",
        full_name="John Doe",
        is_active=True,
        created_at=datetime(2024, 1, 15, 10, 30),
        last_login=datetime(2024, 1, 20, 14, 45)
    ),
    User(
        id=2,
        username="jane_smith",
        email="jane.smith@example.com",
        full_name="Jane Smith",
        is_active=True,
        created_at=datetime(2024, 1, 16, 9, 15),
        last_login=datetime(2024, 1, 19, 16, 20)
    )
]


@app.get(
    "/users",
    response_model=UserList,
    **create_endpoint_docs(
        summary="Get Users",
        description="""
        Retrieve a paginated list of users with optional filtering and sorting.
        
        This endpoint supports:
        - Pagination with customizable page size
        - Filtering by active status
        - Sorting by various fields
        - Search by username or email
        
        **Rate Limiting:** 100 requests per minute per API key
        
        **Authentication:** Requires valid Bearer token or API key
        """,
        tags=["Users", "Public"],
        responses={
            200: {
                "description": "Successfully retrieved users",
                "model": UserList
            },
            400: {
                "description": "Invalid query parameters",
                "model": ErrorResponse
            },
            401: {
                "description": "Authentication required",
                "model": ErrorResponse
            },
            403: {
                "description": "Insufficient permissions",
                "model": ErrorResponse
            },
            429: {
                "description": "Rate limit exceeded",
                "model": ErrorResponse
            }
        },
        examples=[
            {
                "name": "Basic Request",
                "summary": "Get first page of users",
                "description": "Retrieve the first 20 users with default settings",
                "value": {
                    "page": 1,
                    "per_page": 20
                }
            },
            {
                "name": "Filtered Request",
                "summary": "Get active users only",
                "description": "Retrieve only active users with custom page size",
                "value": {
                    "page": 1,
                    "per_page": 10,
                    "active_only": True
                }
            },
            {
                "name": "Search Request",
                "summary": "Search users by username",
                "description": "Search for users with username containing 'john'",
                "value": {
                    "page": 1,
                    "per_page": 20,
                    "search": "john"
                }
            }
        ]
    )
)
async def get_users(
    page: int = Query(
        1, 
        ge=1, 
        description="Page number (starts from 1)",
        example=1
    ),
    per_page: int = Query(
        20, 
        ge=1, 
        le=100, 
        description="Number of users per page (1-100)",
        example=20
    ),
    active_only: Optional[bool] = Query(
        None, 
        description="Filter by active status",
        example=True
    ),
    search: Optional[str] = Query(
        None, 
        description="Search by username or email",
        example="john"
    ),
    sort_by: Optional[str] = Query(
        "created_at", 
        description="Sort field (created_at, username, email)",
        example="username"
    ),
    sort_order: Optional[str] = Query(
        "desc", 
        description="Sort order (asc, desc)",
        example="asc"
    )
):
    """Get paginated list of users with filtering and sorting."""
    
    # Apply filters
    filtered_users = users_db
    if active_only is not None:
        filtered_users = [u for u in filtered_users if u.is_active == active_only]
    
    if search:
        filtered_users = [
            u for u in filtered_users 
            if search.lower() in u.username.lower() or search.lower() in u.email.lower()
        ]
    
    # Apply pagination
    total = len(filtered_users)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_users = filtered_users[start_idx:end_idx]
    
    return UserList(
        users=page_users,
        total=total,
        page=page,
        per_page=per_page,
        has_next=end_idx < total
    )


@app.get(
    "/users/{user_id}",
    response_model=User,
    **create_endpoint_docs(
        summary="Get User by ID",
        description="""
        Retrieve a specific user by their unique identifier.
        
        **Security Notes:**
        - Users can only access their own data unless they have admin privileges
        - Admin users can access any user's data
        - Inactive users cannot be retrieved by non-admin users
        
        **Rate Limiting:** 200 requests per minute per API key
        """,
        tags=["Users"],
        responses={
            200: {
                "description": "User found and returned",
                "model": User
            },
            404: {
                "description": "User not found",
                "model": ErrorResponse
            },
            401: {
                "description": "Authentication required",
                "model": ErrorResponse
            },
            403: {
                "description": "Access denied - insufficient permissions",
                "model": ErrorResponse
            }
        },
        examples=[
            {
                "name": "Valid User ID",
                "summary": "Get existing user",
                "description": "Retrieve user with ID 1",
                "value": {"user_id": 1}
            },
            {
                "name": "Non-existent User",
                "summary": "User not found scenario",
                "description": "Attempt to retrieve non-existent user",
                "value": {"user_id": 999}
            }
        ]
    )
)
async def get_user(
    user_id: int = Path(
        ..., 
        ge=1, 
        description="Unique user identifier",
        example=1
    )
):
    """Get a specific user by ID."""
    
    user = next((u for u in users_db if u.id == user_id), None)
    if not user:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "USER_NOT_FOUND",
                "message": f"User with ID {user_id} not found",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    return user


@app.post(
    "/users",
    response_model=User,
    status_code=201,
    **create_endpoint_docs(
        summary="Create New User",
        description="""
        Create a new user account with the provided information.
        
        **Validation Rules:**
        - Username must be unique and 3-50 characters
        - Email must be valid and unique
        - Password must be at least 8 characters
        - Username can only contain letters, numbers, and underscores
        
        **Business Logic:**
        - New users are active by default
        - Email verification is sent automatically
        - Welcome email is triggered on successful creation
        
        **Rate Limiting:** 10 requests per minute per IP address
        """,
        tags=["Users", "Registration"],
        responses={
            201: {
                "description": "User created successfully",
                "model": User
            },
            400: {
                "description": "Invalid input data",
                "model": ErrorResponse
            },
            409: {
                "description": "Username or email already exists",
                "model": ErrorResponse
            },
            422: {
                "description": "Validation error",
                "model": ErrorResponse
            },
            429: {
                "description": "Rate limit exceeded",
                "model": ErrorResponse
            }
        },
        examples=[
            {
                "name": "Basic User Creation",
                "summary": "Create user with minimal data",
                "description": "Create a new user with only required fields",
                "value": {
                    "username": "new_user",
                    "email": "new.user@example.com",
                    "password": "SecurePass123!"
                }
            },
            {
                "name": "Complete User Creation",
                "summary": "Create user with all fields",
                "description": "Create a new user with all available fields",
                "value": {
                    "username": "complete_user",
                    "email": "complete.user@example.com",
                    "password": "VerySecurePass456!",
                    "full_name": "Complete User Name"
                }
            }
        ]
    )
)
async def create_user(
    user_data: UserCreate = Body(
        ...,
        description="User creation data",
        examples={
            "basic": {
                "summary": "Basic user data",
                "value": {
                    "username": "example_user",
                    "email": "user@example.com",
                    "password": "SecurePassword123!"
                }
            },
            "complete": {
                "summary": "Complete user data",
                "value": {
                    "username": "complete_user",
                    "email": "complete@example.com",
                    "password": "VerySecurePass456!",
                    "full_name": "Complete User"
                }
            }
        }
    )
):
    """Create a new user account."""
    
    # Check for existing username or email
    existing_user = next(
        (u for u in users_db if u.username == user_data.username or u.email == user_data.email),
        None
    )
    
    if existing_user:
        conflict_field = "username" if existing_user.username == user_data.username else "email"
        raise HTTPException(
            status_code=409,
            detail={
                "error": "USER_ALREADY_EXISTS",
                "message": f"User with this {conflict_field} already exists",
                "details": {"field": conflict_field, "value": getattr(user_data, conflict_field)},
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    # Create new user
    new_user = User(
        id=len(users_db) + 1,
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        is_active=True,
        created_at=datetime.utcnow(),
        last_login=None
    )
    
    users_db.append(new_user)
    return new_user


@app.put(
    "/users/{user_id}",
    response_model=User,
    **create_endpoint_docs(
        summary="Update User",
        description="""
        Update an existing user's information.
        
        **Authorization:**
        - Users can only update their own profile
        - Admin users can update any user's profile
        - Some fields may require additional permissions
        
        **Update Rules:**
        - Only provided fields will be updated
        - Email changes require verification
        - Username changes may not be allowed based on policy
        
        **Rate Limiting:** 20 requests per minute per user
        """,
        tags=["Users"],
        responses={
            200: {
                "description": "User updated successfully",
                "model": User
            },
            400: {
                "description": "Invalid update data",
                "model": ErrorResponse
            },
            401: {
                "description": "Authentication required",
                "model": ErrorResponse
            },
            403: {
                "description": "Insufficient permissions",
                "model": ErrorResponse
            },
            404: {
                "description": "User not found",
                "model": ErrorResponse
            },
            409: {
                "description": "Email already in use",
                "model": ErrorResponse
            }
        },
        examples=[
            {
                "name": "Update Email",
                "summary": "Change user email",
                "description": "Update only the user's email address",
                "value": {
                    "email": "newemail@example.com"
                }
            },
            {
                "name": "Update Multiple Fields",
                "summary": "Update multiple user fields",
                "description": "Update email, full name, and status",
                "value": {
                    "email": "updated@example.com",
                    "full_name": "Updated Full Name",
                    "is_active": False
                }
            }
        ]
    )
)
async def update_user(
    user_id: int = Path(
        ..., 
        ge=1, 
        description="ID of the user to update",
        example=1
    ),
    user_data: UserUpdate = Body(
        ...,
        description="User update data",
        examples={
            "email_only": {
                "summary": "Update email only",
                "value": {"email": "new.email@example.com"}
            },
            "full_update": {
                "summary": "Update multiple fields",
                "value": {
                    "email": "updated@example.com",
                    "full_name": "Updated Name",
                    "is_active": True
                }
            }
        }
    )
):
    """Update an existing user's information."""
    
    # Find user
    user_index = next(
        (i for i, u in enumerate(users_db) if u.id == user_id),
        None
    )
    
    if user_index is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "USER_NOT_FOUND",
                "message": f"User with ID {user_id} not found",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    user = users_db[user_index]
    
    # Check for email conflicts
    if user_data.email and user_data.email != user.email:
        existing_email = next(
            (u for u in users_db if u.email == user_data.email and u.id != user_id),
            None
        )
        if existing_email:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "EMAIL_ALREADY_EXISTS",
                    "message": "Email address is already in use",
                    "details": {"field": "email", "value": user_data.email},
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
    
    # Update user fields
    update_data = user_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    users_db[user_index] = user
    return user


@app.delete(
    "/users/{user_id}",
    status_code=204,
    **create_endpoint_docs(
        summary="Delete User",
        description="""
        Permanently delete a user account and all associated data.
        
        **⚠️ Warning:** This action is irreversible!
        
        **Authorization:**
        - Only admin users can delete accounts
        - Users cannot delete their own accounts through this endpoint
        - Use account deactivation for reversible user management
        
        **Data Handling:**
        - All user data is permanently removed
        - Associated content may be anonymized or transferred
        - Audit logs are maintained for compliance
        
        **Rate Limiting:** 5 requests per minute per admin user
        """,
        tags=["Users", "Admin"],
        responses={
            204: {
                "description": "User deleted successfully"
            },
            401: {
                "description": "Authentication required",
                "model": ErrorResponse
            },
            403: {
                "description": "Admin privileges required",
                "model": ErrorResponse
            },
            404: {
                "description": "User not found",
                "model": ErrorResponse
            },
            409: {
                "description": "Cannot delete user with active dependencies",
                "model": ErrorResponse
            }
        },
        examples=[
            {
                "name": "Delete User",
                "summary": "Delete user account",
                "description": "Permanently delete user with ID 1",
                "value": {"user_id": 1}
            }
        ]
    )
)
async def delete_user(
    user_id: int = Path(
        ..., 
        ge=1, 
        description="ID of the user to delete",
        example=1
    )
):
    """Delete a user account permanently."""
    
    user_index = next(
        (i for i, u in enumerate(users_db) if u.id == user_id),
        None
    )
    
    if user_index is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "USER_NOT_FOUND",
                "message": f"User with ID {user_id} not found",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    # Remove user from database
    del users_db[user_index]
    
    # Return 204 No Content
    return None


# Setup enhanced documentation
if __name__ == "__main__":
    # Configure enhanced documentation
    config = APIDocumentationConfig(
        title="User Management API - Enhanced Documentation",
        description="Comprehensive example of enhanced API documentation",
        version="2.0.0",
        documentation_level=DocumentationLevel.COMPREHENSIVE,
        include_examples=True,
        include_error_responses=True,
        include_security_schemes=True,
        include_rate_limiting=True,
        include_monitoring_endpoints=True,
        custom_css="""
        .swagger-ui .topbar { background-color: #2c3e50; }
        .swagger-ui .topbar .download-url-wrapper { display: none; }
        """,
        custom_js="""
        console.log('Enhanced API Documentation Loaded');
        """
    )
    
    setup_api_documentation(app, config)
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)