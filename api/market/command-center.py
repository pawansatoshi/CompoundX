import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs,urlparse
BACKEND=Path(__file__).resolve().parents[2]/'backend'
if str(BACKEND) not in sys.path: sys.path.insert(0,str(BACKEND))
from compoundx.autonomous_intelligence import build_autonomous_intelligence
from compoundx.adaptive_intelligence import adaptive_snapshot,calibrated_probability,counterfactual_matrix,dynamic_risk_size,evidence_dependency,regime_distribution,self_critique,signal_half_life
from compoundx.db import connection,is_configured
from compoundx.derivatives_gate import final_derivatives_options_gate,derivatives_options_advisory
from compoundx.economic_calendar import committee_calendar_gate,fetch_calendar
from compoundx.exchange import ExchangeGateway
from compoundx.expiry import analyze_expiries
from compoundx.market_intelligence import build_command_center
from compoundx.research_engine import build_research_intelligence
from compoundx.trade_chart import equity_curve,summarize_trades,trade_markers
from compoundx.portfolio import build_portfolio,portfolio_risk_gate
from compoundx.strategy_ranking import rank_strategy
from compoundx.degradation import monitor as degradation_monitor
from compoundx.adversarial import challenge as adversarial_challenge
from compoundx.strategy_engine import STRATEGIES,generate,select_best
from compoundx.historical_validation import run_backtest
from compoundx.vercel_http import read_json,send_json


def _trade_ledger(symbol,limit=100):
    if not is_configured(): return {'source':'empty','trades':[],'summary':summarize_trades([]),'equity_curve':[],'open_positions':[]}
    with connection() as conn:
        cur=conn.execute("SELECT id,symbol,side,quantity,entry_price,exit_price,realized_pnl,fees,slippage,mode,status,opened_at,closed_at FROM trades WHERE symbol=%s ORDER BY opened_at DESC LIMIT %s",(symbol,limit)); names=[d.name for d in cur.description]; rows=[dict(zip(names,r)) for r in cur.fetchall()]
        op=conn.execute("SELECT symbol,side,quantity,entry_price,status,opened_at FROM trades WHERE status='OPEN' AND mode='PAPER' ORDER BY opened_at DESC LIMIT 50"); on=[dict(zip([d.name for d in op.description],r)) for r in op.fetchall()]
    return {'source':'postgresql','trades':trade_markers(rows),'summary':summarize_trades(rows),'equity_curve':equity_curve(rows),'open_positions':on}

def _apply_macro_gate(result,symbol):
    cal=fetch_calendar(symbol=symbol,days=3); result['economic_calendar']=cal; passed,reasons=committee_calendar_gate(cal); result['economic_calendar_gate']='PASS' if passed else 'BLOCKED'; result['macro_risk']=cal.get('risk_score',1.)
    if not passed: result['decision']='NO_TRADE'; result.setdefault('reasons',[]).extend(reasons); result.setdefault('adversarial',{})['passed']=False
    return result

def _strategy_research(market_data,derivatives):
    payload=market_data.get('1h') or market_data.get('4h') or next(iter(market_data.values()),{})
    candles=payload.get('ohlcv',[]) if isinstance(payload,dict) else []
    if not candles:return {'usable':False,'reason':'no historical OHLCV available'}
    h=[float(x[2]) for x in candles]; l=[float(x[3]) for x in candles]; c=[float(x[4]) for x in candles]; v=[float(x[5]) for x in candles]
    candidates=[generate(h,l,c,v,s,derivatives) for s in STRATEGIES]
    candidates=[x for x in candidates if x.get('side')!='NONE']
    best=select_best(candidates,'UNKNOWN')
    best_bt=run_backtest(candles,best.get('strategy','trend_following')) if best.get('strategy')!='none' else {'usable':False,'reason':'no candidate strategy'}
    return {'usable':True,'candidates':sorted(candidates,key=lambda x:x.get('score',0),reverse=True),'selected_hypothesis':best,'historical_backtest':best_bt,'research_only':True}

