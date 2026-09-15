from __future__ import annotations

"""Deterministic research layer inspired by mature open-source trading systems.

This module deliberately implements algorithms locally instead of importing trading
framework code. It is dependency-light, reproducible and fail-closed. LLMs may
consume its outputs, but cannot bypass its validation or risk gates.
"""

from dataclasses import dataclass, asdict
from math import isfinite, sqrt
from statistics import mean, median
from typing import Any, Iterable, Sequence
import random


EPS = 1e-12


def _f(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        return v if isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _clamp(x: Any, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, _f(x)))


def _returns(values: Sequence[float]) -> list[float]:
    out: list[float] = []
    for a, b in zip(values, values[1:]):
        a, b = _f(a), _f(b)
        if a > 0 and b > 0:
            out.append(b / a - 1.0)
    return out


def _trade_returns(trades: Iterable[Any]) -> list[float]:
    out: list[float] = []
    for t in trades:
        if isinstance(t, dict):
            if t.get("return_pct") is not None:
                out.append(_f(t["return_pct"]) / (100.0 if abs(_f(t["return_pct"])) > 2 else 1.0))
            elif t.get("pnl_pct") is not None:
                out.append(_f(t["pnl_pct"]) / (100.0 if abs(_f(t["pnl_pct"])) > 2 else 1.0))
            elif t.get("realized_pnl") is not None:
                pnl, entry = _f(t["realized_pnl"]), abs(_f(t.get("entry_price"))) * abs(_f(t.get("quantity")))
                if entry > EPS:
                    out.append(pnl / entry)
        else:
            out.append(_f(t))
    return out


def performance_metrics(returns: Sequence[float], periods_per_year: float = 365.0) -> dict[str, float]:
    r = [x for x in (_f(v) for v in returns) if isfinite(x)]
    if not r:
        return {"samples": 0, "expectancy": 0.0, "win_rate": 0.0, "profit_factor": 0.0, "sharpe": 0.0, "sortino": 0.0, "max_drawdown": 0.0, "total_return": 0.0}
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    gains = sum(x for x in r if x > 0)
    losses = sum(-x for x in r if x < 0)
    downside = [x for x in r if x < 0]
    for x in r:
        equity *= 1.0 + x
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / max(peak, EPS))
    avg = mean(r)
    sd = sqrt(mean((x - avg) ** 2 for x in r)) if len(r) > 1 else 0.0
    dsd = sqrt(mean(x * x for x in downside)) if downside else 0.0
    return {
        "samples": len(r), "expectancy": avg, "win_rate": sum(x > 0 for x in r) / len(r),
        "profit_factor": gains / losses if losses > EPS else (999.0 if gains > 0 else 0.0),
        "sharpe": avg / sd * sqrt(periods_per_year) if sd > EPS else 0.0,
        "sortino": avg / dsd * sqrt(periods_per_year) if dsd > EPS else 0.0,
        "max_drawdown": max_dd, "total_return": equity - 1.0,
    }


def rule_significance(signal_returns: Sequence[float], random_returns: Sequence[float] | None = None, iterations: int = 2000, seed: int = 42) -> dict[str, Any]:
    """Bootstrap a signal mean against a matched random-entry baseline.

    The result is deliberately conservative: small samples never become a
    statistically significant positive edge, even if their mean is high.
    """
    observed = [_f(x) for x in signal_returns if isfinite(_f(x))]
    baseline = [_f(x) for x in (random_returns or []) if isfinite(_f(x))]
    if len(observed) < 30:
        return {"usable": False, "significant": False, "sample_count": len(observed), "p_value": 1.0, "effect_size": 0.0, "reason": f"insufficient significance sample ({len(observed)}/30)"}
    if not baseline:
        baseline = observed
    rng = random.Random(seed)
    observed_mean = mean(observed)
    baseline_mean = mean(baseline)
    effect = observed_mean - baseline_mean
    pool = baseline
    exceed = 0
    for _ in range(max(200, iterations)):
        sample = [pool[rng.randrange(len(pool))] for _ in observed]
        if mean(sample) - baseline_mean >= effect:
            exceed += 1
    p = (exceed + 1) / (max(200, iterations) + 1)
    return {"usable": True, "significant": bool(effect > 0 and p < 0.05), "sample_count": len(observed), "p_value": round(p, 6), "effect_size": round(effect, 8), "signal_mean": observed_mean, "baseline_mean": baseline_mean, "confidence": round(1.0 - p, 6), "reason": "positive edge statistically significant" if effect > 0 and p < 0.05 else "edge not statistically significant"}


