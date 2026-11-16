"""BTC15 Signal Lab v2. Research dashboard; no real-money execution."""
import io, json, time
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from engine import candles, features, proxy_probability
from live_signals import technical_signal
from scalp import scalp_screen
from microstructure import recent_trades, accumulate_trades, provisional_candles, pressure, supply_demand_zones
from streamlit_autorefresh import st_autorefresh
from advanced import (market_bundle,detailed_book,spot_quality,zones,history_binance,research_backtest,
    reliability_table,evaluate_market_predictions,init_research_db,record_snapshot,record_trade,settle_trade,market_history)

st.set_page_config(page_title='BTC15 Intelligence Terminal',page_icon='₿',layout='wide',initial_sidebar_state='expanded')
st.markdown('''<style>.block-container{padding-top:1.2rem;max-width:1550px}div[data-testid="stMetric"]{background:#131e2b;border:1px solid #29384b;border-radius:12px;padding:12px} .stApp{background:#0b111b;color:#e8eef7}h1,h2,h3{letter-spacing:-.025em}</style>''',unsafe_allow_html=True)
st.title('₿ BTC15 Intelligence Terminal')
st.caption('POLYMARKET BTC 15-MIN UP/DOWN  •  LIVE MARKET RESEARCH  •  PAPER TRADING ONLY  •  NO EXECUTION KEYS')
with st.sidebar:
    st.header('Terminal settings')
    refresh=st.slider('Refresh every (seconds)',2,60,2)
    auto_refresh=st.toggle('Auto-refresh live dashboard',value=True)
    if auto_refresh:st_autorefresh(interval=refresh*1000,key='btc15_auto_refresh')
    stake=st.number_input('Paper order size ($)',1.,10000.,10.,1.)
    fee_pct=st.slider('Paper fee assumption (%)',0.,10.,1.,.1)/100
    min_edge=st.slider('Minimum modeled edge (percentage points)',1,30,8)/100
    max_spread=st.slider('Maximum acceptable spread',.01,.25,.08,.01)
    st.warning('All model probabilities in live view are illustrative and UNCALIBRATED. A real edge is NOT established. No automatic entries.')
    st.markdown('**Feed status** and snapshot capture are visible below. Refresh works only while the app is running.')

@st.cache_data(ttl=8,show_spinner=False)
def fetch_market():return market_bundle()
@st.cache_data(ttl=10,show_spinner=False)
def fetch_candles():return candles()
@st.cache_data(ttl=2,show_spinner=False)
def fetch_book(token,size):return detailed_book(token,size)
@st.cache_data(ttl=30,show_spinner=False)
def fetch_history(token,start,end):return market_history(token,start,end)

@st.cache_data(ttl=2,show_spinner=False)
def fetch_ticks():return recent_trades(100)

con=init_research_db(str(Path(__file__).with_name('research.db')))
market=btc=source=up=down=None
errors=[]
try:market=fetch_market()
except Exception as e:errors.append('Polymarket discovery: '+str(e))
try:btc,source=fetch_candles()
except Exception as e:errors.append('Bitcoin spot candles: '+str(e))
if market:
    try:up=fetch_book(market['up'],stake);down=fetch_book(market['down'],stake)
    except Exception as e:errors.append('CLOB order books: '+str(e))
# Poll recent exchange trades. Repeated polling is near-real-time, NOT a true websocket tick stream.
ticks=[];tick_error=None
try:
    fresh=fetch_ticks()
    st.session_state['recent_spot_trades']=accumulate_trades(st.session_state.get('recent_spot_trades',[]),fresh)
    ticks=st.session_state['recent_spot_trades']
except Exception as exc:
    tick_error=str(exc)
    st.session_state['recent_spot_trades']=[]  # fail closed; do not show old trades as live

for e in errors:st.error(e)
now=pd.Timestamp.now(tz='UTC')
if btc is not None:
    btc=btc.copy();btc['ts']=pd.to_datetime(btc.ts,utc=True)
    btc=btc[btc.ts<now.floor('min')].sort_values('ts').drop_duplicates('ts')
