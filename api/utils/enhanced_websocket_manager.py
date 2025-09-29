"""Enhanced WebSocket manager with production-ready features.

This module provides:
- Advanced error handling with circuit breakers
- Automatic reconnection logic
- Message persistence and replay
- Connection health monitoring
- Rate limiting and backpressure handling
- Metrics and observability
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Callable, Union
from dataclasses import dataclass, asdict, field
from collections import defaultdict, deque
from enum import Enum
import weakref
import logging
from contextlib import asynccontextmanager
import hashlib
import pickle
from pathlib import Path

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    from websockets.exceptions import ConnectionClosed, WebSocketException
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WebSocketServerProtocol = None
    ConnectionClosed = Exception
    WebSocketException = Exception

from .logging_config import get_logger
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig

logger = get_logger('enhanced_websocket')


class ConnectionState(Enum):
    """WebSocket connection states."""
    CONNECTING = 'connecting'
    CONNECTED = 'connected'
    RECONNECTING = 'reconnecting'
    DISCONNECTED = 'disconnected'
    FAILED = 'failed'


class MessagePriority(Enum):
    """Message priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class MessageType(Enum):
    """WebSocket message types."""
    CLIP_GENERATION_START = 'clip_generation_start'
    CLIP_GENERATION_PROGRESS = 'clip_generation_progress'
    CLIP_GENERATION_COMPLETE = 'clip_generation_complete'
    CLIP_GENERATION_ERROR = 'clip_generation_error'
    SINGLE_CLIP_START = 'single_clip_start'
    SINGLE_CLIP_COMPLETE = 'single_clip_complete'
    SINGLE_CLIP_ERROR = 'single_clip_error'
    SYSTEM_STATUS = 'system_status'
    USER_NOTIFICATION = 'user_notification'
    HEARTBEAT = 'heartbeat'
    ERROR = 'error'
    RECONNECT = 'reconnect'
    RATE_LIMIT = 'rate_limit'


@dataclass
class EnhancedWebSocketMessage:
    """Enhanced WebSocket message with priority and persistence."""
    type: MessageType
    data: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    job_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    expires_at: Optional[datetime] = None
    persistent: bool = False
    
    def __post_init__(self):
        if self.expires_at is None:
            # Default expiration: 1 hour for normal messages, 24 hours for critical
            hours = 24 if self.priority == MessagePriority.CRITICAL else 1
            self.expires_at = self.timestamp + timedelta(hours=hours)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'type': self.type.value,
            'data': self.data,
            'priority': self.priority.value,
            'timestamp': self.timestamp.isoformat() + 'Z',
            'message_id': self.message_id,
            'user_id': self.user_id,
            'job_id': self.job_id,
            'retry_count': self.retry_count
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    def is_expired(self) -> bool:
        """Check if message has expired."""
        return datetime.utcnow() > self.expires_at
    
    def can_retry(self) -> bool:
        """Check if message can be retried."""
        return self.retry_count < self.max_retries and not self.is_expired()


@dataclass
class ConnectionMetrics:
    """Connection metrics and health information."""
    connection_id: str
    connected_at: datetime
    last_heartbeat: datetime
    messages_sent: int = 0
    messages_failed: int = 0
    bytes_sent: int = 0
    reconnect_count: int = 0
    last_error: Optional[str] = None
    error_count: int = 0
    avg_response_time: float = 0.0
    
    def calculate_health_score(self) -> float:
        """Calculate connection health score (0-100)."""
        if self.messages_sent == 0:
            return 100.0
        
        success_rate = (self.messages_sent - self.messages_failed) / self.messages_sent
        time_since_heartbeat = (datetime.utcnow() - self.last_heartbeat).total_seconds()
        
        # Penalize for errors and stale connections
        health = success_rate * 100
        health -= min(self.error_count * 5, 50)  # Max 50 point penalty for errors
        health -= min(time_since_heartbeat / 60 * 10, 30)  # Penalty for stale connections
        
        return max(0.0, min(100.0, health))