def monte_carlo_robustness(returns: Sequence[float], iterations: int = 1000, seed: int = 42) -> dict[str, Any]:
    """Stress-test trade ordering and return sampling without future leakage."""
    r = [_f(x) for x in returns if isfinite(_f(x))]
    if len(r) < 30:
        return {"usable": False, "iterations": 0, "reason": f"insufficient Monte Carlo sample ({len(r)}/30)"}
    rng = random.Random(seed)
    totals: list[float] = []
    dds: list[float] = []
    for _ in range(max(200, iterations)):
        sample = list(r)
        rng.shuffle(sample)
        equity, peak, dd = 1.0, 1.0, 0.0
        for x in sample:
            equity *= max(EPS, 1.0 + x)
            peak = max(peak, equity)
            dd = max(dd, (peak - equity) / max(peak, EPS))
        totals.append(equity - 1.0)
        dds.append(dd)
    totals.sort(); dds.sort()
    q = lambda xs, p: xs[min(len(xs) - 1, max(0, int((len(xs) - 1) * p)))]
    return {"usable": True, "iterations": len(totals), "median_return": q(totals, .5), "p05_return": q(totals, .05), "p95_return": q(totals, .95), "p95_max_drawdown": q(dds, .95), "probability_loss": sum(x < 0 for x in totals) / len(totals), "robust": q(totals, .05) >= 0 and q(dds, .95) <= 0.20}


def walk_forward_splits(n: int, train_size: int = 200, test_size: int = 50, step: int | None = None) -> list[dict[str, int]]:
    if n <= 0 or train_size <= 0 or test_size <= 0:
        return []
    step = step or test_size
    out: list[dict[str, int]] = []
    start = 0
    while start + train_size + test_size <= n:
        out.append({"train_start": start, "train_end": start + train_size, "test_start": start + train_size, "test_end": start + train_size + test_size})
        start += step
    return out


def walk_forward_validate(returns: Sequence[float], train_size: int = 200, test_size: int = 50, step: int | None = None) -> dict[str, Any]:
    r = [_f(x) for x in returns]
    splits = walk_forward_splits(len(r), train_size, test_size, step)
    if not splits:
        return {"usable": False, "splits": [], "reason": "insufficient data for walk-forward validation"}
    rows = []
    for s in splits:
        train = performance_metrics(r[s["train_start"]:s["train_end"]])
        test = performance_metrics(r[s["test_start"]:s["test_end"]])
        rows.append({"split": s, "train": train, "test": test})
    oos = [x["test"]["expectancy"] for x in rows]
    return {"usable": True, "splits": rows, "oos_expectancy": mean(oos), "oos_positive_split_rate": sum(x > 0 for x in oos) / len(oos), "stable": sum(x > 0 for x in oos) / len(oos) >= 0.60}


