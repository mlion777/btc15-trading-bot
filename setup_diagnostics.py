"""Explain developing setups independently from Polymarket execution gates.
These are technical observations, not trading recommendations.
"""
import math


def describe_setup(z, confirmation):
    if not z:
        return {'bias':'NEUTRAL','score':0,'stage':'DATA UNAVAILABLE','checks':{},'reason':'No indicator history'}
    ema9=z.get('ema9'); ema21=z.get('ema21'); hist=z.get('macd_histogram'); rsi=z.get('rsi14')
    checks={
        'EMA trend': 1 if ema9 is not None and ema21 is not None and ema9>ema21 else (-1 if ema9 is not None and ema21 is not None and ema9<ema21 else 0),
        'MACD momentum': 1 if hist is not None and hist>0 else (-1 if hist is not None and hist<0 else 0),
        'RSI direction': 1 if rsi is not None and rsi>55 else (-1 if rsi is not None and rsi<45 else 0),
    }
    score=sum(checks.values()); bias='LONG' if score>=2 else 'SHORT' if score<=-2 else 'NEUTRAL'
    confirmation=confirmation or {}
    if bias=='NEUTRAL': stage='NO DIRECTIONAL SETUP'
    elif confirmation.get('ok'): stage='TECHNICALLY CONFIRMED'
    else: stage='DEVELOPING SETUP'
    return {'bias':bias,'score':score,'stage':stage,'checks':checks,
            'reason':'Technical context only; not a Polymarket entry or proven edge'}


def entry_diagnostics(scalp, quality, market, up, down, confirmation, tick_age=None):
    reasons=[]
    if not quality.get('ok'): reasons.append('Spot data: '+str(quality.get('reason','failed quality check')))
    if not market: reasons.append('Polymarket market missing')
    else:
        if market.get('reference') is None: reasons.append('Source price-to-beat missing')
        if not market.get('accepting_orders',True): reasons.append('Market not accepting orders')
    if not up or not down: reasons.append('UP/DOWN order book missing')
    if tick_age is None: reasons.append('No observed live spot trade')
    elif tick_age>15: reasons.append(f'Observed spot trade is {tick_age:.1f}s old')
    if scalp.get('reason') and not scalp.get('side'): reasons.append('Scalp filter: '+scalp['reason'])
    if confirmation and not confirmation.get('ok'):
        failed=[name for name in ('trend','bos','rejection','volume') if not confirmation.get(name)]
        if failed: reasons.append('Closed candle missing: '+', '.join(failed))
    return reasons
