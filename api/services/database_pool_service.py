#!/usr/bin/env python3
"""
Database Connection Pool Service

Provides optimized database connection pooling for:
- PostgreSQL/Supabase connections
- Connection lifecycle management
- Query optimization and monitoring
- Connection health checks
- Performance metrics
"""

import asyncio
import time
from typing import Any, Dict, List, Optional, Union, AsyncGenerator
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from enum import Enum

import asyncpg
from asyncpg import Pool, Connection
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy import text, event
from supabase import create_client, Client

from api.config.environments import get_environment_config
from api.utils.structured_logging import get_logger

logger = get_logger(__name__)

class ConnectionType(Enum):
    """Database connection types"""
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    ADMIN = "admin"

class QueryType(Enum):
    """Query classification types"""
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    DDL = "ddl"
    TRANSACTION = "transaction"

@dataclass
class PoolConfig:
    """Database pool configuration"""
    min_size: int = 5
    max_size: int = 20
    max_queries: int = 50000
    max_inactive_connection_lifetime: float = 300.0  # 5 minutes
    timeout: float = 60.0
    command_timeout: float = 30.0
    server_settings: Dict[str, str] = field(default_factory=lambda: {
        'application_name': 'cliper_api',
        'timezone': 'UTC'
    })
    
@dataclass
class QueryMetrics:
    """Query performance metrics"""
    query_hash: str
    query_type: QueryType
    execution_time: float
    rows_affected: int
    timestamp: datetime
    connection_id: str
    success: bool
    error_message: Optional[str] = None

@dataclass
class ConnectionMetrics:
    """Connection pool metrics"""
    total_connections: int
    active_connections: int
    idle_connections: int
    total_queries: int
    successful_queries: int
    failed_queries: int
    average_query_time: float
    peak_connections: int
    pool_exhaustion_count: int
    last_reset: datetime

