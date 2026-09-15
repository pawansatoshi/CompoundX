# CompoundX self-learning trading layer

CompoundX now includes a bounded, auditable learning layer for paper trading.

## Loop

1. Build the current market/setup context.
2. Before a decision, retrieve comparable historical lessons by a stable setup fingerprint.
3. Apply a bounded advisory score adjustment of at most +/-2.
4. Re-run the normal signal threshold and risk firewall. Learning cannot bypass risk controls.
5. After a closed trade, record the outcome, detected mistake, proposed solution, evidence and confidence.
6. Persist the lesson and learning review in PostgreSQL for later retrieval.

## Safety invariants

- Learning is advisory and bounded.
- It cannot change hard risk limits.
- It cannot disable stop-loss or drawdown protection.
- It cannot enable live execution or withdrawals.
- Insufficient history produces no adjustment.
- Repeated historical failures can reduce a setup score and produce `NO TRADE` when the adjusted score falls below the existing strategy threshold.

## API

- `POST /api/learning/pre_trade` — authenticated pre-trade learning gate.
- `POST /api/learning/lessons` — authenticated post-trade lesson persistence.
- `POST /api/learning/review` — authenticated retrieval of comparable lessons.

The persistent database is the source of truth. A future worker can export immutable daily JSONL snapshots for external research/audit without making local serverless disk the source of truth.

## Example lesson

```json
{
  "pattern": "breakout_low_volume",
  "mistake": "entered_without_volume_confirmation",
  "solution": "require_volume_confirmation",
  "confidence": 0.84
}
```

This is an adaptive research component, not a guarantee of profitable trading.
