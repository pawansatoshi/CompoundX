from __future__ import annotations

"""Closed-loop adaptive intelligence primitives.

This layer does not place orders. It evaluates uncertainty, regime drift,
strategy reliability, signal half-life, counterfactuals and risk sizing so the
existing fail-closed committee can make better decisions.
"""
from math import log
from typing import Any


def _f(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        return v if v == v and abs(v) != float('inf') else default
    except (TypeError, ValueError):
        return default


def _clamp(x: Any, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, _f(x)))


def regime_distribution(tf_results: dict[str, Any]) -> dict[str, Any]:
    rows = [v for v in (tf_results or {}).values() if isinstance(v, dict)]
    counts: dict[str, int] = {}
    for row in rows:
        r = str(row.get('regime', 'UNKNOWN')).upper()
        counts[r] = counts.get(r, 0) + 1
    total = sum(counts.values())
    distribution = {k: round(v / total, 6) for k, v in counts.items()} if total else {}
    ordered = sorted(distribution.items(), key=lambda x: x[1], reverse=True)
    top = ordered[0] if ordered else ('UNKNOWN', 0.0)
    transition = sum(distribution.get(x, 0.0) for x in ('TRANSITION', 'HIGH_VOLATILITY'))
    return {'distribution': distribution, 'regime': top[0], 'confidence': top[1], 'transition_probability': round(transition, 6), 'unstable': transition >= 0.25}


def evidence_dependency(votes: list[dict[str, Any]]) -> dict[str, Any]:
    clusters: dict[str, list[dict[str, Any]]] = {}
    for vote in votes or []:
        cluster = str(vote.get('cluster', 'uncategorized'))
        clusters.setdefault(cluster, []).append(vote)
    independent = []
    for cluster, rows in clusters.items():
        best = max(rows, key=lambda r: _f(r.get('strength', r.get('magnitude'))) * _clamp(r.get('quality', 1.0)))
        independent.append({'cluster': cluster, 'models': len(rows), 'representative': best.get('model'), 'weight': round(_f(best.get('strength', best.get('magnitude'))) * _clamp(best.get('quality', 1.0)), 6)})
    redundancy = 1.0 - (len(independent) / max(1, len(votes or [])))
    return {'clusters': independent, 'independent_clusters': len(independent), 'redundancy': round(max(0.0, redundancy), 6), 'policy': 'one contribution per evidence dependency cluster'}


