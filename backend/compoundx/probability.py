from __future__ import annotations

"""Calibrated probability and quality-weighted evidence pooling."""
from math import exp, log
from typing import Any


def _f(x,d=0.0):
    try:
        v=float(x); return v if v==v and abs(v)!=float('inf') else d
    except (TypeError,ValueError): return d

def _clamp(x,lo=0.0,hi=1.0): return max(lo,min(hi,_f(x)))

def log_odds_pool(votes:list[dict[str,Any]])->dict[str,Any]:
    llr=0.0; mass=0.0; details=[]
    clusters={}
    for v in votes:
        d=1 if _f(v.get('direction'))>0 else -1 if _f(v.get('direction'))<0 else 0
        mag=_clamp(v.get('magnitude',v.get('strength',0)))
        q=_clamp(v.get('quality',v.get('weight',1)))
        cluster=str(v.get('cluster','uncategorized'))
        if d==0 or q<=0: continue
        clusters.setdefault(cluster,[]).append((d,mag,q))
    # one independent contribution per evidence cluster: strongest reliable view
    for cluster, rows in clusters.items():
        d,mag,q=max(rows,key=lambda x:x[1]*x[2])
        contribution=d*mag*q
        llr += contribution; mass += q
        details.append({'cluster':cluster,'direction':d,'magnitude':round(mag,4),'quality':round(q,4),'llr':round(contribution,4)})
    # Scale to a conservative probability. Saturation is intentionally limited.
    p=1/(1+exp(-2*llr)) if mass else .5
    coverage=min(1.0,len(details)/5.0)
    uncertainty=max(.0,1.0-min(1.0,abs(p-.5)*2))*0.25 + max(0,.7-coverage)*.25
    return {'probability':round(p,6),'ci_low':round(max(0,p-uncertainty),6),'ci_high':round(min(1,p+uncertainty),6),'evidence_mass':round(mass,6),'coverage':round(coverage,6),'clusters':details,'conflict':any(x['direction']!=details[0]['direction'] for x in details[1:]) if details else False}


def calibrate_probability(raw: float, calibration: dict[str,Any]|None=None)->float:
    # Optional Platt-style parameters; absent calibration is explicitly neutral.
    c=calibration or {}; p=_clamp(raw)
    a=_f(c.get('a'),1.0); b=_f(c.get('b'),0.0)
    logit=log(max(1e-6,p)/max(1e-6,1-p))
    return round(1/(1+exp(-(a*logit+b))),6)
