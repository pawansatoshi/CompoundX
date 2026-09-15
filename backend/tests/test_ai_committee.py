from compoundx.ai_committee import evaluate_committee
from compoundx.validation import evaluate_out_of_sample, walk_forward_slices


def strong_context():
    return {
        "direction": 1,
        "regime": "BULL_TREND",
        "regime_score": 0.95,
        "trend_score": 0.92,
        "momentum_score": 0.90,
        "volatility_score": 0.84,
        "liquidity_score": 0.90,
        "structure_score": 0.88,
        "news_score": 0.82,
        "history_count": 100,
        "history_win_rate": 0.80,
        "history_expectancy": 0.02,
        "history_direction": 1,
        "risk_reward": 2.2,
        "spread_bps": 5,
        "expected_slippage_bps": 4,
        "risk_ok": True,
        "execution_ok": True,
        "adversarial_score": 0.4,
    }


def test_strong_candidate_is_accepted_by_filter():
    result = evaluate_committee(strong_context())
    assert result.decision == "TRADE"
    assert result.agreement >= 0.75
    assert result.edge >= 0.68


def test_unknown_regime_fails_closed():
    context = strong_context()
    context["regime"] = "UNKNOWN"
    result = evaluate_committee(context)
    assert result.decision == "NO_TRADE"
    assert "unknown regime" in result.reasons


def test_insufficient_history_fails_closed():
    context = strong_context()
    context["history_count"] = 3
    result = evaluate_committee(context)
    assert result.decision == "NO_TRADE"
    assert any("insufficient" in x for x in result.reasons)


def test_adversarial_failure_blocks_trade():
    context = strong_context()
    context["adversarial_score"] = -0.9
    result = evaluate_committee(context)
    assert result.decision == "NO_TRADE"
    assert any("adversarial" in x for x in result.reasons)


def test_risk_and_execution_are_hard_gates():
    context = strong_context()
    context["risk_ok"] = False
    context["execution_ok"] = False
    result = evaluate_committee(context)
    assert result.decision == "NO_TRADE"


def test_validation_requires_out_of_sample_evidence():
    report = evaluate_out_of_sample([0.01] * 60, [0.8] * 60, min_samples=50)
    assert report.samples == 60
    assert report.passed
    assert report.brier_score >= 0


def test_walk_forward_slices_are_non_overlapping_tests():
    slices = walk_forward_slices(1000, train=500, test=100, step=100)
    assert slices
    assert slices[0] == (0, 500, 500, 600)
    assert all(test_start == train_end for _, train_end, test_start, _ in slices)
