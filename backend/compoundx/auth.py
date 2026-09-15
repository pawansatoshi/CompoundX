"""Production authentication helpers: Argon2id, JWT and TOTP."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from cryptography.fernet import Fernet

PASSWORD_HASHER = PasswordHasher()
ALGORITHM = "HS256"


def _jwt_secret() -> str:
    value = os.getenv("JWT_SECRET", "").strip()
    if len(value) < 32:
        raise RuntimeError("JWT_SECRET must be at least 32 characters")
    return value


def _fernet() -> Fernet:
    value = os.getenv("TOTP_ENCRYPTION_KEY", "").strip()
    if not value:
        raise RuntimeError("TOTP_ENCRYPTION_KEY is not configured")
    return Fernet(value.encode())


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("password must be at least 12 characters")
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(encoded_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False


def encrypt_totp_secret(secret: str) -> bytes:
    return _fernet().encrypt(secret.encode("utf-8"))


def decrypt_totp_secret(value: bytes) -> str:
    return _fernet().decrypt(value).decode("utf-8")


def new_totp_secret() -> str:
    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def issue_token(user_id: str, role: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "email": email,
        "iat": now,
        "exp": now + timedelta(hours=8),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, _jwt_secret(), algorithms=[ALGORITHM])
