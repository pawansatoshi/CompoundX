from __future__ import annotations

"""Final cross-market gate for futures and options evidence.

This is deliberately a confirmation/risk gate, not a standalone trading signal.
It runs immediately before CompoundX finalizes a candidate trade.
"""

from typing import Any


def _num(value: Any, default: float = 0.0) -> float:
    try:
        value = float(value)
        return value if value == value and abs(value) != float("inf") else default
    except (TypeError, ValueError):
        return default


def final_derivatives_options_gate(
    derivatives: dict[str, Any] | None,
    expiry: dict[str, Any] | None,
    expiry_market_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check current futures/perpetual and listed-options evidence before a trade.

    Futures evidence is checked for every candidate. Listed options are checked
    from the raw exchange chain whenever the exchange exposes option contracts.
    Missing options are explicitly NOT_AVAILABLE, never a fake positive signal.
    """
    d = derivatives if isinstance(derivatives, dict) else {}
    e = expiry if isinstance(expiry, dict) else {}
    raw = expiry_market_data if isinstance(expiry_market_data, dict) else {}
    blockers: list[str] = []
    warnings: list[str] = []

    futures_available = bool(d.get("available", False))
    futures = {
        "checked": True,
        "available": futures_available,
        "funding_rate": _num(d.get("funding_rate")),
        "open_interest": _num(d.get("open_interest")),
        "open_interest_change_pct": _num(d.get("open_interest_change_pct", d.get("oi_change_pct"))),
        "basis_pct": _num(d.get("basis_pct")),
        "liquidations_24h": _num(d.get("liquidations_24h")),
    }
    if not futures_available:
        blockers.append("futures/perpetual evidence unavailable")
    else:
        funding = futures["funding_rate"]
        oi_change = futures["open_interest_change_pct"]
        basis = futures["basis_pct"]
        if funding > 0.001 and oi_change > 0:
            warnings.append("futures long crowding elevated")
        if funding < -0.001 and oi_change > 0:
            warnings.append("futures short crowding elevated")
        if abs(basis) > 1.0:
            warnings.append("futures basis is unusually wide")

    raw_instruments = raw.get("instruments") if isinstance(raw.get("instruments"), list) else []
    option_chain = [
        item for item in raw_instruments
        if isinstance(item, dict) and (item.get("option") or item.get("optionType") or item.get("option_type"))
    ]
    option_count = len(option_chain)
    option_usable = sum(1 for item in option_chain if _num(item.get("open_interest")) > 0 and _num(item.get("volume")) > 0 and _num(item.get("spread_bps")) <= 35.0)
    option_iv = sum(1 for item in option_chain if item.get("implied_volatility") is not None)
    option_delta = sum(1 for item in option_chain if item.get("delta") is not None)
    option_gamma = sum(1 for item in option_chain if item.get("gamma") is not None)
    option_theta = sum(1 for item in option_chain if item.get("theta") is not None)
    option_vega = sum(1 for item in option_chain if item.get("vega") is not None)
    option_rho = sum(1 for item in option_chain if item.get("rho") is not None)
    options_available = option_count > 0
    options = {
        "checked": True,
        "available": options_available,
        "status": "AVAILABLE" if options_available else "NOT_AVAILABLE",
        "instruments_checked": option_count,
        "usable_instruments": option_usable,
        "iv_observations": option_iv,
        "delta_observations": option_delta,
        "gamma_observations": option_gamma,
        "theta_observations": option_theta,
        "vega_observations": option_vega,
        "rho_observations": option_rho,
        "expiry_status": e.get("status", "UNKNOWN"),
        "nearest_expiry": e.get("nearest"),
    }
    if options_available:
        if option_usable <= 0:
            blockers.append("listed options detected but usable options evidence is weak")
        if option_iv == 0:
            warnings.append("option implied-volatility data unavailable")
        if option_delta == 0 or option_gamma == 0 or option_theta == 0 or option_vega == 0:
            warnings.append("one or more option Greeks unavailable from exchange")

    return {
        "passed": not blockers,
        "futures": futures,
        "options": options,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
        "policy": "futures checked on every candidate; options chain checked whenever listed options exist",
    }
