# CompoundX

**Secure, non-custodial algorithmic trading platform — V1 foundation**

CompoundX is being designed around three principles:

1. **Daily compounding of realized net P&L**
2. **Risk-first autonomous execution**
3. **Admin-controlled access with single-use invitation codes**

> ⚠️ V1 is paper-trading only. No live exchange execution is enabled. CompoundX does not guarantee a daily return or profit.

## Architecture

```text
User / Admin
     |
     v
Next.js / Web UI (Vercel)
     |
     v
Authenticated API
     |
     +--> Access control / audit
     +--> Market data
     +--> Strategy engine
     +--> Risk firewall
     +--> Execution engine
     |
     v
Exchange API (future; withdrawals disabled)
```

## Strategy V1

The initial strategy stack will combine:

- market-regime classification
- EMA 20/50/200 trend structure
- VWAP
- RSI and ATR
- volume confirmation
- market structure
- breakout/retest
- controlled range reversion
- signal scoring

The system may return **NO TRADE**. It must never force a daily target.

## Risk defaults

- Risk per trade: 0.50%
- Daily loss circuit breaker: -2%
- Maximum portfolio drawdown: 10%
- Maximum concurrent positions: 3
- Withdrawal permission: disabled
- Emergency stop: required
- Daily compounding: realized net P&L after fees/slippage

These are starting parameters for testing, not performance guarantees.

## Security requirements

- Private repository recommended before any production secrets are introduced.
- Never commit API keys, passwords, JWT secrets, seed phrases, or exchange credentials.
- Exchange API keys must not have withdrawal permission.
- Admin access must use strong authentication and 2FA/passkeys.
- Invitation codes must be cryptographically random, hashed at rest, expiring, revocable and atomically single-use.
- Server-side validation is mandatory; frontend validation is never trusted.
- Trading must fail closed when market data, configuration, authentication or risk checks are unavailable.

## Development roadmap

### Phase 1 — Foundation
- dashboard
- admin UI
- authentication model
- single-use access-code model
- audit log model

### Phase 2 — Research
- historical data adapter
- indicators
- regime classifier
- signal engine
- backtester

### Phase 3 — Risk
- position sizing
- stop-loss logic
- daily circuit breaker
- drawdown protection
- kill switch

### Phase 4 — Paper trading
- live market data
- simulated execution
- daily compounding
- performance analytics

### Phase 5 — Live execution
- only after backtest + walk-forward + paper validation
- exchange-specific API integration
- trading permission only
- withdrawals permanently disabled

## Local preview

The first UI prototype is a zero-build static page in `index.html` and can be opened directly in a browser or deployed as a static Vercel project.

## License

Private/proprietary project for the project owner unless changed by the owner.