def _apply_research(result,ledger,market_data,derivatives):
    features=['open','high','low','close','volume','ema20','ema50','ema200','vwap','rsi','atr','market_structure','spread_bps','depth','funding_rate','open_interest','expiry_distance','macro_risk','news_score','regime']
    research=build_research_intelligence(market_data={},market_summary=result,trades=ledger.get('trades',[]),feature_names=features); result['research_intelligence']=research; result['research_gate']='PASS' if research.get('research_ready') else 'NOT_CERTIFIED'
    result['strategy_research']=_strategy_research(market_data,derivatives)
    return result

def _adaptive(result,market_data,ledger,equity):
    regime_rows={}
    for tf,payload in (market_data or {}).items():
        if isinstance(payload,dict):
            regime_rows[tf]={'usable':True,'regime':payload.get('regime',result.get('regime','UNKNOWN')),'direction':payload.get('direction',result.get('direction_label','NONE'))}
    regime=regime_distribution(regime_rows)
    result['adaptive_intelligence']=adaptive_snapshot(result.get('autonomous_intelligence',{}),baseline=result.get('strategy_baseline'),specialist_records=result.get('specialist_calibration',[]))
    result['adaptive_intelligence']['regime_distribution']=regime
    result['adaptive_intelligence']['evidence_dependency']=evidence_dependency(result.get('autonomous_intelligence',{}).get('votes',[]))
    p=calibrated_probability(float(result.get('score',0.5) or 0.5),1.0,float(result.get('uncertainty',0.0) or 0.0))
    result['adaptive_intelligence']['final_probability']=p
    raw_ev=result.get('net_expected_value',result.get('expected_value'))
    net_ev=float(raw_ev) if raw_ev is not None else None
    if net_ev is not None:
        result['adaptive_intelligence']['counterfactual']=counterfactual_matrix(net_ev,float(result.get('execution_cost',0.0) or 0.0))
    else:
        result['adaptive_intelligence']['counterfactual']={'available':False,'reason':'net expected value unavailable; no synthetic EV is invented'}
    entry=float(result.get('entry_price',0) or 0); stop=float(result.get('stop_loss',0) or 0)
    if entry>0 and stop>0:
        result['adaptive_intelligence']['dynamic_position_size']=dynamic_risk_size(equity,entry,stop,float(result.get('risk_fraction',.005) or .005),probability=p['calibrated'],edge=float(result.get('historical_edge',0) or 0),regime_confidence=regime['confidence'],liquidity_score=float(result.get('liquidity_score',.7) or .7),execution_score=max(0.,1.-float(result.get('expected_slippage_bps',0) or 0)/20.),degradation_multiplier=float(result.get('strategy_degradation',{}).get('capital_multiplier',1.) or 1.))
    result['adaptive_intelligence']['signal_half_life']=signal_half_life(float(result.get('signal_age_seconds',0) or 0),float(result.get('signal_half_life_seconds',900) or 900))
    critique=self_critique(thesis=str(result.get('thesis',result.get('selected_hypothesis',{}).get('reason',''))),supporting=list(result.get('supporting_evidence',[])),contradicting=list(result.get('contradicting_evidence',[])),missing=list(result.get('missing_evidence',[])),invalidation=str(result.get('invalidation',result.get('stop_reason',''))),probability=p['calibrated'],calibrated_lower_bound=p['lower_bound'],net_ev=net_ev)
    result['adaptive_intelligence']['self_critique']=critique
    if not critique['passed'] and result.get('decision')=='TRADE':
        result['decision']='NO_TRADE'; result.setdefault('reasons',[]).extend(['adaptive self-critique failed']+critique['failures'])
    if net_ev is not None and result['adaptive_intelligence']['counterfactual'].get('survives_all') is False and result.get('decision')=='TRADE':
        result['decision']='NO_TRADE'; result.setdefault('reasons',[]).append('trade thesis fails stressed net-EV scenarios')
    if result['adaptive_intelligence']['signal_half_life'].get('stale') and result.get('decision')=='TRADE':
        result['decision']='NO_TRADE'; result.setdefault('reasons',[]).append('signal edge is stale')
    return result

