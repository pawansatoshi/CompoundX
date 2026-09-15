from compoundx.derivatives_gate import final_derivatives_options_gate


def test_futures_are_checked_and_validated():
    result = final_derivatives_options_gate(
        {"available": True, "funding_rate": 0.0001, "open_interest": 1000, "open_interest_change_pct": 2, "basis_pct": 0.2},
        {"status": "AVAILABLE"},
        {"instruments": []},
    )
    assert result["passed"] is True
    assert result["futures"]["checked"] is True


def test_missing_futures_blocks_final_trade_gate():
    result = final_derivatives_options_gate({"available": False}, {"status": "UNKNOWN"}, {"instruments": []})
    assert result["passed"] is False
    assert any("futures" in reason for reason in result["blockers"])


def test_listed_options_are_checked_without_becoming_fake_signal():
    result = final_derivatives_options_gate(
        {"available": True, "funding_rate": 0.0, "open_interest": 1000, "basis_pct": 0.0},
        {"status": "AVAILABLE", "nearest": {"days_to_expiry": 2}},
        {"instruments": [
            {"symbol": "BTC-OPT", "option": True, "optionType": "call", "open_interest": 100, "volume": 50, "spread_bps": 10, "implied_volatility": 0.55},
        ]},
    )
    assert result["passed"] is True
    assert result["options"]["checked"] is True
    assert result["options"]["available"] is True
    assert result["options"]["instruments_checked"] == 1
    assert result["options"]["iv_observations"] == 1