def calibration_report(probabilities: Sequence[float], outcomes: Sequence[int | bool], bins: int = 10) -> dict[str, Any]:
    if len(probabilities) != len(outcomes) or len(probabilities) < 30:
        return {"usable": False, "brier": 1.0, "ece": 1.0, "samples": len(probabilities), "reason": "insufficient calibration sample"}
    rows = []
    brier = 0.0
    for p, y in zip(probabilities, outcomes):
        p = _clamp(p); y = 1.0 if bool(y) else 0.0; brier += (p - y) ** 2
    ece = 0.0
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        idx = [j for j, p in enumerate(probabilities) if lo <= _clamp(p) < hi or (i == bins - 1 and _clamp(p) == hi)]
        if idx:
            conf = mean(_clamp(probabilities[j]) for j in idx); acc = mean(1.0 if bool(outcomes[j]) else 0.0 for j in idx)
            gap = abs(conf - acc); ece += len(idx) / len(probabilities) * gap
            rows.append({"bin": i, "count": len(idx), "confidence": conf, "accuracy": acc, "gap": gap})
    return {"usable": True, "brier": brier / len(probabilities), "ece": ece, "samples": len(probabilities), "bins": rows, "calibrated": ece <= 0.10}


def reliability_weight(metrics: dict[str, Any]) -> float:
    """Turn out-of-sample quality into a bounded committee weight."""
    accuracy = _clamp(metrics.get("accuracy", metrics.get("win_rate", 0.5)))
    calibration = _clamp(1.0 - _f(metrics.get("ece", 0.5)), 0.0, 1.0)
    stability = _clamp(metrics.get("stability", metrics.get("oos_positive_split_rate", 0.5)))
    sample = min(1.0, _f(metrics.get("samples", metrics.get("sample_count", 0))) / 200.0)
    return round(max(0.10, min(1.50, (0.45 * accuracy + 0.30 * calibration + 0.25 * stability) * (0.5 + 0.5 * sample))), 6)


