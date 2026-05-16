from collections.abc import Generator

from sqlalchemy.orm import Session

from agentic_trader.database.session import SessionLocal, get_engine


def get_db() -> Generator[Session, None, None]:
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
