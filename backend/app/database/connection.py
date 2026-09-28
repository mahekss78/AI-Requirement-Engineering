"""
app/database/connection.py
==========================
Database engine and session factory for the AREA platform.

Responsibilities:
- Create a single SQLAlchemy engine connected to PostgreSQL using the
  DATABASE_URL from settings. The engine is shared across all requests.
- Expose a `SessionLocal` factory that creates per-request database sessions.
- Provide a `get_db` FastAPI dependency that yields a session and guarantees
  it is closed after the request completes (even on exception).
- Expose a `create_all_tables` helper called at application startup to
  materialise all ORM-defined tables that do not yet exist.

Connection Design:
- pool_pre_ping=True: validates connections before use, preventing
  "connection already closed" errors after PostgreSQL restarts.
- autocommit=False: every write must be explicitly committed, preserving
  ACID guarantees on the state machine transitions.
- autoflush=False: prevents SQLAlchemy from issuing unexpected SQL during
  attribute access, making behaviour predictable in async contexts.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from typing import Generator

from app.config import settings


# ------------------------------------------------------------------ #
# Declarative Base
# All ORM model classes in models.py inherit from this Base.
# SQLAlchemy uses it to discover tables when create_all_tables() is called.
# ------------------------------------------------------------------ #
class Base(DeclarativeBase):
    pass


# ------------------------------------------------------------------ #
# Engine
# A single engine instance is reused for the lifetime of the process.
# ------------------------------------------------------------------ #
engine_kwargs = {
    "echo": (settings.APP_ENV == "development"),
}
if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

# ------------------------------------------------------------------ #
# Session Factory
# SessionLocal() creates a new Session bound to the engine above.
# ------------------------------------------------------------------ #
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    class_=Session,
)


# ------------------------------------------------------------------ #
# FastAPI Dependency
# ------------------------------------------------------------------ #
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session per request.

    Usage in a route:
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...

    The session is always closed in the finally block, preventing
    connection leaks regardless of whether the request succeeded or raised.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ------------------------------------------------------------------ #
# Table Initialisation
# ------------------------------------------------------------------ #
def create_all_tables() -> None:
    """
    Create all tables defined via ORM models if they do not already exist.

    Called once from main.py on application startup. In production, Alembic
    migrations should be used instead; this helper is provided for the MVP
    to simplify local setup.

    Import must happen inside the function body to avoid circular imports:
    models.py imports Base from this module; importing models here at module
    level would form a circular dependency chain.
    """
    # Local import breaks the circular dependency
    import app.models.models as _models  # noqa: F401 — import triggers registration

    Base.metadata.create_all(bind=engine)

    if settings.DATABASE_URL.startswith("sqlite"):
        try:
            from sqlalchemy import inspect
            inspector = inspect(engine)
            with engine.connect() as conn:
                if inspector.has_table("documents"):
                    conn.execute(text("UPDATE documents SET project_id = '00000000-0000-0000-0000-000000000001' WHERE typeof(project_id) = 'integer'"))
                if inspector.has_table("requirements"):
                    conn.execute(text("UPDATE requirements SET project_id = '00000000-0000-0000-0000-000000000001' WHERE typeof(project_id) = 'integer'"))
                if inspector.has_table("projects"):
                    conn.execute(text("DELETE FROM projects WHERE typeof(id) = 'integer'"))
                conn.commit()
        except Exception:
            pass


def verify_connection() -> bool:
    """
    Execute a trivial query to confirm the database is reachable.
    Returns True on success, False on any connection error.
    Used in the /health endpoint.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
