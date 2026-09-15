from __future__ import annotations

"""Quality-weighted, fail-closed evidence committee.

The committee is deterministic: ML may supply calibrated probabilities later,
but no opaque model can bypass risk, execution or validation controls.
Derivatives/options are advisory evidence, never mandatory availability gates.
"""
from dataclasses import dataclass
from math import exp, isfinite, log
from typing import Any
from .economic_calendar import committee_calendar_gate
from .expiry import analyze_expiries
from .liquidity import analyze_multi_timeframe_liquidity
from .probability import log_odds_pool

MIN_HISTORY=20
MIN_EDGE=.68
MIN_AGREEMENT=.75
MIN_RR=1.5
MAX_SPREAD_BPS=35.0
MAX_SLIPPAGE_BPS=20.0

@dataclass(frozen=True)
class Vote:
    model:str; direction:int; strength:float; reason:str; quality:float=1.0; cluster:str='uncategorized'

@dataclass(frozen=True)
class CommitteeDecision:
    decision:str; direction:int; score:float; agreement:float; edge:float; reasons:tuple[str,...]; votes:tuple[Vote,...]
    liquidity:dict[str,Any]|None=None; expiry:dict[str,Any]|None=None; probability:dict[str,Any]|None=None

def _clamp(v:Any,lo=-1.,hi=1.):
    try: x=float(v)
    except (TypeError,ValueError): return 0.
    return max(lo,min(hi,x)) if isfinite(x) else 0.

def _q(context:dict[str,Any],name:str)->float:
    q=context.get(f'{name}_quality',context.get('evidence_quality',1.0))
    return max(0.,min(1.,float(q or 0)))

def _vote(name,value,reason,context,cluster):
    x=_clamp(value); return Vote(name,1 if x>0 else -1 if x<0 else 0,abs(x),reason,_q(context,name),cluster)

def _history_edge(context):
    n=int(context.get('history_count',0) or 0); wr=float(context.get('history_win_rate',0) or 0); ex=float(context.get('history_expectancy',0) or 0)
    if n<MIN_HISTORY:return 0.,0,f'insufficient comparable history ({n}/{MIN_HISTORY})'
    if not 0<=wr<=1:return 0.,0,'invalid historical win rate'
    edge=max(0.,min(1.,.5*wr+.5*(1. if ex>0 else 0.)))
    d=1 if _clamp(context.get('history_direction',context.get('direction',0)))>0 else -1 if _clamp(context.get('history_direction',context.get('direction',0)))<0 else 0
    return edge,d,f'history n={n}, win_rate={wr:.2%}, expectancy={ex:.4g}'

