"""Zero-configuration Vercel FastAPI entrypoint for CompoundX."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from fastapi.responses import FileResponse

from compoundx.main import app as _app

app = _app


@app.get("/", include_in_schema=False)
def dashboard():
    """Serve the static command-center dashboard from the FastAPI app."""
    return FileResponse(ROOT / "index.html", media_type="text/html")
