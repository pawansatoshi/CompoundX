from __future__ import annotations

"""Auditable paper-trade chart/ledger projection."""
from typing import Any


def _f(x: Any, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def trade_markers(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    markers = []
    for r in rows:
        side = str(r.get("side", "")).upper()
        entry = _f(r.get("entry_price"))
        if side not in {"LONG", "SHORT"} or entry <= 0:
            continue
        exit_price = r.get("exit_price")
        markers.append({"trade_id": str(r.get("id")), "type": "BUY" if side == "LONG" else "SELL", "side": side, "time": r.get("opened_at"), "price": entry, "status": r.get("status"), "pnl": _f(r.get("realized_pnl")), "fees": _f(r.get("fees")), "slippage": _f(r.get("slippage")), "exit": {"time": r.get("closed_at"), "price": _f(exit_price)} if exit_price is not None else None, "stop": _f(r.get("stop_price")) if r.get("stop_price") is not None else None, "target": _f(r.get("target_price")) if r.get("target_price") is not None else None})
    return markers


def summarize_trades(rows: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [r for r in rows if str(r.get("status", "")).upper() == "CLOSED"]
    pnl = sum(_f(r.get("realized_pnl")) for r in closed)
    fees = sum(_f(r.get("fees")) for r in closed)
    wins = sum(_f(r.get("realized_pnl")) > 0 for r in closed)
    losses = sum(_f(r.get("realized_pnl")) < 0 for r in closed)
    return {"trades": len(rows), "closed": len(closed), "open": sum(str(r.get("status", "")).upper() == "OPEN" for r in rows), "wins": wins, "losses": losses, "win_rate": wins / len(closed) if closed else 0.0, "realized_pnl": pnl, "fees": fees, "net_pnl": pnl - fees}


def equity_curve(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda r: str(r.get("closed_at") or r.get("opened_at") or ""))
    equity, out = 0.0, []
    for r in ordered:
        if str(r.get("status", "")).upper() != "CLOSED":
            continue
        equity += _f(r.get("realized_pnl")) - _f(r.get("fees"))
        out.append({"time": r.get("closed_at"), "equity": equity, "trade_id": str(r.get("id"))})
    return out
