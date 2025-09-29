"""Circuit breaker pattern implementation for enhanced error recovery.

Provides:
- Circuit breaker with configurable failure thresholds
- Automatic recovery and health checking
- Fallback mechanisms and graceful degradation
- Metrics collection and monitoring
- Integration with external services
- Adaptive timeout and retry strategies
"""

import asyncio
import time
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, TypeVar, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
from functools import wraps
from contextlib import asynccontextmanager

from pydantic import BaseModel

from api.utils.enhanced_logging import get_logger, SecurityEvent
from api.config.production import get_settings
from api.utils.redis_client import get_redis_client


logger = get_logger(__name__)
settings = get_settings()
redis_client = get_redis_client()

T = TypeVar('T')
R = TypeVar('R')


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


class FailureType(str, Enum):
    """Types of failures that can trigger circuit breaker."""
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    HTTP_ERROR = "http_error"
    VALIDATION_ERROR = "validation_error"
    RATE_LIMIT = "rate_limit"
    SERVICE_UNAVAILABLE = "service_unavailable"
    UNKNOWN = "unknown"


class RecoveryStrategy(str, Enum):
    """Recovery strategies for circuit breaker."""
    IMMEDIATE = "immediate"  # Try recovery immediately
    EXPONENTIAL_BACKOFF = "exponential_backoff"  # Exponential backoff
    LINEAR_BACKOFF = "linear_backoff"  # Linear backoff
    FIXED_INTERVAL = "fixed_interval"  # Fixed interval
    ADAPTIVE = "adaptive"  # Adaptive based on failure patterns


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5  # Number of failures to open circuit
    recovery_timeout: float = 60.0  # Seconds to wait before trying recovery
    success_threshold: int = 3  # Successful calls needed to close circuit
    timeout: float = 30.0  # Request timeout in seconds
    
    # Advanced settings
    failure_rate_threshold: float = 0.5  # Failure rate to open circuit (0.0-1.0)
    minimum_requests: int = 10  # Minimum requests before considering failure rate
    sliding_window_size: int = 100  # Size of sliding window for metrics
    
    # Recovery settings
    recovery_strategy: RecoveryStrategy = RecoveryStrategy.EXPONENTIAL_BACKOFF
    max_recovery_time: float = 300.0  # Maximum recovery time in seconds
    recovery_factor: float = 2.0  # Backoff factor for recovery
    
    # Health check settings
    health_check_interval: float = 30.0  # Health check interval in seconds
    health_check_timeout: float = 5.0  # Health check timeout
    
    # Monitoring settings
    enable_metrics: bool = True
    metrics_retention: int = 1000  # Number of metrics to retain


@dataclass
class CallResult:
    """Result of a circuit breaker call."""
    success: bool
    duration: float
    error: Optional[Exception] = None
    failure_type: Optional[FailureType] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'success': self.success,
            'duration': self.duration,
            'error': str(self.error) if self.error else None,
            'failure_type': self.failure_type.value if self.failure_type else None,
            'timestamp': self.timestamp.isoformat()
        }


