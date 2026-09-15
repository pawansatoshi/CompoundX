-- CompoundX PostgreSQL schema. Apply once to the production database.
-- Secrets are never stored in plaintext.

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
  password_hash TEXT NOT NULL,
  totp_secret_encrypted BYTEA,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS access_codes (
  id UUID PRIMARY KEY,
  code_hash TEXT UNIQUE NOT NULL,
  created_by UUID NOT NULL REFERENCES users(id),
  expires_at TIMESTAMPTZ NOT NULL,
  redeemed_at TIMESTAMPTZ,
  redeemed_by UUID REFERENCES users(id),
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (redeemed_at IS NULL OR redeemed_by IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS audit_events (
  id BIGSERIAL PRIMARY KEY,
  event_hash TEXT NOT NULL,
  action TEXT NOT NULL,
  actor TEXT NOT NULL,
  outcome TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS trades (
  id UUID PRIMARY KEY,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('LONG', 'SHORT')),
  quantity NUMERIC NOT NULL CHECK (quantity > 0),
  entry_price NUMERIC NOT NULL CHECK (entry_price > 0),
  exit_price NUMERIC,
  realized_pnl NUMERIC NOT NULL DEFAULT 0,
  fees NUMERIC NOT NULL DEFAULT 0,
  slippage NUMERIC NOT NULL DEFAULT 0,
  mode TEXT NOT NULL CHECK (mode IN ('PAPER', 'LIVE')),
  status TEXT NOT NULL CHECK (status IN ('OPEN', 'CLOSED', 'CANCELLED')),
  opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS trade_lessons (
  id UUID PRIMARY KEY,
  trade_id UUID NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
  fingerprint TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  regime TEXT NOT NULL,
  setup TEXT NOT NULL,
  won BOOLEAN NOT NULL,
  mistake TEXT NOT NULL,
  solution TEXT NOT NULL,
  confidence NUMERIC NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS learning_reviews (
  id BIGSERIAL PRIMARY KEY,
  trade_id UUID REFERENCES trades(id) ON DELETE SET NULL,
  fingerprint TEXT NOT NULL,
  base_score INTEGER NOT NULL CHECK (base_score BETWEEN 0 AND 9),
  adjusted_score INTEGER NOT NULL CHECK (adjusted_score BETWEEN 0 AND 9),
  adjustment INTEGER NOT NULL CHECK (adjustment BETWEEN -2 AND 2),
  blocked BOOLEAN NOT NULL,
  matched_lessons INTEGER NOT NULL DEFAULT 0,
  rationale TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rate_limits (
  bucket_key TEXT PRIMARY KEY,
  window_started_at TIMESTAMPTZ NOT NULL,
  request_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_access_codes_expiry ON access_codes (expires_at);
CREATE INDEX IF NOT EXISTS idx_audit_events_created_at ON audit_events (created_at);
CREATE INDEX IF NOT EXISTS idx_trades_opened_at ON trades (opened_at);
CREATE INDEX IF NOT EXISTS idx_rate_limits_window ON rate_limits (window_started_at);
CREATE INDEX IF NOT EXISTS idx_trade_lessons_fingerprint ON trade_lessons (fingerprint, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trade_lessons_trade ON trade_lessons (trade_id);
CREATE INDEX IF NOT EXISTS idx_learning_reviews_created_at ON learning_reviews (created_at DESC);