def drift_score(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    keys = ('expectancy', 'win_rate', 'profit_factor', 'sharpe', 'oos_positive_split_rate')
    drops = []
    for key in keys:
        old = _f(baseline.get(key), 0.0)
        cur = _f(current.get(key), 0.0)
        if old > 0:
            drops.append(max(0.0, (old - cur) / old))
    score = sum(drops) / len(drops) if drops else 0.0
    return {'score': round(_clamp(score), 6), 'drift': score >= 0.30, 'severe': score >= 0.50, 'action': 'PAUSE' if score >= 0.50 else 'REDUCE' if score >= 0.30 else 'NORMAL'}


def specialist_reliability(records: list[dict[str, Any]], min_samples: int = 30) -> dict[str, Any]:
    out = {}
    for row in records or []:
        name = str(row.get('specialist', 'unknown'))
        n = int(_f(row.get('samples')))
        if n < min_samples:
            out[name] = {'weight': 0.5, 'status': 'INSUFFICIENT_HISTORY', 'samples': n}
            continue
        brier = _f(row.get('brier'), 0.25)
        ece = _f(row.get('ece'), 0.10)
        accuracy = _clamp(row.get('accuracy', 0.5))
        weight = _clamp(1.0 - min(1.0, brier * 2.0) - min(0.5, ece) + (accuracy - 0.5))
        out[name] = {'weight': round(weight, 6), 'status': 'RELIABLE' if weight >= 0.60 else 'DOWNWEIGHT', 'samples': n, 'brier': brier, 'ece': ece}
    return out


def calibrated_probability(probability: float, reliability_weight: float = 1.0, uncertainty: float = 0.0) -> dict[str, Any]:
    p = _clamp(probability)
    w = _clamp(reliability_weight)
    u = _clamp(uncertainty)
    # Shrink uncertain predictions toward 0.5 rather than manufacturing confidence.
    adjusted = 0.5 + (p - 0.5) * w * (1.0 - u)
    return {'raw': round(p, 6), 'calibrated': round(_clamp(adjusted), 6), 'uncertainty': round(u, 6), 'lower_bound': round(max(0.0, adjusted - u * 0.25), 6), 'upper_bound': round(min(1.0, adjusted + u * 0.25), 6)}


def dynamic_risk_size(equity: float, entry: float, stop: float, base_risk: float, *, probability: float, edge: float, regime_confidence: float, liquidity_score: float, execution_score: float, portfolio_multiplier: float = 1.0, degradation_multiplier: float = 1.0) -> dict[str, Any]:
    equity, entry, stop = _f(equity), _f(entry), _f(stop)
    distance = abs(entry - stop)
    if equity <= 0 or entry <= 0 or distance <= 0:
        return {'size': 0.0, 'risk_amount': 0.0, 'multiplier': 0.0, 'reason': 'invalid sizing inputs'}
    quality = sum(_clamp(x) for x in (probability, edge, regime_confidence, liquidity_score, execution_score)) / 5.0
    multiplier = min(1.0, max(0.0, quality)) * _clamp(portfolio_multiplier) * _clamp(degradation_multiplier)
    risk_amount = equity * max(0.0, _f(base_risk)) * multiplier
    return {'size': risk_amount / distance, 'risk_amount': risk_amount, 'multiplier': round(multiplier, 6), 'quality': round(quality, 6), 'policy': 'adaptive sizing can only reduce configured base risk'}


def signal_half_life(age_seconds: float, half_life_seconds: float) -> dict[str, Any]:
    age, half = max(0.0, _f(age_seconds)), max(1.0, _f(half_life_seconds, 1.0))
    remaining = 2.0 ** (-age / half)
    return {'age_seconds': age, 'half_life_seconds': half, 'remaining_edge_fraction': round(remaining, 6), 'stale': remaining < 0.25}


def counterfactual_matrix(base_ev: float, costs: float, stress_levels: tuple[float, ...] = (0.0, 0.25, 0.50, 1.0)) -> dict[str, Any]:
    base, cost = _f(base_ev), max(0.0, _f(costs))
    scenarios = [{'stress': s, 'net_ev': round(base * (1.0 - s) - cost * (1.0 + s), 8), 'positive': base * (1.0 - s) - cost * (1.0 + s) > 0} for s in stress_levels]
    return {'scenarios': scenarios, 'survives_all': all(x['positive'] for x in scenarios), 'worst_net_ev': min(x['net_ev'] for x in scenarios)}


def opportunity_cost(candidates: list[dict[str, Any]], no_trade_ev: float = 0.0) -> dict[str, Any]:
    rows = [x for x in (candidates or []) if _f(x.get('net_ev')) == _f(x.get('net_ev'))]
    best = max(rows, key=lambda x: _f(x.get('net_ev')), default={'action': 'NO_TRADE', 'net_ev': no_trade_ev})
    selected = best if _f(best.get('net_ev')) > _f(no_trade_ev) else {'action': 'NO_TRADE', 'net_ev': no_trade_ev}
    return {'selected': selected, 'alternatives': sorted(rows, key=lambda x: _f(x.get('net_ev')), reverse=True)}


def self_critique(*, thesis: str, supporting: list[str], contradicting: list[str], missing: list[str], invalidation: str, probability: float, calibrated_lower_bound: float, net_ev: float) -> dict[str, Any]:
    failures = []
    if not thesis or not invalidation: failures.append('thesis or invalidation is missing')
    if not supporting: failures.append('no supporting evidence')
    if len(contradicting) >= len(supporting) and contradicting: failures.append('contradicting evidence is not dominated')
    if missing: failures.append('material evidence is missing')
    if calibrated_lower_bound < 0.55: failures.append('calibrated lower probability bound is weak')
    if net_ev <= 0: failures.append('net expected value is not positive')
    return {'passed': not failures, 'failures': failures, 'thesis': thesis, 'invalidation': invalidation, 'probability': round(_clamp(probability), 6), 'calibrated_lower_bound': round(_clamp(calibrated_lower_bound), 6), 'net_ev': round(_f(net_ev), 8)}


def adaptive_snapshot(result: dict[str, Any], *, baseline: dict[str, Any] | None = None, specialist_records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    votes = result.get('votes', []) if isinstance(result, dict) else []
    p = _f(result.get('score', result.get('probability', 0.5)), 0.5)
    regime = result.get('regime', {}) if isinstance(result.get('regime'), dict) else {}
    current_metrics = result.get('strategy_metrics', {}) if isinstance(result.get('strategy_metrics'), dict) else {}
    drift = drift_score(current_metrics, baseline or {}) if baseline else {'score': 0.0, 'drift': False, 'severe': False, 'action': 'NO_BASELINE'}
    reliability = specialist_reliability(specialist_records or [])
    uncertainty = _clamp(result.get('uncertainty', 0.0))
    calibration = calibrated_probability(p, 1.0, uncertainty)
    return {
        'regime': regime,
        'probability': calibration,
        'evidence_dependency': evidence_dependency(votes),
        'drift': drift,
        'specialist_reliability': reliability,
        'state': 'CAUTION' if drift.get('drift') or calibration['lower_bound'] < 0.55 else 'NORMAL',
        'learning_policy': 'observe -> attribute -> validate OOS -> promote; never self-enable live trading',
    }
