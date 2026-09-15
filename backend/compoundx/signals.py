from __future__ import annotations

from dataclasses import dataclass

from .indicators import ema, rsi, vwap
from .regime import Regime


@dataclass(frozen=True)
class Signal:
    side: str
    score: int
    reason: str
    regime: Regime


def score_signal(high: list[float], low: list[float], close: list[float], volume: list[float], regime: Regime) -> Signal:
    if not (len(high) == len(low) == len(close) == len(volume)) or len(close) < 50:
        return Signal("NONE", 0, "insufficient data", Regime.UNKNOWN)
    if regime in (Regime.UNKNOWN, Regime.HIGH_VOLATILITY):
        return Signal("NONE", 0, "unsafe regime", regime)
    e20, e50, e200 = ema(close, 20), ema(close, 50), ema(close, 200)
    vw = vwap(high, low, close, volume)
    rs = rsi(close, 14)
    bullish = e20[-1] > e50[-1] > e200[-1]
    bearish = e20[-1] < e50[-1] < e200[-1]
    side = "LONG" if bullish else "SHORT" if bearish else "NONE"
    score = 0
    if side != "NONE": score += 2
    if (side == "LONG" and close[-1] > vw[-1]) or (side == "SHORT" and close[-1] < vw[-1]): score += 1
    if (side == "LONG" and close[-1] > close[-2]) or (side == "SHORT" and close[-1] < close[-2]): score += 1
    avg_volume = sum(volume[-20:]) / 20
    if volume[-1] >= avg_volume * 1.1: score += 1
    if (side == "LONG" and rs[-1] > 50) or (side == "SHORT" and rs[-1] < 50): score += 1
    if (side == "LONG" and close[-1] > max(high[-21:-1])) or (side == "SHORT" and close[-1] < min(low[-21:-1])): score += 2
    return Signal(side if score >= 7 else "NONE", score, "rule-based confirmation", regime)
