"""WebSocket service for real-time progress tracking and status updates.

This module provides:
- Real-time progress broadcasting for video processing
- Client connection management
- Message queuing and delivery
- Connection health monitoring
- Scalable WebSocket handling
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

import websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed, WebSocketException

from api.services.redis_service import redis_service
from api.utils.retry import exponential_backoff_retry, FAST_RETRY

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """WebSocket message types."""
    PROGRESS_UPDATE = "progress_update"
    CLIP_UPDATE = "clip_update"
    STATUS_UPDATE = "status_update"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    SUBSCRIPTION = "subscription"
    UNSUBSCRIPTION = "unsubscription"


@dataclass
class WebSocketMessage:
    """WebSocket message structure."""
    type: MessageType
    data: Dict[str, Any]
    timestamp: float
    client_id: Optional[str] = None
    
    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps({
            'type': self.type.value,
            'data': self.data,
            'timestamp': self.timestamp,
            'client_id': self.client_id
        })


@dataclass
class ClientConnection:
    """Client connection information."""
    websocket: WebSocketServerProtocol
    client_id: str
    user_id: Optional[str]
    subscriptions: Set[str]
    connected_at: float
    last_heartbeat: float
    
    def is_alive(self) -> bool:
        """Check if connection is alive."""
        return (
            not self.websocket.closed and
            time.time() - self.last_heartbeat < 60  # 60 seconds timeout
        )


class WebSocketService:
    """WebSocket service for real-time communication."""
    
    def __init__(self):
        self.connections: Dict[str, ClientConnection] = {}
        self.subscriptions: Dict[str, Set[str]] = {}  # topic -> client_ids
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.running = False
        self.server = None
        
        # Configuration
        self.host = "0.0.0.0"
        self.port = 8001
        self.heartbeat_interval = 30  # seconds
        self.cleanup_interval = 60  # seconds
    
    async def start_server(self):
        """Start WebSocket server."""
        if self.running:
            logger.warning("WebSocket server already running")
            return
        
        try:
            self.server = await websockets.serve(
                self.handle_client,
                self.host,
                self.port,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            
            self.running = True
            
            # Start background tasks
            asyncio.create_task(self._message_processor())
            asyncio.create_task(self._heartbeat_monitor())
            asyncio.create_task(self._connection_cleanup())
            
            logger.info(f"WebSocket server started on {self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
            raise
    
    async def stop_server(self):
        """Stop WebSocket server."""
        if not self.running:
            return
        
        self.running = False
        
        # Close all connections
        for connection in list(self.connections.values()):
            try:
                await connection.websocket.close()
            except Exception:
                pass
        
        self.connections.clear()
        self.subscriptions.clear()
        
        # Stop server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        logger.info("WebSocket server stopped")
    
    async def handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """Handle new client connection."""
        client_id = f"client_{int(time.time() * 1000)}_{id(websocket)}"
        
        try:
            # Register connection
            connection = ClientConnection(
                websocket=websocket,
                client_id=client_id,
                user_id=None,
                subscriptions=set(),
                connected_at=time.time(),
                last_heartbeat=time.time()
            )
            
            self.connections[client_id] = connection
            
            logger.info(f"Client {client_id} connected from {websocket.remote_address}")
            
            # Send welcome message
            await self._send_to_client(
                client_id,
                WebSocketMessage(
                    type=MessageType.STATUS_UPDATE,
                    data={
                        'status': 'connected',
                        'client_id': client_id,
                        'server_time': time.time()
                    },
                    timestamp=time.time(),
                    client_id=client_id
                )
            )
            
            # Handle messages
            async for message in websocket:
                await self._handle_client_message(client_id, message)
                
        except ConnectionClosed:
            logger.info(f"Client {client_id} disconnected")
        except WebSocketException as e:
            logger.warning(f"WebSocket error for client {client_id}: {e}")
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
        finally:
            # Cleanup connection
            await self._cleanup_client(client_id)
    
    async def _handle_client_message(self, client_id: str, message: str):
        """Handle message from client."""
        try:
            data = json.loads(message)
            message_type = MessageType(data.get('type'))
            
            connection = self.connections.get(client_id)
            if not connection:
                return
            
            # Update heartbeat
            connection.last_heartbeat = time.time()
            
            if message_type == MessageType.HEARTBEAT:
                await self._handle_heartbeat(client_id, data)
            elif message_type == MessageType.SUBSCRIPTION:
                await self._handle_subscription(client_id, data)
            elif message_type == MessageType.UNSUBSCRIPTION:
                await self._handle_unsubscription(client_id, data)
            else:
                logger.warning(f"Unknown message type from {client_id}: {message_type}")
                
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Invalid message from {client_id}: {e}")
        except Exception as e:
            logger.error(f"Error handling message from {client_id}: {e}")
    
    async def _handle_heartbeat(self, client_id: str, data: Dict[str, Any]):
        """Handle heartbeat message."""
        await self._send_to_client(
            client_id,
            WebSocketMessage(
                type=MessageType.HEARTBEAT,
                data={'status': 'alive', 'server_time': time.time()},
                timestamp=time.time(),
                client_id=client_id
            )
        )
    
    async def _handle_subscription(self, client_id: str, data: Dict[str, Any]):
        """Handle subscription request."""
        topics = data.get('topics', [])
        user_id = data.get('user_id')
        
        connection = self.connections.get(client_id)
        if not connection:
            return
        
        # Update user ID
        if user_id:
            connection.user_id = user_id
        
        # Add subscriptions
        for topic in topics:
            connection.subscriptions.add(topic)
            
            if topic not in self.subscriptions:
                self.subscriptions[topic] = set()
            self.subscriptions[topic].add(client_id)
        
        logger.info(f"Client {client_id} subscribed to topics: {topics}")
        
        # Send confirmation
        await self._send_to_client(
            client_id,
            WebSocketMessage(
                type=MessageType.SUBSCRIPTION,
                data={
                    'status': 'subscribed',
                    'topics': list(connection.subscriptions)
                },
                timestamp=time.time(),
                client_id=client_id
            )
        )
    
    async def _handle_unsubscription(self, client_id: str, data: Dict[str, Any]):
        """Handle unsubscription request."""
        topics = data.get('topics', [])
        
        connection = self.connections.get(client_id)
        if not connection:
            return
        
        # Remove subscriptions
        for topic in topics:
            connection.subscriptions.discard(topic)
            
            if topic in self.subscriptions:
                self.subscriptions[topic].discard(client_id)
                
                # Clean up empty topic
                if not self.subscriptions[topic]:
                    del self.subscriptions[topic]
        
        logger.info(f"Client {client_id} unsubscribed from topics: {topics}")
    
    async def _cleanup_client(self, client_id: str):
        """Clean up client connection."""
        connection = self.connections.pop(client_id, None)
        if not connection:
            return
        
        # Remove from all subscriptions
        for topic in connection.subscriptions:
            if topic in self.subscriptions:
                self.subscriptions[topic].discard(client_id)
                
                # Clean up empty topic
                if not self.subscriptions[topic]:
                    del self.subscriptions[topic]
        
        logger.info(f"Client {client_id} cleaned up")
    
    async def _send_to_client(self, client_id: str, message: WebSocketMessage):
        """Send message to specific client."""
        connection = self.connections.get(client_id)
        if not connection or not connection.is_alive():
            return
        
        try:
            await connection.websocket.send(message.to_json())
        except (ConnectionClosed, WebSocketException):
            # Connection closed, will be cleaned up by monitor
            pass
        except Exception as e:
            logger.error(f"Error sending message to {client_id}: {e}")
    
    async def _broadcast_to_topic(self, topic: str, message: WebSocketMessage):
        """Broadcast message to all clients subscribed to topic."""
        client_ids = self.subscriptions.get(topic, set()).copy()
        
        if not client_ids:
            return
        
        # Send to all subscribers
        tasks = []
        for client_id in client_ids:
            tasks.append(self._send_to_client(client_id, message))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _message_processor(self):
        """Process queued messages."""
        while self.running:
            try:
                # Get message from queue with timeout
                try:
                    message_data = await asyncio.wait_for(
                        self.message_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                message_type = message_data.get('type')
                topic = message_data.get('topic')
                data = message_data.get('data', {})
                
                if not topic:
                    continue
                
                # Create message
                message = WebSocketMessage(
                    type=MessageType(message_type),
                    data=data,
                    timestamp=time.time()
                )
                
                # Broadcast to topic
                await self._broadcast_to_topic(topic, message)
                
                # Mark task as done
                self.message_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error processing message: {e}")
    
    async def _heartbeat_monitor(self):
        """Monitor client heartbeats."""
        while self.running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                # Check all connections
                dead_clients = []
                for client_id, connection in self.connections.items():
                    if not connection.is_alive():
                        dead_clients.append(client_id)
                
                # Clean up dead connections
                for client_id in dead_clients:
                    await self._cleanup_client(client_id)
                    logger.info(f"Removed dead client: {client_id}")
                
            except Exception as e:
                logger.error(f"Error in heartbeat monitor: {e}")
    
    async def _connection_cleanup(self):
        """Periodic connection cleanup."""
        while self.running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                # Log connection stats
                active_connections = len(self.connections)
                total_subscriptions = sum(len(subs) for subs in self.subscriptions.values())
                
                logger.info(
                    f"WebSocket stats: {active_connections} connections, "
                    f"{len(self.subscriptions)} topics, {total_subscriptions} subscriptions"
                )
                
                # Store stats in Redis
                await redis_service.set_key(
                    "websocket:stats",
                    {
                        'active_connections': active_connections,
                        'topics': len(self.subscriptions),
                        'total_subscriptions': total_subscriptions,
                        'timestamp': time.time()
                    },
                    ttl=300  # 5 minutes
                )
                
            except Exception as e:
                logger.error(f"Error in connection cleanup: {e}")
    
    # Public API methods
    
    async def broadcast_progress_update(self, data: Dict[str, Any]):
        """Broadcast progress update."""
        task_id = data.get('task_id')
        video_id = data.get('video_id')
        
        if not task_id:
            return
        
        # Queue message for processing
        await self.message_queue.put({
            'type': MessageType.PROGRESS_UPDATE.value,
            'topic': f"task:{task_id}",
            'data': data
        })
        
        # Also broadcast to video topic if available
        if video_id:
            await self.message_queue.put({
                'type': MessageType.PROGRESS_UPDATE.value,
                'topic': f"video:{video_id}",
                'data': data
            })
    
    async def broadcast_clip_update(self, data: Dict[str, Any]):
        """Broadcast clip status update."""
        clip_id = data.get('clip_id')
        video_id = data.get('video_id')
        
        if not clip_id:
            return
        
        # Queue message for processing
        await self.message_queue.put({
            'type': MessageType.CLIP_UPDATE.value,
            'topic': f"clip:{clip_id}",
            'data': data
        })
        
        # Also broadcast to video topic if available
        if video_id:
            await self.message_queue.put({
                'type': MessageType.CLIP_UPDATE.value,
                'topic': f"video:{video_id}",
                'data': data
            })
    
    async def broadcast_status_update(self, data: Dict[str, Any]):
        """Broadcast general status update."""
        await self.message_queue.put({
            'type': MessageType.STATUS_UPDATE.value,
            'topic': 'global',
            'data': data
        })
    
    async def broadcast_error(self, data: Dict[str, Any]):
        """Broadcast error message."""
        task_id = data.get('task_id')
        video_id = data.get('video_id')
        
        # Queue message for processing
        await self.message_queue.put({
            'type': MessageType.ERROR.value,
            'topic': 'global',
            'data': data
        })
        
        # Also send to specific topics if available
        if task_id:
            await self.message_queue.put({
                'type': MessageType.ERROR.value,
                'topic': f"task:{task_id}",
                'data': data
            })
        
        if video_id:
            await self.message_queue.put({
                'type': MessageType.ERROR.value,
                'topic': f"video:{video_id}",
                'data': data
            })
    
    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            'active_connections': len(self.connections),
            'topics': len(self.subscriptions),
            'total_subscriptions': sum(len(subs) for subs in self.subscriptions.values()),
            'server_running': self.running,
            'queue_size': self.message_queue.qsize()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for WebSocket service."""
        try:
            stats = await self.get_connection_stats()
            
            return {
                'status': 'healthy' if self.running else 'stopped',
                'stats': stats,
                'timestamp': time.time()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': time.time()
            }


# Global WebSocket service instance
websocket_service = WebSocketService()


# Utility functions for easy integration

async def start_websocket_server():
    """Start WebSocket server."""
    await websocket_service.start_server()


async def stop_websocket_server():
    """Stop WebSocket server."""
    await websocket_service.stop_server()


async def broadcast_progress(task_id: str, progress: float, message: str, **kwargs):
    """Convenience function to broadcast progress."""
    data = {
        'task_id': task_id,
        'progress': progress,
        'message': message,
        **kwargs
    }
    await websocket_service.broadcast_progress_update(data)


async def broadcast_clip_status(clip_id: str, status: str, **kwargs):
    """Convenience function to broadcast clip status."""
    data = {
        'clip_id': clip_id,
        'status': status,
        **kwargs
    }
    await websocket_service.broadcast_clip_update(data)


async def broadcast_error_message(error: str, **kwargs):
    """Convenience function to broadcast error."""
    data = {
        'error': error,
        'timestamp': time.time(),
        **kwargs
    }
    await websocket_service.broadcast_error(data)