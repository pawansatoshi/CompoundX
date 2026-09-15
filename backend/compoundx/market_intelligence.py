from __future__ import annotations

"""Deterministic market-intelligence layer for the CompoundX command center.

Market observations can produce a research candidate, but a trade is never
authorized without historical evidence, risk approval and execution checks.
"""

from datetime import datetime, timezone
from math import isfinite
from statistics import mean
from typing import Any

from .indicators import atr, ema, rsi, vwap

TIMEFRAME_ORDER = ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w")


def _f(value: Any, default: float = 0.0) -> float:
    try:
        value = float(value)
        return value if isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _ohlcv(candles: list[list[float]]) -> tuple[list[float], list[float], list[float], list[float]]:
    rows = [x for x in candles if isinstance(x, (list, tuple)) and len(x) >= 6]
    return ([ _f(x[2]) for x in rows ], [ _f(x[3]) for x in rows ], [ _f(x[4]) for x in rows ], [ _f(x[5]) for x in rows ])


def _structure(high: list[float], low: list[float], close: list[float], window: int = 20) -> str:
    if len(close) < 5:
        return "UNKNOWN"
    h, l, c = max(high[-window:]), min(low[-window:]), close[-1]
    pos = (c - l) / max(1e-12, h - l)
    if pos >= 0.8:
        return "UPPER_RANGE"
    if pos <= 0.2:
        return "LOWER_RANGE"
    return "MID_RANGE"


def _regime(closes: list[float], fast: float, slow: float, long: float, atr_pct: float, volume_ratio: float) -> tuple[str, float]:
    if len(closes) < 30:
        return "INSUFFICIENT_DATA", 0.0
    separation = abs(fast - slow) / max(1e-12, closes[-1])
    if atr_pct > 0.045:
        return "HIGH_VOLATILITY", _clamp(0.55 + min(0.4, atr_pct * 6))
    if separation < 0.0015:
        return ("ACCUMULATION_DISTRIBUTION", 0.68) if volume_ratio > 1.5 else ("RANGE", 0.64)
    if fast > slow > long:
        return "TREND_UP", _clamp(0.70 + separation * 20)
    if fast < slow < long:
        return "TREND_DOWN", _clamp(0.70 + separation * 20)
    if volume_ratio > 2.0:
        return "BREAKOUT_ATTEMPT", 0.72
    return "TRANSITION", 0.58


def analyze_timeframe(timeframe: str, candles: list[list[float]]) -> dict[str, Any]:
    high, low, close, volume = _ohlcv(candles)
    if len(close) < 50:
        return {"timeframe": timeframe, "usable": False, "score": 0.0, "direction": "NEUTRAL", "regime": "INSUFFICIENT_DATA", "reason": "at least 50 candles required"}
    e20, e50, e200 = ema(close, 20), ema(close, 50), ema(close, 200)
    rs, at, vw = rsi(close, 14), atr(high, low, close, 14), vwap(high, low, close, volume)
    c, atr_pct = close[-1], at[-1] / max(1e-12, close[-1])
    vol_ratio = volume[-1] / max(1e-12, mean(volume[-20:]))
    regime, regime_score = _regime(close, e20[-1], e50[-1], e200[-1], atr_pct, vol_ratio)
    trend = 1 if e20[-1] > e50[-1] > e200[-1] else -1 if e20[-1] < e50[-1] < e200[-1] else 0
    momentum = 1 if rs[-1] >= 55 else -1 if rs[-1] <= 45 else 0
    vwap_side = 1 if c > vw[-1] else -1 if c < vw[-1] else 0
    structure = _structure(high, low, close)
    structure_bias = 1 if structure == "UPPER_RANGE" else -1 if structure == "LOWER_RANGE" else 0
    directional = trend + momentum + vwap_side + structure_bias
    direction = "LONG" if directional >= 2 else "SHORT" if directional <= -2 else "NEUTRAL"
    score = _clamp(0.35 * abs(trend) + 0.20 * abs(momentum) + 0.20 * abs(vwap_side) + 0.15 * abs(structure_bias) + 0.10 * regime_score)
    return {"timeframe": timeframe, "usable": True, "score": round(score, 4), "direction": direction, "regime": regime, "regime_score": round(regime_score, 4), "price": c, "ema20": e20[-1], "ema50": e50[-1], "ema200": e200[-1], "rsi14": rs[-1], "atr": at[-1], "atr_pct": atr_pct, "vwap": vw[-1], "volume_ratio": vol_ratio, "structure": structure}