quality=spot_quality(btc,now) if btc is not None else {'ok':False,'reason':'Unavailable'}
z=zones(btc) if btc is not None and len(btc)>60 else {}
spot=z.get('spot')
if ticks:spot=ticks[-1]['price']  # Coinbase last observed trade, distinct from closed-candle proxy
if market:
    st.markdown(f"**Market:** [{market['slug']}]({market['url']}) · **UTC start:** {pd.to_datetime(market['start'],unit='s',utc=True)} · **UTC end:** {pd.to_datetime(market['end'],unit='s',utc=True)}")

c1,c2,c3,c4,c5=st.columns(5)
c1.metric('BTC spot (Coinbase trade proxy)' ,f'${spot:,.2f}' if spot else '—')
c2.metric('Price to beat (source)',f"${market['reference']:,.2f}" if market and market['reference'] else 'UNAVAILABLE')
c3.metric('Time remaining',f"{int(market['seconds_left'])//60:02d}:{int(market['seconds_left'])%60:02d}" if market else '—')
c4.metric('UP best ask',f"{up['ask']:.3f}" if up and up['ask'] is not None else '—')
c5.metric('DOWN best ask',f"{down['ask']:.3f}" if down and down['ask'] is not None else '—')

status='WAIT — DATA NOT READY'
if market and quality['ok'] and up and down and market['reference'] is not None and market['seconds_left']>30:
    status='WAIT — UNCALIBRATED'
signal=technical_signal(btc,z,market,up,down,quality,min_edge=min_edge,max_spread=max_spread,fee=fee_pct) if btc is not None else {'bias':'WAIT','candidate':'NONE','prob_up':None,'reason':'No candles','edge':None,'score':0}
scalp=scalp_screen(z,market,up,down,quality,max_spread=max_spread,fee=fee_pct)
if scalp['side'] and ticks and (pd.Timestamp.now(tz='UTC')-ticks[-1]['ts']).total_seconds()>15:
    scalp={'side':None,'reason':'Coinbase trade feed stale; suppressing scalp candidate'}
if scalp['side']:
    st.success(f"**{scalp['status']}** · Simulated entry {scalp['entry']:.3f} · Illustrative target bid {scalp['exit_target']:.3f} · Gross target {scalp['gross_target_pct']:.1f}% (before costs/slippage)")
else:
    st.warning(f"**NO ENTRY** · {scalp['reason']} · The dashboard hides directional calls when filters fail.")
st.caption('PAPER SCALP is a technical screening result, not a validated profitable opportunity or real-money buy instruction. Target prices are hypothetical, not executable guarantees.')
if signal['prob_up'] is not None:
    ca,cb,cc=st.columns(3)
    ca.metric('Volatility-proxy UP likelihood (UNCALIBRATED)',f"{signal['prob_up']:.1%}")
    cb.metric('Volatility-proxy DOWN likelihood (UNCALIBRATED)',f"{1-signal['prob_up']:.1%}")
    cc.metric('Research edge vs executable ask',f"{signal['edge']:+.1%}" if signal['edge'] is not None else 'NO QUALIFYING QUOTE')
st.caption('Technical bias updates on refresh and is NOT a buy instruction. A paper candidate is a hypothesis, not a verified edge. Source-reported strike is not independently oracle verified. No live trading orders are placed.')

