"""Enhanced retry mechanisms with exponential backoff and jitter."""

import asyncio
import random
import time
import logging
from typing import Callable, Any, Optional, Type, Tuple, List
from dataclasses import dataclass
from functools import wraps
from enum import Enum

logger = logging.getLogger(__name__)

class BackoffStrategy(Enum):
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"
    FIBONACCI = "fibonacci"

@dataclass
class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    jitter: bool = True
    jitter_range: float = 0.1  # ±10% jitter
    exponential_base: float = 2.0
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    non_retryable_exceptions: Tuple[Type[Exception], ...] = ()
    retry_condition: Optional[Callable[[Exception], bool]] = None

class RetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted."""
    def __init__(self, attempts: int, last_exception: Exception):
        self.attempts = attempts
        self.last_exception = last_exception
        super().__init__(f"Retry exhausted after {attempts} attempts. Last error: {last_exception}")

class EnhancedRetry:
    """Enhanced retry mechanism with multiple backoff strategies."""
    
    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
        self._fibonacci_cache = [1, 1]
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt number."""
        if self.config.backoff_strategy == BackoffStrategy.FIXED:
            delay = self.config.base_delay
        elif self.config.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.config.base_delay * attempt
        elif self.config.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.config.base_delay * (self.config.exponential_base ** (attempt - 1))
        elif self.config.backoff_strategy == BackoffStrategy.FIBONACCI:
            delay = self.config.base_delay * self._get_fibonacci(attempt)
        else:
            delay = self.config.base_delay
        
        # Apply max delay limit
        delay = min(delay, self.config.max_delay)
        
        # Apply jitter if enabled
        if self.config.jitter:
            jitter_amount = delay * self.config.jitter_range
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0, delay)
    
    def _get_fibonacci(self, n: int) -> int:
        """Get nth Fibonacci number with caching."""
        while len(self._fibonacci_cache) <= n:
            next_fib = self._fibonacci_cache[-1] + self._fibonacci_cache[-2]
            self._fibonacci_cache.append(next_fib)
        return self._fibonacci_cache[n]
    
    def _should_retry(self, exception: Exception, attempt: int) -> bool:
        """Determine if we should retry based on the exception and attempt count."""
        # Check if we've exceeded max attempts
        if attempt >= self.config.max_attempts:
            return False
        
        # Check non-retryable exceptions first
        if any(isinstance(exception, exc_type) for exc_type in self.config.non_retryable_exceptions):
            return False
        
        # Check custom retry condition
        if self.config.retry_condition:
            return self.config.retry_condition(exception)
        
        # Check retryable exceptions
        return any(isinstance(exception, exc_type) for exc_type in self.config.retryable_exceptions)
    
    async def execute_async(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with retry logic."""
        last_exception = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                logger.debug(f"Attempt {attempt}/{self.config.max_attempts} for {func.__name__}")
                result = await func(*args, **kwargs)
                
                if attempt > 1:
                    logger.info(f"Function {func.__name__} succeeded on attempt {attempt}")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                if not self._should_retry(e, attempt):
                    logger.error(f"Not retrying {func.__name__} due to non-retryable exception: {e}")
                    raise e
                
                if attempt < self.config.max_attempts:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {self.config.max_attempts} attempts failed for {func.__name__}")
        
        raise RetryExhaustedError(self.config.max_attempts, last_exception)
    
    def execute_sync(self, func: Callable, *args, **kwargs) -> Any:
        """Execute sync function with retry logic."""
        last_exception = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                logger.debug(f"Attempt {attempt}/{self.config.max_attempts} for {func.__name__}")
                result = func(*args, **kwargs)
                
                if attempt > 1:
                    logger.info(f"Function {func.__name__} succeeded on attempt {attempt}")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                if not self._should_retry(e, attempt):
                    logger.error(f"Not retrying {func.__name__} due to non-retryable exception: {e}")
                    raise e
                
                if attempt < self.config.max_attempts:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.config.max_attempts} attempts failed for {func.__name__}")
        
        raise RetryExhaustedError(self.config.max_attempts, last_exception)

def retry_async(config: RetryConfig = None):
    """Decorator for async functions with retry logic."""
    retry_handler = EnhancedRetry(config)
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_handler.execute_async(func, *args, **kwargs)
        return wrapper
    return decorator

def retry_sync(config: RetryConfig = None):
    """Decorator for sync functions with retry logic."""
    retry_handler = EnhancedRetry(config)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return retry_handler.execute_sync(func, *args, **kwargs)
        return wrapper
    return decorator

# Predefined retry configurations for common scenarios
FFMPEG_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=30.0,
    backoff_strategy=BackoffStrategy.EXPONENTIAL,
    retryable_exceptions=(subprocess.CalledProcessError, TimeoutError),
    non_retryable_exceptions=(FileNotFoundError, PermissionError)
)

SUPABASE_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=1.0,
    max_delay=60.0,
    backoff_strategy=BackoffStrategy.EXPONENTIAL,
    retryable_exceptions=(ConnectionError, TimeoutError),
    non_retryable_exceptions=(ValueError, TypeError)
)

LLM_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=5.0,
    max_delay=120.0,
    backoff_strategy=BackoffStrategy.EXPONENTIAL,
    retryable_exceptions=(ConnectionError, TimeoutError),
    retry_condition=lambda e: "rate limit" in str(e).lower() or "timeout" in str(e).lower()
)

FILE_OPERATION_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=0.5,
    max_delay=5.0,
    backoff_strategy=BackoffStrategy.LINEAR,
    retryable_exceptions=(OSError, IOError),
    non_retryable_exceptions=(FileNotFoundError, PermissionError)
)

# Convenience functions
async def retry_async_operation(func: Callable, config: RetryConfig = None, *args, **kwargs) -> Any:
    """Retry an async operation with the given configuration."""
    retry_handler = EnhancedRetry(config)
    return await retry_handler.execute_async(func, *args, **kwargs)

def retry_sync_operation(func: Callable, config: RetryConfig = None, *args, **kwargs) -> Any:
    """Retry a sync operation with the given configuration."""
    retry_handler = EnhancedRetry(config)
    return retry_handler.execute_sync(func, *args, **kwargs)