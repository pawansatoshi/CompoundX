"""One-time access-code primitives.

Production persistence must store only a hash and consume redemption atomically
inside a database transaction with a UNIQUE constraint on the code hash.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_code(groups: int = 4, group_size: int = 4) -> str:
    raw = "".join(secrets.choice(ALPHABET) for _ in range(groups * group_size))
    return "-".join(raw[i:i + group_size] for i in range(0, len(raw), group_size))


def code_hash(code: str) -> str:
    normalized = code.strip().upper()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def expiry(hours: int = 24) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)
