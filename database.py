import os
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DEFAULT_DATABASE_URL = "sqlite:///./task_manager.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def _get_engine_kwargs(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


engine = create_engine(DATABASE_URL, **_get_engine_kwargs(DATABASE_URL))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    import models  # noqa: F401

    last_error = None
    for _ in range(10):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except Exception as error:
            last_error = error
            time.sleep(2)
    raise last_error


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
