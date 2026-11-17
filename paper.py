"""Paper BTC spot/short P&L simulator, NOT a Polymarket contract execution simulator."""
import sqlite3, time
from pathlib import Path
DB=Path(__file__).with_name('paper_trades.sqlite3')

def connect():
    db=sqlite3.connect(str(DB),timeout=5)
    db.execute('CREATE TABLE IF NOT EXISTS positions (id INTEGER PRIMARY KEY, side TEXT, entry_ts REAL, entry_price REAL, qty REAL, stake REAL, status TEXT, exit_ts REAL, exit_price REAL, pnl REAL, reason TEXT, entry_reason TEXT)')
    db.commit();return db

def run(side,price,reason,now=None,stake=10.0,fee_bps=8,slippage_bps=3):
    """At most one position; 0.8% target, 0.55% stop, max 4 minutes; no guaranteed hold."""
    now=time.time() if now is None else now
    db=connect(); open_pos=db.execute("SELECT id,side,entry_ts,entry_price,qty,stake FROM positions WHERE status='OPEN' ORDER BY id DESC LIMIT 1").fetchone()
    action=None
    if open_pos:
        pid,old_side,t0,entry,qty,initial=open_pos
        raw=(price-entry)/entry*(1 if old_side=='UP' else -1)
        # Conservatively charge both entry and exit slippage and fees.
        net=raw-2*(fee_bps+slippage_bps)/10000
        why='TAKE PROFIT' if net>=.008 else 'STOP LOSS' if net<=-.0055 else 'TIME EXIT' if now-t0>=240 else 'TREND REVERSAL' if side not in (old_side,'WAIT') and now-t0>=15 else None
        if why:
            pnl=initial*net
            db.execute('UPDATE positions SET status=?,exit_ts=?,exit_price=?,pnl=?,reason=? WHERE id=?',('CLOSED',now,price,pnl,why,pid));db.commit()
            action=f'EXIT {old_side} • {why} • ${pnl:+.2f}'
            open_pos=None
    if not open_pos and side in ('UP','DOWN'):
        # Avoid immediate re-entry in same minute or after exit on same tick.
        last=db.execute('SELECT max(entry_ts) FROM positions').fetchone()[0]
        if (last is None or now-last>=60) and not action:
            qty=stake/price
            db.execute('INSERT INTO positions (side,entry_ts,entry_price,qty,stake,status,entry_reason) VALUES (?,?,?,?,?,?,?)',(side,now,price,qty,stake,'OPEN',reason));db.commit()
            action=f'PAPER {side} • ${stake:.2f} • ${price:,.2f}'
    row=db.execute("SELECT side,entry_price,stake,entry_reason FROM positions WHERE status='OPEN' ORDER BY id DESC LIMIT 1").fetchone()
    stats=db.execute("SELECT count(*),coalesce(sum(pnl),0),coalesce(sum(case when pnl>0 then 1 else 0 end),0) FROM positions WHERE status='CLOSED'").fetchone()
    history=db.execute("SELECT side,entry_ts,entry_price,exit_ts,exit_price,pnl,reason FROM positions ORDER BY id DESC LIMIT 25").fetchall()
    db.close()
    return {'open':row,'stats':stats,'history':history,'action':action}
