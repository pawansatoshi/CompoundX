from __future__ import annotations

"""Portfolio-aware exposure, correlation and marginal-risk intelligence."""
from math import sqrt
from statistics import mean
from typing import Any


def _f(x: Any, default=0.0) -> float:
    try:
        v=float(x)
        return v if v == v and abs(v) != float('inf') else default
    except (TypeError, ValueError): return default


def _corr(a: list[float], b: list[float]) -> float:
    n=min(len(a),len(b))
    if n<3: return 0.0
    a,b=a[-n:],b[-n:]; ma,mb=mean(a),mean(b)
    da=[x-ma for x in a]; db=[x-mb for x in b]
    den=sqrt(sum(x*x for x in da)*sum(x*x for x in db))
    return sum(x*y for x,y in zip(da,db))/den if den else 0.0


def build_portfolio(open_positions: list[dict[str,Any]]|None, return_series: dict[str,list[float]]|None=None, candidate: dict[str,Any]|None=None) -> dict[str,Any]:
    positions=open_positions or []; series=return_series or {}; candidate=candidate or {}
    symbols=[str(p.get('symbol','')).upper() for p in positions if p.get('symbol')]
    exposures=[]
    for p in positions:
        qty=abs(_f(p.get('quantity'))); px=abs(_f(p.get('price',p.get('entry_price'))))
        exposures.append({'symbol':p.get('symbol'),'strategy':p.get('strategy','unknown'),'direction':p.get('direction',p.get('side','')),'notional':qty*px})
    matrix={}
    for s in symbols:
        matrix[s]={}
        for t in symbols: matrix[s][t]=round(_corr(series.get(s,[]),series.get(t,[])),4) if s!=t else 1.0
    cand_sym=str(candidate.get('symbol','')).upper()
    corr_to_book=max((abs(matrix.get(cand_sym,{}).get(s,0.0)) for s in symbols if s!=cand_sym),default=0.0)
    total=sum(x['notional'] for x in exposures)
    return {'positions':exposures,'position_count':len(exposures),'gross_notional':total,'correlation_matrix':matrix,'candidate_symbol':cand_sym,'candidate_max_abs_correlation':round(corr_to_book,4),'portfolio_heat':round(total/max(_f(candidate.get('equity'),1.0),1e-12),6),'correlation_adjustment':round(max(0.1,1.0-corr_to_book),4) if cand_sym else 1.0,'concentration_warning':corr_to_book>=0.85,'policy':'portfolio-aware; correlated positions count as concentrated exposure'}


def portfolio_risk_gate(portfolio: dict[str,Any], candidate_risk: float, max_heat: float=0.03, max_correlation: float=0.85) -> dict[str,Any]:
    heat=_f(portfolio.get('portfolio_heat')); corr=_f(portfolio.get('candidate_max_abs_correlation'))
    blockers=[]
    if heat+max(0.0,candidate_risk)>max_heat: blockers.append('portfolio heat limit')
    if corr>=max_correlation and portfolio.get('position_count',0)>0: blockers.append('candidate highly correlated with existing book')
    return {'passed':not blockers,'blockers':blockers,'marginal_risk':round(max(0.0,candidate_risk)*max(0.1,1.0-corr),6),'heat':heat,'max_heat':max_heat}
