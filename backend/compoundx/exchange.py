from __future__ import annotations

import os
import ccxt


class ExchangeGateway:
    """CCXT gateway. Public market data is allowed; live orders remain gated."""

    DEFAULT_TIMEFRAMES = ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w")

    def __init__(self, exchange_id: str = "binance", sandbox: bool = True):
        if not hasattr(ccxt, exchange_id):
            raise ValueError(f"unsupported exchange: {exchange_id}")
        cls = getattr(ccxt, exchange_id)
        self.exchange = cls({"enableRateLimit": True, "apiKey": os.getenv("COMPOUNDX_EXCHANGE_API_KEY", ""), "secret": os.getenv("COMPOUNDX_EXCHANGE_SECRET", "")})
        if sandbox:
            self.exchange.set_sandbox_mode(True)

    def ticker(self, symbol: str) -> dict:
        return self.exchange.fetch_ticker(symbol)

    def order_book(self, symbol: str, limit: int = 100) -> dict:
        if limit < 10 or limit > 1000:
            raise ValueError("order-book limit must be between 10 and 1000")
        return self.exchange.fetch_order_book(symbol, limit=limit)

    def supported_timeframes(self) -> list[str]:
        available = getattr(self.exchange, "timeframes", None) or {}
        return [tf for tf in self.DEFAULT_TIMEFRAMES if tf in available]

    def ohlcv(self, symbol: str, timeframe: str = "15m", limit: int = 250) -> list[list[float]]:
        if timeframe not in self.DEFAULT_TIMEFRAMES:
            raise ValueError(f"unsupported CompoundX timeframe: {timeframe}")
        if limit < 50 or limit > 1000:
            raise ValueError("limit must be between 50 and 1000")
        return self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    def multi_timeframe_market_data(self, symbol: str, *, limit: int = 250, orderbook_limit: int = 100) -> dict[str, dict]:
        data = {}
        for timeframe in self.supported_timeframes():
            candles = self.ohlcv(symbol, timeframe=timeframe, limit=limit)
            data[timeframe] = {"ohlcv": candles, "orderbook": self.order_book(symbol, limit=orderbook_limit), "volume": candles[-1][5] if candles else 0.0, "average_volume": sum(row[5] for row in candles[-20:]) / max(1, len(candles[-20:])) if candles else 0.0}
        return data

    def expiry_market_data(self, symbol: str, *, limit: int = 100) -> dict:
        """Discover all exchange-listed expiring derivatives/options for the base asset."""
        self.exchange.load_markets()
        base = symbol.split("/")[0]
        markets = []
        for market in self.exchange.markets.values():
            if market.get("base") != base or not market.get("expiry"):
                continue
            item = {"symbol": market.get("symbol"), "id": market.get("id"), "type": market.get("type"), "contract": market.get("contract"), "option": market.get("option"), "expiry": market.get("expiry"), "strike": market.get("strike"), "optionType": market.get("optionType")}
            try:
                ticker = self.exchange.fetch_ticker(item["symbol"])
                item["volume"] = ticker.get("baseVolume") or ticker.get("quoteVolume") or 0.0
                bid, ask = ticker.get("bid"), ticker.get("ask")
                item["spread_bps"] = ((ask - bid) / ((ask + bid) / 2.0) * 10000.0) if bid and ask and ask >= bid else 0.0
            except Exception:
                item["volume"], item["spread_bps"] = 0.0, 0.0
            try:
                if self.exchange.has.get("fetchOpenInterest"):
                    oi = self.exchange.fetch_open_interest(item["symbol"])
                    item["open_interest"] = oi.get("openInterestValue") or oi.get("openInterestAmount") or 0.0
            except Exception:
                item["open_interest"] = 0.0
            markets.append(item)
            if len(markets) >= limit:
                break
        return {"market_type": "derivative", "instruments": markets}

    def create_order(self, *args, **kwargs):
        raise RuntimeError("live execution is disabled; use paper execution")
