"""Authentication service for user management and token handling."""

import asyncio
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import bcrypt
import jwt
from fastapi import HTTPException, status
from pydantic import BaseModel, EmailStr

from api.core.config import get_settings
from api.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ValidationError,
    DatabaseError
)
from api.core.database import get_db_pool

settings = get_settings()

class UserCreate(BaseModel):
    """User creation model."""
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    """User login model."""
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    """User response model."""
    id: str
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class AuthService:
    """Authentication service for user management."""
    
    def __init__(self):
        self.secret_key = settings.secret_key
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 7
        self.blacklisted_tokens: set = set()
    
    def _hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def _verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    
    def _generate_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Generate a JWT token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def _decode_token(self, token: str) -> dict:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.JWTError:
            raise AuthenticationError("Invalid token")
    
    def generate_reset_token(self) -> str:
        """Generate a secure reset token."""
        return secrets.token_urlsafe(32)
    
    def generate_verification_token(self) -> str:
        """Generate a secure email verification token."""
        return secrets.token_urlsafe(32)
    
    async def create_user(self, user_data: UserCreate) -> UserResponse:
        """Create a new user."""
        pool = await get_db_pool()
        if not pool:
            raise DatabaseError("Database connection failed")
        
        try:
            async with pool.acquire() as conn:
                # Check if user already exists
                existing_user = await conn.fetchrow(
                    "SELECT id FROM users WHERE email = $1",
                    user_data.email
                )
                
                if existing_user:
                    raise ValidationError("User with this email already exists")
                
                # Hash password
                hashed_password = self._hash_password(user_data.password)
                
                # Create user
                user_id = str(uuid.uuid4())
                now = datetime.utcnow()
                
                await conn.execute(
                    """
                    INSERT INTO users (id, email, password_hash, full_name, is_active, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    user_id, user_data.email, hashed_password, user_data.full_name, True, now, now
                )
                
                return UserResponse(
                    id=user_id,
                    email=user_data.email,
                    full_name=user_data.full_name,
                    is_active=True,
                    created_at=now,
                    updated_at=now
                )
        
        except Exception as e:
            if isinstance(e, (ValidationError, AuthenticationError)):
                raise
            raise DatabaseError(f"Failed to create user: {str(e)}")
    
    async def authenticate_user(self, email: str, password: str) -> Optional[UserResponse]:
        """Authenticate a user with email and password."""
        pool = await get_db_pool()
        if not pool:
            raise DatabaseError("Database connection failed")
        
        try:
            async with pool.acquire() as conn:
                user = await conn.fetchrow(
                    "SELECT * FROM users WHERE email = $1 AND is_active = true",
                    email
                )
                
                if not user or not self._verify_password(password, user['password_hash']):
                    return None
                
                return UserResponse(
                    id=user['id'],
                    email=user['email'],
                    full_name=user['full_name'],
                    is_active=user['is_active'],
                    created_at=user['created_at'],
                    updated_at=user['updated_at']
                )
        
        except Exception as e:
            raise DatabaseError(f"Failed to authenticate user: {str(e)}")
    
    async def get_user_by_id(self, user_id: str) -> Optional[UserResponse]:
        """Get user by ID."""
        pool = await get_db_pool()
        if not pool:
            raise DatabaseError("Database connection failed")
        
        try:
            async with pool.acquire() as conn:
                user = await conn.fetchrow(
                    "SELECT * FROM users WHERE id = $1 AND is_active = true",
                    user_id
                )
                
                if not user:
                    return None
                
                return UserResponse(
                    id=user['id'],
                    email=user['email'],
                    full_name=user['full_name'],
                    is_active=user['is_active'],
                    created_at=user['created_at'],
                    updated_at=user['updated_at']
                )
        
        except Exception as e:
            raise DatabaseError(f"Failed to get user: {str(e)}")
    
    async def get_user_by_email(self, email: str) -> Optional[UserResponse]:
        """Get user by email."""
        pool = await get_db_pool()
        if not pool:
            raise DatabaseError("Database connection failed")
        
        try:
            async with pool.acquire() as conn:
                user = await conn.fetchrow(
                    "SELECT * FROM users WHERE email = $1 AND is_active = true",
                    email
                )
                
                if not user:
                    return None
                
                return UserResponse(
                    id=user['id'],
                    email=user['email'],
                    full_name=user['full_name'],
                    is_active=user['is_active'],
                    created_at=user['created_at'],
                    updated_at=user['updated_at']
                )
        
        except Exception as e:
            raise DatabaseError(f"Failed to get user by email: {str(e)}")
    
    def create_access_token(self, user_id: str) -> str:
        """Create an access token for a user."""
        expires_delta = timedelta(minutes=self.access_token_expire_minutes)
        return self._generate_token(
            data={"sub": user_id, "type": "access"},
            expires_delta=expires_delta
        )
    
    def create_refresh_token(self, user_id: str) -> str:
        """Create a refresh token for a user."""
        expires_delta = timedelta(days=self.refresh_token_expire_days)
        return self._generate_token(
            data={"sub": user_id, "type": "refresh"},
            expires_delta=expires_delta
        )
    
    async def login(self, login_data: UserLogin) -> TokenResponse:
        """Login a user and return tokens."""
        user = await self.authenticate_user(login_data.email, login_data.password)
        if not user:
            raise AuthenticationError("Invalid email or password")
        
        access_token = self.create_access_token(user.id)
        refresh_token = self.create_refresh_token(user.id)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.access_token_expire_minutes * 60
        )
    
    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """Refresh an access token using a refresh token."""
        if refresh_token in self.blacklisted_tokens:
            raise AuthenticationError("Token has been revoked")
        
        try:
            payload = self._decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise AuthenticationError("Invalid token type")
            
            user_id = payload.get("sub")
            if not user_id:
                raise AuthenticationError("Invalid token payload")
            
            # Verify user still exists and is active
            user = await self.get_user_by_id(user_id)
            if not user:
                raise AuthenticationError("User not found or inactive")
            
            # Create new tokens
            new_access_token = self.create_access_token(user_id)
            new_refresh_token = self.create_refresh_token(user_id)
            
            # Blacklist old refresh token
            self.blacklisted_tokens.add(refresh_token)
            
            return TokenResponse(
                access_token=new_access_token,
                refresh_token=new_refresh_token,
                expires_in=self.access_token_expire_minutes * 60
            )
        
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Refresh token has expired")
        except jwt.JWTError:
            raise AuthenticationError("Invalid refresh token")
    
    async def logout(self, access_token: str, refresh_token: Optional[str] = None) -> bool:
        """Logout a user by blacklisting their tokens."""
        try:
            # Blacklist access token
            self.blacklisted_tokens.add(access_token)
            
            # Blacklist refresh token if provided
            if refresh_token:
                self.blacklisted_tokens.add(refresh_token)
            
            return True
        
        except Exception as e:
            raise AuthenticationError(f"Failed to logout: {str(e)}")
    
    async def verify_token(self, token: str) -> dict:
        """Verify and decode a token."""
        if token in self.blacklisted_tokens:
            raise AuthenticationError("Token has been revoked")
        
        return self._decode_token(token)
    
    async def get_current_user(self, token: str) -> UserResponse:
        """Get current user from token."""
        payload = await self.verify_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            raise AuthenticationError("Invalid token payload")
        
        user = await self.get_user_by_id(user_id)
        if not user:
            raise AuthenticationError("User not found or inactive")
        
        return user
    
    async def update_password(self, user_id: str, new_password: str) -> bool:
        """Update user password."""
        pool = await get_db_pool()
        if not pool:
            raise DatabaseError("Database connection failed")
        
        try:
            async with pool.acquire() as conn:
                hashed_password = self._hash_password(new_password)
                
                result = await conn.execute(
                    "UPDATE users SET password_hash = $1, updated_at = $2 WHERE id = $3",
                    hashed_password, datetime.utcnow(), user_id
                )
                
                return result == "UPDATE 1"
        
        except Exception as e:
            raise DatabaseError(f"Failed to update password: {str(e)}")
    
    async def store_reset_token(self, email: str, token: str) -> bool:
        """Store password reset token."""
        pool = await get_db_pool()
        if not pool:
            raise DatabaseError("Database connection failed")
        
        try:
            async with pool.acquire() as conn:
                expires_at = datetime.utcnow() + timedelta(hours=1)  # Token expires in 1 hour
                
                await conn.execute(
                    """
                    INSERT INTO password_reset_tokens (email, token, expires_at, created_at)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (email) DO UPDATE SET
                        token = EXCLUDED.token,
                        expires_at = EXCLUDED.expires_at,
                        created_at = EXCLUDED.created_at
                    """,
                    email, token, expires_at, datetime.utcnow()
                )
                
                return True
        
        except Exception as e:
            raise DatabaseError(f"Failed to store reset token: {str(e)}")
    
    async def verify_reset_token(self, token: str) -> Optional[str]:
        """Verify password reset token and return email."""
        pool = await get_db_pool()
        if not pool:
            raise DatabaseError("Database connection failed")
        
        try:
            async with pool.acquire() as conn:
                result = await conn.fetchrow(
                    """
                    SELECT email FROM password_reset_tokens 
                    WHERE token = $1 AND expires_at > $2
                    """,
                    token, datetime.utcnow()
                )
                
                if result:
                    # Delete used token
                    await conn.execute(
                        "DELETE FROM password_reset_tokens WHERE token = $1",
                        token
                    )
                    return result['email']
                
                return None
        
        except Exception as e:
            raise DatabaseError(f"Failed to verify reset token: {str(e)}")

# Global auth service instance
auth_service = AuthService()