live,depth,history,paper,testing,health=st.tabs(['📈 Live terminal','📚 Order book & market','🧭 Price zones','📝 Paper portfolio','🧪 Historical lab','🩺 Data health & exports'])
with live:
    st.subheader('Live trade-tape and price zones')
    if ticks:
        last=ticks[-1]
        age=(pd.Timestamp.now(tz='UTC')-last['ts']).total_seconds()
        st.caption(f'Coinbase BTC-USD latest observed trade: {last["ts"]} UTC · {age:.1f}s old · {len(ticks)} unique recent trades collected while this session is open. Polls every {refresh}s, not every exchange tick.')
        if age>15:st.warning('Spot trade feed is stale (>15s); ignore live scalp candidates.')
    else:
        st.warning('Coinbase recent trades unavailable; only historical closed candles are shown. '+(tick_error or ''))
    for label,ob in [('UP',up),('DOWN',down)]:
        p=pressure(ob)
        if p:
            st.write(f'**{label} contract top-five-level depth:** bids ${p["bid_usd"]:,.0f} / asks ${p["ask_usd"]:,.0f} · bid share {p["bid_share"]:.0%} · imbalance {p["imbalance"]:+.1%}')
            st.progress(max(0.,min(1.,p['bid_share'])))
    st.caption('Order-book pressure is resting liquidity, not actual market buy/sell flow. UP and DOWN are separate contracts. Quotes may change or be cancelled.')
    if btc is not None and len(btc)>40:
        chart=btc.tail(240).copy()
        live_candles=provisional_candles(ticks)
        if not live_candles.empty:
            # Only overlay the current incomplete minute; avoid replacing authoritative historical bars.
            live_candles=live_candles[live_candles.ts>=now.floor('min')]
            chart=pd.concat([chart,live_candles],ignore_index=True).sort_values('ts').drop_duplicates('ts',keep='last')
        fig=go.Figure()
        fig.add_trace(go.Candlestick(x=chart.ts,open=chart.open,high=chart.high,low=chart.low,close=chart.close,name='BTC 1m candles + provisional trade-built candle'))
        for key,color in [('ema9','#5bc0eb'),('ema21','#f6c453'),('ema55','#bd8cff')]:
            s=btc.close.ewm(span=int(key[3:]),adjust=False).mean().tail(min(len(btc),240))
            fig.add_trace(go.Scatter(x=btc.ts.tail(len(s)),y=s,name=key.upper(),line=dict(color=color,width=1.3)))
        zone_data=supply_demand_zones(btc)
        for kind,color in [('demand','rgba(22,163,74,0.18)'),('supply','rgba(239,68,68,0.18)')]:
            for band in zone_data[kind]:
                fig.add_hrect(y0=band['low'],y1=band['high'],fillcolor=color,line_width=0,
                              annotation_text=kind.upper(),annotation_position='top left')
        if scalp.get('side') and ticks and (now-ticks[-1]['ts']).total_seconds()<=15:
            fig.add_annotation(x=chart.ts.iloc[-1],y=spot,text='PAPER '+scalp['side']+' candidate',
                               showarrow=True,arrowhead=2,ay=-55 if scalp['side']=='UP' else 55,
                               bgcolor='#164e3a' if scalp['side']=='UP' else '#7f1d1d',font=dict(color='white'))
        if market and market['reference']:
            fig.add_hline(y=market['reference'],line_dash='dash',line_color='#eab308',annotation_text='Source-reported price to beat')
        fig.update_layout(height=540,margin=dict(l=8,r=8,t=12,b=8),xaxis_rangeslider_visible=False,template='plotly_dark',legend_orientation='h',uirevision='btc15',xaxis=dict(type='date',range=[chart.ts.iloc[-1]-pd.Timedelta(minutes=80),now+pd.Timedelta(minutes=2)]))
        st.plotly_chart(fig,use_container_width=True,config={'scrollZoom':True,'displaylogo':False})
        if market and spot and market['reference']:
            distance=spot-market['reference']
            st.metric('Spot minus source-reported strike (NOT oracle)',f'${distance:+,.2f}',f'{100*distance/market["reference"]:+.3f}%')
            st.caption(f'Reference grade: {market["reference_grade"]} · {market["reference_source"]}. Source-reported does NOT mean independently Chainlink-verified.')
            proxy=proxy_probability(btc,market['seconds_left'],spot,market['reference'])
            if proxy is not None:
                st.write(f'Illustrative volatility-only UP estimate: **{proxy:.1%}** / DOWN estimate: **{1-proxy:.1%}**. **NOT CALIBRATED — DO NOT TREAT AS A TRADE SIGNAL.**')
    st.subheader('Directional context')
    if z:
        a,b,c,d=st.columns(4)
        a.metric('EMA trend',z['trend']);b.metric('RSI (14)',f"{z['rsi14']:.1f}" if z['rsi14'] is not None else '—')
        c.metric('MACD histogram',f"{z['macd_histogram']:+.2f}")
        d.metric('1m log-return volatility',f"{z['volatility_1m']:.5f}" if z['volatility_1m'] else '—')
    st.caption('The current 1-minute candle is provisional and reconstructed from recent Coinbase trade polls; gaps and missed trades are possible. The completed historical bars may come from a different exchange. Demand/supply bands are confirmed historical pivots, not guaranteed liquidity zones. Paper candidate markers are not validated entries.')
