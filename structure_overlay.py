"""Causal, closed-candle FVGs and confirmed setup markers. Research only."""
import pandas as pd
from confirmations import confirm_setup
from reversals import reversal_setup
from microstructure import supply_demand_zones


def overlays(df, max_bars=220):
    if df is None or len(df)<60:
        return {'zones': [], 'fvgs': [], 'markers': []}
    x = df.sort_values('ts').drop_duplicates('ts').tail(max_bars).reset_index(drop=True)
    # Last candle is treated as provisional and never used to confirm a signal.
    closed = x.iloc[:-1].copy()
    def ts(i): return int(pd.Timestamp(closed.ts.iloc[i]).timestamp())
    zones = []
    for kind, entries in supply_demand_zones(closed).items():
        for z in entries:
            zones.append({'kind':kind,'low':float(z['low']),'high':float(z['high']), 'start':int(pd.Timestamp(z['ts']).timestamp())})
    fvgs=[]
    for i in range(2,len(closed)):
        lo0, hi0=float(closed.low.iloc[i-2]),float(closed.high.iloc[i-2])
        lo2, hi2=float(closed.low.iloc[i]),float(closed.high.iloc[i])
        if lo2>hi0: kind='bull'; low=hi0; high=lo2
        elif hi2<lo0: kind='bear';low=hi2;high=lo0
        else:continue
        # Show only gaps not completely filled by subsequent CLOSED bars.
        if kind=='bull' and any(float(v)<=low for v in closed.low.iloc[i+1:]):continue
        if kind=='bear' and any(float(v)>=high for v in closed.high.iloc[i+1:]):continue
        fvgs.append({'kind':kind,'low':low,'high':high,'start':ts(i)})
    markers=[]
    # The full trailing history is recomputed for each candle, avoiding future leakage.
    for i in range(60,len(closed)):
        history=closed.iloc[:i+1]
        for side in ('UP','DOWN'):
            r=confirm_setup(history,side)
            if r['ok']:
                markers.append({'time':ts(i),'position':'belowBar' if side=='UP' else 'aboveBar',
                                'color':'#25d998' if side=='UP' else '#ff6575',
                                'shape':'arrowUp' if side=='UP' else 'arrowDown',
                                'text':'PAPER LONG' if side=='UP' else 'PAPER SHORT'})
                break
    # Separate reversal annotations from trend-following confirmations.
    # The marker is placed on the candle whose close first satisfied the rules.
    for i in range(35,len(closed)):
        history=closed.iloc[:i+1]
        for side in ('UP','DOWN'):
            result=reversal_setup(history,side)
            if result['confirmed']:
                markers.append({'time':ts(i),'position':'belowBar' if side=='UP' else 'aboveBar',
                                'color':'#45d5f7' if side=='UP' else '#ffb347',
                                'shape':'arrowUp' if side=='UP' else 'arrowDown',
                                'text':'REV LONG' if side=='UP' else 'REV SHORT'})
                break
    return {'zones':zones[-6:],'fvgs':fvgs[-12:],'markers':sorted(markers,key=lambda m:m['time'])[-55:]}
