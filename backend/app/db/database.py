"""Database setup and session utilities."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
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


def init_db() -> None:
    """Create DB tables for local/dev use."""
    import app.models.auth  # noqa: F401
    import app.models.energy_plan  # noqa: F401
    import app.models.meter_data  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_schema_upgrades()


def _ensure_sqlite_schema_upgrades() -> None:
    """Apply lightweight schema upgrades for local SQLite DBs."""
    if not settings.database_url.startswith("sqlite"):
        return

    required_columns = {
        "service_address": "ALTER TABLE user_nmis ADD COLUMN service_address VARCHAR(512)",
        "suburb": "ALTER TABLE user_nmis ADD COLUMN suburb VARCHAR(128)",
        "state": "ALTER TABLE user_nmis ADD COLUMN state VARCHAR(8)",
        "postcode": "ALTER TABLE user_nmis ADD COLUMN postcode VARCHAR(8)",
        "latitude": "ALTER TABLE user_nmis ADD COLUMN latitude FLOAT",
        "longitude": "ALTER TABLE user_nmis ADD COLUMN longitude FLOAT",
        "geocode_source": "ALTER TABLE user_nmis ADD COLUMN geocode_source VARCHAR(32)",
        "geocoded_at": "ALTER TABLE user_nmis ADD COLUMN geocoded_at DATETIME",
    }

    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(user_nmis)")).fetchall()
        existing = {row[1] for row in rows}
        for column_name, ddl in required_columns.items():
            if column_name in existing:
                continue
            conn.execute(text(ddl))
