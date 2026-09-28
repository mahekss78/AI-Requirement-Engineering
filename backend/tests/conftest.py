"""
tests/conftest.py
=================
Shared pytest fixtures for the AREA backend test suite.

Phase 1 provides two foundational fixtures:
- `test_settings`: Returns a Settings instance pointing at a SQLite
  in-memory database so tests never touch the real PostgreSQL instance.
- `test_db`: Yields a clean database session backed by that SQLite DB,
  creating and dropping all tables around each test function.

Phase 2 will add:
- `mock_llm`: An AsyncMock replacing the OpenAI client.
- `mock_rag`: An AsyncMock replacing ChromaDB queries.
"""

import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Generator

from app.database.connection import Base
from app.config import Settings


TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """
    Returns a Settings instance configured for testing.
    Uses SQLite in-memory so no PostgreSQL instance is required.
    """
    return Settings(
        DATABASE_URL=TEST_DATABASE_URL,
        OPENAI_API_KEY="sk-test-key",   # placeholder; LLM calls will be mocked
    )


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """
    Yields a clean database session for a single test.

    - Creates all tables before the test.
    - Rolls back all writes after the test, ensuring test isolation.
    - Drops all tables at teardown to prevent state leakage between tests.
    """
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},  # Required for SQLite
        poolclass=StaticPool,                       # Shared in-memory pool across threads
    )
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    # Import models to register them with Base.metadata
    import app.models.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    session = TestingSession()


    from app.database.connection import get_db
    from main import app

    def _override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db

    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        session.close()
        Base.metadata.drop_all(bind=engine)

