from fastapi import FastAPI

from .config import CONFIG

app = FastAPI(title="CompoundX API", version="0.1.0")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "paper_trading": CONFIG.paper_trading,
        "live_execution_enabled": CONFIG.live_execution_enabled,
        "withdrawals_enabled": CONFIG.withdrawals_enabled,
    }


@app.get("/risk/defaults")
def risk_defaults():
    return {
        "risk_per_trade": CONFIG.risk.risk_per_trade,
        "daily_loss_limit": CONFIG.risk.daily_loss_limit,
        "max_drawdown": CONFIG.risk.max_drawdown,
        "max_positions": CONFIG.risk.max_positions,
    }
