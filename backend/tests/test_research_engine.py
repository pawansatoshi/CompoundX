from compoundx.research_engine import (
    calibration_report,
    funding_basis_signal,
    lookahead_audit,
    monte_carlo_robustness,
    performance_metrics,
    reliability_weighted_consensus,
    rule_significance,
    simulate_fill,
    stat_arb_signal,
    triple_barrier,
    walk_forward_splits,
)


def test_performance_metrics_and_drawdown():
    result = performance_metrics([0.10, -0.05, 0.08, -0.02])
    assert result["samples"] == 4
    assert result["win_rate"] == 0.5
    assert result["max_drawdown"] > 0


def test_significance_fails_closed_for_small_samples():
    result = rule_significance([0.1] * 29)
    assert result["usable"] is False
    assert result["significant"] is False


def test_monte_carlo_fails_closed_for_small_samples():
    result = monte_carlo_robustness([0.01] * 29)
    assert result["usable"] is False


def test_walk_forward_has_non_overlapping_oos_windows():
    splits = walk_forward_splits(500, train_size=200, test_size=50)
    assert splits
    assert splits[0]["train_end"] == splits[0]["test_start"]
    assert splits[0]["test_end"] <= splits[1]["train_start"] + 200


def test_calibration_report_detects_well_calibrated_data():
    probs = [0.5] * 30
    outcomes = [i % 2 == 0 for i in range(30)]
    result = calibration_report(probs, outcomes)
    assert result["usable"] is True
    assert result["brier"] <= 0.26


def test_lookahead_audit_blocks_future_feature_names():
    result = lookahead_audit(["rsi", "ema20", "future_return"])
    assert result["passed"] is False
    assert "future_return" in result["suspect_features"]


def test_reliability_weighted_consensus_prefers_stronger_model():
    result = reliability_weighted_consensus([
        {"model": "trend", "direction": 1, "strength": 1, "weight": 1.0},
        {"model": "weak", "direction": -1, "strength": 1, "weight": 0.1},
    ])
    assert result["direction"] == 1
    assert result["score"] > 0.5


def test_execution_simulator_rejects_bad_slippage():
    fill = simulate_fill(side="BUY", quantity=100, bid=100, ask=110, depth=1, max_slippage_bps=20)
    assert fill.status == "REJECTED"


def test_triple_barrier_stop_and_target():
    stop = triple_barrier(side="LONG", entry=100, stop=95, targets=[105], high=103, low=94, age_bars=1, max_bars=10)
    target = triple_barrier(side="LONG", entry=100, stop=95, targets=[105], high=106, low=99, age_bars=1, max_bars=10)
    assert stop["exit"] == "STOP_LOSS"
    assert target["exit"] == "TAKE_PROFIT_1"


def test_stat_arb_signal_is_fail_closed_for_short_history():
    result = stat_arb_signal([1] * 29, [1] * 29)
    assert result["usable"] is False


def test_funding_basis_signal():
    assert funding_basis_signal(0.001, 0.2)["signal"] == "SHORT_BIAS"
    assert funding_basis_signal(-0.001, -0.2)["signal"] == "LONG_BIAS"
