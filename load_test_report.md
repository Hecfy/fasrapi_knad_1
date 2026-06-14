# Load Test Report

## Goal

Проверить поведение `Task Manager API` под нагрузкой на `MySQL`, поднятой в отдельном Docker-контейнере, а не на `SQLite`, потому что:

- SQLite плохо подходит для конкурентной записи и realistic load profile
- MySQL работает как отдельный сервер БД и соответствует Docker-заданию
- кэширование `GET /tasks` имеет смысл оценивать на серверной БД, а не на файловой

## Environment

- Application: FastAPI `Task Manager API`
- Load tool: `Locust`
- Database target: `MySQL 8.4`
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
cp .env.example .env
docker compose up --build
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

В текущем контейнере разработки Docker не установлен, поэтому здесь подготовлены:

- воспроизводимая Docker Compose-конфигурация с MySQL
- готовый Locust-сценарий
- команды запуска для реального прогона

Если среда запуска поддерживает Docker, отчёт нужно дополнить фактическими метриками после headless-прогона.
