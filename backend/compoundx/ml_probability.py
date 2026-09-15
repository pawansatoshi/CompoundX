from __future__ import annotations

"""Dependency-light logistic probability model for research.

The model is deliberately small and regularized. It is a probability estimator,
not a trade oracle. Training must use strictly out-of-sample/rolling data.
"""
from math import exp
from typing import Any

class LogisticModel:
    def __init__(self,features:list[str],lr=.05,l2=.01,epochs=300):
        self.features=features; self.lr=lr; self.l2=l2; self.epochs=epochs; self.weights=[0.0]*len(features); self.bias=0.0; self.fitted=False
    def _sig(self,z):
        z=max(-30,min(30,z)); return 1/(1+exp(-z))
    def predict_proba(self,row:dict[str,Any])->float:
        z=self.bias+sum(w*float(row.get(f,0) or 0) for f,w in zip(self.features,self.weights))
        return self._sig(z)
    def fit(self,rows:list[dict[str,Any]],labels:list[int|bool])->dict[str,Any]:
        if len(rows)!=len(labels) or len(rows)<30:return {'fitted':False,'samples':len(rows),'reason':'need >=30 aligned observations'}
        for _ in range(self.epochs):
            gw=[0.0]*len(self.features); gb=0.0
            for x,y in zip(rows,labels):
                p=self.predict_proba(x); err=p-(1 if y else 0); gb+=err
                for j,f in enumerate(self.features): gw[j]+=err*float(x.get(f,0) or 0)
            n=len(rows); self.bias-=self.lr*gb/n
            for j in range(len(self.weights)): self.weights[j]-=self.lr*(gw[j]/n+self.l2*self.weights[j])
        self.fitted=True
        return {'fitted':True,'samples':len(rows),'features':self.features,'weights':self.weights,'bias':self.bias,'policy':'research/OOS training only'}


def brier_score(probabilities:list[float],labels:list[int|bool])->float:
    if not probabilities or len(probabilities)!=len(labels): return 1.0
    return sum((max(0,min(1,float(p)))-(1 if y else 0))**2 for p,y in zip(probabilities,labels))/len(labels)
