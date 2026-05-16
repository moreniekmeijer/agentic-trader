"""
Database connectie en session management.
DATABASE_URL in .env: postgresql://user:password@localhost:5432/agentic_trader
"""

from __future__ import annotations

import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from agentic_trader.database.models import Base

_engine: Engine | None = None
SessionLocal = sessionmaker(autocommit=False, autoflush=False)


def get_engine() -> Engine:
    global _engine

    if _engine is not None:
        return _engine

    load_dotenv(os.getenv("ENV_FILE"))
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    _engine = create_engine(
        database_url,
        pool_pre_ping=True,  # detecteer verbroken connecties
        pool_size=5,
        max_overflow=10,
    )
    SessionLocal.configure(bind=_engine)

    return _engine


@contextmanager
def get_session():
    get_engine()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_tables() -> None:
    """Aanmaken van alle tabellen (gebruik Alembic voor productie-migraties)."""
    Base.metadata.create_all(bind=get_engine())


def drop_tables() -> None:
    """Verwijder alle tabellen."""
    Base.metadata.drop_all(bind=get_engine())
