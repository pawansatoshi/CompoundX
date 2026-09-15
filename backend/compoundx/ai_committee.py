from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from typing import Any
from .economic_calendar import committee_calendar_gate
from .expiry import analyze_expiries
from .probability import log_odds_pool
MIN_HISTORY=20; MIN_EDGE=.68; MIN_AGREEMENT=.75; MIN_RR=1.5; MAX_SPREAD_BPS=35.; MAX_SLIPPAGE_BPS=20.
@dataclass(frozen=True)
class Vote:
    model:str; direction:int; strength:float; reason:str; quality:float=1.; cluster:str='uncategorized'
@dataclass(frozen=True)
class CommitteeDecision:
    decision:str; direction:int; score:float; agreement:float; edge:float; reasons:tuple[str,...]; votes:tuple[Vote,...]; liquidity:dict[str,Any]|None=None; expiry:dict[str,Any]|None=None; probability:dict[str,Any]|None=None
def _clamp(v:Any,lo=-1.,hi=1.):
    try:x=float(v)
    except:return 0.
    return max(lo,min(hi,x)) if isfinite(x) else 0.
def _q(c,n): return max(0.,min(1.,float(c.get(f'{n}_quality',c.get('evidence_quality',1.)) or 0)))
def _vote(n,v,r,c,cluster):
    x=_clamp(v); return Vote(n,1 if x>0 else -1 if x<0 else 0,abs(x),r,_q(c,n),cluster)
def _history_edge(c):
    n=int(c.get('history_count',0) or 0); wr=float(c.get('history_win_rate',0) or 0); ex=float(c.get('history_expectancy',0) or 0)
    if n<MIN_HISTORY:return 0.,0,f'insufficient comparable history ({n}/{MIN_HISTORY})'
    if not 0<=wr<=1:return 0.,0,'invalid historical win rate'
    d=c.get('history_direction',c.get('direction',0)); d=1 if d>0 else -1 if d<0 else 0
    return max(0.,min(1.,.5*wr+.5*(1 if ex>0 else 0))),d,f'history n={n}, win_rate={wr:.2%}, expectancy={ex:.4g}'
def evaluate_committee(c:dict[str,Any])->CommitteeDecision:
    direction=1 if c.get('direction',0)>0 else -1 if c.get('direction',0)<0 else 0; reasons=[]; regime=str(c.get('regime','UNKNOWN')).upper()
    if regime=='UNKNOWN':reasons.append('unknown regime')
    liquidity=c.get('liquidity_matrix') if isinstance(c.get('liquidity_matrix'),dict) else None; ls=_clamp(liquidity.get('score',0) if liquidity else c.get('liquidity_score',0))
    if liquidity and not liquidity.get('usable',False):reasons.append(str(liquidity.get('reason','liquidity rejected')))
    elif not liquidity and 'liquidity_score' not in c:reasons.append('missing multi-timeframe liquidity evidence')
    expiry=c.get('expiry_analysis');
    if not isinstance(expiry,dict):expiry=analyze_expiries(c.get('expiry_instruments'),market_type='spot' if str(c.get('market_type','')).lower() in {'spot','cash'} else 'spot')
    econ=c.get('economic_calendar')
    if isinstance(econ,dict):
        passed,rs=committee_calendar_gate(econ)
        if not passed:reasons.extend(rs)
    votes=[_vote('regime',c.get('regime_score',0),f'regime={regime}',c,'price'),_vote('trend',c.get('trend_score',0),'trend confirmation',c,'price'),_vote('momentum',c.get('momentum_score',0),'momentum confirmation',c,'price'),_vote('volatility',c.get('volatility_score',0),'volatility quality',c,'volatility'),_vote('liquidity',ls,'liquidity quality',c,'flow'),_vote('structure',c.get('structure_score',0),'market structure',c,'price'),_vote('news',c.get('news_score',0),'news/sentiment',c,'event')]
    he,hd,hr=_history_edge(c)
    if he==0 and int(c.get('history_count',0) or 0)<MIN_HISTORY:reasons.append(hr)
    votes.append(Vote('history',1 if he>0 and hd==direction else -1 if he>0 and hd and hd!=direction else 0,he,hr,_q(c,'history'),'historical'))
    es=1. if expiry.get('status')=='NOT_APPLICABLE' else _clamp(expiry.get('score',0));votes.append(_vote('expiry',es,str(expiry.get('reason','expiry reviewed')),c,'derivatives'))
    if isinstance(econ,dict):votes.append(_vote('economic_calendar',0 if not econ.get('usable') else max(0.,1-float(econ.get('risk_score',0))),str(econ.get('reason','macro reviewed')),c,'event'))
    da=c.get('derivatives_advisory') or {};oa=c.get('options_advisory') or {};votes.append(_vote('derivatives',da.get('bias',0),'futures positioning advisory',c,'flow'));votes.append(_vote('options',oa.get('bias',0),'options positioning advisory',c,'derivatives'))
    pooled=log_odds_pool([{'model':v.model,'direction':v.direction,'magnitude':v.strength,'quality':v.quality,'cluster':v.cluster} for v in votes]);p=pooled['probability'] if direction>0 else 1-pooled['probability'];active=[v for v in votes if v.direction];aligned=[v for v in active if v.direction==direction];agreement=len(aligned)/len(active) if active else 0
    if he<MIN_EDGE:reasons.append('historical edge below threshold')
    if hd not in (0,direction):reasons.append('historical direction conflicts')
    if agreement<MIN_AGREEMENT:reasons.append(f'model agreement {agreement:.1%} below {MIN_AGREEMENT:.0%}')
    if float(c.get('risk_reward',0) or 0)<MIN_RR:reasons.append('risk/reward below threshold')
    if float(c.get('spread_bps',0) or 0)>MAX_SPREAD_BPS:reasons.append('spread too wide')
    if float(c.get('expected_slippage_bps',0) or 0)>MAX_SLIPPAGE_BPS:reasons.append('expected slippage too high')
    if not c.get('risk_ok',False):reasons.append('risk firewall rejected candidate')
    if _clamp(c.get('adversarial_score',0))<0:reasons.append('adversarial review found a strong failure case')
    if not c.get('execution_ok',False):reasons.append('execution-quality gate failed')
    if p<.60:reasons.append('calibrated probability below threshold')
    return CommitteeDecision('TRADE' if direction and not reasons else 'NO_TRADE',direction,round(p,6),round(agreement,6),round(he,6),tuple(dict.fromkeys(reasons)),tuple(votes),liquidity,expiry,pooled)
def decision_dict(r:CommitteeDecision)->dict[str,Any]:
    return {'decision':r.decision,'direction':r.direction,'direction_label':'LONG' if r.direction>0 else 'SHORT' if r.direction<0 else 'NONE','score':r.score,'agreement':r.agreement,'historical_edge':r.edge,'reasons':list(r.reasons),'votes':[{'model':v.model,'direction':v.direction,'strength':round(v.strength,6),'quality':round(v.quality,6),'cluster':v.cluster,'reason':v.reason} for v in r.votes],'liquidity':r.liquidity,'expiry':r.expiry,'probability':r.probability,'live_execution':False}
