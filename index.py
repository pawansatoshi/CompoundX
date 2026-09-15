"""Vercel FastAPI entrypoint.

The dashboard remains a static index.html at the project root, while this
recognized FastAPI entrypoint exposes the /api/* backend routes.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from compoundx.main import app
