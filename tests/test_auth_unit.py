import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

import auth
import models


def test_password_hashing_roundtrip():
    hashed_password = auth.get_password_hash("password123")

    assert hashed_password != "password123"
    assert auth.verify_password("password123", hashed_password) is True
    assert auth.verify_password("wrong-password", hashed_password) is False


def test_create_access_token_uses_default_expiry():
    before_issue = datetime.now(timezone.utc)
    token = auth.create_access_token({"sub": "42"})
    after_issue = datetime.now(timezone.utc)

    payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

    assert payload["sub"] == "42"
    assert before_issue + timedelta(minutes=14) <= expires_at <= after_issue + timedelta(minutes=16)


def test_create_access_token_honors_custom_expiry():
    before_issue = datetime.now(timezone.utc)
    token = auth.create_access_token({"sub": "7"}, expires_delta=timedelta(minutes=5))

    payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

    assert before_issue + timedelta(minutes=4) <= expires_at <= before_issue + timedelta(minutes=6)


def test_get_current_user_returns_user_for_valid_token(create_user, db_session):
    user = create_user(login="valid-user", password="password123")
    token = auth.create_access_token({"sub": str(user.id)})

    current_user = asyncio.run(auth.get_current_user(token=token, db=db_session))

    assert isinstance(current_user, models.User)
    assert current_user.id == user.id


def test_get_current_user_rejects_invalid_token(db_session):
    with pytest.raises(auth.HTTPException) as exc_info:
        asyncio.run(auth.get_current_user(token="not-a-jwt", db=db_session))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Не удалось проверить учётные данные"


def test_get_current_user_rejects_missing_subject(db_session):
    token = auth.create_access_token({"role": "tester"})

    with pytest.raises(auth.HTTPException) as exc_info:
        asyncio.run(auth.get_current_user(token=token, db=db_session))

    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_deleted_user(db_session):
    token = auth.create_access_token({"sub": "999"})

    with pytest.raises(auth.HTTPException) as exc_info:
        asyncio.run(auth.get_current_user(token=token, db=db_session))

    assert exc_info.value.status_code == 401
