"""Single-screen BTC research chart with paper BTC P&L. Independent of Bucko."""
import time, sqlite3
from pathlib import Path
import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from strategy import resample,technical,consensus,zones
from paper import run,connect

st.set_page_config(page_title='BTC | Chart Terminal',layout='wide',initial_sidebar_state='collapsed')
st.markdown('''<style>
#MainMenu,footer,header,[data-testid="stSidebar"],[data-testid="stToolbar"], [data-testid="stDecoration"]{display:none!important}
.block-container{padding:0!important;max-width:100%!important}
[data-testid="stAppViewContainer"]{background:#070b0e}
[data-testid="stPlotlyChart"]{margin:0!important}
</style>''',unsafe_allow_html=True)
API='https://api.exchange.coinbase.com/products/BTC-USD'
@st.cache_data(ttl=8,show_spinner=False)
def minute_candles():
    r=requests.get(API+'/candles',params={'granularity':60},headers={'User-Agent':'BTC15-Paper-Research/1.0'},timeout=10)
    r.raise_for_status();x=r.json()
    if not isinstance(x,list):raise ValueError('Coinbase candles unavailable')
    d=pd.DataFrame(x,columns=['timestamp','low','high','open','close','volume'])
    d['ts']=pd.to_datetime(d.timestamp,unit='s',utc=True)
    for col in ('open','high','low','close','volume'):d[col]=pd.to_numeric(d[col],errors='coerce')
    return d[['ts','open','high','low','close','volume']].dropna().sort_values('ts').drop_duplicates('ts').reset_index(drop=True)
@st.cache_data(ttl=3,show_spinner=False)
def recent_trades():
    r=requests.get(API+'/trades',params={'limit':1000},headers={'User-Agent':'BTC15-Paper-Research/1.0'},timeout=10)
    r.raise_for_status();data=r.json()
    d=pd.DataFrame(data)
    if d.empty:return pd.DataFrame(columns=['ts','price','size','trade_id'])
    d['ts']=pd.to_datetime(d.time,utc=True,errors='coerce')
    d['price']=pd.to_numeric(d.price,errors='coerce');d['size']=pd.to_numeric(d['size'],errors='coerce')
    d['trade_id']=pd.to_numeric(d.trade_id,errors='coerce')
    return d[['ts','price','size','trade_id']].dropna().sort_values('ts')
def store_ticks(d):
    db=sqlite3.connect(str(Path(__file__).with_name('ticks.sqlite3')),timeout=5)
    db.execute('CREATE TABLE IF NOT EXISTS ticks (trade_id INTEGER PRIMARY KEY, ts TEXT, price REAL, size REAL)')
    if len(d):
        db.executemany('INSERT OR IGNORE INTO ticks VALUES (?,?,?,?)',[(int(r.trade_id),r.ts.isoformat(),float(r.price),float(r.size)) for r in d.itertuples()])
    cutoff=(pd.Timestamp.now(tz='UTC')-pd.Timedelta(hours=3)).isoformat()
    db.execute('DELETE FROM ticks WHERE ts<?',(cutoff,));db.commit()
    out=pd.read_sql_query('SELECT ts,price,size FROM ticks ORDER BY ts',db);db.close()
    if len(out):out['ts']=pd.to_datetime(out.ts,utc=True)
    return out
def from_ticks(d,seconds):
    if d.empty:return pd.DataFrame(columns=['ts','open','high','low','close','volume'])
    a=d.set_index('ts').resample(f'{seconds}s').agg(open=('price','first'),high=('price','max'),low=('price','min'),close=('price','last'),volume=('size','sum')).dropna(subset=['open']).reset_index()
    return a

