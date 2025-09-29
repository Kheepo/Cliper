#!/usr/bin/env python3
"""
Database Optimization Script

This script provides comprehensive database optimization including:
- Index creation and management
- Query performance analysis
- Connection pooling optimization
- Database maintenance tasks
- Performance monitoring
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from contextlib import asynccontextmanager

import asyncpg
from supabase import create_client, Client
from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.pool import QueuePool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from api.config.environments import get_environment_config
from api.utils.structured_logging import get_logger

logger = get_logger(__name__)

@dataclass
class IndexDefinition:
    """Definition for database index"""
    table: str
    columns: List[str]
    name: Optional[str] = None
    unique: bool = False
    partial: Optional[str] = None
    method: str = "btree"
    concurrent: bool = True

@dataclass
class QueryPerformanceMetrics:
    """Query performance metrics"""
    query: str
    execution_time: float
    rows_examined: int
    rows_returned: int
    index_usage: Dict[str, Any]
    timestamp: datetime

class DatabaseOptimizer:
    """Comprehensive database optimization manager"""
    
    def __init__(self):
        self.config = get_environment_config()
        self.supabase: Optional[Client] = None
        self.async_engine = None
        self.connection_pool = None
        self.performance_metrics: List[QueryPerformanceMetrics] = []
        
        # Define critical indexes for performance
        self.critical_indexes = [
            # Users table indexes
            IndexDefinition(
                table="users",
                columns=["auth_id"],
                name="idx_users_auth_id",
                unique=True
            ),
            IndexDefinition(
                table="users",
                columns=["email"],
                name="idx_users_email",
                unique=True
            ),
            IndexDefinition(
                table="users",
                columns=["created_at"],
                name="idx_users_created_at"
            ),
            
            # Jobs table indexes
            IndexDefinition(
                table="jobs",
                columns=["user_id"],
                name="idx_jobs_user_id"
            ),
            IndexDefinition(
                table="jobs",
                columns=["status"],
                name="idx_jobs_status"
            ),
            IndexDefinition(
                table="jobs",
                columns=["created_at"],
                name="idx_jobs_created_at"
            ),
            IndexDefinition(
                table="jobs",
                columns=["user_id", "status"],
                name="idx_jobs_user_status"
            ),
            IndexDefinition(
                table="jobs",
                columns=["user_id", "created_at"],
                name="idx_jobs_user_created"
            ),
            
            # Job results indexes
            IndexDefinition(
                table="job_results",
                columns=["job_id"],
                name="idx_job_results_job_id",
                unique=True
            ),
            IndexDefinition(
                table="job_results",
                columns=["created_at"],
                name="idx_job_results_created_at"
            ),
            
            # Video clips indexes
            IndexDefinition(
                table="video_clips",
                columns=["job_id"],
                name="idx_video_clips_job_id"
            ),
            IndexDefinition(
                table="video_clips",
                columns=["virality_score"],
                name="idx_video_clips_virality"
            ),
            IndexDefinition(
                table="video_clips",
                columns=["job_id", "virality_score"],
                name="idx_video_clips_job_virality"
            ),
            
            # User settings indexes
            IndexDefinition(
                table="user_settings",
                columns=["user_id"],
                name="idx_user_settings_user_id",
                unique=True
            ),
            
            # API keys indexes (if table exists)
            IndexDefinition(
                table="api_keys",
                columns=["user_id"],
                name="idx_api_keys_user_id"
            ),
            IndexDefinition(
                table="api_keys",
                columns=["key_hash"],
                name="idx_api_keys_hash",
                unique=True
            ),
            IndexDefinition(
                table="api_keys",
                columns=["status"],
                name="idx_api_keys_status"
            ),
            IndexDefinition(
                table="api_keys",
                columns=["expires_at"],
                name="idx_api_keys_expires",
                partial="WHERE expires_at IS NOT NULL"
            ),
            
            # Sessions indexes (if table exists)
            IndexDefinition(
                table="user_sessions",
                columns=["user_id"],
                name="idx_sessions_user_id"
            ),
            IndexDefinition(
                table="user_sessions",
                columns=["session_id"],
                name="idx_sessions_session_id",
                unique=True
            ),
            IndexDefinition(
                table="user_sessions",
                columns=["expires_at"],
                name="idx_sessions_expires"
            ),
        ]
    
    async def initialize(self):
        """Initialize database connections and optimization tools"""
        try:
            # Initialize Supabase client
            supabase_url = self.config.get("SUPABASE_URL")
            supabase_key = self.config.get("SUPABASE_SERVICE_ROLE_KEY")
            
            if supabase_url and supabase_key:
                self.supabase = create_client(supabase_url, supabase_key)
                logger.info("Supabase client initialized for optimization")
            
            # Initialize async engine with optimized pool settings
            database_url = self.config.get("DATABASE_URL")
            if database_url:
                self.async_engine = create_async_engine(
                    database_url,
                    poolclass=QueuePool,
                    pool_size=20,
                    max_overflow=30,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    echo=False
                )
                logger.info("Async database engine initialized")
            
            # Initialize direct asyncpg connection pool
            if database_url:
                self.connection_pool = await asyncpg.create_pool(
                    database_url,
                    min_size=5,
                    max_size=25,
                    command_timeout=60,
                    server_settings={
                        'jit': 'off',
                        'application_name': 'cliper_optimizer'
                    }
                )
                logger.info("AsyncPG connection pool initialized")
                
        except Exception as e:
            logger.error(f"Failed to initialize database optimizer: {e}")
            raise
    
    async def analyze_table_performance(self, table_name: str) -> Dict[str, Any]:
        """Analyze performance metrics for a specific table"""
        if not self.connection_pool:
            raise RuntimeError("Database connection not initialized")
        
        async with self.connection_pool.acquire() as conn:
            # Get table statistics
            stats_query = """
            SELECT 
                schemaname,
                tablename,
                attname,
                n_distinct,
                correlation,
                most_common_vals,
                most_common_freqs
            FROM pg_stats 
            WHERE tablename = $1 AND schemaname = 'public'
            """
            
            table_stats = await conn.fetch(stats_query, table_name)
            
            # Get index usage statistics
            index_query = """
            SELECT 
                indexrelname as index_name,
                idx_tup_read,
                idx_tup_fetch,
                idx_scan,
                idx_blks_read,
                idx_blks_hit
            FROM pg_stat_user_indexes 
            WHERE relname = $1
            """
            
            index_stats = await conn.fetch(index_query, table_name)
            
            # Get table size information
            size_query = """
            SELECT 
                pg_size_pretty(pg_total_relation_size($1)) as total_size,
                pg_size_pretty(pg_relation_size($1)) as table_size,
                pg_size_pretty(pg_total_relation_size($1) - pg_relation_size($1)) as index_size
            """
            
            size_info = await conn.fetchrow(size_query, table_name)
            
            return {
                "table_name": table_name,
                "statistics": [dict(row) for row in table_stats],
                "indexes": [dict(row) for row in index_stats],
                "size_info": dict(size_info) if size_info else {},
                "analyzed_at": datetime.now().isoformat()
            }
    
    async def create_index(self, index_def: IndexDefinition) -> bool:
        """Create a database index with the given definition"""
        if not self.connection_pool:
            raise RuntimeError("Database connection not initialized")
        
        try:
            # Generate index name if not provided
            if not index_def.name:
                index_def.name = f"idx_{index_def.table}_{'_'.join(index_def.columns)}"
            
            # Build CREATE INDEX statement
            columns_str = ", ".join(index_def.columns)
            
            create_sql = f"CREATE"
            if index_def.unique:
                create_sql += " UNIQUE"
            
            create_sql += f" INDEX"
            if index_def.concurrent:
                create_sql += " CONCURRENTLY"
            
            create_sql += f" IF NOT EXISTS {index_def.name}"
            create_sql += f" ON {index_def.table}"
            
            if index_def.method != "btree":
                create_sql += f" USING {index_def.method}"
            
            create_sql += f" ({columns_str})"
            
            if index_def.partial:
                create_sql += f" {index_def.partial}"
            
            async with self.connection_pool.acquire() as conn:
                logger.info(f"Creating index: {create_sql}")
                await conn.execute(create_sql)
                logger.info(f"Successfully created index {index_def.name}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to create index {index_def.name}: {e}")
            return False
    
    async def create_all_indexes(self) -> Dict[str, bool]:
        """Create all critical indexes for performance optimization"""
        results = {}
        
        for index_def in self.critical_indexes:
            try:
                # Check if table exists first
                if await self.table_exists(index_def.table):
                    success = await self.create_index(index_def)
                    results[index_def.name or f"{index_def.table}_{'_'.join(index_def.columns)}"] = success
                else:
                    logger.warning(f"Table {index_def.table} does not exist, skipping index creation")
                    results[index_def.name or f"{index_def.table}_{'_'.join(index_def.columns)}"] = False
            except Exception as e:
                logger.error(f"Error creating index for {index_def.table}: {e}")
                results[index_def.name or f"{index_def.table}_{'_'.join(index_def.columns)}"] = False
        
        return results
    
    async def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database"""
        if not self.connection_pool:
            return False
        
        try:
            async with self.connection_pool.acquire() as conn:
                result = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = $1 AND table_schema = 'public')",
                    table_name
                )
                return bool(result)
        except Exception as e:
            logger.error(f"Error checking if table {table_name} exists: {e}")
            return False
    
    async def analyze_slow_queries(self, duration_threshold: float = 1.0) -> List[Dict[str, Any]]:
        """Analyze slow queries from pg_stat_statements"""
        if not self.connection_pool:
            raise RuntimeError("Database connection not initialized")
        
        try:
            async with self.connection_pool.acquire() as conn:
                # Check if pg_stat_statements extension is available
                ext_check = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements')"
                )
                
                if not ext_check:
                    logger.warning("pg_stat_statements extension not available")
                    return []
                
                slow_queries = await conn.fetch("""
                    SELECT 
                        query,
                        calls,
                        total_exec_time,
                        mean_exec_time,
                        max_exec_time,
                        rows,
                        100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
                    FROM pg_stat_statements 
                    WHERE mean_exec_time > $1
                    ORDER BY mean_exec_time DESC 
                    LIMIT 20
                """, duration_threshold * 1000)  # Convert to milliseconds
                
                return [dict(row) for row in slow_queries]
                
        except Exception as e:
            logger.error(f"Error analyzing slow queries: {e}")
            return []
    
    async def optimize_table_statistics(self, table_name: str) -> bool:
        """Update table statistics for better query planning"""
        if not self.connection_pool:
            raise RuntimeError("Database connection not initialized")
        
        try:
            async with self.connection_pool.acquire() as conn:
                await conn.execute(f"ANALYZE {table_name}")
                logger.info(f"Updated statistics for table {table_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to update statistics for {table_name}: {e}")
            return False
    
    async def vacuum_analyze_all_tables(self) -> Dict[str, bool]:
        """Run VACUUM ANALYZE on all user tables"""
        if not self.connection_pool:
            raise RuntimeError("Database connection not initialized")
        
        results = {}
        
        try:
            async with self.connection_pool.acquire() as conn:
                # Get all user tables
                tables = await conn.fetch("""
                    SELECT tablename 
                    FROM pg_tables 
                    WHERE schemaname = 'public'
                """)
                
                for table_row in tables:
                    table_name = table_row['tablename']
                    try:
                        await conn.execute(f"VACUUM ANALYZE {table_name}")
                        results[table_name] = True
                        logger.info(f"VACUUM ANALYZE completed for {table_name}")
                    except Exception as e:
                        logger.error(f"VACUUM ANALYZE failed for {table_name}: {e}")
                        results[table_name] = False
                        
        except Exception as e:
            logger.error(f"Error during VACUUM ANALYZE operation: {e}")
        
        return results
    
    async def get_database_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive database performance report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "database_size": {},
            "table_analysis": {},
            "slow_queries": [],
            "index_usage": {},
            "connection_stats": {},
            "recommendations": []
        }
        
        try:
            if not self.connection_pool:
                await self.initialize()
            
            async with self.connection_pool.acquire() as conn:
                # Database size information
                db_size = await conn.fetchrow("""
                    SELECT 
                        pg_size_pretty(pg_database_size(current_database())) as total_size,
                        current_database() as database_name
                """)
                report["database_size"] = dict(db_size) if db_size else {}
                
                # Table sizes and row counts
                table_info = await conn.fetch("""
                    SELECT 
                        schemaname,
                        tablename,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                        n_tup_ins as inserts,
                        n_tup_upd as updates,
                        n_tup_del as deletes,
                        n_live_tup as live_rows,
                        n_dead_tup as dead_rows
                    FROM pg_stat_user_tables
                    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                """)
                
                report["table_analysis"] = [dict(row) for row in table_info]
                
                # Slow queries analysis
                report["slow_queries"] = await self.analyze_slow_queries()
                
                # Index usage statistics
                index_usage = await conn.fetch("""
                    SELECT 
                        schemaname,
                        tablename,
                        indexrelname,
                        idx_scan,
                        idx_tup_read,
                        idx_tup_fetch
                    FROM pg_stat_user_indexes
                    ORDER BY idx_scan DESC
                """)
                
                report["index_usage"] = [dict(row) for row in index_usage]
                
                # Connection statistics
                conn_stats = await conn.fetchrow("""
                    SELECT 
                        numbackends as active_connections,
                        xact_commit as transactions_committed,
                        xact_rollback as transactions_rolled_back,
                        blks_read as blocks_read,
                        blks_hit as blocks_hit,
                        tup_returned as tuples_returned,
                        tup_fetched as tuples_fetched,
                        tup_inserted as tuples_inserted,
                        tup_updated as tuples_updated,
                        tup_deleted as tuples_deleted
                    FROM pg_stat_database 
                    WHERE datname = current_database()
                """)
                
                report["connection_stats"] = dict(conn_stats) if conn_stats else {}
                
                # Generate recommendations
                report["recommendations"] = await self.generate_optimization_recommendations(report)
                
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            report["error"] = str(e)
        
        return report
    
    async def generate_optimization_recommendations(self, report: Dict[str, Any]) -> List[str]:
        """Generate optimization recommendations based on performance analysis"""
        recommendations = []
        
        try:
            # Check for tables with high dead tuple ratio
            for table in report.get("table_analysis", []):
                live_rows = table.get("live_rows", 0)
                dead_rows = table.get("dead_rows", 0)
                
                if live_rows > 0 and dead_rows / live_rows > 0.1:
                    recommendations.append(
                        f"Table {table['tablename']} has high dead tuple ratio ({dead_rows}/{live_rows}). Consider running VACUUM."
                    )
            
            # Check for unused indexes
            for index in report.get("index_usage", []):
                if index.get("idx_scan", 0) == 0:
                    recommendations.append(
                        f"Index {index['indexrelname']} on table {index['tablename']} is never used. Consider dropping it."
                    )
            
            # Check for slow queries
            slow_queries = report.get("slow_queries", [])
            if len(slow_queries) > 0:
                recommendations.append(
                    f"Found {len(slow_queries)} slow queries. Review and optimize these queries or add appropriate indexes."
                )
            
            # Check cache hit ratio
            conn_stats = report.get("connection_stats", {})
            blocks_read = conn_stats.get("blocks_read", 0)
            blocks_hit = conn_stats.get("blocks_hit", 0)
            
            if blocks_read + blocks_hit > 0:
                hit_ratio = blocks_hit / (blocks_read + blocks_hit)
                if hit_ratio < 0.95:
                    recommendations.append(
                        f"Database cache hit ratio is {hit_ratio:.2%}. Consider increasing shared_buffers."
                    )
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            recommendations.append("Error generating recommendations. Check logs for details.")
        
        return recommendations
    
    async def cleanup(self):
        """Clean up database connections"""
        try:
            if self.connection_pool:
                await self.connection_pool.close()
                logger.info("Database connection pool closed")
            
            if self.async_engine:
                await self.async_engine.dispose()
                logger.info("Async engine disposed")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

# Convenience functions for common optimization tasks
async def optimize_database():
    """Run complete database optimization"""
    optimizer = DatabaseOptimizer()
    
    try:
        await optimizer.initialize()
        
        logger.info("Starting database optimization...")
        
        # Create all critical indexes
        index_results = await optimizer.create_all_indexes()
        logger.info(f"Index creation results: {index_results}")
        
        # Update table statistics
        vacuum_results = await optimizer.vacuum_analyze_all_tables()
        logger.info(f"VACUUM ANALYZE results: {vacuum_results}")
        
        # Generate performance report
        report = await optimizer.get_database_performance_report()
        logger.info(f"Performance report generated with {len(report.get('recommendations', []))} recommendations")
        
        return {
            "index_creation": index_results,
            "vacuum_analyze": vacuum_results,
            "performance_report": report
        }
        
    finally:
        await optimizer.cleanup()

if __name__ == "__main__":
    # Run optimization when script is executed directly
    asyncio.run(optimize_database())