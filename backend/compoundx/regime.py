from __future__ import annotations

from enum import Enum
from dataclasses import dataclass

from .indicators import atr, ema


class Regime(str, Enum):
    BULL_TREND = "BULL_TREND"
    BEAR_TREND = "BEAR_TREND"
    RANGE = "RANGE"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RegimeResult:
    regime: Regime
    volatility_ratio: float
    confidence: float


def classify_regime(high: list[float], low: list[float], close: list[float]) -> RegimeResult:
    if len(close) < 50 or len(high) != len(close) or len(low) != len(close):
        return RegimeResult(Regime.UNKNOWN, 0.0, 0.0)
    e20, e50, e200 = ema(close, 20), ema(close, 50), ema(close, 200)
    a = atr(high, low, close, 14)
    if not a or close[-1] <= 0:
        return RegimeResult(Regime.UNKNOWN, 0.0, 0.0)
    recent_atr = a[-1]
    baseline = sum(a[-20:]) / min(20, len(a))
    volatility_ratio = recent_atr / baseline if baseline else 0.0
    if volatility_ratio >= 2.0:
        return RegimeResult(Regime.HIGH_VOLATILITY, volatility_ratio, min(1.0, volatility_ratio / 3.0))
    spread = abs(e20[-1] - e50[-1]) / close[-1]
    if e20[-1] > e50[-1] > e200[-1] and spread >= 0.002:
        return RegimeResult(Regime.BULL_TREND, volatility_ratio, min(1.0, spread * 100.0))
    if e20[-1] < e50[-1] < e200[-1] and spread >= 0.002:
        return RegimeResult(Regime.BEAR_TREND, volatility_ratio, min(1.0, spread * 100.0))
    return RegimeResult(Regime.RANGE, volatility_ratio, max(0.0, 1.0 - spread * 100.0))
