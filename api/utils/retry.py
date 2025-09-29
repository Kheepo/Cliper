"""Retry utilities with exponential backoff and circuit breaker patterns.

This module provides robust retry mechanisms for handling transient failures
in video processing operations.
"""

import asyncio
import logging
import random
import time
from functools import wraps
from typing import Any, Callable, Optional, Type, Union, List

logger = logging.getLogger(__name__)


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """Circuit breaker pattern implementation."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator to apply circuit breaker."""
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if self.state == 'open':
                if time.time() - self.last_failure_time < self.recovery_timeout:
                    raise CircuitBreakerError("Circuit breaker is open")
                else:
                    self.state = 'half-open'
            
            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise e
        
        return wrapper
    
    def _on_success(self):
        """Handle successful operation."""
        self.failure_count = 0
        self.state = 'closed'
    
    def _on_failure(self):
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'open'
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )


async def exponential_backoff_retry(
    func: Callable,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Union[Type[Exception], tuple] = Exception,
    *args,
    **kwargs
) -> Any:
    """Retry function with exponential backoff.
    
    Args:
        func: Function to retry
        max_attempts: Maximum number of attempts
        base_delay: Initial delay between retries
        max_delay: Maximum delay between retries
        backoff_factor: Factor to multiply delay by each retry
        jitter: Add random jitter to delay
        exceptions: Exception types to retry on
        *args, **kwargs: Arguments to pass to func
    
    Returns:
        Result of successful function call
    
    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    
    for attempt in range(max_attempts):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        
        except exceptions as e:
            last_exception = e
            
            if attempt == max_attempts - 1:
                logger.error(
                    f"Function {func.__name__} failed after {max_attempts} attempts: {e}"
                )
                raise e
            
            # Calculate delay with exponential backoff
            delay = min(base_delay * (backoff_factor ** attempt), max_delay)
            
            # Add jitter to prevent thundering herd
            if jitter:
                delay *= (0.5 + random.random() * 0.5)
            
            logger.warning(
                f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}. "
                f"Retrying in {delay:.2f}s"
            )
            
            await asyncio.sleep(delay)
    
    # This should never be reached, but just in case
    raise last_exception


def retry_on_exception(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Union[Type[Exception], tuple] = Exception
):
    """Decorator for retrying functions with exponential backoff."""
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await exponential_backoff_retry(
                func=func,
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                backoff_factor=backoff_factor,
                jitter=jitter,
                exceptions=exceptions,
                *args,
                **kwargs
            )
        return wrapper
    
    return decorator


class RetryConfig:
    """Configuration for retry operations."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
        circuit_breaker: bool = False,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self.circuit_breaker = circuit_breaker
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout


class RetryableOperation:
    """Wrapper for retryable operations with circuit breaker."""
    
    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
        self.circuit_breaker = None
        
        if self.config.circuit_breaker:
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=self.config.failure_threshold,
                recovery_timeout=self.config.recovery_timeout
            )
    
    async def execute(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute function with retry and circuit breaker."""
        
        if self.circuit_breaker:
            func = self.circuit_breaker(func)
        
        return await exponential_backoff_retry(
            func=func,
            max_attempts=self.config.max_attempts,
            base_delay=self.config.base_delay,
            max_delay=self.config.max_delay,
            backoff_factor=self.config.backoff_factor,
            jitter=self.config.jitter,
            *args,
            **kwargs
        )


# Predefined retry configurations for common scenarios
FAST_RETRY = RetryConfig(
    max_attempts=3,
    base_delay=0.5,
    max_delay=5.0,
    backoff_factor=1.5
)

STANDARD_RETRY = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    backoff_factor=2.0
)

ROBUST_RETRY = RetryConfig(
    max_attempts=5,
    base_delay=2.0,
    max_delay=60.0,
    backoff_factor=2.0,
    circuit_breaker=True
)

CRITICAL_RETRY = RetryConfig(
    max_attempts=10,
    base_delay=1.0,
    max_delay=120.0,
    backoff_factor=1.8,
    circuit_breaker=True,
    failure_threshold=3,
    recovery_timeout=300.0
)