def reliability_weighted_consensus(votes: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not votes:
        return {"direction": 0, "score": 0.0, "agreement": 0.0, "weights": []}
    weighted = 0.0; total = 0.0; aligned = 0.0
    details = []
    for v in votes:
        direction = 1 if _f(v.get("direction")) > 0 else -1 if _f(v.get("direction")) < 0 else 0
        strength = _clamp(v.get("strength", 0.0))
        weight = _f(v.get("weight"), reliability_weight(v.get("validation", {})))
        weighted += direction * strength * weight; total += weight
        if direction: aligned += weight
        details.append({"model": v.get("model", "unknown"), "direction": direction, "strength": strength, "weight": weight})
    raw = weighted / max(total, EPS)
    return {"direction": 1 if raw > 0 else -1 if raw < 0 else 0, "score": round(abs(raw), 6), "agreement": round(aligned / max(total, EPS), 6), "weights": details}


def lookahead_audit(feature_names: Iterable[str], future_terms: Iterable[str] | None = None) -> dict[str, Any]:
    terms = {str(x).lower() for x in (future_terms or ("future", "next_close", "next_return", "forward_return", "target", "future_high", "future_low", "lookahead"))}
    bad = []
    for name in feature_names:
        low = str(name).lower()
        if any(term in low for term in terms):
            bad.append(str(name))
    return {"passed": not bad, "suspect_features": bad, "checked": len(list(feature_names)) if not isinstance(feature_names, list) else len(feature_names), "reason": "lookahead terms detected" if bad else "no obvious future-data feature names detected"}


def recursive_stability(values_by_history: Sequence[Sequence[float]], tolerance: float = 0.02) -> dict[str, Any]:
    if len(values_by_history) < 2:
        return {"passed": False, "reason": "need at least two history windows"}
    last = [_f(x) for x in values_by_history[-1]]
    diffs = []
    for row in values_by_history[:-1]:
        cur = [_f(x) for x in row]
        if cur and last:
            m = min(len(cur), len(last)); diffs.append(mean(abs(cur[i] - last[i]) / max(abs(last[i]), EPS) for i in range(m)))
    drift = mean(diffs) if diffs else 1.0
    return {"passed": drift <= tolerance, "mean_relative_drift": drift, "tolerance": tolerance}


@dataclass(frozen=True)
class Fill:
    status: str
    filled_quantity: float
    fill_price: float
    fee: float
    slippage: float
    reason: str


def simulate_fill(*, side: str, quantity: float, bid: float, ask: float, depth: float, max_slippage_bps: float = 20.0, latency_bps: float = 0.0, fee_rate: float = 0.0005) -> Fill:
    side = str(side).upper(); quantity = max(0.0, _f(quantity)); bid, ask, depth = _f(bid), _f(ask), max(0.0, _f(depth))
    if side not in {"BUY", "SELL", "LONG", "SHORT"} or quantity <= 0 or bid <= 0 or ask <= 0 or ask < bid:
        return Fill("REJECTED", 0.0, 0.0, 0.0, 0.0, "invalid market or order")
    px = ask if side in {"BUY", "LONG"} else bid
    spread_bps = (ask - bid) / max((ask + bid) / 2, EPS) * 10000
    impact_bps = min(max_slippage_bps * 2, quantity / max(depth, EPS) * 10000)
    total_slip_bps = spread_bps / 2 + impact_bps + max(0.0, latency_bps)
    if total_slip_bps > max_slippage_bps:
        return Fill("REJECTED", 0.0, 0.0, 0.0, total_slip_bps, "slippage budget exceeded")
    fill_price = px * (1.0 + (total_slip_bps / 10000) * (1 if side in {"BUY", "LONG"} else -1))
    fee = fill_price * quantity * fee_rate
    return Fill("FILLED" if quantity <= depth else "PARTIAL", min(quantity, depth), fill_price, fee, fill_price * min(quantity, depth) * total_slip_bps / 10000, "simulated order-book fill")


def triple_barrier(*, side: str, entry: float, stop: float, targets: Sequence[float], high: float, low: float, age_bars: int, max_bars: int) -> dict[str, Any]:
    side = str(side).upper(); entry, stop, high, low = map(_f, (entry, stop, high, low))
    targets = [_f(x) for x in targets]
    if side in {"BUY", "LONG"}:
        if low <= stop: return {"exit": "STOP_LOSS", "price": stop, "barrier": "stop"}
        for i, target in enumerate(targets, 1):
            if high >= target: return {"exit": f"TAKE_PROFIT_{i}", "price": target, "barrier": "target"}
    else:
        if high >= stop: return {"exit": "STOP_LOSS", "price": stop, "barrier": "stop"}
        for i, target in enumerate(targets, 1):
            if low <= target: return {"exit": f"TAKE_PROFIT_{i}", "price": target, "barrier": "target"}
    if age_bars >= max_bars: return {"exit": "TIME_LIMIT", "price": entry, "barrier": "time"}
    return {"exit": "OPEN", "price": None, "barrier": None}


def stat_arb_signal(leg_a: Sequence[float], leg_b: Sequence[float], entry_z: float = 2.0, exit_z: float = 0.5) -> dict[str, Any]:
    if len(leg_a) != len(leg_b) or len(leg_a) < 30:
        return {"usable": False, "zscore": 0.0, "signal": "NO_TRADE", "reason": "insufficient paired history"}
    spread = [_f(a) - _f(b) for a, b in zip(leg_a, leg_b)]
    mu = mean(spread); sd = sqrt(mean((x - mu) ** 2 for x in spread))
    z = (spread[-1] - mu) / max(sd, EPS)
    signal = "SHORT_SPREAD" if z >= entry_z else "LONG_SPREAD" if z <= -entry_z else "EXIT" if abs(z) <= exit_z else "HOLD"
    return {"usable": True, "zscore": z, "signal": signal, "mean": mu, "std": sd}


def funding_basis_signal(funding_rate: float, basis_pct: float, funding_threshold: float = 0.0005, basis_threshold: float = 0.10) -> dict[str, Any]:
    funding, basis = _f(funding_rate), _f(basis_pct)
    if funding > funding_threshold and basis > basis_threshold: signal = "SHORT_BIAS"
    elif funding < -funding_threshold and basis < -basis_threshold: signal = "LONG_BIAS"
    else: signal = "NEUTRAL"
    return {"signal": signal, "funding_rate": funding, "basis_pct": basis}


def strategy_experiment(variants: dict[str, Sequence[float]]) -> dict[str, Any]:
    rows = []
    for name, returns in variants.items():
        m = performance_metrics(returns)
        score = m["expectancy"] * (1.0 + max(0.0, m["sharpe"])) / max(1.0 + 5.0 * m["max_drawdown"], 1.0)
        rows.append({"variant": name, **m, "risk_adjusted_score": score})
    rows.sort(key=lambda x: x["risk_adjusted_score"], reverse=True)
    return {"variants": rows, "winner": rows[0]["variant"] if rows else None, "selection_rule": "risk-adjusted out-of-sample evidence, not raw return"}


def drl_research_adapter(observation: dict[str, Any], action_space: Sequence[str] = ("SHORT", "FLAT", "LONG")) -> dict[str, Any]:
    """Safe DRL interface: returns a research action only, never an order.

    A future trained policy can replace this deterministic baseline without
    changing the committee contract.
    """
    score = _f(observation.get("signal_score")) + 0.25 * _f(observation.get("regime_bias"))
    action = "LONG" if score > 0.5 else "SHORT" if score < -0.5 else "FLAT"
    if action not in action_space: action = "FLAT"
    return {"action": action, "research_only": True, "confidence": min(1.0, abs(score) / 2.0), "live_execution": False}


def build_research_intelligence(*, market_data: dict[str, Any], market_summary: dict[str, Any], trades: Sequence[dict[str, Any]] | None = None, feature_names: Sequence[str] | None = None, probabilities: Sequence[float] | None = None, outcomes: Sequence[int | bool] | None = None, strategy_variants: dict[str, Sequence[float]] | None = None) -> dict[str, Any]:
    """Build the research gates consumed by the command center."""
    trades = list(trades or [])
    trade_returns = _trade_returns(trades)
    metrics = performance_metrics(trade_returns)
    significance = rule_significance(trade_returns)
    monte_carlo = monte_carlo_robustness(trade_returns)
    walk = walk_forward_validate(trade_returns)
    calibration = calibration_report(probabilities or [], outcomes or []) if probabilities is not None and outcomes is not None else {"usable": False, "reason": "no probability/outcome dataset supplied"}
    audit = lookahead_audit(feature_names or [])
    variants = strategy_experiment(strategy_variants) if strategy_variants else {"variants": [], "winner": None, "selection_rule": "risk-adjusted out-of-sample evidence, not raw return"}
    gates = {
        "lookahead": audit.get("passed", False),
        "significance": significance.get("significant", False),
        "walk_forward": walk.get("stable", False),
        "monte_carlo": monte_carlo.get("robust", False),
        "calibration": calibration.get("calibrated", False) if calibration.get("usable") else False,
    }
    # No historical dataset means research cannot certify a live decision.
    research_ready = all(gates.values()) if trade_returns else False
    return {
        "version": "research-v2",
        "research_ready": research_ready,
        "gates": gates,
        "performance": metrics,
        "rule_significance": significance,
        "monte_carlo": monte_carlo,
        "walk_forward": walk,
        "calibration": calibration,
        "lookahead_audit": audit,
        "strategy_experiments": variants,
        "execution_model": {"event_driven": True, "order_book": True, "partial_fills": True, "latency": True, "fees": True, "slippage": True},
        "triple_barrier": {"enabled": True, "take_profit": True, "stop_loss": True, "time_limit": True},
        "stat_arb": {"enabled": True, "live_execution": False},
        "funding_basis": {"enabled": True, "live_execution": False},
        "drl": {"enabled": True, "research_only": True, "live_execution": False},
        "cross_exchange": {"enabled": True, "normalized": True, "live_execution": False},
        "specialist_agents": ["trend", "momentum", "breakout", "mean_reversion", "volatility", "liquidity", "funding", "basis", "derivatives", "macro", "news", "historical_edge", "ml_probability", "execution", "risk"],
        "llm_boundary": "LLM proposes and explains; deterministic research/risk/execution gates decide",
    }
