def test_register_user_success(client):
    response = client.post(
        "/auth/register",
        json={"login": "new-user", "password": "password123"},
    )

    assert response.status_code == 201
    assert response.json() == {"id": 1, "login": "new-user"}


def test_register_user_rejects_duplicate_login(client):
    payload = {"login": "duplicate-user", "password": "password123"}

    first_response = client.post("/auth/register", json=payload)
    second_response = client.post("/auth/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 400
    assert second_response.json()["detail"] == "Пользователь с таким логином уже существует"


def test_register_user_validates_payload(client):
    response = client.post(
        "/auth/register",
        json={"login": "ab", "password": "123"},
    )

    assert response.status_code == 422


def test_login_returns_bearer_token(client, register_user):
    register_user(login="login-user", password="password123")

    response = client.post(
        "/auth/login",
        data={"username": "login-user", "password": "password123"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert body["access_token"]


def test_login_rejects_wrong_password(client, register_user):
    register_user(login="login-user", password="password123")

    response = client.post(
        "/auth/login",
        data={"username": "login-user", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Неверный логин или пароль"
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_rejects_unknown_user(client):
    response = client.post(
        "/auth/login",
        data={"username": "missing-user", "password": "password123"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Неверный логин или пароль"
