"""Pytest configuration with isolated temporary SQLite database and storage directory."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Configure test environment before importing application modules
_TMP_DIR = tempfile.mkdtemp(prefix="uniforge_test_")
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{Path(_TMP_DIR, 'test.db').as_posix()}"
os.environ["DATABASE_URL_SYNC"] = f"sqlite:///{Path(_TMP_DIR, 'test.db').as_posix()}"
os.environ["LOCAL_STORAGE_PATH"] = str(Path(_TMP_DIR, "storage"))
os.environ["RATE_LIMIT_REQUESTS_PER_MINUTE"] = "10000"
os.environ["OPENAI_API_KEY"] = ""
os.environ["IMAGE_PROVIDER"] = "none"

from app.core.database import Base, get_db  # noqa: E402
from app.core.rate_limit import rate_limiter  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest_asyncio.fixture(scope="function")
async def db_engine(tmp_path: Path):
    db_file = tmp_path / "case.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_engine):
    rate_limiter.reset()
    session_factory = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