class DatabasePoolService:
    """Comprehensive database connection pool service"""
    
    def __init__(self, config: Optional[PoolConfig] = None):
        self.config = config or PoolConfig()
        self.env_config = get_environment_config()
        
        # Connection pools
        self.asyncpg_pool: Optional[Pool] = None
        self.sqlalchemy_engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[sessionmaker] = None
        self.supabase_client: Optional[Client] = None
        
        # Metrics tracking
        self.query_metrics: List[QueryMetrics] = []
        self.connection_metrics = ConnectionMetrics(
            total_connections=0,
            active_connections=0,
            idle_connections=0,
            total_queries=0,
            successful_queries=0,
            failed_queries=0,
            average_query_time=0.0,
            peak_connections=0,
            pool_exhaustion_count=0,
            last_reset=datetime.now()
        )
        
        self._query_times: List[float] = []
        self._initialized = False
    
    async def initialize(self):
        """Initialize all database connections and pools"""
        if self._initialized:
            logger.warning("Database pool service already initialized")
            return
        
        try:
            await self._initialize_asyncpg_pool()
            await self._initialize_sqlalchemy_engine()
            await self._initialize_supabase_client()
            
            self._initialized = True
            logger.info("Database pool service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database pool service: {e}")
            await self.cleanup()
            raise
    
    async def _initialize_asyncpg_pool(self):
        """Initialize AsyncPG connection pool"""
        try:
            database_url = self.env_config.get("DATABASE_URL")
            if not database_url:
                raise ValueError("DATABASE_URL not found in environment")
            
            # Convert postgres:// to postgresql:// if needed
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)
            
            self.asyncpg_pool = await asyncpg.create_pool(
                database_url,
                min_size=self.config.min_size,
                max_size=self.config.max_size,
                max_queries=self.config.max_queries,
                max_inactive_connection_lifetime=self.config.max_inactive_connection_lifetime,
                timeout=self.config.timeout,
                command_timeout=self.config.command_timeout,
                server_settings=self.config.server_settings
            )
            
            logger.info(f"AsyncPG pool initialized with {self.config.min_size}-{self.config.max_size} connections")
            
        except Exception as e:
            logger.error(f"Failed to initialize AsyncPG pool: {e}")
            raise
    
    async def _initialize_sqlalchemy_engine(self):
        """Initialize SQLAlchemy async engine"""
        try:
            database_url = self.env_config.get("DATABASE_URL")
            if not database_url:
                raise ValueError("DATABASE_URL not found in environment")
            
            # Convert to async URL
            if database_url.startswith("postgresql://"):
                async_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif database_url.startswith("postgres://"):
                async_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
            else:
                async_url = database_url
            
            self.sqlalchemy_engine = create_async_engine(
                async_url,
                poolclass=QueuePool,
                pool_size=self.config.min_size,
                max_overflow=self.config.max_size - self.config.min_size,
                pool_timeout=self.config.timeout,
                pool_recycle=3600,  # Recycle connections every hour
                pool_pre_ping=True,  # Validate connections before use
                echo=False,  # Set to True for SQL logging in development
                future=True
            )
            
            # Create session factory
            self.session_factory = sessionmaker(
                bind=self.sqlalchemy_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Add event listeners for metrics
            self._setup_sqlalchemy_events()
            
            logger.info("SQLAlchemy async engine initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize SQLAlchemy engine: {e}")
            raise
    
    async def _initialize_supabase_client(self):
        """Initialize Supabase client"""
        try:
            supabase_url = self.env_config.get("SUPABASE_URL")
            supabase_key = self.env_config.get("SUPABASE_SERVICE_ROLE_KEY")
            
            if not supabase_url or not supabase_key:
                logger.warning("Supabase credentials not found, skipping Supabase client initialization")
                return
            
            self.supabase_client = create_client(supabase_url, supabase_key)
            logger.info("Supabase client initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            # Don't raise here as Supabase might be optional
    
    def _setup_sqlalchemy_events(self):
        """Setup SQLAlchemy event listeners for metrics"""
        @event.listens_for(self.sqlalchemy_engine.sync_engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = time.time()
        
        @event.listens_for(self.sqlalchemy_engine.sync_engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            total_time = time.time() - context._query_start_time
            self._record_query_metrics(statement, total_time, cursor.rowcount, True)
    
    def _record_query_metrics(self, query: str, execution_time: float, rows_affected: int, success: bool, error: Optional[str] = None):
        """Record query performance metrics"""
        query_type = self._classify_query(query)
        query_hash = str(hash(query.strip()[:100]))  # Hash first 100 chars
        
        metric = QueryMetrics(
            query_hash=query_hash,
            query_type=query_type,
            execution_time=execution_time,
            rows_affected=rows_affected,
            timestamp=datetime.now(),
            connection_id="sqlalchemy",
            success=success,
            error_message=error
        )
        
        self.query_metrics.append(metric)
        self._query_times.append(execution_time)
        
        # Update connection metrics
        self.connection_metrics.total_queries += 1
        if success:
            self.connection_metrics.successful_queries += 1
        else:
            self.connection_metrics.failed_queries += 1
        
        # Calculate average query time
        if self._query_times:
            self.connection_metrics.average_query_time = sum(self._query_times) / len(self._query_times)
        
        # Keep only recent metrics (last 1000 queries)
        if len(self.query_metrics) > 1000:
            self.query_metrics = self.query_metrics[-1000:]
        if len(self._query_times) > 1000:
            self._query_times = self._query_times[-1000:]
    
    def _classify_query(self, query: str) -> QueryType:
        """Classify query type based on SQL statement"""
        query_lower = query.strip().lower()
        
        if query_lower.startswith('select'):
            return QueryType.SELECT
        elif query_lower.startswith('insert'):
            return QueryType.INSERT
        elif query_lower.startswith('update'):
            return QueryType.UPDATE
        elif query_lower.startswith('delete'):
            return QueryType.DELETE
        elif any(query_lower.startswith(ddl) for ddl in ['create', 'alter', 'drop', 'truncate']):
            return QueryType.DDL
        else:
            return QueryType.TRANSACTION
    
    @asynccontextmanager
    async def get_connection(self, connection_type: ConnectionType = ConnectionType.READ_WRITE) -> AsyncGenerator[Connection, None]:
        """Get a database connection from the pool"""
        if not self.asyncpg_pool:
            raise RuntimeError("AsyncPG pool not initialized")
        
        start_time = time.time()
        connection = None
        
        try:
            connection = await self.asyncpg_pool.acquire(timeout=self.config.timeout)
            self.connection_metrics.active_connections += 1
            
            # Update peak connections
            if self.connection_metrics.active_connections > self.connection_metrics.peak_connections:
                self.connection_metrics.peak_connections = self.connection_metrics.active_connections
            
            yield connection
            
        except asyncio.TimeoutError:
            self.connection_metrics.pool_exhaustion_count += 1
            logger.error("Connection pool exhausted - timeout acquiring connection")
            raise
        except Exception as e:
            logger.error(f"Error acquiring database connection: {e}")
            raise
        finally:
            if connection:
                try:
                    await self.asyncpg_pool.release(connection)
                    self.connection_metrics.active_connections -= 1
                except Exception as e:
                    logger.error(f"Error releasing connection: {e}")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a SQLAlchemy async session"""
        if not self.session_factory:
            raise RuntimeError("SQLAlchemy session factory not initialized")
        
        async with self.session_factory() as session:
            try:
                yield session
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise
            finally:
                await session.close()
    
    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None, fetch: bool = True) -> Optional[List[Dict[str, Any]]]:
        """Execute a query using AsyncPG with metrics tracking"""
        start_time = time.time()
        
        async with self.get_connection() as conn:
            try:
                if fetch:
                    if params:
                        result = await conn.fetch(query, *params.values())
                    else:
                        result = await conn.fetch(query)
                    
                    # Convert to list of dicts
                    return [dict(row) for row in result]
                else:
                    if params:
                        result = await conn.execute(query, *params.values())
                    else:
                        result = await conn.execute(query)
                    
                    return None
                
            except Exception as e:
                execution_time = time.time() - start_time
                self._record_query_metrics(query, execution_time, 0, False, str(e))
                logger.error(f"Query execution failed: {e}")
                raise
            else:
                execution_time = time.time() - start_time
                rows_affected = len(result) if fetch and result else 0
                self._record_query_metrics(query, execution_time, rows_affected, True)
    
    async def execute_transaction(self, queries: List[tuple]) -> bool:
        """Execute multiple queries in a transaction"""
        async with self.get_connection() as conn:
            async with conn.transaction():
                try:
                    for query, params in queries:
                        if params:
                            await conn.execute(query, *params.values())
                        else:
                            await conn.execute(query)
                    return True
                except Exception as e:
                    logger.error(f"Transaction failed: {e}")
                    raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all database connections"""
        health_status = {
            "asyncpg_pool": False,
            "sqlalchemy_engine": False,
            "supabase_client": False,
            "timestamp": datetime.now().isoformat()
        }
        
        # Check AsyncPG pool
        try:
            if self.asyncpg_pool:
                async with self.get_connection() as conn:
                    await conn.fetchval("SELECT 1")
                health_status["asyncpg_pool"] = True
        except Exception as e:
            logger.error(f"AsyncPG health check failed: {e}")
        
        # Check SQLAlchemy engine
        try:
            if self.sqlalchemy_engine:
                async with self.get_session() as session:
                    result = await session.execute(text("SELECT 1"))
                    await result.fetchone()
                health_status["sqlalchemy_engine"] = True
        except Exception as e:
            logger.error(f"SQLAlchemy health check failed: {e}")
        
        # Check Supabase client
        try:
            if self.supabase_client:
                # Simple table query to test connection
                result = self.supabase_client.table("users").select("id").limit(1).execute()
                health_status["supabase_client"] = True
        except Exception as e:
            logger.error(f"Supabase health check failed: {e}")
        
        return health_status
    
    async def get_pool_stats(self) -> Dict[str, Any]:
        """Get detailed pool statistics"""
        stats = {
            "connection_metrics": {
                "total_connections": self.connection_metrics.total_connections,
                "active_connections": self.connection_metrics.active_connections,
                "idle_connections": self.connection_metrics.idle_connections,
                "peak_connections": self.connection_metrics.peak_connections,
                "pool_exhaustion_count": self.connection_metrics.pool_exhaustion_count
            },
            "query_metrics": {
                "total_queries": self.connection_metrics.total_queries,
                "successful_queries": self.connection_metrics.successful_queries,
                "failed_queries": self.connection_metrics.failed_queries,
                "average_query_time": self.connection_metrics.average_query_time,
                "success_rate": (self.connection_metrics.successful_queries / max(self.connection_metrics.total_queries, 1)) * 100
            },
            "pool_config": {
                "min_size": self.config.min_size,
                "max_size": self.config.max_size,
                "timeout": self.config.timeout,
                "command_timeout": self.config.command_timeout
            }
        }
        
        # Add AsyncPG pool stats if available
        if self.asyncpg_pool:
            stats["asyncpg_pool"] = {
                "size": self.asyncpg_pool.get_size(),
                "min_size": self.asyncpg_pool.get_min_size(),
                "max_size": self.asyncpg_pool.get_max_size(),
                "idle_size": self.asyncpg_pool.get_idle_size()
            }
        
        return stats
    
    async def get_slow_queries(self, threshold: float = 1.0, limit: int = 10) -> List[Dict[str, Any]]:
        """Get slow queries above threshold"""
        slow_queries = [
            {
                "query_hash": metric.query_hash,
                "query_type": metric.query_type.value,
                "execution_time": metric.execution_time,
                "rows_affected": metric.rows_affected,
                "timestamp": metric.timestamp.isoformat(),
                "success": metric.success,
                "error_message": metric.error_message
            }
            for metric in self.query_metrics
            if metric.execution_time > threshold
        ]
        
        # Sort by execution time descending
        slow_queries.sort(key=lambda x: x["execution_time"], reverse=True)
        
        return slow_queries[:limit]
    
    async def reset_metrics(self):
        """Reset all metrics"""
        self.query_metrics.clear()
        self._query_times.clear()
        
        self.connection_metrics = ConnectionMetrics(
            total_connections=0,
            active_connections=self.connection_metrics.active_connections,  # Keep current active
            idle_connections=0,
            total_queries=0,
            successful_queries=0,
            failed_queries=0,
            average_query_time=0.0,
            peak_connections=0,
            pool_exhaustion_count=0,
            last_reset=datetime.now()
        )
        
        logger.info("Database pool metrics reset")
    
    async def cleanup(self):
        """Clean up all database connections"""
        try:
            if self.asyncpg_pool:
                await self.asyncpg_pool.close()
                logger.info("AsyncPG pool closed")
            
            if self.sqlalchemy_engine:
                await self.sqlalchemy_engine.dispose()
                logger.info("SQLAlchemy engine disposed")
            
            # Supabase client doesn't need explicit cleanup
            
            self._initialized = False
            logger.info("Database pool service cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during database pool cleanup: {e}")

# Global database pool service instance
db_pool_service: Optional[DatabasePoolService] = None

async def get_db_pool_service() -> DatabasePoolService:
    """Get or create global database pool service instance"""
    global db_pool_service
    
    if db_pool_service is None:
        db_pool_service = DatabasePoolService()
        await db_pool_service.initialize()
    
    return db_pool_service

async def initialize_db_pool_service(config: Optional[PoolConfig] = None) -> DatabasePoolService:
    """Initialize global database pool service with custom config"""
    global db_pool_service
    
    db_pool_service = DatabasePoolService(config)
    await db_pool_service.initialize()
    
    return db_pool_service

# FastAPI dependency for getting database session
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for getting database session"""
    service = await get_db_pool_service()
    async with service.get_session() as session:
        yield session

# FastAPI dependency for getting AsyncPG connection
async def get_db_connection() -> AsyncGenerator[Connection, None]:
    """FastAPI dependency for getting AsyncPG connection"""
    service = await get_db_pool_service()
    async with service.get_connection() as connection:
        yield connection

# Example usage
async def example_usage():
    """Example of how to use the database pool service"""
    # Initialize service
    service = await get_db_pool_service()
    
    # Execute a query
    result = await service.execute_query("SELECT * FROM users LIMIT 5")
    print(f"Query result: {result}")
    
    # Use SQLAlchemy session
    async with service.get_session() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM users"))
        count = await result.scalar()
        print(f"User count: {count}")
    
    # Health check
    health = await service.health_check()
    print(f"Health status: {health}")
    
    # Pool statistics
    stats = await service.get_pool_stats()
    print(f"Pool stats: {stats}")
    
    # Cleanup
    await service.cleanup()

if __name__ == "__main__":
    asyncio.run(example_usage())