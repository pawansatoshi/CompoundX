from __future__ import annotations

"""Order-book and volume liquidity analysis for every supported timeframe.

The analyzer is deliberately fail-closed: missing or stale liquidity data can
never be treated as confirmation. It evaluates execution liquidity separately
for LONG and SHORT candidates and aggregates multiple timeframes without
pretending that one timeframe represents the whole market.
"""

from dataclasses import dataclass
from math import isfinite
from typing import Any

DEFAULT_TIMEFRAMES = (
    "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w"
)
MIN_TIMEFRAMES = 3
MIN_DEPTH_MULTIPLE = 5.0
MAX_SPREAD_BPS = 35.0
MAX_IMPACT_BPS = 20.0


@dataclass(frozen=True)
class LiquidityResult:
    timeframe: str
    score: float
    side_score: float
    spread_bps: float
    depth_notional: float
    depth_multiple: float
    estimated_impact_bps: float
    imbalance: float
    usable: bool
    reason: str


def _num(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return x if isfinite(x) else default


def _depth(levels: Any, reference_price: float, max_bps: float = 50.0) -> float:
    if not isinstance(levels, (list, tuple)) or reference_price <= 0:
        return 0.0
    total = 0.0
    for level in levels:
        if not isinstance(level, (list, tuple)) or len(level) < 2:
            continue
        price, amount = _num(level[0]), _num(level[1])
        if price <= 0 or amount <= 0:
            continue
        distance_bps = abs(price - reference_price) / reference_price * 10000.0
        if distance_bps <= max_bps:
            total += price * amount
    return total


def analyze_liquidity(timeframe: str, orderbook: dict[str, Any], *, side: str, order_notional: float = 0.0, volume: float = 0.0, average_volume: float = 0.0) -> LiquidityResult:
    side = str(side).upper()
    if side not in {"LONG", "SHORT"}:
        return LiquidityResult(timeframe, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False, "invalid side")
    if not isinstance(orderbook, dict):
        return LiquidityResult(timeframe, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False, "missing order book")

    bids, asks = orderbook.get("bids"), orderbook.get("asks")
    if not bids or not asks:
        return LiquidityResult(timeframe, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False, "empty order book")
    bid = _num(bids[0][0]) if isinstance(bids[0], (list, tuple)) and bids[0] else 0.0
    ask = _num(asks[0][0]) if isinstance(asks[0], (list, tuple)) and asks[0] else 0.0
    if bid <= 0 or ask <= 0 or ask < bid:
        return LiquidityResult(timeframe, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False, "invalid top of book")

    mid = (bid + ask) / 2.0
    spread_bps = (ask - bid) / mid * 10000.0
    bid_depth = _depth(bids, mid)
    ask_depth = _depth(asks, mid)
    total_depth = bid_depth + ask_depth
    imbalance = (bid_depth - ask_depth) / total_depth if total_depth else 0.0

    # LONG consumes asks; SHORT consumes bids. The opposite side is still
    # useful as exit/support liquidity, so both sides enter the quality score.
    executable_depth = ask_depth if side == "LONG" else bid_depth
    depth_multiple = executable_depth / order_notional if order_notional > 0 else 0.0
    volume_ratio = volume / average_volume if average_volume > 0 else 1.0

    # Conservative impact proxy: larger requested notional relative to visible
    # depth implies greater price impact. Unknown order size is not confirmation.
    estimated_impact_bps = 100.0 / max(depth_multiple, 0.01) if order_notional > 0 else 100.0
    spread_score = max(0.0, min(1.0, 1.0 - spread_bps / MAX_SPREAD_BPS))
    depth_score = max(0.0, min(1.0, depth_multiple / MIN_DEPTH_MULTIPLE)) if order_notional > 0 else 0.0
    volume_score = max(0.0, min(1.0, volume_ratio / 1.5))
    side_pressure = imbalance if side == "LONG" else -imbalance
    side_score = max(0.0, min(1.0, 0.5 + 0.5 * side_pressure))
    impact_score = max(0.0, min(1.0, 1.0 - estimated_impact_bps / MAX_IMPACT_BPS))
    score = 0.30 * spread_score + 0.35 * depth_score + 0.15 * volume_score + 0.10 * side_score + 0.10 * impact_score

    usable = (
        spread_bps <= MAX_SPREAD_BPS
        and order_notional > 0
        and depth_multiple >= MIN_DEPTH_MULTIPLE
        and estimated_impact_bps <= MAX_IMPACT_BPS
        and score >= 0.65
    )
    reason = "liquidity adequate" if usable else "insufficient execution liquidity"
    return LiquidityResult(timeframe, round(score, 6), round(side_score, 6), round(spread_bps, 4), round(executable_depth, 4), round(depth_multiple, 4), round(estimated_impact_bps, 4), round(imbalance, 6), usable, reason)


def analyze_multi_timeframe_liquidity(snapshots: dict[str, dict[str, Any]], *, side: str, order_notional: float) -> dict[str, Any]:
    """Evaluate all supplied timeframes and require broad liquidity confirmation."""
    results: list[LiquidityResult] = []
    for timeframe in DEFAULT_TIMEFRAMES:
        snapshot = snapshots.get(timeframe)
        if not snapshot:
            continue
        results.append(analyze_liquidity(timeframe, snapshot.get("orderbook", {}), side=side, order_notional=order_notional, volume=_num(snapshot.get("volume")), average_volume=_num(snapshot.get("average_volume"))))

    if len(results) < MIN_TIMEFRAMES:
        return {"usable": False, "score": 0.0, "timeframes_checked": len(results), "results": [r.__dict__ for r in results], "reason": f"insufficient timeframe liquidity data ({len(results)}/{MIN_TIMEFRAMES})"}

    usable = [r for r in results if r.usable]
    score = sum(r.score for r in results) / len(results)
    max_spread = max(r.spread_bps for r in results)
    max_impact = max(r.estimated_impact_bps for r in results)
    broad_confirmation = len(usable) / len(results) >= 0.75
    overall = broad_confirmation and score >= 0.70 and max_spread <= MAX_SPREAD_BPS and max_impact <= MAX_IMPACT_BPS
    return {
        "usable": overall,
        "score": round(score, 6),
        "timeframes_checked": len(results),
        "usable_timeframes": len(usable),
        "confirmation_ratio": round(len(usable) / len(results), 6),
        "max_spread_bps": round(max_spread, 4),
        "max_estimated_impact_bps": round(max_impact, 4),
        "results": [r.__dict__ for r in results],
        "reason": "multi-timeframe liquidity confirmed" if overall else "multi-timeframe liquidity rejected",
    }
