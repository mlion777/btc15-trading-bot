"""Exploratory, unvalidated technical watchlist; never an order recommendation."""
def watch(z, long_confirmation=None, short_confirmation=None, long_reversal=None, short_reversal=None, price_action=None):
    if not z or not z.get('spot'):
        return {'side':None,'stage':'NO DATA','reason':'Spot indicators unavailable'}
    votes={}
    for side in ('UP','DOWN'):
        sign=1 if side=='UP' else -1
        score=0
        ema9=z.get('ema9'); ema21=z.get('ema21'); macd=z.get('macd_histogram'); rsi=z.get('rsi14')
        if ema9 is not None and ema21 is not None and (ema9-ema21)*sign>0: score+=1
        if macd is not None and macd*sign>0: score+=1
        if rsi is not None and (rsi-50)*sign>3: score+=1
        conf=(long_confirmation if side=='UP' else short_confirmation) or {}
        rev=(long_reversal if side=='UP' else short_reversal) or {}
        if conf.get('ok'): score+=2
        if rev.get('ok'): score+=2
        # Price action can add at most three votes; avoid turning a single green candle into an entry.
        pa=(price_action or {}).get("votes",{})
        score+=min(3,max(0,int(pa.get(side,0))))
        votes[side]=score
    winner=max(votes,key=votes.get)
    if votes[winner]<2 or votes[winner]==votes['DOWN' if winner=='UP' else 'UP']:
        return {'side':None,'stage':'MIXED','reason':'No directional advantage','votes':votes}
    return {'side':winner,'stage':'DEVELOPING' if votes[winner]<4 else 'STRONGER TECHNICAL SETUP',
            'reason':'Unvalidated technical score; not a calibrated win probability','votes':votes}
