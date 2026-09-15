import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from compoundx.economic_calendar import fetch_calendar
from compoundx.vercel_http import bearer_claims, read_json, send_json


class handler(BaseHTTPRequestHandler):
    def _run(self, body=None):
        bearer_claims(self)
        if body is None:
            params = parse_qs(urlparse(self.path).query)
            symbol = params.get("symbol", ["BTC/USDT"])[0]
            days = int(params.get("days", [3])[0])
        else:
            symbol = str(body.get("symbol", "BTC/USDT")).strip()
            days = int(body.get("days", 3))
        result = fetch_calendar(symbol=symbol, days=days)
        send_json(self, {**result, "live_execution": False})

    def do_GET(self):
        try:
            self._run()
        except PermissionError as exc:
            send_json(self, {"detail": str(exc)}, 401)
        except ValueError as exc:
            send_json(self, {"detail": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"detail": str(exc)}, 503)

    def do_POST(self):
        try:
            self._run(read_json(self))
        except PermissionError as exc:
            send_json(self, {"detail": str(exc)}, 401)
        except ValueError as exc:
            send_json(self, {"detail": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"detail": str(exc)}, 503)
