# backend/app/core/database.py
"""
Database configuration and session management.

Supports both SQLite (development) and PostgreSQL+PostGIS (production).
Environment-specific configuration via DATABASE_URL or .env file.
"""

from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import NullPool, QueuePool
import os
import warnings
import sys

# Add backend to path for imports
backend_path = os.path.join(os.path.dirname(__file__), '..', '..')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Import settings for environment-based configuration.
# Phase 14: no longer falls back to "backend.app.core.config" on
# ImportError - see app/main.py's import block for why that fallback
# pattern is dangerous (it silently duplicates model registration under a
# second SQLAlchemy Base). The sys.path insertion just above guarantees
# "app.core.config" resolves, so a single plain import is both simpler and
# safer.
from app.core.config import settings

# Database URL configuration
# Priority: 1. Environment variable DATABASE_URL, 2. Settings-based URL, 3. SQLite fallback

# SQLite is configured with a path that is relative to the *project root* (e.g.
# "backend/trackx.db"). SQLAlchemy treats it as relative to the current working
# directory, so running from `backend/` would resolve to `backend/backend/trackx.db`
# and fail. Anchor the path to this file's repo root so it works from any CWD.
# database.py -> app -> core -> backend -> <project-root> (4 levels up)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_sqlite_path = settings.SQLITE_DB_PATH if settings.SQLITE_DB_PATH else "backend/trackx.db"
if not os.path.isabs(_sqlite_path):
    _sqlite_path = os.path.join(_PROJECT_ROOT, _sqlite_path)
_sqlite_url = f"sqlite:///{_sqlite_path}"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    settings.SYNC_DATABASE_URI if not settings.USE_SQLITE else _sqlite_url
)

# Database type detection
IS_POSTGIS = DATABASE_URL.startswith("postgresql")
IS_SQLITE = DATABASE_URL.startswith("sqlite")

# PostGIS spatial extension setup
if IS_POSTGIS:
    try:
        from geoalchemy2 import Geometry
        from sqlalchemy.engine.url import make_url
        # Ensure PostGIS extension is available
        print("[PostGIS] Spatial database enabled")
    except ImportError:
        warnings.warn("PostGIS requested but geoalchemy2 not installed. Falling back to basic PostgreSQL.")
        IS_POSTGIS = False

# Create engine with appropriate configuration
if IS_SQLITE:
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False}  # SQLite specific
    )
    print("[SQLite] Database configured for development")
elif IS_POSTGIS:
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # Verify connections before using
    )
    print("[PostgreSQL+PostGIS] Database configured for production")
else:
    # Fallback for basic PostgreSQL without PostGIS
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
    )
    print("[PostgreSQL] Database configured (without PostGIS)")

# Create session factory
SessionLocal = sessionmaker(
    engine,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()

# Metadata for migrations
metadata = MetaData()


def get_db() -> Session:
    """
    Dependency for getting database sessions.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database tables.
    For PostGIS, also creates the spatial extension if needed.
    """
    if IS_POSTGIS:
        # Create PostGIS extension if it doesn't exist
        try:
            with engine.connect() as conn:
                conn.execute("CREATE EXTENSION IF NOT EXISTS postgis")
                conn.commit()
                print("[OK] PostGIS extension enabled")
        except Exception as e:
            print(f"[WARNING] Could not enable PostGIS extension: {e}")
    
    Base.metadata.create_all(engine)
    print("[OK] Database tables created")


def check_db_connection() -> bool:
    """
    Test database connection.
    Returns True if connection successful, False otherwise.
    """
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")
        return False


def get_db_info() -> dict:
    """
    Get database connection information for monitoring.
    """
    return {
        "database_type": "PostgreSQL+PostGIS" if IS_POSTGIS else "SQLite" if IS_SQLITE else "PostgreSQL",
        "database_url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,  # Hide credentials
        "is_postgis": IS_POSTGIS,
        "is_sqlite": IS_SQLITE,
        "connection_healthy": check_db_connection()
    }
