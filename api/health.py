import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from compoundx.config import CONFIG
from compoundx.db import is_configured
from compoundx.vercel_http import send_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        send_json(self, {"status": "ok", "paper_trading": CONFIG.paper_trading, "live_execution_enabled": CONFIG.live_execution_enabled, "withdrawals_enabled": CONFIG.withdrawals_enabled, "database_configured": is_configured()})
