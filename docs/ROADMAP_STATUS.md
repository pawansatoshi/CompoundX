# CompoundX Roadmap Status

Updated: 2026-09-15

## Software implementation complete
- [x] Architecture/specification baseline
- [x] Strategy V1 documentation
- [x] Risk firewall defaults and validation
- [x] Daily net-P&L compounding primitive
- [x] One-time access-code generation/hash primitive
- [x] FastAPI API with Vercel Python entrypoint
- [x] Indicator engine: EMA, RSI, ATR, VWAP
- [x] Market-regime classifier
- [x] Rule-based signal scoring with 7/9 threshold
- [x] Paper order simulator and mark-to-market
- [x] Deterministic backtester with fees/slippage
- [x] CCXT sandbox/public market-data gateway
- [x] Live order method hard-disabled
- [x] PostgreSQL schema for users, codes, trades, audit and rate limits
- [x] Argon2id password verification
- [x] JWT authentication
- [x] TOTP enrollment and login enforcement when enrolled
- [x] Atomic single-use access-code redemption
- [x] Database-backed rate limiting
- [x] Server-side Pydantic request validation
- [x] Persistent tamper-evident audit events
- [x] Bounded self-learning trade journal and setup fingerprinting
- [x] Pre-trade historical lesson review with bounded score adjustment
- [x] Post-trade mistake/solution persistence
- [x] Learning-review audit records
- [x] Self-learning API endpoints and tests
- [x] Multi-model deterministic AI trade committee
- [x] Adversarial thesis/failure-case gate
- [x] Historical-edge and minimum-sample gate
- [x] Side-aware order-book liquidity analysis
- [x] Multi-timeframe liquidity analysis across 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d and 1w where the exchange supports them
- [x] Bid/ask depth, spread, volume, depth-multiple and market-impact checks
- [x] Independent LONG and SHORT liquidity evaluation
- [x] Broad multi-timeframe liquidity confirmation gate
- [x] Liquidity-aware exchange market-data collection
- [x] Authenticated multi-timeframe liquidity API
- [x] Liquidity, spread and expected-slippage gates
- [x] Risk and execution hard gates
- [x] Committee decision persistence for audit
- [x] Out-of-sample validation metrics: expectancy, profit factor, drawdown, Sharpe, Brier and calibration error
- [x] Walk-forward split generator
- [x] AI committee and validation unit tests
- [x] Liquidity unit tests
- [x] Vercel security headers and CSP
- [x] Client-side demo PIN removed
- [x] Security policy and environment-variable template

## Liquidity decision model
For each candidate side, CompoundX can collect the exchange order book and OHLCV for every supported timeframe. LONG evaluates executable ask-side depth; SHORT evaluates executable bid-side depth. The engine also measures bid/ask spread, visible depth relative to intended order notional, estimated market impact, volume relative to recent average, and order-book imbalance. Missing or insufficient timeframe data fails closed rather than being interpreted as confirmation.

## Evidence gates — cannot be fabricated by code
- [ ] Apply `database/schema.sql` to a real production PostgreSQL database
- [ ] Configure Vercel Production Environment Variables and complete admin bootstrap, then remove bootstrap secrets
- [ ] Run full historical-data backtests on selected markets/timeframes and retain result artifacts
- [ ] Run walk-forward validation on unseen data
- [ ] Operate paper trading continuously for 30–60 days and retain signed/dated performance logs
- [ ] Independent security review / penetration test
- [ ] Only if all evidence gates pass: tiny controlled live test with exchange trading-only permissions and withdrawals disabled
- [ ] Gradual scaling based on measured risk-adjusted performance

## Safety gate
CompoundX remains paper-only by default. The exchange gateway deliberately refuses live order creation. No software change is a promise of profitability. The 6–8% daily figure is a target scenario, not a guaranteed return. The committee's `TRADE` decision means the candidate passed the configured evidence filters; it does not mean a profitable outcome is guaranteed.

## AI committee safety model
The committee is fail-closed. Unknown regime, insufficient comparable history, material model disagreement, poor risk/reward, excessive spread/slippage, failed risk/execution checks, insufficient multi-timeframe liquidity, or an adversarial failure case results in `NO_TRADE`. The committee cannot change hard risk limits, enable live execution, or enable withdrawals. Its decisions and model votes are persisted for audit when PostgreSQL is configured.

## Self-learning safety model
Learning is advisory and bounded to +/-2 signal points. It cannot change hard risk limits, disable stop-loss/drawdown protection, enable live execution, or enable withdrawals. Insufficient history produces no adjustment. Persistent PostgreSQL records are the source of truth for lessons and reviews.

## Vercel architecture
The root dashboard is static HTML and `api/index.py` exposes the FastAPI application under `/api/*`. Vercel's Python runtime supports FastAPI/ASGI functions; continuous trading workers should remain separate from Vercel serverless execution.

## Acceptance criteria
A phase is complete only when implementation tests pass, failure paths are fail-closed, and required real-world evidence is recorded. Live trading is not considered complete merely because an exchange API can place an order.
