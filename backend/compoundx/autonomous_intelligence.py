from __future__ import annotations

"""CompoundX autonomous decision intelligence.

This module is intentionally deterministic and fail-closed.  It turns raw
market observations into structured evidence, competing setup hypotheses,
stress tests, calibrated probabilities and a final autonomy gate.  Optional
feeds (order flow, liquidations, options, cross-asset, on-chain and news) are
represented explicitly as evidence; missing evidence never becomes a fake
positive signal.
"""

from dataclasses import dataclass
from math import exp, isfinite, log, sqrt
from statistics import mean, median
from typing import Any, Iterable

TIMEFRAMES = ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w")
STRATEGIES = (
    "trend_following", "breakout", "mean_reversion", "momentum",
    "volatility_expansion", "volatility_contraction", "liquidity_sweep_reversal",
    "funding_reversal", "oi_divergence", "event_driven",
)


def _f(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        return v if isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _clamp(x: Any, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, _f(x)))


def _direction(x: Any) -> int:
    v = _f(x)
    return 1 if v > 0 else -1 if v < 0 else 0


def _available(d: Any, keys: Iterable[str]) -> bool:
    return isinstance(d, dict) and any(k in d and d[k] is not None for k in keys)


def data_quality_guard(market_data: dict[str, Any], required_timeframes: int = 3) -> dict[str, Any]:
    usable = 0
    issues: list[str] = []
    freshness: list[float] = []
    for tf, payload in (market_data or {}).items():
        candles = payload.get("ohlcv") if isinstance(payload, dict) else None
        if not isinstance(candles, list) or len(candles) < 50:
            continue
        usable += 1
        last = candles[-1]
        if isinstance(last, (list, tuple)) and len(last) >= 6:
            ts = _f(last[0])
            if ts > 1e11:
                ts /= 1000
            freshness.append(ts)
        for row in candles[-10:]:
            if not isinstance(row, (list, tuple)) or len(row) < 6:
                issues.append(f"{tf}: malformed candle")
                continue
            o, h, l, c = map(_f, row[1:5])
            if min(o, h, l, c) <= 0 or h < max(o, c) or l > min(o, c):
                issues.append(f"{tf}: invalid OHLC")
    if usable < required_timeframes:
        issues.append(f"insufficient clean timeframes ({usable}/{required_timeframes})")
    return {"usable": not issues, "usable_timeframes": usable, "issues": list(dict.fromkeys(issues)), "latest_timestamps": freshness[-5:]}


def regime_switching_engine(tf_results: dict[str, Any]) -> dict[str, Any]:
    rows = [v for v in tf_results.values() if isinstance(v, dict) and v.get("usable")]
    if not rows:
        return {"regime": "UNKNOWN", "confidence": 0.0, "transition": True, "eligible_strategies": [], "reason": "no usable timeframe evidence"}
    regimes = [str(v.get("regime", "UNKNOWN")) for v in rows]
    counts = {r: regimes.count(r) for r in set(regimes)}
    regime = max(counts, key=counts.get)
    transition = sum(r in {"TRANSITION", "HIGH_VOLATILITY"} for r in regimes) / len(regimes) >= 0.35
    mapping = {
        "TREND_UP": ["trend_following", "momentum", "breakout"],
        "TREND_DOWN": ["trend_following", "momentum", "breakout"],
        "RANGE": ["mean_reversion", "liquidity_sweep_reversal", "volatility_contraction"],
        "ACCUMULATION_DISTRIBUTION": ["mean_reversion", "breakout"],
        "BREAKOUT_ATTEMPT": ["breakout", "momentum", "volatility_expansion"],
        "HIGH_VOLATILITY": ["volatility_expansion", "liquidity_sweep_reversal"],
        "TRANSITION": ["mean_reversion", "liquidity_sweep_reversal"],
    }
    return {"regime": regime, "confidence": round(counts[regime] / len(rows), 4), "transition": transition, "eligible_strategies": mapping.get(regime, []), "distribution": counts}


