"""Causal closed-bar reversal observations. NOT verified profitable trade signals."""
import math
import pandas as pd


def reversal_setup(df, side, lookback=12, atr_window=14):
    """Identify supply/demand rejection + structure change, without EMA trend gate.

    Uses only supplied completed bars. The result is known after the last bar closes.
    """
    base={'side':side,'confirmed':False,'stage':'UNAVAILABLE','reasons':[],
          'checks':{},'candle_time':None,'price':None}
    if side not in ('UP','DOWN') or df is None or len(df)<max(35,lookback+5):
        return {**base,'reasons':['Insufficient completed candles']}
    x=df.sort_values('ts').drop_duplicates('ts').tail(100).reset_index(drop=True)
    if not all(k in x.columns for k in ('open','high','low','close','ts')):
        return {**base,'reasons':['OHLC data missing']}
    try:
        o,h,l,c=[x[k].astype(float) for k in ('open','high','low','close')]
        if not all(math.isfinite(float(v.iloc[-1])) for v in (o,h,l,c)):
            return {**base,'reasons':['Invalid prices']}
        tr=pd.concat([(h-l),(h-c.shift(1)).abs(),(l-c.shift(1)).abs()],axis=1).max(axis=1)
        atr=float(tr.iloc[-atr_window-1:-1].median())
        if not math.isfinite(atr) or atr<=0:return {**base,'reasons':['Invalid volatility']}
        bull=side=='UP'; current=len(x)-1
        # A prior confirmed swing extreme is a proxy zone, not a proven resting order.
        prior=x.iloc[max(0,current-25):current-1]
        level=float(prior.low.min() if bull else prior.high.max())
        tolerance=max(atr*.4,level*.00015)
        # Previous 3 bars OR the signal bar must touch the zone.
        window=x.iloc[-4:]
        touched=(float(window.low.min())<=level+tolerance) if bull else (float(window.high.max())>=level-tolerance)
        # Candle closes away from the tested level with directional body.
        rng=max(float(h.iloc[-1]-l.iloc[-1]),1e-9)
        body=abs(float(c.iloc[-1]-o.iloc[-1]))/rng
        decisive=(c.iloc[-1]>o.iloc[-1] and (h.iloc[-1]-c.iloc[-1])/rng<=.38) if bull else (c.iloc[-1]<o.iloc[-1] and (c.iloc[-1]-l.iloc[-1])/rng<=.38)
        candle=bool(decisive and body>=.45)
        # Break of short-term structure (last 3 completed bars before signal bar).
        structure=bool(c.iloc[-1]>h.iloc[-4:-1].max()) if bull else bool(c.iloc[-1]<l.iloc[-4:-1].min())
        # Momentum change is independent of long-term EMA alignment.
        previous_move=float(c.iloc[-2]-c.iloc[-5]); last_move=float(c.iloc[-1]-c.iloc[-2])
        turn=bool(last_move>0 and (previous_move<0 or c.iloc[-1]>c.iloc[-2])) if bull else bool(last_move<0 and (previous_move>0 or c.iloc[-1]<c.iloc[-2]))
        checks={'zone_touch':bool(touched),'decisive_candle':candle,'micro_structure_break':structure,'directional_turn':turn}
        # An early warning is not a confirmed entry. Confirmation requires zone + decisive bar + structure.
        confirmed=checks['zone_touch'] and checks['decisive_candle'] and checks['micro_structure_break']
        stage='CONFIRMED REVERSAL (TECHNICAL)' if confirmed else 'REVERSAL WATCH' if touched and (candle or turn) else 'NO REVERSAL'
        reasons=[k.replace('_',' ') for k,v in checks.items() if not v]
        return {**base,'confirmed':bool(confirmed),'stage':stage,'checks':checks,
                'reasons':reasons,'candle_time':str(x.ts.iloc[-1]),'price':float(c.iloc[-1]),
                'zone_level':level,'atr':atr}
    except (TypeError,ValueError,IndexError,KeyError) as exc:
        return {**base,'reasons':['Malformed candle history: '+str(exc)]}
