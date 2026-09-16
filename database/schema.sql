-- CompoundX PostgreSQL schema. Apply once to the production database.
-- Secrets are never stored in plaintext.

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY, email TEXT UNIQUE NOT NULL, role TEXT NOT NULL CHECK (role IN ('admin','user')), password_hash TEXT NOT NULL,
  totp_secret_encrypted BYTEA, is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS access_codes (
  id UUID PRIMARY KEY, code_hash TEXT UNIQUE NOT NULL, created_by UUID NOT NULL REFERENCES users(id), expires_at TIMESTAMPTZ NOT NULL,
  redeemed_at TIMESTAMPTZ, redeemed_by UUID REFERENCES users(id), revoked_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), CHECK (redeemed_at IS NULL OR redeemed_by IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS audit_events (
  id BIGSERIAL PRIMARY KEY, event_hash TEXT NOT NULL, action TEXT NOT NULL, actor TEXT NOT NULL, outcome TEXT NOT NULL, metadata JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS trades (
  id UUID PRIMARY KEY, symbol TEXT NOT NULL, side TEXT NOT NULL CHECK (side IN ('LONG','SHORT')), quantity NUMERIC NOT NULL CHECK (quantity>0), entry_price NUMERIC NOT NULL CHECK (entry_price>0), exit_price NUMERIC,
  realized_pnl NUMERIC NOT NULL DEFAULT 0, fees NUMERIC NOT NULL DEFAULT 0, slippage NUMERIC NOT NULL DEFAULT 0, mode TEXT NOT NULL CHECK (mode IN ('PAPER','LIVE')), status TEXT NOT NULL CHECK (status IN ('OPEN','CLOSED','CANCELLED')), opened_at TIMESTAMPTZ NOT NULL DEFAULT now(), closed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS trade_lessons (
  id UUID PRIMARY KEY, trade_id UUID NOT NULL REFERENCES trades(id) ON DELETE CASCADE, fingerprint TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL, regime TEXT NOT NULL, setup TEXT NOT NULL,
  won BOOLEAN NOT NULL, mistake TEXT NOT NULL, solution TEXT NOT NULL, confidence NUMERIC NOT NULL CHECK (confidence>=0 AND confidence<=1), evidence JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS learning_reviews (
  id BIGSERIAL PRIMARY KEY, trade_id UUID REFERENCES trades(id) ON DELETE SET NULL, fingerprint TEXT NOT NULL, base_score INTEGER NOT NULL CHECK (base_score BETWEEN 0 AND 9), adjusted_score INTEGER NOT NULL CHECK (adjusted_score BETWEEN 0 AND 9), adjustment INTEGER NOT NULL CHECK (adjustment BETWEEN -2 AND 2), blocked BOOLEAN NOT NULL, matched_lessons INTEGER NOT NULL DEFAULT 0, rationale TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ai_committee_reviews (
  id BIGSERIAL PRIMARY KEY, fingerprint TEXT NOT NULL, decision TEXT NOT NULL CHECK (decision IN ('TRADE','NO_TRADE')), direction SMALLINT NOT NULL CHECK (direction IN (-1,0,1)), score NUMERIC NOT NULL CHECK (score>=0 AND score<=1), agreement NUMERIC NOT NULL CHECK (agreement>=0 AND agreement<=1), historical_edge NUMERIC NOT NULL CHECK (historical_edge>=0 AND historical_edge<=1), reasons JSONB NOT NULL DEFAULT '[]'::jsonb, votes JSONB NOT NULL DEFAULT '[]'::jsonb, live_execution_allowed BOOLEAN NOT NULL DEFAULT FALSE, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS validation_runs (
  id BIGSERIAL PRIMARY KEY, validation_type TEXT NOT NULL CHECK (validation_type IN ('BACKTEST','WALK_FORWARD','PAPER')), samples INTEGER NOT NULL CHECK (samples>=0), win_rate NUMERIC NOT NULL CHECK (win_rate>=0 AND win_rate<=1), expectancy NUMERIC NOT NULL, profit_factor NUMERIC NOT NULL, max_drawdown NUMERIC NOT NULL CHECK (max_drawdown>=0), sharpe NUMERIC NOT NULL, brier_score NUMERIC NOT NULL CHECK (brier_score>=0), calibration_error NUMERIC NOT NULL CHECK (calibration_error>=0), passed BOOLEAN NOT NULL, failures JSONB NOT NULL DEFAULT '[]'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS strategy_registry (
  strategy_id TEXT PRIMARY KEY, family TEXT NOT NULL, version TEXT NOT NULL, state TEXT NOT NULL,
  config JSONB NOT NULL DEFAULT '{}'::jsonb, metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  capital_multiplier NUMERIC NOT NULL DEFAULT 0 CHECK (capital_multiplier>=0 AND capital_multiplier<=1), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS specialist_calibration (
  specialist TEXT NOT NULL, regime TEXT NOT NULL, samples INTEGER NOT NULL DEFAULT 0,
  brier NUMERIC, ece NUMERIC, accuracy NUMERIC, reliability_weight NUMERIC, updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (specialist,regime)
);
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
  id BIGSERIAL PRIMARY KEY, equity NUMERIC NOT NULL, gross_notional NUMERIC NOT NULL DEFAULT 0,
  portfolio_heat NUMERIC NOT NULL DEFAULT 0, concentration NUMERIC NOT NULL DEFAULT 0,
  correlation_matrix JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS market_observations (
  id BIGSERIAL PRIMARY KEY, symbol TEXT NOT NULL, timeframe TEXT NOT NULL, observed_at TIMESTAMPTZ NOT NULL,
  source TEXT NOT NULL, freshness_seconds NUMERIC, quality NUMERIC NOT NULL CHECK (quality>=0 AND quality<=1), features JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS exchange_connections (
  id UUID PRIMARY KEY, user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  exchange_id TEXT NOT NULL, mode TEXT NOT NULL CHECK (mode IN ('DEMO','LIVE')),
  api_key_encrypted BYTEA NOT NULL, secret_encrypted BYTEA NOT NULL, passphrase_encrypted BYTEA,
  label TEXT NOT NULL DEFAULT '', enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(user_id, exchange_id, mode)
);
CREATE INDEX IF NOT EXISTS idx_exchange_connections_user ON exchange_connections(user_id,exchange_id,mode);

CREATE TABLE IF NOT EXISTS rate_limits (bucket_key TEXT PRIMARY KEY, window_started_at TIMESTAMPTZ NOT NULL, request_count INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_access_codes_expiry ON access_codes(expires_at);
CREATE INDEX IF NOT EXISTS idx_audit_events_created_at ON audit_events(created_at);
CREATE INDEX IF NOT EXISTS idx_trades_opened_at ON trades(opened_at);
CREATE INDEX IF NOT EXISTS idx_rate_limits_window ON rate_limits(window_started_at);
CREATE INDEX IF NOT EXISTS idx_trade_lessons_fingerprint ON trade_lessons(fingerprint,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trade_lessons_trade ON trade_lessons(trade_id);
CREATE INDEX IF NOT EXISTS idx_learning_reviews_created_at ON learning_reviews(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_committee_reviews_created_at ON ai_committee_reviews(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_committee_reviews_fingerprint ON ai_committee_reviews(fingerprint,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_validation_runs_created_at ON validation_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_registry_state ON strategy_registry(state);
CREATE INDEX IF NOT EXISTS idx_market_observations_symbol_time ON market_observations(symbol,timeframe,observed_at DESC);
