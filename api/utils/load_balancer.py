"""Comprehensive load balancing and horizontal scaling system.

Provides:
- Multiple load balancing algorithms
- Service discovery and registration
- Health-aware load balancing
- Auto-scaling capabilities
- Request routing and distribution
- Performance monitoring
- Failover and recovery
"""

import asyncio
import time
import random
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from urllib.parse import urlparse

import aiohttp
from pydantic import BaseModel

from api.utils.enhanced_logging import get_logger
from api.config.production import get_settings
from api.utils.health_checker import get_health_checker, HealthStatus
from api.utils.resource_monitor import get_resource_monitor


logger = get_logger(__name__)
settings = get_settings()


class LoadBalancingAlgorithm(str, Enum):
    """Load balancing algorithms."""
    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_LEAST_CONNECTIONS = "weighted_least_connections"
    LEAST_RESPONSE_TIME = "least_response_time"
    WEIGHTED_RESPONSE_TIME = "weighted_response_time"
    RANDOM = "random"
    WEIGHTED_RANDOM = "weighted_random"
    CONSISTENT_HASH = "consistent_hash"
    IP_HASH = "ip_hash"
    RESOURCE_BASED = "resource_based"
    ADAPTIVE = "adaptive"


class ServiceStatus(str, Enum):
    """Service status for load balancing."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DRAINING = "draining"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class ScalingDirection(str, Enum):
    """Auto-scaling directions."""
    UP = "up"
    DOWN = "down"
    NONE = "none"


class ScalingTrigger(str, Enum):
    """Auto-scaling triggers."""
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    REQUEST_RATE = "request_rate"
    RESPONSE_TIME = "response_time"
    QUEUE_LENGTH = "queue_length"
    CUSTOM_METRIC = "custom_metric"


@dataclass
class ServiceEndpoint:
    """Service endpoint configuration."""
    id: str
    host: str
    port: int
    weight: float = 1.0
    max_connections: int = 100
    timeout: float = 30.0
    
    # Status tracking
    status: ServiceStatus = ServiceStatus.UNKNOWN
    current_connections: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    last_response_time: float = 0.0
    average_response_time: float = 0.0
    last_health_check: Optional[datetime] = None
    
    # Metadata
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def url(self) -> str:
        """Get the full URL for this endpoint."""
        return f"http://{self.host}:{self.port}"
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_requests == 0:
            return 100.0
        return ((self.total_requests - self.failed_requests) / self.total_requests) * 100
    
    @property
    def load_factor(self) -> float:
        """Calculate current load factor (0.0 to 1.0)."""
        if self.max_connections == 0:
            return 0.0
        return min(self.current_connections / self.max_connections, 1.0)
    
    def is_available(self) -> bool:
        """Check if endpoint is available for requests."""
        return (
            self.status == ServiceStatus.HEALTHY and
            self.current_connections < self.max_connections
        )
    
    def update_metrics(self, response_time: float, success: bool):
        """Update endpoint metrics."""
        self.total_requests += 1
        if not success:
            self.failed_requests += 1
        
        self.last_response_time = response_time
        
        # Update average response time (exponential moving average)
        alpha = 0.1
        if self.average_response_time == 0:
            self.average_response_time = response_time
        else:
            self.average_response_time = (
                alpha * response_time + (1 - alpha) * self.average_response_time
            )


@dataclass
class LoadBalancerConfig:
    """Load balancer configuration."""
    algorithm: LoadBalancingAlgorithm = LoadBalancingAlgorithm.ROUND_ROBIN
    health_check_interval: float = 30.0
    health_check_timeout: float = 5.0
    health_check_path: str = "/health"
    
    # Failover settings
    max_retries: int = 3
    retry_delay: float = 1.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 60.0
    
    # Session affinity
    session_affinity: bool = False
    session_cookie_name: str = "lb_session"
    session_timeout: float = 3600.0  # 1 hour
    
    # Request routing
    sticky_sessions: bool = False
    hash_key_header: Optional[str] = None
    
    # Performance settings
    connection_pool_size: int = 100
    request_timeout: float = 30.0
    

@dataclass
class ScalingPolicy:
    """Auto-scaling policy configuration."""
    enabled: bool = True
    min_instances: int = 1
    max_instances: int = 10
    
    # Scaling triggers
    scale_up_threshold: float = 70.0  # percentage
    scale_down_threshold: float = 30.0  # percentage
    scale_up_cooldown: float = 300.0  # 5 minutes
    scale_down_cooldown: float = 600.0  # 10 minutes
    
    # Scaling behavior
    scale_up_step: int = 1
    scale_down_step: int = 1
    evaluation_period: float = 60.0  # 1 minute
    evaluation_periods: int = 3  # Number of periods to evaluate
    
    # Triggers
    triggers: List[ScalingTrigger] = field(default_factory=lambda: [ScalingTrigger.CPU_USAGE])
    custom_metrics: Dict[str, float] = field(default_factory=dict)


class RequestMetrics(BaseModel):
    """Request metrics for monitoring."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    min_response_time: float = float('inf')
    max_response_time: float = 0.0
    requests_per_second: float = 0.0
    
    # Time-based metrics
    last_request_time: Optional[datetime] = None
    start_time: datetime = field(default_factory=datetime.utcnow)
    
    def update(self, response_time: float, success: bool):
        """Update metrics with new request data."""
        self.total_requests += 1
        self.last_request_time = datetime.utcnow()
        
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
        
        # Update response time metrics
        self.min_response_time = min(self.min_response_time, response_time)
        self.max_response_time = max(self.max_response_time, response_time)
        
        # Update average (exponential moving average)
        alpha = 0.1
        if self.average_response_time == 0:
            self.average_response_time = response_time
        else:
            self.average_response_time = (
                alpha * response_time + (1 - alpha) * self.average_response_time
            )
        
        # Calculate requests per second
        elapsed = (datetime.utcnow() - self.start_time).total_seconds()
        if elapsed > 0:
            self.requests_per_second = self.total_requests / elapsed
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100


