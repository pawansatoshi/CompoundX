from __future__ import annotations

"""Economic-calendar intelligence for the CompoundX decision engine.

The calendar is deliberately fail-closed: if the configured macro-data source is
unavailable, the engine cannot authorize a new trade. This prevents a stale or
missing macro calendar from being mistaken for a clean macro environment.
"""

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

DEFAULT_COUNTRIES = ("united states", "euro area", "united kingdom", "china", "japan", "canada", "australia", "india")
CRYPTO_MACRO_KEYWORDS = (
    "interest rate", "rate decision", "fomc", "fed", "ecb", "boe", "boj", "rbi",
    "cpi", "inflation", "core inflation", "pce", "employment", "non farm", "payroll",
    "unemployment", "jobless", "gdp", "retail sales", "pmi", "ism", "consumer confidence",
    "producer price", "ppi", "central bank", "powell", "press conference", "minutes",
    "treasury", "bond auction", "budget", "trade balance", "industrial production",
)

_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def _float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        text = str(value).strip().replace(",", "")
        multiplier = 1.0
        if text.endswith(("K", "k")):
            multiplier = 1_000.0; text = text[:-1]
        elif text.endswith(("M", "m")):
            multiplier = 1_000_000.0; text = text[:-1]
        elif text.endswith(("B", "b")):
            multiplier = 1_000_000_000.0; text = text[:-1]
        return float(re.sub(r"[^0-9.+-]", "", text)) * multiplier
    except (TypeError, ValueError):
        return None


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _importance(raw: Any) -> int:
    try:
        return max(1, min(3, int(raw)))
    except (TypeError, ValueError):
        text = str(raw or "").lower()
        return 3 if "high" in text else 2 if "medium" in text else 1


def _relevance(event: dict[str, Any], symbol: str) -> float:
    text = " ".join(str(event.get(k, "")) for k in ("Country", "Category", "Event", "Currency")).lower()
    score = 0.25 if any(k in text for k in CRYPTO_MACRO_KEYWORDS) else 0.0
    if "united states" in text or "usd" in text:
        score += 0.45
    if any(k in text for k in ("euro area", "european", "ecb", "united kingdom", "china", "japan")):
        score += 0.15
    if symbol.upper().startswith(("BTC", "ETH", "SOL")):
        score += 0.10
    return min(1.0, score)


def _normalize(raw: dict[str, Any], symbol: str, now: datetime) -> dict[str, Any] | None:
    dt = _parse_dt(raw.get("Date") or raw.get("date"))
    if not dt:
        return None
    importance = _importance(raw.get("Importance", raw.get("importance")))
    event = {
        "id": str(raw.get("CalendarId", raw.get("id", ""))),
        "time": dt.isoformat(),
        "country": str(raw.get("Country", raw.get("country", ""))),
        "category": str(raw.get("Category", raw.get("category", ""))),
        "event": str(raw.get("Event", raw.get("event", ""))),
        "currency": str(raw.get("Currency", raw.get("currency", ""))),
        "importance": importance,
        "actual": raw.get("Actual", raw.get("actual")),
        "forecast": raw.get("Forecast", raw.get("forecast")),
        "previous": raw.get("Previous", raw.get("previous")),
        "revised": raw.get("Revised", raw.get("revised")),
        "source": str(raw.get("Source", raw.get("source", ""))),
    }
    event["relevance"] = round(_relevance(raw, symbol), 4)
    event["minutes_from_now"] = round((dt - now).total_seconds() / 60.0, 2)
    return event


def analyze_calendar(events: list[dict[str, Any]], symbol: str = "BTC/USDT", now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    normalized = [x for x in (_normalize(e, symbol, now) for e in events) if x]
    normalized.sort(key=lambda x: x["time"])
    for event in normalized:
        minutes = abs(float(event["minutes_from_now"]))
        importance = int(event["importance"])
        relevance = float(event["relevance"])
        pre = 45 if importance == 3 else 20 if importance == 2 else 5
        post = 30 if importance == 3 else 15 if importance == 2 else 10
        event["blackout"] = relevance >= 0.45 and ((0 <= event["minutes_from_now"] <= pre) or (-post <= event["minutes_from_now"] < 0))
        event["surprise"] = None
        actual, forecast = _float(event.get("actual")), _float(event.get("forecast"))
        if actual is not None and forecast not in (None, 0):
            event["surprise"] = round((actual - forecast) / abs(forecast), 6)
        event["urgency"] = round(min(1.0, (importance / 3.0) * max(relevance, 0.25) * (1.0 if minutes <= 180 else 0.5)), 4)
    relevant = [e for e in normalized if e["relevance"] >= 0.25]
    high_risk = [e for e in relevant if e["importance"] == 3]
    blackout = [e for e in relevant if e["blackout"]]
    next_high = next((e for e in high_risk if e["minutes_from_now"] >= 0), None)
    risk_score = max((float(e["urgency"]) for e in relevant if e["minutes_from_now"] >= -30), default=0.0)
    return {
        "status": "READY",
        "usable": True,
        "symbol": symbol,
        "as_of": now.isoformat(),
        "events_checked": len(normalized),
        "relevant_events": len(relevant),
        "high_impact_events": len(high_risk),
        "blackout_active": bool(blackout),
        "risk_score": round(risk_score, 4),
        "next_high_impact": next_high,
        "blackout_events": blackout[:10],
        "events": relevant[:50],
        "reason": "macro calendar reviewed",
    }


def fetch_calendar(symbol: str = "BTC/USDT", days: int = 3, countries: tuple[str, ...] = DEFAULT_COUNTRIES) -> dict[str, Any]:
    api_key = os.getenv("TRADING_ECONOMICS_API_KEY", "").strip()
    required = os.getenv("ECONOMIC_CALENDAR_REQUIRED", "true").lower() not in {"0", "false", "no"}
    if not api_key:
        return {"status": "UNAVAILABLE", "usable": not required, "symbol": symbol, "events": [], "relevant_events": 0, "blackout_active": False, "risk_score": 1.0 if required else 0.0, "reason": "economic calendar API key is not configured"}
    days = max(1, min(14, int(days)))
    key = f"{symbol}|{days}|{','.join(countries)}"
    cached = _CACHE.get(key)
    if cached and time.time() - cached[0] < 60:
        return cached[1]
    start = datetime.now(timezone.utc).date()
    end = start + timedelta(days=days)
    url = f"https://api.tradingeconomics.com/calendar/country/{quote(','.join(countries))}/{start.isoformat()}/{end.isoformat()}?c={quote(api_key)}&f=json"
    try:
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "CompoundX/1.0"})
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        result = analyze_calendar(payload if isinstance(payload, list) else [], symbol=symbol)
        _CACHE[key] = (time.time(), result)
        return result
    except Exception as exc:
        return {"status": "UNAVAILABLE", "usable": not required, "symbol": symbol, "events": [], "relevant_events": 0, "blackout_active": False, "risk_score": 1.0 if required else 0.0, "reason": f"economic calendar unavailable: {type(exc).__name__}"}


def committee_calendar_gate(calendar: dict[str, Any]) -> tuple[bool, list[str]]:
    if not bool(calendar.get("usable", False)):
        return False, [str(calendar.get("reason", "economic calendar evidence unavailable"))]
    reasons: list[str] = []
    if bool(calendar.get("blackout_active")):
        reasons.append("high-impact economic event blackout window active")
    return not reasons, reasons
