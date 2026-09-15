import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from compoundx.vercel_http import send_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        send_json(self, {"mode": "PAPER", "live_orders": False, "withdrawals": False})
