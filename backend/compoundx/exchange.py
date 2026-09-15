from __future__ import annotations

import os

import ccxt


class ExchangeGateway:
    """CCXT gateway. Public market data is allowed; live orders remain gated."""

    def __init__(self, exchange_id: str = "binance", sandbox: bool = True):
        if not hasattr(ccxt, exchange_id):
            raise ValueError(f"unsupported exchange: {exchange_id}")
        cls = getattr(ccxt, exchange_id)
        config = {
            "enableRateLimit": True,
            "apiKey": os.getenv("COMPOUNDX_EXCHANGE_API_KEY", ""),
            "secret": os.getenv("COMPOUNDX_EXCHANGE_SECRET", ""),
        }
        self.exchange = cls(config)
        if sandbox:
            self.exchange.set_sandbox_mode(True)

    def ticker(self, symbol: str) -> dict:
        return self.exchange.fetch_ticker(symbol)

    def ohlcv(self, symbol: str, timeframe: str = "15m", limit: int = 250) -> list[list[float]]:
        if limit < 50 or limit > 1000:
            raise ValueError("limit must be between 50 and 1000")
        return self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    def create_order(self, *args, **kwargs):
        raise RuntimeError("live execution is disabled; use paper execution")
