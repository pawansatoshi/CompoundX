import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from compoundx.exchange import ExchangeGateway
from compoundx.expiry import analyze_expiries
from compoundx.vercel_http import bearer_claims, read_json, send_json


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            bearer_claims(self)
            body = read_json(self)
            symbol = str(body.get("symbol", "")).strip()
            if not symbol:
                raise ValueError("symbol is required")
            exchange_id = str(body.get("exchange", "binance")).strip().lower()
            gateway = ExchangeGateway(exchange_id=exchange_id, sandbox=True)
            raw = gateway.expiry_market_data(symbol, limit=min(250, max(1, int(body.get("limit", 100)))))
            market_type = "derivative" if raw.get("instruments") else "spot"
            analysis = analyze_expiries(raw.get("instruments", []), market_type=market_type)
            send_json(self, {"symbol": symbol, "exchange": exchange_id, "analysis": analysis, "live_execution": False})
        except PermissionError as exc:
            send_json(self, {"detail": str(exc)}, 401)
        except ValueError as exc:
            send_json(self, {"detail": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"detail": str(exc)}, 500)
