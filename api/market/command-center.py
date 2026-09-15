import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from compoundx.economic_calendar import committee_calendar_gate, fetch_calendar
from compoundx.exchange import ExchangeGateway
from compoundx.expiry import analyze_expiries
from compoundx.market_intelligence import build_command_center
from compoundx.vercel_http import read_json, send_json


def _apply_macro_gate(result: dict, symbol: str) -> dict:
    calendar = fetch_calendar(symbol=symbol, days=3)
    result["economic_calendar"] = calendar
    passed, macro_reasons = committee_calendar_gate(calendar)
    result["economic_calendar_gate"] = "PASS" if passed else "BLOCKED"
    result["macro_risk"] = calendar.get("risk_score", 1.0)
    if not passed:
        result["decision"] = "NO_TRADE"
        result.setdefault("reasons", []).extend(macro_reasons)
        result.setdefault("adversarial", {}).setdefault("failures", []).extend(macro_reasons)
        result.setdefault("adversarial", {})["passed"] = False
        result.setdefault("adversarial", {})["challenge"] = "REJECT"
    return result


def _scan(symbol: str, exchange_id: str, sandbox: bool, equity: float, limit: int) -> dict:
    gateway = ExchangeGateway(exchange_id=exchange_id, sandbox=sandbox)
    market_data = gateway.multi_timeframe_market_data(symbol, limit=limit, orderbook_limit=100)
    derivatives = gateway.derivatives_market_data(symbol)
    expiry_data = gateway.expiry_market_data(symbol, limit=100)
    expiry = analyze_expiries(expiry_data.get("instruments"), market_type=expiry_data.get("market_type", "spot"))
    result = build_command_center(symbol, market_data, derivatives, expiry, equity=equity)
    result["exchange"] = exchange_id
    result["sandbox"] = sandbox
    result["data_source"] = "exchange_public_market_data"
    result["supported_timeframes"] = gateway.supported_timeframes()
    result["live_execution"] = False
    return _apply_macro_gate(result, symbol)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            params = parse_qs(urlparse(self.path).query)
            symbol = params.get("symbol", ["BTC/USDT"])[0]
            exchange_id = params.get("exchange", ["binance"])[0].lower()
            sandbox = params.get("sandbox", ["true"])[0].lower() != "false"
            send_json(self, _scan(symbol, exchange_id, sandbox, 100.0, 250))
        except ValueError as exc:
            send_json(self, {"detail": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"detail": str(exc), "decision": "NO_TRADE", "live_execution": False}, 503)

    def do_POST(self):
        try:
            body = read_json(self)
            symbol = str(body.get("symbol", "BTC/USDT")).strip()
            exchange_id = str(body.get("exchange", "binance")).lower()
            sandbox = bool(body.get("sandbox", True))
            equity = max(0.0, float(body.get("equity", 100.0)))
            limit = min(500, max(50, int(body.get("limit", 250))))
            send_json(self, _scan(symbol, exchange_id, sandbox, equity, limit))
        except ValueError as exc:
            send_json(self, {"detail": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"detail": str(exc), "decision": "NO_TRADE", "live_execution": False}, 503)