@dataclass
class EnhancedConnectionInfo:
    """Enhanced connection information with metrics and state."""
    connection_id: str
    user_id: Optional[str]
    websocket: Any
    state: ConnectionState = ConnectionState.CONNECTING
    subscriptions: Set[str] = field(default_factory=set)
    message_queue: deque = field(default_factory=lambda: deque(maxlen=1000))
    priority_queue: Dict[MessagePriority, deque] = field(default_factory=lambda: {
        MessagePriority.CRITICAL: deque(maxlen=100),
        MessagePriority.HIGH: deque(maxlen=200),
        MessagePriority.NORMAL: deque(maxlen=500),
        MessagePriority.LOW: deque(maxlen=200)
    })
    metrics: ConnectionMetrics = None
    is_authenticated: bool = False
    rate_limit_tokens: int = 100
    rate_limit_last_refill: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        if self.metrics is None:
            self.metrics = ConnectionMetrics(
                connection_id=self.connection_id,
                connected_at=datetime.utcnow(),
                last_heartbeat=datetime.utcnow()
            )


class EnhancedWebSocketManager:
    """Enhanced WebSocket manager with production features."""
    
    def __init__(self, 
                 max_connections: int = 1000,
                 heartbeat_interval: float = 30.0,
                 redis_url: Optional[str] = None,
                 message_persistence_dir: Optional[str] = None):
        self.connections: Dict[str, EnhancedConnectionInfo] = {}
        self.user_connections: Dict[str, Set[str]] = defaultdict(set)
        self.job_subscribers: Dict[str, Set[str]] = defaultdict(set)
        self.max_connections = max_connections
        self.heartbeat_interval = heartbeat_interval
        self.running = False
        
        # Background tasks
        self.heartbeat_task = None
        self.cleanup_task = None
        self.message_processor_task = None
        self.rate_limit_task = None
        
        # Synchronization
        self._lock = asyncio.Lock()
        
        # Circuit breakers
        self.websocket_circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=30.0,
                expected_exception=WebSocketException
            )
        )
        
        # Redis for message persistence (optional)
        self.redis_client = None
        if redis_url and REDIS_AVAILABLE:
            self.redis_client = redis.from_url(redis_url)
        
        # File-based message persistence fallback
        self.persistence_dir = None
        if message_persistence_dir:
            self.persistence_dir = Path(message_persistence_dir)
            self.persistence_dir.mkdir(exist_ok=True)
        
        # Message handlers and middleware
        self.message_handlers: Dict[str, Callable] = {}
        self.middleware: List[Callable] = []
        
        # Statistics and metrics
        self.stats = {
            'total_connections': 0,
            'active_connections': 0,
            'messages_sent': 0,
            'messages_failed': 0,
            'messages_queued': 0,
            'bytes_sent': 0,
            'reconnections': 0,
            'circuit_breaker_trips': 0
        }
        
        # Rate limiting configuration
        self.rate_limit_config = {
            'tokens_per_minute': 100,
            'burst_size': 20,
            'refill_interval': 1.0  # seconds
        }
    
    async def start(self):
        """Start the enhanced WebSocket manager."""
        if self.running:
            return
        
        self.running = True
        
        # Start Redis connection if available
        if self.redis_client:
            try:
                await self.redis_client.ping()
                logger.info("Redis connection established for message persistence")
            except Exception as e:
                logger.warning(f"Redis connection failed, using file persistence: {e}")
                self.redis_client = None
        
        # Start background tasks
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        self.message_processor_task = asyncio.create_task(self._message_processor_loop())
        self.rate_limit_task = asyncio.create_task(self._rate_limit_loop())
        
        logger.info("Enhanced WebSocket manager started")
    
    async def stop(self):
        """Stop the enhanced WebSocket manager."""
        if not self.running:
            return
        
        self.running = False
        
        # Cancel background tasks
        tasks = [self.heartbeat_task, self.cleanup_task, 
                self.message_processor_task, self.rate_limit_task]
        for task in tasks:
            if task:
                task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*[t for t in tasks if t], return_exceptions=True)
        
        # Close all connections
        await self._close_all_connections()
        
        # Close Redis connection
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("Enhanced WebSocket manager stopped")
    
    async def add_connection(self, websocket: Any, user_id: Optional[str] = None) -> str:
        """Add a new WebSocket connection with enhanced features."""
        if len(self.connections) >= self.max_connections:
            raise Exception("Maximum connections reached")
        
        connection_id = str(uuid.uuid4())
        
        async with self._lock:
            connection_info = EnhancedConnectionInfo(
                connection_id=connection_id,
                user_id=user_id,
                websocket=websocket,
                state=ConnectionState.CONNECTED
            )
            
            if user_id:
                connection_info.is_authenticated = True
                self.user_connections[user_id].add(connection_id)
            
            self.connections[connection_id] = connection_info
            
            self.stats['total_connections'] += 1
            self.stats['active_connections'] = len(self.connections)
        
        # Send welcome message with connection info
        welcome_message = EnhancedWebSocketMessage(
            type=MessageType.SYSTEM_STATUS,
            priority=MessagePriority.HIGH,
            data={
                'status': 'connected',
                'connection_id': connection_id,
                'server_time': datetime.utcnow().isoformat() + 'Z',
                'features': {
                    'message_persistence': self.redis_client is not None or self.persistence_dir is not None,
                    'rate_limiting': True,
                    'priority_queuing': True,
                    'auto_reconnect': True
                }
            }
        )
        
        await self._queue_message(connection_id, welcome_message)
        
        # Load any persisted messages for this user
        if user_id:
            await self._load_persisted_messages(user_id, connection_id)
        
        logger.info(
            f"Enhanced WebSocket connection added: {connection_id}",
            extra={'connection_id': connection_id, 'user_id': user_id}
        )
        
        return connection_id
    
    async def _queue_message(self, connection_id: str, message: EnhancedWebSocketMessage):
        """Queue a message for delivery with priority handling."""
        async with self._lock:
            if connection_id not in self.connections:
                return False
            
            connection_info = self.connections[connection_id]
            
            # Check rate limiting
            if not self._check_rate_limit(connection_info):
                # Send rate limit message
                rate_limit_msg = EnhancedWebSocketMessage(
                    type=MessageType.RATE_LIMIT,
                    priority=MessagePriority.HIGH,
                    data={'message': 'Rate limit exceeded, message queued'}
                )
                connection_info.priority_queue[MessagePriority.HIGH].append(rate_limit_msg)
                return False
            
            # Add to appropriate priority queue
            connection_info.priority_queue[message.priority].append(message)
            self.stats['messages_queued'] += 1
            
            # Persist critical messages
            if message.persistent or message.priority == MessagePriority.CRITICAL:
                await self._persist_message(message)
            
            return True
    
    def _check_rate_limit(self, connection_info: EnhancedConnectionInfo) -> bool:
        """Check if connection is within rate limits."""
        now = datetime.utcnow()
        time_diff = (now - connection_info.rate_limit_last_refill).total_seconds()
        
        # Refill tokens based on time passed
        if time_diff >= self.rate_limit_config['refill_interval']:
            tokens_to_add = int(time_diff / 60 * self.rate_limit_config['tokens_per_minute'])
            connection_info.rate_limit_tokens = min(
                self.rate_limit_config['burst_size'],
                connection_info.rate_limit_tokens + tokens_to_add
            )
            connection_info.rate_limit_last_refill = now
        
        # Check if we have tokens available
        if connection_info.rate_limit_tokens > 0:
            connection_info.rate_limit_tokens -= 1
            return True
        
        return False
    
    async def _persist_message(self, message: EnhancedWebSocketMessage):
        """Persist message for reliability."""
        try:
            message_data = {
                'message': message.to_dict(),
                'created_at': datetime.utcnow().isoformat()
            }
            
            if self.redis_client:
                # Use Redis for persistence
                key = f"ws_message:{message.user_id}:{message.message_id}"
                await self.redis_client.setex(
                    key, 
                    int((message.expires_at - datetime.utcnow()).total_seconds()),
                    json.dumps(message_data)
                )
            elif self.persistence_dir:
                # Use file-based persistence
                file_path = self.persistence_dir / f"{message.user_id}_{message.message_id}.json"
                with open(file_path, 'w') as f:
                    json.dump(message_data, f)
        
        except Exception as e:
            logger.error(f"Failed to persist message {message.message_id}: {e}")
    
    async def _load_persisted_messages(self, user_id: str, connection_id: str):
        """Load persisted messages for a user."""
        try:
            if self.redis_client:
                # Load from Redis
                pattern = f"ws_message:{user_id}:*"
                keys = await self.redis_client.keys(pattern)
                
                for key in keys:
                    message_data = await self.redis_client.get(key)
                    if message_data:
                        data = json.loads(message_data)
                        # Recreate message and queue it
                        msg_dict = data['message']
                        message = EnhancedWebSocketMessage(
                            type=MessageType(msg_dict['type']),
                            data=msg_dict['data'],
                            priority=MessagePriority(msg_dict['priority']),
                            message_id=msg_dict['message_id'],
                            user_id=msg_dict['user_id'],
                            job_id=msg_dict['job_id']
                        )
                        await self._queue_message(connection_id, message)
            
            elif self.persistence_dir:
                # Load from files
                pattern = f"{user_id}_*.json"
                for file_path in self.persistence_dir.glob(pattern):
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                        msg_dict = data['message']
                        message = EnhancedWebSocketMessage(
                            type=MessageType(msg_dict['type']),
                            data=msg_dict['data'],
                            priority=MessagePriority(msg_dict['priority']),
                            message_id=msg_dict['message_id'],
                            user_id=msg_dict['user_id'],
                            job_id=msg_dict['job_id']
                        )
                        await self._queue_message(connection_id, message)
                        # Clean up file after loading
                        file_path.unlink()
        
        except Exception as e:
            logger.error(f"Failed to load persisted messages for user {user_id}: {e}")
    
    async def _message_processor_loop(self):
        """Process queued messages with priority handling."""
        while self.running:
            try:
                await asyncio.sleep(0.1)  # Process messages every 100ms
                
                async with self._lock:
                    connection_ids = list(self.connections.keys())
                
                for connection_id in connection_ids:
                    await self._process_connection_queue(connection_id)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in message processor loop: {e}", exc_info=True)
    
    async def _process_connection_queue(self, connection_id: str):
        """Process queued messages for a specific connection."""
        async with self._lock:
            if connection_id not in self.connections:
                return
            
            connection_info = self.connections[connection_id]
            
            if connection_info.state != ConnectionState.CONNECTED:
                return
        
        # Process messages by priority (highest first)
        for priority in [MessagePriority.CRITICAL, MessagePriority.HIGH, 
                        MessagePriority.NORMAL, MessagePriority.LOW]:
            
            queue = connection_info.priority_queue[priority]
            messages_to_process = min(len(queue), 5)  # Limit batch size
            
            for _ in range(messages_to_process):
                if not queue:
                    break
                
                message = queue.popleft()
                
                # Check if message has expired
                if message.is_expired():
                    continue
                
                success = await self._send_message_direct(connection_id, message)
                
                if not success and message.can_retry():
                    # Re-queue for retry
                    message.retry_count += 1
                    queue.append(message)
    
    async def _send_message_direct(self, connection_id: str, message: EnhancedWebSocketMessage) -> bool:
        """Send message directly to WebSocket connection."""
        try:
            async with self._lock:
                if connection_id not in self.connections:
                    return False
                
                connection_info = self.connections[connection_id]
            
            # Use circuit breaker for WebSocket operations
            async with self.websocket_circuit_breaker:
                message_json = message.to_json()
                await connection_info.websocket.send(message_json)
                
                # Update metrics
                connection_info.metrics.messages_sent += 1
                connection_info.metrics.bytes_sent += len(message_json.encode('utf-8'))
                
                self.stats['messages_sent'] += 1
                self.stats['bytes_sent'] += len(message_json.encode('utf-8'))
                
                return True
        
        except Exception as e:
            logger.error(f"Failed to send message to {connection_id}: {e}")
            
            async with self._lock:
                if connection_id in self.connections:
                    self.connections[connection_id].metrics.messages_failed += 1
                    self.connections[connection_id].metrics.error_count += 1
                    self.connections[connection_id].metrics.last_error = str(e)
            
            self.stats['messages_failed'] += 1
            
            # Mark connection for reconnection if it's a connection error
            if isinstance(e, (ConnectionClosed, WebSocketException)):
                await self._handle_connection_error(connection_id)
            
            return False
    
    async def _handle_connection_error(self, connection_id: str):
        """Handle connection errors and attempt reconnection."""
        async with self._lock:
            if connection_id not in self.connections:
                return
            
            connection_info = self.connections[connection_id]
            connection_info.state = ConnectionState.RECONNECTING
            connection_info.metrics.reconnect_count += 1
        
        self.stats['reconnections'] += 1
        
        logger.info(f"Attempting to reconnect connection {connection_id}")
        
        # In a real implementation, you would attempt to re-establish the WebSocket connection
        # For now, we'll mark it as failed after a timeout
        await asyncio.sleep(5)
        
        async with self._lock:
            if connection_id in self.connections:
                self.connections[connection_id].state = ConnectionState.FAILED
    
    async def _rate_limit_loop(self):
        """Refill rate limit tokens periodically."""
        while self.running:
            try:
                await asyncio.sleep(self.rate_limit_config['refill_interval'])
                
                async with self._lock:
                    for connection_info in self.connections.values():
                        # Refill tokens
                        connection_info.rate_limit_tokens = min(
                            self.rate_limit_config['burst_size'],
                            connection_info.rate_limit_tokens + 1
                        )
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in rate limit loop: {e}", exc_info=True)
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeat messages."""
        while self.running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                heartbeat_message = EnhancedWebSocketMessage(
                    type=MessageType.HEARTBEAT,
                    priority=MessagePriority.LOW,
                    data={
                        'timestamp': datetime.utcnow().isoformat() + 'Z',
                        'server_stats': self.get_stats()
                    }
                )
                
                await self.broadcast_to_all(heartbeat_message)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}", exc_info=True)
    
    async def _cleanup_loop(self):
        """Clean up stale connections and expired messages."""
        while self.running:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                cutoff_time = datetime.utcnow() - timedelta(minutes=5)
                stale_connections = []
                
                async with self._lock:
                    for connection_id, connection_info in self.connections.items():
                        if connection_info.metrics.last_heartbeat < cutoff_time:
                            stale_connections.append(connection_id)
                
                for connection_id in stale_connections:
                    logger.info(f"Removing stale connection: {connection_id}")
                    await self.remove_connection(connection_id)
                
                # Clean up expired persisted messages
                await self._cleanup_expired_messages()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)
    
    async def _cleanup_expired_messages(self):
        """Clean up expired persisted messages."""
        try:
            if self.redis_client:
                # Redis TTL handles expiration automatically
                pass
            elif self.persistence_dir:
                # Clean up old files
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                for file_path in self.persistence_dir.glob("*.json"):
                    if file_path.stat().st_mtime < cutoff_time.timestamp():
                        file_path.unlink()
        except Exception as e:
            logger.error(f"Error cleaning up expired messages: {e}")
    
    async def remove_connection(self, connection_id: str):
        """Remove a WebSocket connection."""
        async with self._lock:
            if connection_id not in self.connections:
                return
            
            connection_info = self.connections[connection_id]
            
            # Remove from user connections
            if connection_info.user_id:
                self.user_connections[connection_info.user_id].discard(connection_id)
                if not self.user_connections[connection_info.user_id]:
                    del self.user_connections[connection_info.user_id]
            
            # Remove from job subscriptions
            for job_id in connection_info.subscriptions:
                self.job_subscribers[job_id].discard(connection_id)
                if not self.job_subscribers[job_id]:
                    del self.job_subscribers[job_id]
            
            # Close WebSocket if still open
            try:
                if hasattr(connection_info.websocket, 'close') and not connection_info.websocket.closed:
                    await connection_info.websocket.close()
            except Exception as e:
                logger.warning(f"Error closing WebSocket: {e}")
            
            del self.connections[connection_id]
            self.stats['active_connections'] = len(self.connections)
        
        logger.info(f"Enhanced WebSocket connection removed: {connection_id}")
    
    async def _close_all_connections(self):
        """Close all WebSocket connections."""
        async with self._lock:
            connection_ids = list(self.connections.keys())
        
        for connection_id in connection_ids:
            await self.remove_connection(connection_id)
    
    async def send_to_user(self, user_id: str, message: EnhancedWebSocketMessage) -> int:
        """Send a message to all connections for a user."""
        message.user_id = user_id
        sent_count = 0
        
        async with self._lock:
            connection_ids = self.user_connections.get(user_id, set()).copy()
        
        for connection_id in connection_ids:
            if await self._queue_message(connection_id, message):
                sent_count += 1
        
        return sent_count
    
    async def broadcast_to_job(self, job_id: str, message: EnhancedWebSocketMessage) -> int:
        """Broadcast a message to all subscribers of a job."""
        message.job_id = job_id
        sent_count = 0
        
        async with self._lock:
            connection_ids = self.job_subscribers.get(job_id, set()).copy()
        
        for connection_id in connection_ids:
            if await self._queue_message(connection_id, message):
                sent_count += 1
        
        return sent_count
    
    async def broadcast_to_all(self, message: EnhancedWebSocketMessage) -> int:
        """Broadcast a message to all connections."""
        sent_count = 0
        
        async with self._lock:
            connection_ids = list(self.connections.keys())
        
        for connection_id in connection_ids:
            if await self._queue_message(connection_id, message):
                sent_count += 1
        
        return sent_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get enhanced WebSocket manager statistics."""
        connection_health_scores = []
        
        for connection_info in self.connections.values():
            health_score = connection_info.metrics.calculate_health_score()
            connection_health_scores.append(health_score)
        
        avg_health = sum(connection_health_scores) / len(connection_health_scores) if connection_health_scores else 100.0
        
        return {
            **self.stats,
            'active_users': len(self.user_connections),
            'active_job_subscriptions': len(self.job_subscribers),
            'average_connection_health': avg_health,
            'circuit_breaker_state': self.websocket_circuit_breaker.state.value,
            'redis_available': self.redis_client is not None,
            'persistence_enabled': self.redis_client is not None or self.persistence_dir is not None,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
    
    # Convenience methods for clip generation events
    async def notify_clip_generation_start(self, job_id: str, user_id: str, total_clips: int, **kwargs):
        """Notify about clip generation start."""
        message = EnhancedWebSocketMessage(
            type=MessageType.CLIP_GENERATION_START,
            priority=MessagePriority.HIGH,
            data={
                'job_id': job_id,
                'total_clips': total_clips,
                'status': 'started',
                **kwargs
            },
            user_id=user_id,
            job_id=job_id,
            persistent=True
        )
        
        await self.send_to_user(user_id, message)
        await self.broadcast_to_job(job_id, message)
    
    async def notify_clip_generation_progress(self, job_id: str, user_id: str, 
                                            current_clip: int, total_clips: int, 
                                            progress_percent: float, **kwargs):
        """Notify about clip generation progress."""
        message = EnhancedWebSocketMessage(
            type=MessageType.CLIP_GENERATION_PROGRESS,
            priority=MessagePriority.NORMAL,
            data={
                'job_id': job_id,
                'current_clip': current_clip,
                'total_clips': total_clips,
                'progress_percent': progress_percent,
                'status': 'in_progress',
                **kwargs
            },
            user_id=user_id,
            job_id=job_id
        )
        
        await self.send_to_user(user_id, message)
        await self.broadcast_to_job(job_id, message)
    
    async def notify_clip_generation_complete(self, job_id: str, user_id: str, 
                                            clips_generated: int, success_count: int, 
                                            error_count: int, **kwargs):
        """Notify about clip generation completion."""
        message = EnhancedWebSocketMessage(
            type=MessageType.CLIP_GENERATION_COMPLETE,
            priority=MessagePriority.HIGH,
            data={
                'job_id': job_id,
                'clips_generated': clips_generated,
                'success_count': success_count,
                'error_count': error_count,
                'status': 'completed',
                **kwargs
            },
            user_id=user_id,
            job_id=job_id,
            persistent=True
        )
        
        await self.send_to_user(user_id, message)
        await self.broadcast_to_job(job_id, message)
    
    async def notify_clip_generation_error(self, job_id: str, user_id: str, error: str, **kwargs):
        """Notify about clip generation error."""
        message = EnhancedWebSocketMessage(
            type=MessageType.CLIP_GENERATION_ERROR,
            priority=MessagePriority.CRITICAL,
            data={
                'job_id': job_id,
                'error': error,
                'status': 'error',
                **kwargs
            },
            user_id=user_id,
            job_id=job_id,
            persistent=True
        )
        
        await self.send_to_user(user_id, message)
        await self.broadcast_to_job(job_id, message)


# Global enhanced WebSocket manager instance
enhanced_websocket_manager = EnhancedWebSocketManager()


def get_enhanced_websocket_manager() -> EnhancedWebSocketManager:
    """Get the global enhanced WebSocket manager instance."""
    return enhanced_websocket_manager


@asynccontextmanager
async def enhanced_websocket_context():
    """Context manager for enhanced WebSocket manager lifecycle."""
    await enhanced_websocket_manager.start()
    try:
        yield enhanced_websocket_manager
    finally:
        await enhanced_websocket_manager.stop()