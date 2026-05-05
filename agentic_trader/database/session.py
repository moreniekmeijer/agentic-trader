"""
Database connectie en session management.
DATABASE_URL in .env: postgresql://user:password@localhost:5432/agentic_trader
"""

from __future__ import annotations

import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agentic_trader.database.models import Base

load_dotenv(os.getenv("ENV_FILE"))

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # detecteer verbroken connecties
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_session():
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
    Base.metadata.create_all(bind=engine)


def drop_tables() -> None:
    """Verwijder alle tabellen."""
    Base.metadata.drop_all(bind=engine)