class LoadBalancer:
    """Advanced load balancer with multiple algorithms and health checking."""
    
    def __init__(self, config: LoadBalancerConfig):
        self.config = config
        self.endpoints: List[ServiceEndpoint] = []
        self.metrics = RequestMetrics()
        
        # Algorithm state
        self.current_index = 0
        self.connection_counts: Dict[str, int] = defaultdict(int)
        self.response_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Session management
        self.sessions: Dict[str, str] = {}  # session_id -> endpoint_id
        self.session_timestamps: Dict[str, datetime] = {}
        
        # Health checking
        self.health_check_task: Optional[asyncio.Task] = None
        self.circuit_breakers: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # HTTP session for health checks
        self.session: Optional[aiohttp.ClientSession] = None
        
        logger.info(f"Load balancer initialized with {config.algorithm.value} algorithm")
    
    async def start(self):
        """Start the load balancer."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.request_timeout),
            connector=aiohttp.TCPConnector(limit=self.config.connection_pool_size)
        )
        
        # Start health checking
        if self.config.health_check_interval > 0:
            self.health_check_task = asyncio.create_task(self._health_check_loop())
        
        logger.info("Load balancer started")
    
    async def stop(self):
        """Stop the load balancer."""
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
        
        if self.session:
            await self.session.close()
        
        logger.info("Load balancer stopped")
    
    def add_endpoint(self, endpoint: ServiceEndpoint):
        """Add a service endpoint."""
        self.endpoints.append(endpoint)
        self.connection_counts[endpoint.id] = 0
        self.response_times[endpoint.id] = deque(maxlen=100)
        
        # Initialize circuit breaker
        self.circuit_breakers[endpoint.id] = {
            'failures': 0,
            'last_failure': None,
            'state': 'closed'  # closed, open, half-open
        }
        
        logger.info(f"Added endpoint: {endpoint.id} ({endpoint.url})")
    
    def remove_endpoint(self, endpoint_id: str):
        """Remove a service endpoint."""
        self.endpoints = [ep for ep in self.endpoints if ep.id != endpoint_id]
        
        if endpoint_id in self.connection_counts:
            del self.connection_counts[endpoint_id]
        if endpoint_id in self.response_times:
            del self.response_times[endpoint_id]
        if endpoint_id in self.circuit_breakers:
            del self.circuit_breakers[endpoint_id]
        
        logger.info(f"Removed endpoint: {endpoint_id}")
    
    def get_available_endpoints(self) -> List[ServiceEndpoint]:
        """Get list of available endpoints."""
        available = []
        
        for endpoint in self.endpoints:
            # Check circuit breaker
            cb = self.circuit_breakers[endpoint.id]
            if cb['state'] == 'open':
                # Check if we should try half-open
                if (cb['last_failure'] and 
                    time.time() - cb['last_failure'] > self.config.circuit_breaker_timeout):
                    cb['state'] = 'half-open'
                    logger.info(f"Circuit breaker half-open for {endpoint.id}")
                else:
                    continue
            
            if endpoint.is_available():
                available.append(endpoint)
        
        return available
    
    async def select_endpoint(self, request_context: Optional[Dict[str, Any]] = None) -> Optional[ServiceEndpoint]:
        """Select an endpoint based on the configured algorithm."""
        available_endpoints = self.get_available_endpoints()
        
        if not available_endpoints:
            logger.warning("No available endpoints")
            return None
        
        request_context = request_context or {}
        
        # Check for session affinity
        if self.config.session_affinity or self.config.sticky_sessions:
            session_id = request_context.get('session_id')
            if session_id and session_id in self.sessions:
                endpoint_id = self.sessions[session_id]
                endpoint = next((ep for ep in available_endpoints if ep.id == endpoint_id), None)
                if endpoint:
                    return endpoint
        
        # Select based on algorithm
        if self.config.algorithm == LoadBalancingAlgorithm.ROUND_ROBIN:
            return self._round_robin_select(available_endpoints)
        
        elif self.config.algorithm == LoadBalancingAlgorithm.WEIGHTED_ROUND_ROBIN:
            return self._weighted_round_robin_select(available_endpoints)
        
        elif self.config.algorithm == LoadBalancingAlgorithm.LEAST_CONNECTIONS:
            return self._least_connections_select(available_endpoints)
        
        elif self.config.algorithm == LoadBalancingAlgorithm.WEIGHTED_LEAST_CONNECTIONS:
            return self._weighted_least_connections_select(available_endpoints)
        
        elif self.config.algorithm == LoadBalancingAlgorithm.LEAST_RESPONSE_TIME:
            return self._least_response_time_select(available_endpoints)
        
        elif self.config.algorithm == LoadBalancingAlgorithm.WEIGHTED_RESPONSE_TIME:
            return self._weighted_response_time_select(available_endpoints)
        
        elif self.config.algorithm == LoadBalancingAlgorithm.RANDOM:
            return random.choice(available_endpoints)
        
        elif self.config.algorithm == LoadBalancingAlgorithm.WEIGHTED_RANDOM:
            return self._weighted_random_select(available_endpoints)
        
        elif self.config.algorithm == LoadBalancingAlgorithm.CONSISTENT_HASH:
            return self._consistent_hash_select(available_endpoints, request_context)
        
        elif self.config.algorithm == LoadBalancingAlgorithm.IP_HASH:
            return self._ip_hash_select(available_endpoints, request_context)
        
        elif self.config.algorithm == LoadBalancingAlgorithm.RESOURCE_BASED:
            return self._resource_based_select(available_endpoints)
        
        elif self.config.algorithm == LoadBalancingAlgorithm.ADAPTIVE:
            return self._adaptive_select(available_endpoints)
        
        else:
            return available_endpoints[0]
    
    def _round_robin_select(self, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        """Round-robin selection."""
        endpoint = endpoints[self.current_index % len(endpoints)]
        self.current_index += 1
        return endpoint
    
    def _weighted_round_robin_select(self, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        """Weighted round-robin selection."""
        total_weight = sum(ep.weight for ep in endpoints)
        if total_weight == 0:
            return self._round_robin_select(endpoints)
        
        # Create weighted list
        weighted_endpoints = []
        for endpoint in endpoints:
            count = max(1, int(endpoint.weight * 10))  # Scale weights
            weighted_endpoints.extend([endpoint] * count)
        
        if not weighted_endpoints:
            return endpoints[0]
        
        endpoint = weighted_endpoints[self.current_index % len(weighted_endpoints)]
        self.current_index += 1
        return endpoint
    
    def _least_connections_select(self, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        """Least connections selection."""
        return min(endpoints, key=lambda ep: ep.current_connections)
    
    def _weighted_least_connections_select(self, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        """Weighted least connections selection."""
        def score(ep):
            if ep.weight == 0:
                return float('inf')
            return ep.current_connections / ep.weight
        
        return min(endpoints, key=score)
    
    def _least_response_time_select(self, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        """Least response time selection."""
        return min(endpoints, key=lambda ep: ep.average_response_time or 0)
    
    def _weighted_response_time_select(self, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        """Weighted response time selection."""
        def score(ep):
            if ep.weight == 0:
                return float('inf')
            return (ep.average_response_time or 0) / ep.weight
        
        return min(endpoints, key=score)
    
    def _weighted_random_select(self, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        """Weighted random selection."""
        total_weight = sum(ep.weight for ep in endpoints)
        if total_weight == 0:
            return random.choice(endpoints)
        
        r = random.uniform(0, total_weight)
        current_weight = 0
        
        for endpoint in endpoints:
            current_weight += endpoint.weight
            if r <= current_weight:
                return endpoint
        
        return endpoints[-1]
    
    def _consistent_hash_select(self, endpoints: List[ServiceEndpoint], context: Dict[str, Any]) -> ServiceEndpoint:
        """Consistent hash selection."""
        hash_key = context.get('hash_key', '')
        if not hash_key:
            # Use client IP or session ID as fallback
            hash_key = context.get('client_ip', context.get('session_id', str(time.time())))
        
        # Simple consistent hashing
        hash_value = int(hashlib.md5(hash_key.encode()).hexdigest(), 16)
        return endpoints[hash_value % len(endpoints)]
    
    def _ip_hash_select(self, endpoints: List[ServiceEndpoint], context: Dict[str, Any]) -> ServiceEndpoint:
        """IP hash selection."""
        client_ip = context.get('client_ip', '127.0.0.1')
        hash_value = int(hashlib.md5(client_ip.encode()).hexdigest(), 16)
        return endpoints[hash_value % len(endpoints)]
    
    def _resource_based_select(self, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        """Resource-based selection considering load factor."""
        def score(ep):
            # Lower score is better
            load_score = ep.load_factor * 100
            response_score = ep.average_response_time or 0
            failure_score = (ep.failed_requests / max(ep.total_requests, 1)) * 100
            
            return load_score + response_score + failure_score
        
        return min(endpoints, key=score)
    
    def _adaptive_select(self, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        """Adaptive selection based on multiple factors."""
        def score(ep):
            # Combine multiple factors with weights
            connection_score = ep.current_connections / max(ep.max_connections, 1) * 30
            response_score = (ep.average_response_time or 0) * 20
            failure_score = (ep.failed_requests / max(ep.total_requests, 1)) * 100 * 25
            load_score = ep.load_factor * 25
            
            return connection_score + response_score + failure_score + load_score
        
        return min(endpoints, key=score)
    
    async def make_request(self, method: str, path: str, **kwargs) -> Tuple[Optional[Any], ServiceEndpoint]:
        """Make a request through the load balancer."""
        request_context = kwargs.pop('request_context', {})
        
        for attempt in range(self.config.max_retries + 1):
            endpoint = await self.select_endpoint(request_context)
            
            if not endpoint:
                raise Exception("No available endpoints")
            
            start_time = time.time()
            success = False
            response = None
            error = None
            
            try:
                # Track connection
                endpoint.current_connections += 1
                self.connection_counts[endpoint.id] += 1
                
                # Make request
                url = f"{endpoint.url}{path}"
                
                async with self.session.request(method, url, **kwargs) as resp:
                    response_time = time.time() - start_time
                    
                    if resp.status < 400:
                        success = True
                        response = await resp.json() if 'application/json' in resp.headers.get('content-type', '') else await resp.text()
                        
                        # Update circuit breaker on success
                        cb = self.circuit_breakers[endpoint.id]
                        if cb['state'] == 'half-open':
                            cb['state'] = 'closed'
                            cb['failures'] = 0
                            logger.info(f"Circuit breaker closed for {endpoint.id}")
                    else:
                        error = f"HTTP {resp.status}: {await resp.text()}"
                
            except Exception as e:
                response_time = time.time() - start_time
                error = str(e)
                
                # Update circuit breaker on failure
                cb = self.circuit_breakers[endpoint.id]
                cb['failures'] += 1
                cb['last_failure'] = time.time()
                
                if cb['failures'] >= self.config.circuit_breaker_threshold:
                    cb['state'] = 'open'
                    logger.warning(f"Circuit breaker opened for {endpoint.id}")
            
            finally:
                # Update metrics
                endpoint.current_connections -= 1
                endpoint.update_metrics(response_time, success)
                self.metrics.update(response_time, success)
                
                # Store response time
                self.response_times[endpoint.id].append(response_time)
            
            if success:
                # Handle session affinity
                if self.config.session_affinity:
                    session_id = request_context.get('session_id')
                    if session_id:
                        self.sessions[session_id] = endpoint.id
                        self.session_timestamps[session_id] = datetime.utcnow()
                
                return response, endpoint
            
            # If not successful and we have retries left, wait and try again
            if attempt < self.config.max_retries:
                await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                logger.warning(f"Request failed, retrying ({attempt + 1}/{self.config.max_retries}): {error}")
        
        raise Exception(f"Request failed after {self.config.max_retries} retries: {error}")
    
    async def _health_check_loop(self):
        """Background health checking loop."""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._perform_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
    
    async def _perform_health_checks(self):
        """Perform health checks on all endpoints."""
        tasks = []
        
        for endpoint in self.endpoints:
            task = asyncio.create_task(self._check_endpoint_health(endpoint))
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _check_endpoint_health(self, endpoint: ServiceEndpoint):
        """Check health of a single endpoint."""
        try:
            url = f"{endpoint.url}{self.config.health_check_path}"
            
            async with self.session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=self.config.health_check_timeout)
            ) as response:
                
                if response.status == 200:
                    if endpoint.status != ServiceStatus.HEALTHY:
                        logger.info(f"Endpoint {endpoint.id} is now healthy")
                    endpoint.status = ServiceStatus.HEALTHY
                else:
                    if endpoint.status != ServiceStatus.UNHEALTHY:
                        logger.warning(f"Endpoint {endpoint.id} health check failed: HTTP {response.status}")
                    endpoint.status = ServiceStatus.UNHEALTHY
                
                endpoint.last_health_check = datetime.utcnow()
                
        except Exception as e:
            if endpoint.status != ServiceStatus.UNHEALTHY:
                logger.warning(f"Endpoint {endpoint.id} health check failed: {e}")
            endpoint.status = ServiceStatus.UNHEALTHY
            endpoint.last_health_check = datetime.utcnow()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get load balancer metrics."""
        return {
            'algorithm': self.config.algorithm.value,
            'total_endpoints': len(self.endpoints),
            'healthy_endpoints': len([ep for ep in self.endpoints if ep.status == ServiceStatus.HEALTHY]),
            'unhealthy_endpoints': len([ep for ep in self.endpoints if ep.status == ServiceStatus.UNHEALTHY]),
            'request_metrics': self.metrics.dict(),
            'endpoints': [
                {
                    'id': ep.id,
                    'url': ep.url,
                    'status': ep.status.value,
                    'weight': ep.weight,
                    'current_connections': ep.current_connections,
                    'total_requests': ep.total_requests,
                    'success_rate': ep.success_rate,
                    'average_response_time': ep.average_response_time,
                    'load_factor': ep.load_factor
                }
                for ep in self.endpoints
            ],
            'circuit_breakers': {
                ep_id: cb for ep_id, cb in self.circuit_breakers.items()
            }
        }
    
    def cleanup_sessions(self):
        """Clean up expired sessions."""
        now = datetime.utcnow()
        expired_sessions = []
        
        for session_id, timestamp in self.session_timestamps.items():
            if (now - timestamp).total_seconds() > self.config.session_timeout:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
            del self.session_timestamps[session_id]
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")


