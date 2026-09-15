from datetime import datetime, timedelta, timezone

from compoundx.economic_calendar import analyze_calendar, committee_calendar_gate


def test_high_impact_us_event_blocks_trade():
    now = datetime.now(timezone.utc)
    events = [{
        "CalendarId": "1",
        "Date": (now + timedelta(minutes=20)).isoformat(),
        "Country": "United States",
        "Category": "Interest Rate",
        "Event": "FOMC Rate Decision",
        "Importance": 3,
        "Currency": "USD",
        "Forecast": "5.0",
        "Previous": "5.0",
    }]
    result = analyze_calendar(events, symbol="BTC/USDT", now=now)
    passed, reasons = committee_calendar_gate(result)
    assert result["status"] == "READY"
    assert result["blackout_active"] is True
    assert passed is False
    assert any("blackout" in reason for reason in reasons)


def test_low_relevance_event_does_not_create_crypto_blackout():
    now = datetime.now(timezone.utc)
    events = [{
        "CalendarId": "2",
        "Date": (now + timedelta(minutes=10)).isoformat(),
        "Country": "India",
        "Category": "Rainfall",
        "Event": "Monsoon Rainfall",
        "Importance": 3,
        "Currency": "",
    }]
    result = analyze_calendar(events, symbol="BTC/USDT", now=now)
    passed, reasons = committee_calendar_gate(result)
    assert result["blackout_active"] is False
    assert passed is True
    assert reasons == []
