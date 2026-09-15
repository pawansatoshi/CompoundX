import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from compoundx.db import connection, is_configured
from compoundx.learning import review_similar_lessons
from compoundx.main import bearer_token
from compoundx.vercel_http import send_json


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not is_configured():
            send_json(self, {"detail": "Database is not configured"}, 503)
            return
        try:
            bearer_token(self.headers.get("Authorization"))
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            with connection() as conn:
                result = review_similar_lessons(conn, body.get("context") or {})
            send_json(self, result)
        except Exception as exc:
            send_json(self, {"detail": str(exc)}, 400)
