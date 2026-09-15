from __future__ import annotations

"""Lightweight regime persistence and change-point detection."""
from statistics import mean
from typing import Any

def _f(x):
    try:return float(x)
    except:return 0.

def detect_change_point(returns:list[float],window:int=20,threshold:float=2.5)->dict[str,Any]:
    if len(returns)<window*2:return {'usable':False,'changed':False,'reason':'insufficient regime history'}
    a=[_f(x) for x in returns[-2*window:-window]]; b=[_f(x) for x in returns[-window:]]; ma,mb=mean(a),mean(b)
    va=mean((x-ma)**2 for x in a); vb=mean((x-mb)**2 for x in b); pooled=max((va+vb)/2,1e-12)
    z=abs(mb-ma)/(pooled**.5)
    return {'usable':True,'changed':z>=threshold,'z_score':round(z,4),'mean_shift':round(mb-ma,8),'variance_ratio':round(vb/max(va,1e-12),4),'reason':'regime change detected' if z>=threshold else 'no material change detected'}

def regime_persistence(labels:list[str],lookback:int=20)->dict[str,Any]:
    if not labels:return {'usable':False,'persistence':0.}
    x=labels[-lookback:]; last=x[-1]; return {'usable':True,'regime':last,'persistence':round(sum(v==last for v in x)/len(x),4),'transition':sum(v!=last for v in x[-5:])/min(5,len(x))>=.6}