@st.fragment(run_every='5s')
def terminal():
    try:
        m=minute_candles(); ticks=store_ticks(recent_trades())
        if len(m)<40:raise ValueError('Insufficient Coinbase history')
        now=pd.Timestamp.now(tz='UTC')
        # Discard latest incomplete minute for strategy/zone computations.
        closed=m[m.ts<now.floor('min')].copy()
        frames={'1s':from_ticks(ticks,1),'5s':from_ticks(ticks,5),'10s':from_ticks(ticks,10),'15s':from_ticks(ticks,15),'30s':from_ticks(ticks,30),
                '1m':m,'2m':resample(m,120),'3m':resample(m,180),'5m':resample(m,300),'15m':resample(m,900)}
        # If 15s/30s history is warming up, use confirmed 1m + 5m bias as a WATCH, not an entry.
        direction,reads,why=consensus(frames)
        primary=technical(m)
        price=float(ticks.price.iloc[-1]) if len(ticks) else float(m.close.iloc[-1])
        last_tick=ticks.ts.iloc[-1] if len(ticks) else m.ts.iloc[-1]
        age=(now-last_tick).total_seconds()
        can_paper=direction in ('UP','DOWN') and age<12 and len(frames['15s'])>=36 and len(frames['30s'])>=36
        paper_side=direction if can_paper else 'WAIT'
        # Paper orders are simulated on BTC spot movements, NOT Polymarket contract prices.
        result=run(paper_side,price,why,stake=10) if age<12 else {'open':None,'stats':(0,0,0),'history':[],'action':'STALE DATA: NO NEW ENTRY'}
        d=m.tail(180).copy()
        fig=go.Figure()
        fig.add_trace(go.Candlestick(x=d.ts,open=d.open,high=d.high,low=d.low,close=d.close,name='BTC',
            increasing=dict(line=dict(color='#16d995'),fillcolor='#139b73'),
            decreasing=dict(line=dict(color='#ff5371'),fillcolor='#c83b55'),showlegend=False))
        for n,color in ((9,'#52b9d4'),(21,'#c09cf5'),(34,'#dfa451')):
            fig.add_trace(go.Scatter(x=d.ts,y=d.close.ewm(span=n,adjust=False).mean(),mode='lines',name=f'EMA {n}',line=dict(color=color,width=1.3)))
        future=d.ts.iloc[-1]+pd.Timedelta(minutes=12)
        for label,lo,hi,t,color in zones(closed):
            if t<d.ts.iloc[0]:continue
            fig.add_shape(type='rect',x0=t,x1=future,y0=lo,y1=hi,fillcolor=color,opacity=.18,line_width=0,layer='below')
            fig.add_annotation(x=future,y=(lo+hi)/2,text=label,xanchor='right',showarrow=False,font=dict(color=color,size=10))
        # Display only actual recorded paper entries/exits; never retrospectively paint simulated calls.
        for side,entry_ts,entry_price,exit_ts,exit_price,pnl,reason in result['history']:
            t=pd.to_datetime(entry_ts,unit='s',utc=True)
            if t>=d.ts.iloc[0]:
                fig.add_annotation(x=t,y=entry_price,text=('▲ LONG' if side=='UP' else '▼ SHORT'),showarrow=True,
                    arrowhead=0,ax=0,ay=40 if side=='UP' else -40,bgcolor='#b5fa4c' if side=='UP' else '#ff5774',font=dict(color='#0b1011',size=11),borderpad=5)
            if exit_ts:
                x=pd.to_datetime(exit_ts,unit='s',utc=True)
                if x>=d.ts.iloc[0]:fig.add_annotation(x=x,y=exit_price,text=f'EXIT ${pnl:+.2f}',showarrow=True,arrowhead=0,ax=0,ay=-35,bgcolor='#3b4551',font=dict(color='white',size=10))
        seconds=900-(int(now.timestamp())%900)
        display_side=direction if direction!='WAIT' else primary['side']+' WATCH' if primary['side']!='WAIT' else 'WAIT'
        status=f'BTCUSD  ${price:,.2f}     •     {display_side}     •     15M  {seconds//60:02d}:{seconds%60:02d}     •     PAPER BTC ONLY'
        fig.update_layout(template='plotly_dark',paper_bgcolor='#070b0e',plot_bgcolor='#070b0e',height=900,
            margin=dict(l=10,r=75,t=100,b=25),font=dict(color='#b8c7c9'),title=dict(text=status,x=.015,font=dict(size=16)),
            xaxis=dict(rangeslider=dict(visible=False),gridcolor='#182429',showspikes=True),
            yaxis=dict(side='right',gridcolor='#182429',tickformat=',.2f',showspikes=True),
            hovermode='x unified',dragmode='pan',
            annotations=list(fig.layout.annotations)+[dict(x=.01,y=1.04,xref='paper',yref='paper',xanchor='left',showarrow=False,
              text=f"1s · 5s · 10s · 15s · 30s · 1m · 2m · 3m · 5m · 15m analyzed | 1m candles shown | {why} | Paper: {result['action'] or 'monitoring'} | Closed: {result['stats'][0]} / P&L ${result['stats'][1]:+.2f}",font=dict(size=11,color='#9caeb2'))])
        st.plotly_chart(fig,use_container_width=True,config={'scrollZoom':True,'displayModeBar':True})
    except Exception as e:
        st.error(f'Chart temporarily unavailable: {type(e).__name__}: {e}')
terminal()
