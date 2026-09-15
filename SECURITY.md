# CompoundX Security Policy

## Never commit
- exchange API keys or secrets
- passwords or passkeys
- database credentials
- JWT/session secrets
- seed phrases/private keys
- production environment files

## Trading safety
- paper trading is the default
- live execution is disabled by default
- withdrawals are disabled by design
- every live order must pass authentication, authorization, validation and the risk firewall
- any missing/invalid market data or risk state must fail closed

## Access
Admin operations require strong authentication and 2FA/passkey in production. Invitation codes are single-use, expiring, revocable and stored as hashes.

## Reporting
Do not publish credentials or exploit details in public issues. Report security problems privately to the project owner.
