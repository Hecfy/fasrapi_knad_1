from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import SessionLocal, get_db, init_db

SORTABLE_TASK_FIELDS = {"title", "status", "priority", "created_at"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Task Manager API",
    description="API для управления задачами с аутентификацией",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def clear_task_cache() -> None:
    get_cached_tasks.cache_clear()


def _build_tasks_query(
    db: Session,
    user_id: int,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    status_filter: Optional[str] = None,
):
    query = db.query(models.Task).filter(models.Task.owner_id == user_id)

    if search:
        query = query.filter(
            (models.Task.title.ilike(f"%{search}%"))
            | (models.Task.description.ilike(f"%{search}%"))
        )

    if status_filter:
        query = query.filter(models.Task.status == status_filter)

    if sort_by:
        query = query.order_by(getattr(models.Task, sort_by).asc())
    else:
        query = query.order_by(models.Task.created_at.desc())

    return query


def _serialize_task(task: models.Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "created_at": task.created_at,
        "owner_id": task.owner_id,
    }


@app.post("/auth/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(
        models.User.login == user.login
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Пользователь с таким логином уже существует"
        )

    db_user = models.User(
        login=user.login,
        hashed_password=auth.get_password_hash(user.password)
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@app.post("/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    db_user = db.query(models.User).filter(
        models.User.login == form_data.username
    ).first()

    if not db_user or not auth.verify_password(form_data.password, db_user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token = auth.create_access_token(
        data={"sub": str(db_user.id)},
        expires_delta=timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/tasks", response_model=schemas.TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
        task: schemas.TaskCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_user)
):

    db_task = models.Task(
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        owner_id=current_user.id,
        created_at=datetime.now(timezone.utc)
    )

    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    clear_task_cache()

    return db_task


@app.get("/tasks", response_model=List[schemas.TaskOut])
def get_tasks(
        skip: int = Query(0, ge=0, description="Пропустить N задач (пагинация)"),
        limit: int = Query(10, ge=1, le=100, description="Количество задач (макс 100)"),
        sort_by: Optional[str] = Query(None, pattern="^(title|status|priority|created_at)$"),
        search: Optional[str] = Query(None, min_length=1, description="Поиск по заголовку и описанию"),
        status_filter: Optional[str] = Query(None, description="Фильтр по статусу"),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_user)
):
    cached_tasks = get_cached_tasks(
        current_user.id,
        search or "",
        sort_by or "",
        status_filter or "",
    )

    return list(cached_tasks[skip: skip + limit])


@app.put("/tasks/{task_id}", response_model=schemas.TaskOut)
def update_task(
        task_id: int,
        task_update: schemas.TaskUpdate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_user)
):

    db_task = db.query(models.Task) \
        .filter(
        models.Task.id == task_id,
        models.Task.owner_id == current_user.id
    ) \
        .first()

    if not db_task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    update_data = task_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(db_task, field, value)

    db.commit()
    db.refresh(db_task)
    clear_task_cache()

    return db_task


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
        task_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_user)
):

    db_task = db.query(models.Task) \
        .filter(
        models.Task.id == task_id,
        models.Task.owner_id == current_user.id
    ) \
        .first()

    if not db_task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    db.delete(db_task)
    db.commit()
    clear_task_cache()

    return None


@lru_cache(maxsize=128)
def get_cached_tasks(user_id: int, search: str, sort_by: str, status_filter: str):
    normalized_sort = sort_by if sort_by in SORTABLE_TASK_FIELDS else None

    with SessionLocal() as db:
        tasks = _build_tasks_query(
            db,
            user_id=user_id,
            search=search or None,
            sort_by=normalized_sort,
            status_filter=status_filter or None,
        ).all()

    return tuple(_serialize_task(task) for task in tasks)
