from dataclasses import dataclass


@dataclass(frozen=True)
class RiskConfig:
    risk_per_trade: float = 0.005
    daily_loss_limit: float = 0.02
    max_drawdown: float = 0.10
    max_positions: int = 3
    max_leverage: float = 1.0


@dataclass(frozen=True)
class StrategyConfig:
    minimum_signal_score: int = 7
    target_low: float = 0.06
    target_high: float = 0.08
    force_daily_target: bool = False


@dataclass(frozen=True)
class AppConfig:
    paper_trading: bool = True
    live_execution_enabled: bool = False
    withdrawals_enabled: bool = False
    risk: RiskConfig = RiskConfig()
    strategy: StrategyConfig = StrategyConfig()


CONFIG = AppConfig()
