# CompoundX Strategy V1

## Objective
Target disciplined compounding of realized net P&L. 6–8% is an aspirational target band, never a guaranteed daily return.

## Timeframes
- Regime: 1h
- Setup: 15m
- Trigger: 5m

## Regime states
1. BULL_TREND: close > EMA200, EMA20 > EMA50 > EMA200, ADX filter when available.
2. BEAR_TREND: inverse conditions.
3. RANGE: price oscillating around VWAP/mean with compressed ATR and no persistent EMA separation.
4. HIGH_VOLATILITY: ATR/price above configured threshold or abnormal volume.
5. UNKNOWN: insufficient or inconsistent data.

UNKNOWN and HIGH_VOLATILITY default to NO_TRADE.

## Trend pullback long
Required score >= 7/9:
- trend alignment +2
- VWAP alignment +1
- market structure HH/HL +2
- volume confirmation +1
- momentum confirmation +1
- pullback/retest trigger +2

Short is the inverse.

## Breakout/retest
- identify confirmed range boundary
- require close outside boundary
- wait for retest
- reject false breakout if price closes back inside range
- require volume/momentum confirmation
- score >= 7/9

## Range reversion
Only in RANGE regime:
- enter near statistically defined range edge
- require momentum exhaustion and rejection
- stop outside range invalidation
- do not use during HIGH_VOLATILITY or trend regime

## Risk
- 0.50% account risk per trade starting default
- maximum 3 concurrent positions
- daily loss circuit breaker -2%
- maximum drawdown 10%
- no martingale
- no averaging down by default
- no forced trades

## Position sizing
risk_amount = equity * risk_per_trade
position_notional = risk_amount / abs(entry - stop)
Then enforce exchange minimums, maximum notional, leverage and portfolio exposure limits.

## Daily compounding
At daily close:
closing_equity = opening_equity + realized_net_pnl
realized_net_pnl includes fees and recorded slippage.
Next session's sizing uses closing_equity.
Unrealized P&L is not compounded until realized.

## Execution states
SIGNAL -> RISK_CHECK -> ORDER_PREP -> ORDER_SUBMIT -> ORDER_ACK -> POSITION_TRACK -> EXIT -> SETTLE
Any validation failure results in NO_TRADE / BLOCKED.
