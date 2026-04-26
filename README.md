# Task Manager API

FastAPI-сервис для управления задачами с JWT-аутентификацией, покрытый автотестами и подготовленный для нагрузочного тестирования через PostgreSQL.

## Что сделано

- Конфигурируемая база данных через `DATABASE_URL`
- Поддержка двух режимов:
  - `SQLite` для быстрых локальных запусков и автоматических тестов
  - `PostgreSQL` для реалистичного запуска приложения и нагрузочного тестирования
- Юнит- и функциональные тесты в папке `tests/`
- Нагрузочный сценарий `locustfile.py`
- Конфигурация `docker-compose.yml` для PostgreSQL
- HTML-отчёт покрытия в папке `htmlcov/` после генерации
- Подтверждённое покрытие приложения: `100%` (`coverage run -m pytest tests`)

## Запуск приложения

### 1. Установка зависимостей

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### 2. Быстрый локальный запуск на SQLite

```bash
unset DATABASE_URL
uvicorn main:app --reload
```

По умолчанию будет использоваться `sqlite:///./task_manager.db`.

### 3. Запуск с PostgreSQL через Docker Compose

```bash
docker compose up -d postgres
export DATABASE_URL=postgresql+psycopg://task_manager:task_manager@localhost:5432/task_manager
uvicorn main:app --reload
```

## Запуск тестов

```bash
pytest tests
```

## Проверка покрытия

```bash
coverage run -m pytest tests
coverage report -m
coverage html
```

После генерации откройте `htmlcov/index.html`. Этот каталог должен лежать в репозитории как артефакт для проверяющего.

## Нагрузочное тестирование

### Подготовка

1. Поднимите PostgreSQL:

```bash
docker compose up -d postgres
```

2. Установите переменную окружения:

```bash
export DATABASE_URL=postgresql+psycopg://task_manager:task_manager@localhost:5432/task_manager
```

3. Запустите приложение:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Запуск Locust

Интерактивный режим:

```bash
locust -f locustfile.py --host http://127.0.0.1:8000
```

Headless-режим:

```bash
locust -f locustfile.py --host http://127.0.0.1:8000 --headless -u 20 -r 5 -t 2m
```

Для разделения сценариев можно использовать теги:

```bash
locust -f locustfile.py --host http://127.0.0.1:8000 --headless -u 20 -r 5 -t 2m --tags read-heavy mixed
```

## Структура проекта

- `main.py` - FastAPI-приложение и бизнес-логика API
- `database.py` - инициализация БД и сессий
- `auth.py` - JWT и проверка пользователя
- `tests/` - автотесты
- `locustfile.py` - нагрузочный сценарий
- `load_test_report.md` - описание сценария и результатов/наблюдений
- `docker-compose.yml` - локальный PostgreSQL для нагрузочного тестирования

## Краткая заметка по кэшу

Кэширование подключено к `GET /tasks` через `lru_cache`. После `POST /tasks`, `PUT /tasks/{task_id}` и `DELETE /tasks/{task_id}` кэш очищается, чтобы пользователь не видел устаревший список задач.
