from __future__ import annotations

from typing import Sequence


def ema(values: Sequence[float], period: int) -> list[float]:
    if period <= 0 or not values:
        return []
    alpha = 2.0 / (period + 1.0)
    out: list[float] = []
    value = float(values[0])
    out.append(value)
    for raw in values[1:]:
        value = alpha * float(raw) + (1.0 - alpha) * value
        out.append(value)
    return out


def rsi(values: Sequence[float], period: int = 14) -> list[float]:
    if period <= 0 or len(values) < 2:
        return [50.0] * len(values)
    gains: list[float] = []
    losses: list[float] = []
    for a, b in zip(values, values[1:]):
        delta = float(b) - float(a)
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    out = [50.0]
    avg_gain = sum(gains[:period]) / period if len(gains) >= period else (sum(gains) / max(1, len(gains)))
    avg_loss = sum(losses[:period]) / period if len(losses) >= period else (sum(losses) / max(1, len(losses)))
    def value() -> float:
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
        return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
    out.extend([value()] * min(period, len(values) - 1))
    start = period
    for i in range(start, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out.append(value())
    return out[: len(values)]


def atr(high: Sequence[float], low: Sequence[float], close: Sequence[float], period: int = 14) -> list[float]:
    if not (len(high) == len(low) == len(close)) or not close or period <= 0:
        return []
    tr: list[float] = [float(high[0]) - float(low[0])]
    for i in range(1, len(close)):
        tr.append(max(float(high[i]) - float(low[i]), abs(float(high[i]) - float(close[i-1])), abs(float(low[i]) - float(close[i-1]))))
    out: list[float] = []
    value = sum(tr[:period]) / min(period, len(tr))
    for i, current in enumerate(tr):
        if i == 0:
            out.append(value)
        elif i < period:
            value = sum(tr[:i+1]) / (i + 1)
            out.append(value)
        else:
            value = (value * (period - 1) + current) / period
            out.append(value)
    return out


def vwap(high: Sequence[float], low: Sequence[float], close: Sequence[float], volume: Sequence[float]) -> list[float]:
    if not (len(high) == len(low) == len(close) == len(volume)):
        return []
    cumulative_pv = 0.0
    cumulative_volume = 0.0
    out: list[float] = []
    for h, l, c, vol in zip(high, low, close, volume):
        typical = (float(h) + float(l) + float(c)) / 3.0
        cumulative_pv += typical * max(0.0, float(vol))
        cumulative_volume += max(0.0, float(vol))
        out.append(typical if cumulative_volume == 0 else cumulative_pv / cumulative_volume)
    return out
