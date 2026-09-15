from compoundx.derivatives_gate import final_derivatives_options_gate,derivatives_options_advisory
from compoundx.probability import log_odds_pool
from compoundx.portfolio import build_portfolio,portfolio_risk_gate
from compoundx.strategy_ranking import rank_strategy
from compoundx.lifecycle import evaluate_lifecycle
from compoundx.degradation import monitor
from compoundx.strategy_engine import generate


def test_derivatives_options_are_advisory_only():
    r=final_derivatives_options_gate({'available':False},{'status':'UNKNOWN'}, {'instruments':[]})
    assert r['passed'] is True and r['blockers']==[] and r['policy']=='ADVISORY_ONLY'


def test_quality_pool_decorrelates_clusters():
    r=log_odds_pool([
        {'model':'trend','direction':1,'magnitude':.9,'quality':1,'cluster':'price'},
        {'model':'momentum','direction':1,'magnitude':.9,'quality':1,'cluster':'price'},
        {'model':'flow','direction':-1,'magnitude':.9,'quality':1,'cluster':'flow'},
    ])
    assert len(r['clusters'])==2 and r['conflict'] is True


def test_portfolio_correlation_limits():
    p=build_portfolio([{'symbol':'ETH/USDT','quantity':1,'entry_price':100}],{'ETH/USDT':[1,2,3],'BTC/USDT':[1,2,3]},{'symbol':'BTC/USDT','equity':100})
    assert p['candidate_max_abs_correlation']>0.99
    assert portfolio_risk_gate(p,.005)['passed'] is False


def test_ranking_is_bounded():
    r=rank_strategy({'expectancy':.01,'sharpe':2,'sortino':3,'profit_factor':1.8,'max_drawdown':.08,'oos_positive_split_rate':.8,'robust':True,'ece':.04,'samples':200})
    assert 0<=r['score']<=1 and 0<=r['health']<=1


def test_lifecycle_requires_real_evidence():
    r=evaluate_lifecycle({'samples':10,'significant':False,'robust':False,'oos_positive_split_rate':.2,'regime_count':1,'ece':.2,'stress_passed':False})
    assert r['promotion_ready'] is False and r['state']=='RESEARCHING'


def test_degradation_only_reduces_capital():
    r=monitor({'expectancy':.001},{'expectancy':.01})
    assert r['capital_multiplier']<=1 and r['action'] in {'NORMAL','REDUCE_CAPITAL','PAUSE_STRATEGY'}


def test_strategy_dispatch_is_real():
    c=[float(100+i*.5) for i in range(100)]; h=[x+1 for x in c]; l=[x-1 for x in c]; v=[100]*100
    r=generate(h,l,c,v,'trend_following')
    assert r['strategy']=='trend_following' and r['side'] in {'LONG','SHORT','NONE'}
