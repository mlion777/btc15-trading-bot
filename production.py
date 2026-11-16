"""Operational research tools: independently persisted observations, audit and rolling proxy evaluation.
Never authenticates Chainlink outcomes and never places real orders.
"""
import json, math, sqlite3, time
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import brier_score_loss, log_loss
from engine import FEATURES, features

SCHEMA = '''
CREATE TABLE IF NOT EXISTS observations (
 id INTEGER PRIMARY KEY, captured_at TEXT NOT NULL, captured_epoch REAL NOT NULL,
 slug TEXT NOT NULL, market_start INTEGER NOT NULL, market_end INTEGER NOT NULL,
 spot REAL, spot_source TEXT, reference REAL, reference_grade TEXT,
 up_bid REAL, up_ask REAL, down_bid REAL, down_ask REAL,
 up_vwap REAL, down_vwap REAL, up_fillable INTEGER, down_fillable INTEGER,
 up_spread REAL, down_spread REAL, up_depth_usd REAL, down_depth_usd REAL,
 spot_age_seconds REAL, spot_gaps INTEGER, quote_skew_seconds REAL,
 market_active INTEGER, accepting_orders INTEGER, quality_ok INTEGER,
 failure_reason TEXT, UNIQUE(slug,captured_epoch)
);
CREATE TABLE IF NOT EXISTS official_outcomes (
 slug TEXT PRIMARY KEY, outcome TEXT NOT NULL CHECK(outcome IN ('UP','DOWN')),
 evidence_url TEXT NOT NULL, verified_at TEXT NOT NULL,
 verification_level TEXT NOT NULL DEFAULT 'USER_ATTESTED'
);
CREATE TABLE IF NOT EXISTS paper_signals (
 id INTEGER PRIMARY KEY, captured_at TEXT NOT NULL, slug TEXT NOT NULL,
 side TEXT NOT NULL CHECK(side IN ('UP','DOWN')), probability REAL NOT NULL,
 quote_vwap REAL NOT NULL, stake REAL NOT NULL, shares REAL NOT NULL,
 assumed_fee REAL NOT NULL, model_version TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'OPEN', outcome TEXT, pnl REAL,
 UNIQUE(slug,model_version)
);
CREATE INDEX IF NOT EXISTS idx_obs_time ON observations(captured_epoch);
CREATE INDEX IF NOT EXISTS idx_obs_slug ON observations(slug);
'''

def open_db(path):
    con=sqlite3.connect(path, timeout=20, check_same_thread=False)
    con.execute('PRAGMA busy_timeout=20000')
    con.execute('PRAGMA journal_mode=WAL')
    con.executescript(SCHEMA)
    return con

def parse_time(value):
    return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()

def quote_integrity(up,down,now=None,max_skew=12):
    now=time.time() if now is None else now
    if not up or not down:return False,'Order book unavailable',None
    try:
        timestamps=[parse_time(up['observed_at']),parse_time(down['observed_at'])]
        skew=max(timestamps)-min(timestamps)
        if skew>max_skew:return False,'UP/DOWN quote timestamps too far apart',skew
        if now-max(timestamps)>25:return False,'Order books stale',skew
        if any(t-now>5 for t in timestamps):return False,'Future quote timestamp',skew
        for book in (up,down):
            a,b=book.get('ask'),book.get('bid')
            if a is None or b is None or not (0<b<=a<1):return False,'Missing or crossed order book',skew
            if not book.get('fillable'):return False,'Insufficient displayed depth for paper stake',skew
        return True,'OK',skew
    except (TypeError,ValueError,KeyError,OverflowError):return False,'Invalid order book fields',None

