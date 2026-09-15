import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from compoundx.exchange import ExchangeGateway
from compoundx.expiry import analyze_expiries
from compoundx.market_intelligence import build_command_center
from compoundx.vercel_http import read_json, send_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            query = self.path.split("?", 1)[1] if "?" in self.path else ""
            params = dict(item.split("=", 1) for item in query.split("&") if "=" in item)
            symbol = params.get("symbol", "BTC/USDT").replace("%2F", "/").replace("%2f", "/")
            exchange_id = params.get("exchange", "binance").lower()
            sandbox = params.get("sandbox", "true").lower() != "false"
            gateway = ExchangeGateway(exchange_id=exchange_id, sandbox=sandbox)
            market_data = gateway.multi_timeframe_market_data(symbol, limit=250, orderbook_limit=100)
            derivatives = gateway.derivatives_market_data(symbol)
            expiry_data = gateway.expiry_market_data(symbol, limit=100)
            expiry = analyze_expiries(expiry_data.get("instruments"), market_type=expiry_data.get("market_type", "spot"))
            result = build_command_center(symbol, market_data, derivatives, expiry, equity=100.0)
            result["exchange"] = exchange_id
            result["sandbox"] = sandbox
            result["data_source"] = "exchange_public_market_data"
            result["supported_timeframes"] = gateway.supported_timeframes()
            result["live_execution"] = False
            send_json(self, result)
        except ValueError as exc:
            send_json(self, {"detail": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"detail": str(exc), "decision": "NO_TRADE", "live_execution": False}, 503)

    def do_POST(self):
        try:
            body = read_json(self)
            symbol = str(body.get("symbol", "BTC/USDT")).strip()
            gateway = ExchangeGateway(exchange_id=str(body.get("exchange", "binance")).lower(), sandbox=bool(body.get("sandbox", True)))
            market_data = gateway.multi_timeframe_market_data(symbol, limit=min(500, max(50, int(body.get("limit", 250)))), orderbook_limit=100)
            derivatives = gateway.derivatives_market_data(symbol)
            expiry_data = gateway.expiry_market_data(symbol, limit=100)
            expiry = analyze_expiries(expiry_data.get("instruments"), market_type=expiry_data.get("market_type", "spot"))
            result = build_command_center(symbol, market_data, derivatives, expiry, equity=max(0.0, float(body.get("equity", 100.0))))
            result["exchange"] = str(body.get("exchange", "binance")).lower()
            result["sandbox"] = bool(body.get("sandbox", True))
            result["data_source"] = "exchange_public_market_data"
            result["live_execution"] = False
            send_json(self, result)
        except ValueError as exc:
            send_json(self, {"detail": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"detail": str(exc), "decision": "NO_TRADE", "live_execution": False}, 503)
