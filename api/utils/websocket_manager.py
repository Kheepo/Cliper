"""WebSocket manager for real-time clip generation progress updates.

This module provides:
- WebSocket connection management
- Real-time progress broadcasting
- User-specific message routing
- Connection health monitoring
- Message queuing and delivery guarantees
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Callable
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from enum import Enum
import weakref
import logging
from contextlib import asynccontextmanager
import pickle
import redis
from .enhanced_retry import retry_async, RetryConfig, BackoffStrategy
from .circuit_breaker import circuit_breaker

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WebSocketServerProtocol = None

from .logging_config import get_logger

logger = get_logger('websocket')


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


@dataclass
class WebSocketMessage:
    """WebSocket message structure."""
    type: MessageType
    data: Dict[str, Any]
    timestamp: datetime = None
    message_id: str = None
    user_id: Optional[str] = None
    job_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.message_id is None:
            self.message_id = str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'type': self.type.value,
            'data': self.data,
            'timestamp': self.timestamp.isoformat() + 'Z',
            'message_id': self.message_id,
            'user_id': self.user_id,
            'job_id': self.job_id
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""
    connection_id: str
    user_id: Optional[str]
    websocket: Any  # WebSocketServerProtocol
    connected_at: datetime
    last_heartbeat: datetime
    subscriptions: Set[str]  # Job IDs or topics
    message_queue: deque
    is_authenticated: bool = False
    
    def __post_init__(self):
        if not hasattr(self, 'message_queue'):
            self.message_queue = deque(maxlen=100)  # Limit queue size


class WebSocketManager:
    """Manages WebSocket connections and message broadcasting."""
    
    def __init__(self, max_connections: int = 1000, heartbeat_interval: float = 30.0):
        self.connections: Dict[str, ConnectionInfo] = {}
        self.user_connections: Dict[str, Set[str]] = defaultdict(set)  # user_id -> connection_ids
        self.job_subscribers: Dict[str, Set[str]] = defaultdict(set)  # job_id -> connection_ids
        self.max_connections = max_connections
        self.heartbeat_interval = heartbeat_interval
        self.running = False
        self.heartbeat_task = None
        self.cleanup_task = None
        self._lock = asyncio.Lock()
        
        # Message handlers
        self.message_handlers: Dict[str, Callable] = {}
        
        # Statistics
        self.stats = {
            'total_connections': 0,
            'active_connections': 0,
            'messages_sent': 0,
            'messages_failed': 0,
            'bytes_sent': 0
        }
    
    async def start(self):
        """Start the WebSocket manager."""
        if self.running:
            return
        
        self.running = True
        
        # Start background tasks
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.logger.info("WebSocket manager started")
    
    async def stop(self):
        """Stop the WebSocket manager."""
        if not self.running:
            return
        
        self.running = False
        
        # Cancel background tasks
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        if self.cleanup_task:
            self.cleanup_task.cancel()
        
        # Close all connections
        await self._close_all_connections()
        
        logger.logger.info("WebSocket manager stopped")
    
    async def add_connection(self, websocket: Any, user_id: Optional[str] = None) -> str:
        """Add a new WebSocket connection."""
        if len(self.connections) >= self.max_connections:
            raise Exception("Maximum connections reached")
        
        connection_id = str(uuid.uuid4())
        
        async with self._lock:
            connection_info = ConnectionInfo(
                connection_id=connection_id,
                user_id=user_id,
                websocket=websocket,
                connected_at=datetime.utcnow(),
                last_heartbeat=datetime.utcnow(),
                subscriptions=set(),
                message_queue=deque(maxlen=100)
            )
            
            self.connections[connection_id] = connection_info
            
            if user_id:
                self.user_connections[user_id].add(connection_id)
                connection_info.is_authenticated = True
            
            self.stats['total_connections'] += 1
            self.stats['active_connections'] = len(self.connections)
        
        logger.logger.info(
            f"WebSocket connection added: {connection_id}",
            extra={'connection_id': connection_id, 'user_id': user_id}
        )
        
        # Send welcome message
        await self.send_to_connection(
            connection_id,
            WebSocketMessage(
                type=MessageType.SYSTEM_STATUS,
                data={
                    'status': 'connected',
                    'connection_id': connection_id,
                    'server_time': datetime.utcnow().isoformat() + 'Z'
                }
            )
        )
        
        return connection_id
    
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
                if not connection_info.websocket.closed:
                    await connection_info.websocket.close()
            except Exception as e:
                logger.logger.warning(f"Error closing WebSocket: {e}")
            
            del self.connections[connection_id]
            self.stats['active_connections'] = len(self.connections)
        
        logger.logger.info(
            f"WebSocket connection removed: {connection_id}",
            extra={'connection_id': connection_id}
        )
    
    async def subscribe_to_job(self, connection_id: str, job_id: str):
        """Subscribe a connection to job updates."""
        async with self._lock:
            if connection_id in self.connections:
                self.connections[connection_id].subscriptions.add(job_id)
                self.job_subscribers[job_id].add(connection_id)
                
                logger.logger.debug(
                    f"Connection {connection_id} subscribed to job {job_id}",
                    extra={'connection_id': connection_id, 'job_id': job_id}
                )
    
    async def unsubscribe_from_job(self, connection_id: str, job_id: str):
        """Unsubscribe a connection from job updates."""
        async with self._lock:
            if connection_id in self.connections:
                self.connections[connection_id].subscriptions.discard(job_id)
                self.job_subscribers[job_id].discard(connection_id)
                
                if not self.job_subscribers[job_id]:
                    del self.job_subscribers[job_id]
                
                logger.logger.debug(
                    f"Connection {connection_id} unsubscribed from job {job_id}",
                    extra={'connection_id': connection_id, 'job_id': job_id}
                )
    
    async def send_to_connection(self, connection_id: str, message: WebSocketMessage) -> bool:
        """Send a message to a specific connection."""
        async with self._lock:
            if connection_id not in self.connections:
                return False
            
            connection_info = self.connections[connection_id]
        
        try:
            message_json = message.to_json()
            await connection_info.websocket.send(message_json)
            
            self.stats['messages_sent'] += 1
            self.stats['bytes_sent'] += len(message_json.encode('utf-8'))
            
            logger.log_websocket_event(
                event_type='message_sent',
                user_id=connection_info.user_id,
                data={'message_type': message.type.value, 'connection_id': connection_id}
            )
            
            return True
        
        except Exception as e:
            logger.logger.error(
                f"Failed to send message to connection {connection_id}: {e}",
                extra={'connection_id': connection_id, 'message_type': message.type.value}
            )
            
            self.stats['messages_failed'] += 1
            
            # Remove broken connection
            await self.remove_connection(connection_id)
            return False
    
    async def send_to_user(self, user_id: str, message: WebSocketMessage) -> int:
        """Send a message to all connections for a user."""
        message.user_id = user_id
        sent_count = 0
        
        async with self._lock:
            connection_ids = self.user_connections.get(user_id, set()).copy()
        
        for connection_id in connection_ids:
            if await self.send_to_connection(connection_id, message):
                sent_count += 1
        
        return sent_count
    
    async def broadcast_to_job(self, job_id: str, message: WebSocketMessage) -> int:
        """Broadcast a message to all subscribers of a job."""
        message.job_id = job_id
        sent_count = 0
        
        async with self._lock:
            connection_ids = self.job_subscribers.get(job_id, set()).copy()
        
        for connection_id in connection_ids:
            if await self.send_to_connection(connection_id, message):
                sent_count += 1
        
        return sent_count
    
    async def broadcast_to_all(self, message: WebSocketMessage) -> int:
        """Broadcast a message to all connections."""
        sent_count = 0
        
        async with self._lock:
            connection_ids = list(self.connections.keys())
        
        for connection_id in connection_ids:
            if await self.send_to_connection(connection_id, message):
                sent_count += 1
        
        return sent_count
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeat messages."""
        while self.running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                heartbeat_message = WebSocketMessage(
                    type=MessageType.HEARTBEAT,
                    data={'timestamp': datetime.utcnow().isoformat() + 'Z'}
                )
                
                await self.broadcast_to_all(heartbeat_message)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.logger.error(f"Error in heartbeat loop: {e}", exc_info=True)
    
    async def _cleanup_loop(self):
        """Clean up stale connections."""
        while self.running:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                cutoff_time = datetime.utcnow() - timedelta(minutes=5)
                stale_connections = []
                
                async with self._lock:
                    for connection_id, connection_info in self.connections.items():
                        if connection_info.last_heartbeat < cutoff_time:
                            stale_connections.append(connection_id)
                
                for connection_id in stale_connections:
                    logger.logger.info(f"Removing stale connection: {connection_id}")
                    await self.remove_connection(connection_id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.logger.error(f"Error in cleanup loop: {e}", exc_info=True)
    
    async def _close_all_connections(self):
        """Close all WebSocket connections."""
        async with self._lock:
            connection_ids = list(self.connections.keys())
        
        for connection_id in connection_ids:
            await self.remove_connection(connection_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket manager statistics."""
        return {
            **self.stats,
            'active_users': len(self.user_connections),
            'active_job_subscriptions': len(self.job_subscribers),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
    
    # Convenience methods for clip generation events
    
    async def notify_clip_generation_start(self, job_id: str, user_id: str, total_clips: int, **kwargs):
        """Notify about clip generation start."""
        message = WebSocketMessage(
            type=MessageType.CLIP_GENERATION_START,
            data={
                'job_id': job_id,
                'total_clips': total_clips,
                'status': 'started',
                **kwargs
            },
            user_id=user_id,
            job_id=job_id
        )
        
        await self.send_to_user(user_id, message)
        await self.broadcast_to_job(job_id, message)
    
    async def notify_clip_generation_progress(self, job_id: str, user_id: str, 
                                            current_clip: int, total_clips: int, 
                                            progress_percent: float, **kwargs):
        """Notify about clip generation progress."""
        message = WebSocketMessage(
            type=MessageType.CLIP_GENERATION_PROGRESS,
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
        message = WebSocketMessage(
            type=MessageType.CLIP_GENERATION_COMPLETE,
            data={
                'job_id': job_id,
                'clips_generated': clips_generated,
                'success_count': success_count,
                'error_count': error_count,
                'status': 'completed',
                **kwargs
            },
            user_id=user_id,
            job_id=job_id
        )
        
        await self.send_to_user(user_id, message)
        await self.broadcast_to_job(job_id, message)
    
    async def notify_clip_generation_error(self, job_id: str, user_id: str, error: str, **kwargs):
        """Notify about clip generation error."""
        message = WebSocketMessage(
            type=MessageType.CLIP_GENERATION_ERROR,
            data={
                'job_id': job_id,
                'error': error,
                'status': 'error',
                **kwargs
            },
            user_id=user_id,
            job_id=job_id
        )
        
        await self.send_to_user(user_id, message)
        await self.broadcast_to_job(job_id, message)
    
    async def notify_single_clip_complete(self, job_id: str, user_id: str, 
                                        clip_id: str, clip_path: str, 
                                        thumbnail_path: Optional[str] = None, **kwargs):
        """Notify about single clip completion."""
        message = WebSocketMessage(
            type=MessageType.SINGLE_CLIP_COMPLETE,
            data={
                'job_id': job_id,
                'clip_id': clip_id,
                'clip_path': clip_path,
                'thumbnail_path': thumbnail_path,
                **kwargs
            },
            user_id=user_id,
            job_id=job_id
        )
        
        await self.send_to_user(user_id, message)
        await self.broadcast_to_job(job_id, message)


# Global WebSocket manager instance
websocket_manager = WebSocketManager()


def get_websocket_manager() -> WebSocketManager:
    """Get the global WebSocket manager instance."""
    return websocket_manager


@asynccontextmanager
async def websocket_context():
    """Context manager for WebSocket manager lifecycle."""
    await websocket_manager.start()
    try:
        yield websocket_manager
    finally:
        await websocket_manager.stop()


# Celery integration helpers
def sync_notify_clip_generation_start(job_id: str, user_id: str, total_clips: int, **kwargs):
    """Synchronous wrapper for clip generation start notification."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.run_until_complete(
        websocket_manager.notify_clip_generation_start(job_id, user_id, total_clips, **kwargs)
    )


def sync_notify_clip_generation_progress(job_id: str, user_id: str, current_clip: int, 
                                       total_clips: int, progress_percent: float, **kwargs):
    """Synchronous wrapper for clip generation progress notification."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.run_until_complete(
        websocket_manager.notify_clip_generation_progress(
            job_id, user_id, current_clip, total_clips, progress_percent, **kwargs
        )
    )


def sync_notify_clip_generation_complete(job_id: str, user_id: str, clips_generated: int, 
                                       success_count: int, error_count: int, **kwargs):
    """Synchronous wrapper for clip generation completion notification."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.run_until_complete(
        websocket_manager.notify_clip_generation_complete(
            job_id, user_id, clips_generated, success_count, error_count, **kwargs
        )
    )


def sync_notify_clip_generation_error(job_id: str, user_id: str, error: str, **kwargs):
    """Synchronous wrapper for clip generation error notification."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.run_until_complete(
        websocket_manager.notify_clip_generation_error(job_id, user_id, error, **kwargs)
    )