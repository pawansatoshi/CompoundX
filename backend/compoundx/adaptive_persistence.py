from __future__ import annotations

"""Persistence helpers for the adaptive intelligence loop.

Persistence is best-effort: database failures are surfaced to observability but
must never turn an otherwise fail-closed market decision into a false trade.
"""

import hashlib
import json
from typing import Any

from .db import connection, is_configured


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, default=str, separators=(",", ":"), sort_keys=True)


def _direction(result: dict[str, Any]) -> int:
    raw = result.get("direction")
    if isinstance(raw, (int, float)):
        return 1 if raw > 0 else -1 if raw < 0 else 0
    label = str(result.get("direction_label", "NONE")).upper()
    return 1 if label == "LONG" else -1 if label == "SHORT" else 0


def adaptive_fingerprint(result: dict[str, Any], symbol: str) -> str:
    payload = {
        "symbol": symbol,
        "direction": _direction(result),
        "regime": result.get("regime"),
        "strategy": result.get("strategy") or result.get("strategy_research", {}).get("selected_hypothesis", {}).get("strategy"),
        "probability": result.get("adaptive_intelligence", {}).get("final_probability"),
        "evidence_dependency": result.get("adaptive_intelligence", {}).get("evidence_dependency"),
    }
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def persist_adaptive_decision(result: dict[str, Any], symbol: str) -> dict[str, Any]:
    """Persist one adaptive decision without affecting the trading decision."""
    if not is_configured():
        return {"persisted": False, "reason": "database not configured"}

    adaptive = result.get("adaptive_intelligence") or {}
    fingerprint = adaptive_fingerprint(result, symbol)
    decision = str(result.get("decision", "NO_TRADE")).upper()
    if decision not in {"TRADE", "NO_TRADE"}:
        decision = "NO_TRADE"
    strategy = result.get("strategy") or (result.get("strategy_research") or {}).get("selected_hypothesis", {}).get("strategy") or "unknown"
    regime = result.get("regime")
    if isinstance(regime, dict):
        regime = regime.get("label") or regime.get("regime") or "UNKNOWN"
    regime = str(regime or "UNKNOWN")
    probability = adaptive.get("final_probability")
    if isinstance(probability, dict):
        probability = probability.get("calibrated")
    lower = probability
    if isinstance(adaptive.get("final_probability"), dict):
        lower = adaptive["final_probability"].get("lower_bound")
    raw_ev = result.get("net_expected_value", result.get("expected_value"))
    net_ev = None if raw_ev is None else float(raw_ev)

    thesis = {
        "thesis": result.get("thesis", ""),
        "invalidation": result.get("invalidation", result.get("stop_reason", "")),
    }
    evidence = {
        "supporting": result.get("supporting_evidence", []),
        "contradicting": result.get("contradicting_evidence", []),
        "missing": result.get("missing_evidence", []),
        "dependency": adaptive.get("evidence_dependency", {}),
    }

    with connection() as conn:
        conn.execute(
            """INSERT INTO adaptive_decisions
               (fingerprint,symbol,decision,direction,probability,probability_lower,net_expected_value,
                regime,strategy,thesis,evidence,counterfactual,self_critique)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb)""",
            (
                fingerprint,
                symbol,
                decision,
                _direction(result),
                probability,
                lower,
                net_ev,
                regime,
                str(strategy),
                _json(thesis),
                _json(evidence),
                _json(adaptive.get("counterfactual", {})),
                _json(adaptive.get("self_critique", {})),
            ),
        )
    return {"persisted": True, "fingerprint": fingerprint}
