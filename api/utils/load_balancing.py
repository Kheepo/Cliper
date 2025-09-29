"""Load balancing and horizontal scaling utilities.

Provides:
- Service discovery and registration
- Health check coordination
- Load balancing algorithms
- Session affinity management
- Circuit breaker patterns
- Auto-scaling triggers
- Distributed task coordination
- Node coordination and failover
"""

import asyncio
import json
import time
import hashlib
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict, deque
import redis.asyncio as redis
import httpx
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class NodeStatus(str, Enum):
    """Node status states."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DRAINING = "draining"
    OFFLINE = "offline"


class LoadBalancingAlgorithm(str, Enum):
    """Load balancing algorithms."""
    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    LEAST_RESPONSE_TIME = "least_response_time"
    CONSISTENT_HASH = "consistent_hash"
    RANDOM = "random"
    WEIGHTED_RANDOM = "weighted_random"


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ServiceNode:
    """Service node information."""
    id: str
    host: str
    port: int
    weight: float = 1.0
    status: NodeStatus = NodeStatus.HEALTHY
    last_health_check: Optional[datetime] = None
    response_time_ms: float = 0.0
    active_connections: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    load_score: float = 0.0
    metadata: Optional[Dict[str, Any]] = None
    
    @property
    def endpoint(self) -> str:
        return f"http://{self.host}:{self.port}"
    
    @property
    def is_available(self) -> bool:
        return self.status in [NodeStatus.HEALTHY, NodeStatus.DEGRADED]


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5
    recovery_timeout: int = 60
    success_threshold: int = 3
    timeout: float = 30.0
    

@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics."""
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    total_requests: int = 0
    total_failures: int = 0


class CircuitBreaker:
    """Circuit breaker for fault tolerance."""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self.stats.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.stats.state = CircuitBreakerState.HALF_OPEN
                    self.stats.success_count = 0
                else:
                    raise Exception("Circuit breaker is OPEN")
        
        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.timeout
            )
            
            await self._on_success()
            return result
            
        except Exception as e:
            await self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        if not self.stats.last_failure_time:
            return True
        
        time_since_failure = datetime.utcnow() - self.stats.last_failure_time
        return time_since_failure.total_seconds() >= self.config.recovery_timeout
    
    async def _on_success(self):
        """Handle successful request."""
        async with self._lock:
            self.stats.total_requests += 1
            self.stats.last_success_time = datetime.utcnow()
            
            if self.stats.state == CircuitBreakerState.HALF_OPEN:
                self.stats.success_count += 1
                if self.stats.success_count >= self.config.success_threshold:
                    self.stats.state = CircuitBreakerState.CLOSED
                    self.stats.failure_count = 0
            elif self.stats.state == CircuitBreakerState.CLOSED:
                self.stats.failure_count = 0
    
    async def _on_failure(self):
        """Handle failed request."""
        async with self._lock:
            self.stats.total_requests += 1
            self.stats.total_failures += 1
            self.stats.failure_count += 1
            self.stats.last_failure_time = datetime.utcnow()
            
            if self.stats.failure_count >= self.config.failure_threshold:
                self.stats.state = CircuitBreakerState.OPEN


