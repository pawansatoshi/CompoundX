from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean
from typing import Iterable


@dataclass(frozen=True)
class ValidationReport:
    samples: int
    wins: int
    losses: int
    win_rate: float
    expectancy: float
    profit_factor: float
    max_drawdown: float
    sharpe: float
    brier_score: float
    calibration_error: float
    passed: bool
    failures: tuple[str, ...]


def _max_drawdown(returns: list[float]) -> float:
    equity = peak = 1.0
    worst = 0.0
    for r in returns:
        equity *= 1.0 + r
        peak = max(peak, equity)
        worst = max(worst, (peak - equity) / peak if peak else 0.0)
    return worst


def evaluate_out_of_sample(outcomes: Iterable[float], probabilities: Iterable[float], *, min_samples: int = 50, min_win_rate: float = 0.55, max_drawdown: float = 0.20) -> ValidationReport:
    pnl = [float(x) for x in outcomes]
    probs = [max(0.0, min(1.0, float(x))) for x in probabilities]
    if len(pnl) != len(probs):
        raise ValueError("outcomes and probabilities must have equal length")
    if not pnl:
        raise ValueError("validation requires at least one sample")
    wins = sum(x > 0 for x in pnl)
    losses = len(pnl) - wins
    win_rate = wins / len(pnl)
    expectancy = mean(pnl)
    gross_profit = sum(x for x in pnl if x > 0)
    gross_loss = abs(sum(x for x in pnl if x < 0))
    profit_factor = gross_profit / gross_loss if gross_loss else float("inf")
    dd = _max_drawdown(pnl)
    mu = mean(pnl)
    variance = mean((x - mu) ** 2 for x in pnl)
    sharpe = mu / sqrt(variance) * sqrt(len(pnl)) if variance > 0 else 0.0
    actual = [1.0 if x > 0 else 0.0 for x in pnl]
    brier = mean((p - a) ** 2 for p, a in zip(probs, actual))
    bins = [[] for _ in range(10)]
    for p, a in zip(probs, actual):
        bins[min(9, int(p * 10))].append((p, a))
    calibration_error = sum(abs(mean(p for p, _ in b) - mean(a for _, a in b)) * len(b) for b in bins if b) / len(pnl)
    failures: list[str] = []
    if len(pnl) < min_samples:
        failures.append(f"insufficient out-of-sample samples: {len(pnl)}/{min_samples}")
    if win_rate < min_win_rate:
        failures.append(f"win rate {win_rate:.2%} below {min_win_rate:.2%}")
    if expectancy <= 0:
        failures.append("non-positive expectancy")
    if dd > max_drawdown:
        failures.append(f"max drawdown {dd:.2%} above {max_drawdown:.2%}")
    if profit_factor < 1.0:
        failures.append("profit factor below 1.0")
    return ValidationReport(len(pnl), wins, losses, win_rate, expectancy, profit_factor, dd, sharpe, brier, calibration_error, not failures, tuple(failures))


def walk_forward_slices(size: int, *, train: int = 500, test: int = 100, step: int = 100) -> list[tuple[int, int, int, int]]:
    if min(size, train, test, step) <= 0:
        raise ValueError("size, train, test and step must be positive")
    slices = []
    start = 0
    while start + train + test <= size:
        slices.append((start, start + train, start + train, start + train + test))
        start += step
    return slices
