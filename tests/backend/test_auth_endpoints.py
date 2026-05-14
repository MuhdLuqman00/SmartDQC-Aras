import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.db.models import User
from backend.auth import hash_password


@pytest.fixture
def client(override_get_db):
    return TestClient(app)


def test_login_valid_credentials(client, db_session):
    db_session.add(User(
        username="testuser",
        password_hash=hash_password("testpass"),
        role="analyst",
        is_active=True,
    ))
    db_session.commit()
    resp = client.post(
        "/auth/login",
        data={"username": "testuser", "password": "testpass"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["role"] == "analyst"


def test_login_wrong_password(client, db_session):
    db_session.add(User(
        username="testuser2",
        password_hash=hash_password("correct"),
        role="viewer",
        is_active=True,
    ))
    db_session.commit()
    resp = client.post(
        "/auth/login",
        data={"username": "testuser2", "password": "wrong"},
    )
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post(
        "/auth/login",
        data={"username": "nobody", "password": "x"},
    )
    assert resp.status_code == 401


def test_me_with_valid_token(client, db_session):
    db_session.add(User(
        username="meuser",
        password_hash=hash_password("mepass"),
        role="admin",
        is_active=True,
    ))
    db_session.commit()
    login = client.post("/auth/login", data={"username": "meuser", "password": "mepass"})
    token = login.json()["access_token"]
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "meuser"
    assert resp.json()["role"] == "admin"


def test_me_without_token(client):
    resp = client.get("/auth/me", headers={"Authorization": "invalid"})
    assert resp.status_code == 401


def test_me_with_invalid_bearer_token(client):
    resp = client.get("/auth/me", headers={"Authorization": "Bearer thisisnotavalidjwt"})
    assert resp.status_code == 401


def test_logout_returns_ok(client):
    resp = client.post("/auth/logout")
    assert resp.status_code == 200
