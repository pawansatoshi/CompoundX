from http.server import BaseHTTPRequestHandler

from compoundx.config import CONFIG
from compoundx.vercel_http import send_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        send_json(self, {"status": "ok", "paper_trading": CONFIG.paper_trading, "live_execution_enabled": CONFIG.live_execution_enabled, "withdrawals_enabled": CONFIG.withdrawals_enabled, "database_configured": __import__("compoundx.db", fromlist=["is_configured"]).is_configured()})
