"""Non-repainting, completed-candle technical confirmations for paper research.
Signals are not proven profitable and do not imitate proprietary Bucko parameters.
"""
import math
import pandas as pd

def confirm_setup(df, side, zones=None, lookback=12):
    result={'ok':False,'reason':'Insufficient closed candles','bos':False,'rejection':False,'trend':False,'volume':False,'candle_time':None}
    if side not in ('UP','DOWN') or df is None or len(df)<max(60,lookback+4):return result
    x=df.sort_values('ts').drop_duplicates('ts').tail(90).copy()
    close=x.close.astype(float); high=x.high.astype(float); low=x.low.astype(float); op=x.open.astype(float)
    vol=x.volume.astype(float) if 'volume' in x else pd.Series([0.]*len(x),index=x.index)
    if not all(math.isfinite(v) for v in [close.iloc[-1],high.iloc[-1],low.iloc[-1]]):return result
    ema9=close.ewm(span=9,adjust=False).mean();ema21=close.ewm(span=21,adjust=False).mean();ema55=close.ewm(span=55,adjust=False).mean()
    bull=side=='UP';trend=ema9.iloc[-1]>ema21.iloc[-1]>ema55.iloc[-1] if bull else ema9.iloc[-1]<ema21.iloc[-1]<ema55.iloc[-1]
    prior_high=float(high.iloc[-lookback-1:-1].max());prior_low=float(low.iloc[-lookback-1:-1].min())
    bos=close.iloc[-1]>prior_high if bull else close.iloc[-1]<prior_low
    candle_range=max(1e-9,float(high.iloc[-1]-low.iloc[-1])); body=abs(float(close.iloc[-1]-op.iloc[-1]))
    # Closed candle close near directional extreme, with meaningful body.
    rejection=(float(high.iloc[-1]-close.iloc[-1])/candle_range<.25 if bull else float(close.iloc[-1]-low.iloc[-1])/candle_range<.25) and body/candle_range>=.5 and (close.iloc[-1]>op.iloc[-1] if bull else close.iloc[-1]<op.iloc[-1])
    baseline=float(vol.iloc[-21:-1].median());volume=baseline>0 and float(vol.iloc[-1])>=1.15*baseline
    # A BOS plus decisive close, trend, and volume confirmation; do not call zones proof of resting orders.
    result.update(ok=bool(trend and bos and rejection and volume),reason='All four closed-candle confirmations passed' if trend and bos and rejection and volume else 'Closed-candle confirmations incomplete',bos=bool(bos),rejection=bool(rejection),trend=bool(trend),volume=bool(volume),candle_time=str(x.ts.iloc[-1]))
    return result

def trade_pressure(trades,lookback_seconds=60):
    """Coinbase side denotes maker side: sell maker => aggressive buyer."""
    if not trades:return None
    end=max(t['ts'] for t in trades)
    recent=[t for t in trades if 0<=(end-t['ts']).total_seconds()<=lookback_seconds]
    buy=sum(t['price']*t['size'] for t in recent if t.get('side')=='sell')
    sell=sum(t['price']*t['size'] for t in recent if t.get('side')=='buy')
    if buy+sell<=0:return None
    return {'aggressive_buy_usd':buy,'aggressive_sell_usd':sell,'imbalance':(buy-sell)/(buy+sell),'trades':len(recent)}
