"""Idempotent paper-only contract scalper. No credentials or real orders."""
import sqlite3, time, json
from pathlib import Path

DB=Path(__file__).with_name('auto_paper.db')

def db(path=None):
    c=sqlite3.connect(str(path or DB), timeout=10)
    c.execute('PRAGMA busy_timeout=10000')
    c.execute('''CREATE TABLE IF NOT EXISTS auto_positions(id INTEGER PRIMARY KEY, market TEXT NOT NULL UNIQUE,
       side TEXT, token TEXT, opened REAL, expires REAL, stake REAL, shares REAL, entry REAL,
       fee_in REAL, exit_price REAL, fee_out REAL, pnl REAL, state TEXT, reason TEXT, exit_reason TEXT)''')
    c.commit();return c

def evaluate(opportunity, market, quality, up, down, tick_age, max_spread=.08, fee_rate=.01,
             min_votes=4, min_margin=2, min_seconds=120, max_seconds=780):
    reasons=[]
    if not market: return None,['Market unavailable']
    if not market.get('active') or not market.get('accepting_orders'):reasons.append('Market not accepting orders')
    if not market.get('reference') or market.get('reference_grade')=='UNAVAILABLE':reasons.append('Price to beat unavailable')
    if not quality.get('ok'):reasons.append('Spot candle quality failed')
    if tick_age is None or tick_age>15 or tick_age<0:reasons.append('Recent Coinbase trade is stale or missing')
    seconds=float(market.get('seconds_left') or 0)
    if not min_seconds<=seconds<=max_seconds:reasons.append('Outside entry window (2–13 minutes remaining)')
    side=opportunity.get('side'); votes=opportunity.get('votes') or {}
    if side not in ('UP','DOWN'):reasons.append('No directional setup')
    elif votes.get(side,0)<min_votes or votes.get(side,0)-votes.get('DOWN' if side=='UP' else 'UP',0)<min_margin:
        reasons.append('Trend/reversal confirmations not strong enough')
    ob=(up if side=='UP' else down) if side else None
    if not ob or not ob.get('fillable'):reasons.append('Insufficient order-book liquidity')
    else:
        ask=ob.get('vwap'); spread=ob.get('spread')
        if ask is None or not .08<=float(ask)<=.82:reasons.append('Entry price outside 8–82 cents')
        if spread is None or spread<0 or spread>max_spread:reasons.append('Spread too wide')
        if ob.get('bid') is None:reasons.append('No executable exit bid')
    if reasons:return None,reasons
    return {'side':side,'ob':ob,'reason':f"Technical votes {votes}; strong directional alignment or confirmed reversal. Simulated only."},[]

def tick(market, opportunity, quality, up, down, tick_age, stake=10,fee_rate=.01,
         max_spread=.08, enabled=True, min_votes=4):
    """Call on each refresh. Uses UNIQUE market to avoid repeat entries across sessions."""
    c=db();now=time.time();events=[]
    try:
        rows=c.execute("SELECT id,side,shares,entry,stake,fee_in,expires FROM auto_positions WHERE state='OPEN'").fetchall()
        for ident,side,shares,entry,cost,fee_in,expires in rows:
            ob=up if side=='UP' else down
            bid=ob.get('bid') if ob and market and market.get('slug')==c.execute('SELECT market FROM auto_positions WHERE id=?',(ident,)).fetchone()[0] else None
            if bid is not None and 0<float(bid)<=1:
                # Conservative: sell into bid, and deduct assumed fee on proceeds.
                net=shares*float(bid)*(1-fee_rate)-cost-fee_in
                target=max(.045,2*(ob.get('spread') or .02))
                if net>=cost*.08:exit_reason='TAKE PROFIT'
                elif net<=-cost*.10:exit_reason='STOP LOSS'
                elif now>=expires-75:exit_reason='EXIT BUFFER'
                else:exit_reason=None
                if exit_reason:
                    c.execute('UPDATE auto_positions SET state=?,exit_price=?,fee_out=?,pnl=?,exit_reason=? WHERE id=?',
                              ('CLOSED',float(bid),shares*float(bid)*fee_rate,net,exit_reason,ident));events.append(exit_reason)
            elif now>=expires:
                c.execute("UPDATE auto_positions SET state='AWAITING_OFFICIAL_SETTLEMENT',exit_reason='No valid exit quote before expiry' WHERE id=?",(ident,))
                events.append('Unresolved: needs official settlement')
        c.commit()
        candidate,reasons=evaluate(opportunity,market,quality,up,down,tick_age,max_spread,fee_rate,min_votes)
        if not enabled:reasons=['Auto paper trading paused']
        if enabled and candidate and not c.execute("SELECT 1 FROM auto_positions WHERE state='OPEN' LIMIT 1").fetchone():
            side=candidate['side'];ob=candidate['ob'];entry=float(ob['vwap']);shares=float(stake)/entry
            try:
                c.execute('INSERT INTO auto_positions(market,side,token,opened,expires,stake,shares,entry,fee_in,state,reason) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                          (market['slug'],side,market['up'] if side=='UP' else market['down'],now,market['end'],stake,shares,entry,stake*fee_rate,'OPEN',candidate['reason']))
                c.commit();events.append(f'OPENED PAPER {side} at {entry:.3f}')
            except sqlite3.IntegrityError:reasons=['Already traded this 15-minute market']
        elif candidate and enabled:reasons=['Another paper position is already open']
        rows=c.execute('SELECT id,market,side,opened,stake,shares,entry,state,pnl,reason,exit_reason FROM auto_positions ORDER BY id DESC LIMIT 100').fetchall()
        cols=['id','market','side','opened','stake','shares','entry','state','pnl','reason','exit_reason']
        return {'events':events,'blocked':reasons,'positions':[dict(zip(cols,r)) for r in rows]}
    finally:c.close()