def capture(con,m,spot,source,quality,up,down,now=None):
    now=time.time() if now is None else now
    valid,reason,skew=quote_integrity(up,down,now)
    issues=[]
    if not valid:issues.append(reason)
    if not quality.get('ok'):issues.append('Spot feed stale/gapped')
    if m.get('reference') is None:issues.append('Price-to-beat unavailable')
    if m.get('reference_grade')!='SOURCE_REPORTED':issues.append('Price-to-beat not source-reported')
    if m.get('active') is not True or m.get('accepting_orders') is not True:issues.append('Market not active/accepting')
    if not (m['start']<=now<m['end']):issues.append('Outside market window')
    ok=not issues
    def v(book,key):return book.get(key) if book else None
    record=(datetime.fromtimestamp(now,timezone.utc).isoformat(),now,m['slug'],m['start'],m['end'],spot,source,
        m.get('reference'),m.get('reference_grade'),v(up,'bid'),v(up,'ask'),v(down,'bid'),v(down,'ask'),
        v(up,'vwap'),v(down,'vwap'),int(bool(v(up,'fillable'))),int(bool(v(down,'fillable'))),
        v(up,'spread'),v(down,'spread'),v(up,'ask_depth_usd'),v(down,'ask_depth_usd'),
        quality.get('age_seconds'),quality.get('gaps'),skew,int(m.get('active') is True),
        int(m.get('accepting_orders') is True),int(ok),'; '.join(issues))
    con.execute('''INSERT OR IGNORE INTO observations (
    captured_at,captured_epoch,slug,market_start,market_end,spot,spot_source,reference,reference_grade,
    up_bid,up_ask,down_bid,down_ask,up_vwap,down_vwap,up_fillable,down_fillable,
    up_spread,down_spread,up_depth_usd,down_depth_usd,spot_age_seconds,spot_gaps,
    quote_skew_seconds,market_active,accepting_orders,quality_ok,failure_reason
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',record)
    con.commit()
    return {'ok':ok,'reasons':issues,'quote_skew_seconds':skew}

def summary(con):
    counts=con.execute('SELECT COUNT(*),COUNT(DISTINCT slug),MIN(captured_at),MAX(captured_at),SUM(quality_ok) FROM observations').fetchone()
    return dict(zip(['observations','markets','first_utc','last_utc','quality_passes'],counts))

def evidence_outcome(con,slug,outcome,url):
    if outcome not in ('UP','DOWN'):raise ValueError('Invalid outcome')
    if not (url.startswith('https://') and len(url)>12):raise ValueError('Provide an HTTPS evidence URL')
    con.execute('INSERT INTO official_outcomes(slug,outcome,evidence_url,verified_at,verification_level) VALUES(?,?,?,?,?) ON CONFLICT(slug) DO UPDATE SET outcome=excluded.outcome,evidence_url=excluded.evidence_url,verified_at=excluded.verified_at,verification_level=excluded.verification_level',
        (slug,outcome, url,datetime.now(timezone.utc).isoformat(),'USER_ATTESTED'))
    con.commit()

def audit_observations(con):
    """One quote per market, joined only to user-attested outcomes. Never claim independent verification."""
    return pd.read_sql_query('''SELECT o.*,r.outcome,r.evidence_url,r.verification_level FROM observations o
      JOIN official_outcomes r ON o.slug=r.slug WHERE o.quality_ok=1 AND o.id=(
      SELECT o2.id FROM observations o2 WHERE o2.slug=o.slug AND o2.quality_ok=1
      ORDER BY o2.captured_epoch ASC LIMIT 1) ORDER BY o.captured_epoch''',con)

def rolling_proxy(df,train_min=250,step=48,test_block=48):
    """Expanding walk-forward predictions. Labels are spot-price proxies, not official outcomes."""
    x=features(df).sort_values('ts').drop_duplicates('ts').reset_index(drop=True)
    x['epoch']=x.ts.astype('int64')//10**9
    x=x[x.epoch%900==0].copy().reset_index(drop=True)
    x['future_close']=x.close.shift(-1)
    x['next_epoch']=x.epoch.shift(-1)
    x=x[(x.next_epoch-x.epoch==900)].dropna(subset=FEATURES+['future_close']).reset_index(drop=True)
    x['y']=(x.future_close>=x.close).astype(int)
    # Purge the most recent training row before each test fold: its target ends at the fold start.
    if len(x)<train_min+test_block+2:return None,'Not enough complete windows for walk-forward research'
    predictions=[]; folds=[]
    for start in range(train_min+1,len(x),step):
        tr=x.iloc[:start-1];te=x.iloc[start:min(start+test_block,len(x))]
        if len(te)<10 or tr.y.nunique()!=2:continue
        model=make_pipeline(StandardScaler(),LogisticRegression(max_iter=1000,C=.2))
        model.fit(tr[FEATURES],tr.y)
        p=model.predict_proba(te[FEATURES])[:,1]
        predictions.extend({'ts':str(t),'prob_up_uncalibrated':float(q),'actual_up':int(y),'fold':len(folds)+1}
                           for t,q,y in zip(te.ts,p,te.y))
        folds.append({'train_n':len(tr),'test_n':len(te),'train_end':str(tr.ts.iloc[-1]),'test_start':str(te.ts.iloc[0])})
    if not predictions:return None,'No valid folds'
    pred=pd.DataFrame(predictions).drop_duplicates('ts')
    y=pred.actual_up.to_numpy();p=pred.prob_up_uncalibrated.to_numpy()
    return {'predictions':pred,'folds':pd.DataFrame(folds),'metrics':{
        'samples':len(pred),'folds':len(folds),'accuracy':float(np.mean((p>=.5)==y)),
        'brier':float(brier_score_loss(y,p)),'log_loss':float(log_loss(y,np.clip(p,1e-6,1-1e-6))),
        'majority_baseline_accuracy':float(max(y.mean(),1-y.mean())),
        'status':'UNCALIBRATED SPOT PROXY; NOT AN EXECUTABLE SIGNAL'}},None

def signal_gate(m,quality,up,down,prob_up=None,model_validated=False,stake=10,fee_fraction=.01,min_edge=.08,max_spread=.08,now=None):
    """Fail-closed gate. Requires externally established settlement-matched model validation."""
    now=time.time() if now is None else now
    failures=[]
    if not model_validated:failures.append('No independently validated settlement-matched model')
    if prob_up is None or not np.isfinite(prob_up) or not 0<=prob_up<=1:failures.append('No valid calibrated probability')
    if m.get('reference_grade')!='ORACLE_VERIFIED':failures.append('Oracle reference not independently verified')
    if not quality.get('ok'):failures.append('Spot data quality failed')
    ok,reason,_=quote_integrity(up,down,now)
    if not ok:failures.append(reason)
    if m.get('active') is not True or m.get('accepting_orders') is not True:failures.append('Market inactive')
    if not (30<=m.get('end',0)-now<=870):failures.append('Outside allowed entry window')
    if failures:return {'side':'WAIT','reasons':failures,'edge':None}
    choices=[]
    for side,book,p in [('UP',up,prob_up),('DOWN',down,1-prob_up)]:
        if book['spread']>max_spread:continue
        if not book['fillable'] or not book['shares']:continue
        net=p*book['shares']-stake*(1+fee_fraction)
        edge=net/stake
        choices.append((edge,side))
    if not choices:return {'side':'WAIT','reasons':['No executable qualifying order book'],'edge':None}
    edge,side=max(choices)
    return {'side':side if edge>=min_edge else 'WAIT','edge':edge,'reasons':[] if edge>=min_edge else ['Insufficient modeled net edge']}
