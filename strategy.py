"""Independent, causal multi-timeframe technical analysis. Not Bucko proprietary code."""
import pandas as pd

def resample(candles, seconds):
    if candles is None or candles.empty:
        return pd.DataFrame(columns=['ts','open','high','low','close','volume'])
    return (candles.set_index('ts').resample(f'{seconds}s',label='left',closed='left')
            .agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'})
            .dropna(subset=['open']).reset_index())

def technical(candles):
    if len(candles)<36:
        return {'side':'WAIT','score':0,'bull':0,'bear':0,'reasons':['Not enough completed candles']}
    d=candles.iloc[:-1]  # exclude potentially incomplete candle
    if len(d)<35:
        return {'side':'WAIT','score':0,'bull':0,'bear':0,'reasons':['Not enough completed candles']}
    c=d.close.astype(float)
    e9=c.ewm(span=9,adjust=False).mean();e21=c.ewm(span=21,adjust=False).mean();e34=c.ewm(span=34,adjust=False).mean()
    last=d.iloc[-1]; prev=d.iloc[-2]; recent=d.iloc[-9:-1]
    rng=(d.high-d.low).rolling(14,min_periods=5).mean().iloc[-1]
    medvol=d.volume.iloc[-21:-1].median()
    votes=[]
    if e9.iloc[-1]>e21.iloc[-1]>e34.iloc[-1]: votes.append(('UP','EMA trend aligned'))
    elif e9.iloc[-1]<e21.iloc[-1]<e34.iloc[-1]:votes.append(('DOWN','EMA trend aligned'))
    if last.close>recent.high.max():votes.append(('UP','Breakout above recent highs'))
    if last.close<recent.low.min():votes.append(('DOWN','Breakdown below recent lows'))
    if (c.iloc[-6:].diff().dropna()>0).sum()>=4:votes.append(('UP','Higher closing momentum'))
    if (c.iloc[-6:].diff().dropna()<0).sum()>=4:votes.append(('DOWN','Lower closing momentum'))
    if last.close>last.open and last.close-last.open>rng*.5:votes.append(('UP','Bullish impulse candle'))
    if last.close<last.open and last.open-last.close>rng*.5:votes.append(('DOWN','Bearish impulse candle'))
    if medvol>0 and last.volume>medvol*1.2:
        if last.close>last.open:votes.append(('UP','Above-median buying-volume candle'))
        elif last.close<last.open:votes.append(('DOWN','Above-median selling-volume candle'))
    if last.close>e9.iloc[-1] and e9.iloc[-1]>e9.iloc[-3]:votes.append(('UP','Rising short-term average'))
    if last.close<e9.iloc[-1] and e9.iloc[-1]<e9.iloc[-3]:votes.append(('DOWN','Falling short-term average'))
    bull=sum(s=='UP' for s,_ in votes);bear=sum(s=='DOWN' for s,_ in votes)
    side='UP' if bull>=3 and bull>=bear+2 else 'DOWN' if bear>=3 and bear>=bull+2 else 'WAIT'
    return {'side':side,'score':max(bull,bear),'bull':bull,'bear':bear,'reasons':[r for s,r in votes if s==side]}

def consensus(frames):
    # 1m and 5m determine trend; 15s/30s are timing only. Avoid counting highly correlated 1s ticks as independent votes.
    out={name:technical(df) for name,df in frames.items()}
    direction=out['1m']['side']
    trend=out['5m']['side']
    timing=[out[k]['side'] for k in ('15s','30s')]
    if direction=='WAIT':return 'WAIT',out,'1m direction not confirmed'
    if trend not in (direction,'WAIT'):return 'WAIT',out,'5m trend conflicts with 1m'
    if timing.count(direction)<1:return 'WAIT',out,'Subminute entry timing not confirmed'
    return direction,out,'1m trend + subminute timing; 5m not opposed'

def zones(d):
    # Historical three-candle FVGs, using completed bars only; preserve time of discovery.
    d=d.iloc[:-1].reset_index(drop=True)
    out=[]
    if len(d)<20:return out
    atr=(d.high-d.low).rolling(14,min_periods=5).mean()
    for i in range(15,len(d)):
        a=d.iloc[i-2];c=d.iloc[i];gap=max(float(atr.iloc[i])*.15,0.01)
        if c.low>a.high+gap:out.append(('FVG UP',float(a.high),float(c.low),c.ts,'#2e9f79'))
        if c.high<a.low-gap:out.append(('FVG DOWN',float(c.high),float(a.low),c.ts,'#db5470'))
    kept=[]
    for label,lo,hi,t,color in out:
        later=d[d.ts>t]
        if label=='FVG UP' and (later.close<lo).any():continue
        if label=='FVG DOWN' and (later.close>hi).any():continue
        kept.append((label,lo,hi,t,color))
    return kept[-8:]
