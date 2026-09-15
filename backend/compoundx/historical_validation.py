from __future__ import annotations

"""Reproducible OHLCV strategy backtest + walk-forward research runner."""
from typing import Any
from .strategy_engine import generate
from .research_engine import performance_metrics,monte_carlo_robustness,walk_forward_validate,rule_significance

def run_backtest(ohlcv:list[list[Any]],strategy:str,fee_bps:float=5.,slippage_bps:float=5.,holding_bars:int=12)->dict[str,Any]:
    if len(ohlcv)<100:return {'usable':False,'reason':f'insufficient historical candles ({len(ohlcv)}/100)'}
    h=[float(x[2]) for x in ohlcv]; l=[float(x[3]) for x in ohlcv]; c=[float(x[4]) for x in ohlcv]; v=[float(x[5]) for x in ohlcv]
    returns=[]; trades=[]; i=60
    cost=(fee_bps+slippage_bps)/10000*2
    while i+holding_bars<len(c):
        s=generate(h[:i+1],l[:i+1],c[:i+1],v[:i+1],strategy)
        if s['side']=='NONE': i+=1; continue
        entry=c[i]; exit_px=c[i+holding_bars]; raw=(exit_px/entry-1) if s['side']=='LONG' else (entry/exit_px-1)
        net=raw-cost; returns.append(net); trades.append({'bar':i,'strategy':strategy,'side':s['side'],'entry':entry,'exit':exit_px,'return_pct':net*100}); i+=holding_bars
    metrics=performance_metrics(returns,periods_per_year=max(1,365*24))
    mc=monte_carlo_robustness(returns); wf=walk_forward_validate(returns,train_size=min(200,max(30,len(returns)//3)),test_size=max(10,min(50,max(10,len(returns)//6)))) if len(returns)>=80 else {'usable':False,'reason':'insufficient trades for walk-forward'}
    sig=rule_significance(returns)
    return {'usable':True,'strategy':strategy,'trade_count':len(trades),'trades':trades,'metrics':metrics,'monte_carlo':mc,'walk_forward':wf,'significance':sig,'cost_model':{'fee_bps_roundtrip':fee_bps*2,'slippage_bps_roundtrip':slippage_bps*2},'research_only':True}


def run_strategy_suite(ohlcv:list[list[Any]],strategies:list[str]|None=None)->dict[str,Any]:
    names=strategies or ['trend_following','breakout','mean_reversion','momentum','volatility_expansion','volatility_contraction','liquidity_sweep_reversal']
    rows=[]
    for s in names:
        try: rows.append(run_backtest(ohlcv,s))
        except Exception as exc: rows.append({'usable':False,'strategy':s,'reason':str(exc)})
    usable=[x for x in rows if x.get('usable')]
    usable.sort(key=lambda x:(x.get('metrics',{}).get('sharpe',0),x.get('metrics',{}).get('expectancy',0)),reverse=True)
    return {'strategies':usable,'ranked':usable,'best':usable[0] if usable else None,'research_only':True,'policy':'no result enables live trading'}
