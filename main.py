from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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


INDEX_HTML = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Task Manager API</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #1f2933;
      --muted: #66788a;
      --line: #d8e0e8;
      --paper: #f7fafc;
      --panel: #ffffff;
      --primary: #0f766e;
      --primary-dark: #115e59;
      --danger: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      color: var(--ink);
      background: linear-gradient(135deg, #eef6f4 0%, #f8fafc 45%, #edf2f7 100%);
    }
    header {
      padding: 32px clamp(18px, 4vw, 56px) 20px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.74);
    }
    h1 { margin: 0 0 8px; font-size: clamp(28px, 5vw, 48px); }
    p { margin: 0; color: var(--muted); }
    main {
      display: grid;
      grid-template-columns: minmax(280px, 380px) 1fr;
      gap: 20px;
      padding: 24px clamp(18px, 4vw, 56px) 40px;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      box-shadow: 0 14px 34px rgba(31, 41, 51, 0.08);
    }
    h2 { margin: 0 0 14px; font-size: 20px; }
    form { display: grid; gap: 10px; margin-bottom: 16px; }
    label { display: grid; gap: 5px; color: var(--muted); font-size: 13px; }
    input, textarea, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px 11px;
      font: inherit;
      color: var(--ink);
      background: #fff;
    }
    textarea { min-height: 84px; resize: vertical; }
    button {
      border: 0;
      border-radius: 6px;
      padding: 10px 12px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      color: #fff;
      background: var(--primary);
    }
    button:hover { background: var(--primary-dark); }
    button.secondary { background: #415466; }
    button.danger { background: var(--danger); }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .status {
      min-height: 22px;
      margin: 12px 0;
      color: var(--muted);
      font-size: 14px;
    }
    .task-list {
      display: grid;
      gap: 12px;
    }
    .task {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: var(--paper);
    }
    .task h3 { margin: 0 0 6px; font-size: 18px; }
    .meta { color: var(--muted); font-size: 13px; margin-bottom: 10px; }
    @media (max-width: 820px) {
      main { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Task Manager</h1>
  </header>
  <main>
    <section>
      <h2>Пользователь</h2>
      <form id="auth-form">
        <label>Логин <input id="login" value="demo_user" minlength="3" maxlength="50" required></label>
        <label>Пароль <input id="password" value="password123" type="password" minlength="6" required></label>
        <div class="actions">
          <button type="button" id="register">Регистрация</button>
          <button type="submit" class="secondary">Войти</button>
        </div>
      </form>
      <div id="auth-status" class="status">Сначала зарегистрируйтесь или войдите.</div>
    </section>

    <section>
      <h2>Задачи</h2>
      <form id="task-form">
        <label>Название <input id="title" value="Docker demo task" maxlength="150" required></label>
        <label>Описание <textarea id="description" maxlength="500">Created from the containerized web UI</textarea></label>
        <label>Статус
          <select id="task-status">
            <option value="pending">pending</option>
            <option value="in_progress">in_progress</option>
            <option value="done">done</option>
          </select>
        </label>
        <label>Приоритет <input id="priority" type="number" min="1" max="5" value="2"></label>
        <button type="submit">Создать задачу</button>
      </form>
      <div class="actions">
        <button type="button" id="refresh" class="secondary">Обновить список</button>
      </div>
      <div id="task-status-line" class="status"></div>
      <div id="tasks" class="task-list"></div>
    </section>
  </main>
  <script>
    let token = "";
    const authStatus = document.getElementById("auth-status");
    const taskStatusLine = document.getElementById("task-status-line");
    const tasksNode = document.getElementById("tasks");

    function credentials() {
      return {
        login: document.getElementById("login").value,
        password: document.getElementById("password").value,
      };
    }

    function authHeaders() {
      return { Authorization: `Bearer ${token}` };
    }

    async function parseResponse(response) {
      const text = await response.text();
      const data = text ? JSON.parse(text) : null;
      if (!response.ok) {
        throw new Error(data?.detail || response.statusText);
      }
      return data;
    }

    document.getElementById("register").addEventListener("click", async () => {
      try {
        const body = credentials();
        await parseResponse(await fetch("/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }));
        authStatus.textContent = "Пользователь зарегистрирован. Теперь можно войти.";
      } catch (error) {
        authStatus.textContent = error.message;
      }
    });

    document.getElementById("auth-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const body = credentials();
        const params = new URLSearchParams({ username: body.login, password: body.password });
        const data = await parseResponse(await fetch("/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: params,
        }));
        token = data.access_token;
        authStatus.textContent = "Вход выполнен. Можно работать с задачами.";
        await loadTasks();
      } catch (error) {
        authStatus.textContent = error.message;
      }
    });

    document.getElementById("task-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const payload = {
          title: document.getElementById("title").value,
          description: document.getElementById("description").value,
          status: document.getElementById("task-status").value,
          priority: Number(document.getElementById("priority").value),
        };
        await parseResponse(await fetch("/tasks", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify(payload),
        }));
        taskStatusLine.textContent = "Задача создана.";
        await loadTasks();
      } catch (error) {
        taskStatusLine.textContent = error.message;
      }
    });

    async function loadTasks() {
      if (!token) {
        taskStatusLine.textContent = "Нужно войти.";
        return;
      }
      const tasks = await parseResponse(await fetch("/tasks?limit=100", { headers: authHeaders() }));
      tasksNode.innerHTML = "";
      taskStatusLine.textContent = tasks.length ? `Задач: ${tasks.length}` : "Задач пока нет.";
      for (const task of tasks) {
        const node = document.createElement("article");
        node.className = "task";
        node.innerHTML = `
          <h3>${task.title}</h3>
          <div class="meta">id ${task.id} · ${task.status} · priority ${task.priority}</div>
          <p>${task.description || ""}</p>
          <div class="actions">
            <button class="secondary" data-action="done" data-id="${task.id}">done</button>
            <button class="danger" data-action="delete" data-id="${task.id}">Удалить</button>
          </div>
        `;
        tasksNode.appendChild(node);
      }
    }

    tasksNode.addEventListener("click", async (event) => {
      const button = event.target.closest("button");
      if (!button) return;
      try {
        const id = button.dataset.id;
        if (button.dataset.action === "delete") {
          await parseResponse(await fetch(`/tasks/${id}`, { method: "DELETE", headers: authHeaders() }));
        } else {
          await parseResponse(await fetch(`/tasks/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json", ...authHeaders() },
            body: JSON.stringify({ status: "done" }),
          }));
        }
        await loadTasks();
      } catch (error) {
        taskStatusLine.textContent = error.message;
      }
    });

    document.getElementById("refresh").addEventListener("click", loadTasks);
  </script>
</body>
</html>
"""


BASE_STYLE = """
  <style>
    :root {
      color-scheme: light;
      --ink: #1f2933;
      --muted: #66788a;
      --line: #d8e0e8;
      --paper: #f7fafc;
      --panel: #ffffff;
      --primary: #0f766e;
      --primary-dark: #115e59;
      --danger: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      color: var(--ink);
      min-height: 100vh;
      background: linear-gradient(135deg, #eef6f4 0%, #f8fafc 45%, #edf2f7 100%);
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding: 28px clamp(18px, 4vw, 56px) 18px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.74);
    }
    h1 { margin: 0; font-size: clamp(28px, 5vw, 44px); }
    h2 { margin: 0 0 14px; font-size: 22px; }
    p { margin: 0; color: var(--muted); }
    a { color: var(--primary-dark); font-weight: 700; text-decoration: none; }
    nav { display: flex; gap: 12px; flex-wrap: wrap; }
    main {
      display: grid;
      gap: 20px;
      padding: 24px clamp(18px, 4vw, 56px) 40px;
    }
    main.auth-layout {
      max-width: 520px;
      margin: 0 auto;
      width: 100%;
    }
    main.tasks-layout {
      grid-template-columns: minmax(280px, 360px) 1fr;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      box-shadow: 0 14px 34px rgba(31, 41, 51, 0.08);
    }
    form { display: grid; gap: 10px; margin-bottom: 16px; }
    label { display: grid; gap: 5px; color: var(--muted); font-size: 13px; }
    input, textarea, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px 11px;
      font: inherit;
      color: var(--ink);
      background: #fff;
    }
    textarea { min-height: 84px; resize: vertical; }
    button {
      border: 0;
      border-radius: 6px;
      padding: 10px 12px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      color: #fff;
      background: var(--primary);
    }
    button:hover { background: var(--primary-dark); }
    button.secondary { background: #415466; }
    button.danger { background: var(--danger); }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    .status {
      min-height: 22px;
      margin: 12px 0;
      color: var(--muted);
      font-size: 14px;
    }
    .task-list { display: grid; gap: 12px; }
    .task {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: var(--paper);
    }
    .task h3 { margin: 0 0 6px; font-size: 18px; }
    .meta { color: var(--muted); font-size: 13px; margin-bottom: 10px; }
    .filters {
      display: grid;
      grid-template-columns: repeat(4, minmax(120px, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }
    @media (max-width: 900px) {
      header { align-items: flex-start; flex-direction: column; }
      main.tasks-layout { grid-template-columns: 1fr; }
      .filters { grid-template-columns: 1fr; }
    }
  </style>
"""


REGISTER_HTML = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Регистрация · Task Manager</title>
""" + BASE_STYLE + """
</head>
<body>
  <header>
    <h1>Task Manager</h1>
    <nav>
      <a href="/login">Вход</a>
      <a href="/tasks-ui">Задачи</a>
    </nav>
  </header>
  <main class="auth-layout">
    <section>
      <h2>Регистрация</h2>
      <form id="register-form">
        <label>Логин <input id="login" value="demo_user" minlength="3" maxlength="50" required></label>
        <label>Пароль <input id="password" value="password123" type="password" minlength="6" required></label>
        <button type="submit">Создать пользователя</button>
      </form>
      <div id="status" class="status"></div>
      <p>Уже есть аккаунт? <a href="/login">Войти</a></p>
    </section>
  </main>
  <script>
    async function parseResponse(response) {
      const text = await response.text();
      const data = text ? JSON.parse(text) : null;
      if (!response.ok) throw new Error(data?.detail || response.statusText);
      return data;
    }

    document.getElementById("register-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const status = document.getElementById("status");
      try {
        await parseResponse(await fetch("/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            login: document.getElementById("login").value,
            password: document.getElementById("password").value,
          }),
        }));
        status.textContent = "Пользователь создан. Перенаправляю на вход.";
        setTimeout(() => window.location.href = "/login", 700);
      } catch (error) {
        status.textContent = error.message;
      }
    });
  </script>
</body>
</html>
"""


LOGIN_HTML = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Вход · Task Manager</title>
""" + BASE_STYLE + """
</head>
<body>
  <header>
    <h1>Task Manager</h1>
    <nav>
      <a href="/register">Регистрация</a>
      <a href="/tasks-ui">Задачи</a>
    </nav>
  </header>
  <main class="auth-layout">
    <section>
      <h2>Вход</h2>
      <form id="login-form">
        <label>Логин <input id="login" value="demo_user" minlength="3" maxlength="50" required></label>
        <label>Пароль <input id="password" value="password123" type="password" minlength="6" required></label>
        <button type="submit">Войти</button>
      </form>
      <div id="status" class="status"></div>
      <p>Нет аккаунта? <a href="/register">Зарегистрироваться</a></p>
    </section>
  </main>
  <script>
    async function parseResponse(response) {
      const text = await response.text();
      const data = text ? JSON.parse(text) : null;
      if (!response.ok) throw new Error(data?.detail || response.statusText);
      return data;
    }

    document.getElementById("login-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const status = document.getElementById("status");
      try {
        const params = new URLSearchParams({
          username: document.getElementById("login").value,
          password: document.getElementById("password").value,
        });
        const data = await parseResponse(await fetch("/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: params,
        }));
        localStorage.setItem("taskManagerToken", data.access_token);
        status.textContent = "Вход выполнен. Открываю задачи.";
        setTimeout(() => window.location.href = "/tasks-ui", 500);
      } catch (error) {
        status.textContent = error.message;
      }
    });
  </script>
</body>
</html>
"""


TASKS_HTML = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Задачи · Task Manager</title>
""" + BASE_STYLE + """
</head>
<body>
  <header>
    <h1>Task Manager</h1>
    <nav>
      <a href="/login">Вход</a>
      <a href="/register">Регистрация</a>
    </nav>
  </header>
  <main class="tasks-layout">
    <section>
      <h2>Новая задача</h2>
      <form id="task-form">
        <label>Название <input id="title" value="Docker demo task" maxlength="150" required></label>
        <label>Описание <textarea id="description" maxlength="500">Created from the containerized web UI</textarea></label>
        <label>Статус
          <select id="task-status">
            <option value="pending">pending</option>
            <option value="in_progress">in_progress</option>
            <option value="done">done</option>
          </select>
        </label>
        <label>Приоритет <input id="priority" type="number" min="1" max="5" value="2"></label>
        <button type="submit">Создать задачу</button>
      </form>
      <div id="task-status-line" class="status"></div>
      <div class="actions">
        <button type="button" id="logout" class="danger">Выйти</button>
      </div>
    </section>

    <section>
      <h2>Список задач</h2>
      <form id="filter-form" class="filters">
        <label>Поиск <input id="search" placeholder="title или description"></label>
        <label>Статус
          <select id="status-filter">
            <option value="">Все</option>
            <option value="pending">pending</option>
            <option value="in_progress">in_progress</option>
            <option value="done">done</option>
          </select>
        </label>
        <label>Сортировка
          <select id="sort-by">
            <option value="">created_at desc</option>
            <option value="created_at">created_at asc</option>
            <option value="title">title asc</option>
            <option value="status">status asc</option>
            <option value="priority">priority asc</option>
          </select>
        </label>
        <label>Лимит <input id="limit" type="number" min="1" max="100" value="100"></label>
      </form>
      <div class="actions">
        <button type="button" id="refresh" class="secondary">Обновить список</button>
        <button type="button" id="reset-filters" class="secondary">Сбросить фильтры</button>
      </div>
      <div id="list-status-line" class="status"></div>
      <div id="tasks" class="task-list"></div>
    </section>
  </main>
  <script>
    const token = localStorage.getItem("taskManagerToken") || "";
    const taskStatusLine = document.getElementById("task-status-line");
    const listStatusLine = document.getElementById("list-status-line");
    const tasksNode = document.getElementById("tasks");

    if (!token) window.location.href = "/login";

    function authHeaders() {
      return { Authorization: `Bearer ${token}` };
    }

    async function parseResponse(response) {
      const text = await response.text();
      const data = text ? JSON.parse(text) : null;
      if (!response.ok) throw new Error(data?.detail || response.statusText);
      return data;
    }

    document.getElementById("task-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const payload = {
          title: document.getElementById("title").value,
          description: document.getElementById("description").value,
          status: document.getElementById("task-status").value,
          priority: Number(document.getElementById("priority").value),
        };
        await parseResponse(await fetch("/tasks", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify(payload),
        }));
        taskStatusLine.textContent = "Задача создана.";
        await loadTasks();
      } catch (error) {
        taskStatusLine.textContent = error.message;
      }
    });

    function buildQuery() {
      const params = new URLSearchParams();
      const search = document.getElementById("search").value;
      const statusFilter = document.getElementById("status-filter").value;
      const sortBy = document.getElementById("sort-by").value;
      const limit = document.getElementById("limit").value || "100";
      params.set("limit", limit);
      if (search) params.set("search", search);
      if (statusFilter) params.set("status_filter", statusFilter);
      if (sortBy) params.set("sort_by", sortBy);
      return params.toString();
    }

    async function loadTasks() {
      if (!token) {
        listStatusLine.textContent = "Нужно войти.";
        return;
      }
      const tasks = await parseResponse(await fetch(`/tasks?${buildQuery()}`, { headers: authHeaders() }));
      tasksNode.innerHTML = "";
      listStatusLine.textContent = tasks.length ? `Задач: ${tasks.length}` : "Задач пока нет.";
      for (const task of tasks) {
        const node = document.createElement("article");
        node.className = "task";
        node.innerHTML = `
          <h3>${task.title}</h3>
          <div class="meta">id ${task.id} · ${task.status} · priority ${task.priority}</div>
          <p>${task.description || ""}</p>
          <div class="actions">
            <button class="secondary" data-action="done" data-id="${task.id}">done</button>
            <button class="danger" data-action="delete" data-id="${task.id}">Удалить</button>
          </div>
        `;
        tasksNode.appendChild(node);
      }
    }

    tasksNode.addEventListener("click", async (event) => {
      const button = event.target.closest("button");
      if (!button) return;
      try {
        const id = button.dataset.id;
        if (button.dataset.action === "delete") {
          await parseResponse(await fetch(`/tasks/${id}`, { method: "DELETE", headers: authHeaders() }));
        } else {
          await parseResponse(await fetch(`/tasks/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json", ...authHeaders() },
            body: JSON.stringify({ status: "done" }),
          }));
        }
        await loadTasks();
      } catch (error) {
        listStatusLine.textContent = error.message;
      }
    });

    document.getElementById("refresh").addEventListener("click", loadTasks);
    document.getElementById("filter-form").addEventListener("input", loadTasks);
    document.getElementById("reset-filters").addEventListener("click", () => {
      document.getElementById("search").value = "";
      document.getElementById("status-filter").value = "";
      document.getElementById("sort-by").value = "";
      document.getElementById("limit").value = "100";
      loadTasks();
    });
    document.getElementById("logout").addEventListener("click", () => {
      localStorage.removeItem("taskManagerToken");
      window.location.href = "/login";
    });
    loadTasks();
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(LOGIN_HTML)


@app.get("/register", response_class=HTMLResponse)
def register_page():
    return HTMLResponse(REGISTER_HTML)


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return HTMLResponse(LOGIN_HTML)


@app.get("/tasks-ui", response_class=HTMLResponse)
def tasks_page():
    return HTMLResponse(TASKS_HTML)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


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
