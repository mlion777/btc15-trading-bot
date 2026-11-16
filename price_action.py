"""Closed-candle directional analysis; scores are not win probabilities."""
def analyze(candles, market=None, spot=None):
    result={'side':None,'stage':'NO DATA','votes':{'UP':0,'DOWN':0},'reasons':[], 'details':[]}
    if candles is None or len(candles)<8:return result
    c=candles.sort_values('ts').tail(12)
    close=c['close'].astype(float).tolist(); high=c['high'].astype(float).tolist(); low=c['low'].astype(float).tolist()
    up=down=0; reasons=[]; details=[]
    # Closed-candle progression, robust to a single red pullback candle.
    rises=sum(close[i]>close[i-1] for i in range(-6,0))
    falls=6-rises
    if rises>=4:up+=2; reasons.append('4+ of last 6 closed candles advanced')
    if falls>=4:down+=2; details.append('4+ of last 6 closed candles declined')
    if close[-1]>close[-6] and min(close[-3:])>min(close[-8:-3]):
        up+=1; reasons.append('higher recent price floor and positive 5-candle return')
    if close[-1]<close[-6] and max(close[-3:])<max(close[-8:-3]):
        down+=1; details.append('lower recent price ceiling and negative 5-candle return')
    # Breakout of preceding 5 closed candles, or sustained hold above prior range.
    prior_high=max(high[-7:-2]); prior_low=min(low[-7:-2])
    if close[-1]>prior_high:up+=2; reasons.append('closed above previous five-candle resistance')
    elif close[-2]>prior_high and close[-1]>prior_high*.9995:
        up+=1; reasons.append('holding near recent upside breakout after pullback')
    if close[-1]<prior_low:down+=2; details.append('closed below previous five-candle support')
    elif close[-2]<prior_low and close[-1]<prior_low*1.0005:
        down+=1; details.append('holding near downside breakout after bounce')
    ref=(market or {}).get('reference')
    current=spot if spot is not None else close[-1]
    if ref and float(ref)>0:
        move=(float(current)/float(ref)-1)*100
        result['contract_move_pct']=round(move,4)
        if move>.04:up+=1; reasons.append('BTC is above this contract price-to-beat')
        if move<-.04:down+=1; details.append('BTC is below this contract price-to-beat')
    result['votes']={'UP':up,'DOWN':down}
    if up>down and up>=2:result.update(side='UP',stage='BULLISH PRICE ACTION',reasons=reasons,details=details)
    elif down>up and down>=2:result.update(side='DOWN',stage='BEARISH PRICE ACTION',reasons=details,details=reasons)
    else:result.update(stage='MIXED / WAIT',reasons=reasons+details)
    return result
