#!/usr/bin/env python3
"""
Load balancing and horizontal scaling module for clip generation system.
Provides intelligent request distribution, auto-scaling, and resource management.
"""

import asyncio
import time
import json
import logging
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import hashlib
import random
from concurrent.futures import ThreadPoolExecutor
import threading
from datetime import datetime, timedelta

from api.core.config import get_settings
from api.monitoring.resource_monitor import ResourceMonitor
from api.monitoring.health_checker import HealthChecker
from api.utils.redis_utils import RedisUtils
from api.core.database import get_database


class LoadBalancingStrategy(Enum):
    """Load balancing strategies."""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    RESOURCE_BASED = "resource_based"
    CONSISTENT_HASHING = "consistent_hashing"
    ADAPTIVE = "adaptive"


class NodeStatus(Enum):
    """Node status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


@dataclass
class WorkerNode:
    """Worker node configuration and state."""
    id: str
    host: str
    port: int
    weight: float = 1.0
    max_connections: int = 100
    current_connections: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    status: NodeStatus = NodeStatus.HEALTHY
    last_health_check: datetime = field(default_factory=datetime.now)
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    error_count: int = 0
    success_count: int = 0
    total_requests: int = 0
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def url(self) -> str:
        """Get node URL."""
        return f"http://{self.host}:{self.port}"
    
    @property
    def load_score(self) -> float:
        """Calculate node load score (0-1, lower is better)."""
        connection_load = self.current_connections / self.max_connections
        resource_load = (self.cpu_usage + self.memory_usage + self.disk_usage) / 3
        error_rate = self.error_count / max(self.total_requests, 1)
        
        # Weighted combination
        return (connection_load * 0.3 + resource_load * 0.5 + error_rate * 0.2)
    
    @property
    def average_response_time(self) -> float:
        """Get average response time."""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    def update_metrics(self, cpu: float, memory: float, disk: float, connections: int):
        """Update node metrics."""
        self.cpu_usage = cpu
        self.memory_usage = memory
        self.disk_usage = disk
        self.current_connections = connections
        self.last_health_check = datetime.now()
    
    def record_request(self, response_time: float, success: bool):
        """Record request metrics."""
        self.response_times.append(response_time)
        self.total_requests += 1
        
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
    
    def is_healthy(self, health_threshold: float = 0.8) -> bool:
        """Check if node is healthy."""
        if self.status in [NodeStatus.OFFLINE, NodeStatus.MAINTENANCE]:
            return False
        
        # Check resource thresholds
        if self.cpu_usage > 90 or self.memory_usage > 90 or self.disk_usage > 95:
            return False
        
        # Check error rate
        if self.total_requests > 10:
            error_rate = self.error_count / self.total_requests
            if error_rate > (1 - health_threshold):
                return False
        
        # Check last health check time
        if datetime.now() - self.last_health_check > timedelta(minutes=5):
            return False
        
        return True


@dataclass
class LoadBalancingConfig:
    """Load balancing configuration."""
    strategy: LoadBalancingStrategy = LoadBalancingStrategy.ADAPTIVE
    health_check_interval: int = 30  # seconds
    max_retries: int = 3
    retry_delay: float = 1.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60
    sticky_sessions: bool = False
    session_timeout: int = 3600  # seconds
    auto_scaling_enabled: bool = True
    min_nodes: int = 2
    max_nodes: int = 10
    scale_up_threshold: float = 0.8
    scale_down_threshold: float = 0.3
    scale_cooldown: int = 300  # seconds
    consistent_hash_replicas: int = 150


class ConsistentHashRing:
    """Consistent hashing implementation for load balancing."""
    
    def __init__(self, replicas: int = 150):
        self.replicas = replicas
        self.ring = {}
        self.sorted_keys = []
    
    def _hash(self, key: str) -> int:
        """Hash function for consistent hashing."""
        return int(hashlib.md5(key.encode()).hexdigest(), 16)
    
    def add_node(self, node: WorkerNode):
        """Add a node to the hash ring."""
        for i in range(self.replicas):
            key = self._hash(f"{node.id}:{i}")
            self.ring[key] = node
        
        self.sorted_keys = sorted(self.ring.keys())
    
    def remove_node(self, node: WorkerNode):
        """Remove a node from the hash ring."""
        for i in range(self.replicas):
            key = self._hash(f"{node.id}:{i}")
            if key in self.ring:
                del self.ring[key]
        
        self.sorted_keys = sorted(self.ring.keys())
    
    def get_node(self, key: str) -> Optional[WorkerNode]:
        """Get the node responsible for a key."""
        if not self.ring:
            return None
        
        hash_key = self._hash(key)
        
        # Find the first node with a key >= hash_key
        for ring_key in self.sorted_keys:
            if ring_key >= hash_key:
                return self.ring[ring_key]
        
        # Wrap around to the first node
        return self.ring[self.sorted_keys[0]]


class CircuitBreaker:
    """Circuit breaker for node failure handling."""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half-open"
            else:
                raise Exception("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e
    
    def on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = "closed"
    
    def on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"


class LoadBalancer:
    """Advanced load balancer with multiple strategies and auto-scaling."""
    
    def __init__(self, config: LoadBalancingConfig = None):
        self.config = config or LoadBalancingConfig()
        self.settings = get_settings()
        self.logger = logging.getLogger(__name__)
        
        # Node management
        self.nodes: Dict[str, WorkerNode] = {}
        self.healthy_nodes: List[WorkerNode] = []
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Load balancing state
        self.current_index = 0
        self.hash_ring = ConsistentHashRing(self.config.consistent_hash_replicas)
        self.sticky_sessions: Dict[str, str] = {}  # session_id -> node_id
        
        # Monitoring
        self.resource_monitor = ResourceMonitor()
        self.health_checker = HealthChecker()
        self.redis_utils = RedisUtils()
        self.db = get_database()
        
        # Auto-scaling
        self.last_scale_action = 0
        self.scaling_lock = threading.Lock()
        
        # Metrics
        self.request_count = 0
        self.total_response_time = 0.0
        self.error_count = 0
        
        # Background tasks
        self._health_check_task = None
        self._auto_scale_task = None
        self._running = False
    
    async def start(self):
        """Start the load balancer."""
        self.logger.info("Starting load balancer...")
        self._running = True
        
        # Initialize monitoring
        await self.resource_monitor.start()
        await self.health_checker.start()
        
        # Load existing nodes from database
        await self._load_nodes_from_db()
        
        # Start background tasks
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        if self.config.auto_scaling_enabled:
            self._auto_scale_task = asyncio.create_task(self._auto_scale_loop())
        
        self.logger.info(f"Load balancer started with {len(self.nodes)} nodes")
    
    async def stop(self):
        """Stop the load balancer."""
        self.logger.info("Stopping load balancer...")
        self._running = False
        
        # Cancel background tasks
        if self._health_check_task:
            self._health_check_task.cancel()
        if self._auto_scale_task:
            self._auto_scale_task.cancel()
        
        # Stop monitoring
        await self.resource_monitor.stop()
        await self.health_checker.stop()
        
        self.logger.info("Load balancer stopped")
    
    async def add_node(self, node: WorkerNode) -> bool:
        """Add a new worker node."""
        try:
            # Validate node
            if not await self._validate_node(node):
                return False
            
            # Add to nodes
            self.nodes[node.id] = node
            self.circuit_breakers[node.id] = CircuitBreaker(
                self.config.circuit_breaker_threshold,
                self.config.circuit_breaker_timeout
            )
            
            # Update hash ring
            self.hash_ring.add_node(node)
            
            # Update healthy nodes list
            await self._update_healthy_nodes()
            
            # Save to database
            await self._save_node_to_db(node)
            
            self.logger.info(f"Added node {node.id} ({node.url})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add node {node.id}: {e}")
            return False
    
    async def remove_node(self, node_id: str) -> bool:
        """Remove a worker node."""
        try:
            if node_id not in self.nodes:
                return False
            
            node = self.nodes[node_id]
            
            # Remove from hash ring
            self.hash_ring.remove_node(node)
            
            # Remove from collections
            del self.nodes[node_id]
            if node_id in self.circuit_breakers:
                del self.circuit_breakers[node_id]
            
            # Update healthy nodes list
            await self._update_healthy_nodes()
            
            # Remove from database
            await self._remove_node_from_db(node_id)
            
            # Clear sticky sessions for this node
            self.sticky_sessions = {
                session_id: nid for session_id, nid in self.sticky_sessions.items()
                if nid != node_id
            }
            
            self.logger.info(f"Removed node {node_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to remove node {node_id}: {e}")
            return False
    
    async def get_node(self, request_id: str = None, session_id: str = None, 
                      capabilities: List[str] = None) -> Optional[WorkerNode]:
        """Get the best node for a request."""
        try:
            # Filter nodes by capabilities
            available_nodes = self._filter_nodes_by_capabilities(capabilities)
            
            if not available_nodes:
                self.logger.warning("No available nodes found")
                return None
            
            # Handle sticky sessions
            if session_id and self.config.sticky_sessions:
                if session_id in self.sticky_sessions:
                    node_id = self.sticky_sessions[session_id]
                    if node_id in self.nodes and self.nodes[node_id].is_healthy():
                        return self.nodes[node_id]
            
            # Select node based on strategy
            node = await self._select_node(available_nodes, request_id)
            
            # Update sticky session
            if session_id and self.config.sticky_sessions and node:
                self.sticky_sessions[session_id] = node.id
                # Clean up old sessions
                await self._cleanup_sticky_sessions()
            
            return node
            
        except Exception as e:
            self.logger.error(f"Failed to get node: {e}")
            return None
    
    async def record_request(self, node_id: str, response_time: float, 
                           success: bool, error: str = None):
        """Record request metrics."""
        try:
            # Update global metrics
            self.request_count += 1
            self.total_response_time += response_time
            if not success:
                self.error_count += 1
            
            # Update node metrics
            if node_id in self.nodes:
                node = self.nodes[node_id]
                node.record_request(response_time, success)
                
                # Update circuit breaker
                if node_id in self.circuit_breakers:
                    if success:
                        self.circuit_breakers[node_id].on_success()
                    else:
                        self.circuit_breakers[node_id].on_failure()
            
            # Store metrics in Redis for monitoring
            await self._store_metrics(node_id, response_time, success, error)
            
        except Exception as e:
            self.logger.error(f"Failed to record request metrics: {e}")
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get load balancer metrics."""
        try:
            total_nodes = len(self.nodes)
            healthy_nodes = len(self.healthy_nodes)
            
            avg_response_time = (
                self.total_response_time / self.request_count 
                if self.request_count > 0 else 0
            )
            
            error_rate = (
                self.error_count / self.request_count 
                if self.request_count > 0 else 0
            )
            
            node_metrics = {}
            for node_id, node in self.nodes.items():
                node_metrics[node_id] = {
                    "status": node.status.value,
                    "load_score": node.load_score,
                    "cpu_usage": node.cpu_usage,
                    "memory_usage": node.memory_usage,
                    "disk_usage": node.disk_usage,
                    "current_connections": node.current_connections,
                    "total_requests": node.total_requests,
                    "error_count": node.error_count,
                    "average_response_time": node.average_response_time
                }
            
            return {
                "total_nodes": total_nodes,
                "healthy_nodes": healthy_nodes,
                "total_requests": self.request_count,
                "error_count": self.error_count,
                "error_rate": error_rate,
                "average_response_time": avg_response_time,
                "strategy": self.config.strategy.value,
                "auto_scaling_enabled": self.config.auto_scaling_enabled,
                "nodes": node_metrics
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get metrics: {e}")
            return {}
    
    def _filter_nodes_by_capabilities(self, capabilities: List[str] = None) -> List[WorkerNode]:
        """Filter nodes by required capabilities."""
        if not capabilities:
            return self.healthy_nodes
        
        filtered_nodes = []
        for node in self.healthy_nodes:
            if all(cap in node.capabilities for cap in capabilities):
                filtered_nodes.append(node)
        
        return filtered_nodes
    
    async def _select_node(self, nodes: List[WorkerNode], request_id: str = None) -> Optional[WorkerNode]:
        """Select node based on configured strategy."""
        if not nodes:
            return None
        
        if self.config.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return self._round_robin_selection(nodes)
        
        elif self.config.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            return self._least_connections_selection(nodes)
        
        elif self.config.strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN:
            return self._weighted_round_robin_selection(nodes)
        
        elif self.config.strategy == LoadBalancingStrategy.RESOURCE_BASED:
            return self._resource_based_selection(nodes)
        
        elif self.config.strategy == LoadBalancingStrategy.CONSISTENT_HASHING:
            return self._consistent_hashing_selection(request_id or str(time.time()))
        
        elif self.config.strategy == LoadBalancingStrategy.ADAPTIVE:
            return await self._adaptive_selection(nodes)
        
        else:
            return self._round_robin_selection(nodes)
    
    def _round_robin_selection(self, nodes: List[WorkerNode]) -> WorkerNode:
        """Round-robin node selection."""
        node = nodes[self.current_index % len(nodes)]
        self.current_index += 1
        return node
    
    def _least_connections_selection(self, nodes: List[WorkerNode]) -> WorkerNode:
        """Least connections node selection."""
        return min(nodes, key=lambda n: n.current_connections)
    
    def _weighted_round_robin_selection(self, nodes: List[WorkerNode]) -> WorkerNode:
        """Weighted round-robin node selection."""
        total_weight = sum(node.weight for node in nodes)
        if total_weight == 0:
            return self._round_robin_selection(nodes)
        
        random_weight = random.uniform(0, total_weight)
        current_weight = 0
        
        for node in nodes:
            current_weight += node.weight
            if current_weight >= random_weight:
                return node
        
        return nodes[-1]
    
    def _resource_based_selection(self, nodes: List[WorkerNode]) -> WorkerNode:
        """Resource-based node selection (lowest load score)."""
        return min(nodes, key=lambda n: n.load_score)
    
    def _consistent_hashing_selection(self, key: str) -> Optional[WorkerNode]:
        """Consistent hashing node selection."""
        return self.hash_ring.get_node(key)
    
    async def _adaptive_selection(self, nodes: List[WorkerNode]) -> WorkerNode:
        """Adaptive node selection based on multiple factors."""
        # Calculate scores for each node
        node_scores = []
        
        for node in nodes:
            # Base score from load
            load_score = node.load_score
            
            # Response time factor
            avg_response_time = node.average_response_time
            response_factor = min(avg_response_time / 1000, 1.0)  # Normalize to 0-1
            
            # Error rate factor
            error_rate = node.error_count / max(node.total_requests, 1)
            
            # Connection factor
            connection_factor = node.current_connections / node.max_connections
            
            # Combined score (lower is better)
            combined_score = (
                load_score * 0.4 +
                response_factor * 0.3 +
                error_rate * 0.2 +
                connection_factor * 0.1
            )
            
            node_scores.append((node, combined_score))
        
        # Select node with lowest score
        best_node = min(node_scores, key=lambda x: x[1])[0]
        return best_node
    
    async def _health_check_loop(self):
        """Background health check loop."""
        while self._running:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(5)
    
    async def _perform_health_checks(self):
        """Perform health checks on all nodes."""
        tasks = []
        for node in self.nodes.values():
            task = asyncio.create_task(self._check_node_health(node))
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        await self._update_healthy_nodes()
    
    async def _check_node_health(self, node: WorkerNode):
        """Check health of a single node."""
        try:
            # Get node metrics
            metrics = await self.health_checker.check_node_health(node.url)
            
            if metrics:
                node.update_metrics(
                    cpu=metrics.get("cpu_usage", 0),
                    memory=metrics.get("memory_usage", 0),
                    disk=metrics.get("disk_usage", 0),
                    connections=metrics.get("active_connections", 0)
                )
                
                # Update status based on health
                if node.is_healthy():
                    if node.status == NodeStatus.UNHEALTHY:
                        node.status = NodeStatus.HEALTHY
                        self.logger.info(f"Node {node.id} recovered")
                else:
                    if node.status == NodeStatus.HEALTHY:
                        node.status = NodeStatus.DEGRADED
                        self.logger.warning(f"Node {node.id} degraded")
            else:
                # Health check failed
                if node.status in [NodeStatus.HEALTHY, NodeStatus.DEGRADED]:
                    node.status = NodeStatus.UNHEALTHY
                    self.logger.error(f"Node {node.id} became unhealthy")
        
        except Exception as e:
            self.logger.error(f"Health check failed for node {node.id}: {e}")
            if node.status in [NodeStatus.HEALTHY, NodeStatus.DEGRADED]:
                node.status = NodeStatus.UNHEALTHY
    
    async def _update_healthy_nodes(self):
        """Update the list of healthy nodes."""
        self.healthy_nodes = [
            node for node in self.nodes.values()
            if node.status in [NodeStatus.HEALTHY, NodeStatus.DEGRADED]
        ]
    
    async def _auto_scale_loop(self):
        """Background auto-scaling loop."""
        while self._running:
            try:
                await self._check_auto_scaling()
                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Auto-scaling loop error: {e}")
                await asyncio.sleep(30)
    
    async def _check_auto_scaling(self):
        """Check if auto-scaling is needed."""
        if not self.config.auto_scaling_enabled:
            return
        
        current_time = time.time()
        if current_time - self.last_scale_action < self.config.scale_cooldown:
            return
        
        with self.scaling_lock:
            # Calculate average load across healthy nodes
            if not self.healthy_nodes:
                return
            
            avg_load = sum(node.load_score for node in self.healthy_nodes) / len(self.healthy_nodes)
            
            # Scale up if load is high
            if (avg_load > self.config.scale_up_threshold and 
                len(self.healthy_nodes) < self.config.max_nodes):
                await self._scale_up()
                self.last_scale_action = current_time
            
            # Scale down if load is low
            elif (avg_load < self.config.scale_down_threshold and 
                  len(self.healthy_nodes) > self.config.min_nodes):
                await self._scale_down()
                self.last_scale_action = current_time
    
    async def _scale_up(self):
        """Scale up by adding a new node."""
        try:
            # This would typically integrate with container orchestration
            # For now, we'll log the scaling decision
            self.logger.info("Auto-scaling: Scale up triggered")
            
            # In a real implementation, this would:
            # 1. Request new container/VM from orchestrator
            # 2. Wait for it to be ready
            # 3. Add it to the load balancer
            
            # Placeholder for actual scaling logic
            await self._request_new_node()
            
        except Exception as e:
            self.logger.error(f"Scale up failed: {e}")
    
    async def _scale_down(self):
        """Scale down by removing a node."""
        try:
            # Find the least loaded node
            least_loaded_node = min(self.healthy_nodes, key=lambda n: n.load_score)
            
            self.logger.info(f"Auto-scaling: Scale down triggered, removing node {least_loaded_node.id}")
            
            # Gracefully drain the node
            await self._drain_node(least_loaded_node)
            
            # Remove from load balancer
            await self.remove_node(least_loaded_node.id)
            
            # In a real implementation, this would also:
            # 1. Signal orchestrator to terminate the container/VM
            
        except Exception as e:
            self.logger.error(f"Scale down failed: {e}")
    
    async def _request_new_node(self):
        """Request a new node from the orchestrator."""
        # Placeholder for orchestrator integration
        # This would typically call Kubernetes API, Docker Swarm, etc.
        pass
    
    async def _drain_node(self, node: WorkerNode):
        """Gracefully drain a node before removal."""
        try:
            # Mark node as draining
            node.status = NodeStatus.MAINTENANCE
            
            # Wait for existing connections to finish
            timeout = 30  # seconds
            start_time = time.time()
            
            while node.current_connections > 0 and time.time() - start_time < timeout:
                await asyncio.sleep(1)
            
            self.logger.info(f"Node {node.id} drained successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to drain node {node.id}: {e}")
    
    async def _validate_node(self, node: WorkerNode) -> bool:
        """Validate a node before adding it."""
        try:
            # Check if node is reachable
            health_status = await self.health_checker.check_node_health(node.url)
            return health_status is not None
        except Exception:
            return False
    
    async def _load_nodes_from_db(self):
        """Load existing nodes from database."""
        try:
            rows = await self.db.fetch_all(
                "SELECT * FROM worker_nodes WHERE status != 'offline'"
            )
            
            for row in rows:
                node = WorkerNode(
                    id=row["id"],
                    host=row["host"],
                    port=row["port"],
                    weight=row["weight"],
                    max_connections=row["max_connections"],
                    capabilities=json.loads(row["capabilities"] or "[]"),
                    metadata=json.loads(row["metadata"] or "{}")
                )
                
                await self.add_node(node)
        
        except Exception as e:
            self.logger.error(f"Failed to load nodes from database: {e}")
    
    async def _save_node_to_db(self, node: WorkerNode):
        """Save node to database."""
        try:
            await self.db.execute(
                """
                INSERT INTO worker_nodes (id, host, port, weight, max_connections, 
                                        capabilities, metadata, status, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (id) DO UPDATE SET
                    host = $2, port = $3, weight = $4, max_connections = $5,
                    capabilities = $6, metadata = $7, status = $8, updated_at = NOW()
                """,
                node.id, node.host, node.port, node.weight, node.max_connections,
                json.dumps(node.capabilities), json.dumps(node.metadata),
                node.status.value, datetime.now()
            )
        except Exception as e:
            self.logger.error(f"Failed to save node to database: {e}")
    
    async def _remove_node_from_db(self, node_id: str):
        """Remove node from database."""
        try:
            await self.db.execute(
                "UPDATE worker_nodes SET status = 'offline', updated_at = NOW() WHERE id = $1",
                node_id
            )
        except Exception as e:
            self.logger.error(f"Failed to remove node from database: {e}")
    
    async def _store_metrics(self, node_id: str, response_time: float, 
                           success: bool, error: str = None):
        """Store metrics in Redis."""
        try:
            metrics_key = f"lb_metrics:{node_id}:{int(time.time() // 60)}"  # Per minute
            
            await self.redis_utils.hincrby(metrics_key, "requests", 1)
            await self.redis_utils.hincrbyfloat(metrics_key, "response_time", response_time)
            
            if not success:
                await self.redis_utils.hincrby(metrics_key, "errors", 1)
            
            # Set expiration
            await self.redis_utils.expire(metrics_key, 3600)  # 1 hour
            
        except Exception as e:
            self.logger.error(f"Failed to store metrics: {e}")
    
    async def _cleanup_sticky_sessions(self):
        """Clean up expired sticky sessions."""
        try:
            current_time = time.time()
            expired_sessions = []
            
            for session_id in self.sticky_sessions:
                # In a real implementation, you'd check session timestamp
                # For now, we'll just clean up sessions for offline nodes
                node_id = self.sticky_sessions[session_id]
                if node_id not in self.nodes or not self.nodes[node_id].is_healthy():
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self.sticky_sessions[session_id]
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup sticky sessions: {e}")


# Global load balancer instance
_load_balancer = None


def get_load_balancer() -> LoadBalancer:
    """Get the global load balancer instance."""
    global _load_balancer
    if _load_balancer is None:
        _load_balancer = LoadBalancer()
    return _load_balancer