with depth:
    if market:
        st.write('**Market rules (always review before relying on the price to beat)**')
        st.text_area('Resolution description',market['rules'] or 'Not available; open the Polymarket event to review.',height=115,disabled=True)
        st.json({'market_id':market['market_id'],'active':market['active'],'accepting_orders':market['accepting_orders'],
                 'volume':market['volume'],'liquidity':market['liquidity'],'fee_schedule_raw':market['fee_schedule'],
                 'reference_grade':market['reference_grade']})
    for label,ob in [('UP',up),('DOWN',down)]:
        st.subheader(label+' — executable depth simulation')
        if ob:
            a,b,c,d=st.columns(4)
            a.metric('Bid',f"{ob['bid']:.4f}" if ob['bid'] is not None else '—')
            b.metric('Ask',f"{ob['ask']:.4f}" if ob['ask'] is not None else '—')
            c.metric('Spread',f"{ob['spread']:.4f}" if ob['spread'] is not None else '—')
            d.metric(f'VWAP for ${stake:.0f}',f"{ob['vwap']:.4f}" if ob['fillable'] else 'NOT FILLABLE')
            x,y=st.columns(2)
            with x:st.caption('ASK ladder (price, shares)');st.dataframe(pd.DataFrame(ob['asks'],columns=['price','shares']),hide_index=True)
            with y:st.caption('BID ladder (price, shares)');st.dataframe(pd.DataFrame(ob['bids'],columns=['price','shares']),hide_index=True)
            if ob['spread'] is not None and ob['spread']>max_spread:st.warning(f'{label} spread exceeds your maximum.')
    if market:
        with st.expander('Recent CLOB token price history (NOT historical executable asks)'):
            token=st.selectbox('Token for history',['UP','DOWN'])
            if st.button('Load CLOB price history'):
                try:
                    t=market['up'] if token=='UP' else market['down']
                    h=fetch_history(t,market['start'],market['end'])
                    if h.empty:st.info('No price history returned')
                    else:
                        h['time']=pd.to_datetime(h.t,unit='s',utc=True)
                        st.line_chart(h.set_index('time').p)
                except Exception as e:st.error(str(e))
with history:
    if z:
        st.subheader('Support, resistance & trend zones (spot proxy)')
        for period in (15,60,180):
            a,b=st.columns(2)
            a.metric(f'{period}m support (recent low)',f"${z[f'support_{period}m']:,.2f}")
            b.metric(f'{period}m resistance (recent high)',f"${z[f'resistance_{period}m']:,.2f}")
        st.write(f"EMA 9: ${z['ema9']:,.2f} · EMA 21: ${z['ema21']:,.2f} · EMA 55: ${z['ema55']:,.2f}")
        st.caption('These are rolling highs/lows, not proven institutional supply/demand or guaranteed reversal zones.')
