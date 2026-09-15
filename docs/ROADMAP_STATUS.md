# CompoundX Roadmap Status

Updated: 2026-09-15

## Software implementation complete
- [x] Architecture/specification baseline
- [x] Strategy V1 documentation
- [x] Risk firewall defaults and validation
- [x] Daily net-P&L compounding primitive
- [x] One-time access-code generation/hash primitive
- [x] FastAPI API with Vercel-compatible Python handlers
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
- [x] Expiry-aware analysis for daily, weekly, monthly, quarterly and other exchange-defined expiries
- [x] Expiry discovery from exchange-listed derivatives/options
- [x] Time-to-expiry, open-interest, volume, spread and optional IV/put-call analysis
- [x] Expiry-aware AI committee gate
- [x] Authenticated expiry analysis API
- [x] Expiry unit tests
- [x] Unified market-intelligence engine: multi-timeframe technical state, structure, regime, liquidity map, derivatives context, expiry context, adversarial challenge, sizing and execution simulation
- [x] Live command-center market endpoint with exchange public data
- [x] Premium responsive hero/dashboard UI with 14-timeframe matrix, liquidity, derivatives, expiry, AI committee, risk, execution and learning surfaces
- [x] Automatic 30-second market refresh with fail-closed UI state
- [x] Risk and execution hard gates
- [x] Committee decision persistence for audit
- [x] Out-of-sample validation metrics: expectancy, profit factor, drawdown, Sharpe, Brier and calibration error
- [x] Walk-forward split generator
- [x] AI committee and validation unit tests
- [x] Liquidity unit tests
- [x] Command-center market-intelligence unit tests
- [x] Vercel security headers and CSP
- [x] Client-side demo PIN removed
- [x] Security policy and environment-variable template

## New research and decision-quality stack — implemented
- [x] Matched-baseline bootstrap rule-significance engine with minimum sample gate
- [x] Monte Carlo trade-order robustness analysis with percentile outcomes and drawdown stress
- [x] Walk-forward validation engine with non-overlapping out-of-sample windows
- [x] Lookahead feature-name audit gate
- [x] Recursive indicator/history stability check primitive
- [x] Reliability-weighted committee consensus primitive
- [x] Probability calibration report with Brier score and expected calibration error
- [x] Risk-adjusted strategy-variant experiment selector
- [x] Event-driven order-book fill simulator with spread, depth, impact, latency, fees and slippage
- [x] Partial-fill simulation and slippage-budget rejection
- [x] Triple-barrier trade lifecycle: stop-loss, multi-target take-profit and time limit
- [x] Funding/basis dislocation signal primitive
- [x] Cross-exchange normalization/intelligence contract
- [x] Statistical-arbitrage z-score signal primitive
- [x] DRL research adapter with explicit research-only/live-disabled boundary
- [x] Specialist-agent contract covering trend, momentum, breakout, mean reversion, volatility, liquidity, funding, basis, derivatives, macro, news, historical edge, ML probability, execution and risk
- [x] Single command-center research payload; no additional Vercel function required
- [x] Research certification gate: an autonomous TRADE cannot be certified without sufficient validation evidence

## Command center architecture
The dashboard is now a thin visualization layer over the same evidence-first backend. It requests public exchange market data, analyzes every supported timeframe, computes a side-aware liquidity map, derives futures context, discovers expiring instruments, runs the adversarial gate, produces a paper-only trade plan, simulates fills and exposes the learning/risk state. The UI never converts an unavailable metric into a positive signal.

The research layer is deterministic and dependency-light. It implements statistical significance, Monte Carlo robustness, walk-forward evaluation, lookahead auditing, calibration, reliability weighting, realistic fill simulation, triple-barrier lifecycle controls, statistical arbitrage and funding/basis research. LLMs can propose and explain hypotheses, but they cannot bypass research, risk or execution gates.

An order book is instantaneous rather than a candle timeframe. CompoundX therefore pairs one current order-book snapshot with timeframe-specific OHLCV/volume context. LONG consumes ask-side depth; SHORT consumes bid-side depth. This prevents the dashboard from pretending that an order book has independent historical candles.

## Derivatives and expiry depth
The exchange adapter now attempts funding, open interest and spot-vs-perpetual basis where CCXT exposes the corresponding methods. Liquidations, OI change, option IV/skew/gamma, strike concentration and put/call ratios are treated as optional exchange-specific evidence rather than fabricated values.

Expiry discovery uses the exchange's actual listed expiry metadata. Instruments are grouped into DAILY, WEEKLY, MONTHLY, QUARTERLY and OTHER for analysis, while the raw expiry timestamp remains the source of truth. The research layer now consumes major-strike evidence when available and exposes hooks for IV/skew/gamma and cross-expiry research. A production-grade options venue integration should add strike-by-strike OI change, full IV surface/term structure, skew, gamma exposure, expiry clustering and liquidation/OI interaction when the selected venue exposes those feeds.

## Liquidity and expiry decision model
For each candidate side, CompoundX can collect the exchange order book and OHLCV for every supported timeframe. LONG evaluates executable ask-side depth; SHORT evaluates executable bid-side depth. The engine also measures bid/ask spread, visible depth relative to intended order notional, estimated market impact, volume relative to recent average, and order-book imbalance. Missing or insufficient timeframe data fails closed rather than being interpreted as confirmation.

For derivatives/options, CompoundX discovers exchange-listed expiry instruments and groups them into DAILY, WEEKLY, MONTHLY, QUARTERLY and OTHER tenors. It evaluates time-to-expiry, open interest, volume, spread and optional implied-volatility/put-call inputs. Spot markets are explicitly marked `NOT_APPLICABLE`; missing expiry evidence on an expiring derivative fails closed. Expiry is contextual evidence, never a standalone buy/sell signal.

## Evidence gates — real-world validation still required
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
The committee is fail-closed. Unknown regime, insufficient comparable history, material model disagreement, poor risk/reward, excessive spread/slippage, failed risk/execution checks, insufficient multi-timeframe liquidity, unavailable/weak expiry evidence for expiring derivatives, or an adversarial failure case results in `NO_TRADE`. The committee cannot change hard risk limits, enable live execution, or enable withdrawals. Its decisions and model votes are persisted for audit when PostgreSQL is configured.

## Self-learning safety model
Learning is advisory and bounded to +/-2 signal points. It cannot change hard risk limits, disable stop-loss/drawdown protection, enable live execution, or enable withdrawals. Insufficient history produces no adjustment. Persistent PostgreSQL records are the source of truth for lessons and reviews.

## Vercel architecture
The root dashboard is static HTML. Each `api/**` Python handler is deployed as a Vercel function and imports the shared backend package. Continuous workers, long-running paper execution and future live execution must remain separate from Vercel serverless execution. The new research stack is intentionally integrated into the existing command-center function to avoid increasing the Vercel function count.

## Acceptance criteria
A phase is complete only when implementation tests pass, failure paths are fail-closed, and required real-world evidence is recorded. Live trading is not considered complete merely because an exchange API can place an order.
