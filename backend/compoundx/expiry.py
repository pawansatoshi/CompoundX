from __future__ import annotations

"""Expiry-aware market intelligence. Expiry is contextual evidence, never a standalone signal."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

TENORS = ("DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "OTHER")


def _num(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        return x if x == x and abs(x) != float("inf") else default
    except (TypeError, ValueError):
        return default


def _expiry_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        ts = float(value) / (1000.0 if float(value) > 10_000_000_000 else 1.0)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def classify_tenor(expiry: datetime, reference: datetime | None = None) -> str:
    ref = reference or datetime.now(timezone.utc)
    days = max(0.0, (expiry - ref).total_seconds() / 86400.0)
    if days <= 2.0:
        return "DAILY"
    if days <= 10.0:
        return "WEEKLY"
    if days <= 45.0:
        return "MONTHLY"
    if days <= 120.0:
        return "QUARTERLY"
    return "OTHER"


@dataclass(frozen=True)
class ExpiryResult:
    tenor: str
    expiry: str | None
    days_to_expiry: float
    open_interest: float
    volume: float
    spread_bps: float
    implied_volatility: float | None
    put_call_ratio: float | None
    score: float
    usable: bool
    reason: str


def analyze_expiry_instrument(instrument: dict[str, Any], *, reference: datetime | None = None) -> ExpiryResult:
    expiry = _expiry_dt(instrument.get("expiry") or instrument.get("expiration"))
    if expiry is None:
        return ExpiryResult("OTHER", None, 0.0, 0.0, 0.0, 0.0, None, None, 0.0, False, "missing expiry")
    ref = reference or datetime.now(timezone.utc)
    days = (expiry - ref).total_seconds() / 86400.0
    if days < 0:
        return ExpiryResult("OTHER", expiry.isoformat(), days, 0.0, 0.0, 0.0, None, None, 0.0, False, "expired instrument")
    tenor = str(instrument.get("tenor") or classify_tenor(expiry, ref)).upper()
    if tenor not in TENORS:
        tenor = "OTHER"
    oi = max(0.0, _num(instrument.get("open_interest")))
    volume = max(0.0, _num(instrument.get("volume")))
    spread = max(0.0, _num(instrument.get("spread_bps")))
    iv_raw, pcr_raw = instrument.get("implied_volatility"), instrument.get("put_call_ratio")
    iv = _num(iv_raw) if iv_raw is not None else None
    pcr = _num(pcr_raw) if pcr_raw is not None else None
    avg_oi = max(oi, _num(instrument.get("average_open_interest")))
    avg_vol = _num(instrument.get("average_volume"))
    oi_quality = min(1.0, oi / avg_oi) if avg_oi > 0 else 0.0
    volume_quality = min(1.0, volume / avg_vol) if avg_vol > 0 else 0.0
    spread_quality = max(0.0, min(1.0, 1.0 - spread / 35.0))
    urgency_quality = max(0.0, min(1.0, 1.0 - abs(days - 7.0) / 30.0))
    score = 0.35 * oi_quality + 0.25 * volume_quality + 0.25 * spread_quality + 0.15 * urgency_quality
    usable = oi > 0 and volume > 0 and spread <= 35.0 and score >= 0.60
    return ExpiryResult(tenor, expiry.isoformat(), round(days, 6), oi, volume, round(spread, 4), iv, pcr, round(score, 6), usable, "expiry evidence adequate" if usable else "weak expiry evidence")


def analyze_expiries(instruments: list[dict[str, Any]] | None, *, market_type: str = "spot", reference: datetime | None = None) -> dict[str, Any]:
    if str(market_type).lower() in {"spot", "cash"} and not instruments:
        return {"status": "NOT_APPLICABLE", "usable": True, "score": 1.0, "tenors": {}, "reason": "spot market has no expiry"}
    if not instruments:
        return {"status": "UNKNOWN", "usable": False, "score": 0.0, "tenors": {}, "reason": "expiry data unavailable"}
    results = [analyze_expiry_instrument(x, reference=reference) for x in instruments if isinstance(x, dict)]
    if not results:
        return {"status": "UNKNOWN", "usable": False, "score": 0.0, "tenors": {}, "reason": "no valid expiry instruments"}
    by_tenor: dict[str, list[dict[str, Any]]] = {t: [] for t in TENORS}
    for result in results:
        by_tenor[result.tenor].append(result.__dict__)
    usable = [r for r in results if r.usable]
    score = sum(r.score for r in results) / len(results)
    nearest = min(results, key=lambda r: r.days_to_expiry)
    return {"status": "AVAILABLE", "usable": bool(usable), "score": round(score, 6), "instruments_checked": len(results), "usable_instruments": len(usable), "tenors": by_tenor, "nearest": nearest.__dict__, "reason": "expiry structure available" if usable else "expiry evidence weak"}
