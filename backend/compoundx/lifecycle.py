from __future__ import annotations

"""Persistable strategy lifecycle policy: research -> validation -> paper -> promotion/demotion."""
from typing import Any

STATES=('RESEARCHING','BACKTESTED','WALK_FORWARD_PASSED','PAPER','PROMOTED','DEGRADED','DEMOTED','RETIRED')

def evaluate_lifecycle(metrics:dict[str,Any], current:str='RESEARCHING')->dict[str,Any]:
    n=int(metrics.get('samples',metrics.get('trade_count',0)) or 0)
    oos=float(metrics.get('oos_positive_split_rate',0) or 0)
    sig=bool(metrics.get('significant',False)); robust=bool(metrics.get('robust',False)); regimes=int(metrics.get('regime_count',0) or 0)
    ece=float(metrics.get('ece',1) or 1); stress=bool(metrics.get('stress_passed',False))
    failures=[]
    if n<30: failures.append('insufficient research sample')
    if not sig: failures.append('statistical significance not established')
    if not robust: failures.append('Monte Carlo robustness not established')
    if oos<.60: failures.append('walk-forward OOS consistency below 60%')
    if regimes<3: failures.append('insufficient regime coverage')
    if ece>.10: failures.append('calibration error too high')
    if not stress: failures.append('execution stress validation not passed')
    if current=='RESEARCHING' and not failures: nxt='BACKTESTED'
    elif current in {'BACKTESTED','WALK_FORWARD_PASSED'} and not failures: nxt='PAPER'
    elif current=='PAPER' and not failures and n>=100: nxt='PROMOTED'
    elif current in {'PROMOTED','PAPER'} and (oos<.40 or metrics.get('degraded',False)): nxt='DEGRADED'
    elif current=='DEGRADED' and (oos<.30 or metrics.get('retire',False)): nxt='RETIRED'
    else: nxt=current
    return {'state':nxt,'passed':not failures,'failures':failures,'promotion_ready':nxt=='PROMOTED','policy':'evidence-based; calendar days alone never promote a strategy'}
