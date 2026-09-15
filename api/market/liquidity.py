import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from compoundx.exchange import ExchangeGateway
from compoundx.liquidity import analyze_multi_timeframe_liquidity
from compoundx.vercel_http import bearer_claims, read_json, send_json


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            bearer_claims(self)
            body = read_json(self)
            symbol = str(body.get("symbol", "")).strip()
            if not symbol:
                raise ValueError("symbol is required")
            order_notional = float(body.get("order_notional", 0) or 0)
            if order_notional <= 0:
                raise ValueError("order_notional must be positive")
            exchange_id = str(body.get("exchange", "binance")).strip().lower()
            gateway = ExchangeGateway(exchange_id=exchange_id, sandbox=True)
            snapshots = gateway.multi_timeframe_market_data(symbol, limit=250, orderbook_limit=100)
            long_result = analyze_multi_timeframe_liquidity(snapshots, side="LONG", order_notional=order_notional)
            short_result = analyze_multi_timeframe_liquidity(snapshots, side="SHORT", order_notional=order_notional)
            send_json(self, {
                "symbol": symbol,
                "exchange": exchange_id,
                "timeframes": gateway.supported_timeframes(),
                "long": long_result,
                "short": short_result,
                "live_execution": False,
            })
        except PermissionError as exc:
            send_json(self, {"detail": str(exc)}, 401)
        except ValueError as exc:
            send_json(self, {"detail": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"detail": str(exc)}, 500)
