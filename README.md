# Task Manager API

FastAPI-сервис для управления задачами с JWT-аутентификацией, покрытый автотестами и подготовленный для запуска в Docker вместе с MySQL.

## Что сделано

- Конфигурируемая база данных через `DATABASE_URL`
- Поддержка двух режимов:
  - `SQLite` для быстрых локальных запусков и автоматических тестов
  - `MySQL` для Docker-запуска приложения и базы в разных контейнерах
- Юнит- и функциональные тесты в папке `tests/`
- Нагрузочный сценарий `locustfile.py`
- Dockerfile для FastAPI-приложения
- Dockerfile для MySQL-контейнера
- Конфигурация `docker-compose.yml` для запуска приложения и MySQL
- Volume `mysql_data` для сохранения состояния базы данных
- HTML-отчёт покрытия в папке `htmlcov/` после генерации
- Подтверждённое покрытие приложения: `<90%` (`coverage run -m pytest tests`)

## Docker-запуск

В проекте есть два контейнера:

- `app` - FastAPI-приложение
- `db` - MySQL-база данных

Секреты не хранятся в `Dockerfile`. Для локального запуска используется `.env`, а в репозитории лежит только безопасный пример `.env.example`.

### 1. Подготовьте переменные окружения

```bash
cp .env.example .env
```

Для учебного запуска можно оставить демо-значения из `.env.example`. Если меняете MySQL-пароль после первого запуска, создайте новый volume командой `docker compose down -v`, иначе MySQL продолжит хранить старого пользователя.

### 2. Соберите и запустите контейнеры

```bash
docker compose up --build
```

Приложение будет доступно по адресу:

```text
http://localhost:8000
```

Основные страницы интерфейса:

- `http://localhost:8000/login` - вход
- `http://localhost:8000/register` - регистрация
- `http://localhost:8000/tasks-ui` - задачи, фильтры и сортировки

Swagger UI:

```text
http://localhost:8000/docs
```

### 3. Проверка CRUD

Через веб-интерфейс `http://localhost:8000` можно:

- зарегистрировать пользователя
- войти
- создать задачу
- посмотреть список задач
- отсортировать и отфильтровать список задач
- обновить статус задачи
- удалить задачу

### 4. Проверка volume

1. Запустите проект через `docker compose up --build`.
2. Создайте пользователя и задачу.
3. Остановите контейнеры:

```bash
docker compose down
```

4. Запустите контейнеры снова:

```bash
docker compose up
```

5. Войдите тем же пользователем и проверьте, что задача сохранилась.

Данные сохраняются в Docker volume `mysql_data`. Если выполнить `docker compose down -v`, volume будет удалён вместе с данными.

### Если MySQL пишет `Access denied`

MySQL применяет `MYSQL_USER` и `MYSQL_PASSWORD` только при первом создании volume. Если после первого запуска поменять пароль в `.env`, старый volume продолжит хранить пользователя со старым паролем.

Для чистого перезапуска с новыми значениями:

```bash
docker compose down -v
docker compose up --build
```

Если данные нужно сохранить, верните в `.env` тот пароль, с которым база была создана изначально.

Подробное объяснение Docker и устройства контейнеризации в этом проекте: [DOCKER_EXPLANATION.md](DOCKER_EXPLANATION.md).

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

### 3. Docker-запуск с MySQL

```bash
cp .env.example #or .env
docker compose up --build
```

В этом режиме MySQL не публикуется на хост-машину. Приложение обращается к базе внутри Docker-сети по адресу `db:3306`.

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

1. Поднимите приложение и MySQL:

```bash
docker compose up --build
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
- `Dockerfile` - образ FastAPI-приложения
- `docker/mysql/Dockerfile` - образ MySQL-контейнера
- `docker-compose.yml` - запуск приложения и MySQL
- `DOCKER_EXPLANATION.md` - подробное объяснение Docker и контейнеризации проекта

## Краткая заметка по кэшу

Кэширование подключено к `GET /tasks` через `lru_cache`. После `POST /tasks`, `PUT /tasks/{task_id}` и `DELETE /tasks/{task_id}` кэш очищается, чтобы пользователь не видел устаревший список задач.