with paper:
    st.subheader('Manual paper execution — order-book VWAP, not best-ask fantasy fills')
    st.caption('Quotes are snapshots. Simulated fills assume the displayed book stays available and do not model latency or queue priority. No real orders.')
    side=st.radio('Paper side',['UP','DOWN'],horizontal=True)
    ob=up if side=='UP' else down
    note=st.text_input('Entry rationale (optional)',placeholder='Hypothesis, trend context, observed catalyst')
    if ob and ob['fillable']:
        fee=stake*fee_pct
        st.write(f"Estimated **{ob['shares']:.3f} shares**, entry VWAP **${ob['vwap']:.4f}**, assumed fee **${fee:.2f}**, maximum loss **${stake+fee:.2f}**, winning net P&L **${ob['shares']-stake-fee:.2f}**.")
        st.caption(f'Break-even probability (including assumed fee): {(stake+fee)/ob["shares"]:.1%}. This is a price threshold, not a model forecast.')
    disabled=not (market and ob and ob['fillable'] and quality['ok'] and market['reference'] is not None and market['seconds_left']>30)
    if st.button('Record simulated entry',disabled=disabled):
        try:record_trade(con,market,side,ob,stake,fee_pct,note);st.success('Simulated trade saved.')
        except Exception as e:st.error(str(e))
    st.divider()
    trades=pd.read_sql_query('SELECT * FROM trades ORDER BY id DESC LIMIT 500',con)
    if not trades.empty:
        st.dataframe(trades,use_container_width=True,hide_index=True)
        csv=trades.to_csv(index=False).encode();st.download_button('Export paper trades CSV',csv,'btc15_paper_trades.csv','text/csv')
        settled=trades[trades.status=='SETTLED']
        if len(settled):
            a,b,c=st.columns(3);a.metric('Settled paper P&L',f'${settled.pnl.sum():,.2f}');b.metric('Settled trades',len(settled));c.metric('Win rate',f'{(settled.pnl>0).mean():.1%}')
        open_ids=trades.loc[trades.status=='OPEN','id'].tolist()
        if open_ids:
            st.subheader('Manual settlement (requires externally verified result)')
            tid=st.selectbox('Open paper trade ID',open_ids)
            outcome=st.radio('Winning side',['UP','DOWN'],horizontal=True,key='settle_side')
            evidence=st.text_input('Official settlement evidence URL / verification note (required)')
            if st.button('Mark paper trade settled',disabled=not evidence.strip()):
                try:settle_trade(con,int(tid),outcome,evidence);st.success('Recorded supplied outcome; evidence was NOT independently verified.');st.rerun()
                except Exception as e:st.error(str(e))
    else:st.info('No paper trades recorded yet.')
with testing:
    st.subheader('Historical research & chronological calibration')
    st.warning('The built-in training labels use Binance/Coinbase 15-minute SPOT PROXY closes, NOT official Polymarket outcomes. This cannot prove a profitable trading edge. Never treat this as a live deployable model.')
    mode=st.radio('Historical data',['Download Binance 1m candles','Upload CSV','Use current feed'],horizontal=True)
    hist=None
    if mode=='Download Binance 1m candles':
        days=st.slider('History length (days)',3,60,14)
        if st.button('Download historical candles'):
            try:
                with st.spinner('Downloading pages of historical candles…'):
                    bar=st.progress(0.0)
                    hist=history_binance(days,progress=lambda p:bar.progress(p))
                    st.session_state['historical']=hist
                st.success(f'Downloaded {len(hist):,} candles')
            except Exception as e:st.error('Download failed: '+str(e))
        hist=st.session_state.get('historical')
    elif mode=='Upload CSV':
        file=st.file_uploader('1-minute OHLCV CSV: ts,open,high,low,close,volume',type='csv')
        if file:
            try:
                hist=pd.read_csv(file)
                hist['ts']=pd.to_datetime(hist.ts,utc=True)
                for c in ('open','high','low','close','volume'):hist[c]=pd.to_numeric(hist[c],errors='raise')
                hist=hist.sort_values('ts').drop_duplicates('ts')
            except Exception as e:st.error('CSV validation failed: '+str(e));hist=None
    else:hist=btc
    if hist is not None:
        st.write(f'{len(hist):,} candles available · {hist.ts.min()} through {hist.ts.max()}')
        st.download_button('Download research candles CSV',hist.to_csv(index=False).encode(),'btc_1m_research.csv','text/csv')
        if st.button('Run 60/20/20 chronological train / calibration / holdout'):
            try:
                with st.spinner('Training and evaluating…'):
                    result,error=research_backtest(hist)
                if error:st.warning(error)
                else:st.session_state['research_result']=result
            except Exception as e:st.error(str(e))
    result=st.session_state.get('research_result')
    if result:
        st.subheader('Untouched holdout metrics (spot proxy)')
        st.json(result['metrics'])
        st.caption('Calibration is trained only on the middle 20%; final holdout is the last 20%. No backtest ROI is reported because historical executable Polymarket quotes and official labels are absent.')
        pred=result['predictions'];st.line_chart(pred.set_index('ts')[['prob_up','actual_up']])
        st.subheader('Reliability diagram data')
        reliability=reliability_table(pred)
        st.dataframe(reliability,use_container_width=True,hide_index=True)
        st.download_button('Export holdout predictions',pred.to_csv(index=False).encode(),'btc15_proxy_holdout.csv','text/csv')
        st.caption('Holdout score is descriptive only; hyperparameter selection or repeated tuning on the same holdout invalidates its independence.')
    st.divider()
    st.subheader('Settlement-matched prediction audit (uploaded data)')
    st.caption('Optional independent dataset with one or more historical prediction snapshots per market. CSV columns: timestamp, slug, prob_up, up_ask, down_ask, actual_up, seconds_left. Outcomes must be official; asks must be timestamped executable quotes; probabilities must be truly out-of-sample. The app cannot verify uploaded provenance.')
    predictions_csv=st.file_uploader('Upload independently collected market predictions',type='csv',key='market_predictions')
    if predictions_csv is not None and st.button('Audit settlement-matched prediction data'):
        try:
            raw=pd.read_csv(predictions_csv)
            metrics,executions,audit=evaluate_market_predictions(raw,fee_pct=fee_pct,min_edge=min_edge)
            st.json(metrics)
            st.dataframe(executions,use_container_width=True)
            st.download_button('Download audited paper entries',executions.to_csv(index=False).encode(),'audited_market_entries.csv','text/csv')
            st.warning('This audit assumes quoted asks were fillable. A positive simulated ROI does not establish deployable profitability. Verify outcome provenance and collect order-book depth and latency.')
        except Exception as e:st.error('Audit rejected: '+str(e))
