"""Run independently of Streamlit: python collector.py --interval 10 --db /data/observations.db"""
import argparse, logging, signal, time
from pathlib import Path
from advanced import market_bundle,detailed_book,spot_quality,zones
from engine import candles
from production import open_db,capture

running=True
def stop(*_):
    global running
    running=False

def run(interval,db,stake):
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    con=open_db(db)
    logging.info('Starting persistent snapshot collector; market reference is not independently oracle-verified')
    while running:
        started=time.monotonic()
        try:
            market=market_bundle();frame,source=candles()
            quality=spot_quality(frame)
            z=zones(frame)
            up=detailed_book(market['up'],stake)
            down=detailed_book(market['down'],stake)
            result=capture(con,market,z.get('spot'),source,quality,up,down)
            logging.info('%s | quality=%s | reasons=%s',market['slug'],result['ok'],result['reasons'])
        except Exception:
            logging.exception('Collector cycle failed; no fabricated data written')
        wait=max(0.1,interval-(time.monotonic()-started))
        if running:time.sleep(wait)
    con.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--interval',type=float,default=10)
    p.add_argument('--db',default='data/observations.db');p.add_argument('--stake',type=float,default=10)
    a=p.parse_args()
    if a.interval<5 or a.stake<=0:p.error('interval must be >=5 seconds and stake positive')
    Path(a.db).parent.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    run(a.interval,a.db,a.stake)
