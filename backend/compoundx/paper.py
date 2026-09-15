from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaperOrder:
    order_id: str
    symbol: str
    side: str
    quantity: float
    entry: float
    stop: float
    take_profit: float


def simulate_order(order_id: str, symbol: str, side: str, quantity: float, entry: float, stop: float, take_profit: float) -> PaperOrder:
    if side not in {"LONG", "SHORT"}:
        raise ValueError("side must be LONG or SHORT")
    if quantity <= 0 or entry <= 0:
        raise ValueError("quantity and entry must be positive")
    if side == "LONG" and not (stop < entry < take_profit):
        raise ValueError("invalid LONG stop/target")
    if side == "SHORT" and not (take_profit < entry < stop):
        raise ValueError("invalid SHORT stop/target")
    return PaperOrder(order_id, symbol, side, quantity, entry, stop, take_profit)


def mark_to_market(order: PaperOrder, price: float) -> float:
    if price <= 0:
        raise ValueError("price must be positive")
    direction = 1.0 if order.side == "LONG" else -1.0
    return (price - order.entry) * order.quantity * direction
