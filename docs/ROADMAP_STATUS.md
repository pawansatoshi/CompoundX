# CompoundX Roadmap Status

Updated: 2026-09-15

## Completed in repository
- [x] Architecture/specification baseline
- [x] Strategy V1 documentation
- [x] Risk firewall defaults and validation
- [x] Daily net-P&L compounding primitive
- [x] One-time access-code generation/hash primitive
- [x] FastAPI health/risk endpoints
- [x] Indicator engine: EMA, RSI, ATR, VWAP
- [x] Market-regime classifier
- [x] Rule-based signal scoring with 7/9 threshold
- [x] Paper order simulator and mark-to-market
- [x] Deterministic backtester with fees/slippage
- [x] CCXT sandbox/public market-data gateway
- [x] Live order method hard-disabled
- [x] Tamper-evident audit-event helper
- [x] Security policy

## Still required before any real-money trading
- [ ] PostgreSQL persistence and migrations
- [ ] Production authentication, authorization, TOTP/passkey flow
- [ ] Atomic single-use access-code redemption in DB
- [ ] Rate limiting and abuse controls
- [ ] Complete API request validation and audit persistence
- [ ] Walk-forward/backtest validation on real historical datasets
- [ ] 30-60 day paper-trading evidence
- [ ] Independent security review
- [ ] Tiny controlled live test with exchange permissions restricted to trading only
- [ ] Gradual scaling based on measured risk-adjusted performance

## Safety gate
CompoundX remains paper-only by default. The current exchange gateway deliberately refuses order creation. No software change in this repository should be interpreted as a promise of profitability. The 6-8% daily figure is a target scenario, not a guaranteed return.

## Acceptance criteria
A phase is complete only when its tests pass, failure paths are fail-closed, and the relevant evidence is recorded. Live trading is not considered complete merely because an exchange API can place an order.
