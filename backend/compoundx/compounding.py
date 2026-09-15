from dataclasses import dataclass


@dataclass(frozen=True)
class DayClose:
    opening_equity: float
    realized_pnl: float
    fees: float
    slippage: float

    @property
    def net_pnl(self) -> float:
        return self.realized_pnl - self.fees - self.slippage

    @property
    def closing_equity(self) -> float:
        return max(0.0, self.opening_equity + self.net_pnl)


def compound_next_day(opening_equity: float, realized_pnl: float,
                      fees: float = 0.0, slippage: float = 0.0) -> float:
    return DayClose(opening_equity, realized_pnl, fees, slippage).closing_equity
