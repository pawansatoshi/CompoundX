from __future__ import annotations

"""Deterministic, fail-closed AI-style trade committee."""

from dataclasses import dataclass
from math import isfinite
from typing import Any

from .expiry import analyze_expiries
from .liquidity import analyze_multi_timeframe_liquidity

MIN_HISTORY = 20
MIN_EDGE = 0.68
MIN_AGREEMENT = 0.75
MAX_DISAGREEMENT = 0.25
MIN_RR = 1.5
MAX_SPREAD_BPS = 35.0
MAX_SLIPPAGE_BPS = 20.0
MODELS = ("regime", "trend", "momentum", "volatility", "liquidity", "structure", "history", "news", "expiry")


@dataclass(frozen=True)
class Vote:
    model: str
    direction: int
    strength: float
    reason: str


@dataclass(frozen=True)
class CommitteeDecision:
    decision: str
    direction: int
    score: float
    agreement: float
    edge: float
    reasons: tuple[str, ...]
    votes: tuple[Vote, ...]
    liquidity: dict[str, Any] | None = None
    expiry: dict[str, Any] | None = None


def _clamp(value: Any, lo: float = -1.0, hi: float = 1.0) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not isfinite(value):
        return 0.0
    return max(lo, min(hi, value))


def _vote(name: str, value: Any, reason: str) -> Vote:
    x = _clamp(value)
    return Vote(name, 1 if x > 0 else -1 if x < 0 else 0, abs(x), reason)


def _history_edge(context: dict[str, Any]) -> tuple[float, int, str]:
    n = int(context.get("history_count", 0) or 0)
    win_rate = float(context.get("history_win_rate", 0) or 0)
    expectancy = float(context.get("history_expectancy", 0) or 0)
    if n < MIN_HISTORY:
        return 0.0, 0, f"insufficient comparable history ({n}/{MIN_HISTORY})"
    if not 0.0 <= win_rate <= 1.0:
        return 0.0, 0, "invalid historical win rate"
    edge = max(0.0, min(1.0, 0.5 * win_rate + 0.5 * (1.0 if expectancy > 0 else 0.0)))
    raw_direction = context.get("history_direction", context.get("direction", 0))
    direction = 1 if raw_direction > 0 else -1 if raw_direction < 0 else 0
    return edge, direction, f"history n={n}, win_rate={win_rate:.2%}, expectancy={expectancy:.4g}"


def _legacy_liquidity(context: dict[str, Any], direction: int, reasons: list[str]) -> tuple[float, dict[str, Any] | None]:
    matrix = context.get("liquidity_matrix")
    if isinstance(matrix, dict):
        if not bool(matrix.get("usable", False)):
            reasons.append(str(matrix.get("reason", "multi-timeframe liquidity rejected")))
        return _clamp(matrix.get("score", 0.0)), matrix
    if "liquidity_score" not in context:
        reasons.append("missing multi-timeframe liquidity evidence")
        return 0.0, None
    return _clamp(context.get("liquidity_score", 0.0)), None


