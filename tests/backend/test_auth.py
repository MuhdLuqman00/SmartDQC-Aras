import pytest
from backend.auth import (
    hash_password, verify_password,
    create_access_token, decode_access_token,
    TokenExpiredError, InvalidTokenError,
)


def test_hash_and_verify_roundtrip():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed) is True


def test_wrong_password_rejected():
    hashed = hash_password("secret123")
    assert verify_password("wrong", hashed) is False


def test_token_roundtrip():
    token = create_access_token({"sub": "alice", "role": "admin"})
    payload = decode_access_token(token)
    assert payload["sub"] == "alice"
    assert payload["role"] == "admin"


def test_invalid_token_raises():
    with pytest.raises(InvalidTokenError):
        decode_access_token("not.a.token")


def test_expired_token_raises():
    from datetime import timedelta
    token = create_access_token({"sub": "bob"}, expires_delta=timedelta(seconds=-1))
    with pytest.raises(TokenExpiredError):
        decode_access_token(token)
