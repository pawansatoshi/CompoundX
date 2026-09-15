from dataclasses import dataclass

from .config import CONFIG


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reason: str
    position_size: float = 0.0


def position_size(equity: float, entry: float, stop: float) -> float:
    if equity <= 0 or entry <= 0 or stop <= 0 or entry == stop:
        return 0.0
    risk_amount = equity * CONFIG.risk.risk_per_trade
    distance = abs(entry - stop)
    return risk_amount / distance


def validate_trade(*, equity: float, daily_pnl: float, drawdown: float,
                   open_positions: int, entry: float, stop: float,
                   signal_score: int) -> RiskDecision:
    if not CONFIG.paper_trading and not CONFIG.live_execution_enabled:
        return RiskDecision(False, "live execution disabled")
    if CONFIG.withdrawals_enabled:
        return RiskDecision(False, "unsafe withdrawal configuration")
    if equity <= 0:
        return RiskDecision(False, "invalid equity")
    if daily_pnl <= -CONFIG.risk.daily_loss_limit:
        return RiskDecision(False, "daily loss circuit breaker")
    if drawdown >= CONFIG.risk.max_drawdown:
        return RiskDecision(False, "maximum drawdown reached")
    if open_positions >= CONFIG.risk.max_positions:
        return RiskDecision(False, "maximum open positions reached")
    if signal_score < CONFIG.strategy.minimum_signal_score:
        return RiskDecision(False, "signal score below threshold")
    size = position_size(equity, entry, stop)
    if size <= 0:
        return RiskDecision(False, "invalid stop or entry")
    return RiskDecision(True, "risk checks passed", size)
