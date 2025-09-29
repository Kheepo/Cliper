"""Initial database schema migration

Creates all the core tables for the video analysis application:
- users: User accounts linked to Supabase Auth
- user_settings: User preferences and configuration
- jobs: Video analysis jobs (upload or URL-based)
- job_results: Analysis results with virality scores, hashtags, clips
- job_logs: Detailed logging for job processing
"""

from sqlalchemy import create_engine, MetaData
from api.models.database_models import Base
from api.database import engine
import logging

logger = logging.getLogger(__name__)

def upgrade():
    """Create all tables defined in the models"""
    try:
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to create database tables: {str(e)}")
        raise e

def downgrade():
    """Drop all tables (use with caution!)"""
    try:
        logger.warning("Dropping all database tables...")
        Base.metadata.drop_all(bind=engine)
        logger.info("Database tables dropped successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to drop database tables: {str(e)}")
        raise e

def check_tables_exist():
    """Check if all required tables exist"""
    try:
        metadata = MetaData()
        metadata.reflect(bind=engine)
        
        required_tables = {'users', 'user_settings', 'jobs', 'job_results', 'job_logs'}
        existing_tables = set(metadata.tables.keys())
        
        missing_tables = required_tables - existing_tables
        
        if missing_tables:
            logger.warning(f"Missing tables: {missing_tables}")
            return False
        else:
            logger.info("All required tables exist")
            return True
            
    except Exception as e:
        logger.error(f"Failed to check table existence: {str(e)}")
        return False

if __name__ == "__main__":
    # Run migration when script is executed directly
    upgrade()