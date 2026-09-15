from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestResult:
    starting_equity: float
    ending_equity: float
    total_return: float
    max_drawdown: float
    trades: int
    wins: int
    losses: int
    fees: float
    slippage: float


def run_backtest(prices: list[float], signals: list[int], starting_equity: float = 100.0, fee_rate: float = 0.0005, slippage_rate: float = 0.0005) -> BacktestResult:
    if len(prices) != len(signals) or not prices:
        raise ValueError("prices and signals must have equal non-zero length")
    if starting_equity <= 0:
        raise ValueError("starting_equity must be positive")
    equity = starting_equity
    peak = equity
    max_dd = 0.0
    wins = losses = trades = 0
    fees = slippage = 0.0
    position = 0
    entry = 0.0
    for price, desired in zip(prices, signals):
        price = float(price)
        if price <= 0 or desired not in (-1, 0, 1):
            raise ValueError("invalid price or signal")
        if desired != position:
            if position:
                pnl = (price - entry) * position
                cost = abs(price) * (fee_rate + slippage_rate)
                equity += pnl - cost
                fees += abs(price) * fee_rate
                slippage += abs(price) * slippage_rate
                trades += 1
                wins += pnl > 0
                losses += pnl <= 0
            if desired:
                entry = price
            position = desired
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak else 0.0)
    if position:
        price = float(prices[-1])
        pnl = (price - entry) * position
        cost = abs(price) * (fee_rate + slippage_rate)
        equity += pnl - cost
        fees += abs(price) * fee_rate
        slippage += abs(price) * slippage_rate
        trades += 1
        wins += pnl > 0
        losses += pnl <= 0
    return BacktestResult(starting_equity, equity, equity / starting_equity - 1.0, max_dd, trades, wins, losses, fees, slippage)
