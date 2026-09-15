import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse
BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND) not in sys.path: sys.path.insert(0, str(BACKEND))
from compoundx.autonomous_intelligence import build_autonomous_intelligence
from compoundx.db import connection, is_configured
from compoundx.derivatives_gate import final_derivatives_options_gate
from compoundx.economic_calendar import committee_calendar_gate, fetch_calendar
from compoundx.exchange import ExchangeGateway
from compoundx.expiry import analyze_expiries
from compoundx.market_intelligence import build_command_center
from compoundx.research_engine import build_research_intelligence
from compoundx.trade_chart import equity_curve, summarize_trades, trade_markers
from compoundx.vercel_http import read_json, send_json


def _apply_macro_gate(result, symbol):
    calendar = fetch_calendar(symbol=symbol, days=3)
    result["economic_calendar"] = calendar
    passed, reasons = committee_calendar_gate(calendar)
    result["economic_calendar_gate"] = "PASS" if passed else "BLOCKED"
    result["macro_risk"] = calendar.get("risk_score", 1.0)
    if not passed:
        result["decision"] = "NO_TRADE"
        result.setdefault("reasons", []).extend(reasons)
        result.setdefault("adversarial", {}).setdefault("failures", []).extend(reasons)
        result.setdefault("adversarial", {})["passed"] = False
        result.setdefault("adversarial", {})["challenge"] = "REJECT"
    return result


def _trade_ledger(symbol, limit=100):
    if not is_configured():
        return {"source": "empty", "trades": [], "summary": summarize_trades([]), "equity_curve": []}
    with connection() as conn:
        cur = conn.execute(
            "SELECT id,symbol,side,quantity,entry_price,exit_price,realized_pnl,fees,slippage,mode,status,opened_at,closed_at FROM trades WHERE symbol=%s ORDER BY opened_at DESC LIMIT %s",
            (symbol, limit),
        )
        names = [d.name for d in cur.description]
        rows = [dict(zip(names, r)) for r in cur.fetchall()]
    return {"source": "postgresql", "trades": trade_markers(rows), "summary": summarize_trades(rows), "equity_curve": equity_curve(rows)}


def _apply_research(result, ledger):
    feature_names = [
        "open", "high", "low", "close", "volume", "ema20", "ema50", "ema200",
        "vwap", "rsi", "atr", "market_structure", "spread_bps", "depth", "funding_rate",
        "open_interest", "expiry_distance", "macro_risk", "news_score", "regime",
    ]
    research = build_research_intelligence(
        market_data={},
        market_summary=result,
        trades=ledger.get("trades", []),
        feature_names=feature_names,
    )
    result["research_intelligence"] = research
    result["research_gate"] = "PASS" if research.get("research_ready") else "NOT_CERTIFIED"
    if result.get("decision") == "TRADE" and not research.get("research_ready"):
        result["decision"] = "NO_TRADE"
        result.setdefault("reasons", []).append("research validation not certified")
    return result


def _apply_autonomy(result, symbol, market_data, derivatives, expiry, expiry_market_data):
    autonomy = build_autonomous_intelligence(
        symbol=symbol,
        market_data=market_data,
        market_summary=result,
        derivatives=derivatives,
        expiry=expiry,
        macro_blocked=result.get("economic_calendar_gate") == "BLOCKED",
    )
    result["autonomous_intelligence"] = autonomy
    result["autonomous_decision"] = autonomy.get("decision", "NO_TRADE")
    result["live_execution"] = False
    result["paper_trading"] = True
    if autonomy.get("decision") != "TRADE":
        result["decision"] = "NO_TRADE"
        result.setdefault("reasons", []).extend(autonomy.get("failures", []))
    ledger = _trade_ledger(symbol)
    result["paper_trade_ledger"] = ledger
    result = _apply_research(result, ledger)
    final_gate = final_derivatives_options_gate(derivatives, expiry, expiry_market_data)
    result["derivatives_options_gate"] = final_gate
    if result.get("decision") == "TRADE" and not final_gate.get("passed", False):
        result["decision"] = "NO_TRADE"
        result.setdefault("reasons", []).extend(final_gate.get("blockers", []))
    return result


def _scan(symbol, exchange_id, sandbox, equity, limit):
    gateway = ExchangeGateway(exchange_id=exchange_id, sandbox=sandbox)
    market_data = gateway.multi_timeframe_market_data(symbol, limit=limit, orderbook_limit=100)
    derivatives = gateway.derivatives_market_data(symbol)
    expiry_data = gateway.expiry_market_data(symbol, limit=100)
    expiry = analyze_expiries(expiry_data.get("instruments"), market_type=expiry_data.get("market_type", "spot"))
    result = build_command_center(symbol, market_data, derivatives, expiry, equity=equity)
    result.update({
        "exchange": exchange_id,
        "sandbox": sandbox,
        "data_source": "exchange_public_market_data",
        "supported_timeframes": gateway.supported_timeframes(),
        "live_execution": False,
    })
    return _apply_autonomy(_apply_macro_gate(result, symbol), symbol, market_data, derivatives, expiry, expiry_data)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            p = parse_qs(urlparse(self.path).query)
            symbol = p.get("symbol", ["BTC/USDT"])[0]
            exchange = p.get("exchange", ["binance"])[0].lower()
            sandbox = p.get("sandbox", ["true"])[0].lower() != "false"
            send_json(self, _scan(symbol, exchange, sandbox, 100.0, 250))
        except ValueError as exc:
            send_json(self, {"detail": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"detail": str(exc), "decision": "NO_TRADE", "live_execution": False}, 503)

    def do_POST(self):
        try:
            b = read_json(self)
            symbol = str(b.get("symbol", "BTC/USDT")).strip()
            exchange = str(b.get("exchange", "binance")).lower()
            sandbox = bool(b.get("sandbox", True))
            equity = max(0.0, float(b.get("equity", 100.0)))
            limit = min(500, max(50, int(b.get("limit", 250))))
            send_json(self, _scan(symbol, exchange, sandbox, equity, limit))
        except ValueError as exc:
            send_json(self, {"detail": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"detail": str(exc), "decision": "NO_TRADE", "live_execution": False}, 503)
