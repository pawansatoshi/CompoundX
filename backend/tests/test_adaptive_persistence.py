from compoundx.adaptive_persistence import adaptive_fingerprint


def test_adaptive_fingerprint_is_deterministic_and_direction_aware():
    base = {
        'direction_label': 'LONG',
        'regime': 'TRENDING',
        'strategy': 'trend_following',
        'adaptive_intelligence': {
            'final_probability': {'calibrated': 0.81},
            'evidence_dependency': {'independent_clusters': 4},
        },
    }
    a = adaptive_fingerprint(base, 'BTC/USDT')
    b = adaptive_fingerprint(dict(base), 'BTC/USDT')
    assert a == b
    changed = dict(base)
    changed['direction_label'] = 'SHORT'
    assert adaptive_fingerprint(changed, 'BTC/USDT') != a
