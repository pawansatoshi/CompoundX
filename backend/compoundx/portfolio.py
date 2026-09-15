from __future__ import annotations
from math import sqrt
from statistics import mean
from typing import Any

def _f(x:Any,d=0.):
    try:v=float(x);return v if v==v and abs(v)!=float('inf') else d
    except:return d

def _corr(a,b):
    n=min(len(a),len(b))
    if n<3:return 0.
    a,b=a[-n:],b[-n:];ma,mb=mean(a),mean(b);da=[x-ma for x in a];db=[x-mb for x in b];den=sqrt(sum(x*x for x in da)*sum(x*x for x in db));return sum(x*y for x,y in zip(da,db))/den if den else 0.

def build_portfolio(open_positions=None,return_series=None,candidate=None):
    positions=open_positions or [];series=return_series or {};candidate=candidate or {}; symbols=[str(p.get('symbol','')).upper() for p in positions if p.get('symbol')]
    exposures=[]
    for p in positions: exposures.append({'symbol':p.get('symbol'),'strategy':p.get('strategy','unknown'),'direction':p.get('direction',p.get('side','')),'notional':abs(_f(p.get('quantity')))*abs(_f(p.get('price',p.get('entry_price'))))})
    matrix={s:{t:(1. if s==t else round(_corr(series.get(s,[]),series.get(t,[])),4)) for t in symbols} for s in symbols}
    cand=str(candidate.get('symbol','')).upper(); cand_returns=candidate.get('returns',[]); corr_to_book=max([abs(_corr(cand_returns,series.get(s,[]))) for s in symbols if cand_returns and len(series.get(s,[]))>=3],default=0.)
    total=sum(x['notional'] for x in exposures); equity=max(_f(candidate.get('equity'),1.),1e-12)
    return {'positions':exposures,'position_count':len(exposures),'gross_notional':total,'correlation_matrix':matrix,'candidate_symbol':cand,'candidate_max_abs_correlation':round(corr_to_book,4),'portfolio_heat':round(total/equity,6),'correlation_adjustment':round(max(.1,1-corr_to_book),4),'concentration_warning':corr_to_book>=.85,'policy':'portfolio-aware; correlated positions count as concentrated exposure'}

def portfolio_risk_gate(portfolio,candidate_risk,max_heat=.03,max_correlation=.85):
    heat=_f(portfolio.get('portfolio_heat'));corr=_f(portfolio.get('candidate_max_abs_correlation')); blockers=[]
    if heat+max(0.,candidate_risk)>max_heat:blockers.append('portfolio heat limit')
    if corr>=max_correlation and portfolio.get('position_count',0)>0:blockers.append('candidate highly correlated with existing book')
    return {'passed':not blockers,'blockers':blockers,'marginal_risk':round(max(0.,candidate_risk)*max(.1,1-corr),6),'heat':heat,'max_heat':max_heat}
