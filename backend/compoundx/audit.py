from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone


def audit_event(action: str, actor: str, outcome: str, metadata: dict | None = None) -> dict:
    safe = metadata or {}
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "actor": actor,
        "outcome": outcome,
        "metadata": safe,
    }
    payload["event_hash"] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return payload
