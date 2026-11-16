"""Client-side live chart: Coinbase public match feed, never settlement oracle."""
import json
import pandas as pd
import streamlit.components.v1 as components
from structure_overlay import overlays


def show_streaming_chart(btc, reference=None, height=650):
    bars=[]
    for row in btc.tail(220).itertuples():
        bars.append(dict(time=int(pd.Timestamp(row.ts).timestamp()),open=float(row.open),high=float(row.high),low=float(row.low),close=float(row.close)))
    overlay=overlays(btc)
    config=json.dumps({'bars':bars,'overlay':overlay,'reference':float(reference) if reference is not None else None}).replace('</','<\\/')
    html=r'''<!DOCTYPE html><html><head><meta charset="utf-8"><style>
    body{margin:0;background:#0b111b;color:#d9e6f2;font:13px system-ui,Arial}#bar{display:flex;gap:16px;align-items:center;padding:10px 12px;flex-wrap:wrap}#state{font-weight:700}#chart{height:535px;position:relative}#overlay{position:absolute;inset:0;pointer-events:none;z-index:2}#legend{padding:7px 12px;color:#9caec2;font-size:12px}.pill{background:#16263a;padding:5px 9px;border-radius:5px}
    </style></head><body><div id="bar"><b>BTC-USD • Coinbase match stream</b><span class="pill" id="state">CONNECTING</span><span id="price">—</span><span id="age">—</span><span id="flow">Aggressor flow: —</span><span id="tf">1-minute candles • live developing bar</span></div><div id="chart"><canvas id="overlay"></canvas></div><div id="legend">Shaded green/red: historical pivot demand/supply • translucent FVG bands: unfilled three-candle gaps • Arrows: historical closed-bar PAPER confirmations only. No real-money recommendation. Gold: unverified reference price.</div>
    <script src="https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script>
    <script>const cfg=__CONFIG__;
    const el=document.getElementById('chart'),state=document.getElementById('state'),p=document.getElementById('price'),age=document.getElementById('age'),flow=document.getElementById('flow');
    if(!window.LightweightCharts){state.textContent='CHART LIBRARY BLOCKED';throw Error('Chart library unavailable')}
    const chart=LightweightCharts.createChart(el,{width:el.clientWidth,height:535,layout:{background:{type:'solid',color:'#0b111b'},textColor:'#c7d3df'},grid:{vertLines:{color:'#1a2633'},horzLines:{color:'#1a2633'}},timeScale:{timeVisible:true,secondsVisible:true,borderColor:'#273646'},rightPriceScale:{borderColor:'#273646'},crosshair:{mode:LightweightCharts.CrosshairMode.Normal}});
    const candles=chart.addCandlestickSeries({upColor:'#1ac784',downColor:'#ef5350',borderVisible:false,wickUpColor:'#1ac784',wickDownColor:'#ef5350',priceFormat:{type:'price',precision:2,minMove:.01}});
    const bars=cfg.bars.slice().sort((a,b)=>a.time-b.time);candles.setData(bars);chart.timeScale().fitContent();
    candles.setMarkers(cfg.overlay.markers.filter(m=>bars.some(b=>b.time===m.time)).sort((a,b)=>a.time-b.time));
    const canvas=document.getElementById('overlay'),ctx=canvas.getContext('2d');
    function drawOverlay(){const rect=el.getBoundingClientRect(),dpr=window.devicePixelRatio||1;
      canvas.width=Math.round(rect.width*dpr);canvas.height=Math.round(rect.height*dpr);
      canvas.style.width=rect.width+'px';canvas.style.height=rect.height+'px';ctx.setTransform(dpr,0,0,dpr,0,0);
      for(const z of [...cfg.overlay.zones,...cfg.overlay.fvgs]){
        const y1=candles.priceToCoordinate(z.high),y2=candles.priceToCoordinate(z.low);
        if(y1===null||y2===null)continue;
        const x0=chart.timeScale().timeToCoordinate(z.start);
        const left=x0===null?0:Math.max(0,x0),width=Math.max(0,rect.width-left-65);
        if(width<=0)continue;
        const demand=z.kind==='demand',bull=z.kind==='bull';const green=demand||bull;
        ctx.fillStyle=green?'rgba(24,185,125,0.14)':'rgba(244,79,98,0.14)';
        ctx.strokeStyle=green?'rgba(35,217,151,0.55)':'rgba(255,91,109,0.55)';
        ctx.fillRect(left,Math.min(y1,y2),width,Math.max(2,Math.abs(y2-y1)));
        ctx.strokeRect(left,Math.min(y1,y2),width,Math.max(2,Math.abs(y2-y1)));
        ctx.fillStyle=green?'#5ce8b0':'#ff8794';ctx.font='10px system-ui';
        ctx.fillText(z.kind==='demand'?'DEMAND':z.kind==='supply'?'SUPPLY':green?'BULL FVG':'BEAR FVG',Math.max(left+4,rect.width-148),Math.max(12,Math.min(y1,y2)-3));
      }
    }
    chart.timeScale().subscribeVisibleTimeRangeChange(drawOverlay);
    setTimeout(drawOverlay,250);
    if(cfg.reference)candles.createPriceLine({price:cfg.reference,color:'#eab308',lineWidth:1,lineStyle:LightweightCharts.LineStyle.Dashed,axisLabelVisible:true,title:'PRICE TO BEAT (SOURCE)'});
    let last=bars[bars.length-1],lastTick=0,ws=null,attempt=0,buy=0,sell=0,windowStart=Date.now(),latestTradeId=0;
    const minute=t=>Math.floor(t/60)*60;
    function onTrade(m){const ts=Date.parse(m.time)/1000,px=Number(m.price),size=Number(m.size);if(!Number.isFinite(ts)||!Number.isFinite(px)||!Number.isFinite(size)||px<=0)return;
      const id=Number(m.trade_id);if(Number.isFinite(id)&&id<=latestTradeId)return;if(Number.isFinite(id))latestTradeId=id;
      const t=minute(ts);if(t<last.time)return;
      if(t>last.time){last={time:t,open:last.close,high:px,low:px,close:px};}else{last={...last,high:Math.max(last.high,px),low:Math.min(last.low,px),close:px};}
      candles.update(last);drawOverlay();lastTick=Date.now();p.textContent='$'+px.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
      if(Date.now()-windowStart>60000){buy=0;sell=0;windowStart=Date.now();}if(m.side==='sell')buy+=px*size;else if(m.side==='buy')sell+=px*size;
      const total=buy+sell;flow.textContent=total?'60s aggressor buy share: '+(100*buy/total).toFixed(1)+'%':'Aggressor flow: —';}
    function connect(){state.textContent='CONNECTING';ws=new WebSocket('wss://ws-feed.exchange.coinbase.com');
      ws.onopen=()=>{attempt=0;state.textContent='LIVE • WEBSOCKET';state.style.color='#1ac784';ws.send(JSON.stringify({type:'subscribe',product_ids:['BTC-USD'],channels:['matches','heartbeat']}));};
      ws.onmessage=e=>{let m;try{m=JSON.parse(e.data)}catch{return}if(m.type==='match'||m.type==='last_match')onTrade(m)};
      ws.onerror=()=>{state.textContent='FEED ERROR';state.style.color='#ef5350'};
      ws.onclose=()=>{state.textContent='DISCONNECTED • RECONNECTING';state.style.color='#ef5350';setTimeout(connect,Math.min(30000,1000*2**Math.min(attempt++,5)))};}
    connect();setInterval(()=>{age.textContent=lastTick?'Last trade '+((Date.now()-lastTick)/1000).toFixed(1)+'s ago':'Waiting for trades';if(lastTick&&Date.now()-lastTick>12000){state.textContent='STALE FEED';state.style.color='#eab308'}},500);
    new ResizeObserver(()=>{chart.applyOptions({width:el.clientWidth});drawOverlay()}).observe(el);
    window.addEventListener('pagehide',()=>{if(ws)ws.close()});
    </script></body></html>'''.replace('__CONFIG__',config)
    components.html(html,height=height,scrolling=False)
