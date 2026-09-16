import os
import sys
import uuid
from http.server import BaseHTTPRequestHandler
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from compoundx.auth import _fernet
from compoundx.db import connection, is_configured
from compoundx.exchange import ExchangeGateway, SUPPORTED_EXCHANGES, exchange_catalog
from compoundx.vercel_http import bearer_claims, read_json, send_json


def _enc(value: str) -> bytes:
    return _fernet().encrypt(value.encode("utf-8"))


def _dec(value: bytes) -> str:
    return _fernet().decrypt(value).decode("utf-8")


def _credentials(user_id: str, exchange_id: str, mode: str) -> dict[str, str]:
    if not is_configured():
        raise RuntimeError("Database is not configured")
    with connection() as conn:
        row = conn.execute(
            "SELECT api_key_encrypted,secret_encrypted,passphrase_encrypted FROM exchange_connections WHERE user_id=%s AND exchange_id=%s AND mode=%s AND enabled=TRUE",
            (uuid.UUID(user_id), exchange_id, mode),
        ).fetchone()
    if not row:
        raise ValueError("exchange connection is not configured")
    return {"api_key": _dec(row[0]), "secret": _dec(row[1]), "password": _dec(row[2]) if row[2] else ""}


def _save(user_id: str, body: dict) -> dict:
    exchange_id = str(body.get("exchange", "")).strip().lower()
    mode = str(body.get("mode", "DEMO")).strip().upper()
    api_key = str(body.get("api_key", "")).strip()
    secret = str(body.get("secret", "")).strip()
    passphrase = str(body.get("passphrase", "")).strip()
    label = str(body.get("label", "")).strip()[:80]
    if exchange_id not in SUPPORTED_EXCHANGES:
        raise ValueError("unsupported exchange")
    if mode not in {"DEMO", "LIVE"}:
        raise ValueError("mode must be DEMO or LIVE")
    if not api_key or not secret:
        raise ValueError("api_key and secret are required")
    if mode == "LIVE" and os.getenv("LIVE_TRADING_ENABLED", "false").lower() != "true":
        raise PermissionError("live trading is not enabled on this deployment")
    if not is_configured():
        raise RuntimeError("Database is not configured")
    with connection() as conn:
        conn.execute(
            """INSERT INTO exchange_connections(id,user_id,exchange_id,mode,api_key_encrypted,secret_encrypted,passphrase_encrypted,label,enabled)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
               ON CONFLICT(user_id,exchange_id,mode) DO UPDATE SET api_key_encrypted=EXCLUDED.api_key_encrypted,secret_encrypted=EXCLUDED.secret_encrypted,passphrase_encrypted=EXCLUDED.passphrase_encrypted,label=EXCLUDED.label,enabled=TRUE,updated_at=now()""",
            (uuid.uuid4(), uuid.UUID(user_id), exchange_id, mode, _enc(api_key), _enc(secret), _enc(passphrase) if passphrase else None, label),
        )
    return {"ok": True, "exchange": exchange_id, "mode": mode, "configured": True}


def _test(user_id: str, exchange_id: str, mode: str) -> dict:
    credentials = _credentials(user_id, exchange_id, mode)
    gateway = ExchangeGateway(exchange_id=exchange_id, sandbox=(mode == "DEMO"), credentials=credentials)
    balance = gateway.balance()
    total = balance.get("total") or {}
    nonzero = {k: v for k, v in total.items() if isinstance(v, (int, float)) and v > 0}
    return {"ok": True, "exchange": exchange_id, "mode": mode, "connected": True, "assets": list(nonzero.keys())[:25]}


def _order(user_id: str, body: dict) -> dict:
    exchange_id = str(body.get("exchange", "")).strip().lower()
    mode = str(body.get("mode", "DEMO")).strip().upper()
    symbol = str(body.get("symbol", "")).strip()
    side = str(body.get("side", "")).strip().lower()
    order_type = str(body.get("order_type", "market")).strip().lower()
    amount = float(body.get("amount", 0) or 0)
    price = body.get("price")
    price = float(price) if price is not None else None
    if mode == "LIVE":
        if os.getenv("LIVE_TRADING_ENABLED", "false").lower() != "true":
            raise PermissionError("live trading is disabled")
        if body.get("confirm_live") is not True:
            raise PermissionError("confirm_live=true is required for a live order")
    credentials = _credentials(user_id, exchange_id, mode)
    gateway = ExchangeGateway(exchange_id=exchange_id, sandbox=(mode == "DEMO"), credentials=credentials)
    if mode == "DEMO":
        ticker = gateway.ticker(symbol)
        fill = float(ticker.get("last") or ticker.get("close") or 0)
        if fill <= 0:
            raise RuntimeError("demo market price unavailable")
        return {"ok": True, "mode": "DEMO", "simulated": True, "symbol": symbol, "side": side, "amount": amount, "price": fill, "order_id": "demo-" + uuid.uuid4().hex[:16]}
    order = gateway.create_order(symbol, side, amount, order_type, price)
    return {"ok": True, "mode": "LIVE", "simulated": False, "order": order}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            claims = bearer_claims(self)
            send_json(self, {"exchanges": exchange_catalog(), "live_enabled": os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true", "user": claims.get("email")})
        except PermissionError as exc:
            send_json(self, {"detail": str(exc)}, 401)
        except Exception as exc:
            send_json(self, {"detail": str(exc)}, 500)

    def do_POST(self):
        try:
            claims = bearer_claims(self)
            body = read_json(self)
            action = str(body.get("action", "")).strip().lower()
            if action == "save":
                result = _save(claims["sub"], body)
            elif action == "test":
                result = _test(claims["sub"], str(body.get("exchange", "")).strip().lower(), str(body.get("mode", "DEMO")).strip().upper())
            elif action == "order":
                result = _order(claims["sub"], body)
            else:
                raise ValueError("action must be save, test, or order")
            send_json(self, result)
        except PermissionError as exc:
            send_json(self, {"detail": str(exc)}, 401)
        except ValueError as exc:
            send_json(self, {"detail": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"detail": str(exc)}, 500)