def evaluate_committee(context:dict[str,Any])->CommitteeDecision:
    direction=1 if context.get('direction',0)>0 else -1 if context.get('direction',0)<0 else 0; reasons=[]
    regime=str(context.get('regime','UNKNOWN')).upper()
    if regime=='UNKNOWN': reasons.append('unknown regime')
    liquidity=context.get('liquidity_matrix') if isinstance(context.get('liquidity_matrix'),dict) else None
    liquidity_score=_clamp(liquidity.get('score',0) if liquidity else context.get('liquidity_score',0))
    if liquidity and not liquidity.get('usable',False): reasons.append(str(liquidity.get('reason','liquidity rejected')))
    elif not liquidity and 'liquidity_score' not in context: reasons.append('missing multi-timeframe liquidity evidence')
    expiry=context.get('expiry_analysis')
    if not isinstance(expiry,dict) and context.get('expiry_instruments') is not None: expiry=analyze_expiries(context.get('expiry_instruments'),market_type=str(context.get('market_type','derivative')))
    if not isinstance(expiry,dict): expiry=analyze_expiries(None,market_type='spot' if str(context.get('market_type','')).lower() in {'spot','cash'} else 'spot')
    if isinstance(context.get('economic_calendar'),dict):
        passed,rs=committee_calendar_gate(context['economic_calendar'])
        if not passed: reasons.extend(rs)
    votes=[
      _vote('regime',context.get('regime_score',0),f'regime={regime}',context,'price'),
      _vote('trend',context.get('trend_score',0),'trend confirmation',context,'price'),
      _vote('momentum',context.get('momentum_score',0),'momentum confirmation',context,'price'),
      _vote('volatility',context.get('volatility_score',0),'volatility quality',context,'volatility'),
      _vote('liquidity',liquidity_score,'liquidity quality',context,'flow'),
      _vote('structure',context.get('structure_score',0),'market structure',context,'price'),
      _vote('news',context.get('news_score',0),'news/sentiment',context,'event'),
    ]
    he,hd,hr=_history_edge(context); votes.append(Vote('history',1 if he>0 and hd==direction else -1 if he>0 and hd and hd!=direction else 0,he,hr,_q(context,'history'),'historical'))
    es=1. if expiry.get('status')=='NOT_APPLICABLE' else _clamp(expiry.get('score',0)); votes.append(_vote('expiry',es,str(expiry.get('reason','expiry reviewed')),context,'derivatives'))
    econ=context.get('economic_calendar')
    if isinstance(econ,dict): votes.append(_vote('economic_calendar',0 if not econ.get('usable') else max(0.,1-float(econ.get('risk_score',0))),str(econ.get('reason','macro reviewed')),context,'event'))
    # Optional derivatives/options confirmation: neutral when unavailable, never a hard blocker.
    deriv=context.get('derivatives_advisory') or {}; db=_clamp(deriv.get('bias',0)); votes.append(_vote('derivatives',db,'futures positioning (advisory)',context,'flow'))
    opt=context.get('options_advisory') or {}; ob=_clamp(opt.get('bias',0)); votes.append(_vote('options',ob,'options/expiry positioning (advisory)',context,'derivatives'))
    payload=[{'model':v.model,'direction':v.direction,'magnitude':v.strength,'quality':v.quality,'cluster':v.cluster} for v in votes]
    pooled=log_odds_pool(payload); p=pooled['probability'] if direction>0 else 1-pooled['probability']
    active=[v for v in votes if v.direction]; aligned=[v for v in active if v.direction==direction]; agreement=len(aligned)/len(active) if active else 0
    score=max(0.,min(1.,p)); reasons.extend([] if active else ['no directional consensus'])
    if he<MIN_EDGE: reasons.append('historical edge below threshold')
    if hd not in (0,direction): reasons.append('historical direction conflicts')
    if agreement<MIN_AGREEMENT: reasons.append(f'model agreement {agreement:.1%} below {MIN_AGREEMENT:.0%}')
    rr=float(context.get('risk_reward',0) or 0)
    if rr<MIN_RR: reasons.append(f'risk/reward {rr:.2f} below {MIN_RR:.2f}')
    if float(context.get('spread_bps',0) or 0)>MAX_SPREAD_BPS: reasons.append('spread too wide')
    if float(context.get('expected_slippage_bps',0) or 0)>MAX_SLIPPAGE_BPS: reasons.append('expected slippage too high')
    if not context.get('risk_ok',False): reasons.append('risk firewall rejected candidate')
    if _clamp(context.get('adversarial_score',0))<0: reasons.append('adversarial review found a strong failure case')
    if not context.get('execution_ok',False): reasons.append('execution-quality gate failed')
    if pooled['ci_low']>0 and (p<.60 or (direction>0 and pooled['ci_low']<.55) or (direction<0 and pooled['ci_high']>.45)): reasons.append('probability uncertainty too high')
    decision='TRADE' if direction and not reasons else 'NO_TRADE'
    return CommitteeDecision(decision,direction,round(score,6),round(agreement,6),round(he,6),tuple(dict.fromkeys(reasons)),tuple(votes),liquidity,expiry,pooled)

def decision_dict(r:CommitteeDecision)->dict[str,Any]:
    return {'decision':r.decision,'direction':r.direction,'direction_label':'LONG' if r.direction>0 else 'SHORT' if r.direction<0 else 'NONE','score':r.score,'agreement':r.agreement,'historical_edge':r.edge,'reasons':list(r.reasons),'votes':[{'model':v.model,'direction':v.direction,'strength':round(v.strength,6),'quality':round(v.quality,6),'cluster':v.cluster,'reason':v.reason} for v in r.votes],'liquidity':r.liquidity,'expiry':r.expiry,'probability':r.probability,'live_execution':False}
