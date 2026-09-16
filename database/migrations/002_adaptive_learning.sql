-- CompoundX adaptive learning persistence. Safe to run repeatedly.
CREATE TABLE IF NOT EXISTS adaptive_decisions (
  id BIGSERIAL PRIMARY KEY,
  fingerprint TEXT NOT NULL,
  symbol TEXT NOT NULL,
  decision TEXT NOT NULL CHECK (decision IN ('TRADE','NO_TRADE')),
  direction SMALLINT NOT NULL CHECK (direction IN (-1,0,1)),
  probability NUMERIC CHECK (probability IS NULL OR (probability>=0 AND probability<=1)),
  probability_lower NUMERIC CHECK (probability_lower IS NULL OR (probability_lower>=0 AND probability_lower<=1)),
  net_expected_value NUMERIC,
  regime TEXT,
  strategy TEXT,
  thesis JSONB NOT NULL DEFAULT '{}'::jsonb,
  evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
  counterfactual JSONB NOT NULL DEFAULT '{}'::jsonb,
  self_critique JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS strategy_performance_snapshots (
  id BIGSERIAL PRIMARY KEY,
  strategy_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  regime TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  samples INTEGER NOT NULL DEFAULT 0 CHECK (samples>=0),
  expectancy NUMERIC NOT NULL DEFAULT 0,
  win_rate NUMERIC NOT NULL DEFAULT 0 CHECK (win_rate>=0 AND win_rate<=1),
  profit_factor NUMERIC NOT NULL DEFAULT 0,
  sharpe NUMERIC NOT NULL DEFAULT 0,
  brier NUMERIC,
  ece NUMERIC,
  capital_multiplier NUMERIC NOT NULL DEFAULT 0 CHECK (capital_multiplier>=0 AND capital_multiplier<=1),
  state TEXT NOT NULL DEFAULT 'PAPER',
  metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS execution_metrics (
  id BIGSERIAL PRIMARY KEY,
  exchange_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  mode TEXT NOT NULL CHECK (mode IN ('PAPER','LIVE')),
  order_id TEXT,
  expected_price NUMERIC,
  fill_price NUMERIC,
  expected_slippage_bps NUMERIC,
  realized_slippage_bps NUMERIC,
  latency_ms NUMERIC,
  fees NUMERIC,
  partial_fill_ratio NUMERIC CHECK (partial_fill_ratio IS NULL OR (partial_fill_ratio>=0 AND partial_fill_ratio<=1)),
  implementation_shortfall NUMERIC,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_adaptive_decisions_symbol_time ON adaptive_decisions(symbol,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_adaptive_decisions_fingerprint ON adaptive_decisions(fingerprint,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_perf_lookup ON strategy_performance_snapshots(strategy_id,symbol,regime,timeframe,observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_execution_metrics_lookup ON execution_metrics(exchange_id,symbol,created_at DESC);
