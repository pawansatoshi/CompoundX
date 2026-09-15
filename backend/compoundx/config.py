from dataclasses import dataclass


@dataclass(frozen=True)
class RiskConfig:
    risk_per_trade: float = 0.005
    daily_loss_limit: float = 0.02
    max_drawdown: float = 0.10
    max_positions: int = 3
    max_leverage: float = 1.0
    max_portfolio_heat: float = 0.03
    max_position_correlation: float = 0.85


@dataclass(frozen=True)
class StrategyConfig:
    minimum_signal_score: int = 7
    minimum_calibrated_probability: float = 0.60
    minimum_probability_lower_bound: float = 0.55
    minimum_evidence_coverage: float = 0.70


@dataclass(frozen=True)
class ValidationConfig:
    minimum_research_samples: int = 30
    minimum_paper_samples: int = 100
    minimum_regime_count: int = 3
    minimum_oos_positive_split_rate: float = 0.60
    maximum_ece: float = 0.10
    require_stress_pass: bool = True


@dataclass(frozen=True)
class AppConfig:
    paper_trading: bool = True
    live_execution_enabled: bool = False
    withdrawals_enabled: bool = False
    risk: RiskConfig = RiskConfig()
    strategy: StrategyConfig = StrategyConfig()
    validation: ValidationConfig = ValidationConfig()


CONFIG = AppConfig()
