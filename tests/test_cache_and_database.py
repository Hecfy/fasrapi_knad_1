from sqlalchemy import inspect

import main
import models
from database import Base, _get_engine_kwargs, engine, init_db


def test_get_engine_kwargs_for_sqlite_and_postgres():
    sqlite_kwargs = _get_engine_kwargs("sqlite:///./task_manager.db")
    postgres_kwargs = _get_engine_kwargs("postgresql+psycopg://user:pass@localhost/db")

    assert sqlite_kwargs == {"connect_args": {"check_same_thread": False}}
    assert postgres_kwargs == {}


def test_init_db_creates_required_tables():
    Base.metadata.drop_all(bind=engine)

    init_db()
    inspector = inspect(engine)

    assert {"tasks", "users"}.issubset(set(inspector.get_table_names()))


def test_get_cached_tasks_returns_stale_data_until_cache_is_cleared(create_user, create_task, db_session):
    user = create_user(login="cache-user", password="password123")
    task = create_task(owner=user, description="Original description")

    first_snapshot = main.get_cached_tasks(user.id, "", "", "")
    db_task = db_session.query(models.Task).filter(models.Task.id == task.id).first()
    db_task.description = "Updated description"
    db_session.commit()
    second_snapshot = main.get_cached_tasks(user.id, "", "", "")

    main.clear_task_cache()
    refreshed_snapshot = main.get_cached_tasks(user.id, "", "", "")

    assert first_snapshot[0]["description"] == "Original description"
    assert second_snapshot[0]["description"] == "Original description"
    assert refreshed_snapshot[0]["description"] == "Updated description"
