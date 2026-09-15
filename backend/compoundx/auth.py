from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

_passwords = PasswordHasher()


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("password must be at least 12 characters")
    return _passwords.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        return _passwords.verify(encoded_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False
