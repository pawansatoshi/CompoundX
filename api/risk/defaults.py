import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from compoundx.config import CONFIG
from compoundx.vercel_http import send_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        send_json(self, {"risk_per_trade": CONFIG.risk.risk_per_trade, "daily_loss_limit": CONFIG.risk.daily_loss_limit, "max_drawdown": CONFIG.risk.max_drawdown, "max_positions": CONFIG.risk.max_positions, "minimum_signal_score": CONFIG.strategy.minimum_signal_score})
