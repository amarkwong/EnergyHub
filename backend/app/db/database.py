"""Database setup and session utilities."""
from __future__ import annotations

from collections.abc import Generator

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import get_settings

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for request scope."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _alembic_cfg() -> AlembicConfig:
    """Build an Alembic config that points at our migrations directory."""
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parent.parent.parent
    cfg = AlembicConfig(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "migrations"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def init_db() -> None:
    """Run Alembic migrations to bring the DB schema up to date."""
    command.upgrade(_alembic_cfg(), "head")
