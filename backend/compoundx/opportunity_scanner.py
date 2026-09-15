from __future__ import annotations

"""Small, deterministic multi-asset opportunity scanner. It ranks; it does not execute."""
from typing import Any
from .strategy_ranking import rank_opportunities

DEFAULT_UNIVERSE=('BTC/USDT','ETH/USDT','SOL/USDT','BNB/USDT','XRP/USDT','ADA/USDT','DOGE/USDT','AVAX/USDT','LINK/USDT','SUI/USDT')

def scan(universe:list[str]|None, evaluator, max_symbols:int=10)->dict[str,Any]:
    symbols=(universe or list(DEFAULT_UNIVERSE))[:max_symbols]; candidates=[]; errors=[]
    for symbol in symbols:
        try:
            row=evaluator(symbol)
            if isinstance(row,dict):
                candidates.append({'symbol':symbol,**row})
        except Exception as exc:
            errors.append({'symbol':symbol,'error':str(exc)})
    ranked=rank_opportunities(candidates)
    return {'symbols_checked':symbols,'opportunities':ranked,'errors':errors,'policy':'scanner ranks evidence; it never bypasses risk or execution gates'}
