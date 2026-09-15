import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from compoundx.db import connection, is_configured
from compoundx.learning import review_similar_lessons
from compoundx.vercel_http import bearer_claims, read_json, send_json


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            if not is_configured():
                send_json(self, {"detail": "Database is not configured"}, 503)
                return
            bearer_claims(self)
            body = read_json(self)
            with connection() as conn:
                result = review_similar_lessons(conn, body.get("context") or {})
            send_json(self, result)
        except PermissionError as exc:
            send_json(self, {"detail": str(exc)}, 401)
        except ValueError as exc:
            send_json(self, {"detail": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"detail": str(exc)}, 500)
