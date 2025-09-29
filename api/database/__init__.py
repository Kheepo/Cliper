"""Database package initialization."""

from .config import (
    engine,
    SessionLocal,
    Base,
    get_database_session,
    get_db_session,
    create_tables,
    check_database_connection,
    get_db_health
)

# Alias for FastAPI dependency injection
get_db = get_database_session

__all__ = [
    "engine",
    "SessionLocal", 
    "Base",
    "get_database_session",
    "get_db_session",
    "get_db",
    "create_tables",
    "check_database_connection",
    "get_db_health"
]