from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from compoundx.auth import bearer_claims
from compoundx.exchange import ExchangeGateway
from compoundx.expiry import analyze_expiries


class handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict):
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            bearer_claims(self.headers.get("Authorization", ""))
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
            symbol = str(data.get("symbol", "")).strip()
            if not symbol:
                return self._send(400, {"error": "symbol is required"})
            exchange_id = str(data.get("exchange", "binance"))
            gateway = ExchangeGateway(exchange_id=exchange_id, sandbox=True)
            raw = gateway.expiry_market_data(symbol, limit=min(250, max(1, int(data.get("limit", 100)))))
            analysis = analyze_expiries(raw.get("instruments", []), market_type=raw.get("market_type", "derivative"))
            return self._send(200, {"symbol": symbol, "exchange": exchange_id, "analysis": analysis, "live_execution": False})
        except PermissionError as exc:
            return self._send(401, {"error": str(exc)})
        except (ValueError, json.JSONDecodeError) as exc:
            return self._send(400, {"error": str(exc)})
        except Exception as exc:
            return self._send(502, {"error": "expiry market-data request failed", "detail": str(exc)})
