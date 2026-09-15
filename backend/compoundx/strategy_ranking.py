from __future__ import annotations

"""Evidence-based strategy ranking; no ranking can override hard risk gates."""
from math import sqrt
from typing import Any


def _f(x, d=0.0):
    try:
        v=float(x); return v if v==v and abs(v)!=float('inf') else d
    except (TypeError,ValueError): return d


def rank_strategy(metrics: dict[str,Any], portfolio_fit: float=1.0, regime_fit: float=1.0) -> dict[str,Any]:
    # All inputs are bounded so a single flattering metric cannot dominate.
    exp=max(-1,min(1,_f(metrics.get('expectancy'))*100))
    sharpe=max(0,min(1,_f(metrics.get('sharpe'))/3))
    sortino=max(0,min(1,_f(metrics.get('sortino'))/4))
    pf=max(0,min(1,(_f(metrics.get('profit_factor'))-1)/2))
    dd=max(0,min(1,1-_f(metrics.get('max_drawdown'))/0.30))
    oos=max(0,min(1,_f(metrics.get('oos_positive_split_rate'),.5)))
    robust=max(0,min(1,_f(metrics.get('robust_score',metrics.get('robust',0.5)),.5)))
    cal=max(0,min(1,1-_f(metrics.get('ece'),.20)/.20))
    capacity=max(0,min(1,_f(metrics.get('capacity_score'),.5)))
    score=(.16*exp+.12*sharpe+.10*sortino+.10*pf+.16*dd+.14*oos+.10*robust+.06*cal+.06*capacity)*max(0,min(1,portfolio_fit))*max(0,min(1,regime_fit))
    return {'score':round(score,6),'confidence':round(min(1,0.35+0.65*min(1,_f(metrics.get('samples'))/200)),6),'health':round((oos+robust+cal)/3,6),'regime_fit':round(regime_fit,6),'portfolio_fit':round(portfolio_fit,6),'capacity':round(capacity,6),'degradation_score':round(max(0,1-(oos+robust+cal)/3),6),'components':{'expectancy':exp,'sharpe':sharpe,'sortino':sortino,'profit_factor':pf,'drawdown':dd,'oos':oos,'robustness':robust,'calibration':cal,'capacity':capacity}}


def rank_opportunities(candidates: list[dict[str,Any]]) -> list[dict[str,Any]]:
    ranked=[]
    for c in candidates:
        ev=_f(c.get('expected_value')); risk=max(_f(c.get('marginal_risk'),1),1e-6)
        quality=_f(c.get('confidence',.5)); liquidity=_f(c.get('liquidity_quality',.5)); decay=max(0,min(1,_f(c.get('time_to_decay_score',1),1)))
        score=(max(-1,min(1,ev))/risk)*(.4+.6*quality)*(.5+.5*liquidity)*decay
        ranked.append({**c,'opportunity_score':round(score,6)})
    return sorted(ranked,key=lambda x:x['opportunity_score'],reverse=True)
