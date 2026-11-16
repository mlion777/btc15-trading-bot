"""Transparent research-only live bias; not a calibrated probability or trade instruction."""
import math
import numpy as np
from engine import proxy_probability

def technical_signal(candles, zones, market, up, down, quality, min_edge=.08, max_spread=.08, fee=.01):
    result={'bias':'WAIT','reason':'Insufficient fresh market data','prob_up':None,'candidate':'NONE','edge':None,'score':0}
    if not market or not quality.get('ok') or not zones or not up or not down:
        return result
    remaining=float(market.get('seconds_left') or 0)
    strike=market.get('reference')
    spot=zones.get('spot')
    if not strike or not spot or remaining<30 or remaining>900:
        result['reason']='Reference price unavailable or market outside trading window'
        return result
    try:
        p=proxy_probability(candles,remaining,spot,strike)
    except (ValueError,OverflowError,TypeError):
        p=None
    if p is None or not np.isfinite(p):return result
    result['prob_up']=float(p)
    score=0
    if zones['ema9']>zones['ema21']:score+=1
    elif zones['ema9']<zones['ema21']:score-=1
    if zones['macd_histogram']>0:score+=1
    elif zones['macd_histogram']<0:score-=1
    rsi=zones.get('rsi14')
    if rsi is not None:
        if rsi>55:score+=1
        elif rsi<45:score-=1
    result['score']=score
    result['bias']='UP' if score>=2 else ('DOWN' if score<=-2 else 'MIXED')
    result['reason']='Technical indicator vote (EMA, MACD, RSI), not a validated win forecast'
    side='UP' if result['bias']=='UP' else ('DOWN' if result['bias']=='DOWN' else None)
    if side:
        ob=up if side=='UP' else down
        prob=p if side=='UP' else 1-p
        ask=ob.get('vwap') if ob.get('fillable') else None
        spread=ob.get('spread')
        if ask is not None and spread is not None and spread<=max_spread and 0<ask<1:
            edge=prob-ask-fee
            result['edge']=float(edge)
            if edge>=min_edge:
                result['candidate']='PAPER '+side
                result['reason']='Uncalibrated volatility proxy exceeds simulated ask plus buffers; research candidate ONLY'
    return result
