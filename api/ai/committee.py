import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from compoundx.ai_committee import decision_dict, evaluate_committee
from compoundx.db import connection, is_configured
from compoundx.learning import fingerprint
from compoundx.vercel_http import bearer_claims, read_json, send_json


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            bearer_claims(self)
            body = read_json(self)
            context = body.get("context")
            if not isinstance(context, dict):
                raise ValueError("context must be an object")
            result = decision_dict(evaluate_committee(context))
            if is_configured():
                with connection() as conn:
                    conn.execute(
                        "INSERT INTO ai_committee_reviews(fingerprint,decision,direction,score,agreement,historical_edge,reasons,votes,live_execution_allowed) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,FALSE)",
                        (fingerprint(context), result["decision"], result["direction"], result["score"], result["agreement"], result["historical_edge"], json.dumps(result["reasons"]), json.dumps(result["votes"])),
                    )
            send_json(self, result)
        except PermissionError as exc:
            send_json(self, {"detail": str(exc)}, 401)
        except ValueError as exc:
            send_json(self, {"detail": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"detail": str(exc)}, 500)
