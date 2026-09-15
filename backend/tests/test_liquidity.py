from compoundx.liquidity import analyze_liquidity, analyze_multi_timeframe_liquidity


def orderbook():
    return {
        "bids": [[100.0, 100.0], [99.9, 100.0], [99.8, 100.0]],
        "asks": [[100.1, 100.0], [100.2, 100.0], [100.3, 100.0]],
    }


def snapshots(count=4):
    return {
        tf: {"orderbook": orderbook(), "volume": 200.0, "average_volume": 100.0}
        for tf in ("1m", "5m", "15m", "1h")[:count]
    }


def test_liquidity_is_side_aware_and_measures_spread_depth_and_impact():
    result = analyze_liquidity("5m", orderbook(), side="LONG", order_notional=1000, volume=200, average_volume=100)
    assert result.spread_bps > 0
    assert result.depth_notional > 0
    assert result.depth_multiple > 0
    assert result.estimated_impact_bps > 0
    assert 0 <= result.score <= 1


def test_multi_timeframe_requires_broad_confirmation():
    result = analyze_multi_timeframe_liquidity(snapshots(), side="LONG", order_notional=1000)
    assert result["timeframes_checked"] == 4
    assert result["confirmation_ratio"] >= 0
    assert 0 <= result["score"] <= 1


def test_missing_timeframes_fail_closed():
    result = analyze_multi_timeframe_liquidity(snapshots(2), side="SHORT", order_notional=1000)
    assert not result["usable"]
    assert "insufficient timeframe" in result["reason"]


def test_short_path_is_evaluated_separately():
    long_result = analyze_multi_timeframe_liquidity(snapshots(), side="LONG", order_notional=1000)
    short_result = analyze_multi_timeframe_liquidity(snapshots(), side="SHORT", order_notional=1000)
    assert long_result["timeframes_checked"] == short_result["timeframes_checked"]
    assert all(row["timeframe"] for row in short_result["results"])
