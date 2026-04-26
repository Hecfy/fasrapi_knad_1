from datetime import datetime, timedelta, timezone

import main


def test_create_task_requires_authentication(client):
    response = client.post(
        "/tasks",
        json={"title": "Task", "description": "Desc", "status": "pending", "priority": 1},
    )

    assert response.status_code == 401


def test_create_task_successfully(client, auth_headers):
    response = client.post(
        "/tasks",
        json={"title": "Write tests", "description": "Cover CRUD", "status": "in_progress", "priority": 3},
        headers=auth_headers(),
    )

    body = response.json()
    assert response.status_code == 201
    assert body["title"] == "Write tests"
    assert body["description"] == "Cover CRUD"
    assert body["status"] == "in_progress"
    assert body["priority"] == 3
    assert body["owner_id"] == 1


def test_create_task_validates_payload(client, auth_headers):
    response = client.post(
        "/tasks",
        json={"title": "", "description": "Desc", "status": "pending", "priority": 9},
        headers=auth_headers(),
    )

    assert response.status_code == 422


def test_get_tasks_returns_default_descending_order(client, auth_headers):
    headers = auth_headers()
    older_task = client.post(
        "/tasks",
        json={"title": "Older", "description": "First", "status": "pending", "priority": 1},
        headers=headers,
    )
    newer_task = client.post(
        "/tasks",
        json={"title": "Newer", "description": "Second", "status": "done", "priority": 2},
        headers=headers,
    )

    response = client.get("/tasks", headers=headers)

    assert older_task.status_code == 201
    assert newer_task.status_code == 201
    assert response.status_code == 200
    assert [task["title"] for task in response.json()] == ["Newer", "Older"]


def test_get_tasks_filters_searches_sorts_and_paginates(client, auth_headers, create_user, create_task):
    user = create_user(login="tasks-user", password="password123")
    headers = auth_headers(login="tasks-user", password="password123")
    create_task(
        owner=user,
        title="Bravo",
        description="Handle docs",
        status="pending",
        priority=3,
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    create_task(
        owner=user,
        title="Alpha",
        description="Important release",
        status="done",
        priority=1,
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    create_task(
        owner=user,
        title="Charlie",
        description="Important review",
        status="done",
        priority=2,
        created_at=datetime.now(timezone.utc),
    )
    main.clear_task_cache()

    filtered_response = client.get(
        "/tasks",
        params={"search": "Important", "status_filter": "done", "sort_by": "title"},
        headers=headers,
    )
    paginated_response = client.get(
        "/tasks",
        params={"skip": 1, "limit": 1, "sort_by": "title"},
        headers=headers,
    )

    assert filtered_response.status_code == 200
    assert [task["title"] for task in filtered_response.json()] == ["Alpha", "Charlie"]
    assert paginated_response.status_code == 200
    assert [task["title"] for task in paginated_response.json()] == ["Bravo"]


def test_get_tasks_isolated_by_owner(client, auth_headers, create_user, create_task):
    first_user = create_user(login="owner-one", password="password123")
    second_user = create_user(login="owner-two", password="password123")
    create_task(owner=first_user, title="Visible task")
    create_task(owner=second_user, title="Hidden task")
    main.clear_task_cache()

    response = client.get("/tasks", headers=auth_headers(login="owner-one", password="password123"))

    assert response.status_code == 200
    assert [task["title"] for task in response.json()] == ["Visible task"]


def test_get_tasks_validates_query_parameters(client, auth_headers):
    headers = auth_headers()

    invalid_limit_response = client.get("/tasks", params={"limit": 0}, headers=headers)
    invalid_sort_response = client.get("/tasks", params={"sort_by": "unknown"}, headers=headers)

    assert invalid_limit_response.status_code == 422
    assert invalid_sort_response.status_code == 422


def test_create_task_clears_cached_list(client, auth_headers):
    headers = auth_headers()
    initial_response = client.get("/tasks", headers=headers)
    create_response = client.post(
        "/tasks",
        json={"title": "Fresh task", "description": "Updated list", "status": "pending", "priority": 1},
        headers=headers,
    )
    refreshed_response = client.get("/tasks", headers=headers)

    assert initial_response.status_code == 200
    assert initial_response.json() == []
    assert create_response.status_code == 201
    assert [task["title"] for task in refreshed_response.json()] == ["Fresh task"]


def test_update_task_updates_selected_fields(client, auth_headers, create_user, create_task):
    user = create_user(login="editor", password="password123")
    task = create_task(owner=user, title="Old title", status="pending", priority=1)
    headers = auth_headers(login="editor", password="password123")
    client.get("/tasks", headers=headers)

    response = client.put(
        f"/tasks/{task.id}",
        json={"status": "done", "priority": 5},
        headers=headers,
    )
    refreshed_list = client.get("/tasks", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "done"
    assert response.json()["priority"] == 5
    assert refreshed_list.json()[0]["status"] == "done"


def test_update_task_returns_404_for_missing_or_foreign_task(client, auth_headers, create_user, create_task):
    owner = create_user(login="task-owner", password="password123")
    other_user = create_user(login="task-outsider", password="password123")
    foreign_task = create_task(owner=other_user, title="Foreign task")
    headers = auth_headers(login="task-owner", password="password123")

    missing_response = client.put(f"/tasks/9999", json={"status": "done"}, headers=headers)
    foreign_response = client.put(
        f"/tasks/{foreign_task.id}",
        json={"status": "done"},
        headers=headers,
    )

    assert owner.id != other_user.id
    assert missing_response.status_code == 404
    assert foreign_response.status_code == 404


def test_update_task_validates_payload(client, auth_headers, create_user, create_task):
    user = create_user(login="validator", password="password123")
    task = create_task(owner=user)

    response = client.put(
        f"/tasks/{task.id}",
        json={"priority": 8},
        headers=auth_headers(login="validator", password="password123"),
    )

    assert response.status_code == 422


def test_delete_task_removes_task_and_clears_cache(client, auth_headers, create_user, create_task):
    user = create_user(login="deleter", password="password123")
    task = create_task(owner=user, title="Delete me")
    headers = auth_headers(login="deleter", password="password123")
    client.get("/tasks", headers=headers)

    delete_response = client.delete(f"/tasks/{task.id}", headers=headers)
    list_response = client.get("/tasks", headers=headers)

    assert delete_response.status_code == 204
    assert delete_response.text == ""
    assert list_response.json() == []


def test_delete_task_returns_404_for_missing_or_foreign_task(client, auth_headers, create_user, create_task):
    owner = create_user(login="delete-owner", password="password123")
    other_user = create_user(login="delete-outsider", password="password123")
    foreign_task = create_task(owner=other_user, title="Foreign task")
    headers = auth_headers(login="delete-owner", password="password123")

    missing_response = client.delete("/tasks/9999", headers=headers)
    foreign_response = client.delete(f"/tasks/{foreign_task.id}", headers=headers)

    assert owner.id != other_user.id
    assert missing_response.status_code == 404
    assert foreign_response.status_code == 404