class CircuitBreakerMetrics(BaseModel):
    """Circuit breaker metrics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeouts: int = 0
    circuit_opens: int = 0
    circuit_closes: int = 0
    
    average_response_time: float = 0.0
    failure_rate: float = 0.0
    current_state: CircuitState = CircuitState.CLOSED
    
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_changed_at: datetime = field(default_factory=datetime.utcnow)
    
    # Failure breakdown
    failure_types: Dict[str, int] = field(default_factory=dict)
    
    def update_failure(self, failure_type: FailureType, duration: float):
        """Update metrics for a failure."""
        self.total_requests += 1
        self.failed_requests += 1
        self.last_failure_time = datetime.utcnow()
        
        if failure_type == FailureType.TIMEOUT:
            self.timeouts += 1
        
        # Update failure types
        failure_key = failure_type.value
        self.failure_types[failure_key] = self.failure_types.get(failure_key, 0) + 1
        
        # Update failure rate
        if self.total_requests > 0:
            self.failure_rate = self.failed_requests / self.total_requests
        
        # Update average response time
        self._update_response_time(duration)
    
    def update_success(self, duration: float):
        """Update metrics for a success."""
        self.total_requests += 1
        self.successful_requests += 1
        self.last_success_time = datetime.utcnow()
        
        # Update failure rate
        if self.total_requests > 0:
            self.failure_rate = self.failed_requests / self.total_requests
        
        # Update average response time
        self._update_response_time(duration)
    
    def _update_response_time(self, duration: float):
        """Update average response time."""
        if self.total_requests == 1:
            self.average_response_time = duration
        else:
            # Exponential moving average
            alpha = 0.1
            self.average_response_time = (alpha * duration + 
                                        (1 - alpha) * self.average_response_time)
    
    def reset_window(self):
        """Reset sliding window metrics."""
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.timeouts = 0
        self.failure_rate = 0.0
        self.failure_types.clear()


class CircuitBreaker:
    """Circuit breaker implementation with advanced features."""
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state_changed_at = datetime.utcnow()
        
        # Metrics and monitoring
        self.metrics = CircuitBreakerMetrics()
        self.call_history: deque[CallResult] = deque(maxlen=self.config.sliding_window_size)
        
        # Recovery management
        self.recovery_attempts = 0
        self.next_recovery_time: Optional[datetime] = None
        
        # Health checking
        self.health_check_task: Optional[asyncio.Task] = None
        self.health_check_function: Optional[Callable] = None
        
        # Fallback functions
        self.fallback_functions: Dict[str, Callable] = {}
        
        # Thread safety - will be initialized when needed
        self.lock = None
        
        # Health check task will be started when needed
        self.health_check_task: Optional[asyncio.Task] = None
        self._health_check_enabled = self.config.health_check_interval > 0
    
    def _ensure_lock_initialized(self):
        """Initialize the asyncio lock if not already done."""
        if self.lock is None:
            try:
                self.lock = asyncio.Lock()
            except RuntimeError:
                # No event loop available, will be initialized when needed
                pass
    
    def _ensure_health_check_started(self):
        """Start health check task if enabled and not already running."""
        if (self._health_check_enabled and 
            (self.health_check_task is None or self.health_check_task.done())):
            try:
                # Only create task if we're in an async context
                loop = asyncio.get_running_loop()
                self.health_check_task = asyncio.create_task(self._health_check_loop())
            except RuntimeError:
                # No event loop available, health check will start when call is made
                pass
    
    async def call(self, func: Callable[..., T], *args, fallback_key: Optional[str] = None, 
                  **kwargs) -> T:
        """Execute function through circuit breaker."""
        # Ensure lock and health check are initialized
        self._ensure_lock_initialized()
        self._ensure_health_check_started()
        
        async with self.lock:
            # Check if circuit is open
            if self.state == CircuitState.OPEN:
                if not self._should_attempt_reset():
                    # Circuit is open, try fallback or raise exception
                    if fallback_key and fallback_key in self.fallback_functions:
                        logger.warning(f"Circuit {self.name} is open, using fallback")
                        return await self._execute_fallback(fallback_key, *args, **kwargs)
                    else:
                        raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is open")
                else:
                    # Try to reset circuit
                    await self._transition_to_half_open()
        
        # Execute the function
        start_time = time.time()
        
        try:
            # Apply timeout
            result = await asyncio.wait_for(
                self._execute_function(func, *args, **kwargs),
                timeout=self.config.timeout
            )
            
            duration = time.time() - start_time
            await self._record_success(duration)
            
            return result
            
        except asyncio.TimeoutError as e:
            duration = time.time() - start_time
            await self._record_failure(e, FailureType.TIMEOUT, duration)
            raise CircuitBreakerTimeoutError(f"Circuit breaker {self.name} timeout") from e
            
        except Exception as e:
            duration = time.time() - start_time
            failure_type = self._classify_error(e)
            await self._record_failure(e, failure_type, duration)
            
            # Try fallback on failure
            if fallback_key and fallback_key in self.fallback_functions:
                logger.warning(f"Function failed, using fallback for circuit {self.name}")
                return await self._execute_fallback(fallback_key, *args, **kwargs)
            
            raise
    
    async def _execute_function(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute the actual function."""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, func, *args, **kwargs)
    
    async def _execute_fallback(self, fallback_key: str, *args, **kwargs) -> Any:
        """Execute fallback function."""
        fallback_func = self.fallback_functions[fallback_key]
        
        if asyncio.iscoroutinefunction(fallback_func):
            return await fallback_func(*args, **kwargs)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, fallback_func, *args, **kwargs)
    
    def _classify_error(self, error: Exception) -> FailureType:
        """Classify error type."""
        error_type = type(error).__name__.lower()
        
        if 'timeout' in error_type:
            return FailureType.TIMEOUT
        elif 'connection' in error_type:
            return FailureType.CONNECTION_ERROR
        elif 'http' in error_type:
            return FailureType.HTTP_ERROR
        elif 'validation' in error_type:
            return FailureType.VALIDATION_ERROR
        elif 'rate' in error_type or 'limit' in error_type:
            return FailureType.RATE_LIMIT
        elif 'unavailable' in error_type or 'service' in error_type:
            return FailureType.SERVICE_UNAVAILABLE
        else:
            return FailureType.UNKNOWN
    
    async def _record_success(self, duration: float):
        """Record successful call."""
        self._ensure_lock_initialized()
        async with self.lock:
            call_result = CallResult(success=True, duration=duration)
            self.call_history.append(call_result)
            
            self.metrics.update_success(duration)
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                
                if self.success_count >= self.config.success_threshold:
                    await self._transition_to_closed()
            
            logger.debug(f"Circuit {self.name}: Successful call in {duration:.3f}s")
    
    async def _record_failure(self, error: Exception, failure_type: FailureType, duration: float):
        """Record failed call."""
        self._ensure_lock_initialized()
        async with self.lock:
            call_result = CallResult(
                success=False, 
                duration=duration, 
                error=error, 
                failure_type=failure_type
            )
            self.call_history.append(call_result)
            
            self.metrics.update_failure(failure_type, duration)
            self.failure_count += 1
            self.last_failure_time = datetime.utcnow()
            
            # Check if circuit should open
            if self._should_open_circuit():
                await self._transition_to_open()
            
            logger.warning(f"Circuit {self.name}: Failed call - {failure_type.value}: {error}")
    
    def _should_open_circuit(self) -> bool:
        """Check if circuit should be opened."""
        # Check failure count threshold
        if self.failure_count >= self.config.failure_threshold:
            return True
        
        # Check failure rate threshold
        if len(self.call_history) >= self.config.minimum_requests:
            recent_calls = list(self.call_history)[-self.config.minimum_requests:]
            failures = sum(1 for call in recent_calls if not call.success)
            failure_rate = failures / len(recent_calls)
            
            if failure_rate >= self.config.failure_rate_threshold:
                return True
        
        return False
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt reset."""
        if not self.next_recovery_time:
            return True
        
        return datetime.utcnow() >= self.next_recovery_time
    
    async def _transition_to_open(self):
        """Transition circuit to open state."""
        if self.state != CircuitState.OPEN:
            self.state = CircuitState.OPEN
            self.state_changed_at = datetime.utcnow()
            self.metrics.circuit_opens += 1
            self.metrics.current_state = CircuitState.OPEN
            
            # Calculate next recovery time
            self._calculate_next_recovery_time()
            
            logger.warning(f"Circuit {self.name} opened due to failures")
            
            # Log security event for monitoring
            security_event = SecurityEvent(
                event_type="circuit_breaker_open",
                severity="medium",
                details={
                    'circuit_name': self.name,
                    'failure_count': self.failure_count,
                    'failure_rate': self.metrics.failure_rate
                }
            )
            logger.security(security_event)
    
    async def _transition_to_half_open(self):
        """Transition circuit to half-open state."""
        self.state = CircuitState.HALF_OPEN
        self.state_changed_at = datetime.utcnow()
        self.success_count = 0
        self.metrics.current_state = CircuitState.HALF_OPEN
        
        logger.info(f"Circuit {self.name} transitioned to half-open")
    
    async def _transition_to_closed(self):
        """Transition circuit to closed state."""
        self.state = CircuitState.CLOSED
        self.state_changed_at = datetime.utcnow()
        self.failure_count = 0
        self.success_count = 0
        self.recovery_attempts = 0
        self.next_recovery_time = None
        
        self.metrics.circuit_closes += 1
        self.metrics.current_state = CircuitState.CLOSED
        
        logger.info(f"Circuit {self.name} closed - service recovered")
    
    def _calculate_next_recovery_time(self):
        """Calculate next recovery attempt time."""
        base_delay = self.config.recovery_timeout
        
        if self.config.recovery_strategy == RecoveryStrategy.IMMEDIATE:
            delay = 0
        elif self.config.recovery_strategy == RecoveryStrategy.FIXED_INTERVAL:
            delay = base_delay
        elif self.config.recovery_strategy == RecoveryStrategy.LINEAR_BACKOFF:
            delay = base_delay * (self.recovery_attempts + 1)
        elif self.config.recovery_strategy == RecoveryStrategy.EXPONENTIAL_BACKOFF:
            delay = base_delay * (self.config.recovery_factor ** self.recovery_attempts)
        elif self.config.recovery_strategy == RecoveryStrategy.ADAPTIVE:
            # Adaptive strategy based on failure patterns
            recent_failures = [call for call in self.call_history if not call.success]
            if recent_failures:
                avg_failure_duration = statistics.mean(call.duration for call in recent_failures)
                delay = base_delay + avg_failure_duration
            else:
                delay = base_delay
        else:
            delay = base_delay
        
        # Cap the delay
        delay = min(delay, self.config.max_recovery_time)
        
        self.next_recovery_time = datetime.utcnow() + timedelta(seconds=delay)
        self.recovery_attempts += 1
        
        logger.info(f"Circuit {self.name}: Next recovery attempt in {delay:.1f}s")
    
    async def _health_check_loop(self):
        """Background health checking loop."""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                
                if self.state == CircuitState.OPEN and self.health_check_function:
                    try:
                        # Perform health check
                        await asyncio.wait_for(
                            self.health_check_function(),
                            timeout=self.config.health_check_timeout
                        )
                        
                        # Health check passed, try to recover
                        logger.info(f"Circuit {self.name}: Health check passed")
                        await self._transition_to_half_open()
                        
                    except Exception as e:
                        logger.debug(f"Circuit {self.name}: Health check failed: {e}")
                
            except Exception as e:
                logger.error(f"Error in health check loop for circuit {self.name}: {e}")
    
    def register_fallback(self, key: str, func: Callable):
        """Register a fallback function."""
        self.fallback_functions[key] = func
        logger.info(f"Registered fallback '{key}' for circuit {self.name}")
    
    def register_health_check(self, func: Callable):
        """Register a health check function."""
        self.health_check_function = func
        logger.info(f"Registered health check for circuit {self.name}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics."""
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'recovery_attempts': self.recovery_attempts,
            'state_changed_at': self.state_changed_at.isoformat(),
            'next_recovery_time': self.next_recovery_time.isoformat() if self.next_recovery_time else None,
            'metrics': self.metrics.dict(),
            'call_history_size': len(self.call_history)
        }
    
    def reset(self):
        """Reset circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.recovery_attempts = 0
        self.next_recovery_time = None
        self.state_changed_at = datetime.utcnow()
        self.call_history.clear()
        self.metrics = CircuitBreakerMetrics()
        
        logger.info(f"Circuit {self.name} manually reset")
    
    async def close(self):
        """Close circuit breaker and cleanup resources."""
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"Circuit {self.name} closed and cleaned up")


class CircuitBreakerManager:
    """Manages multiple circuit breakers."""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.default_config = CircuitBreakerConfig()
    
    def get_circuit_breaker(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """Get or create circuit breaker."""
        if name not in self.circuit_breakers:
            circuit_config = config or self.default_config
            self.circuit_breakers[name] = CircuitBreaker(name, circuit_config)
            logger.info(f"Created circuit breaker: {name}")
        
        return self.circuit_breakers[name]
    
    def remove_circuit_breaker(self, name: str):
        """Remove circuit breaker."""
        if name in self.circuit_breakers:
            circuit = self.circuit_breakers.pop(name)
            asyncio.create_task(circuit.close())
            logger.info(f"Removed circuit breaker: {name}")
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all circuit breakers."""
        return {name: cb.get_metrics() for name, cb in self.circuit_breakers.items()}
    
    def reset_all(self):
        """Reset all circuit breakers."""
        for circuit in self.circuit_breakers.values():
            circuit.reset()
        
        logger.info("Reset all circuit breakers")
    
    async def close_all(self):
        """Close all circuit breakers."""
        for circuit in self.circuit_breakers.values():
            await circuit.close()
        
        self.circuit_breakers.clear()
        logger.info("Closed all circuit breakers")