class ServiceRegistry:
    """Service discovery and registration."""
    
    def __init__(self, redis_client: redis.Redis, service_name: str):
        self.redis = redis_client
        self.service_name = service_name
        self.nodes: Dict[str, ServiceNode] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._health_check_task: Optional[asyncio.Task] = None
        
    async def register_node(self, node: ServiceNode, ttl: int = 30):
        """Register a service node."""
        self.nodes[node.id] = node
        
        # Store in Redis for distributed discovery
        node_data = {
            **asdict(node),
            'last_seen': datetime.utcnow().isoformat(),
            'ttl': ttl
        }
        
        await self.redis.hset(
            f"service:{self.service_name}:nodes",
            node.id,
            json.dumps(node_data, default=str)
        )
        
        # Set TTL for automatic cleanup
        await self.redis.expire(
            f"service:{self.service_name}:nodes:{node.id}",
            ttl
        )
        
        logger.info(f"Registered node {node.id} for service {self.service_name}")
    
    async def unregister_node(self, node_id: str):
        """Unregister a service node."""
        if node_id in self.nodes:
            del self.nodes[node_id]
        
        await self.redis.hdel(f"service:{self.service_name}:nodes", node_id)
        await self.redis.delete(f"service:{self.service_name}:nodes:{node_id}")
        
        logger.info(f"Unregistered node {node_id} from service {self.service_name}")
    
    async def discover_nodes(self) -> List[ServiceNode]:
        """Discover available service nodes."""
        # Get nodes from Redis
        nodes_data = await self.redis.hgetall(f"service:{self.service_name}:nodes")
        
        discovered_nodes = []
        for node_id, node_json in nodes_data.items():
            try:
                node_data = json.loads(node_json)
                node = ServiceNode(**{k: v for k, v in node_data.items() 
                                    if k not in ['last_seen', 'ttl']})
                discovered_nodes.append(node)
                
                # Update local cache
                self.nodes[node.id] = node
                
            except Exception as e:
                logger.error(f"Error parsing node data for {node_id}: {e}")
        
        return discovered_nodes
    
    async def get_healthy_nodes(self) -> List[ServiceNode]:
        """Get list of healthy nodes."""
        await self.discover_nodes()
        return [node for node in self.nodes.values() if node.is_available]
    
    async def health_check_node(self, node: ServiceNode) -> bool:
        """Perform health check on a node."""
        try:
            start_time = time.time()
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{node.endpoint}/health")
                
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                # Update node metrics
                node.response_time_ms = response_time
                node.last_health_check = datetime.utcnow()
                
                # Parse health data if available
                try:
                    health_data = response.json()
                    node.cpu_usage = health_data.get('cpu_usage', 0)
                    node.memory_usage = health_data.get('memory_usage', 0)
                    node.active_connections = health_data.get('active_connections', 0)
                    
                    # Calculate load score
                    node.load_score = (
                        node.cpu_usage * 0.4 +
                        node.memory_usage * 0.3 +
                        (node.active_connections / 100) * 0.2 +
                        (node.response_time_ms / 1000) * 0.1
                    )
                    
                except Exception:
                    pass
                
                # Update status based on response time and load
                if response_time > 5000 or node.load_score > 0.9:
                    node.status = NodeStatus.DEGRADED
                else:
                    node.status = NodeStatus.HEALTHY
                
                return True
            else:
                node.status = NodeStatus.UNHEALTHY
                return False
                
        except Exception as e:
            logger.warning(f"Health check failed for node {node.id}: {e}")
            node.status = NodeStatus.UNHEALTHY
            return False
    
    async def start_health_monitoring(self, interval: int = 30):
        """Start background health monitoring."""
        if self._health_check_task:
            return
        
        async def health_check_loop():
            while True:
                try:
                    nodes = list(self.nodes.values())
                    
                    # Perform health checks concurrently
                    tasks = [self.health_check_node(node) for node in nodes]
                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Update registry
                    for node in nodes:
                        if node.is_available:
                            await self.register_node(node)
                    
                    await asyncio.sleep(interval)
                    
                except Exception as e:
                    logger.error(f"Error in health check loop: {e}")
                    await asyncio.sleep(interval)
        
        self._health_check_task = asyncio.create_task(health_check_loop())
        logger.info(f"Started health monitoring for service {self.service_name}")
    
    async def stop_health_monitoring(self):
        """Stop background health monitoring."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None


class LoadBalancer:
    """Load balancer with multiple algorithms."""
    
    def __init__(self, service_registry: ServiceRegistry, algorithm: LoadBalancingAlgorithm = LoadBalancingAlgorithm.ROUND_ROBIN):
        self.registry = service_registry
        self.algorithm = algorithm
        self._round_robin_index = 0
        self._consistent_hash_ring: Dict[int, str] = {}
        self._session_affinity: Dict[str, str] = {}  # session_id -> node_id
        
    async def select_node(self, session_id: Optional[str] = None, key: Optional[str] = None) -> Optional[ServiceNode]:
        """Select a node based on the configured algorithm."""
        healthy_nodes = await self.registry.get_healthy_nodes()
        
        if not healthy_nodes:
            return None
        
        # Check session affinity first
        if session_id and session_id in self._session_affinity:
            node_id = self._session_affinity[session_id]
            node = next((n for n in healthy_nodes if n.id == node_id), None)
            if node:
                return node
            else:
                # Remove stale session affinity
                del self._session_affinity[session_id]
        
        # Apply load balancing algorithm
        if self.algorithm == LoadBalancingAlgorithm.ROUND_ROBIN:
            node = self._round_robin_select(healthy_nodes)
        elif self.algorithm == LoadBalancingAlgorithm.WEIGHTED_ROUND_ROBIN:
            node = self._weighted_round_robin_select(healthy_nodes)
        elif self.algorithm == LoadBalancingAlgorithm.LEAST_CONNECTIONS:
            node = self._least_connections_select(healthy_nodes)
        elif self.algorithm == LoadBalancingAlgorithm.LEAST_RESPONSE_TIME:
            node = self._least_response_time_select(healthy_nodes)
        elif self.algorithm == LoadBalancingAlgorithm.CONSISTENT_HASH:
            node = self._consistent_hash_select(healthy_nodes, key or session_id or "")
        elif self.algorithm == LoadBalancingAlgorithm.RANDOM:
            node = random.choice(healthy_nodes)
        elif self.algorithm == LoadBalancingAlgorithm.WEIGHTED_RANDOM:
            node = self._weighted_random_select(healthy_nodes)
        else:
            node = healthy_nodes[0]
        
        # Set session affinity if session_id provided
        if session_id and node:
            self._session_affinity[session_id] = node.id
        
        return node
    
    def _round_robin_select(self, nodes: List[ServiceNode]) -> ServiceNode:
        """Round-robin selection."""
        node = nodes[self._round_robin_index % len(nodes)]
        self._round_robin_index += 1
        return node
    
    def _weighted_round_robin_select(self, nodes: List[ServiceNode]) -> ServiceNode:
        """Weighted round-robin selection."""
        total_weight = sum(node.weight for node in nodes)
        if total_weight == 0:
            return self._round_robin_select(nodes)
        
        # Create weighted list
        weighted_nodes = []
        for node in nodes:
            count = max(1, int(node.weight * 10))
            weighted_nodes.extend([node] * count)
        
        return self._round_robin_select(weighted_nodes)
    
    def _least_connections_select(self, nodes: List[ServiceNode]) -> ServiceNode:
        """Least connections selection."""
        return min(nodes, key=lambda n: n.active_connections)
    
    def _least_response_time_select(self, nodes: List[ServiceNode]) -> ServiceNode:
        """Least response time selection."""
        return min(nodes, key=lambda n: n.response_time_ms)
    
    def _consistent_hash_select(self, nodes: List[ServiceNode], key: str) -> ServiceNode:
        """Consistent hash selection."""
        if not self._consistent_hash_ring or len(self._consistent_hash_ring) != len(nodes) * 100:
            self._build_hash_ring(nodes)
        
        if not self._consistent_hash_ring:
            return nodes[0]
        
        key_hash = int(hashlib.md5(key.encode()).hexdigest(), 16)
        
        # Find the first node with hash >= key_hash
        for hash_value in sorted(self._consistent_hash_ring.keys()):
            if hash_value >= key_hash:
                node_id = self._consistent_hash_ring[hash_value]
                return next(n for n in nodes if n.id == node_id)
        
        # Wrap around to the first node
        first_hash = min(self._consistent_hash_ring.keys())
        node_id = self._consistent_hash_ring[first_hash]
        return next(n for n in nodes if n.id == node_id)
    
    def _weighted_random_select(self, nodes: List[ServiceNode]) -> ServiceNode:
        """Weighted random selection."""
        total_weight = sum(node.weight for node in nodes)
        if total_weight == 0:
            return random.choice(nodes)
        
        r = random.uniform(0, total_weight)
        cumulative_weight = 0
        
        for node in nodes:
            cumulative_weight += node.weight
            if r <= cumulative_weight:
                return node
        
        return nodes[-1]
    
    def _build_hash_ring(self, nodes: List[ServiceNode]):
        """Build consistent hash ring."""
        self._consistent_hash_ring.clear()
        
        for node in nodes:
            # Create multiple virtual nodes for better distribution
            for i in range(100):
                virtual_key = f"{node.id}:{i}"
                hash_value = int(hashlib.md5(virtual_key.encode()).hexdigest(), 16)
                self._consistent_hash_ring[hash_value] = node.id


class DistributedTaskCoordinator:
    """Coordinate tasks across multiple nodes."""
    
    def __init__(self, redis_client: redis.Redis, node_id: str):
        self.redis = redis_client
        self.node_id = node_id
        self.active_tasks: Dict[str, asyncio.Task] = {}
        
    async def acquire_task_lock(self, task_id: str, ttl: int = 300) -> bool:
        """Acquire distributed lock for task execution."""
        lock_key = f"task_lock:{task_id}"
        
        # Try to acquire lock
        result = await self.redis.set(
            lock_key,
            self.node_id,
            nx=True,  # Only set if not exists
            ex=ttl    # Expire after TTL seconds
        )
        
        return result is not None
    
    async def release_task_lock(self, task_id: str):
        """Release distributed task lock."""
        lock_key = f"task_lock:{task_id}"
        
        # Only release if we own the lock
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        
        await self.redis.eval(lua_script, 1, lock_key, self.node_id)
    
    async def coordinate_task(self, task_id: str, task_func: Callable, *args, **kwargs):
        """Execute task with distributed coordination."""
        if await self.acquire_task_lock(task_id):
            try:
                logger.info(f"Node {self.node_id} acquired lock for task {task_id}")
                
                # Execute task
                if asyncio.iscoroutinefunction(task_func):
                    result = await task_func(*args, **kwargs)
                else:
                    result = task_func(*args, **kwargs)
                
                # Store result
                await self.redis.setex(
                    f"task_result:{task_id}",
                    3600,  # 1 hour TTL
                    json.dumps({
                        "result": result,
                        "node_id": self.node_id,
                        "completed_at": datetime.utcnow().isoformat()
                    }, default=str)
                )
                
                return result
                
            finally:
                await self.release_task_lock(task_id)
        else:
            logger.info(f"Task {task_id} already being executed by another node")
            
            # Wait for result from other node
            for _ in range(60):  # Wait up to 60 seconds
                result_data = await self.redis.get(f"task_result:{task_id}")
                if result_data:
                    result = json.loads(result_data)
                    return result["result"]
                await asyncio.sleep(1)
            
            raise Exception(f"Task {task_id} execution timeout")


class AutoScaler:
    """Auto-scaling based on metrics."""
    
    def __init__(self, service_registry: ServiceRegistry, redis_client: redis.Redis):
        self.registry = service_registry
        self.redis = redis_client
        self.metrics_history: deque = deque(maxlen=100)
        self._scaling_task: Optional[asyncio.Task] = None
        
    async def collect_metrics(self) -> Dict[str, float]:
        """Collect scaling metrics."""
        nodes = await self.registry.get_healthy_nodes()
        
        if not nodes:
            return {}
        
        # Calculate aggregate metrics
        total_cpu = sum(node.cpu_usage for node in nodes) / len(nodes)
        total_memory = sum(node.memory_usage for node in nodes) / len(nodes)
        total_connections = sum(node.active_connections for node in nodes)
        avg_response_time = sum(node.response_time_ms for node in nodes) / len(nodes)
        
        # Get queue length from Redis
        queue_length = await self.redis.llen("clip_processing_queue") or 0
        
        metrics = {
            "avg_cpu_usage": total_cpu,
            "avg_memory_usage": total_memory,
            "total_connections": total_connections,
            "avg_response_time": avg_response_time,
            "queue_length": queue_length,
            "node_count": len(nodes),
            "timestamp": time.time()
        }
        
        self.metrics_history.append(metrics)
        return metrics
    
    async def should_scale_up(self) -> bool:
        """Determine if scaling up is needed."""
        if len(self.metrics_history) < 5:
            return False
        
        recent_metrics = list(self.metrics_history)[-5:]
        
        # Check if consistently high load
        high_cpu = all(m["avg_cpu_usage"] > 80 for m in recent_metrics)
        high_memory = all(m["avg_memory_usage"] > 80 for m in recent_metrics)
        high_queue = all(m["queue_length"] > 50 for m in recent_metrics)
        slow_response = all(m["avg_response_time"] > 2000 for m in recent_metrics)
        
        return high_cpu or high_memory or high_queue or slow_response
    
    async def should_scale_down(self) -> bool:
        """Determine if scaling down is needed."""
        if len(self.metrics_history) < 10:
            return False
        
        recent_metrics = list(self.metrics_history)[-10:]
        
        # Check if consistently low load
        low_cpu = all(m["avg_cpu_usage"] < 30 for m in recent_metrics)
        low_memory = all(m["avg_memory_usage"] < 30 for m in recent_metrics)
        low_queue = all(m["queue_length"] < 5 for m in recent_metrics)
        fast_response = all(m["avg_response_time"] < 500 for m in recent_metrics)
        
        # Don't scale down if only one node
        current_nodes = recent_metrics[-1]["node_count"]
        
        return (low_cpu and low_memory and low_queue and fast_response and current_nodes > 1)
    
    async def trigger_scale_up(self):
        """Trigger scale up action."""
        logger.info("Triggering scale up")
        
        # Publish scale up event
        await self.redis.publish(
            "scaling_events",
            json.dumps({
                "action": "scale_up",
                "timestamp": datetime.utcnow().isoformat(),
                "metrics": dict(self.metrics_history[-1]) if self.metrics_history else {}
            })
        )
    
    async def trigger_scale_down(self):
        """Trigger scale down action."""
        logger.info("Triggering scale down")
        
        # Publish scale down event
        await self.redis.publish(
            "scaling_events",
            json.dumps({
                "action": "scale_down",
                "timestamp": datetime.utcnow().isoformat(),
                "metrics": dict(self.metrics_history[-1]) if self.metrics_history else {}
            })
        )
    
    async def start_auto_scaling(self, interval: int = 60):
        """Start auto-scaling monitoring."""
        if self._scaling_task:
            return
        
        async def scaling_loop():
            while True:
                try:
                    await self.collect_metrics()
                    
                    if await self.should_scale_up():
                        await self.trigger_scale_up()
                    elif await self.should_scale_down():
                        await self.trigger_scale_down()
                    
                    await asyncio.sleep(interval)
                    
                except Exception as e:
                    logger.error(f"Error in auto-scaling loop: {e}")
                    await asyncio.sleep(interval)
        
        self._scaling_task = asyncio.create_task(scaling_loop())
        logger.info("Started auto-scaling monitoring")
    
    async def stop_auto_scaling(self):
        """Stop auto-scaling monitoring."""
        if self._scaling_task:
            self._scaling_task.cancel()
            try:
                await self._scaling_task
            except asyncio.CancelledError:
                pass
            self._scaling_task = None


# Global instances
_service_registries: Dict[str, ServiceRegistry] = {}
_load_balancers: Dict[str, LoadBalancer] = {}
_task_coordinator: Optional[DistributedTaskCoordinator] = None
_auto_scaler: Optional[AutoScaler] = None


def get_service_registry(service_name: str, redis_client: redis.Redis) -> ServiceRegistry:
    """Get or create service registry."""
    if service_name not in _service_registries:
        _service_registries[service_name] = ServiceRegistry(redis_client, service_name)
    return _service_registries[service_name]


def get_load_balancer(service_name: str, redis_client: redis.Redis, algorithm: LoadBalancingAlgorithm = LoadBalancingAlgorithm.ROUND_ROBIN) -> LoadBalancer:
    """Get or create load balancer."""
    if service_name not in _load_balancers:
        registry = get_service_registry(service_name, redis_client)
        _load_balancers[service_name] = LoadBalancer(registry, algorithm)
    return _load_balancers[service_name]


def get_task_coordinator(redis_client: redis.Redis, node_id: str) -> DistributedTaskCoordinator:
    """Get or create task coordinator."""
    global _task_coordinator
    if not _task_coordinator:
        _task_coordinator = DistributedTaskCoordinator(redis_client, node_id)
    return _task_coordinator


def get_auto_scaler(service_name: str, redis_client: redis.Redis) -> AutoScaler:
    """Get or create auto scaler."""
    global _auto_scaler
    if not _auto_scaler:
        registry = get_service_registry(service_name, redis_client)
        _auto_scaler = AutoScaler(registry, redis_client)
    return _auto_scaler


@asynccontextmanager
async def circuit_breaker_context(node: ServiceNode, config: CircuitBreakerConfig = None):
    """Context manager for circuit breaker protection."""
    if config is None:
        config = CircuitBreakerConfig()
    
    # Get or create circuit breaker for node
    registry = _service_registries.get("default")
    if registry and node.id not in registry.circuit_breakers:
        registry.circuit_breakers[node.id] = CircuitBreaker(config)
    
    circuit_breaker = registry.circuit_breakers.get(node.id) if registry else CircuitBreaker(config)
    
    try:
        yield circuit_breaker
    except Exception:
        raise


# Export commonly used items
__all__ = [
    'ServiceNode',
    'ServiceRegistry',
    'LoadBalancer',
    'LoadBalancingAlgorithm',
    'CircuitBreaker',
    'CircuitBreakerConfig',
    'DistributedTaskCoordinator',
    'AutoScaler',
    'NodeStatus',
    'get_service_registry',
    'get_load_balancer',
    'get_task_coordinator',
    'get_auto_scaler',
    'circuit_breaker_context'
]