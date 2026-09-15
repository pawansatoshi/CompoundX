"""Small PostgreSQL access layer used by the API.

The API fails closed when DATABASE_URL is missing. No local file database is used
because Vercel function filesystems are ephemeral and unsuitable for auth state.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg


def database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("DATABASE_URL is not configured")
    return value


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(database_url())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def is_configured() -> bool:
    return bool(os.getenv("DATABASE_URL", "").strip())