with health:
    st.subheader('Data provenance & operational health')
    st.json({'checked_at_utc':str(now),'spot_source':source,'spot_quality':quality,
             'market_slug':market['slug'] if market else None,
             'reference_status':market['reference_grade'] if market else 'UNAVAILABLE',
             'reference_source':market['reference_source'] if market else None,
             'up_quote_time':up['observed_at'] if up else None,
             'down_quote_time':down['observed_at'] if down else None,
             'market_active':market['active'] if market else None,
             'api_errors':errors})
    st.write('**Safety gates:** completed candles only; gap/staleness checks; source-reported strike must exist; no live model recommendation without settlement-matched calibration; no wallet or execution API.')
    st.caption('Polling latency is nonzero; this is not a tick-synchronized feed. Website API strike is not cryptographic oracle verification. Streamlit restarts and ephemeral hosting can erase local SQLite state.')
    snaps=pd.read_sql_query('SELECT * FROM snapshots ORDER BY id DESC LIMIT 1000',con)
    st.metric('Captured market snapshots',len(snaps))
    if not snaps.empty:
        st.dataframe(snaps.head(50),hide_index=True,use_container_width=True)
        st.download_button('Export market snapshots CSV',snaps.to_csv(index=False).encode(),'btc15_market_snapshots.csv','text/csv')
    st.write('**Production readiness checklist**')
    for item in ['Acquire independently verifiable Chainlink settlement data and market-specific rule version',
                 'Capture tick-level oracle, spot and CLOB streams with monotonic timestamps',
                 'Collect historical executable depth and official resolution labels',
                 'Use rolling walk-forward validation, confidence intervals, drift monitoring and a never-touched holdout',
                 'Calibrate actual contract outcomes and verify positive cost-adjusted expected value',
                 'Implement realistic latency, spread, slippage, fee schedules, partial fills and downtime scenarios',
                 'Move persistent storage to a managed database and add uptime monitoring']:
        st.checkbox(item,value=False,disabled=True)

if market and up and down and quality['ok'] and spot and z:
    try:record_snapshot(con,market,spot,source,up,down,z)
    except Exception as e:st.warning('Snapshot logging failed: '+str(e))
con.close()
st.caption('No real-money execution · No guaranteed predictions · Quotes may be stale · Historical proxy metrics are not verified Polymarket performance')
# Streamlit autorefresh handles reruns; avoid blocking the rest of the app.

