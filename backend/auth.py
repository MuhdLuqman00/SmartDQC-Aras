from __future__ import annotations
import os
import warnings as _warnings
from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt
from jose import ExpiredSignatureError, JWTError, jwt

_SECRET = os.environ.get("JWT_SECRET", "JWT_SECRET_PLACEHOLDER")
if not os.environ.get("JWT_SECRET"):
    _warnings.warn("JWT_SECRET not set — using insecure dev default", stacklevel=1)

_ALGORITHM = "HS256"
_DEFAULT_EXPIRY = timedelta(hours=8)

__all__ = [
    "hash_password", "verify_password",
    "create_access_token", "decode_access_token",
    "TokenExpiredError", "InvalidTokenError",
]


class TokenExpiredError(Exception):
    pass


class InvalidTokenError(Exception):
    pass


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    payload = dict(data)
    payload["exp"] = datetime.now(timezone.utc) + (expires_delta or _DEFAULT_EXPIRY)
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
    except ExpiredSignatureError:
        raise TokenExpiredError("Token has expired")
    except JWTError:
        raise InvalidTokenError("Token is invalid")
