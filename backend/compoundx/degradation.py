from __future__ import annotations

"""Automatic edge-degradation monitor; only reduces risk, never increases it."""
from typing import Any

def _f(x,d=0.):
    try:
        v=float(x); return v if v==v and abs(v)!=float('inf') else d
    except (TypeError,ValueError): return d

def monitor(metrics:dict[str,Any], baseline:dict[str,Any]|None=None)->dict[str,Any]:
    b=baseline or {}; alerts=[]; score=0.
    for key,weight in [('expectancy',.35),('sharpe',.20),('win_rate',.15),('profit_factor',.15),('oos_positive_split_rate',.15)]:
        cur=_f(metrics.get(key)); old=_f(b.get(key),cur)
        if old and cur < old*.70: alerts.append(f'{key} degraded >30%'); score += weight
    if _f(metrics.get('slippage_bps')) > _f(b.get('slippage_bps'),_f(metrics.get('slippage_bps')))*1.5 and _f(b.get('slippage_bps')): alerts.append('realized slippage elevated'); score += .15
    if _f(metrics.get('drawdown')) > _f(metrics.get('max_drawdown_budget'),1): alerts.append('drawdown budget exceeded'); score += .35
    action='NORMAL' if score<.20 else 'REDUCE_CAPITAL' if score<.45 else 'PAUSE_STRATEGY'
    return {'degraded':score>=.20,'score':round(min(1,score),4),'action':action,'alerts':alerts,'capital_multiplier':1.0 if score<.20 else .5 if score<.45 else 0.0,'policy':'one-way safety response; monitor cannot increase capital'}
