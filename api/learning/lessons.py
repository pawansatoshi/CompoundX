import sys
import uuid
from http.server import BaseHTTPRequestHandler
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from compoundx.db import connection, is_configured
from compoundx.learning import record_trade_lesson
from compoundx.vercel_http import bearer_claims, read_json, send_json


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            if not is_configured():
                send_json(self, {"detail": "Database is not configured"}, 503)
                return
            bearer_claims(self)
            body = read_json(self)
            trade_id = str(body.get("trade_id", ""))
            uuid.UUID(trade_id)
            context = body.get("context") or {}
            outcome = body.get("outcome") or {}
            with connection() as conn:
                result = record_trade_lesson(conn, trade_id=trade_id, context=context, outcome=outcome)
            send_json(self, {"ok": True, **result})
        except PermissionError as exc:
            send_json(self, {"detail": str(exc)}, 401)
        except ValueError as exc:
            send_json(self, {"detail": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"detail": str(exc)}, 500)
