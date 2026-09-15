from __future__ import annotations

"""Per-candidate red-team challenge. Advisory evidence can veto a weak thesis only through the normal committee/risk path."""
from typing import Any

def _f(x,d=0.):
    try:
        v=float(x); return v if v==v and abs(v)!=float('inf') else d
    except (TypeError,ValueError): return d

def challenge(candidate:dict[str,Any], market:dict[str,Any]|None=None, derivatives:dict[str,Any]|None=None, options:dict[str,Any]|None=None)->dict[str,Any]:
    market=market or {}; derivatives=derivatives or {}; options=options or {}; failures=[]; warnings=[]
    direction=str(candidate.get('direction','')).upper()
    if _f(candidate.get('expected_slippage_bps'))*2 > _f(candidate.get('max_slippage_bps'),20): failures.append('2x slippage stress fails')
    if _f(candidate.get('risk_reward')) < 1.5: failures.append('risk/reward weak')
    if _f(candidate.get('confidence'),.5) < .55: failures.append('low confidence')
    if market.get('stale'): failures.append('market data stale')
    if derivatives.get('crowding')=='crowded_long' and direction=='LONG': warnings.append('futures long crowding contradicts LONG')
    if derivatives.get('crowding')=='crowded_short' and direction=='SHORT': warnings.append('futures short crowding contradicts SHORT')
    if _f(options.get('pcr')) and ((direction=='LONG' and _f(options.get('pcr'))<.5) or (direction=='SHORT' and _f(options.get('pcr'))>2)): warnings.append('options positioning is directionally contrary')
    if market.get('macro_risk') and _f(market.get('macro_risk'))>.8: failures.append('macro risk elevated')
    return {'passed':not failures,'failures':failures,'warnings':warnings,'stress_tests':{'slippage_2x':not any('slippage' in x for x in failures)},'decision':'REJECT' if failures else 'SURVIVES','policy':'red-team challenge; derivatives/options are advisory evidence'}
