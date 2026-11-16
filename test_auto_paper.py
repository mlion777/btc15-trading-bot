from auto_paper import evaluate

def fixtures():
 m={'active':True,'accepting_orders':True,'reference':74000,'reference_grade':'SOURCE_REPORTED','seconds_left':500}
 q={'ok':True};ob={'fillable':True,'vwap':.5,'spread':.02,'bid':.48}
 o={'side':'UP','votes':{'UP':4,'DOWN':1}}
 return m,q,ob,o

def test_good_paper_candidate():
 m,q,ob,o=fixtures()
 candidate,reasons=evaluate(o,m,q,ob,ob,2)
 assert candidate['side']=='UP' and not reasons

def test_stale_feed_blocks():
 m,q,ob,o=fixtures()
 candidate,reasons=evaluate(o,m,q,ob,ob,22)
 assert candidate is None and any('stale' in r for r in reasons)

def test_weak_signal_blocks():
 m,q,ob,o=fixtures();o['votes']['UP']=3
 assert evaluate(o,m,q,ob,ob,2)[0] is None

def test_wide_spread_blocks():
 m,q,ob,o=fixtures();ob['spread']=.2
 assert evaluate(o,m,q,ob,ob,2)[0] is None