def analyze_orderbook(orderbook: dict[str, Any], order_notional: float = 100.0) -> dict[str, Any]:
    bids, asks = orderbook.get("bids") or [], orderbook.get("asks") or []
    if not bids or not asks:
        return {"usable": False, "reason": "order book unavailable", "spread_bps": 0.0, "imbalance": 0.0, "long": {}, "short": {}, "walls": []}
    bid, ask = _f(bids[0][0]), _f(asks[0][0])
    mid = (bid + ask) / 2.0
    spread_bps = (ask - bid) / max(1e-12, mid) * 10000.0

    def side(rows: list[Any]) -> tuple[float, float]:
        depth = impact = 0.0
        remaining = max(0.0, order_notional)
        for row in rows:
            if len(row) < 2:
                continue
            price, qty = _f(row[0]), max(0.0, _f(row[1]))
            notional = price * qty
            depth += notional
            if remaining > 0 and price > 0:
                take = min(remaining, notional)
                impact += take * abs(price - mid) / mid
                remaining -= take
        return depth, impact / max(1e-12, order_notional) * 10000.0 if order_notional > 0 else 0.0

    bid_depth, bid_impact = side(bids)
    ask_depth, ask_impact = side(asks)
    imbalance = (bid_depth - ask_depth) / max(1e-12, bid_depth + ask_depth)
    long_score = _clamp(0.55 * min(1.0, ask_depth / max(1.0, order_notional * 5.0)) + 0.45 * (1.0 - max(-1.0, imbalance)) / 2.0)
    short_score = _clamp(0.55 * min(1.0, bid_depth / max(1.0, order_notional * 5.0)) + 0.45 * (1.0 + min(1.0, imbalance)) / 2.0)
    walls = []
    for label, rows in (("bid", bids), ("ask", asks)):
        for row in rows[:20]:
            if len(row) >= 2:
                notional = _f(row[0]) * _f(row[1])
                if notional >= max(1.0, order_notional):
                    walls.append({"side": label, "price": _f(row[0]), "notional": notional})
    return {"usable": spread_bps <= 35.0 and bid_depth > 0 and ask_depth > 0, "spread_bps": round(spread_bps, 4), "imbalance": round(imbalance, 4), "bid_depth": bid_depth, "ask_depth": ask_depth, "walls": sorted(walls, key=lambda x: x["notional"], reverse=True)[:10], "long": {"score": round(long_score, 4), "executable_depth": ask_depth, "impact_bps": round(ask_impact, 4)}, "short": {"score": round(short_score, 4), "executable_depth": bid_depth, "impact_bps": round(bid_impact, 4)}}


def analyze_derivatives(derivatives: dict[str, Any] | None) -> dict[str, Any]:
    d = derivatives or {}
    funding, oi = _f(d.get("funding_rate")), _f(d.get("open_interest"))
    oi_change, basis, liquidations = _f(d.get("open_interest_change_pct")), _f(d.get("basis_pct")), _f(d.get("liquidations_24h"))
    available = any(x != 0 for x in (funding, oi, oi_change, basis, liquidations))
    return {"available": available, "funding_rate": funding, "open_interest": oi, "open_interest_change_pct": oi_change, "basis_pct": basis, "liquidations_24h": liquidations, "positioning": "crowded_long" if funding > 0.0005 and oi_change > 0 else "crowded_short" if funding < -0.0005 and oi_change > 0 else "mixed", "warning": "derivatives evidence unavailable" if not available else "contextual only"}