def structure_engine(tf_results: dict[str, Any]) -> dict[str, Any]:
    rows = [v for v in tf_results.values() if isinstance(v, dict) and v.get("usable")]
    if not rows:
        return {"usable": False, "bias": 0, "quality": 0.0, "signals": []}
    bias = sum(_direction(v.get("direction")) for v in rows)
    upper = sum(v.get("structure") == "UPPER_RANGE" for v in rows)
    lower = sum(v.get("structure") == "LOWER_RANGE" for v in rows)
    signals: list[str] = []
    if upper and lower:
        signals.append("multi-timeframe structure conflict")
    if upper >= max(2, len(rows) // 2): signals.append("price positioned in upper ranges")
    if lower >= max(2, len(rows) // 2): signals.append("price positioned in lower ranges")
    return {"usable": True, "bias": bias, "quality": round(abs(bias) / max(1, len(rows)), 4), "signals": signals, "upper_count": upper, "lower_count": lower}


def order_flow_intelligence(order_flow: dict[str, Any] | None) -> dict[str, Any]:
    d = order_flow or {}
    if not _available(d, ("delta", "cvd", "taker_buy_ratio", "aggressive_buy_volume", "aggressive_sell_volume")):
        return {"available": False, "usable": False, "bias": 0.0, "reason": "order-flow evidence unavailable"}
    buy = _f(d.get("aggressive_buy_volume"))
    sell = _f(d.get("aggressive_sell_volume"))
    delta = _f(d.get("delta"), buy - sell)
    total = max(1e-12, buy + sell)
    bias = _clamp((delta / total + 1) / 2) * 2 - 1 if buy or sell else _clamp(d.get("taker_buy_ratio", 0.5)) * 2 - 1
    absorption = bool(d.get("absorption", False))
    return {"available": True, "usable": True, "bias": round(bias, 4), "delta": delta, "cvd": _f(d.get("cvd")), "taker_buy_ratio": _f(d.get("taker_buy_ratio", 0.5)), "absorption": absorption, "spoofing_anomaly": bool(d.get("spoofing_anomaly", False)), "reason": "order flow analyzed"}


def liquidation_intelligence(liquidations: dict[str, Any] | None, price: float = 0.0) -> dict[str, Any]:
    d = liquidations or {}
    if not _available(d, ("long_clusters", "short_clusters", "long_liquidations", "short_liquidations", "intensity")):
        return {"available": False, "usable": False, "bias": 0.0, "reason": "liquidation evidence unavailable"}
    longs = _f(d.get("long_liquidations"))
    shorts = _f(d.get("short_liquidations"))
    bias = (shorts - longs) / max(1e-12, shorts + longs)
    clusters = d.get("long_clusters", []) + d.get("short_clusters", []) if isinstance(d.get("long_clusters", []), list) and isinstance(d.get("short_clusters", []), list) else []
    nearest = min((abs(_f(c.get("price")) - price) / max(1e-12, price) for c in clusters if isinstance(c, dict) and _f(c.get("price")) > 0), default=None)
    return {"available": True, "usable": True, "bias": round(bias, 4), "long_liquidations": longs, "short_liquidations": shorts, "intensity": _f(d.get("intensity")), "nearest_cluster_pct": nearest, "cascade_risk": _clamp(d.get("intensity")) > 0.8}


def derivatives_brain(derivatives: dict[str, Any] | None) -> dict[str, Any]:
    d = derivatives or {}
    available = _available(d, ("funding_rate", "open_interest", "open_interest_change_pct", "basis_pct"))
    if not available:
        return {"available": False, "usable": False, "bias": 0.0, "crowding": "unknown", "reason": "derivatives evidence unavailable"}
    funding = _f(d.get("funding_rate"))
    oi_change = _f(d.get("open_interest_change_pct"))
    basis = _f(d.get("basis_pct"))
    crowding = "crowded_long" if funding > 0.0005 and oi_change > 0 else "crowded_short" if funding < -0.0005 and oi_change > 0 else "mixed"
    divergence = "price_up_oi_down" if d.get("price_change_pct", 0) > 0 and oi_change < 0 else "price_down_oi_down" if d.get("price_change_pct", 0) < 0 and oi_change < 0 else "aligned"
    bias = -0.5 if crowding == "crowded_long" else 0.5 if crowding == "crowded_short" else 0.0
    return {"available": True, "usable": True, "funding_rate": funding, "oi_change_pct": oi_change, "basis_pct": basis, "crowding": crowding, "divergence": divergence, "bias": bias, "liquidation_24h": _f(d.get("liquidations_24h"))}


def options_expiry_brain(expiry: dict[str, Any] | None, spot: float = 0.0) -> dict[str, Any]:
    d = expiry or {}
    instruments = d.get("instruments") if isinstance(d, dict) else None
    if not isinstance(instruments, list) or not instruments:
        status = str(d.get("status", "NOT_APPLICABLE")) if isinstance(d, dict) else "UNKNOWN"
        return {"available": status == "NOT_APPLICABLE", "usable": status == "NOT_APPLICABLE", "status": status, "major_strikes": [], "reason": "expiry/options evidence unavailable" if status != "NOT_APPLICABLE" else "no expiry required"}
    strikes: list[dict[str, Any]] = []
    for item in instruments:
        if not isinstance(item, dict): continue
        strike = _f(item.get("strike"))
        if strike <= 0: continue
        strikes.append({"strike": strike, "oi": _f(item.get("open_interest")), "volume": _f(item.get("volume")), "option_type": item.get("optionType", item.get("option_type"))})
    top = sorted(strikes, key=lambda x: x["oi"] + 0.1 * x["volume"], reverse=True)[:10]
    return {"available": True, "usable": bool(d.get("usable", True)), "status": d.get("status", "AVAILABLE"), "major_strikes": top, "skew": _f(d.get("skew")), "iv": _f(d.get("iv")), "pcr": _f(d.get("pcr")), "gamma_exposure": _f(d.get("gamma_exposure")), "expiry_countdown_hours": _f(d.get("expiry_countdown_hours"))}


def cross_asset_intelligence(cross_asset: dict[str, Any] | None, symbol: str = "BTC/USDT") -> dict[str, Any]:
    d = cross_asset or {}
    if not d:
        return {"available": False, "usable": False, "bias": 0.0, "conflicts": ["cross-asset evidence unavailable"]}
    risk = 0.0
    conflicts: list[str] = []
    for key, weight in (("dxy_change_pct", -0.25), ("nasdaq_change_pct", 0.25), ("spx_change_pct", 0.15), ("vix_change_pct", -0.15), ("us10y_change_bps", -0.08)):
        risk += _f(d.get(key)) * weight
    if _f(d.get("dxy_change_pct")) > 0.5 and _f(d.get("nasdaq_change_pct")) < -0.5:
        conflicts.append("macro risk-off cross-asset alignment")
    return {"available": True, "usable": True, "bias": round(max(-1.0, min(1.0, risk / 2)), 4), "conflicts": conflicts, "inputs": d}


def anomaly_detector(features: dict[str, Any] | None) -> dict[str, Any]:
    d = features or {}
    metrics = [
        _f(d.get("volume_z")), _f(d.get("volatility_z")), _f(d.get("spread_z")),
        _f(d.get("oi_z")), _f(d.get("funding_z")), _f(d.get("correlation_break_z")),
        _f(d.get("news_velocity_z")), _f(d.get("social_velocity_z")),
    ]
    extreme = max((abs(x) for x in metrics), default=0.0)
    return {"available": bool(d), "anomalous": extreme >= 3.0, "severity": round(min(1.0, extreme / 6.0), 4), "max_z": extreme, "reason": "extreme market anomaly" if extreme >= 3.0 else "no extreme anomaly detected"}


def setup_hypotheses(mtf: dict[str, Any], regime: dict[str, Any], structure: dict[str, Any], derivatives: dict[str, Any], liquidity: dict[str, Any]) -> list[dict[str, Any]]:
    direction = _direction(1 if mtf.get("direction") == "LONG" else -1 if mtf.get("direction") == "SHORT" else 0)
    out: list[dict[str, Any]] = []
    if direction:
        out.append({"name": "continuation", "direction": direction, "prior": _clamp(mtf.get("consensus"))})
        out.append({"name": "breakout", "direction": direction, "prior": 0.55 if regime.get("regime") in {"BREAKOUT_ATTEMPT", "TREND_UP", "TREND_DOWN"} else 0.25})
        out.append({"name": "reversal", "direction": -direction, "prior": 0.45 if structure.get("signals") else 0.20})
    out.append({"name": "no_trade", "direction": 0, "prior": 0.35 + (0.25 if regime.get("transition") else 0)})
    if derivatives.get("crowding") in {"crowded_long", "crowded_short"}:
        out.append({"name": "crowding_reversal", "direction": -1 if derivatives.get("crowding") == "crowded_long" else 1, "prior": 0.5})
    return sorted(out, key=lambda x: x["prior"], reverse=True)


def historical_twin(history: dict[str, Any] | None, fingerprint: dict[str, Any]) -> dict[str, Any]:
    d = history or {}
    n = int(_f(d.get("count")))
    if n < 20:
        return {"available": False, "usable": False, "sample_count": n, "similarity": 0.0, "reason": f"insufficient comparable history ({n}/20)"}
    similarity = _clamp(d.get("similarity", d.get("similarity_score", 0.0)))
    return {"available": True, "usable": similarity >= 0.65, "sample_count": n, "similarity": similarity, "win_rate": _clamp(d.get("win_rate")), "expectancy": _f(d.get("expectancy")), "median_time_to_target_hours": _f(d.get("median_time_to_target_hours")), "fingerprint": fingerprint}


def probability_calibration(predicted: float, calibration: dict[str, Any] | None) -> dict[str, Any]:
    p = _clamp(predicted)
    d = calibration or {}
    n = int(_f(d.get("sample_count")))
    observed = _clamp(d.get("observed_rate"))
    if n < 30:
        return {"usable": False, "probability": p, "sample_count": n, "brier": _f(d.get("brier")), "ece": _f(d.get("ece")), "reason": "probability calibration requires >=30 observations"}
    adjusted = _clamp(0.5 * p + 0.5 * observed)
    return {"usable": True, "probability": adjusted, "sample_count": n, "brier": _f(d.get("brier")), "ece": _f(d.get("ece")), "reason": "calibrated against observed outcomes"}


def meta_labeling(primary_probability: float, features: dict[str, Any]) -> dict[str, Any]:
    p = _clamp(primary_probability)
    penalty = 0.0
    if features.get("anomalous"): penalty += 0.15
    if features.get("mtf_conflict"): penalty += 0.15
    if features.get("macro_blocked"): penalty += 0.50
    if features.get("execution_bad"): penalty += 0.20
    score = _clamp(p - penalty)
    return {"tradeability": score >= 0.70, "score": round(score, 4), "penalty": round(penalty, 4)}


def expected_value(probability: float, avg_win: float, avg_loss: float, costs: float = 0.0, stress_multiplier: float = 1.0) -> dict[str, Any]:
    p = _clamp(probability)
    win, loss, c = max(0.0, _f(avg_win)), max(0.0, _f(avg_loss)), max(0.0, _f(costs))
    ev = p * win - (1 - p) * loss - c
    stress_loss = loss * max(1.0, stress_multiplier)
    stress_ev = p * win - (1 - p) * stress_loss - c
    return {"ev": ev, "stress_ev": stress_ev, "positive": ev > 0, "stress_positive": stress_ev > 0, "breakeven_probability": (loss + c) / max(1e-12, win + loss)}


def dynamic_trade_plan(price: float, atr_value: float, direction: int, support: float = 0.0, resistance: float = 0.0, rr: float = 2.0) -> dict[str, Any]:
    p, a = _f(price), max(0.0, _f(atr_value))
    if p <= 0 or a <= 0 or direction == 0:
        return {"usable": False, "reason": "price/ATR unavailable"}
    stop = p - 1.25 * a if direction > 0 else p + 1.25 * a
    if direction > 0 and support > 0: stop = min(stop, support * 0.998)
    if direction < 0 and resistance > 0: stop = max(stop, resistance * 1.002)
    distance = abs(p - stop)
    target = p + rr * distance if direction > 0 else p - rr * distance
    return {"usable": True, "entry": p, "stop": stop, "target": target, "rr": rr, "stop_distance_pct": distance / p}


def counterfactual_stress(plan: dict[str, Any], probability: float, slippage_bps: float, macro_blocked: bool = False) -> dict[str, Any]:
    if not plan.get("usable"):
        return {"passed": False, "scenarios": [], "reason": "trade plan unavailable"}
    p = _clamp(probability)
    base = _f(plan.get("target")) - _f(plan.get("entry"))
    if _f(plan.get("entry")) > _f(plan.get("target")): base = abs(base)
    scenarios = [
        ("base", p, 1.0), ("slippage_2x", p - 0.04, 1.0),
        ("volatility_shock", p - 0.08, 1.25), ("execution_depth_loss", p - 0.10, 1.35),
    ]
    results = [{"name": n, "probability": _clamp(prob), "risk_multiplier": m, "survives": _clamp(prob) >= 0.65 and base > 0 and slippage_bps <= 40 * m} for n, prob, m in scenarios]
    if macro_blocked: results.append({"name": "macro_event", "probability": 0.0, "risk_multiplier": 2.0, "survives": False})
    return {"passed": all(r["survives"] for r in results), "scenarios": results, "reason": "all stress scenarios survived" if all(r["survives"] for r in results) else "fragile under stress"}


def decision_stability(probability: float, perturbations: Iterable[float] = (-0.02, -0.01, 0.01, 0.02)) -> dict[str, Any]:
    p = _clamp(probability)
    decisions = [_clamp(p + delta) >= 0.70 for delta in perturbations]
    stable = all(x == decisions[0] for x in decisions)
    return {"stable": stable, "base": p >= 0.70, "perturbations": list(perturbations), "decisions": decisions}


def strategy_selector(regime: dict[str, Any], strategy_stats: dict[str, Any] | None = None) -> dict[str, Any]:
    stats = strategy_stats or {}
    eligible = regime.get("eligible_strategies") or []
    ranked = []
    for name in eligible:
        row = stats.get(name, {}) if isinstance(stats, dict) else {}
        if row.get("disabled"):
            continue
        expectancy = _f(row.get("expectancy"))
        pf = _f(row.get("profit_factor"))
        ranked.append({"strategy": name, "expectancy": expectancy, "profit_factor": pf, "score": expectancy + min(3.0, pf) * 0.1})
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return {"eligible": eligible, "ranked": ranked, "selected": ranked[0]["strategy"] if ranked else None}


def strategy_kill_switch(strategy_stats: dict[str, Any] | None) -> dict[str, Any]:
    disabled: list[str] = []
    reasons: dict[str, str] = {}
    for name, row in (strategy_stats or {}).items():
        if not isinstance(row, dict): continue
        if _f(row.get("sample_count")) >= 30 and (_f(row.get("expectancy")) <= 0 or _f(row.get("profit_factor")) < 1.0 or _f(row.get("max_drawdown")) > _f(row.get("max_drawdown_limit", 0.25))):
            disabled.append(name); reasons[name] = "validated performance degradation"
    return {"disabled": disabled, "reasons": reasons}


def portfolio_guard(positions: list[dict[str, Any]] | None, candidate: dict[str, Any] | None) -> dict[str, Any]:
    rows = positions or []
    cand = candidate or {}
    current = sum(abs(_f(x.get("notional"))) for x in rows)
    candidate_notional = abs(_f(cand.get("notional")))
    symbols = [str(x.get("symbol")) for x in rows]
    concentration = (candidate_notional / max(1e-12, current + candidate_notional)) if candidate_notional else 0.0
    correlated = sum(1 for x in rows if x.get("correlation_group") == cand.get("correlation_group") and cand.get("correlation_group"))
    return {"allowed": concentration <= 0.60 and correlated < 3, "current_notional": current, "candidate_notional": candidate_notional, "concentration": concentration, "correlated_positions": correlated}


def execution_quality(execution: dict[str, Any] | None) -> dict[str, Any]:
    d = execution or {}
    if not d.get("usable"): return {"passed": False, "reason": "execution simulation unavailable"}
    spread = _f(d.get("spread_bps"))
    slip = _f(d.get("slippage_bps"))
    fill = _f(d.get("filled_notional")) / max(1e-12, _f(d.get("requested_notional")))
    passed = spread <= 35 and slip <= 20 and fill >= 0.999
    return {"passed": passed, "spread_bps": spread, "slippage_bps": slip, "fill_ratio": fill, "reason": "execution quality passed" if passed else "execution quality failed"}


def ensemble_score(votes: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [v for v in votes if isinstance(v, dict)]
    if not valid: return {"score": 0.0, "direction": 0, "agreement": 0.0}
    total_w = sum(max(0.0, _f(v.get("weight", 1.0))) for v in valid)
    score = sum(_direction(v.get("direction")) * max(0.0, _f(v.get("weight", 1.0))) * _clamp(v.get("strength")) for v in valid) / max(1e-12, total_w)
    direction = _direction(score)
    aligned = sum(1 for v in valid if _direction(v.get("direction")) == direction and direction != 0)
    return {"score": round(score, 4), "direction": direction, "agreement": round(aligned / len(valid), 4)}


def monte_carlo_summary(outcomes: list[float] | None, iterations: int = 2000) -> dict[str, Any]:
    """Cheap deterministic robustness proxy; production can replace with seeded MC.

    We report empirical drawdown/loss-streak statistics and deliberately avoid
    presenting a synthetic simulation as real performance evidence.
    """
    vals = [_f(x) for x in (outcomes or [])]
    if len(vals) < 30: return {"usable": False, "sample_count": len(vals), "reason": "Monte Carlo requires >=30 realized outcomes"}
    equity, peak, max_dd, streak, max_streak = 1.0, 1.0, 0.0, 0, 0
    for x in vals:
        equity *= max(0.01, 1.0 + x)
        peak = max(peak, equity)
        max_dd = max(max_dd, 1 - equity / peak)
        streak = streak + 1 if x < 0 else 0
        max_streak = max(max_streak, streak)
    return {"usable": True, "sample_count": len(vals), "empirical_max_drawdown": max_dd, "max_loss_streak": max_streak, "median_outcome": median(vals), "mean_outcome": mean(vals), "iterations": iterations}


def build_autonomous_intelligence(*, symbol: str, market_data: dict[str, Any], market_summary: dict[str, Any], derivatives: dict[str, Any] | None = None, expiry: dict[str, Any] | None = None, order_flow: dict[str, Any] | None = None, liquidations: dict[str, Any] | None = None, cross_asset: dict[str, Any] | None = None, anomalies: dict[str, Any] | None = None, history: dict[str, Any] | None = None, calibration: dict[str, Any] | None = None, strategy_stats: dict[str, Any] | None = None, positions: list[dict[str, Any]] | None = None, execution: dict[str, Any] | None = None, macro_blocked: bool = False) -> dict[str, Any]:
    """Run the full autonomous evidence pipeline and return an auditable trace."""
    quality = data_quality_guard(market_data)
    tf_results = market_summary.get("timeframes", {}) if isinstance(market_summary, dict) else {}
    regime = regime_switching_engine(tf_results)
    structure = structure_engine(tf_results)
    flow = order_flow_intelligence(order_flow)
    liq = liquidation_intelligence(liquidations, _f(market_summary.get("price")))
    deriv = derivatives_brain(derivatives)
    opt = options_expiry_brain(expiry, _f(market_summary.get("price")))
    cross = cross_asset_intelligence(cross_asset, symbol)
    anomaly = anomaly_detector(anomalies)
    hypotheses = setup_hypotheses(market_summary.get("mtf", market_summary), regime, structure, deriv, market_summary.get("liquidity", {}))
    fingerprint = {"regime": regime.get("regime"), "structure_bias": structure.get("bias"), "derivatives_crowding": deriv.get("crowding"), "expiry_status": opt.get("status"), "timeframes": tuple(sorted(tf_results))}
    twin = historical_twin(history, fingerprint)
    primary = _clamp(0.50 + 0.20 * _clamp(market_summary.get("confidence")) + 0.15 * structure.get("quality") + 0.10 * abs(flow.get("bias", 0)) + 0.05 * max(0.0, cross.get("bias", 0)))
    calibrated = probability_calibration(primary, calibration)
    probability = calibrated["probability"]
    meta = meta_labeling(probability, {"anomalous": anomaly.get("anomalous"), "mtf_conflict": market_summary.get("mtf", {}).get("conflict", False), "macro_blocked": macro_blocked, "execution_bad": not bool((execution or {}).get("usable", False))})
    plan = dynamic_trade_plan(_f(market_summary.get("price")), _f(market_summary.get("atr")), _direction(1 if market_summary.get("direction") == "LONG" else -1 if market_summary.get("direction") == "SHORT" else 0))
    ev = expected_value(probability, _f(history.get("avg_win")) if history else 0.0, _f(history.get("avg_loss")) if history else 0.0, _f(history.get("costs")) if history else 0.0, 1.35)
    stress = counterfactual_stress(plan, probability, _f((execution or {}).get("slippage_bps")), macro_blocked)
    stability = decision_stability(probability)
    kill = strategy_kill_switch(strategy_stats)
    strategy = strategy_selector(regime, strategy_stats)
    portfolio = portfolio_guard(positions, {"notional": (execution or {}).get("requested_notional", 0), "correlation_group": symbol.split("/")[0] if symbol else None})
    exec_quality = execution_quality(execution)
    votes = [
        {"model": "regime", "direction": 1 if regime.get("regime") == "TREND_UP" else -1 if regime.get("regime") == "TREND_DOWN" else 0, "strength": regime.get("confidence", 0.0), "weight": 1.2},
        {"model": "structure", "direction": _direction(structure.get("bias")), "strength": structure.get("quality", 0.0), "weight": 1.2},
        {"model": "order_flow", "direction": _direction(flow.get("bias")), "strength": abs(flow.get("bias", 0.0)), "weight": 1.0},
        {"model": "derivatives", "direction": _direction(deriv.get("bias")), "strength": abs(deriv.get("bias", 0.0)), "weight": 1.0},
        {"model": "cross_asset", "direction": _direction(cross.get("bias")), "strength": abs(cross.get("bias", 0.0)), "weight": 0.8},
        {"model": "history", "direction": _direction((history or {}).get("direction", 0)), "strength": twin.get("win_rate", 0.0), "weight": 1.4},
    ]
    ensemble = ensemble_score(votes)
    failures: list[str] = []
    if not quality.get("usable"): failures.extend(quality.get("issues", []))
    if macro_blocked: failures.append("economic calendar blocked the setup")
    if anomaly.get("anomalous"): failures.append("extreme market anomaly")
    if not twin.get("usable"): failures.append(twin.get("reason", "historical twin unavailable"))
    if not calibrated.get("usable"): failures.append(calibrated.get("reason", "calibration unavailable"))
    if not meta.get("tradeability"): failures.append("meta-labeling rejected tradeability")
    if not ev.get("positive") or not ev.get("stress_positive"): failures.append("expected value fails stress test")
    if not stress.get("passed"): failures.append(stress.get("reason", "counterfactual stress failed"))
    if not stability.get("stable"): failures.append("decision unstable under small perturbations")
    if not portfolio.get("allowed"): failures.append("portfolio concentration/correlation guard rejected")
    if not exec_quality.get("passed"): failures.append(exec_quality.get("reason", "execution-quality gate failed"))
    if not strategy.get("selected"): failures.append("no validated strategy available for current regime")
    if strategy.get("selected") in kill.get("disabled", []): failures.append("selected strategy is kill-switched")
    decision = "TRADE" if not failures else "NO_TRADE"
    return {
        "engine": "compoundx-autonomous-v1",
        "decision": decision,
        "symbol": symbol,
        "probability": round(probability, 6),
        "quality": quality,
        "regime": regime,
        "structure": structure,
        "order_flow": flow,
        "liquidations": liq,
        "derivatives": deriv,
        "options_expiry": opt,
        "cross_asset": cross,
        "anomaly": anomaly,
        "hypotheses": hypotheses,
        "historical_twin": twin,
        "calibration": calibrated,
        "meta_label": meta,
        "trade_plan": plan,
        "expected_value": ev,
        "counterfactual": stress,
        "stability": stability,
        "strategy": strategy,
        "strategy_kill_switch": kill,
        "portfolio_guard": portfolio,
        "execution_quality": exec_quality,
        "ensemble": ensemble,
        "failures": list(dict.fromkeys(failures)),
        "paper_trading": True,
        "live_execution": False,
        "withdrawals_enabled": False,
        "decision_trace": [
            "data_quality", "regime", "structure", "order_flow", "liquidity", "derivatives",
            "expiry_options", "cross_asset", "anomaly", "setup_hypotheses", "historical_twin",
            "calibration", "meta_label", "expected_value", "counterfactual", "stability",
            "strategy_selection", "portfolio_guard", "execution_quality", "adversarial_ensemble", "final_gate",
        ],
    }