# V3 persistent collector, walk-forward diagnostics and conservative signal governance.
from production import open_db as open_operations_db, summary as operations_summary, audit_observations, rolling_proxy, signal_gate
st.divider()
st.header('🛰️ V3 — Persistent Intelligence & Validation Center')
st.caption('Run collector.py separately for uninterrupted capture. This dashboard only reads persisted observations; a browser refresh is not a reliable data collector.')
operations_path=Path(__file__).with_name('data')/'observations.db'
operations_path.parent.mkdir(parents=True,exist_ok=True)
try:
    ops=open_operations_db(str(operations_path))
    stats=operations_summary(ops)
    k1,k2,k3,k4=st.columns(4)
    k1.metric('Persisted observations',stats['observations'] or 0)
    k2.metric('Distinct markets',stats['markets'] or 0)
    k3.metric('Quality-approved observations',stats['quality_passes'] or 0)
    k4.metric('Collector latest',str(stats['last_utc'] or 'NOT RUNNING')[:19])
    gate=signal_gate(market or {},quality,up,down,model_validated=False,stake=stake,fee_fraction=fee_pct,min_edge=min_edge)
    st.warning('**Production signal gate: '+gate['side']+'** · '+ '; '.join(gate['reasons']))
    with st.expander('Collected quote audit and export'):
        recent=pd.read_sql_query('SELECT * FROM observations ORDER BY captured_epoch DESC LIMIT 5000',ops)
        if not recent.empty:
            st.dataframe(recent.head(100),hide_index=True,use_container_width=True)
            st.download_button('Export timestamped observations',recent.to_csv(index=False).encode(),'btc15_collected_observations.csv','text/csv')
            bad=recent[recent.quality_ok==0]
            if not bad.empty:st.write('Most common quality rejections',bad.failure_reason.value_counts().head(10))
        else:st.info('No observations collected yet. Start the independent collector to populate this database.')
    with st.expander('Official outcome evidence registry (user-attested; NOT independently verified)'):
        st.caption('Outcomes are not automatically imported or cryptographically verified. Entries remain USER_ATTESTED and are never treated as validated training labels.')
        from production import evidence_outcome
        with st.form('outcome_evidence'):
            slug_input=st.text_input('Market slug',placeholder='btc-updown-15m-...')
            side_input=st.selectbox('Winning outcome',['UP','DOWN'])
            evidence_input=st.text_input('Official outcome evidence URL (HTTPS)')
            submitted=st.form_submit_button('Record user-attested outcome')
            if submitted:
                try:
                    if not slug_input.startswith('btc-updown-15m-'):raise ValueError('Invalid market slug')
                    evidence_outcome(ops,slug_input,side_input,evidence_input)
                    st.success('Outcome recorded as USER_ATTESTED, not oracle-verified.')
                except Exception as exc:st.error(str(exc))
        audited=audit_observations(ops)
        st.metric('Markets with quote + user-attested outcome',len(audited))
        if not audited.empty:st.download_button('Export matched evidence rows',audited.to_csv(index=False).encode(),'btc15_user_attested_audit.csv','text/csv')
    with st.expander('Expanding walk-forward research (spot proxy, uncalibrated)'):
        st.caption('This evaluates multiple forward-only time blocks and purges the boundary label. It does not validate Polymarket settlements or live contract profitability.')
        sample=st.session_state.get('historical')
        if sample is None:sample=btc
        if st.button('Run rolling historical diagnostics'):
            if sample is None:st.error('No historical candles available.')
            else:
                with st.spinner('Running walk-forward folds…'):
                    wf,err=rolling_proxy(sample)
                if err:st.warning(err)
                else:st.session_state['walk_forward_v3']=wf
        wf=st.session_state.get('walk_forward_v3')
        if wf:
            st.json(wf['metrics'])
            st.dataframe(wf['folds'],hide_index=True,use_container_width=True)
            st.download_button('Export out-of-sample fold predictions',wf['predictions'].to_csv(index=False).encode(),'btc15_walkforward_proxy.csv','text/csv')
    ops.close()
except Exception as exc:st.error('Operational database unavailable: '+str(exc))