def aggregate_timeframes(timeframes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = [v for k, v in timeframes.items() if k in TIMEFRAME_ORDER and v.get("usable")]
    if not rows:
        return {"direction": "NEUTRAL", "consensus": 0.0, "regime": "UNKNOWN", "conflict": True, "usable_timeframes": 0}
    longs, shorts = sum(r["direction"] == "LONG" for r in rows), sum(r["direction"] == "SHORT" for r in rows)
    direction = "LONG" if longs > shorts else "SHORT" if shorts > longs else "NEUTRAL"
    regimes = [r.get("regime") for r in rows]
    return {"direction": direction, "consensus": round(max(longs, shorts) / len(rows), 4), "regime": max(set(regimes), key=regimes.count), "conflict": min(longs, shorts) >= max(1, len(rows) // 4), "usable_timeframes": len(rows), "longs": longs, "shorts": shorts}


def adversarial_gate(direction: str, mtf: dict[str, Any], liquidity: dict[str, Any], derivatives: dict[str, Any], expiry: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if direction == "NEUTRAL": failures.append("no directional consensus")
    if mtf.get("conflict"): failures.append("multi-timeframe conflict")
    if mtf.get("consensus", 0.0) < 0.75: failures.append("consensus below adversarial threshold")
    if not liquidity.get("usable"): failures.append("liquidity unavailable or unsafe")
    if direction == "LONG" and liquidity.get("long", {}).get("score", 0.0) < 0.70: failures.append("long executable liquidity weak")
    if direction == "SHORT" and liquidity.get("short", {}).get("score", 0.0) < 0.70: failures.append("short executable liquidity weak")
    if derivatives.get("warning") == "derivatives evidence unavailable": failures.append("derivatives evidence unavailable")
    if expiry.get("status") == "UNKNOWN": failures.append("expiry structure unavailable for derivative context")
    return {"passed": not failures, "failures": failures, "challenge": "PASS" if not failures else "REJECT"}


def position_size(equity: float, risk_fraction: float, entry: float, stop: float, confidence: float) -> dict[str, float]:
    risk_budget = max(0.0, equity) * _clamp(risk_fraction, 0.0, 0.02)
    distance = abs(entry - stop)
    base = risk_budget / distance if distance > 0 else 0.0
    qty = base * (0.5 + 0.5 * _clamp(confidence))
    return {"risk_budget": risk_budget, "stop_distance": distance, "base_quantity": base, "quantity": qty, "notional": qty * entry}


def simulate_execution(orderbook: dict[str, Any], direction: str, notional: float, fee_bps: float = 5.0) -> dict[str, Any]:
    rows = (orderbook.get("asks") or []) if direction == "LONG" else (orderbook.get("bids") or [])
    if not rows or notional <= 0:
        return {"usable": False, "reason": "execution book unavailable"}
    remaining, spent, quantity = notional, 0.0, 0.0
    for row in rows:
        if len(row) < 2: continue
        price, qty = _f(row[0]), max(0.0, _f(row[1]))
        take = min(remaining, price * qty)
        quantity += take / max(1e-12, price)
        spent += take
        remaining -= take
        if remaining <= 0: break
    if spent <= 0 or quantity <= 0:
        return {"usable": False, "reason": "insufficient visible depth"}
    avg_fill, best = spent / quantity, _f(rows[0][0])
    return {"usable": remaining <= notional * 0.001, "requested_notional": notional, "filled_notional": spent, "quantity": quantity, "average_fill": avg_fill, "slippage_bps": abs(avg_fill - best) / max(1e-12, best) * 10000.0, "fee": spent * fee_bps / 10000.0, "remaining_notional": remaining}


def build_command_center(symbol: str, market_data: dict[str, dict[str, Any]], derivatives: dict[str, Any] | None, expiry: dict[str, Any] | None, equity: float = 100.0) -> dict[str, Any]:
    tf_results = {tf: analyze_timeframe(tf, payload.get("ohlcv") or []) for tf, payload in market_data.items()}
    usable = [v for v in tf_results.values() if v.get("usable")]
    primary = usable[-1] if usable else {"price": 0.0, "atr": 0.0, "regime": "UNKNOWN"}
    book = market_data.get("15m") or next(iter(market_data.values()), {})
    liquidity = analyze_orderbook(book.get("orderbook") or {}, order_notional=max(25.0, equity * 0.01))
    mtf, deriv, exp = aggregate_timeframes(tf_results), analyze_derivatives(derivatives), expiry or {"status": "NOT_APPLICABLE", "usable": True, "score": 1.0}
    adversarial = adversarial_gate(mtf["direction"], mtf, liquidity, deriv, exp)
    directional_liquidity = liquidity.get("long", {}).get("score", 0.0) if mtf["direction"] == "LONG" else liquidity.get("short", {}).get("score", 0.0)
    confidence = round(_clamp(0.30 * mtf.get("consensus", 0.0) + 0.25 * directional_liquidity + 0.20 * exp.get("score", 0.0) + 0.15 * (0.75 if deriv.get("available") else 0.0) + 0.10 * (0.0 if adversarial["failures"] else 1.0)), 4)
    reasons = list(adversarial["failures"])
    reasons.append("historical edge must be proven before authorization")
    if primary.get("regime") == "HIGH_VOLATILITY": reasons.append("high volatility regime")
    entry, atr_value = primary.get("price", 0.0), primary.get("atr", 0.0)
    plan = {"direction": mtf["direction"], "entry": entry, "stop": 0.0, "target": 0.0, "rr": 0.0}
    if entry and atr_value and mtf["direction"] == "LONG": plan.update(stop=entry - 1.5 * atr_value, target=entry + 3.0 * atr_value, rr=2.0)
    elif entry and atr_value and mtf["direction"] == "SHORT": plan.update(stop=entry + 1.5 * atr_value, target=entry - 3.0 * atr_value, rr=2.0)
    sizing = position_size(equity, 0.005, plan["entry"], plan["stop"], confidence) if plan["stop"] else {"risk_budget": equity * 0.005, "stop_distance": 0.0, "base_quantity": 0.0, "quantity": 0.0, "notional": 0.0}
    execution = simulate_execution(book.get("orderbook") or {}, mtf["direction"], max(25.0, min(equity, equity * 0.10))) if mtf["direction"] in {"LONG", "SHORT"} else {"usable": False, "reason": "no directional candidate"}
    return {"symbol": symbol, "timestamp": datetime.now(timezone.utc).isoformat(), "price": entry, "decision": "NO_TRADE", "confidence": confidence, "reasons": reasons, "regime": mtf.get("regime"), "market_score": confidence, "timeframes": tf_results, "multi_timeframe": mtf, "liquidity": liquidity, "derivatives": deriv, "expiry": exp, "adversarial": adversarial, "trade_plan": plan, "position_sizing": sizing, "execution_simulation": execution, "risk": {"risk_per_trade": 0.005, "daily_loss_limit": 0.02, "max_drawdown": 0.10, "live_execution": False, "withdrawals": False}, "learning": {"mode": "journal-driven", "historical_edge_required": True, "adaptive_adjustment_cap": "+/-2 signal points", "can_disable_risk": False}}
