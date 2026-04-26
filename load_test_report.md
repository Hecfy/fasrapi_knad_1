# Load Test Report

## Goal

Проверить поведение `Task Manager API` под нагрузкой на `PostgreSQL`, а не на `SQLite`, потому что:

- SQLite плохо подходит для конкурентной записи и realistic load profile
- PostgreSQL ближе к ожидаемому production-сценарию
- кэширование `GET /tasks` имеет смысл оценивать на серверной БД, а не на файловой

## Environment

- Application: FastAPI `Task Manager API`
- Load tool: `Locust`
- Database target: `PostgreSQL 16`
- Docker bootstrap: `docker-compose.yml`
- Scenario file: `locustfile.py`

## Workload

Пользователь Locust делает следующее:

1. Регистрируется и логинится
2. Создаёт несколько стартовых задач
3. Выполняет read-heavy запросы:
   - `GET /tasks`
   - `GET /tasks` с фильтрацией и сортировкой
4. Периодически создаёт новые задачи, чтобы нагрузка была смешанной, а не только read-only

## Suggested Run Commands

```bash
docker compose up -d postgres
export DATABASE_URL=postgresql+psycopg://task_manager:task_manager@localhost:5432/task_manager
uvicorn main:app --host 0.0.0.0 --port 8000
locust -f locustfile.py --host http://127.0.0.1:8000 --headless -u 20 -r 5 -t 2m
```

Для отдельного акцента на чтении:

```bash
locust -f locustfile.py --host http://127.0.0.1:8000 --headless -u 20 -r 5 -t 2m --tags read-heavy
```

## Metrics to Record

- Requests per second
- Median response time
- 95th percentile response time
- Error rate
- Разница между холодным и прогретым кэшем для `GET /tasks`

## Result Notes

В текущем контейнере разработки Docker и локальный PostgreSQL не установлены, поэтому здесь подготовлены:

- воспроизводимая Postgres-конфигурация
- готовый Locust-сценарий
- команды запуска для реального прогона

Если среда запуска поддерживает Docker, отчёт нужно дополнить фактическими метриками после headless-прогона.
