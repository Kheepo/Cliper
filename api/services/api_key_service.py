"""API Key Management Service.

Provides comprehensive API key management:
- API key generation with cryptographic security
- Key rotation and expiration management
- Secure storage with hashing
- Usage tracking and rate limiting
- Key scoping and permissions
- Audit logging for key operations
"""

import logging
import secrets
import hashlib
import hmac
from typing import Optional, Dict, List, Any, Set
from datetime import datetime, timedelta, timezone
from enum import Enum
from dataclasses import dataclass
import redis
import json
from pydantic import BaseModel

from api.core.config import settings
from api.utils.structured_logging import StructuredLogger
from api.utils.supabase_client import get_supabase_admin_client

logger = logging.getLogger(__name__)
structured_logger = StructuredLogger("api_key_service")

class APIKeyStatus(str, Enum):
    """API key status enumeration."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"

class APIKeyScope(str, Enum):
    """API key scope enumeration."""
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    ADMIN = "admin"
    WEBHOOK = "webhook"
    INTEGRATION = "integration"

@dataclass
class APIKeyConfig:
    """API key configuration."""
    default_expiry_days: int = 90
    max_keys_per_user: int = 10
    key_prefix: str = "sk_"
    key_length: int = 32
    hash_algorithm: str = "sha256"
    rotation_warning_days: int = 7
    rate_limit_per_hour: int = 1000
    enable_usage_tracking: bool = True
    enable_ip_restrictions: bool = True

class APIKeyInfo(BaseModel):
    """API key information model."""
    key_id: str
    user_id: str
    name: str
    scope: APIKeyScope
    status: APIKeyStatus
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    usage_count: int = 0
    rate_limit_per_hour: int
    allowed_ips: List[str] = []
    metadata: Dict[str, Any] = {}

class APIKeyUsage(BaseModel):
    """API key usage tracking model."""
    key_id: str
    timestamp: datetime
    endpoint: str
    method: str
    ip_address: str
    user_agent: str
    response_status: int
    response_time_ms: float

class APIKeyService:
    """Service for managing API keys."""
    
    def __init__(self):
        self.config = APIKeyConfig()
        self.redis = redis.Redis.from_url(settings.REDIS_URL) if hasattr(settings, 'REDIS_URL') else None
        self.supabase = get_supabase_admin_client()
        
        # In-memory fallback if Redis is not available
        self._key_cache: Dict[str, APIKeyInfo] = {}
        self._usage_cache: List[APIKeyUsage] = []
    
    def _generate_key_id(self) -> str:
        """Generate unique key ID."""
        return secrets.token_urlsafe(16)
    
    def _generate_api_key(self) -> str:
        """Generate cryptographically secure API key."""
        key_bytes = secrets.token_bytes(self.config.key_length)
        key_string = secrets.token_urlsafe(self.config.key_length)
        return f"{self.config.key_prefix}{key_string}"
    
    def _hash_api_key(self, api_key: str) -> str:
        """Create secure hash of API key for storage."""
        # Use HMAC with a secret key for additional security
        secret_key = getattr(settings, 'API_KEY_SECRET', 'default-secret-key').encode()
        return hmac.new(secret_key, api_key.encode(), hashlib.sha256).hexdigest()
    
    def _get_redis_key(self, key_type: str, identifier: str) -> str:
        """Generate Redis key with namespace."""
        return f"api_keys:{key_type}:{identifier}"
    
    def _validate_key_format(self, api_key: str) -> bool:
        """Validate API key format."""
        if not api_key.startswith(self.config.key_prefix):
            return False
        
        # Remove prefix and check length
        key_part = api_key[len(self.config.key_prefix):]
        if len(key_part) < 32:  # Minimum length for security
            return False
        
        return True
    
    def _get_scope_permissions(self, scope: APIKeyScope) -> Set[str]:
        """Get permissions for API key scope."""
        scope_permissions = {
            APIKeyScope.READ_ONLY: {'read'},
            APIKeyScope.READ_WRITE: {'read', 'write'},
            APIKeyScope.ADMIN: {'read', 'write', 'delete', 'admin'},
            APIKeyScope.WEBHOOK: {'webhook'},
            APIKeyScope.INTEGRATION: {'read', 'write', 'integration'}
        }
        return scope_permissions.get(scope, {'read'})
    
    async def create_api_key(
        self,
        user_id: str,
        name: str,
        scope: APIKeyScope = APIKeyScope.READ_ONLY,
        expires_in_days: Optional[int] = None,
        allowed_ips: List[str] = None,
        rate_limit_per_hour: Optional[int] = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create new API key."""
        try:
            # Check user's existing key count
            existing_keys = await self.list_user_keys(user_id, status_filter=APIKeyStatus.ACTIVE)
            if len(existing_keys) >= self.config.max_keys_per_user:
                raise ValueError(f"Maximum number of API keys ({self.config.max_keys_per_user}) reached")
            
            # Generate key components
            key_id = self._generate_key_id()
            api_key = self._generate_api_key()
            key_hash = self._hash_api_key(api_key)
            
            # Set expiration
            expires_at = None
            if expires_in_days or self.config.default_expiry_days:
                days = expires_in_days or self.config.default_expiry_days
                expires_at = datetime.now(timezone.utc) + timedelta(days=days)
            
            # Create key info
            key_info = APIKeyInfo(
                key_id=key_id,
                user_id=user_id,
                name=name,
                scope=scope,
                status=APIKeyStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
                expires_at=expires_at,
                last_used_at=None,
                usage_count=0,
                rate_limit_per_hour=rate_limit_per_hour or self.config.rate_limit_per_hour,
                allowed_ips=allowed_ips or [],
                metadata=metadata or {}
            )
            
            # Store in database
            key_data = {
                'key_id': key_id,
                'user_id': user_id,
                'name': name,
                'key_hash': key_hash,
                'scope': scope.value,
                'status': APIKeyStatus.ACTIVE.value,
                'created_at': key_info.created_at.isoformat(),
                'expires_at': key_info.expires_at.isoformat() if key_info.expires_at else None,
                'rate_limit_per_hour': key_info.rate_limit_per_hour,
                'allowed_ips': json.dumps(key_info.allowed_ips),
                'metadata': json.dumps(key_info.metadata)
            }
            
            result = self.supabase.table('api_keys').insert(key_data).execute()
            if not result.data:
                raise Exception("Failed to store API key in database")
            
            # Cache key info
            if self.redis:
                self.redis.setex(
                    self._get_redis_key('info', key_hash),
                    86400,  # 24 hours
                    key_info.json()
                )
                
                # Add to user's key set
                self.redis.sadd(self._get_redis_key('user', user_id), key_id)
            else:
                self._key_cache[key_hash] = key_info
            
            # Log key creation
            structured_logger.log_security_event(
                event_type="api_key_created",
                user_id=user_id,
                key_id=key_id,
                scope=scope.value,
                expires_at=key_info.expires_at.isoformat() if key_info.expires_at else None
            )
            
            return {
                'key_id': key_id,
                'api_key': api_key,  # Only returned once during creation
                'name': name,
                'scope': scope.value,
                'expires_at': key_info.expires_at.isoformat() if key_info.expires_at else None,
                'rate_limit_per_hour': key_info.rate_limit_per_hour,
                'permissions': list(self._get_scope_permissions(scope))
            }
            
        except Exception as e:
            logger.error(f"Error creating API key: {str(e)}")
            raise
    
    async def validate_api_key(self, api_key: str, ip_address: str = None) -> Optional[APIKeyInfo]:
        """Validate API key and return key information."""
        try:
            # Validate key format
            if not self._validate_key_format(api_key):
                return None
            
            # Hash the key for lookup
            key_hash = self._hash_api_key(api_key)
            
            # Try to get from cache first
            key_info = None
            if self.redis:
                cached_data = self.redis.get(self._get_redis_key('info', key_hash))
                if cached_data:
                    key_info = APIKeyInfo.parse_raw(cached_data)
            else:
                key_info = self._key_cache.get(key_hash)
            
            # If not in cache, get from database
            if not key_info:
                result = self.supabase.table('api_keys').select('*').eq('key_hash', key_hash).execute()
                if not result.data:
                    return None
                
                key_data = result.data[0]
                key_info = APIKeyInfo(
                    key_id=key_data['key_id'],
                    user_id=key_data['user_id'],
                    name=key_data['name'],
                    scope=APIKeyScope(key_data['scope']),
                    status=APIKeyStatus(key_data['status']),
                    created_at=datetime.fromisoformat(key_data['created_at']),
                    expires_at=datetime.fromisoformat(key_data['expires_at']) if key_data['expires_at'] else None,
                    last_used_at=datetime.fromisoformat(key_data['last_used_at']) if key_data['last_used_at'] else None,
                    usage_count=key_data.get('usage_count', 0),
                    rate_limit_per_hour=key_data['rate_limit_per_hour'],
                    allowed_ips=json.loads(key_data['allowed_ips']) if key_data['allowed_ips'] else [],
                    metadata=json.loads(key_data['metadata']) if key_data['metadata'] else {}
                )
                
                # Cache the key info
                if self.redis:
                    self.redis.setex(
                        self._get_redis_key('info', key_hash),
                        86400,
                        key_info.json()
                    )
                else:
                    self._key_cache[key_hash] = key_info
            
            # Validate key status
            if key_info.status != APIKeyStatus.ACTIVE:
                return None
            
            # Check expiration
            if key_info.expires_at and key_info.expires_at < datetime.now(timezone.utc):
                # Mark as expired
                await self._update_key_status(key_info.key_id, APIKeyStatus.EXPIRED)
                return None
            
            # Check IP restrictions
            if ip_address and key_info.allowed_ips:
                if ip_address not in key_info.allowed_ips:
                    structured_logger.log_security_event(
                        event_type="api_key_ip_violation",
                        key_id=key_info.key_id,
                        user_id=key_info.user_id,
                        ip_address=ip_address,
                        allowed_ips=key_info.allowed_ips
                    )
                    return None
            
            # Check rate limiting
            if await self._is_rate_limited(key_info.key_id, key_info.rate_limit_per_hour):
                return None
            
            return key_info
            
        except Exception as e:
            logger.error(f"Error validating API key: {str(e)}")
            return None
    
    async def _is_rate_limited(self, key_id: str, rate_limit: int) -> bool:
        """Check if API key is rate limited."""
        if self.redis:
            key = self._get_redis_key('rate_limit', key_id)
            current_count = self.redis.get(key)
            
            if current_count and int(current_count) >= rate_limit:
                return True
        
        return False
    
    async def record_key_usage(
        self,
        key_id: str,
        endpoint: str,
        method: str,
        ip_address: str,
        user_agent: str,
        response_status: int,
        response_time_ms: float
    ) -> None:
        """Record API key usage."""
        try:
            # Update usage count and last used timestamp
            now = datetime.now(timezone.utc)
            
            # Update in database
            self.supabase.table('api_keys').update({
                'last_used_at': now.isoformat(),
                'usage_count': self.supabase.rpc('increment_usage_count', {'key_id_param': key_id})
            }).eq('key_id', key_id).execute()
            
            # Record detailed usage if enabled
            if self.config.enable_usage_tracking:
                usage_record = APIKeyUsage(
                    key_id=key_id,
                    timestamp=now,
                    endpoint=endpoint,
                    method=method,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    response_status=response_status,
                    response_time_ms=response_time_ms
                )
                
                # Store usage record
                usage_data = {
                    'key_id': key_id,
                    'timestamp': now.isoformat(),
                    'endpoint': endpoint,
                    'method': method,
                    'ip_address': ip_address,
                    'user_agent': user_agent,
                    'response_status': response_status,
                    'response_time_ms': response_time_ms
                }
                
                self.supabase.table('api_key_usage').insert(usage_data).execute()
            
            # Update rate limiting counter
            if self.redis:
                rate_limit_key = self._get_redis_key('rate_limit', key_id)
                pipe = self.redis.pipeline()
                pipe.incr(rate_limit_key)
                pipe.expire(rate_limit_key, 3600)  # 1 hour
                pipe.execute()
            
        except Exception as e:
            logger.error(f"Error recording key usage: {str(e)}")
    
    async def rotate_api_key(self, key_id: str, user_id: str) -> Dict[str, Any]:
        """Rotate API key (create new key and revoke old one)."""
        try:
            # Get existing key info
            result = self.supabase.table('api_keys').select('*').eq('key_id', key_id).eq('user_id', user_id).execute()
            if not result.data:
                raise ValueError("API key not found")
            
            old_key_data = result.data[0]
            
            # Create new key with same properties
            new_key = await self.create_api_key(
                user_id=user_id,
                name=f"{old_key_data['name']} (Rotated)",
                scope=APIKeyScope(old_key_data['scope']),
                expires_in_days=None,  # Use default
                allowed_ips=json.loads(old_key_data['allowed_ips']) if old_key_data['allowed_ips'] else None,
                rate_limit_per_hour=old_key_data['rate_limit_per_hour'],
                metadata=json.loads(old_key_data['metadata']) if old_key_data['metadata'] else None
            )
            
            # Revoke old key
            await self.revoke_api_key(key_id, user_id)
            
            # Log rotation
            structured_logger.log_security_event(
                event_type="api_key_rotated",
                user_id=user_id,
                old_key_id=key_id,
                new_key_id=new_key['key_id']
            )
            
            return new_key
            
        except Exception as e:
            logger.error(f"Error rotating API key: {str(e)}")
            raise
    
    async def revoke_api_key(self, key_id: str, user_id: str) -> bool:
        """Revoke API key."""
        try:
            # Update status in database
            result = self.supabase.table('api_keys').update({
                'status': APIKeyStatus.REVOKED.value,
                'revoked_at': datetime.now(timezone.utc).isoformat()
            }).eq('key_id', key_id).eq('user_id', user_id).execute()
            
            if not result.data:
                return False
            
            # Remove from cache
            if self.redis:
                # We don't have the key hash, so we'll let it expire naturally
                self.redis.srem(self._get_redis_key('user', user_id), key_id)
            
            # Log revocation
            structured_logger.log_security_event(
                event_type="api_key_revoked",
                user_id=user_id,
                key_id=key_id
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error revoking API key: {str(e)}")
            return False
    
    async def _update_key_status(self, key_id: str, status: APIKeyStatus) -> bool:
        """Update API key status."""
        try:
            result = self.supabase.table('api_keys').update({
                'status': status.value
            }).eq('key_id', key_id).execute()
            
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"Error updating key status: {str(e)}")
            return False
    
    async def list_user_keys(
        self,
        user_id: str,
        status_filter: Optional[APIKeyStatus] = None,
        include_usage: bool = False
    ) -> List[Dict[str, Any]]:
        """List user's API keys."""
        try:
            query = self.supabase.table('api_keys').select('*').eq('user_id', user_id)
            
            if status_filter:
                query = query.eq('status', status_filter.value)
            
            result = query.execute()
            
            keys = []
            for key_data in result.data:
                key_info = {
                    'key_id': key_data['key_id'],
                    'name': key_data['name'],
                    'scope': key_data['scope'],
                    'status': key_data['status'],
                    'created_at': key_data['created_at'],
                    'expires_at': key_data['expires_at'],
                    'last_used_at': key_data['last_used_at'],
                    'usage_count': key_data.get('usage_count', 0),
                    'rate_limit_per_hour': key_data['rate_limit_per_hour'],
                    'permissions': list(self._get_scope_permissions(APIKeyScope(key_data['scope'])))
                }
                
                # Add usage statistics if requested
                if include_usage:
                    usage_stats = await self._get_key_usage_stats(key_data['key_id'])
                    key_info['usage_stats'] = usage_stats
                
                keys.append(key_info)
            
            return keys
            
        except Exception as e:
            logger.error(f"Error listing user keys: {str(e)}")
            return []
    
    async def _get_key_usage_stats(self, key_id: str) -> Dict[str, Any]:
        """Get usage statistics for API key."""
        try:
            # Get usage data from last 30 days
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
            
            result = self.supabase.table('api_key_usage').select('*').eq('key_id', key_id).gte('timestamp', thirty_days_ago.isoformat()).execute()
            
            usage_data = result.data
            
            # Calculate statistics
            total_requests = len(usage_data)
            successful_requests = len([u for u in usage_data if 200 <= u['response_status'] < 300])
            error_requests = len([u for u in usage_data if u['response_status'] >= 400])
            
            avg_response_time = 0
            if usage_data:
                avg_response_time = sum(u['response_time_ms'] for u in usage_data) / len(usage_data)
            
            # Group by endpoint
            endpoint_usage = {}
            for usage in usage_data:
                endpoint = usage['endpoint']
                if endpoint not in endpoint_usage:
                    endpoint_usage[endpoint] = 0
                endpoint_usage[endpoint] += 1
            
            return {
                'total_requests_30d': total_requests,
                'successful_requests_30d': successful_requests,
                'error_requests_30d': error_requests,
                'success_rate': (successful_requests / total_requests * 100) if total_requests > 0 else 0,
                'avg_response_time_ms': round(avg_response_time, 2),
                'endpoint_usage': endpoint_usage
            }
            
        except Exception as e:
            logger.error(f"Error getting usage stats: {str(e)}")
            return {}
    
    async def check_expiring_keys(self, warning_days: int = None) -> List[Dict[str, Any]]:
        """Check for API keys that are expiring soon."""
        try:
            warning_days = warning_days or self.config.rotation_warning_days
            warning_date = datetime.now(timezone.utc) + timedelta(days=warning_days)
            
            result = self.supabase.table('api_keys').select('*').eq('status', APIKeyStatus.ACTIVE.value).lte('expires_at', warning_date.isoformat()).execute()
            
            expiring_keys = []
            for key_data in result.data:
                if key_data['expires_at']:
                    expires_at = datetime.fromisoformat(key_data['expires_at'])
                    days_until_expiry = (expires_at - datetime.now(timezone.utc)).days
                    
                    expiring_keys.append({
                        'key_id': key_data['key_id'],
                        'user_id': key_data['user_id'],
                        'name': key_data['name'],
                        'expires_at': key_data['expires_at'],
                        'days_until_expiry': days_until_expiry
                    })
            
            return expiring_keys
            
        except Exception as e:
            logger.error(f"Error checking expiring keys: {str(e)}")
            return []

# Global service instance
api_key_service = APIKeyService()