class AutoScaler:
    """Auto-scaling manager for horizontal scaling."""
    
    def __init__(self, policy: ScalingPolicy):
        self.policy = policy
        self.current_instances = policy.min_instances
        self.last_scale_up = datetime.utcnow() - timedelta(seconds=policy.scale_up_cooldown)
        self.last_scale_down = datetime.utcnow() - timedelta(seconds=policy.scale_down_cooldown)
        
        # Metrics history for evaluation
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=policy.evaluation_periods))
        
        # Scaling callbacks
        self.scale_up_callback: Optional[Callable] = None
        self.scale_down_callback: Optional[Callable] = None
        
        logger.info(f"Auto-scaler initialized with {policy.min_instances}-{policy.max_instances} instances")
    
    def set_scale_callbacks(self, scale_up: Callable, scale_down: Callable):
        """Set callbacks for scaling operations."""
        self.scale_up_callback = scale_up
        self.scale_down_callback = scale_down
    
    async def evaluate_scaling(self, metrics: Dict[str, float]) -> ScalingDirection:
        """Evaluate if scaling is needed based on metrics."""
        if not self.policy.enabled:
            return ScalingDirection.NONE
        
        # Store metrics
        for metric_name, value in metrics.items():
            self.metrics_history[metric_name].append(value)
        
        # Check if we have enough data points
        if len(self.metrics_history[list(metrics.keys())[0]]) < self.policy.evaluation_periods:
            return ScalingDirection.NONE
        
        # Evaluate each trigger
        scale_up_signals = 0
        scale_down_signals = 0
        
        for trigger in self.policy.triggers:
            if trigger == ScalingTrigger.CPU_USAGE:
                cpu_values = list(self.metrics_history.get('cpu_usage', []))
                if cpu_values and all(v > self.policy.scale_up_threshold for v in cpu_values[-self.policy.evaluation_periods:]):
                    scale_up_signals += 1
                elif cpu_values and all(v < self.policy.scale_down_threshold for v in cpu_values[-self.policy.evaluation_periods:]):
                    scale_down_signals += 1
            
            elif trigger == ScalingTrigger.MEMORY_USAGE:
                memory_values = list(self.metrics_history.get('memory_usage', []))
                if memory_values and all(v > self.policy.scale_up_threshold for v in memory_values[-self.policy.evaluation_periods:]):
                    scale_up_signals += 1
                elif memory_values and all(v < self.policy.scale_down_threshold for v in memory_values[-self.policy.evaluation_periods:]):
                    scale_down_signals += 1
            
            elif trigger == ScalingTrigger.REQUEST_RATE:
                request_values = list(self.metrics_history.get('request_rate', []))
                if request_values and all(v > self.policy.scale_up_threshold for v in request_values[-self.policy.evaluation_periods:]):
                    scale_up_signals += 1
                elif request_values and all(v < self.policy.scale_down_threshold for v in request_values[-self.policy.evaluation_periods:]):
                    scale_down_signals += 1
            
            elif trigger == ScalingTrigger.RESPONSE_TIME:
                response_values = list(self.metrics_history.get('response_time', []))
                if response_values and all(v > self.policy.scale_up_threshold for v in response_values[-self.policy.evaluation_periods:]):
                    scale_up_signals += 1
                elif response_values and all(v < self.policy.scale_down_threshold for v in response_values[-self.policy.evaluation_periods:]):
                    scale_down_signals += 1
        
        # Determine scaling direction
        now = datetime.utcnow()
        
        if scale_up_signals > 0 and self.current_instances < self.policy.max_instances:
            # Check cooldown
            if (now - self.last_scale_up).total_seconds() >= self.policy.scale_up_cooldown:
                return ScalingDirection.UP
        
        elif scale_down_signals > 0 and self.current_instances > self.policy.min_instances:
            # Check cooldown
            if (now - self.last_scale_down).total_seconds() >= self.policy.scale_down_cooldown:
                return ScalingDirection.DOWN
        
        return ScalingDirection.NONE
    
    async def scale(self, direction: ScalingDirection) -> bool:
        """Perform scaling operation."""
        if direction == ScalingDirection.NONE:
            return False
        
        now = datetime.utcnow()
        
        if direction == ScalingDirection.UP:
            if self.current_instances >= self.policy.max_instances:
                logger.warning("Cannot scale up: already at maximum instances")
                return False
            
            new_instances = min(
                self.current_instances + self.policy.scale_up_step,
                self.policy.max_instances
            )
            
            if self.scale_up_callback:
                try:
                    await self.scale_up_callback(new_instances - self.current_instances)
                    self.current_instances = new_instances
                    self.last_scale_up = now
                    logger.info(f"Scaled up to {self.current_instances} instances")
                    return True
                except Exception as e:
                    logger.error(f"Scale up failed: {e}")
                    return False
        
        elif direction == ScalingDirection.DOWN:
            if self.current_instances <= self.policy.min_instances:
                logger.warning("Cannot scale down: already at minimum instances")
                return False
            
            new_instances = max(
                self.current_instances - self.policy.scale_down_step,
                self.policy.min_instances
            )
            
            if self.scale_down_callback:
                try:
                    await self.scale_down_callback(self.current_instances - new_instances)
                    self.current_instances = new_instances
                    self.last_scale_down = now
                    logger.info(f"Scaled down to {self.current_instances} instances")
                    return True
                except Exception as e:
                    logger.error(f"Scale down failed: {e}")
                    return False
        
        return False
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get auto-scaler metrics."""
        return {
            'enabled': self.policy.enabled,
            'current_instances': self.current_instances,
            'min_instances': self.policy.min_instances,
            'max_instances': self.policy.max_instances,
            'last_scale_up': self.last_scale_up.isoformat(),
            'last_scale_down': self.last_scale_down.isoformat(),
            'metrics_history': {
                name: list(values) for name, values in self.metrics_history.items()
            }
        }


class LoadBalancingService:
    """Main service coordinating load balancing and auto-scaling."""
    
    def __init__(self, lb_config: LoadBalancerConfig, scaling_policy: Optional[ScalingPolicy] = None):
        self.load_balancer = LoadBalancer(lb_config)
        self.auto_scaler = AutoScaler(scaling_policy) if scaling_policy else None
        
        # Monitoring
        self.monitoring_task: Optional[asyncio.Task] = None
        self.monitoring_interval = 60.0  # 1 minute
        
        logger.info("Load balancing service initialized")
    
    async def start(self):
        """Start the load balancing service."""
        await self.load_balancer.start()
        
        # Set up auto-scaling callbacks
        if self.auto_scaler:
            self.auto_scaler.set_scale_callbacks(
                self._scale_up_callback,
                self._scale_down_callback
            )
        
        # Start monitoring
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info("Load balancing service started")
    
    async def stop(self):
        """Stop the load balancing service."""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        await self.load_balancer.stop()
        
        logger.info("Load balancing service stopped")
    
    async def _monitoring_loop(self):
        """Background monitoring and auto-scaling loop."""
        while True:
            try:
                await asyncio.sleep(self.monitoring_interval)
                
                if self.auto_scaler:
                    # Collect metrics
                    metrics = await self._collect_metrics()
                    
                    # Evaluate scaling
                    direction = await self.auto_scaler.evaluate_scaling(metrics)
                    
                    # Perform scaling if needed
                    if direction != ScalingDirection.NONE:
                        await self.auto_scaler.scale(direction)
                
                # Clean up sessions
                self.load_balancer.cleanup_sessions()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
    
    async def _collect_metrics(self) -> Dict[str, float]:
        """Collect metrics for auto-scaling decisions."""
        metrics = {}
        
        try:
            # Get resource metrics
            resource_monitor = get_resource_monitor()
            
            # CPU usage
            cpu_usage = resource_monitor.get_cpu_usage()
            metrics['cpu_usage'] = cpu_usage
            
            # Memory usage
            memory_usage = resource_monitor.get_memory_usage()
            metrics['memory_usage'] = memory_usage
            
            # Request rate
            lb_metrics = self.load_balancer.metrics
            metrics['request_rate'] = lb_metrics.requests_per_second
            
            # Average response time
            metrics['response_time'] = lb_metrics.average_response_time
            
            # Queue length (if available)
            # This would need to be implemented based on your queue system
            metrics['queue_length'] = 0
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
        
        return metrics
    
    async def _scale_up_callback(self, instances_to_add: int):
        """Callback for scaling up instances."""
        # This would typically involve:
        # 1. Starting new service instances
        # 2. Registering them with service discovery
        # 3. Adding them to the load balancer
        
        logger.info(f"Scaling up: adding {instances_to_add} instances")
        
        # Placeholder implementation
        for i in range(instances_to_add):
            # In a real implementation, you would start new instances here
            # For now, we'll just log the action
            logger.info(f"Would start new instance {i + 1}")
    
    async def _scale_down_callback(self, instances_to_remove: int):
        """Callback for scaling down instances."""
        # This would typically involve:
        # 1. Gracefully draining connections from instances
        # 2. Removing them from the load balancer
        # 3. Stopping the service instances
        
        logger.info(f"Scaling down: removing {instances_to_remove} instances")
        
        # Placeholder implementation
        for i in range(instances_to_remove):
            # In a real implementation, you would stop instances here
            # For now, we'll just log the action
            logger.info(f"Would stop instance {i + 1}")
    
    def add_endpoint(self, endpoint: ServiceEndpoint):
        """Add a service endpoint."""
        self.load_balancer.add_endpoint(endpoint)
    
    def remove_endpoint(self, endpoint_id: str):
        """Remove a service endpoint."""
        self.load_balancer.remove_endpoint(endpoint_id)
    
    async def make_request(self, method: str, path: str, **kwargs):
        """Make a request through the load balancer."""
        return await self.load_balancer.make_request(method, path, **kwargs)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics."""
        metrics = {
            'load_balancer': self.load_balancer.get_metrics(),
            'auto_scaler': self.auto_scaler.get_metrics() if self.auto_scaler else None
        }
        
        return metrics