def evaluate_committee(context: dict[str, Any]) -> CommitteeDecision:
    direction = 1 if context.get("direction", 0) > 0 else -1 if context.get("direction", 0) < 0 else 0
    reasons: list[str] = []
    regime = str(context.get("regime", "UNKNOWN")).upper()
    if regime == "UNKNOWN": reasons.append("unknown regime")
    if context.get("news_risk", False): reasons.append("news/event risk")

    liquidity_score, liquidity = _legacy_liquidity(context, direction, reasons)
    expiry = context.get("expiry_analysis")
    if not isinstance(expiry, dict):
        instruments = context.get("expiry_instruments")
        if instruments is not None:
            expiry = analyze_expiries(instruments, market_type=str(context.get("market_type", "derivative")))
    if not isinstance(expiry, dict):
        # Explicit spot/cash candidates can safely proceed without expiry.
        if str(context.get("market_type", "derivative")).lower() in {"spot", "cash"}:
            expiry = analyze_expiries(None, market_type="spot")
        else:
            expiry = {"status": "UNKNOWN", "usable": False, "score": 0.0, "reason": "expiry evidence unavailable"}
    if not bool(expiry.get("usable", False)) and expiry.get("status") != "NOT_APPLICABLE":
        reasons.append(str(expiry.get("reason", "expiry analysis rejected")))

    votes = [
        _vote("regime", context.get("regime_score", 0), f"regime={regime}"),
        _vote("trend", context.get("trend_score", 0), "trend confirmation"),
        _vote("momentum", context.get("momentum_score", 0), "momentum confirmation"),
        _vote("volatility", context.get("volatility_score", 0), "volatility quality"),
        _vote("liquidity", liquidity_score, "multi-timeframe liquidity quality"),
        _vote("structure", context.get("structure_score", 0), "market structure"),
    ]
    history_edge, history_direction, history_reason = _history_edge(context)
    if int(context.get("history_count", 0) or 0) < MIN_HISTORY:
        reasons.append(history_reason)
    votes.append(_vote("history", history_edge if history_direction == direction else -history_edge, history_reason))
    votes.append(_vote("news", context.get("news_score", 0), "news/sentiment filter"))
    expiry_score = _clamp(expiry.get("score", 0.0)) if expiry.get("status") != "NOT_APPLICABLE" else 1.0
    votes.append(_vote("expiry", expiry_score, str(expiry.get("reason", "expiry not applicable"))))

    active = [v for v in votes if v.direction != 0]
    if not active or direction == 0:
        reasons.append("no directional consensus")
        return CommitteeDecision("NO_TRADE", direction, 0.0, 0.0, history_edge, tuple(reasons), tuple(votes), liquidity, expiry)
    aligned = [v for v in active if v.direction == direction]
    agreement = len(aligned) / len(active)
    weighted = sum(v.direction * v.strength for v in active) / len(active)
    score = max(0.0, min(1.0, (weighted * direction + 1.0) / 2.0))
    if history_edge < MIN_EDGE: reasons.append("historical edge below threshold")
    if history_direction not in (0, direction): reasons.append("historical direction conflicts")
    if agreement < MIN_AGREEMENT: reasons.append(f"model agreement {agreement:.1%} below {MIN_AGREEMENT:.0%}")
    if (1.0 - agreement) > MAX_DISAGREEMENT: reasons.append("material model disagreement")
    if liquidity_score <= 0.0: reasons.append("liquidity evidence unavailable or failed")
    rr = float(context.get("risk_reward", 0) or 0)
    if rr < MIN_RR: reasons.append(f"risk/reward {rr:.2f} below {MIN_RR:.2f}")
    spread = float(context.get("spread_bps", 0) or 0)
    slip = float(context.get("expected_slippage_bps", 0) or 0)
    if spread > MAX_SPREAD_BPS: reasons.append("spread too wide")
    if slip > MAX_SLIPPAGE_BPS: reasons.append("expected slippage too high")
    if not bool(context.get("risk_ok", False)): reasons.append("risk firewall rejected candidate")
    adversarial = _clamp(context.get("adversarial_score", 0))
    if adversarial < 0.0: reasons.append("adversarial review found a strong failure case")
    if not bool(context.get("execution_ok", False)): reasons.append("execution-quality gate failed")
    decision = "TRADE" if not reasons else "NO_TRADE"
    return CommitteeDecision(decision, direction, round(score, 6), round(agreement, 6), round(history_edge, 6), tuple(reasons), tuple(votes), liquidity, expiry)


def decision_dict(result: CommitteeDecision) -> dict[str, Any]:
    return {"decision": result.decision, "direction": result.direction, "direction_label": "LONG" if result.direction > 0 else "SHORT" if result.direction < 0 else "NONE", "score": result.score, "agreement": result.agreement, "historical_edge": result.edge, "reasons": list(result.reasons), "votes": [{"model": v.model, "direction": v.direction, "strength": round(v.strength, 6), "reason": v.reason} for v in result.votes], "liquidity": result.liquidity, "expiry": result.expiry, "live_execution": False}
