import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse
BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND) not in sys.path: sys.path.insert(0, str(BACKEND))
from compoundx.db import connection, is_configured
from compoundx.trade_chart import equity_curve, summarize_trades, trade_markers
from compoundx.vercel_http import send_json

def load_trades(symbol, limit):
    if not is_configured(): return []
    with connection() as conn:
        q = "SELECT id,symbol,side,quantity,entry_price,exit_price,realized_pnl,fees,slippage,mode,status,opened_at,closed_at FROM trades WHERE symbol=%s ORDER BY opened_at DESC LIMIT %s" if symbol else "SELECT id,symbol,side,quantity,entry_price,exit_price,realized_pnl,fees,slippage,mode,status,opened_at,closed_at FROM trades ORDER BY opened_at DESC LIMIT %s"
        cur = conn.execute(q, (symbol, limit) if symbol else (limit,))
        names = [d.name for d in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            p=parse_qs(urlparse(self.path).query); symbol=p.get("symbol",[None])[0]; limit=min(500,max(1,int(p.get("limit",[200])[0]))); rows=load_trades(symbol,limit)
            send_json(self,{"source":"postgresql" if is_configured() else "empty","symbol":symbol,"trades":trade_markers(rows),"summary":summarize_trades(rows),"equity_curve":equity_curve(rows),"paper_trading":True,"live_execution":False})
        except Exception as exc: send_json(self,{"detail":str(exc),"trades":[],"summary":summarize_trades([]),"equity_curve":[],"paper_trading":True,"live_execution":False},503)
