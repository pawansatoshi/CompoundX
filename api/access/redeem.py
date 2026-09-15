import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from compoundx.vercel_http import read_json, redeem, send_json


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            payload, status = redeem(read_json(self), self)
            send_json(self, payload, status)
        except PermissionError as exc:
            code = 429 if str(exc) == "Rate limit exceeded" else 403
            send_json(self, {"detail": str(exc)}, code)
        except ValueError as exc:
            send_json(self, {"detail": str(exc)}, 400)
        except RuntimeError as exc:
            send_json(self, {"detail": str(exc)}, 503)
        except Exception:
            send_json(self, {"detail": "Internal server error"}, 500)
