from __future__ import annotations

"""Advisory cross-market confirmation for futures, options and expiry.

Availability never blocks a trade. Contradictory derivatives evidence is surfaced
and can influence the quality-weighted committee, while hard risk/execution gates
remain authoritative.
"""
from typing import Any

def _num(value:Any,default=0.):
    try:
        v=float(value); return v if v==v and abs(v)!=float('inf') else default
    except (TypeError,ValueError): return default

def derivatives_options_advisory(derivatives:dict[str,Any]|None,expiry:dict[str,Any]|None,expiry_market_data:dict[str,Any]|None=None,direction:int=0)->dict[str,Any]:
    d=derivatives if isinstance(derivatives,dict) else {}; e=expiry if isinstance(expiry,dict) else {}; raw=expiry_market_data if isinstance(expiry_market_data,dict) else {}
    warnings=[]; conflicts=[]; bias=0.
    available=bool(d.get('available',False))
    if available:
        funding=_num(d.get('funding_rate')); oi=_num(d.get('open_interest_change_pct',d.get('oi_change_pct'))); basis=_num(d.get('basis_pct'))
        # Extreme positive funding + rising OI is a contrarian warning to LONG; vice versa SHORT.
        if funding>.001 and oi>0: bias -= .35; warnings.append('futures long crowding elevated')
        if funding<-.001 and oi>0: bias += .35; warnings.append('futures short crowding elevated')
        if abs(basis)>1: warnings.append('futures basis unusually wide')
    else: warnings.append('futures evidence unavailable; neutral contribution')
    chain=raw.get('instruments') if isinstance(raw.get('instruments'),list) else []
    options=[x for x in chain if isinstance(x,dict) and (x.get('option') or x.get('optionType') or x.get('option_type'))]
    if options:
        calls=sum(_num(x.get('open_interest')) for x in options if str(x.get('optionType',x.get('option_type',''))).lower()=='call')
        puts=sum(_num(x.get('open_interest')) for x in options if str(x.get('optionType',x.get('option_type',''))).lower()=='put')
        pcr=puts/max(calls,1e-12)
        if direction>0 and pcr<.5: bias-=.20; conflicts.append('options put/call OI is weak for LONG confirmation')
        if direction<0 and pcr>2: bias+=.20; conflicts.append('options put/call OI is weak for SHORT confirmation')
        if e.get('status')=='AVAILABLE' and _num(e.get('days_to_expiry'))<=1: warnings.append('near-expiry positioning may increase volatility')
    else: warnings.append('listed options unavailable; neutral contribution')
    return {'available':available or bool(options),'bias':round(max(-1,min(1,bias)),4),'warnings':list(dict.fromkeys(warnings)),'conflicts':list(dict.fromkeys(conflicts)),'futures_checked':True,'options_checked':True,'hard_block':False,'policy':'ADVISORY_ONLY'}


def final_derivatives_options_gate(derivatives,expiry,expiry_market_data=None):
    """Backward-compatible wrapper: always passes; exposes advisory evidence."""
    a=derivatives_options_advisory(derivatives,expiry,expiry_market_data)
    return {'passed':True,'futures':{'checked':True,'available':bool((derivatives or {}).get('available',False))},'options':{'checked':True,'available':a['available']},'blockers':[],'warnings':a['warnings']+a['conflicts'],'advisory':a,'policy':'ADVISORY_ONLY; unavailable or weak futures/options evidence never blocks a candidate'}
