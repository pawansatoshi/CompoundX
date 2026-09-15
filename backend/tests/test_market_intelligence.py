from compoundx.market_intelligence import analyze_orderbook, analyze_timeframe, aggregate_timeframes, build_command_center, position_size, simulate_execution


def candles(n=220):
    rows = []
    price = 100.0
    for i in range(n):
        price += 0.12
        rows.append([i * 60_000, price - 0.3, price + 0.5, price - 0.6, price, 1000 + i])
    return rows


def book():
    return {"bids": [[100.0 - i * 0.1, 20.0] for i in range(20)], "asks": [[100.1 + i * 0.1, 20.0] for i in range(20)]}


def test_timeframe_analysis_is_deterministic_and_usable():
    result = analyze_timeframe("15m", candles())
    assert result["usable"] is True
    assert result["price"] > 100
    assert result["ema20"] > result["ema200"]


def test_orderbook_is_side_aware():
    result = analyze_orderbook(book(), 100)
    assert result["usable"] is True
    assert result["long"]["executable_depth"] > 0
    assert result["short"]["executable_depth"] > 0


def test_mtf_aggregation_exposes_consensus_and_conflict():
    rows = {f: {"usable": True, "direction": "LONG", "regime": "TREND_UP"} for f in ("1m", "5m", "15m", "1h")}
    result = aggregate_timeframes(rows)
    assert result["direction"] == "LONG"
    assert result["consensus"] == 1.0
    assert result["conflict"] is False


def test_position_size_never_exceeds_two_percent_risk_fraction():
    result = position_size(1000, 0.50, 100, 98, 1.0)
    assert result["risk_budget"] == 20


def test_execution_simulator_detects_fill_quality():
    result = simulate_execution(book(), "LONG", 100)
    assert result["usable"] is True
    assert result["quantity"] > 0
    assert result["slippage_bps"] >= 0


def test_command_center_always_requires_historical_edge():
    market = {"15m": {"ohlcv": candles(), "orderbook": book()}}
    result = build_command_center("TEST/USDT", market, {"funding_rate": 0.001}, {"status": "AVAILABLE", "usable": True, "score": 0.8})
    assert result["decision"] == "NO_TRADE"
    assert result["risk"]["live_execution"] is False
    assert any("historical edge" in reason for reason in result["reasons"])
