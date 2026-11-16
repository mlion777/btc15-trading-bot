import json, math, sqlite3, time
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import requests
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import brier_score_loss, log_loss

GAMMA='https://gamma-api.polymarket.com'
CLOB='https://clob.polymarket.com'
BINANCE='https://api.binance.com'
COINBASE='https://api.exchange.coinbase.com'
FEATURES=['ret1','ret3','ret5','ema_gap','rsi','volatility','range_position','momentum']

def get(url, params=None):
    r=requests.get(url,params=params,timeout=7,headers={'User-Agent':'BTC15ResearchDashboard/1.0'})
    r.raise_for_status()
    return r.json()

def current_market(now=None):
    now=time.time() if now is None else now
    start=int(now//900)*900
    slug=f'btc-updown-15m-{start}'
    data=get(GAMMA+'/events',{'slug':slug})
    if not data: raise RuntimeError('Current Polymarket event unavailable')
    markets=data[0].get('markets') or []
    if not markets: raise RuntimeError('Current event has no markets')
    m=markets[0]
    outcomes=json.loads(m['outcomes']) if isinstance(m.get('outcomes'),str) else m.get('outcomes',[])
    ids=json.loads(m['clobTokenIds']) if isinstance(m.get('clobTokenIds'),str) else m.get('clobTokenIds',[])
    mapping={str(k).lower():v for k,v in zip(outcomes,ids)}
    if not ('up' in mapping and 'down' in mapping): raise RuntimeError('Cannot map outcome tokens')
    return {'slug':slug,'start':start,'end':start+900,'seconds_left':max(0,start+900-now), 'up':mapping['up'],'down':mapping['down'],'rules':m.get('description') or data[0].get('description') or '', 'url':'https://polymarket.com/event/'+slug}

def book(token):
    data=get(CLOB+'/book',{'token_id':token})
    asks=sorted([(float(x['price']),float(x['size'])) for x in data.get('asks',[])],key=lambda x:x[0])
    bids=sorted([(float(x['price']),float(x['size'])) for x in data.get('bids',[])],key=lambda x:-x[0])
    return {'ask':asks[0][0] if asks else None,'bid':bids[0][0] if bids else None,'ask_depth':sum(x[1] for x in asks[:5]),'bid_depth':sum(x[1] for x in bids[:5])}

def candles(limit=1000):
    try:
        raw=get(BINANCE+'/api/v3/klines',{'symbol':'BTCUSDT','interval':'1m','limit':limit})
        df=pd.DataFrame(raw,columns=['ts','open','high','low','close','volume','close_ts','quote_vol','ntrades','taker_base','taker_quote','ignore'])
        for c in ['open','high','low','close','volume']: df[c]=pd.to_numeric(df[c])
        df['ts']=pd.to_datetime(df['ts'],unit='ms',utc=True)
        return df[['ts','open','high','low','close','volume']], 'Binance BTCUSDT (proxy, NOT settlement feed)'
    except Exception:
        raw=get(COINBASE+'/products/BTC-USD/candles',{'granularity':60})
        df=pd.DataFrame(raw,columns=['unix','low','high','open','close','volume'])
        for c in ['open','high','low','close','volume']: df[c]=pd.to_numeric(df[c])
        df['ts']=pd.to_datetime(df['unix'],unit='s',utc=True)
        return df.sort_values('ts')[['ts','open','high','low','close','volume']].reset_index(drop=True), 'Coinbase BTC-USD (proxy, NOT settlement feed)'

def official_reference(start,end):
    # A public Polymarket website endpoint; availability/schema may change. Fail closed.
    iso_start=datetime.fromtimestamp(start,timezone.utc).isoformat().replace('+00:00','Z')
    iso_end=datetime.fromtimestamp(end,timezone.utc).isoformat().replace('+00:00','Z')
    try:
        d=get('https://polymarket.com/api/crypto/crypto-price',{'symbol':'BTC','eventStartTime':iso_start,'endDate':iso_end,'variant':'fifteenminute'})
        if not isinstance(d,dict): return None,'Unexpected response'
        val=d.get('openPrice')
        if val is None and isinstance(d.get('data'),dict): val=d['data'].get('openPrice')
        val=float(val)
        if not 1000<val<1000000: return None,'Invalid reference price'
        return val,'Polymarket crypto-price API (verify against market rules)'
    except Exception as e:
        return None,'Official reference unavailable: '+str(e)[:110]

def rsi(s,n=14):
    diff=s.diff(); gain=diff.clip(lower=0).ewm(alpha=1/n,adjust=False).mean(); loss=(-diff.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    return 100-100/(1+gain/loss.replace(0,np.nan))

def features(df):
    x=df.copy().sort_values('ts').reset_index(drop=True)
    c=x.close
    x['ret1']=np.log(c/c.shift(1));x['ret3']=np.log(c/c.shift(3));x['ret5']=np.log(c/c.shift(5))
    x['ema_gap']=c.ewm(span=9,adjust=False).mean()/c.ewm(span=21,adjust=False).mean()-1
    x['rsi']=rsi(c)
    x['volatility']=x.ret1.rolling(20).std()
    hi=x.high.rolling(30).max();lo=x.low.rolling(30).min()
    x['range_position']=(c-lo)/(hi-lo).replace(0,np.nan)
    x['momentum']=c/c.shift(10)-1
    return x.replace([np.inf,-np.inf],np.nan)

def train_backtest(df, min_rows=180):
    # One non-overlapping 15-minute sample per market, using spot as a PROXY label.
    x=features(df)
    x['start_epoch']=x.ts.astype('int64')//10**9
    x=x[x.start_epoch%900==0].copy()
    x['future_close']=x.close.shift(-1)
    x['target']=(x.future_close>=x.close).astype(int)
    x=x.dropna(subset=FEATURES+['future_close'])
    if len(x)<min_rows: return None,'Need at least '+str(min_rows)+' complete historical 15-minute windows; current API data is insufficient.'
    cut=int(len(x)*.6); val_end=int(len(x)*.8); train=x.iloc[:cut]; val=x.iloc[cut:val_end]; test=x.iloc[val_end:]
    if train.target.nunique()<2: return None,'Training sample has only one outcome.'
    model=make_pipeline(StandardScaler(),LogisticRegression(max_iter=1000,C=.2))
    model.fit(train[FEATURES],train.target)
    val_p=model.predict_proba(val[FEATURES])[:,1]
    raw_test_p=model.predict_proba(test[FEATURES])[:,1]
    # Fit a Platt calibrator on validation ONLY, never on test.
    if val.target.nunique()<2: return None,'Calibration sample has only one outcome.'
    eps=1e-6
    logit=lambda a: np.log(np.clip(a,eps,1-eps)/(1-np.clip(a,eps,1-eps)))
    calibrator=LogisticRegression(max_iter=1000).fit(logit(val_p).reshape(-1,1),val.target)
    p=calibrator.predict_proba(logit(raw_test_p).reshape(-1,1))[:,1]
    metrics={'windows':len(x),'train':len(train),'calibration':len(val),'test':len(test),'accuracy':float(np.mean((p>=.5)==test.target)),'brier':float(brier_score_loss(test.target,p)),'baseline_brier':float(brier_score_loss(test.target,np.full(len(test),train.target.mean()))),'log_loss':float(log_loss(test.target,p,labels=[0,1]))}
    return ((model,calibrator),metrics,p,test),None

def proxy_probability(df,remaining,spot,strike):
    x=features(df)
    ret=x.ret1.dropna().tail(120)
    if len(ret)<30 or strike is None or remaining<=0: return None
    sigma=max(float(ret.std()),.00002)
    drift=float(ret.tail(15).mean())*.25
    z=(math.log(spot/strike)+drift*remaining/60)/(sigma*math.sqrt(max(remaining/60,1)))
    return float(.5*(1+math.erf(z/math.sqrt(2))))

def decision(prob,ask,seconds_left,verified,fee_buffer=.025,min_edge=.06):
    if not verified or prob is None or ask is None or seconds_left<30: return 'WAIT',None
    edge=prob-ask-fee_buffer
    return ('PAPER UP' if edge>=min_edge else 'WAIT'),edge

def init_db(path):
    con=sqlite3.connect(path)
    con.execute('CREATE TABLE IF NOT EXISTS paper (id INTEGER PRIMARY KEY, created_utc TEXT, slug TEXT, side TEXT, ask REAL, model_prob REAL, edge REAL, size_usd REAL, shares REAL, status TEXT DEFAULT "OPEN", outcome TEXT, pnl REAL, UNIQUE(slug,side))')
    con.commit();return con

def paper_trade(con,market,side,ask,prob,edge,stake):
    if not (0<ask<1 and 0<=prob<=1 and stake>0): raise ValueError('Invalid paper trade')
    con.execute('INSERT OR IGNORE INTO paper(created_utc,slug,side,ask,model_prob,edge,size_usd,shares) VALUES(?,?,?,?,?,?,?,?)',(datetime.now(timezone.utc).isoformat(),market['slug'],side,ask,prob,edge,stake,stake/ask))
    con.commit()

def settle_paper(con,slug,outcome):
    if outcome not in ('UP','DOWN'): raise ValueError('Invalid outcome')
    rows=con.execute('SELECT id,side,size_usd,shares FROM paper WHERE slug=? AND status="OPEN"',(slug,)).fetchall()
    for id,side,stake,shares in rows:
        pnl=(shares if side==outcome else 0)-stake
        con.execute('UPDATE paper SET status="SETTLED",outcome=?,pnl=? WHERE id=?',(outcome,pnl,id))
    con.commit()
