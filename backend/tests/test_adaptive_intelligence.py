from compoundx.adaptive_intelligence import (
    calibrated_probability,
    counterfactual_matrix,
    drift_score,
    dynamic_risk_size,
    evidence_dependency,
    regime_distribution,
    self_critique,
    signal_half_life,
    specialist_reliability,
)


def test_regime_distribution_and_transition():
    result = regime_distribution({
        '15m': {'regime': 'TREND_UP'},
        '1h': {'regime': 'TREND_UP'},
        '4h': {'regime': 'TRANSITION'},
        '1d': {'regime': 'TRANSITION'},
    })
    assert result['regime'] == 'TREND_UP'
    assert result['transition_probability'] == 0.5
    assert result['unstable'] is True


def test_evidence_dependency_deduplicates_correlated_models():
    result = evidence_dependency([
        {'model': 'ema', 'cluster': 'price', 'strength': .8, 'quality': 1},
        {'model': 'rsi', 'cluster': 'price', 'strength': .7, 'quality': 1},
        {'model': 'liquidity', 'cluster': 'flow', 'strength': .6, 'quality': 1},
    ])
    assert result['independent_clusters'] == 2
    assert result['redundancy'] > 0


def test_probability_shrinks_when_uncertain():
    result = calibrated_probability(.9, 1.0, .5)
    assert .5 < result['calibrated'] < .9
    assert result['lower_bound'] < result['calibrated']


def test_drift_is_one_way_safety_response():
    result = drift_score({'expectancy': .2, 'win_rate': .45}, {'expectancy': .5, 'win_rate': .60})
    assert result['drift'] is True
    assert result['action'] in {'REDUCE', 'PAUSE'}


def test_dynamic_size_never_exceeds_base_risk():
    result = dynamic_risk_size(10000, 100, 99, .005, probability=.9, edge=.8, regime_confidence=.9, liquidity_score=.9, execution_score=.9)
    assert result['risk_amount'] <= 50


def test_signal_half_life_detects_stale_signal():
    result = signal_half_life(1800, 600)
    assert result['stale'] is True
    assert result['remaining_edge_fraction'] < .25


def test_counterfactual_survival_requires_all_stress_cases():
    assert counterfactual_matrix(2.0, .05)['survives_all'] is False


def test_specialist_reliability_downweights_weak_calibration():
    result = specialist_reliability([{'specialist': 'trend', 'samples': 100, 'brier': .3, 'ece': .2, 'accuracy': .51}])
    assert result['trend']['status'] == 'DOWNWEIGHT'


def test_self_critique_does_not_invent_missing_ev():
    result = self_critique(thesis='LONG continuation', supporting=['trend'], contradicting=[], missing=[], invalidation='below swing low', probability=.7, calibrated_lower_bound=.6, net_ev=None)
    assert result['passed'] is True
