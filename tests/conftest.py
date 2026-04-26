import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TEST_DB_PATH = Path(tempfile.gettempdir()) / "task_manager_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

import auth
import main
import models
from database import Base, SessionLocal, engine


@pytest.fixture(autouse=True)
def reset_database():
    main.clear_task_cache()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    main.clear_task_cache()


@pytest.fixture
def client():
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def create_user(db_session):
    def _create_user(login: str = "user1", password: str = "password123"):
        user = models.User(
            login=login,
            hashed_password=auth.get_password_hash(password),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create_user


@pytest.fixture
def create_task(create_user, db_session):
    def _create_task(
        *,
        owner=None,
        title: str = "Task",
        description: str = "Task description",
        status: str = "pending",
        priority: int = 1,
        created_at: datetime | None = None,
    ):
        task_owner = owner or create_user()
        task = models.Task(
            title=title,
            description=description,
            status=status,
            priority=priority,
            owner_id=task_owner.id,
            created_at=created_at or datetime.now(timezone.utc),
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        return task

    return _create_task


@pytest.fixture
def register_user(client):
    def _register_user(login: str = "api-user", password: str = "password123"):
        response = client.post(
            "/auth/register",
            json={"login": login, "password": password},
        )
        assert response.status_code == 201
        return response.json()

    return _register_user


@pytest.fixture
def login_user(client):
    def _login_user(login: str = "api-user", password: str = "password123"):
        response = client.post(
            "/auth/register",
            json={"login": login, "password": password},
        )
        assert response.status_code in {201, 400}
        response = client.post(
            "/auth/login",
            data={"username": login, "password": password},
        )
        assert response.status_code == 200
        return response.json()

    return _login_user


@pytest.fixture
def auth_headers(login_user):
    def _auth_headers(login: str = "api-user", password: str = "password123"):
        token_data = login_user(login=login, password=password)
        return {"Authorization": f"Bearer {token_data['access_token']}"}

    return _auth_headers


@pytest.fixture
def stale_task_snapshot(create_user, create_task):
    user = create_user(login="cache-user", password="password123")
    create_task(
        owner=user,
        title="Cached task",
        description="First value",
        priority=2,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    main.clear_task_cache()
    return user
