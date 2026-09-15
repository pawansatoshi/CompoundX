from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from compoundx.access_codes import code_hash, expiry, generate_code
from compoundx.audit import audit_event
from compoundx.auth import (
    decode_token,
    decrypt_totp_secret,
    encrypt_totp_secret,
    hash_password,
    issue_token,
    new_totp_secret,
    verify_password,
    verify_totp,
)
from compoundx.config import CONFIG
from compoundx.db import connection, is_configured


def read_json(handler, max_bytes: int = 16_384) -> dict[str, Any]:
    raw_len = int(handler.headers.get("Content-Length", "0"))
    if raw_len <= 0 or raw_len > max_bytes:
        raise ValueError("Invalid request body")
    raw = handler.rfile.read(raw_len)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON object required")
    return data


def send_json(handler, payload: dict[str, Any], status_code: int = 200) -> None:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def client_key(handler) -> str:
    return getattr(getattr(handler, "client_address", None), "__getitem__", lambda _: "unknown")(0) or "unknown"


def rate_limit(key: str, limit: int = 10, window_seconds: int = 60) -> None:
    if not is_configured():
        raise RuntimeError("Database is not configured")
    now = datetime.now(timezone.utc)
    with connection() as conn:
        row = conn.execute(
            "SELECT window_started_at, request_count FROM rate_limits WHERE bucket_key=%s FOR UPDATE",
            (key,),
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO rate_limits(bucket_key, window_started_at, request_count) VALUES(%s,%s,1)",
                (key, now),
            )
            return
        window_started, count = row
        if (now - window_started).total_seconds() >= window_seconds:
            conn.execute(
                "UPDATE rate_limits SET window_started_at=%s, request_count=1 WHERE bucket_key=%s",
                (now, key),
            )
            return
        if count >= limit:
            raise PermissionError("Rate limit exceeded")
        conn.execute(
            "UPDATE rate_limits SET request_count=request_count+1 WHERE bucket_key=%s",
            (key,),
        )


def write_audit(conn, action: str, actor: str, outcome: str, metadata: dict | None = None) -> None:
    event = audit_event(action, actor, outcome, metadata)
    conn.execute(
        "INSERT INTO audit_events(event_hash, action, actor, outcome, metadata) VALUES(%s,%s,%s,%s,%s::jsonb)",
        (event["event_hash"], action, actor, outcome, json.dumps(event["metadata"])),
    )


def require_db() -> None:
    if not is_configured():
        raise RuntimeError("Database is not configured")


def bearer_claims(handler) -> dict:
    value = handler.headers.get("Authorization", "")
    if not value.startswith("Bearer "):
        raise PermissionError("Authentication required")
    try:
        claims = decode_token(value[7:].strip())
    except Exception as exc:
        raise PermissionError("Invalid or expired token") from exc
    if claims.get("role") != "admin":
        raise PermissionError("Admin role required")
    return claims


def bootstrap(data: dict, handler) -> tuple[dict, int]:
    rate_limit(f"bootstrap:{client_key(handler)}", 3, 300)
    require_db()
    expected = os.getenv("ADMIN_BOOTSTRAP_SECRET", "")
    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD", "")
    if not expected or data.get("bootstrap_secret") != expected or not admin_email or len(password) < 12:
        return {"detail": "Bootstrap denied"}, 403
    with connection() as conn:
        if conn.execute("SELECT count(*) FROM users").fetchone()[0] != 0:
            return {"detail": "Bootstrap already completed"}, 409
        user_id = uuid.uuid4()
        conn.execute(
            "INSERT INTO users(id,email,role,password_hash) VALUES(%s,%s,'admin',%s)",
            (user_id, admin_email, hash_password(password)),
        )
        write_audit(conn, "admin_bootstrap", admin_email, "success")
    return {"ok": True, "message": "Admin created; remove bootstrap environment variables now"}, 200


def login(data: dict, handler) -> tuple[dict, int]:
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    totp_code = data.get("totp_code")
    if len(password) < 12 or not email:
        return {"detail": "Invalid credentials"}, 401
    rate_limit(f"login:{client_key(handler)}:{email}", 8, 300)
    require_db()
    with connection() as conn:
        row = conn.execute(
            "SELECT id,email,role,password_hash,totp_secret_encrypted,is_active FROM users WHERE lower(email)=lower(%s)",
            (email,),
        ).fetchone()
        if not row or not row[5] or not verify_password(password, row[3]):
            return {"detail": "Invalid credentials"}, 401
        if row[4] is not None and (not totp_code or not verify_totp(decrypt_totp_secret(row[4]), str(totp_code))):
            return {"detail": "TOTP required or invalid"}, 401
        token = issue_token(str(row[0]), row[2], row[1])
        write_audit(conn, "login", row[1], "success")
    return {"access_token": token, "token_type": "bearer", "role": row[2]}, 200


def redeem(data: dict, handler) -> tuple[dict, int]:
    code = str(data.get("code", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    if len(code) < 10 or len(password) < 12 or not email:
        return {"detail": "Invalid request"}, 400
    rate_limit(f"redeem:{client_key(handler)}", 6, 300)
    require_db()
    with connection() as conn:
        row = conn.execute(
            "SELECT id,expires_at,redeemed_at,revoked_at FROM access_codes WHERE code_hash=%s FOR UPDATE",
            (code_hash(code),),
        ).fetchone()
        now = datetime.now(timezone.utc)
        if not row or row[2] is not None or row[3] is not None or row[1] <= now:
            return {"detail": "Invalid, expired, revoked or already-used code"}, 400
        if conn.execute("SELECT 1 FROM users WHERE lower(email)=lower(%s)", (email,)).fetchone():
            return {"detail": "Account already exists"}, 409
        user_id = uuid.uuid4()
        conn.execute(
            "INSERT INTO users(id,email,role,password_hash) VALUES(%s,%s,'user',%s)",
            (user_id, email, hash_password(password)),
        )
        conn.execute(
            "UPDATE access_codes SET redeemed_at=%s, redeemed_by=%s WHERE id=%s AND redeemed_at IS NULL",
            (now, user_id, row[0]),
        )
        write_audit(conn, "access_code_redeem", email, "success", {"code_id": str(row[0])})
        token = issue_token(str(user_id), "user", email)
    return {"access_token": token, "token_type": "bearer", "role": "user"}, 200


def create_access_code(handler) -> tuple[dict, int]:
    claims = bearer_claims(handler)
    require_db()
    code = generate_code()
    with connection() as conn:
        conn.execute(
            "INSERT INTO access_codes(id,code_hash,created_by,expires_at) VALUES(%s,%s,%s,%s)",
            (uuid.uuid4(), code_hash(code), uuid.UUID(claims["sub"]), expiry(24)),
        )
        write_audit(conn, "access_code_create", claims.get("email", claims["sub"]), "success")
    return {"code": code, "expires_in_hours": 24, "single_use": True}, 200


def enroll_totp(handler) -> tuple[dict, int]:
    claims = bearer_claims(handler)
    require_db()
    secret = new_totp_secret()
    with connection() as conn:
        conn.execute(
            "UPDATE users SET totp_secret_encrypted=%s WHERE id=%s",
            (encrypt_totp_secret(secret), uuid.UUID(claims["sub"])),
        )
        write_audit(conn, "totp_enroll", claims.get("email", claims["sub"]), "success")
    return {"secret": secret, "issuer": "CompoundX", "account": claims.get("email")}, 200
