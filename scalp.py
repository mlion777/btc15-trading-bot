"""Conservative *paper-only* scalp screening; no claim of calibrated profitability."""
import math

def scalp_screen(z, market, up, down, quality, min_edge=.08, max_spread=.08, fee=.01,
                 min_seconds=90, max_seconds=780, min_score=3, max_entry=.85):
    result={'side':None,'status':'NO ENTRY','reason':'Missing or stale data','score':0,'entry':None,'exit_target':None,'gross_target_pct':None}
    if not market or not quality.get('ok') or not z or not up or not down:
        return result
    if not market.get('active',True) or not market.get('accepting_orders',True):
        result['reason']='Market not accepting orders';return result
    seconds=float(market.get('seconds_left') or 0)
    if not min_seconds <= seconds <= max_seconds:
        result['reason']='Outside scalp time window';return result
    spot=z.get('spot');strike=market.get('reference')
    if not spot or not strike or not math.isfinite(float(spot)) or not math.isfinite(float(strike)):
        result['reason']='Reference or spot price missing';return result
    score=0
    for positive,negative in [(z.get('ema9',0)>z.get('ema21',0),z.get('ema9',0)<z.get('ema21',0)),
                               (z.get('macd_histogram',0)>0,z.get('macd_histogram',0)<0),
                               ((z.get('rsi14') or 50)>=57,(z.get('rsi14') or 50)<=43),
                               (spot>strike,spot<strike)]:
        score+=int(positive)-int(negative)
    result['score']=score
    if abs(score)<min_score:
        result['reason']='Trend confirmation too weak';return result
    side='UP' if score>0 else 'DOWN'
    ob=up if side=='UP' else down
    ask=ob.get('vwap') if ob.get('fillable') else None
    spread=ob.get('spread')
    if ask is None or spread is None or not (0<float(ask)<max_entry) or float(spread)>max_spread:
        result['reason']='Order-book price, depth, or spread not suitable';return result
    # Scalp targets are illustrative order prices, NOT predictions of execution or edge.
    entry=float(ask)
    target=min(.99,entry+max(.04,2*float(spread)+2*fee))
    result.update(side=side,status='PAPER SCALP '+side,entry=entry,exit_target=target,
                  gross_target_pct=(target/entry-1)*100,
                  reason='Four-factor trend alignment and liquidity filters passed; unvalidated paper setup')
    return result
