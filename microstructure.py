"""Public spot trade polling and transparent order-book / price-zone diagnostics.
All spot trades are Coinbase BTC-USD proxies, not Chainlink settlement ticks.
"""
from datetime import datetime, timezone
import pandas as pd
import requests

URL='https://api.exchange.coinbase.com/products/BTC-USD/trades'

def recent_trades(limit=100):
    r=requests.get(URL,params={'limit':min(100,max(1,int(limit)))},headers={'User-Agent':'BTC15-Research/5.1'},timeout=6)
    r.raise_for_status()
    data=r.json()
    rows=[]
    for item in data:
        rows.append({'id':int(item['trade_id']),'ts':pd.to_datetime(item['time'],utc=True),
                     'price':float(item['price']),'size':float(item['size']),
                     'side':str(item.get('side','')).lower()})
    return sorted(rows,key=lambda t:(t['ts'],t['id']))

def accumulate_trades(existing,new,max_age_seconds=300,now=None):
    now=pd.Timestamp.now(tz='UTC') if now is None else pd.Timestamp(now)
    by_id={t['id']:t for t in existing}
    by_id.update({t['id']:t for t in new})
    return sorted([t for t in by_id.values() if 0<=(now-t['ts']).total_seconds()<=max_age_seconds],key=lambda t:(t['ts'],t['id']))

def provisional_candles(trades,frequency='1min'):
    if not trades:return pd.DataFrame(columns=['ts','open','high','low','close','volume'])
    df=pd.DataFrame(trades).sort_values('ts')
    df['bucket']=df.ts.dt.floor(frequency)
    out=df.groupby('bucket',sort=True).agg(open=('price','first'),high=('price','max'),low=('price','min'),close=('price','last'),volume=('size','sum')).reset_index().rename(columns={'bucket':'ts'})
    return out

def pressure(book,levels=5):
    if not book:return None
    bids=book.get('bids',[])[:levels];asks=book.get('asks',[])[:levels]
    if not bids or not asks:return None
    bid_usd=sum(float(p)*float(q) for p,q in bids)
    ask_usd=sum(float(p)*float(q) for p,q in asks)
    total=bid_usd+ask_usd
    if total<=0:return None
    return {'bid_usd':bid_usd,'ask_usd':ask_usd,'imbalance':(bid_usd-ask_usd)/total,
            'bid_share':bid_usd/total,'ask_share':ask_usd/total}

def supply_demand_zones(df,lookback=120,pivot=3,atr_period=14):
    """Confirmed swing highs/lows, with ATR-width bands; no future-bar lookahead.
    Latest pivot bars require pivot subsequent completed bars to confirm.
    """
    if df is None or len(df)<max(atr_period+2,2*pivot+2):return {'demand':[],'supply':[]}
    x=df.sort_values('ts').reset_index(drop=True).tail(lookback).reset_index(drop=True)
    prev=x.close.shift(1)
    tr=pd.concat([(x.high-x.low).abs(),(x.high-prev).abs(),(x.low-prev).abs()],axis=1).max(axis=1)
    atr=float(tr.tail(atr_period).mean())
    width=max(atr*.35,float(x.close.iloc[-1])*.00005)
    demand=[];supply=[]
    for i in range(pivot,len(x)-pivot):
        segment=x.iloc[i-pivot:i+pivot+1]
        lo=float(x.low.iloc[i]);hi=float(x.high.iloc[i])
        if lo==float(segment.low.min()) and (segment.low==lo).sum()==1:
            demand.append({'low':lo-width,'high':lo+width,'ts':x.ts.iloc[i]})
        if hi==float(segment.high.max()) and (segment.high==hi).sum()==1:
            supply.append({'low':hi-width,'high':hi+width,'ts':x.ts.iloc[i]})
    return {'demand':demand[-3:],'supply':supply[-3:]}
