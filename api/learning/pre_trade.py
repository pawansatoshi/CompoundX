import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from compoundx.config import CONFIG
from compoundx.db import connection, is_configured
from compoundx.learning import fingerprint, pre_trade_check
from compoundx.vercel_http import bearer_claims, read_json, send_json


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            if not is_configured():
                send_json(self, {"detail": "Database is not configured"}, 503)
                return
            bearer_claims(self)
            body = read_json(self)
            context = body.get("context") or {}
            base_score = int(body.get("base_score", 0))
            if not 0 <= base_score <= 9:
                raise ValueError("base_score must be 0..9")
            result = pre_trade_check(context, base_score, CONFIG.strategy.minimum_signal_score)
            with connection() as conn:
                conn.execute(
                    "INSERT INTO learning_reviews(trade_id,fingerprint,base_score,adjusted_score,adjustment,blocked,matched_lessons,rationale) VALUES(NULL,%s,%s,%s,%s,%s,%s,%s)",
                    (fingerprint(context), result["base_score"], result["adjusted_score"], result["learning"]["adjustment"], result["blocked"], result["learning"]["similar_trades"], result["reason"]),
                )
            send_json(self, result)
        except PermissionError as exc:
            send_json(self, {"detail": str(exc)}, 401)
        except ValueError as exc:
            send_json(self, {"detail": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"detail": str(exc)}, 500)