# Custom exceptions
class CircuitBreakerError(Exception):
    """Base circuit breaker exception."""
    pass


class CircuitBreakerOpenError(CircuitBreakerError):
    """Circuit breaker is open."""
    pass


class CircuitBreakerTimeoutError(CircuitBreakerError):
    """Circuit breaker timeout."""
    pass


# Decorator for circuit breaker
def circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None, 
                  fallback_key: Optional[str] = None):
    """Decorator to apply circuit breaker to a function."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        circuit = circuit_breaker_manager.get_circuit_breaker(name, config)
        
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await circuit.call(func, *args, fallback_key=fallback_key, **kwargs)
        
        # Store circuit reference on function
        wrapper._circuit_breaker = circuit
        
        return wrapper
    return decorator


# Global circuit breaker manager
circuit_breaker_manager = CircuitBreakerManager()


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get the global circuit breaker manager."""
    return circuit_breaker_manager


def get_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
    """Get circuit breaker by name."""
    return circuit_breaker_manager.get_circuit_breaker(name, config)


# Utility functions
async def with_circuit_breaker(name: str, func: Callable[..., T], *args, 
                              config: Optional[CircuitBreakerConfig] = None,
                              fallback_key: Optional[str] = None, **kwargs) -> T:
    """Execute function with circuit breaker protection."""
    circuit = get_circuit_breaker(name, config)
    return await circuit.call(func, *args, fallback_key=fallback_key, **kwargs)


async def register_fallback_for_circuit(circuit_name: str, fallback_key: str, fallback_func: Callable):
    """Register fallback function for a circuit."""
    circuit = get_circuit_breaker(circuit_name)
    circuit.register_fallback(fallback_key, fallback_func)


async def register_health_check_for_circuit(circuit_name: str, health_check_func: Callable):
    """Register health check function for a circuit."""
    circuit = get_circuit_breaker(circuit_name)
    circuit.register_health_check(health_check_func)