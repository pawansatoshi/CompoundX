from datetime import datetime, timedelta, timezone

from compoundx.expiry import analyze_expiries, analyze_expiry_instrument, classify_tenor


def test_tenor_classification_covers_requested_expiries():
    ref = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert classify_tenor(ref + timedelta(days=1), ref) == "DAILY"
    assert classify_tenor(ref + timedelta(days=7), ref) == "WEEKLY"
    assert classify_tenor(ref + timedelta(days=30), ref) == "MONTHLY"
    assert classify_tenor(ref + timedelta(days=90), ref) == "QUARTERLY"


def test_expiry_analysis_uses_oi_volume_and_spread():
    ref = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = analyze_expiry_instrument({"expiry": ref + timedelta(days=7), "open_interest": 1000, "average_open_interest": 1000, "volume": 500, "average_volume": 500, "spread_bps": 5}, reference=ref)
    assert result.tenor == "WEEKLY"
    assert result.usable is True


def test_empty_spot_expiry_is_not_applicable():
    result = analyze_expiries([], market_type="spot", reference=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert result["status"] == "NOT_APPLICABLE"
    assert result["usable"] is True


def test_derivative_missing_expiry_fails_closed():
    result = analyze_expiries([{"symbol": "X"}], market_type="derivative")
    assert result["usable"] is False
    assert result["status"] == "AVAILABLE"
