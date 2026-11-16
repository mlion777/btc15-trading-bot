"""Research utilities. All external prices are labeled by provenance; no execution."""
import io, json, math, sqlite3, time
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import requests
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import brier_score_loss, log_loss
from engine import FEATURES, features, get, GAMMA, CLOB

UA={'User-Agent':'BTC15SignalLab/2.0'}

def get_metadata_reference(event):
    """Prefer the actual market metadata; source-matched != independently oracle-verified."""
    for item in [event, *(event.get('markets') or [])]:
        meta=item.get('eventMetadata') or {}
        if isinstance(meta,str):
            try:meta=json.loads(meta)
            except ValueError:meta={}
        for key in ('priceToBeat','openPrice'):
            v=meta.get(key)
            try:
                v=float(v)
                if 1000<v<1000000:return v,'Gamma eventMetadata.'+key,'SOURCE_REPORTED'
            except (TypeError,ValueError):pass
    return None,'Not provided in Gamma event metadata','UNAVAILABLE'

def market_bundle(now=None):
    now=time.time() if now is None else now
    start=int(now//900)*900
    slug=f'btc-updown-15m-{start}'
    items=get(GAMMA+'/events',{'slug':slug})
    if not items:raise ValueError('Market event not found')
    event=items[0]; markets=event.get('markets') or []
    if not markets:raise ValueError('No markets attached')
    market=markets[0]
    def parse(x):return json.loads(x) if isinstance(x,str) else x
    outcomes=parse(market.get('outcomes') or []); tokens=parse(market.get('clobTokenIds') or [])
    mapping={str(o).strip().lower():str(t) for o,t in zip(outcomes,tokens)}
    if 'up' not in mapping or 'down' not in mapping:raise ValueError('Outcome mapping invalid')
    ref,refsource,grade=get_metadata_reference(event)
    if ref is None:
        from engine import official_reference
        ref,refsource=official_reference(start,start+900)
        grade='SOURCE_REPORTED' if ref is not None else 'UNAVAILABLE'
    return {'slug':slug,'start':start,'end':start+900,'seconds_left':max(0,start+900-now),
            'up':mapping['up'],'down':mapping['down'],'url':'https://polymarket.com/event/'+slug,
            'rules':market.get('description') or event.get('description') or '',
            'reference':ref,'reference_source':refsource,'reference_grade':grade,
            'volume':market.get('volumeNum') or market.get('volume'),
            'liquidity':market.get('liquidityNum') or market.get('liquidity'),
            'active':market.get('active'),'accepting_orders':market.get('acceptingOrders'),
            'market_id':market.get('id'),'fee_schedule':market.get('feeSchedule')}

def detailed_book(token,stake=10):
    raw=get(CLOB+'/book',{'token_id':token})
    asks=sorted([(float(x['price']),float(x['size'])) for x in raw.get('asks',[])],key=lambda x:x[0]);
    bids=sorted([(float(x['price']),float(x['size'])) for x in raw.get('bids',[])],key=lambda x:-x[0])
    ask=asks[0][0] if asks else None; bid=bids[0][0] if bids else None
    # Cost-to-fill for an approximate fixed USD spend; price * shares = dollars.
    remaining=float(stake);shares=0.;spent=0.
    for price,qty in asks:
        if price<=0:continue
        buy=min(qty,remaining/price)
        shares+=buy;spent+=buy*price;remaining-=buy*price
        if remaining<1e-8:break
    return {'ask':ask,'bid':bid,'spread':ask-bid if ask is not None and bid is not None else None,
            'asks':asks[:15],'bids':bids[:15], 'ask_depth_usd':sum(p*q for p,q in asks[:5]),
            'bid_depth_usd':sum(p*q for p,q in bids[:5]), 'fillable':remaining<1e-6,
            'vwap':spent/shares if shares else None,'shares':shares,'unfilled_usd':remaining,
            'observed_at':datetime.now(timezone.utc).isoformat()}

def spot_quality(df,now=None):
    now=pd.Timestamp.now(tz='UTC') if now is None else pd.Timestamp(now)
    x=df.sort_values('ts').drop_duplicates('ts').copy()
    x=x[x.ts<now.floor('min')]
    if x.empty:return {'ok':False,'reason':'No completed candles'}
    age=(now-x.ts.iloc[-1]).total_seconds()
    delta=x.ts.diff().dt.total_seconds().dropna()
    gaps=int((delta>61).sum())
    invalid=int(((x.low>x.high)|(x.close<=0)|(x.open<=0)|(x.volume<0)).sum())
    return {'ok':age<=150 and gaps==0 and invalid==0,'age_seconds':age,'gaps':gaps,
            'invalid_rows':invalid,'last_ts':str(x.ts.iloc[-1]),'rows':len(x),
            'reason':('OK' if age<=150 and gaps==0 and invalid==0 else 'Stale, missing, or invalid candles')}

def zones(df):
    x=features(df).dropna(subset=['close'])
    if len(x)<50:return {}
    last=x.iloc[-1];cl=float(last.close)
    out={'spot':cl,'ema9':float(x.close.ewm(span=9,adjust=False).mean().iloc[-1]),
         'ema21':float(x.close.ewm(span=21,adjust=False).mean().iloc[-1]),
         'ema55':float(x.close.ewm(span=55,adjust=False).mean().iloc[-1]),
         'rsi14':float(last.rsi) if np.isfinite(last.rsi) else None,
         'volatility_1m':float(last.volatility) if np.isfinite(last.volatility) else None}
    for n in (15,60,180):
        y=x.tail(n)
        out[f'support_{n}m']=float(y.low.min());out[f'resistance_{n}m']=float(y.high.max())
    ema12=x.close.ewm(span=12,adjust=False).mean();ema26=x.close.ewm(span=26,adjust=False).mean()
    macd=ema12-ema26;signal=macd.ewm(span=9,adjust=False).mean()
    out['macd_histogram']=float((macd-signal).iloc[-1]);out['trend']='BULLISH' if out['ema9']>out['ema21']>out['ema55'] else ('BEARISH' if out['ema9']<out['ema21']<out['ema55'] else 'MIXED')
    return out

def history_binance(days=14, progress=None, max_calls=250):
    """Download historical 1m candles, page backwards; no future or incomplete candles."""
    days=max(1,min(int(days),90));now_ms=int(time.time()//60*60*1000)
    earliest=now_ms-days*86400000;cursor=earliest;rows=[];calls=0
    while cursor<now_ms and calls<max_calls:
        data=get('https://api.binance.com/api/v3/klines',{'symbol':'BTCUSDT','interval':'1m','startTime':cursor,'endTime':now_ms-1,'limit':1000})
        if not data:break
        rows.extend(data);last=int(data[-1][0]);new_cursor=last+60000
        if new_cursor<=cursor:break
        cursor=new_cursor;calls+=1
        if progress:progress(min(1,(cursor-earliest)/(now_ms-earliest)))
    if not rows:raise RuntimeError('No Binance candles returned. Upload CSV instead.')
    df=pd.DataFrame(rows,columns=['unix','open','high','low','close','volume','close_ts','quote','trades','taker_base','taker_quote','unused'])
    df['ts']=pd.to_datetime(df.unix,unit='ms',utc=True)
    for c in ['open','high','low','close','volume']:df[c]=pd.to_numeric(df[c])
    return df[['ts','open','high','low','close','volume']].drop_duplicates('ts').sort_values('ts').reset_index(drop=True)

def research_backtest(df,min_windows=250,fee_buffer=.03,min_edge=.06):
    """Spot-PROXY 15m direction research, strictly chronological, non-overlapping."""
    x=features(df).sort_values('ts').drop_duplicates('ts').reset_index(drop=True)
    # Require all 15 one-minute bars in each subsequent prediction window.
    x['continuous_next_15m']=(x.ts.shift(-15)-x.ts).dt.total_seconds().eq(900)
    x['epoch']=x.ts.astype('int64')//10**9
    x=x[x.epoch%900==0].copy().reset_index(drop=True)
    x['next_epoch']=x.epoch.shift(-1)
    x['future_close']=x.close.shift(-1)
    x=x[(x.next_epoch-x.epoch==900) & x.continuous_next_15m].dropna(subset=FEATURES+['future_close']).copy()
    x['target']=(x.future_close>=x.close).astype(int)
    if len(x)<min_windows:return None,f'Need at least {min_windows} contiguous, non-overlapping 15-minute windows; found {len(x)}.'
    a=int(len(x)*.6);b=int(len(x)*.8);train=x.iloc[:a];val=x.iloc[a:b];test=x.iloc[b:]
    if train.target.nunique()<2 or val.target.nunique()<2:return None,'Training/calibration labels must include both directions.'
    model=make_pipeline(StandardScaler(),LogisticRegression(max_iter=2000,C=.2))
    model.fit(train[FEATURES],train.target)
    raw_val=np.clip(model.predict_proba(val[FEATURES])[:,1],1e-6,1-1e-6)
    raw_test=np.clip(model.predict_proba(test[FEATURES])[:,1],1e-6,1-1e-6)
    logit=lambda p:np.log(p/(1-p))
    cal=LogisticRegression(max_iter=2000).fit(logit(raw_val).reshape(-1,1),val.target)
    pred=np.clip(cal.predict_proba(logit(raw_test).reshape(-1,1))[:,1],1e-6,1-1e-6)
    y=test.target.to_numpy()
    metrics={'windows':len(x),'train_windows':len(train),'calibration_windows':len(val),'holdout_windows':len(test),
             'holdout_accuracy':float(np.mean((pred>=.5)==y)),
             'holdout_brier':float(brier_score_loss(y,pred)),
             'baseline_brier':float(brier_score_loss(y,np.full(len(y),train.target.mean()))),
             'holdout_log_loss':float(log_loss(y,pred,labels=[0,1])),
             'holdout_ece':float(expected_calibration_error(y,pred)),
             'holdout_majority_accuracy':float(max(y.mean(),1-y.mean()))}
    result=pd.DataFrame({'ts':test.ts.values,'prob_up':pred,'actual_up':y})
    result['predicted_up']=result.prob_up>=.5
    result['correct']=result.predicted_up==result.actual_up
    result['confidence']=np.maximum(result.prob_up,1-result.prob_up)
    # No executable Polymarket asks in this dataset. Do not compute fictitious ROI.
    return {'metrics':metrics,'predictions':result,'model':model,'calibrator':cal,
            'train_end':str(train.ts.iloc[-1]),'calibration_end':str(val.ts.iloc[-1]),
            'test_start':str(test.ts.iloc[0]),'last_data':str(x.ts.iloc[-1])},None

def expected_calibration_error(y,p,bins=10):
    y=np.asarray(y);p=np.asarray(p);e=0.
    for i in range(bins):
        mask=(p>=i/bins)&(p<((i+1)/bins if i<bins-1 else 1.000001))
        if mask.any():e+=mask.mean()*abs(y[mask].mean()-p[mask].mean())
    return e

def reliability_table(result,bins=10):
    d=result.copy();d['bucket']=pd.cut(d.prob_up,np.linspace(0,1,bins+1),include_lowest=True)
    return d.groupby('bucket',observed=False).agg(count=('actual_up','size'),forecast=('prob_up','mean'),observed=('actual_up','mean')).reset_index().astype({'bucket':str})

def init_research_db(path):
    con=sqlite3.connect(path,check_same_thread=False,timeout=15)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('''CREATE TABLE IF NOT EXISTS snapshots (id INTEGER PRIMARY KEY, captured_utc TEXT NOT NULL,slug TEXT NOT NULL, seconds_left REAL,spot REAL,spot_source TEXT,reference REAL,reference_grade TEXT,up_bid REAL,up_ask REAL,down_bid REAL,down_ask REAL,up_vwap REAL,down_vwap REAL,up_depth_usd REAL,down_depth_usd REAL,trend TEXT, rsi REAL,volatility REAL, UNIQUE(slug,captured_utc))''')
    con.execute('''CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY,created_utc TEXT,slug TEXT,side TEXT,stake REAL,entry_vwap REAL,shares REAL,fees REAL,status TEXT DEFAULT 'OPEN',outcome TEXT,pnl REAL,reference_grade TEXT, notes TEXT)''')
    con.commit();return con

def record_snapshot(con,m,spot,source,up,down,z):
    con.execute('''INSERT INTO snapshots(captured_utc,slug,seconds_left,spot,spot_source,reference,reference_grade,up_bid,up_ask,down_bid,down_ask,up_vwap,down_vwap,up_depth_usd,down_depth_usd,trend,rsi,volatility) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
    (datetime.now(timezone.utc).isoformat(),m['slug'],m['seconds_left'],spot,source,m['reference'],m['reference_grade'],up['bid'],up['ask'],down['bid'],down['ask'],up['vwap'],down['vwap'],up['ask_depth_usd'],down['ask_depth_usd'],z.get('trend'),z.get('rsi14'),z.get('volatility_1m')))
    con.commit()

def record_trade(con,m,side,ob,stake,fee_pct=0,notes=''):
    if not ob['fillable'] or ob['vwap'] is None or not 0<ob['vwap']<1:raise ValueError('Insufficient order-book liquidity for this stake')
    if m['seconds_left']<=15:raise ValueError('Too close to market close')
    fee=stake*fee_pct;shares=ob['shares']
    con.execute('''INSERT INTO trades(created_utc,slug,side,stake,entry_vwap,shares,fees,reference_grade,notes) VALUES(?,?,?,?,?,?,?,?,?)''',
        (datetime.now(timezone.utc).isoformat(),m['slug'],side,stake,ob['vwap'],shares,fee,m['reference_grade'],notes))
    con.commit()

def settle_trade(con,trade_id,outcome,source_note):
    if outcome not in ('UP','DOWN'):raise ValueError('Invalid outcome')
    if not source_note.strip():raise ValueError('Settlement evidence note is required')
    row=con.execute('SELECT side,stake,shares,fees,status FROM trades WHERE id=?',(trade_id,)).fetchone()
    if row is None or row[4]!='OPEN':raise ValueError('Trade not open')
    pnl=(row[2] if row[0]==outcome else 0)-row[1]-row[3]
    con.execute('UPDATE trades SET status=?,outcome=?,pnl=?,notes=COALESCE(notes,\'\')||? WHERE id=?',('SETTLED',outcome,pnl,' | settlement: '+source_note,trade_id));con.commit()

def market_history(token, start=None,end=None):
    params={'market':token,'interval':'max','fidelity':1}
    if start is not None:params['startTs']=int(start)
    if end is not None:params['endTs']=int(end)
    raw=get(CLOB+'/prices-history',params)
    return pd.DataFrame(raw.get('history') or [])

def evaluate_market_predictions(data, fee_pct=.01, min_edge=.06, min_seconds=30):
    """Evaluate user-supplied timestamped predictions against actual settled labels and executable quotes.
    Data MUST be independently collected, chronological, and not in-sample model predictions.
    This function cannot authenticate the provenance of uploaded rows.
    """
    needed={'timestamp','slug','prob_up','up_ask','down_ask','actual_up','seconds_left'}
    missing=needed-set(data.columns)
    if missing:raise ValueError('Missing columns: '+', '.join(sorted(missing)))
    x=data.copy()
    x['timestamp']=pd.to_datetime(x.timestamp,utc=True,errors='raise')
    for c in needed-{'timestamp','slug'}:x[c]=pd.to_numeric(x[c],errors='raise')
    if x[sorted(needed-{'timestamp','slug'})].isna().any().any():raise ValueError('Null numeric values are not allowed')
    if not x.actual_up.isin([0,1]).all():raise ValueError('actual_up must be 0 or 1')
    if not x.prob_up.between(0,1).all():raise ValueError('Invalid probabilities')
    if not x.up_ask.between(.001,.999).all() or not x.down_ask.between(.001,.999).all():raise ValueError('Invalid asks')
    if x.duplicated(['slug','timestamp']).any():raise ValueError('Duplicate slug/timestamp rows')
    x=x.sort_values('timestamp').reset_index(drop=True)
    if len(x)<30:raise ValueError('At least 30 prediction snapshots required for basic descriptive analysis')
    x['pnl_per_dollar']=0.;x['side']='WAIT'
    # One candidate per market, first qualifying snapshot, to avoid duplicate outcome counting.
    seen=set()
    for i,row in x.iterrows():
        if row.slug in seen or row.seconds_left<min_seconds:continue
        up_net=row.prob_up-row.up_ask*(1+fee_pct)
        down_net=(1-row.prob_up)-row.down_ask*(1+fee_pct)
        if max(up_net,down_net)<min_edge:continue
        side='UP' if up_net>=down_net else 'DOWN'
        ask=row.up_ask if side=='UP' else row.down_ask
        # Buy $1 of contracts at ask; fixed fraction fee charged on cash spent.
        won=(row.actual_up==1) if side=='UP' else (row.actual_up==0)
        x.at[i,'pnl_per_dollar']=(1/ask if won else 0)-1-fee_pct
        x.at[i,'side']=side
        seen.add(row.slug)
    trades=x[x.side!='WAIT'].copy()
    baseline=np.full(len(x),x.actual_up.mean())
    out={'rows':len(x),'unique_markets':x.slug.nunique(), 'trades':len(trades),
         'brier':float(brier_score_loss(x.actual_up,x.prob_up)),
         'baseline_brier':float(brier_score_loss(x.actual_up,baseline)),
         'ece':float(expected_calibration_error(x.actual_up,x.prob_up)),
         'paper_win_rate':float(((trades.side=='UP')==(trades.actual_up==1)).mean()) if len(trades) else None,
         'paper_total_pnl_per_1usd_trade':float(trades.pnl_per_dollar.sum()) if len(trades) else 0.,
         'paper_average_roi_per_trade':float(trades.pnl_per_dollar.mean()) if len(trades) else None,
         'assumptions':'Asks assumed fully executable at timestamp, fees fixed; no queue delay, slippage, market impact or oracle provenance verification.'}
    return out,trades,x
