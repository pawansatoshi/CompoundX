from __future__ import annotations
"""Advisory futures/options confirmation. Availability never blocks a trade."""
from typing import Any

def _num(v:Any,d=0.):
    try:x=float(v);return x if x==x and abs(x)!=float('inf') else d
    except:return d

def derivatives_options_advisory(derivatives,expiry,expiry_market_data=None,direction=0):
    d=derivatives if isinstance(derivatives,dict) else {}; e=expiry if isinstance(expiry,dict) else {}; raw=expiry_market_data if isinstance(expiry_market_data,dict) else {}; warnings=[]; conflicts=[]; bias=0.; futures_available=bool(d.get('available',False))
    if futures_available:
        funding=_num(d.get('funding_rate')); oi=_num(d.get('open_interest_change_pct',d.get('oi_change_pct'))); basis=_num(d.get('basis_pct'))
        if funding>.001 and oi>0: bias-=.35; warnings.append('futures long crowding elevated')
        if funding<-.001 and oi>0: bias+=.35; warnings.append('futures short crowding elevated')
        if abs(basis)>1.: warnings.append('futures basis unusually wide')
    else:warnings.append('futures evidence unavailable; neutral contribution')
    chain=raw.get('instruments') if isinstance(raw.get('instruments'),list) else []; options=[x for x in chain if isinstance(x,dict) and (x.get('option') or x.get('optionType') or x.get('option_type'))]
    if options:
        calls=sum(_num(x.get('open_interest')) for x in options if str(x.get('optionType',x.get('option_type',''))).lower()=='call'); puts=sum(_num(x.get('open_interest')) for x in options if str(x.get('optionType',x.get('option_type',''))).lower()=='put'); pcr=puts/max(calls,1e-12)
        if direction>0 and pcr<.5: bias-=.2; conflicts.append('options put/call OI is weak for LONG confirmation')
        if direction<0 and pcr>2: bias+=.2; conflicts.append('options put/call OI is weak for SHORT confirmation')
        if e.get('status')=='AVAILABLE' and _num(e.get('days_to_expiry'))<=1:warnings.append('near-expiry positioning may increase volatility')
    else:warnings.append('listed options unavailable; neutral contribution')
    return {'available':futures_available or bool(options),'bias':round(max(-1,min(1,bias)),4),'warnings':list(dict.fromkeys(warnings)),'conflicts':list(dict.fromkeys(conflicts)),'futures_checked':True,'options_checked':True,'hard_block':False,'policy':'ADVISORY_ONLY'}

def final_derivatives_options_gate(derivatives,expiry,expiry_market_data=None):
    a=derivatives_options_advisory(derivatives,expiry,expiry_market_data)
    chain=(expiry_market_data or {}).get('instruments',[]) if isinstance(expiry_market_data,dict) else []; opts=[x for x in chain if isinstance(x,dict) and (x.get('option') or x.get('optionType') or x.get('option_type'))]
    oi=sum(1 for x in opts if _num(x.get('open_interest'))>0 and _num(x.get('volume'))>0 and _num(x.get('spread_bps'))<=35)
    opt={'checked':True,'available':bool(opts),'status':'AVAILABLE' if opts else 'NOT_AVAILABLE','instruments_checked':len(opts),'usable_instruments':oi,'iv_observations':sum(x.get('implied_volatility') is not None for x in opts),'delta_observations':sum(x.get('delta') is not None for x in opts),'gamma_observations':sum(x.get('gamma') is not None for x in opts),'theta_observations':sum(x.get('theta') is not None for x in opts),'vega_observations':sum(x.get('vega') is not None for x in opts),'rho_observations':sum(x.get('rho') is not None for x in opts)}
    return {'passed':True,'futures':{'checked':True,'available':bool((derivatives or {}).get('available',False))},'options':opt,'blockers':[],'warnings':a['warnings']+a['conflicts'],'advisory':a,'policy':'ADVISORY_ONLY'}
