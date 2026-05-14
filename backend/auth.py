from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone

from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

_SECRET = os.environ.get("JWT_SECRET", "JWT_SECRET_PLACEHOLDER")
_ALGORITHM = "HS256"
_DEFAULT_EXPIRY = timedelta(hours=8)

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenExpiredError(Exception):
    pass


class InvalidTokenError(Exception):
    pass


def hash_password(password: str) -> str:
    return _pwd_ctx.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: timedelta = _DEFAULT_EXPIRY) -> str:
    payload = dict(data)
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
    except ExpiredSignatureError:
        raise TokenExpiredError("Token has expired")
    except JWTError:
        raise InvalidTokenError("Token is invalid")
