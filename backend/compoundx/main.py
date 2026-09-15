from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from .access_codes import code_hash, expiry, generate_code
from .audit import audit_event
from .auth import decrypt_totp_secret, encrypt_totp_secret, hash_password, issue_token, new_totp_secret, verify_password, verify_totp, decode_token
from .config import CONFIG
from .db import connection, is_configured

app = FastAPI(title="CompoundX API", version="0.2.0", docs_url="/api/docs", redoc_url=None)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    totp_code: str | None = Field(default=None, min_length=6, max_length=8)


class RedeemRequest(BaseModel):
    code: str = Field(min_length=10, max_length=32)
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)


class BootstrapRequest(BaseModel):
    bootstrap_secret: str = Field(min_length=16, max_length=256)


def require_database() -> None:
    if not is_configured():
        raise HTTPException(status_code=503, detail="Database is not configured")


def bearer_token(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        return decode_token(authorization[7:].strip())
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


def admin_only(authorization: str | None = Header(default=None)) -> dict:
    claims = bearer_token(authorization)
    if claims.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return claims


def rate_limit(key: str, limit: int = 10, window_seconds: int = 60) -> None:
    require_database()
    now = datetime.now(timezone.utc)
    with connection() as conn:
        row = conn.execute("SELECT window_started_at, request_count FROM rate_limits WHERE bucket_key=%s FOR UPDATE", (key,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO rate_limits(bucket_key, window_started_at, request_count) VALUES(%s,%s,1)", (key, now))
            return
        window_started, count = row
        if (now - window_started).total_seconds() >= window_seconds:
            conn.execute("UPDATE rate_limits SET window_started_at=%s, request_count=1 WHERE bucket_key=%s", (now, key))
            return
        if count >= limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        conn.execute("UPDATE rate_limits SET request_count=request_count+1 WHERE bucket_key=%s", (key,))


def write_audit(conn, action: str, actor: str, outcome: str, metadata: dict | None = None) -> None:
    event = audit_event(action, actor, outcome, metadata)
    conn.execute("INSERT INTO audit_events(event_hash, action, actor, outcome, metadata) VALUES(%s,%s,%s,%s,%s::jsonb)", (event["event_hash"], action, actor, outcome, json.dumps(event["metadata"])))


@app.get("/api/health")
def health():
    return {"status": "ok", "paper_trading": CONFIG.paper_trading, "live_execution_enabled": CONFIG.live_execution_enabled, "withdrawals_enabled": CONFIG.withdrawals_enabled, "database_configured": is_configured()}


@app.get("/api/risk/defaults")
def risk_defaults():
    return {"risk_per_trade": CONFIG.risk.risk_per_trade, "daily_loss_limit": CONFIG.risk.daily_loss_limit, "max_drawdown": CONFIG.risk.max_drawdown, "max_positions": CONFIG.risk.max_positions, "minimum_signal_score": CONFIG.strategy.minimum_signal_score}


@app.get("/api/mode")
def mode():
    return {"mode": "PAPER", "live_orders": False, "withdrawals": False}


@app.post("/api/auth/bootstrap")
def bootstrap(request: BootstrapRequest, http_request: Request):
    rate_limit(f"bootstrap:{http_request.client.host if http_request.client else 'unknown'}", 3, 300)
    require_database()
    expected = os.getenv("ADMIN_BOOTSTRAP_SECRET", "")
    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD", "")
    if not expected or request.bootstrap_secret != expected or not admin_email or len(password) < 12:
        raise HTTPException(status_code=403, detail="Bootstrap denied")
    with connection() as conn:
        if conn.execute("SELECT count(*) FROM users").fetchone()[0] != 0:
            raise HTTPException(status_code=409, detail="Bootstrap already completed")
        user_id = uuid.uuid4()
        conn.execute("INSERT INTO users(id,email,role,password_hash) VALUES(%s,%s,'admin',%s)", (user_id, admin_email, hash_password(password)))
        write_audit(conn, "admin_bootstrap", admin_email, "success")
    return {"ok": True, "message": "Admin created; remove bootstrap environment variables now"}


@app.post("/api/auth/login")
def login(request: LoginRequest, http_request: Request):
    rate_limit(f"login:{http_request.client.host if http_request.client else 'unknown'}:{request.email.lower()}", 8, 300)
    require_database()
    with connection() as conn:
        row = conn.execute("SELECT id,email,role,password_hash,totp_secret_encrypted,is_active FROM users WHERE lower(email)=lower(%s)", (request.email,)).fetchone()
        if not row or not row[5] or not verify_password(request.password, row[3]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if row[4] is not None and (not request.totp_code or not verify_totp(decrypt_totp_secret(row[4]), request.totp_code)):
            raise HTTPException(status_code=401, detail="TOTP required or invalid")
        token = issue_token(str(row[0]), row[2], row[1])
        write_audit(conn, "login", row[1], "success")
    return {"access_token": token, "token_type": "bearer", "role": row[2]}


@app.post("/api/access/redeem")
def redeem(request: RedeemRequest, http_request: Request):
    rate_limit(f"redeem:{http_request.client.host if http_request.client else 'unknown'}", 6, 300)
    require_database()
    with connection() as conn:
        row = conn.execute("SELECT id,expires_at,redeemed_at,revoked_at FROM access_codes WHERE code_hash=%s FOR UPDATE", (code_hash(request.code),)).fetchone()
        now = datetime.now(timezone.utc)
        if not row or row[2] is not None or row[3] is not None or row[1] <= now:
            raise HTTPException(status_code=400, detail="Invalid, expired, revoked or already-used code")
        if conn.execute("SELECT 1 FROM users WHERE lower(email)=lower(%s)", (request.email,)).fetchone():
            raise HTTPException(status_code=409, detail="Account already exists")
        user_id = uuid.uuid4()
        conn.execute("INSERT INTO users(id,email,role,password_hash) VALUES(%s,%s,'user',%s)", (user_id, request.email.lower(), hash_password(request.password)))
        conn.execute("UPDATE access_codes SET redeemed_at=%s, redeemed_by=%s WHERE id=%s AND redeemed_at IS NULL", (now, user_id, row[0]))
        write_audit(conn, "access_code_redeem", request.email.lower(), "success", {"code_id": str(row[0])})
        token = issue_token(str(user_id), "user", request.email.lower())
    return {"access_token": token, "token_type": "bearer", "role": "user"}


@app.post("/api/admin/access-codes")
def create_access_code(claims: dict = Depends(admin_only)):
    require_database()
    code = generate_code()
    with connection() as conn:
        conn.execute("INSERT INTO access_codes(id,code_hash,created_by,expires_at) VALUES(%s,%s,%s,%s)", (uuid.uuid4(), code_hash(code), uuid.UUID(claims["sub"]), expiry(24)))
        write_audit(conn, "access_code_create", claims.get("email", claims["sub"]), "success")
    return {"code": code, "expires_in_hours": 24, "single_use": True}


@app.post("/api/admin/totp/enroll")
def enroll_totp(claims: dict = Depends(admin_only)):
    require_database()
    secret = new_totp_secret()
    with connection() as conn:
        conn.execute("UPDATE users SET totp_secret_encrypted=%s WHERE id=%s", (encrypt_totp_secret(secret), uuid.UUID(claims["sub"])))
        write_audit(conn, "totp_enroll", claims.get("email", claims["sub"]), "success")
    return {"secret": secret, "issuer": "CompoundX", "account": claims.get("email")}