# Global load balancing service
load_balancing_service: Optional[LoadBalancingService] = None


def get_load_balancing_service() -> Optional[LoadBalancingService]:
    """Get the global load balancing service."""
    return load_balancing_service


def initialize_load_balancing(
    lb_config: LoadBalancerConfig,
    scaling_policy: Optional[ScalingPolicy] = None
) -> LoadBalancingService:
    """Initialize the global load balancing service."""
    global load_balancing_service
    
    load_balancing_service = LoadBalancingService(lb_config, scaling_policy)
    
    logger.info("Global load balancing service initialized")
    return load_balancing_service


# Utility functions
def create_default_lb_config() -> LoadBalancerConfig:
    """Create default load balancer configuration."""
    return LoadBalancerConfig(
        algorithm=LoadBalancingAlgorithm.WEIGHTED_LEAST_CONNECTIONS,
        health_check_interval=30.0,
        max_retries=3,
        circuit_breaker_threshold=5
    )


def create_default_scaling_policy() -> ScalingPolicy:
    """Create default auto-scaling policy."""
    return ScalingPolicy(
        min_instances=2,
        max_instances=10,
        scale_up_threshold=70.0,
        scale_down_threshold=30.0,
        triggers=[ScalingTrigger.CPU_USAGE, ScalingTrigger.MEMORY_USAGE]
    )