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
) -> dict[str, Any]:
    """Check current futures/perpetual and listed-options evidence before a trade.

    Futures evidence is expected for crypto candidates. Options are checked when
    the exchange exposes them; an asset without listed options is explicitly
    marked NOT_AVAILABLE rather than treated as a bullish/bearish signal.
    """
    d = derivatives if isinstance(derivatives, dict) else {}
    e = expiry if isinstance(expiry, dict) else {}
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

    option_count = int(_num(e.get("options_count", 0)))
    option_usable = int(_num(e.get("options_usable_instruments", 0)))
    options_available = option_count > 0
    options = {
        "checked": True,
        "available": options_available,
        "status": "AVAILABLE" if options_available else "NOT_AVAILABLE",
        "instruments_checked": option_count,
        "usable_instruments": option_usable,
        "iv_observations": int(_num(e.get("options_iv_observations", 0))),
        "delta_observations": int(_num(e.get("options_delta_observations", 0))),
        "gamma_observations": int(_num(e.get("options_gamma_observations", 0))),
        "theta_observations": int(_num(e.get("options_theta_observations", 0))),
        "vega_observations": int(_num(e.get("options_vega_observations", 0))),
        "rho_observations": int(_num(e.get("options_rho_observations", 0))),
    }
    if options_available:
        if option_usable <= 0:
            blockers.append("listed options detected but usable options evidence is weak")
        if options["gamma_observations"] == 0:
            warnings.append("option gamma data unavailable")
        if options["theta_observations"] == 0:
            warnings.append("option theta data unavailable")
        if options["iv_observations"] == 0:
            warnings.append("option implied-volatility data unavailable")

    return {
        "passed": not blockers,
        "futures": futures,
        "options": options,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
        "policy": "futures checked on every candidate; options checked whenever listed options exist",
    }
