from compoundx.autonomous_intelligence import (
    counterfactual_stress,
    data_quality_guard,
    decision_stability,
    derivatives_brain,
    expected_value,
    historical_twin,
    meta_labeling,
    regime_switching_engine,
    strategy_kill_switch,
)


def candles(n=60):
    return [[i * 60000, 100 + i, 101 + i, 99 + i, 100.5 + i, 1000] for i in range(n)]


def test_data_quality_requires_multiple_clean_timeframes():
    good = {"15m": {"ohlcv": candles()}, "1h": {"ohlcv": candles()}, "4h": {"ohlcv": candles()}}
    assert data_quality_guard(good)["usable"] is True
    assert data_quality_guard({"15m": {"ohlcv": candles()}})["usable"] is False


def test_regime_engine_selects_and_scopes_strategies():
    rows = {tf: {"usable": True, "regime": "TREND_UP", "direction": "LONG"} for tf in ("15m", "1h", "4h")}
    result = regime_switching_engine(rows)
    assert result["regime"] == "TREND_UP"
    assert "trend_following" in result["eligible_strategies"]


def test_derivatives_detect_crowded_longs():
    result = derivatives_brain({"funding_rate": 0.001, "open_interest": 100, "open_interest_change_pct": 5, "basis_pct": 1})
    assert result["crowding"] == "crowded_long"
    assert result["bias"] < 0


def test_historical_twin_fails_closed_without_sample():
    assert historical_twin({"count": 19}, {})["usable"] is False
    assert historical_twin({"count": 40, "similarity": 0.8, "win_rate": 0.72, "expectancy": 0.01}, {})["usable"] is True


def test_ev_requires_stress_survival():
    result = expected_value(0.75, 2.0, 1.0, 0.05, 1.35)
    assert result["positive"] is True
    assert result["stress_positive"] is True


def test_meta_label_rejects_macro_block():
    result = meta_labeling(0.9, {"macro_blocked": True})
    assert result["tradeability"] is False


def test_decision_stability_detects_threshold_fragility():
    assert decision_stability(0.9)["stable"] is True
    assert decision_stability(0.705)["stable"] is False


def test_counterfactual_rejects_macro_block():
    plan = {"usable": True, "entry": 100.0, "target": 104.0}
    assert counterfactual_stress(plan, 0.9, 5, macro_blocked=True)["passed"] is False


def test_strategy_kill_switch_disables_degraded_strategy():
    result = strategy_kill_switch({"breakout": {"sample_count": 50, "expectancy": -0.01, "profit_factor": 0.9, "max_drawdown": 0.2}})
    assert "breakout" in result["disabled"]
