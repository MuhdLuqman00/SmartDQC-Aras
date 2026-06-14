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


# Identity model (post d319dbf): /auth/me reflects the anonymous named-identity
# sent in the X-User header. There is no token validation — access is gated at
# the network perimeter — so /me never returns 401; everyone is treated as admin.
def test_me_reflects_x_user_identity(client):
    resp = client.get("/auth/me", headers={"X-User": "meuser"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "meuser"
    assert resp.json()["role"] == "admin"


def test_me_without_identity_is_anonymous(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["username"] == "anonymous"


def test_me_ignores_bearer_token(client):
    # The JWT path is dead under the anon-identity model; a bogus bearer token is
    # ignored rather than rejected. Identity comes only from X-User.
    resp = client.get("/auth/me", headers={"Authorization": "Bearer thisisnotavalidjwt"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "anonymous"


def test_logout_returns_ok(client):
    resp = client.post("/auth/logout")
    assert resp.status_code == 200