def _apply_intelligence(result,symbol,market_data,derivatives,expiry,expiry_market_data,equity):
    adv=derivatives_options_advisory(derivatives,expiry,expiry_market_data,result.get('direction',0)); result['derivatives_options_advisory']=adv
    autonomy=build_autonomous_intelligence(symbol=symbol,market_data=market_data,market_summary=result,derivatives=derivatives,expiry=expiry,macro_blocked=result.get('economic_calendar_gate')=='BLOCKED'); result['autonomous_intelligence']=autonomy; result['autonomous_decision']=autonomy.get('decision','NO_TRADE'); result['live_execution']=False; result['paper_trading']=True
    if autonomy.get('decision')!='TRADE': result['decision']='NO_TRADE'; result.setdefault('reasons',[]).extend(autonomy.get('failures',[]))
    ledger=_trade_ledger(symbol); result['paper_trade_ledger']=ledger; result=_apply_research(result,ledger,market_data,derivatives)
    portfolio=build_portfolio(ledger.get('open_positions',[]),{}, {'symbol':symbol,'equity':equity}); result['portfolio']=portfolio; pg=portfolio_risk_gate(portfolio,float(result.get('risk_fraction',.005) or .005)); result['portfolio_risk_gate']=pg
    if not pg['passed']: result['decision']='NO_TRADE'; result.setdefault('reasons',[]).extend(pg['blockers'])
    red=adversarial_challenge({'direction':result.get('direction_label',''),'expected_slippage_bps':result.get('expected_slippage_bps',0),'max_slippage_bps':20,'risk_reward':result.get('risk_reward',0),'confidence':result.get('score',0)},{'macro_risk':result.get('macro_risk',0)},{'crowding':'crowded_long' if adv.get('bias',0)<-.3 else 'crowded_short' if adv.get('bias',0)>.3 else 'mixed'},{}); result['adversarial_red_team']=red
    if not red['passed']: result['decision']='NO_TRADE'; result.setdefault('reasons',[]).extend(red['failures'])
    result['derivatives_options_gate']=final_derivatives_options_gate(derivatives,expiry,expiry_market_data)
    result['strategy_ranking']=rank_strategy(result.get('research_intelligence',{}),portfolio_fit=max(.1,pg.get('marginal_risk',1.)),regime_fit=float(result.get('autonomous_intelligence',{}).get('regime',{}).get('confidence',1.) or 1.))
    result['strategy_degradation']=degradation_monitor(result.get('research_intelligence',{}))
    return _adaptive(result,market_data,ledger,equity)

def _scan(symbol,exchange_id,sandbox,equity,limit):
    gateway=ExchangeGateway(exchange_id=exchange_id,sandbox=sandbox); md=gateway.multi_timeframe_market_data(symbol,limit=limit,orderbook_limit=100); d=gateway.derivatives_market_data(symbol); ed=gateway.expiry_market_data(symbol,limit=100); e=analyze_expiries(ed.get('instruments'),market_type=ed.get('market_type','spot'))
    result=build_command_center(symbol,md,d,e,equity=equity); result.update({'exchange':exchange_id,'sandbox':sandbox,'data_source':'exchange_public_market_data','supported_timeframes':gateway.supported_timeframes(),'live_execution':False,'8_percent_daily_target':{'enabled':False,'policy':'research hypothesis only; never a trading target'}})
    return _apply_intelligence(_apply_macro_gate(result,symbol),symbol,md,d,e,ed,equity)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            p=parse_qs(urlparse(self.path).query); symbol=p.get('symbol',['BTC/USDT'])[0]; exchange=p.get('exchange',['binance'])[0].lower(); sandbox=p.get('sandbox',['true'])[0].lower()!='false'; send_json(self,_scan(symbol,exchange,sandbox,100.,250))
        except ValueError as exc: send_json(self,{'detail':str(exc)},400)
        except Exception as exc: send_json(self,{'detail':str(exc),'decision':'NO_TRADE','live_execution':False},503)
    def do_POST(self):
        try:
            b=read_json(self); symbol=str(b.get('symbol','BTC/USDT')).strip(); exchange=str(b.get('exchange','binance')).lower(); sandbox=bool(b.get('sandbox',True)); equity=max(0.,float(b.get('equity',100.))); limit=min(500,max(50,int(b.get('limit',250)))); send_json(self,_scan(symbol,exchange,sandbox,equity,limit))
        except ValueError as exc: send_json(self,{'detail':str(exc)},400)
        except Exception as exc: send_json(self,{'detail':str(exc),'decision':'NO_TRADE','live_execution':False},503)
