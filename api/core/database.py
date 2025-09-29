"""Database connection and pool management."""

import asyncio
import logging
from typing import Optional
import asyncpg
from .config import settings

logger = logging.getLogger(__name__)

# Global connection pool
_db_pool: Optional[asyncpg.Pool] = None

async def create_db_pool() -> asyncpg.Pool:
    """Create database connection pool."""
    global _db_pool
    
    if _db_pool is None:
        try:
            _db_pool = await asyncpg.create_pool(
                settings.database_url,
                min_size=1,
                max_size=10,
                command_timeout=60
            )
            logger.info("Database connection pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise
    
    return _db_pool

async def get_db_pool() -> Optional[asyncpg.Pool]:
    """Get database connection pool."""
    global _db_pool
    
    if _db_pool is None:
        try:
            _db_pool = await create_db_pool()
        except Exception as e:
            logger.error(f"Failed to get database pool: {e}")
            return None
    
    return _db_pool

async def close_db_pool():
    """Close database connection pool."""
    global _db_pool
    
    if _db_pool:
        await _db_pool.close()
        _db_pool = None
        logger.info("Database connection pool closed")

async def test_db_connection() -> bool:
    """Test database connection."""
    try:
        pool = await get_db_pool()
        if pool is None:
            return False
            
        async with pool.acquire() as conn:
            await conn.fetchval('SELECT 1')
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False