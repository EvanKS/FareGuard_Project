"""
FareGuard Database Connection & Engine Management

Primary production backend: PostgreSQL (configured via DATABASE_URL).
Local development/testing fallback: SQLite (data/fareguard.db) — used automatically
when PostgreSQL is unavailable. SQLite is NOT intended for production use.

Manages PostgreSQL connection pools, SQLAlchemy sessions, and automated fallback.
"""

import logging
import os
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

_engine: Optional[Engine] = None
_SessionFactory: Optional[sessionmaker] = None


def get_db_url() -> str:
    """Returns the configured database URL."""
    return settings.DATABASE_URL


def create_db_engine(url: Optional[str] = None, echo: bool = False) -> Engine:
    """
    Creates a SQLAlchemy database engine.
    Tries PostgreSQL first; if unavailable and in local mode, falls back to SQLite.
    """
    target_url = url or get_db_url()

    # Determine if PostgreSQL or SQLite
    if target_url.startswith("postgresql"):
        try:
            engine = create_engine(
                target_url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                connect_args={"connect_timeout": 3},
                echo=echo,
            )
            # Test live connection
            with engine.connect() as conn:
                logger.info(f"Connected to PostgreSQL database at: {target_url.split('@')[-1]}")
            return engine
        except Exception as e:
            logger.warning(
                f"PostgreSQL connection to {target_url} failed ({e}). "
                "Initializing local SQLite persistence engine (data/fareguard.db)."
            )
            # Fallback to local SQLite file
            sqlite_path = settings.DATA_DIR / "fareguard.db"
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            fallback_url = f"sqlite:///{sqlite_path}"
            engine = create_engine(
                fallback_url,
                connect_args={"check_same_thread": False},
                echo=echo,
            )
            # Enable SQLite foreign keys
            @event.listens_for(engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

            return engine
    else:
        # SQLite or other specified dialect
        engine = create_engine(
            target_url,
            connect_args={"check_same_thread": False} if "sqlite" in target_url else {},
            echo=echo,
        )
        if "sqlite" in target_url:
            @event.listens_for(engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
        return engine


def get_engine() -> Engine:
    """Singleton getter for the database engine."""
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session_factory(engine: Optional[Engine] = None) -> sessionmaker:
    """Returns a sessionmaker bound to the active engine."""
    global _SessionFactory
    if engine is not None:
        return sessionmaker(autocommit=False, autoflush=False, bind=engine)
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionFactory


def get_db() -> Generator[Session, None, None]:
    """FastAPI & context dependency yielding a transactional DB session."""
    SessionFactory = get_session_factory()
    db: Session = SessionFactory()
    try:
        yield db
    finally:
        db.close()


def init_db(engine: Optional[Engine] = None) -> None:
    """Creates all database tables defined in SQLAlchemy Base."""
    eng = engine or get_engine()
    # Import models so they are registered on Base
    from database import models  # noqa: F401
    Base.metadata.create_all(bind=eng)
    logger.info("Database tables initialized successfully.")


def reset_db(engine: Optional[Engine] = None) -> None:
    """Drops and re-creates all database tables (for clean test fixtures)."""
    eng = engine or get_engine()
    from database import models  # noqa: F401
    Base.metadata.drop_all(bind=eng)
    Base.metadata.create_all(bind=eng)
    logger.info("Database tables reset successfully.")
