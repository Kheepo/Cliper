from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import asyncio
import json
import time
import logging
from enum import Enum
import aioredis
import socket
import psutil
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class ServiceStatus(Enum):
    """Service status enumeration."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"
    STOPPING = "stopping"
    MAINTENANCE = "maintenance"

class ServiceType(Enum):
    """Service type enumeration."""
    API = "api"
    WORKER = "worker"
    SCHEDULER = "scheduler"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    PROXY = "proxy"
    MONITOR = "monitor"

@dataclass
class ServiceInfo:
    """Service information model."""
    id: str
    name: str
    type: ServiceType
    host: str
    port: int
    status: ServiceStatus
    version: str
    metadata: Dict[str, Any]
    health_check_url: Optional[str] = None
    last_heartbeat: Optional[datetime] = None
    registered_at: Optional[datetime] = None
    tags: Optional[List[str]] = None
    dependencies: Optional[List[str]] = None
    load_balancer_weight: int = 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['type'] = self.type.value
        data['status'] = self.status.value
        if self.last_heartbeat:
            data['last_heartbeat'] = self.last_heartbeat.isoformat()
        if self.registered_at:
            data['registered_at'] = self.registered_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ServiceInfo':
        """Create from dictionary."""
        data['type'] = ServiceType(data['type'])
        data['status'] = ServiceStatus(data['status'])
        if data.get('last_heartbeat'):
            data['last_heartbeat'] = datetime.fromisoformat(data['last_heartbeat'])
        if data.get('registered_at'):
            data['registered_at'] = datetime.fromisoformat(data['registered_at'])
        return cls(**data)

@dataclass
class ServiceDiscoveryConfig:
    """Service discovery configuration."""
    redis_url: str = "redis://localhost:6379"
    service_ttl: int = 30  # seconds
    heartbeat_interval: int = 10  # seconds
    cleanup_interval: int = 60  # seconds
    health_check_timeout: int = 5  # seconds
    registry_key_prefix: str = "service_registry"
    events_key: str = "service_events"
    max_events: int = 1000

class ServiceRegistry:
    """Service registry for service discovery."""
    
    def __init__(self, config: ServiceDiscoveryConfig):
        self.config = config
        self.redis: Optional[aioredis.Redis] = None
        self.services: Dict[str, ServiceInfo] = {}
        self.event_listeners: List[callable] = []
        self._cleanup_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._local_service: Optional[ServiceInfo] = None
        
    async def initialize(self):
        """Initialize the service registry."""
        try:
            # Compatible with aioredis 1.x
            self.redis = await aioredis.create_redis_pool(self.config.redis_url)
            await self.redis.ping()
            logger.info("Service registry initialized successfully")
            
            # Start background tasks
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_services())
            
        except Exception as e:
            logger.error(f"Failed to initialize service registry: {e}")
            raise
    
    async def close(self):
        """Close the service registry."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        
        if self._local_service:
            await self.deregister_service(self._local_service.id)
        
        if self.redis:
            self.redis.close()
            await self.redis.wait_closed()
    
    async def register_service(self, service: ServiceInfo) -> bool:
        """Register a service."""
        try:
            service.registered_at = datetime.utcnow()
            service.last_heartbeat = datetime.utcnow()
            
            # Store in Redis
            key = f"{self.config.registry_key_prefix}:{service.id}"
            await self.redis.setex(
                key,
                self.config.service_ttl,
                json.dumps(service.to_dict())
            )
            
            # Store locally
            self.services[service.id] = service
            
            # Publish event
            await self._publish_event("service_registered", service)
            
            logger.info(f"Service registered: {service.name} ({service.id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register service {service.id}: {e}")
            return False
    
    async def deregister_service(self, service_id: str) -> bool:
        """Deregister a service."""
        try:
            # Remove from Redis
            key = f"{self.config.registry_key_prefix}:{service_id}"
            await self.redis.delete(key)
            
            # Remove locally
            service = self.services.pop(service_id, None)
            
            if service:
                # Publish event
                await self._publish_event("service_deregistered", service)
                logger.info(f"Service deregistered: {service.name} ({service.id})")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to deregister service {service_id}: {e}")
            return False
    
    async def update_service_status(self, service_id: str, status: ServiceStatus) -> bool:
        """Update service status."""
        try:
            service = await self.get_service(service_id)
            if not service:
                return False
            
            old_status = service.status
            service.status = status
            service.last_heartbeat = datetime.utcnow()
            
            # Update in Redis
            key = f"{self.config.registry_key_prefix}:{service_id}"
            await self.redis.setex(
                key,
                self.config.service_ttl,
                json.dumps(service.to_dict())
            )
            
            # Update locally
            self.services[service_id] = service
            
            # Publish event if status changed
            if old_status != status:
                await self._publish_event("service_status_changed", service, {
                    "old_status": old_status.value,
                    "new_status": status.value
                })
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update service status {service_id}: {e}")
            return False
    
    async def heartbeat(self, service_id: str) -> bool:
        """Send heartbeat for a service."""
        try:
            service = await self.get_service(service_id)
            if not service:
                return False
            
            service.last_heartbeat = datetime.utcnow()
            
            # Update TTL in Redis
            key = f"{self.config.registry_key_prefix}:{service_id}"
            await self.redis.setex(
                key,
                self.config.service_ttl,
                json.dumps(service.to_dict())
            )
            
            # Update locally
            self.services[service_id] = service
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send heartbeat for service {service_id}: {e}")
            return False
    
    async def get_service(self, service_id: str) -> Optional[ServiceInfo]:
        """Get service by ID."""
        try:
            # Try local cache first
            if service_id in self.services:
                return self.services[service_id]
            
            # Try Redis
            key = f"{self.config.registry_key_prefix}:{service_id}"
            data = await self.redis.get(key)
            
            if data:
                service = ServiceInfo.from_dict(json.loads(data))
                self.services[service_id] = service
                return service
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get service {service_id}: {e}")
            return None
    
    async def discover_services(
        self,
        service_type: Optional[ServiceType] = None,
        status: Optional[ServiceStatus] = None,
        tags: Optional[List[str]] = None
    ) -> List[ServiceInfo]:
        """Discover services with optional filters."""
        try:
            # Get all services from Redis
            pattern = f"{self.config.registry_key_prefix}:*"
            keys = await self.redis.keys(pattern)
            
            services = []
            for key in keys:
                data = await self.redis.get(key)
                if data:
                    try:
                        service = ServiceInfo.from_dict(json.loads(data))
                        services.append(service)
                    except Exception as e:
                        logger.warning(f"Failed to parse service data from {key}: {e}")
            
            # Apply filters
            filtered_services = services
            
            if service_type:
                filtered_services = [s for s in filtered_services if s.type == service_type]
            
            if status:
                filtered_services = [s for s in filtered_services if s.status == status]
            
            if tags:
                filtered_services = [
                    s for s in filtered_services
                    if s.tags and any(tag in s.tags for tag in tags)
                ]
            
            # Update local cache
            for service in services:
                self.services[service.id] = service
            
            return filtered_services
            
        except Exception as e:
            logger.error(f"Failed to discover services: {e}")
            return []
    
    async def get_healthy_services(self, service_type: Optional[ServiceType] = None) -> List[ServiceInfo]:
        """Get all healthy services."""
        return await self.discover_services(service_type=service_type, status=ServiceStatus.HEALTHY)
    
    async def get_service_endpoints(self, service_name: str) -> List[str]:
        """Get all endpoints for a service."""
        services = await self.discover_services()
        endpoints = []
        
        for service in services:
            if service.name == service_name and service.status == ServiceStatus.HEALTHY:
                endpoint = f"http://{service.host}:{service.port}"
                endpoints.append(endpoint)
        
        return endpoints
    
    async def register_local_service(
        self,
        name: str,
        service_type: ServiceType,
        port: int,
        version: str = "1.0.0",
        metadata: Optional[Dict[str, Any]] = None,
        health_check_url: Optional[str] = None,
        tags: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None
    ) -> str:
        """Register the local service and start heartbeat."""
        try:
            # Get local IP
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            
            # Create service info
            service_id = f"{name}_{local_ip}_{port}_{int(time.time())}"
            
            self._local_service = ServiceInfo(
                id=service_id,
                name=name,
                type=service_type,
                host=local_ip,
                port=port,
                status=ServiceStatus.STARTING,
                version=version,
                metadata=metadata or {},
                health_check_url=health_check_url,
                tags=tags or [],
                dependencies=dependencies or []
            )
            
            # Register service
            await self.register_service(self._local_service)
            
            # Start heartbeat task
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            logger.info(f"Local service registered: {name} ({service_id})")
            return service_id
            
        except Exception as e:
            logger.error(f"Failed to register local service: {e}")
            raise
    
    async def set_local_service_healthy(self):
        """Mark local service as healthy."""
        if self._local_service:
            await self.update_service_status(self._local_service.id, ServiceStatus.HEALTHY)
    
    async def _heartbeat_loop(self):
        """Background heartbeat loop."""
        while True:
            try:
                if self._local_service:
                    await self.heartbeat(self._local_service.id)
                await asyncio.sleep(self.config.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")
                await asyncio.sleep(self.config.heartbeat_interval)
    
    async def _cleanup_expired_services(self):
        """Background task to cleanup expired services."""
        while True:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                
                current_time = datetime.utcnow()
                expired_services = []
                
                for service_id, service in list(self.services.items()):
                    if service.last_heartbeat:
                        time_since_heartbeat = current_time - service.last_heartbeat
                        if time_since_heartbeat.total_seconds() > self.config.service_ttl * 2:
                            expired_services.append(service_id)
                
                for service_id in expired_services:
                    await self.deregister_service(service_id)
                    logger.info(f"Cleaned up expired service: {service_id}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Service cleanup failed: {e}")
    
    async def _publish_event(self, event_type: str, service: ServiceInfo, extra_data: Optional[Dict] = None):
        """Publish service event."""
        try:
            event = {
                "type": event_type,
                "service": service.to_dict(),
                "timestamp": datetime.utcnow().isoformat(),
                "extra": extra_data or {}
            }
            
            # Publish to Redis stream
            await self.redis.xadd(
                self.config.events_key,
                event,
                maxlen=self.config.max_events
            )
            
            # Notify local listeners
            for listener in self.event_listeners:
                try:
                    if asyncio.iscoroutinefunction(listener):
                        await listener(event)
                    else:
                        listener(event)
                except Exception as e:
                    logger.error(f"Event listener failed: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
    
    def add_event_listener(self, listener: callable):
        """Add event listener."""
        self.event_listeners.append(listener)
    
    def remove_event_listener(self, listener: callable):
        """Remove event listener."""
        if listener in self.event_listeners:
            self.event_listeners.remove(listener)

class LoadBalancer:
    """Simple load balancer for service discovery."""
    
    def __init__(self, registry: ServiceRegistry):
        self.registry = registry
        self._round_robin_counters: Dict[str, int] = {}
    
    async def get_service_endpoint(
        self,
        service_name: str,
        strategy: str = "round_robin"
    ) -> Optional[str]:
        """Get service endpoint using load balancing strategy."""
        services = await self.registry.get_healthy_services()
        target_services = [s for s in services if s.name == service_name]
        
        if not target_services:
            return None
        
        if strategy == "round_robin":
            return self._round_robin_select(service_name, target_services)
        elif strategy == "weighted":
            return self._weighted_select(target_services)
        elif strategy == "random":
            import random
            service = random.choice(target_services)
            return f"http://{service.host}:{service.port}"
        else:
            # Default to first available
            service = target_services[0]
            return f"http://{service.host}:{service.port}"
    
    def _round_robin_select(self, service_name: str, services: List[ServiceInfo]) -> str:
        """Round-robin selection."""
        if service_name not in self._round_robin_counters:
            self._round_robin_counters[service_name] = 0
        
        index = self._round_robin_counters[service_name] % len(services)
        self._round_robin_counters[service_name] += 1
        
        service = services[index]
        return f"http://{service.host}:{service.port}"
    
    def _weighted_select(self, services: List[ServiceInfo]) -> str:
        """Weighted selection based on load balancer weight."""
        import random
        
        total_weight = sum(s.load_balancer_weight for s in services)
        if total_weight == 0:
            service = services[0]
        else:
            rand_weight = random.randint(1, total_weight)
            current_weight = 0
            
            for service in services:
                current_weight += service.load_balancer_weight
                if rand_weight <= current_weight:
                    break
        
        return f"http://{service.host}:{service.port}"

# Global service registry instance
service_registry: Optional[ServiceRegistry] = None
load_balancer: Optional[LoadBalancer] = None

@asynccontextmanager
async def get_service_registry(config: Optional[ServiceDiscoveryConfig] = None):
    """Context manager for service registry."""
    global service_registry, load_balancer
    
    if not service_registry:
        config = config or ServiceDiscoveryConfig()
        service_registry = ServiceRegistry(config)
        await service_registry.initialize()
        load_balancer = LoadBalancer(service_registry)
    
    try:
        yield service_registry
    finally:
        pass  # Keep registry alive for the application lifecycle

async def initialize_service_discovery(config: Optional[ServiceDiscoveryConfig] = None):
    """Initialize global service discovery."""
    global service_registry, load_balancer
    
    config = config or ServiceDiscoveryConfig()
    service_registry = ServiceRegistry(config)
    await service_registry.initialize()
    load_balancer = LoadBalancer(service_registry)
    
    logger.info("Service discovery initialized")

async def cleanup_service_discovery():
    """Cleanup service discovery."""
    global service_registry, load_balancer
    
    if service_registry:
        await service_registry.close()
        service_registry = None
        load_balancer = None
    
    logger.info("Service discovery cleaned up")