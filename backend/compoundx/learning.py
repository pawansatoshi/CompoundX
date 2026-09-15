from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .db import connection


# Learning is advisory only. It can never alter hard risk limits or enable live execution.
MIN_SIMILAR_TRADES = 3
MIN_CONFIDENCE = 0.60
MAX_ADJUSTMENT = 2


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def fingerprint(context: dict[str, Any]) -> str:
    """Stable, coarse setup fingerprint used to retrieve comparable past trades."""
    keys = ("symbol", "side", "regime", "timeframe", "setup", "volume_confirmed", "trend_confirmed")
    normalized = {k: context.get(k) for k in keys}
    return hashlib.sha256(_json(normalized).encode()).hexdigest()[:32]


def record_trade_lesson(conn, *, trade_id: str, context: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
    pnl = float(outcome.get("realized_pnl", 0))
    won = pnl > 0
    fingerprint_value = fingerprint(context)
    mistake = str(outcome.get("mistake") or ("none" if won else "setup_failed"))
    solution = str(outcome.get("solution") or ("retain_current_rules" if won else "require_additional_confirmation"))
    evidence = {
        "pnl": pnl,
        "fees": float(outcome.get("fees", 0)),
        "slippage": float(outcome.get("slippage", 0)),
        "exit_reason": outcome.get("exit_reason"),
        "context": context,
    }
    lesson_id = __import__("uuid").uuid4()
    conn.execute(
        "INSERT INTO trade_lessons(id,trade_id,fingerprint,symbol,side,regime,setup,won,mistake,solution,confidence,evidence) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
        (lesson_id, __import__("uuid").UUID(trade_id), fingerprint_value, context.get("symbol", "UNKNOWN"), context.get("side", "NONE"), context.get("regime", "UNKNOWN"), context.get("setup", "unknown"), won, mistake, solution, 0.50 if won else 0.75, _json(evidence)),
    )
    return {"lesson_id": str(lesson_id), "fingerprint": fingerprint_value, "mistake": mistake, "solution": solution}


def review_similar_lessons(conn, context: dict[str, Any], limit: int = 20) -> dict[str, Any]:
    fp = fingerprint(context)
    rows = conn.execute(
        "SELECT id,won,mistake,solution,confidence,evidence FROM trade_lessons WHERE fingerprint=%s ORDER BY created_at DESC LIMIT %s",
        (fp, min(max(limit, 1), 100)),
    ).fetchall()
    if not rows:
        return {"similar_trades": 0, "matched_lessons": [], "adjustment": 0, "decision": "UNCHANGED", "confidence": 0.0}

    losses = sum(1 for r in rows if not r[1])
    wins = len(rows) - losses
    weighted_conf = sum(float(r[4]) for r in rows) / len(rows)
    adjustment = 0
    if len(rows) >= MIN_SIMILAR_TRADES and losses > wins and weighted_conf >= MIN_CONFIDENCE:
        adjustment = -min(MAX_ADJUSTMENT, max(1, losses - wins))
    elif len(rows) >= MIN_SIMILAR_TRADES and wins > losses and weighted_conf >= MIN_CONFIDENCE:
        adjustment = min(MAX_ADJUSTMENT, wins - losses)

    lessons = [
        {"lesson_id": str(r[0]), "won": bool(r[1]), "mistake": r[2], "solution": r[3], "confidence": float(r[4])}
        for r in rows[:10]
    ]
    return {
        "similar_trades": len(rows),
        "wins": wins,
        "losses": losses,
        "matched_lessons": lessons,
        "adjustment": adjustment,
        "decision": "REDUCE" if adjustment < 0 else "SUPPORT" if adjustment > 0 else "UNCHANGED",
        "confidence": round(weighted_conf, 4),
    }


def pre_trade_check(context: dict[str, Any], base_score: int, minimum_score: int) -> dict[str, Any]:
    with connection() as conn:
        learning = review_similar_lessons(conn, context)
    adjusted_score = max(0, min(9, base_score + learning["adjustment"]))
    blocked = learning["decision"] == "REDUCE" and adjusted_score < minimum_score
    return {
        "base_score": base_score,
        "adjusted_score": adjusted_score,
        "minimum_score": minimum_score,
        "blocked": blocked,
        "reason": "historical failure pattern" if blocked else "learning review passed",
        "learning": learning,
    }


def apply_solution_feedback(conn, lesson_id: str, effective: bool) -> None:
    """Reward or penalize a lesson after enough later evidence is available."""
    delta = 0.05 if effective else -0.05
    conn.execute(
        "UPDATE trade_lessons SET confidence=LEAST(1.0,GREATEST(0.0,confidence+%s)), updated_at=%s WHERE id=%s",
        (delta, datetime.now(timezone.utc), __import__("uuid").UUID(lesson_id)),
    )
