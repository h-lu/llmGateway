import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from gateway.app.api.student_register import router as student_register_router
from gateway.app.core.config import settings
from gateway.app.db.async_session import get_db
from gateway.app.db.base import Base


def _sqlite_url_from_absolute_path(path: str) -> str:
    # SQLAlchemy expects 4 slashes for absolute paths. The path already starts
    # with '/', so strip it when appending after '////'.
    return f"sqlite+aiosqlite:////{path.lstrip('/')}"


def test_student_self_registration_happy_path(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "teachproxy_register_test.db"
    engine = create_async_engine(_sqlite_url_from_absolute_path(str(db_path)))

    async def init_db() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(init_db())

    session_maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async def override_get_db():
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    monkeypatch.setattr(settings, "student_registration_code", "course-123")
    monkeypatch.setattr(settings, "student_self_register_default_quota", 12345)

    app = FastAPI()
    app.include_router(student_register_router)
    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/v1/student/register",
        json={
            "registration_code": "course-123",
            "name": " Alice ",
            "email": "ALICE@example.com ",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert isinstance(data.get("api_key"), str)
    assert data["api_key"]
    assert data["student"]["name"] == "Alice"
    assert data["student"]["email"] == "alice@example.com"
    assert data["student"]["current_week_quota"] == 12345

    asyncio.run(engine.dispose())


def test_student_self_registration_rejects_wrong_code(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "teachproxy_register_test.db"
    engine = create_async_engine(_sqlite_url_from_absolute_path(str(db_path)))

    async def init_db() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(init_db())

    session_maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    monkeypatch.setattr(settings, "student_registration_code", "course-123")

    app = FastAPI()
    app.include_router(student_register_router)
    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/v1/student/register",
        json={
            "registration_code": "wrong",
            "name": "Alice",
            "email": "alice@example.com",
        },
    )
    assert resp.status_code == 401

    asyncio.run(engine.dispose())


def test_student_self_registration_disabled_when_code_missing(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "teachproxy_register_test.db"
    engine = create_async_engine(_sqlite_url_from_absolute_path(str(db_path)))

    async def init_db() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(init_db())

    session_maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    monkeypatch.setattr(settings, "student_registration_code", "")

    app = FastAPI()
    app.include_router(student_register_router)
    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/v1/student/register",
        json={
            "registration_code": "course-123",
            "name": "Alice",
            "email": "alice@example.com",
        },
    )
    assert resp.status_code == 404

    asyncio.run(engine.dispose())


def test_student_self_registration_rejects_duplicate_email(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "teachproxy_register_test.db"
    engine = create_async_engine(_sqlite_url_from_absolute_path(str(db_path)))

    async def init_db() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(init_db())

    session_maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async def override_get_db():
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    monkeypatch.setattr(settings, "student_registration_code", "course-123")

    app = FastAPI()
    app.include_router(student_register_router)
    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app, raise_server_exceptions=False)

    payload = {
        "registration_code": "course-123",
        "name": "Alice",
        "email": "alice@example.com",
    }

    resp1 = client.post("/v1/student/register", json=payload)
    assert resp1.status_code == 201, resp1.text

    resp2 = client.post("/v1/student/register", json=payload)
    assert resp2.status_code == 409

    asyncio.run(engine.dispose())

