from __future__ import annotations

"""Actual strategy-family dispatch used by research/scanning.

These are research hypotheses, not claims of profitability. Each strategy emits a
candidate with transparent features so historical/OOS validation can test it.
"""
from typing import Any

STRATEGIES=('trend_following','breakout','mean_reversion','momentum','volatility_expansion','volatility_contraction','liquidity_sweep_reversal','funding_reversal','oi_divergence','event_driven')

def _f(x,d=0.):
    try:
        v=float(x); return v if v==v and abs(v)!=float('inf') else d
    except (TypeError,ValueError): return d

def _atr(h,l,c,n=14):
    if len(c)<n+1:return 0.
    return sum(max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])) for i in range(-n,0))/n

def generate(h:list[float],l:list[float],c:list[float],v:list[float],family:str,context:dict[str,Any]|None=None)->dict[str,Any]:
    context=context or {}; family=str(family); out={'strategy':family,'side':'NONE','score':0.,'reason':'no setup'}
    if len(c)<60:return out|{'reason':'insufficient history'}
    last=c[-1]; atr=_atr(h,l,c); avg=sum(v[-20:])/20 if v else 0.; vol_ratio=v[-1]/avg if avg else 1.
    ret20=last/c[-20]-1; ret5=last/c[-5]-1; mean20=sum(c[-20:])/20
    if family=='trend_following': side='LONG' if ret20>0 and last>mean20 else 'SHORT' if ret20<0 and last<mean20 else 'NONE'; score=min(1,abs(ret20)*8)
    elif family=='breakout': side='LONG' if last>max(h[-21:-1]) else 'SHORT' if last<min(l[-21:-1]) else 'NONE'; score=.8 if side!='NONE' and vol_ratio>1.1 else .4 if side!='NONE' else 0
    elif family=='mean_reversion': side='SHORT' if last>mean20*(1+max(.003,atr/max(last,1)*1.5)) else 'LONG' if last<mean20*(1-max(.003,atr/max(last,1)*1.5)) else 'NONE'; score=min(1,abs(last/mean20-1)*20)
    elif family=='momentum': side='LONG' if ret5>0 else 'SHORT' if ret5<0 else 'NONE'; score=min(1,abs(ret5)*15)
    elif family=='volatility_expansion': side='LONG' if ret5>0 and vol_ratio>1.5 else 'SHORT' if ret5<0 and vol_ratio>1.5 else 'NONE'; score=.75 if side!='NONE' else 0
    elif family=='volatility_contraction': side='LONG' if ret5>0 and vol_ratio<.8 else 'SHORT' if ret5<0 and vol_ratio<.8 else 'NONE'; score=.6 if side!='NONE' else 0
    elif family=='liquidity_sweep_reversal':
        sweep_low=last<min(l[-6:-1]) and last>l[-2]; sweep_high=last>max(h[-6:-1]) and last<h[-2]; side='LONG' if sweep_low else 'SHORT' if sweep_high else 'NONE'; score=.7 if side!='NONE' else 0
    elif family=='funding_reversal':
        f=_f(context.get('funding_rate')); side='SHORT' if f>.001 else 'LONG' if f<-.001 else 'NONE'; score=min(1,abs(f)*250)
    elif family=='oi_divergence':
        oi=_f(context.get('open_interest_change_pct')); side='LONG' if ret5<0 and oi<0 else 'SHORT' if ret5>0 and oi<0 else 'NONE'; score=.65 if side!='NONE' else 0
    elif family=='event_driven':
        ev=_f(context.get('event_surprise')); side='LONG' if ev>.5 else 'SHORT' if ev<-.5 else 'NONE'; score=min(1,abs(ev)/2)
    out.update({'side':side,'score':round(score,6),'atr':atr,'vol_ratio':vol_ratio,'reason':f'{family} hypothesis'})
    return out

def select_best(candidates:list[dict[str,Any]], regime:str='UNKNOWN')->dict[str,Any]:
    eligible={'TREND_UP':{'trend_following','momentum','breakout'},'TREND_DOWN':{'trend_following','momentum','breakout'},'RANGE':{'mean_reversion','liquidity_sweep_reversal','volatility_contraction'},'HIGH_VOLATILITY':{'volatility_expansion','liquidity_sweep_reversal'},'BREAKOUT_ATTEMPT':{'breakout','momentum','volatility_expansion'}}.get(regime.upper(),set(STRATEGIES))
    rows=[x for x in candidates if x.get('side')!='NONE' and x.get('strategy') in eligible]
    return max(rows,key=lambda x:float(x.get('score',0)),default={'strategy':'none','side':'NONE','score':0.,'reason':'no eligible strategy'})
